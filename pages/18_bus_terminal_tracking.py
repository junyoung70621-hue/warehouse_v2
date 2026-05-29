# pages/18_bus_terminal_tracking.py
import io
import re
import uuid
from datetime import date, datetime, timedelta, timezone

_KST = timezone(timedelta(hours=9))

def _now_kst() -> datetime:
    return datetime.now(_KST)

def _today_kst() -> date:
    return datetime.now(_KST).date()

def _ts(ts_str) -> str:
    """Supabase UTC 타임스탬프 → KST 표시 문자열 (YYYY-MM-DD HH:MM)"""
    if not ts_str:
        return ""
    try:
        dt = datetime.fromisoformat(str(ts_str))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(_KST).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return str(ts_str)[:16].replace("T", " ")

import pandas as pd
import streamlit as st

from utils.auth import is_role, require_login, logout
from utils.db import get_supabase
from utils.permissions import get_center as _get_center
from utils.ui import (
    apply_global_css,
    render_sidebar_header,
    render_sidebar_section,
    render_sidebar_user,
    render_top_bar,
)

st.set_page_config(
    page_title="에이텍모빌리티 자재관리",
    page_icon="favicon_32.png",
    layout="wide",
    initial_sidebar_state="expanded",
)

apply_global_css()
require_login()

user        = st.session_state.user
user_role   = user["role"]
user_center = _get_center(user)
user_name   = user.get("name") or user.get("username", "")
user_id     = user["id"]

_is_admin     = user_role == "admin"
_is_materials = user_role == "materials"
_can_manage   = _is_admin or _is_materials
_can_write    = user_role not in ("guest",)

TRACKING_CENTERS = ["강서센터", "강북센터", "강동센터", "강남센터"]
TABLE    = "bus_terminal_assignments"
TM_TABLE = "terminal_movements"

_SQL_SETUP = """\
-- Supabase SQL Editor에서 실행하세요 (최초 1회)
CREATE TABLE IF NOT EXISTS bus_terminal_assignments (
    id            uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
    ih_code       text        NOT NULL,
    device_type   text,
    sub_type      text,
    center        text        NOT NULL,
    employee_id   uuid        REFERENCES users(id) ON DELETE SET NULL,
    employee_name text        NOT NULL,
    assigned_at   timestamptz DEFAULT now(),
    assigned_by   uuid        REFERENCES users(id) ON DELETE SET NULL,
    status        text        NOT NULL DEFAULT 'holding'
                              CHECK (status IN ('holding', 'returned')),
    returned_at   timestamptz,
    notes         text
);
CREATE INDEX IF NOT EXISTS idx_bta_center   ON bus_terminal_assignments(center);
CREATE INDEX IF NOT EXISTS idx_bta_status   ON bus_terminal_assignments(status);
CREATE INDEX IF NOT EXISTS idx_bta_ih_code  ON bus_terminal_assignments(ih_code);
CREATE INDEX IF NOT EXISTS idx_bta_employee ON bus_terminal_assignments(employee_id);
"""


# ── DB ────────────────────────────────────────────────────────────────────────

def _table_exists() -> bool:
    try:
        get_supabase().table(TABLE).select("id").limit(1).execute()
        return True
    except Exception:
        return False


def fetch_assignments(center: str = None, status: str = None, employee_id: str = None) -> list:
    try:
        q = (
            get_supabase().table(TABLE)
            .select("id,ih_code,device_type,sub_type,center,"
                    "employee_id,employee_name,assigned_at,status,returned_at,notes")
            .order("assigned_at", desc=True)
        )
        if center:      q = q.eq("center",      center)
        if status:      q = q.eq("status",      status)
        if employee_id: q = q.eq("employee_id", employee_id)
        return q.limit(3000).execute().data or []
    except Exception:
        return []


def fetch_my_assignments(center: str, status: str = None) -> list:
    """본인 배정 조회 — employee_id 일치 OR (employee_id NULL AND employee_name 일치).
    초기 등록 시 계정 미매칭으로 employee_id가 NULL인 경우도 포함."""
    try:
        q = (
            get_supabase().table(TABLE)
            .select("id,ih_code,device_type,sub_type,center,"
                    "employee_id,employee_name,assigned_at,status,returned_at,notes")
            .eq("center", center)
            .order("assigned_at", desc=True)
        )
        if status:
            q = q.eq("status", status)
        all_rows = q.limit(3000).execute().data or []
        return [
            r for r in all_rows
            if r.get("employee_id") == user_id
            or (not r.get("employee_id") and r.get("employee_name") == user_name)
        ]
    except Exception:
        return []


def fetch_tm_out(center: str) -> dict:
    """terminal_movements 출고 레코드 (to_center=center). ih → 레코드."""
    try:
        rows = (
            get_supabase().table(TM_TABLE)
            .select("trcn_id,device_type,sub_type,upload_date")
            .eq("direction", "out")
            .eq("to_center", center)
            .limit(5000)
            .execute().data or []
        )
        out_map: dict = {}
        for r in rows:
            ih = r["trcn_id"]
            if ih not in out_map:
                out_map[ih] = r
        return out_map
    except Exception:
        return {}


def fetch_tm_in_ihs(center: str) -> set:
    """terminal_movements 입고(반납) 레코드 IH 집합 (from_center=center)."""
    try:
        rows = (
            get_supabase().table(TM_TABLE)
            .select("trcn_id")
            .eq("direction", "in")
            .eq("from_center", center)
            .limit(5000)
            .execute().data or []
        )
        return {r["trcn_id"] for r in rows}
    except Exception:
        return set()


def get_available_terminals(center: str) -> list:
    out_map      = fetch_tm_out(center)
    returned_ihs = fetch_tm_in_ihs(center)
    assigned_ihs = {
        r["ih_code"] for r in fetch_assignments(center=center)
        if r.get("status") in _ACTIVE_STATUSES
    }

    # terminal_movements 기반 가용 풀
    result = {
        ih: {
            "ih_code":     ih,
            "device_type": info.get("device_type", ""),
            "sub_type":    info.get("sub_type",    ""),
            "upload_date": str(info.get("upload_date", "")),
        }
        for ih, info in out_map.items()
        if ih not in returned_ihs and ih not in assigned_ihs
    }

    # 초기 등록 미배정(unassigned) 추가 — terminal_movements 없이 센터에 직접 등록된 것
    for r in fetch_assignments(center=center, status="unassigned"):
        ih = r["ih_code"]
        if ih not in returned_ihs and ih not in assigned_ihs and ih not in result:
            result[ih] = {
                "ih_code":     ih,
                "device_type": r.get("device_type") or "",
                "sub_type":    r.get("sub_type")    or "",
                "upload_date": str(r.get("assigned_at", ""))[:10],
            }

    return sorted(result.values(), key=lambda x: x["ih_code"])


def fetch_center_users(center: str) -> list:
    try:
        sb = get_supabase()
        r1 = (sb.table("users").select("id,name,username,role")
              .eq("assigned_center", center).eq("is_approved", True)
              .neq("role", "guest").execute().data or [])
        r2 = (sb.table("users").select("id,name,username,role")
              .eq("center",          center).eq("is_approved", True)
              .neq("role", "guest").execute().data or [])
        seen, result = set(), []
        for u in r1 + r2:
            if u["id"] not in seen:
                seen.add(u["id"])
                result.append(u)
        return result
    except Exception:
        return []


HIST_TABLE = "bus_terminal_history"

_ACTION_LABEL = {
    "assign":   "배정",
    "swap":     "불량 교체",
    "transfer": "직원 이동",
    "return":   "반납",
    "cancel":   "배정 취소",
    "init":     "초기 등록",
}


def _log(rows: list):
    """이력 테이블에 기록. 실패해도 무시."""
    if not rows:
        return
    try:
        get_supabase().table(HIST_TABLE).insert(rows).execute()
    except Exception:
        pass


def assign_terminals(ih_list: list, center: str, target_id: str, target_name: str, assigner_id: str) -> int:
    now = _now_kst().isoformat()
    sb  = get_supabase()

    # unassigned 레코드가 이미 있으면 update, 없으면 insert
    unassigned_map = {
        r["ih_code"]: r["id"]
        for r in fetch_assignments(center=center, status="unassigned")
    }

    to_update = [item for item in ih_list if item["ih_code"] in unassigned_map]
    to_insert = [item for item in ih_list if item["ih_code"] not in unassigned_map]

    try:
        for item in to_update:
            sb.table(TABLE).update({
                "employee_id":   target_id,
                "employee_name": target_name,
                "assigned_at":   now,
                "assigned_by":   assigner_id,
                "status":        "holding",
            }).eq("id", unassigned_map[item["ih_code"]]).execute()

        records = [
            {
                "id":            str(uuid.uuid4()),
                "ih_code":       item["ih_code"],
                "device_type":   item.get("device_type") or None,
                "sub_type":      item.get("sub_type")    or None,
                "center":        center,
                "employee_id":   target_id,
                "employee_name": target_name,
                "assigned_at":   now,
                "assigned_by":   assigner_id,
                "status":        "holding",
            }
            for item in to_insert
        ]
        if records:
            sb.table(TABLE).insert(records).execute()
        actor_name = user.get("name") or user.get("username", "")
        _log([{
            "center":        center,
            "action":        "assign",
            "ih_code":       item["ih_code"],
            "device_type":   item.get("device_type") or None,
            "sub_type":      item.get("sub_type")    or None,
            "to_employee":   target_name,
            "from_status":   "unassigned" if item["ih_code"] in unassigned_map else None,
            "to_status":     "holding",
            "acted_by":      assigner_id,
            "acted_by_name": actor_name,
            "acted_at":      now,
        } for item in ih_list])
        return len(ih_list)  # to_update + to_insert 모두 포함
    except Exception as e:
        st.error(f"배정 저장 실패: {e}")
        return 0


def return_terminals(assignment_ids: list, records_meta: list = None) -> bool:
    """
    센터로 반납:
      - 양품(holding)   → returned        (센터 가용풀로 복귀)
      - 불량(defective) → center_defective (센터보관 대기)
    records_meta: [{"ih_code","device_type","sub_type","employee_name","status"}, ...]
    """
    if not assignment_ids:
        return False
    try:
        sb  = get_supabase()
        now = _now_kst().isoformat()
        actor_name = user.get("name") or user.get("username", "")
        sb.table(TABLE).update({"status": "returned",         "returned_at": now}) \
          .in_("id", assignment_ids).eq("status", "holding").execute()
        sb.table(TABLE).update({"status": "center_defective", "returned_at": now}) \
          .in_("id", assignment_ids).eq("status", "defective").execute()
        if records_meta:
            _log([{
                "center":        r.get("center", ""),
                "action":        "return",
                "ih_code":       r["ih_code"],
                "device_type":   r.get("device_type"),
                "sub_type":      r.get("sub_type"),
                "from_employee": r.get("employee_name"),
                "from_status":   r.get("status"),
                "to_status":     "returned" if r.get("status") == "holding" else "center_defective",
                "acted_by":      user_id,
                "acted_by_name": actor_name,
                "acted_at":      now,
            } for r in records_meta])
        return True
    except Exception as e:
        st.error(f"반납 처리 실패: {e}")
        return False


def clear_center_assignments(center: str) -> int:
    """센터의 보유중 배정 전체 삭제. 삭제 건수 반환."""
    try:
        rows = fetch_assignments(center=center, status="holding")
        if not rows:
            return 0
        ids = [r["id"] for r in rows]
        get_supabase().table(TABLE).delete().in_("id", ids).execute()
        return len(ids)
    except Exception as e:
        st.error(f"초기화 실패: {e}")
        return -1


def bulk_register(records: list) -> int:
    """초기 일괄 등록. 저장 건수 반환."""
    try:
        get_supabase().table(TABLE).insert(records).execute()
        actor_name = user.get("name") or user.get("username", "")
        now = _now_kst().isoformat()
        _log([{
            "center":        r["center"],
            "action":        "init",
            "ih_code":       r["ih_code"],
            "device_type":   r.get("device_type"),
            "sub_type":      r.get("sub_type"),
            "to_employee":   r["employee_name"],
            "to_status":     "holding",
            "acted_by":      user_id,
            "acted_by_name": actor_name,
            "acted_at":      now,
        } for r in records])
        return len(records)
    except Exception as e:
        st.error(f"저장 실패: {e}")
        return 0


def classify_terminal(raw) -> tuple:
    """IH → (기종, 유형). 버스단말기 현황과 동일한 분류 규칙."""
    s = str(raw).strip()
    try:
        s = str(int(float(s)))
    except (ValueError, OverflowError):
        pass
    digits = "".join(c for c in s if c.isdigit())
    if not digits:
        return "미분류", "알 수 없음"
    n = len(digits)
    if n in (8, 9):
        if digits.startswith("157"):  return "한강버스", "승하차"
        if digits.startswith("1560"): return "B800", "승하차"
        if digits.startswith("1553"): return "B710", "승하차"
        if digits.startswith("1551"): return "B620", "승하차"
        if digits.startswith("1451"): return "B620", "운전자"
    if n == 9:
        if digits.startswith("5600"): return "B800", "표출기"
        if digits.startswith("5500"): return "B800", "통합단말기"
        if digits.startswith("457"):  return "한강버스", "표출기"
        if digits.startswith("447"):  return "한강버스", "통합단말기"
        if digits.startswith("4550"): return "B710", "표출기"
        if digits.startswith("4450"): return "B710", "통합단말기"
        if digits.startswith("4500"): return "B700", "표출기"
        if digits.startswith("4400"): return "B700", "통합단말기"
    if n == 6:
        if digits.startswith("10"):
            if 100001 <= int(digits) <= 100500: return "B620", "모뎀"
            else:                               return "B800", "모뎀"
        if digits.startswith("6"):              return "B710", "모뎀"
        if digits.startswith("4") or digits.startswith("5"): return "B700", "모뎀"
        if digits.startswith("1"):              return "B620", "모뎀"
    return "미분류", "알 수 없음"


_STATUS_LABEL = {
    "unassigned":       "미배정(센터보관)",
    "holding":          "양품 보유중",
    "defective":        "불량 보유중",
    "center_defective": "불량(센터보관)",
    "exchanged":        "교체 완료",
    "returned":         "반납 완료",
}

# 가용풀에서 제외할 활성 상태 — unassigned 제외(가용풀에 표시됨)
_ACTIVE_STATUSES = {"holding", "defective", "center_defective", "exchanged"}

_SQL_MIGRATE = """\
-- 기존 테이블 상태값 확장 (최초 1회)
ALTER TABLE bus_terminal_assignments DROP CONSTRAINT IF EXISTS bus_terminal_assignments_status_check;
ALTER TABLE bus_terminal_assignments ADD CONSTRAINT bus_terminal_assignments_status_check
    CHECK (status IN ('holding', 'defective', 'exchanged', 'returned'));
"""


def swap_terminal(holding_id: str, defective_ih: str, center: str, employee_id: str,
                  employee_name: str, orig_ih: str = "", orig_status: str = "holding",
                  orig_dtype: str = "", orig_stype: str = "") -> bool:
    try:
        sb  = get_supabase()
        now = _now_kst().isoformat()
        actor_name = user.get("name") or user.get("username", "")
        sb.table(TABLE).update({"status": "exchanged", "returned_at": now}) \
          .eq("id", holding_id).execute()
        # 불량 단말기 기종 결정: orig 기종 있으면 그대로, 없으면 IH로 자동 분류
        def_dtype = orig_dtype or ""
        def_stype = orig_stype or ""
        if not def_dtype:
            _ad, _as = classify_terminal(defective_ih)
            if _ad != "미분류":
                def_dtype, def_stype = _ad, _as
        sb.table(TABLE).insert({
            "id":            str(uuid.uuid4()),
            "ih_code":       defective_ih,
            "device_type":   def_dtype or None,
            "sub_type":      def_stype or None,
            "center":        center,
            "employee_id":   employee_id or user_id,
            "employee_name": employee_name,
            "assigned_at":   now,
            "assigned_by":   user_id,
            "status":        "defective",
        }).execute()
        _log([{
            "center":        center,
            "action":        "swap",
            "ih_code":       orig_ih,
            "device_type":   orig_dtype or None,
            "sub_type":      orig_stype or None,
            "from_employee": employee_name,
            "from_status":   orig_status,
            "to_status":     "exchanged",
            "extra_ih":      defective_ih,
            "acted_by":      user_id,
            "acted_by_name": actor_name,
            "acted_at":      now,
        }])
        return True
    except Exception as e:
        st.error(f"교체 처리 실패: {e}")
        return False


TRANSFER_TABLE = "bus_terminal_transfer_requests"


def fetch_center_emails(center: str) -> list:
    """해당 센터 전체 인원 이메일 목록."""
    try:
        sb = get_supabase()
        r1 = sb.table("users").select("email").eq("assigned_center", center).eq("is_approved", True).neq("role", "guest").execute().data or []
        r2 = sb.table("users").select("email").eq("center",          center).eq("is_approved", True).neq("role", "guest").execute().data or []
        seen, result = set(), []
        for u in r1 + r2:
            e = u.get("email", "")
            if e and e not in seen:
                seen.add(e); result.append(e)
        return result
    except Exception:
        return []


def fetch_transfer_requests(center: str) -> list:
    try:
        res = (
            get_supabase().table(TRANSFER_TABLE)
            .select("*")
            .or_(f"from_center.eq.{center},to_center.eq.{center}")
            .order("requested_at", desc=True)
            .limit(200)
            .execute()
        )
        return res.data or []
    except Exception:
        return []


def submit_transfer_request(from_center: str, to_center: str, ih_codes: list,
                             notes: str, actor_id: str, actor_name: str) -> bool:
    try:
        get_supabase().table(TRANSFER_TABLE).insert({
            "id":                 str(uuid.uuid4()),
            "from_center":        from_center,
            "to_center":          to_center,
            "ih_codes":           ih_codes,
            "status":             "pending",
            "notes":              notes or None,
            "requested_by":       actor_id,
            "requested_by_name":  actor_name,
            "requested_at":       _now_kst().isoformat(),
        }).execute()
        return True
    except Exception as e:
        st.error(f"이동신청 저장 실패: {e}")
        return False


def approve_transfer_request(req: dict, actor_id: str, actor_name: str) -> bool:
    """승인: 단말기를 목적 센터로 이동(unassigned), 신청센터 수량 차감."""
    try:
        sb  = get_supabase()
        now = _now_kst().isoformat()
        ih_list = [item["ih_code"] for item in req["ih_codes"]]

        # bus_terminal_assignments: from_center에서 해당 IH를 to_center·unassigned로 이동
        for ih in ih_list:
            rows = fetch_assignments(center=req["from_center"])
            match = [r for r in rows if r["ih_code"] == ih and r["status"] in _ACTIVE_STATUSES | {"unassigned"}]
            if match:
                sb.table(TABLE).update({
                    "center":        req["to_center"],
                    "status":        "unassigned",
                    "employee_id":   None,
                    "employee_name": "(미배정)",
                    "assigned_at":   now,
                    "assigned_by":   actor_id,
                }).eq("id", match[0]["id"]).execute()
            else:
                # terminal_movements 기반 가용 IH: 새 unassigned 레코드 생성
                d_type, s_type = classify_terminal(ih)
                sb.table(TABLE).insert({
                    "id":            str(uuid.uuid4()),
                    "ih_code":       ih,
                    "device_type":   d_type if d_type != "미분류" else None,
                    "sub_type":      s_type if d_type != "미분류" else None,
                    "center":        req["to_center"],
                    "employee_id":   None,
                    "employee_name": "(미배정)",
                    "assigned_at":   now,
                    "assigned_by":   actor_id,
                    "status":        "unassigned",
                }).execute()

        # 이력 기록
        _log([{
            "center":        req["to_center"],
            "action":        "transfer",
            "ih_code":       item["ih_code"],
            "device_type":   item.get("device_type"),
            "sub_type":      item.get("sub_type"),
            "from_employee": item.get("employee_name"),
            "from_status":   "holding",
            "to_status":     "unassigned",
            "acted_by":      actor_id,
            "acted_by_name": actor_name,
            "acted_at":      now,
        } for item in req["ih_codes"]])

        # 요청 상태 업데이트
        sb.table(TRANSFER_TABLE).update({
            "status":           "approved",
            "processed_by":     actor_id,
            "processed_by_name": actor_name,
            "processed_at":     now,
        }).eq("id", req["id"]).execute()
        return True
    except Exception as e:
        st.error(f"승인 처리 실패: {e}")
        return False


def reject_transfer_request(req_id: str, actor_id: str, actor_name: str) -> bool:
    try:
        get_supabase().table(TRANSFER_TABLE).update({
            "status":           "rejected",
            "processed_by":     actor_id,
            "processed_by_name": actor_name,
            "processed_at":     _now_kst().isoformat(),
        }).eq("id", req_id).execute()
        return True
    except Exception as e:
        st.error(f"거절 처리 실패: {e}")
        return False


def delete_assignments(assignment_ids: list, records_meta: list = None) -> bool:
    if not assignment_ids:
        return False
    try:
        get_supabase().table(TABLE).delete().in_("id", assignment_ids).execute()
        if records_meta:
            now = _now_kst().isoformat()
            actor_name = user.get("name") or user.get("username", "")
            _log([{
                "center":        r.get("center", ""),
                "action":        "cancel",
                "ih_code":       r["ih_code"],
                "device_type":   r.get("device_type"),
                "sub_type":      r.get("sub_type"),
                "from_employee": r.get("employee_name"),
                "from_status":   r.get("status"),
                "acted_by":      user_id,
                "acted_by_name": actor_name,
                "acted_at":      now,
            } for r in records_meta])
        return True
    except Exception as e:
        st.error(f"삭제 실패: {e}")
        return False


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    render_sidebar_header()
    if st.button("자재현황(전체)", use_container_width=True, key="sb_top_dash"):
        st.switch_page("pages/10_dashboard.py")
    if st.button("버스단말기 현황", use_container_width=True, key="sb_top_bus"):
        st.switch_page("pages/14_terminal_dashboard.py")
    if st.button("택시단말기 현황", use_container_width=True, key="sb_top_taxi"):
        st.switch_page("pages/17_taxi_dashboard.py")
    st.divider()

    render_sidebar_section("재고 관리")
    if st.button("📦 재고 현황", use_container_width=True, key="sb_wh"):
        st.switch_page("pages/15_combined.py")
    if st.button("📟 센터 단말현황(버스)", use_container_width=True, type="primary", key="sb_btt"):
        st.session_state.pop("_btt_dummy", None)
    if st.button("📋 입출고 이력", use_container_width=True, key="sb_hist"):
        st.switch_page("pages/04_history.py")
    if not is_role("guest"):
        if st.button("📊 사용내역", use_container_width=True, key="sb_usage"):
            st.switch_page("pages/08_usage_history.py")

    if not is_role("guest"):
        render_sidebar_section("요청")
        if st.button("📦 자재요청현황", use_container_width=True, key="sb_mat"):
            st.switch_page("pages/07_material_requests.py")
        if st.button("🛒 구매 요청", use_container_width=True, key="sb_pur"):
            st.switch_page("pages/11_purchase_requests.py")

    if is_role("admin", "materials"):
        render_sidebar_section("관리")
        if st.button("📍 위치 지도", use_container_width=True, key="sb_map"):
            st.switch_page("pages/09_rack_map.py")
    if is_role("admin"):
        if st.button("⚙️ 관리자", use_container_width=True, key="sb_adm"):
            st.switch_page("pages/05_admin.py")
        if st.button("🟢 접속 현황", use_container_width=True, key="sb_online"):
            st.switch_page("pages/13_online_users.py")

    render_sidebar_section("개인")
    if st.button("📢 공지사항", use_container_width=True, key="sb_notice"):
        st.switch_page("pages/16_notices.py")
    if st.button("💬 문의하기", use_container_width=True, key="sb_inq"):
        st.switch_page("pages/12_inquiry.py")
    if st.button("👤 마이페이지", use_container_width=True, key="sb_my"):
        st.switch_page("pages/06_mypage.py")
    if st.button("🚪 로그아웃", use_container_width=True, key="sb_out"):
        logout()
    render_sidebar_user(user)


# ── Main ─────────────────────────────────────────────────────────────────────
render_top_bar("센터 단말현황(버스)", user)

if user_role == "guest":
    st.warning("접근 권한이 없습니다.")
    st.stop()

if not _table_exists():
    st.error("bus_terminal_assignments 테이블이 없습니다.")
    with st.expander("SQL 보기 (Supabase에서 실행)"):
        st.code(_SQL_SETUP, language="sql")
    st.stop()

st.markdown("## 📟 센터 단말현황(버스)")
st.caption("자재센터에서 출고된 단말기를 직원별로 배정하고 불량 반납을 추적합니다.")

# 센터 결정
if _can_manage:
    sel_center = st.selectbox("센터 선택", TRACKING_CENTERS, key="btt_sel_center")
elif user_center in TRACKING_CENTERS:
    sel_center = user_center
    st.markdown(f"**센터:** {sel_center} &nbsp;|&nbsp; **{user_name}**")
else:
    st.warning("이 페이지는 강서·강북·강동·강남·자재센터 소속 직원만 이용할 수 있습니다.")
    st.stop()

st.divider()

# ── 헬퍼: 기종별 수량 표 ─────────────────────────────────────────────────────
def _render_device_summary(rows: list, active_statuses=("holding", "defective")):
    data = [r for r in rows if r.get("status") in active_statuses]
    if not data:
        st.caption("단말기 없음")
        return
    df = pd.DataFrame(data)
    df["기종"] = df["device_type"].fillna("미분류")
    df["유형"] = df["sub_type"].fillna("")
    df["표시"] = df.apply(
        lambda r: r["기종"] if not r["유형"] else f"{r['기종']} {r['유형']}", axis=1
    )
    grp = df.groupby("표시").size().reset_index(name="수량")
    grp = grp.sort_values("표시").reset_index(drop=True)
    total = grp["수량"].sum()
    st.dataframe(grp, use_container_width=True, hide_index=True)
    st.markdown(f"**합계: {total}대**")


# ── 팝업 다이얼로그 ──────────────────────────────────────────────────────────

@st.experimental_dialog("🔄 불량 교체", width="small")
def _dlg_swap(rec: dict):
    exp_dtype = rec.get("device_type") or ""
    exp_stype = rec.get("sub_type")    or ""
    # device_type 미설정 시 IH 번호로 자동 분류
    if not exp_dtype:
        _ad, _as = classify_terminal(rec["ih_code"])
        if _ad != "미분류":
            exp_dtype, exp_stype = _ad, _as
    exp_label = f"{exp_dtype} {exp_stype}".strip() or "미분류"

    src_label = _STATUS_LABEL.get(rec.get("status", ""), "")
    st.markdown(f"설치할 단말기 IH: **`{rec['ih_code']}`** ({src_label})")
    st.markdown(f"기종: **{exp_label}**")
    st.caption("수거한 불량 단말기는 같은 기종·유형이어야 합니다.")

    def_ih = st.text_input("수거한 불량 IH 번호", key="dlg_sw_ih",
                           placeholder="예: 100456")

    type_ok = False
    dup_ok   = True
    if def_ih.strip():
        ih_clean = def_ih.strip()

        # ── 1. 자기 자신 IH 입력 차단 ────────────────────────────────────────
        if ih_clean == rec["ih_code"]:
            st.error("설치할 단말기와 수거한 단말기의 IH가 동일합니다.")
            dup_ok = False
        else:
            # ── 2. 기종 체크 (항상 실행) ──────────────────────────────────────
            d_dtype, d_stype = classify_terminal(ih_clean)
            d_label = f"{d_dtype} {d_stype}".strip()
            if d_dtype == "미분류":
                st.warning("IH를 인식하지 못했습니다. 번호를 확인해 주세요.")
            elif d_dtype != exp_dtype or d_stype != exp_stype:
                st.error(
                    f"기종 불일치: 설치 **{exp_label}** ↔ 수거 **{d_label}**\n\n"
                    "같은 기종·유형끼리만 교체할 수 있습니다."
                )
            else:
                st.success(f"기종 일치: **{d_label}** ✅")
                type_ok = True

            # ── 3. 중복 체크 (기종 OK인 경우에만 의미 있음) ──────────────────
            existing = [
                r for r in fetch_assignments(center=rec["center"])
                if r["ih_code"] == ih_clean and r["status"] in _ACTIVE_STATUSES | {"unassigned"}
            ]
            if existing:
                holder = existing[0].get("employee_name", "")
                st.warning(
                    f"IH `{ih_clean}` 이 **{holder}** 보유 중으로 등록돼 있습니다.\n\n"
                    "현장 수거 후 강제 등록하려면 아래 체크박스를 선택하세요."
                )
                force = st.checkbox("강제 등록 (기존 배정 무시)", key="dlg_sw_force")
                dup_ok = force

    c1, c2 = st.columns(2)
    if c1.button("교체 확정", type="primary", use_container_width=True,
                 key="dlg_sw_ok", disabled=not (type_ok and dup_ok)):
        if swap_terminal(rec["id"], def_ih.strip(), rec["center"],
                         rec.get("employee_id"), rec["employee_name"],
                         orig_ih=rec["ih_code"], orig_status=rec.get("status","holding"),
                         orig_dtype=rec.get("device_type",""), orig_stype=rec.get("sub_type","")):
            st.session_state.pop("btt_dlg_swap", None)
            st.success(f"교체 완료: {rec['ih_code']} → 불량 {def_ih.strip()}")
            st.rerun()
    if c2.button("취소", use_container_width=True, key="dlg_sw_cancel"):
        st.session_state.pop("btt_dlg_swap", None)
        st.rerun()


@st.experimental_dialog("👤 직원 이동", width="small")
def _dlg_transfer(ids: list, center: str, ih_preview: str, meta: list = None):
    st.markdown(f"이동할 단말기 **{len(ids)}건**: `{ih_preview}`")
    cus = fetch_center_users(center)
    if not cus:
        st.warning("센터에 등록된 직원이 없습니다.")
        st.session_state.pop("btt_dlg_transfer", None)
        return
    u_opts = {u.get("name") or u["username"]: u for u in cus}
    t_name = st.selectbox("이동할 직원", list(u_opts.keys()), key="dlg_tr_emp")
    c1, c2 = st.columns(2)
    if c1.button("이동 확정", type="primary", use_container_width=True, key="dlg_tr_ok"):
        t_u = u_opts[t_name]
        try:
            get_supabase().table(TABLE).update({
                "employee_id":   t_u["id"],
                "employee_name": t_u.get("name") or t_u["username"],
                "assigned_at":   _now_kst().isoformat(),
                "assigned_by":   user_id,
            }).in_("id", ids).execute()
            now = _now_kst().isoformat()
            actor_name = user.get("name") or user.get("username", "")
            meta = meta or []
            _log([{
                "center":        center,
                "action":        "transfer",
                "ih_code":       r.get("ih_code",""),
                "device_type":   r.get("device_type"),
                "sub_type":      r.get("sub_type"),
                "from_employee": r.get("employee_name"),
                "to_employee":   t_u.get("name") or t_u["username"],
                "from_status":   r.get("status"),
                "to_status":     r.get("status"),
                "acted_by":      user_id,
                "acted_by_name": actor_name,
                "acted_at":      now,
            } for r in meta])
            st.session_state.pop("btt_dlg_transfer", None)
            st.success(f"✅ {len(ids)}건 → {t_name} 이동 완료!")
            st.rerun()
        except Exception as e:
            st.error(f"이동 실패: {e}")
    if c2.button("취소", use_container_width=True, key="dlg_tr_cancel"):
        st.session_state.pop("btt_dlg_transfer", None)
        st.rerun()


@st.experimental_dialog("↩️ 반납 처리", width="small")
def _dlg_return(ids: list, ih_preview: str, meta: list = None):
    st.markdown(f"선택 **{len(ids)}건**: `{ih_preview}`")
    st.caption("양품은 센터 가용풀로 복귀, 불량은 센터보관 대기 처리됩니다.")
    c1, c2 = st.columns(2)
    if c1.button("반납 확정", type="primary", use_container_width=True, key="dlg_ret_ok"):
        if return_terminals(ids, records_meta=meta):
            st.session_state.pop("btt_dlg_return", None)
            st.success(f"✅ {len(ids)}건 반납 완료!")
            st.rerun()
    if c2.button("취소", use_container_width=True, key="dlg_ret_cancel"):
        st.session_state.pop("btt_dlg_return", None)
        st.rerun()


@st.experimental_dialog("🗑️ 배정 취소", width="small")
def _dlg_cancel(ids: list, ih_preview: str, meta: list = None):
    st.markdown(f"선택 **{len(ids)}건**: `{ih_preview}`")
    st.caption("삭제된 양품 단말기는 센터 배정 가능 풀로 돌아갑니다.")
    c1, c2 = st.columns(2)
    if c1.button("삭제 확정", type="secondary", use_container_width=True, key="dlg_can_ok"):
        if delete_assignments(ids, records_meta=meta):
            st.session_state.pop("btt_dlg_cancel", None)
            st.success(f"✅ {len(ids)}건 취소 완료!")
            st.rerun()
    if c2.button("취소", use_container_width=True, key="dlg_can_cancel"):
        st.session_state.pop("btt_dlg_cancel", None)
        st.rerun()


@st.experimental_dialog("✏️ 레코드 수정 (관리자·센터장)", width="small")
def _dlg_edit(rec: dict, center: str):
    st.caption(f"ID: `{rec['id'][:8]}…`")

    # IH
    new_ih = st.text_input("IH 번호", value=rec.get("ih_code", ""), key="dlg_ed_ih")

    # 기종/유형
    DEVICE_OPTS = ["", "B800", "B700", "B710", "B620", "한강버스", "미분류"]
    SUB_OPTS    = ["", "표출기", "통합단말기", "승하차", "운전자", "모뎀", "알 수 없음"]
    cur_dt = rec.get("device_type") or ""
    cur_st = rec.get("sub_type")    or ""
    new_dt = st.selectbox("기종", DEVICE_OPTS,
                          index=DEVICE_OPTS.index(cur_dt) if cur_dt in DEVICE_OPTS else 0,
                          key="dlg_ed_dt")
    new_st = st.selectbox("유형", SUB_OPTS,
                          index=SUB_OPTS.index(cur_st) if cur_st in SUB_OPTS else 0,
                          key="dlg_ed_st")

    # 배정 직원
    cus     = fetch_center_users(center)
    u_map   = {"(미배정)": {"id": None, "name": "(미배정)"}}
    u_map.update({u.get("name") or u["username"]: u for u in cus})
    cur_emp = rec.get("employee_name") or "(미배정)"
    emp_key = cur_emp if cur_emp in u_map else "(미배정)"
    new_emp_name = st.selectbox("배정 직원", list(u_map.keys()),
                                index=list(u_map.keys()).index(emp_key),
                                key="dlg_ed_emp")
    new_emp_u  = u_map[new_emp_name]
    new_emp_id = new_emp_u.get("id")

    # 상태
    STATUS_OPTS = list(_STATUS_LABEL.keys())
    cur_st_val  = rec.get("status", "holding")
    new_status  = st.selectbox("상태",
                               STATUS_OPTS,
                               index=STATUS_OPTS.index(cur_st_val) if cur_st_val in STATUS_OPTS else 0,
                               format_func=lambda s: _STATUS_LABEL.get(s, s),
                               key="dlg_ed_status")

    c1, c2 = st.columns(2)
    if c1.button("저장", type="primary", use_container_width=True, key="dlg_ed_ok"):
        if not new_ih.strip():
            st.warning("IH 번호를 입력해 주세요.")
        else:
            try:
                get_supabase().table(TABLE).update({
                    "ih_code":       new_ih.strip(),
                    "device_type":   new_dt or None,
                    "sub_type":      new_st or None,
                    "employee_id":   new_emp_id,
                    "employee_name": new_emp_name if new_emp_name != "(미배정)" else "(미배정)",
                    "status":        new_status,
                }).eq("id", rec["id"]).execute()
                st.session_state.pop("btt_dlg_edit", None)
                st.success("수정됐습니다.")
                st.rerun()
            except Exception as e:
                st.error(f"수정 실패: {e}")
    if c2.button("취소", use_container_width=True, key="dlg_ed_cancel"):
        st.session_state.pop("btt_dlg_edit", None)
        st.rerun()


@st.experimental_dialog("➕ 새 배정", width="large")
def _dlg_new_assign(center: str, can_pick_emp: bool):
    if can_pick_emp:
        cus   = fetch_center_users(center)
        u_map = {u.get("name") or u["username"]: u for u in cus}
        sel   = st.selectbox("배정 직원", list(u_map.keys()), key="dlg_na_emp")
        tgt   = u_map[sel]
        tgt_id, tgt_name = tgt["id"], tgt.get("name") or tgt["username"]
    else:
        tgt_id, tgt_name = user_id, user_name
        st.markdown(f"배정 직원: **{tgt_name}**")

    with st.spinner("배정 가능한 단말기 조회 중..."):
        available = get_available_terminals(center)

    if not available:
        st.info("현재 배정 가능한 단말기가 없습니다.\n\n버스단말기 현황에서 출고 업로드 후 이용하세요.")
        if st.button("닫기", key="dlg_na_close"):
            st.rerun()
        return

    avail_df = pd.DataFrame(available)
    avail_df.rename(columns={"ih_code": "IH", "device_type": "기종",
                              "sub_type": "유형", "upload_date": "출고일"}, inplace=True)
    avail_df.insert(0, "선택", False)
    st.caption(f"배정 가능 {len(avail_df)}건")

    edited = st.data_editor(
        avail_df,
        column_config={
            "선택": st.column_config.CheckboxColumn("선택", default=False),
            "IH":   st.column_config.TextColumn("IH",   disabled=True),
            "기종": st.column_config.TextColumn("기종", disabled=True),
            "유형": st.column_config.TextColumn("유형", disabled=True),
            "출고일": st.column_config.TextColumn("출고일", disabled=True),
        },
        use_container_width=True, hide_index=True, key="dlg_na_editor",
    )
    sel = edited[edited["선택"] == True]

    c1, c2 = st.columns(2)
    if c1.button(f"✅ {tgt_name}에게 배정 ({len(sel)}건)",
                 type="primary", use_container_width=True,
                 key="dlg_na_ok", disabled=sel.empty):
        items = [{"ih_code": r["IH"], "device_type": r["기종"], "sub_type": r["유형"]}
                 for _, r in sel.iterrows()]
        if assign_terminals(items, center, tgt_id, tgt_name, user_id):
            st.success(f"✅ {len(items)}건 배정 완료!")
            st.rerun()
    if c2.button("닫기", use_container_width=True, key="dlg_na_cancel"):
        st.rerun()


# ── 다이얼로그 트리거 ─────────────────────────────────────────────────────────
if "btt_dlg_swap"     in st.session_state: _dlg_swap(**st.session_state["btt_dlg_swap"])
if "btt_dlg_transfer" in st.session_state: _dlg_transfer(**st.session_state["btt_dlg_transfer"])
if "btt_dlg_return"   in st.session_state: _dlg_return(**st.session_state["btt_dlg_return"])
if "btt_dlg_cancel"   in st.session_state: _dlg_cancel(**st.session_state["btt_dlg_cancel"])
if "btt_dlg_edit"     in st.session_state: _dlg_edit(**st.session_state["btt_dlg_edit"])


# ── 탭 ───────────────────────────────────────────────────────────────────────
_tabs = ["📋 배정 현황", "🏢 센터 보유현황", "🚛 센터간이동", "📜 변경이력"]
if _can_manage or user_role == "manager":
    _tabs.append("📤 초기 등록")
_tab_objs = st.tabs(_tabs)
tab_my, tab_center, tab_move, tab_hist, *_extra = _tab_objs
tab_init = _extra[0] if _extra else None


# ─────────────────────────────────────────────────────────────────────────────
# Tab 1: 배정 현황 — 본인 소유 단말기
# ─────────────────────────────────────────────────────────────────────────────
with tab_my:
    # 새 배정 버튼
    if _can_write:
        if st.button("➕ 새 배정", key="btt_open_assign"):
            _dlg_new_assign(sel_center, _can_manage or user_role == "manager")

    st.divider()

    # 본인 소유 단말기 (holding + defective)
    if user_role in ("user",):
        my_rows = fetch_my_assignments(center=sel_center)
    elif _can_manage:
        # admin/materials: 선택 가능
        cus_all = fetch_center_users(sel_center)
        if cus_all:
            emp_map  = {u.get("name") or u["username"]: u for u in cus_all}
            emp_map["(전체 보기)"] = None
            sel_view = st.selectbox("직원 선택", list(emp_map.keys()), key="btt_my_emp_sel")
            view_u   = emp_map[sel_view]
            my_rows  = (
                fetch_assignments(center=sel_center)
                if view_u is None
                else fetch_assignments(center=sel_center, employee_id=view_u["id"])
            )
        else:
            my_rows = []
    else:
        my_rows = fetch_my_assignments(center=sel_center)

    active_rows = [r for r in my_rows if r.get("status") in ("holding", "defective")]

    cl, cr = st.columns([1, 2])

    with cl:
        st.markdown("##### 기종별 수량")
        _render_device_summary(active_rows)

    with cr:
        st.markdown("##### 보유 단말기")
        if not active_rows:
            st.info("현재 보유 중인 단말기가 없습니다.")
        else:
            my_df = pd.DataFrame(active_rows).reset_index(drop=True)
            my_df["배정일시"] = my_df["assigned_at"].apply(_ts)
            my_df["상태"]    = my_df["status"].map(_STATUS_LABEL)

            show_df = my_df[["ih_code", "device_type", "sub_type", "상태", "배정일시"]].copy()
            show_df.columns = ["IH", "기종", "유형", "상태", "배정일시"]
            show_df.insert(0, "선택", False)

            edited_my = st.data_editor(
                show_df,
                column_config={
                    "선택":   st.column_config.CheckboxColumn("선택", default=False),
                    "IH":     st.column_config.TextColumn("IH",     disabled=True),
                    "기종":   st.column_config.TextColumn("기종",   disabled=True),
                    "유형":   st.column_config.TextColumn("유형",   disabled=True),
                    "상태":   st.column_config.TextColumn("상태",   disabled=True),
                    "배정일시": st.column_config.TextColumn("배정일시", disabled=True),
                },
                use_container_width=True, hide_index=True, key="btt_my_editor",
            )

            sel_my = edited_my[edited_my["선택"] == True]

            if not sel_my.empty:
                sel_idx     = sel_my.index.tolist()
                sel_recs    = my_df.iloc[sel_idx]
                sel_ids     = sel_recs["id"].tolist()
                ih_preview  = ", ".join(sel_recs["ih_code"].tolist()[:3])
                if len(sel_ids) > 3: ih_preview += f" 외 {len(sel_ids)-3}건"

                holding_sel = sel_recs[sel_recs["status"] == "holding"]
                swap_ok     = len(sel_ids) == 1 and sel_recs.iloc[0]["status"] in ("holding", "defective")

                st.markdown(f"**선택: {len(sel_ids)}건**")
                _can_edit = _is_admin or user_role == "manager"
                _n_cols = 5 if _can_edit else 4
                _btn_cols = st.columns(_n_cols)
                ba1, ba2, ba3, ba4 = _btn_cols[:4]
                ba5 = _btn_cols[4] if _can_edit else None

                if ba1.button("🔄 불량 교체", use_container_width=True,
                              disabled=not swap_ok, key="btt_my_swap",
                              help="단말기 1건만 선택해야 합니다 (양품·불량 모두 가능)."):
                    rec = sel_recs.iloc[0].to_dict()
                    rec["center"] = sel_center
                    st.session_state["btt_dlg_swap"] = {"rec": rec}
                    st.rerun()

                _sel_meta = sel_recs.assign(center=sel_center).to_dict("records")

                if ba2.button("👤 직원 이동", use_container_width=True, key="btt_my_transfer"):
                    st.session_state["btt_dlg_transfer"] = {
                        "ids": sel_ids, "center": sel_center,
                        "ih_preview": ih_preview, "meta": _sel_meta,
                    }
                    st.rerun()

                if ba3.button("↩️ 반납", use_container_width=True, key="btt_my_return"):
                    st.session_state["btt_dlg_return"] = {
                        "ids": sel_ids, "ih_preview": ih_preview, "meta": _sel_meta,
                    }
                    st.rerun()

                if ba4.button("🗑️ 배정 취소", use_container_width=True, key="btt_my_cancel"):
                    st.session_state["btt_dlg_cancel"] = {
                        "ids": sel_ids, "ih_preview": ih_preview, "meta": _sel_meta,
                    }
                    st.rerun()

                if ba5 and ba5.button("✏️ 수정", use_container_width=True, key="btt_my_edit",
                                      disabled=len(sel_ids) != 1,
                                      help="1건만 선택해야 수정할 수 있습니다."):
                    rec = sel_recs.iloc[0].to_dict()
                    st.session_state["btt_dlg_edit"] = {"rec": rec, "center": sel_center}
                    st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# Tab 2: 센터 보유현황
# ─────────────────────────────────────────────────────────────────────────────
with tab_center:
    if st.button("새로고침", key="btt_ctr_refresh"):
        st.rerun()

    all_assigned  = fetch_assignments(center=sel_center)
    active_all    = [r for r in all_assigned if r.get("status") in ("holding", "defective")]

    with st.spinner("센터 현황 조회 중..."):
        available_pool = get_available_terminals(sel_center)

    # 미배정 단말기를 가상 row로 추가
    unassigned_rows = [
        {
            "employee_name": "─ 미배정 ─",
            "ih_code":       t["ih_code"],
            "device_type":   t["device_type"],
            "sub_type":      t["sub_type"],
            "status":        "holding",  # 기종별 수량 집계용
            "assigned_at":   "",
        }
        for t in available_pool
    ]
    center_all_rows = active_all + unassigned_rows

    # ── 직원별 기종별 수량 (가로 피벗) ────────────────────────────────────────
    if active_all or available_pool:
        st.markdown("##### 직원별 기종별 수량")

        rows_for_pivot = []

        # 직원 보유 단말기
        for r in active_all:
            rows_for_pivot.append({
                "직원명": r.get("employee_name") or "(미배정)",
                "기종유형": f"{r.get('device_type') or '미분류'} {r.get('sub_type') or ''}".strip(),
            })

        # 센터 미배정 단말기 (available_pool)
        for t in available_pool:
            rows_for_pivot.append({
                "직원명": "센터 창고",
                "기종유형": f"{t.get('device_type') or '미분류'} {t.get('sub_type') or ''}".strip(),
            })

        if rows_for_pivot:
            p_df = pd.DataFrame(rows_for_pivot)
            pivot = (
                p_df.groupby(["직원명", "기종유형"])
                .size()
                .unstack(fill_value=0)
            )
            pivot.index.name = None
            pivot.columns.name = None
            pivot["합계"] = pivot.sum(axis=1)

            # 센터 보유 행을 맨 아래로, 나머지는 합계 내림차순
            센터행 = pivot[pivot.index == "센터 창고"]
            직원행 = pivot[pivot.index != "센터 창고"].sort_values("합계", ascending=False)

            # 기종별 합계 행
            합계행 = pd.DataFrame(pivot.sum(axis=0)).T
            합계행.index = ["▶ 기종별 합계"]

            pivot_final = pd.concat([직원행, 센터행, 합계행])
            pivot_final.index.name = "직원명"

            def _style_pivot(df):
                styles = pd.DataFrame("", index=df.index, columns=df.columns)
                # 합계 열 — 연노랑
                if "합계" in df.columns:
                    styles["합계"] = "background-color:#FFF2CC; font-weight:600;"
                # 기종별 합계 행 — 연파랑
                total_idx = "▶ 기종별 합계"
                if total_idx in df.index:
                    styles.loc[total_idx] = "background-color:#D9E1F2; font-weight:700;"
                    if "합계" in df.columns:
                        styles.loc[total_idx, "합계"] = "background-color:#BDD7EE; font-weight:700;"
                return styles

            st.dataframe(
                pivot_final.style.apply(_style_pivot, axis=None),
                use_container_width=True,
            )
        st.divider()

    cl2, cr2 = st.columns([1, 2])

    with cl2:
        st.markdown("##### 기종별 수량")
        _render_device_summary(center_all_rows)

    with cr2:
        st.markdown("##### 센터 단말기 현황")
        if not center_all_rows:
            st.info("센터에 단말기가 없습니다.")
        else:
            ctr_df = pd.DataFrame(center_all_rows)
            ctr_df["상태"] = ctr_df["status"].map(
                lambda s: "미배정" if s == "holding" and ctr_df.loc[
                    ctr_df["status"] == s, "employee_name"
                ].str.startswith("─").any() else _STATUS_LABEL.get(s, s)
            )
            # 미배정/배정 구분 재계산
            assigned_ihs  = {r["ih_code"] for r in active_all}
            avail_ihs     = {t["ih_code"] for t in available_pool}
            ctr_df["상태"] = ctr_df.apply(
                lambda r: "미배정" if r["ih_code"] in avail_ihs else _STATUS_LABEL.get(r["status"], r["status"]),
                axis=1
            )
            if "assigned_at" in ctr_df.columns:
                ctr_df["배정일시"] = ctr_df["assigned_at"].apply(_ts)
            disp_ctr = ctr_df[[
                "employee_name", "ih_code", "device_type", "sub_type", "배정일시", "상태"
            ]].copy()
            disp_ctr.columns = ["직원명", "IH", "기종", "유형", "배정일시", "상태"]
            disp_ctr = disp_ctr.sort_values(["직원명", "IH"]).reset_index(drop=True)
            st.dataframe(disp_ctr, use_container_width=True, hide_index=True)

    # ── 데이터 삭제 (admin/materials/manager) ────────────────────────────────
    if _can_manage or user_role == "manager":
        st.divider()
        with st.expander("🗑️ 센터 보유현황 데이터 삭제"):
            st.caption("bus_terminal_assignments 레코드를 삭제합니다. terminal_movements(버스단말기현황) 데이터는 삭제되지 않습니다.")

            del_all_rows = fetch_assignments(center=sel_center)
            if not del_all_rows:
                st.info("삭제할 데이터가 없습니다.")
            else:
                del_df = pd.DataFrame(del_all_rows).reset_index(drop=True)
                del_df["배정일시"] = del_df["assigned_at"].apply(_ts)
                del_df["상태"]     = del_df["status"].map(_STATUS_LABEL)

                del_disp = del_df[["employee_name", "ih_code", "device_type", "sub_type", "배정일시", "상태"]].copy()
                del_disp.columns = ["직원명", "IH", "기종", "유형", "배정일시", "상태"]
                del_disp.insert(0, "선택", False)

                edited_del_ctr = st.data_editor(
                    del_disp,
                    column_config={
                        "선택":   st.column_config.CheckboxColumn("선택", default=False),
                        "직원명": st.column_config.TextColumn("직원명", disabled=True),
                        "IH":     st.column_config.TextColumn("IH",     disabled=True),
                        "기종":   st.column_config.TextColumn("기종",   disabled=True),
                        "유형":   st.column_config.TextColumn("유형",   disabled=True),
                        "배정일시": st.column_config.TextColumn("배정일시", disabled=True),
                        "상태":   st.column_config.TextColumn("상태",   disabled=True),
                    },
                    use_container_width=True, hide_index=True, key="btt_ctr_del_editor",
                )

                # 전체 선택 체크박스
                if st.checkbox("전체 선택", key="btt_ctr_del_all"):
                    sel_del_ctr = del_df
                else:
                    sel_del_ctr_rows = edited_del_ctr[edited_del_ctr["선택"] == True]
                    sel_del_ctr = del_df.iloc[sel_del_ctr_rows.index] if not sel_del_ctr_rows.empty else pd.DataFrame()

                if not sel_del_ctr.empty:
                    del_ids_ctr = sel_del_ctr["id"].tolist()
                    st.warning(f"선택: **{len(del_ids_ctr)}건** 삭제 시 복구 불가")
                    if st.button(f"🗑️ {len(del_ids_ctr)}건 삭제", type="secondary", key="btt_ctr_del_btn"):
                        if delete_assignments(del_ids_ctr):
                            st.success(f"✅ {len(del_ids_ctr)}건 삭제 완료!")
                            st.rerun()


from utils.mail import send_bus_terminal_transfer, send_bus_terminal_transfer_result

_MOVE_STATUS = {"pending": "대기중", "approved": "승인", "rejected": "거절"}
_REGIONAL    = {"강서센터", "강북센터", "강동센터", "강남센터"}

with tab_move:
    # 자재센터는 이 탭 불필요 (불량입고로만 수령)
    if not _can_manage and user_center not in _REGIONAL:
        st.info("이 탭은 강서·강북·강동·강남 센터에서만 사용할 수 있습니다.")
    else:
        mv_sub1, mv_sub2 = st.tabs(["📤 이동 신청", "📋 이동 현황"])

        # ── 이동 신청 ─────────────────────────────────────────────────────────
        with mv_sub1:
            st.markdown("##### 단말기 이동 신청")
            st.caption("본인 센터의 단말기를 선택해 다른 센터로 이동 신청합니다. 목적 센터 승인 후 이동 처리됩니다.")

            # 목적 센터 선택
            src = sel_center if _can_manage else user_center
            dest_options = [c for c in _REGIONAL if c != src]
            to_center = st.selectbox("목적 센터", dest_options, key="mv_to_center")

            # 신청할 단말기 목록 (본인 센터 전체 — unassigned + active)
            all_src_rows = fetch_assignments(center=src)
            movable = [r for r in all_src_rows if r.get("status") in (_ACTIVE_STATUSES | {"unassigned"})]

            if not movable:
                st.info("이동 신청할 단말기가 없습니다.")
            else:
                mv_df = pd.DataFrame(movable).reset_index(drop=True)
                mv_df["배정일시"] = mv_df["assigned_at"].apply(_ts)
                mv_df["상태"] = mv_df["status"].map(_STATUS_LABEL)
                mv_disp = mv_df[["employee_name", "ih_code", "device_type", "sub_type", "배정일시", "상태"]].copy()
                mv_disp.columns = ["보유직원", "IH", "기종", "유형", "배정일시", "상태"]
                mv_disp.insert(0, "선택", False)

                edited_mv = st.data_editor(
                    mv_disp,
                    column_config={
                        "선택":   st.column_config.CheckboxColumn("선택", default=False),
                        "보유직원": st.column_config.TextColumn("보유직원", disabled=True),
                        "IH":     st.column_config.TextColumn("IH",     disabled=True),
                        "기종":   st.column_config.TextColumn("기종",   disabled=True),
                        "유형":   st.column_config.TextColumn("유형",   disabled=True),
                        "배정일시": st.column_config.TextColumn("배정일시", disabled=True),
                        "상태":   st.column_config.TextColumn("상태",   disabled=True),
                    },
                    use_container_width=True, hide_index=True, key="mv_sel_editor",
                )

                sel_mv = edited_mv[edited_mv["선택"] == True]
                mv_notes = st.text_input("비고 (선택)", placeholder="이동 사유 등", key="mv_notes")

                if not sel_mv.empty:
                    sel_mv_recs = mv_df.iloc[sel_mv.index]
                    st.info(f"선택: **{len(sel_mv)}건** → {to_center}")

                    if st.button("📤 이동 신청", type="primary", key="mv_submit_btn"):
                        ih_payload = [
                            {
                                "ih_code":       r["ih_code"],
                                "device_type":   r.get("device_type"),
                                "sub_type":      r.get("sub_type"),
                                "employee_name": r.get("employee_name"),
                            }
                            for _, r in sel_mv_recs.iterrows()
                        ]
                        actor_name = user.get("name") or user.get("username", "")
                        if submit_transfer_request(src, to_center, ih_payload, mv_notes, user_id, actor_name):
                            # 목적 센터 전원에게 메일
                            to_emails = fetch_center_emails(to_center)
                            send_bus_terminal_transfer(
                                emails=to_emails,
                                from_center=src,
                                to_center=to_center,
                                requester_name=actor_name,
                                terminals=ih_payload,
                                notes=mv_notes,
                            )
                            st.success(f"✅ 이동신청 완료! {to_center} 인원에게 메일 발송됐습니다.")
                            st.rerun()

        # ── 이동 현황 ─────────────────────────────────────────────────────────
        with mv_sub2:
            st.markdown("##### 이동 현황")
            if st.button("새로고침", key="mv_refresh"):
                st.rerun()

            reqs = fetch_transfer_requests(sel_center if _can_manage else user_center)

            if not reqs:
                st.info("이동 신청 내역이 없습니다.")
            else:
                # 받은 신청 (대기중) — 승인/거절 가능
                my_center = sel_center if _can_manage else user_center
                pending_in = [r for r in reqs if r["to_center"] == my_center and r["status"] == "pending"]

                if pending_in:
                    st.markdown("**📥 받은 신청 (대기중)**")
                    for req in pending_in:
                        ih_list = req.get("ih_codes", [])
                        with st.container(border=True):
                            c1, c2, c3 = st.columns([3, 1, 1])
                            c1.markdown(
                                f"**{req['from_center']} → {req['to_center']}** &nbsp; "
                                f"`{len(ih_list)}대` &nbsp; "
                                f"신청자: {req.get('requested_by_name','?')} &nbsp; "
                                f"{_ts(req['requested_at'])}"
                            )
                            if req.get("notes"):
                                st.caption(f"비고: {req['notes']}")
                            # IH 목록 표시
                            ih_df = pd.DataFrame(ih_list)
                            if not ih_df.empty:
                                st.dataframe(ih_df.rename(columns={
                                    "ih_code": "IH", "device_type": "기종",
                                    "sub_type": "유형", "employee_name": "보유직원"
                                }), use_container_width=True, hide_index=True)
                            actor_name = user.get("name") or user.get("username", "")
                            if c2.button("✅ 승인", type="primary", use_container_width=True,
                                         key=f"mv_apv_{req['id']}"):
                                if approve_transfer_request(req, user_id, actor_name):
                                    from_emails = fetch_center_emails(req["from_center"])
                                    send_bus_terminal_transfer_result(
                                        emails=from_emails,
                                        from_center=req["from_center"],
                                        to_center=req["to_center"],
                                        approved=True,
                                        processor_name=actor_name,
                                        terminals=ih_list,
                                        notes=req.get("notes", ""),
                                    )
                                    st.success("✅ 승인 완료! 단말기가 이동됐습니다.")
                                    st.rerun()
                            if c3.button("❌ 거절", use_container_width=True,
                                          key=f"mv_rej_{req['id']}"):
                                if reject_transfer_request(req["id"], user_id, actor_name):
                                    from_emails = fetch_center_emails(req["from_center"])
                                    send_bus_terminal_transfer_result(
                                        emails=from_emails,
                                        from_center=req["from_center"],
                                        to_center=req["to_center"],
                                        approved=False,
                                        processor_name=actor_name,
                                        terminals=ih_list,
                                        notes=req.get("notes", ""),
                                    )
                                    st.success("거절 처리됐습니다.")
                                    st.rerun()
                    st.divider()

                # 전체 이력
                st.markdown("**📋 이동 신청 이력**")
                hist_df = pd.DataFrame(reqs)
                hist_df["신청일시"]  = hist_df["requested_at"].apply(_ts)
                hist_df["상태"]     = hist_df["status"].map(_MOVE_STATUS)
                hist_df["단말기수"] = hist_df["ih_codes"].apply(len)
                disp_mv = hist_df[[
                    "from_center", "to_center", "단말기수", "requested_by_name", "신청일시", "상태"
                ]].rename(columns={
                    "from_center":         "출발 센터",
                    "to_center":           "목적 센터",
                    "requested_by_name":   "신청자",
                })
                st.dataframe(disp_mv, use_container_width=True, hide_index=True)


# ─────────────────────────────────────────────────────────────────────────────
# Tab 4: 변경이력
# ─────────────────────────────────────────────────────────────────────────────
with tab_hist:
    # 테이블 존재 확인
    try:
        get_supabase().table(HIST_TABLE).select("id").limit(1).execute()
    except Exception:
        st.error("bus_terminal_history 테이블이 없습니다. Supabase에서 아래 SQL을 먼저 실행해 주세요.")
        st.code("""CREATE TABLE IF NOT EXISTS bus_terminal_history (
    id            uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
    center        text        NOT NULL,
    action        text        NOT NULL CHECK (action IN ('assign','swap','transfer','return','cancel','init')),
    ih_code       text        NOT NULL,
    device_type   text,  sub_type  text,
    from_employee text,  to_employee text,
    from_status   text,  to_status   text,
    extra_ih      text,
    acted_by      uuid        REFERENCES users(id) ON DELETE SET NULL,
    acted_by_name text,
    acted_at      timestamptz DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_bth_center   ON bus_terminal_history(center);
CREATE INDEX IF NOT EXISTS idx_bth_ih       ON bus_terminal_history(ih_code);
CREATE INDEX IF NOT EXISTS idx_bth_acted_at ON bus_terminal_history(acted_at DESC);""", language="sql")
        st.stop()

    hc1, hc2, hc3 = st.columns([2, 2, 1])
    with hc1:
        date_from = st.date_input("시작일", value=_today_kst() - timedelta(days=30),
                                  key="btt_hist_from")
    with hc2:
        date_to = st.date_input("종료일", value=_today_kst(), key="btt_hist_to")
    with hc3:
        action_filter = st.selectbox(
            "액션", ["전체"] + list(_ACTION_LABEL.values()), key="btt_hist_action"
        )

    hs1, hs2 = st.columns([3, 1])
    with hs1:
        search_kw = st.text_input("검색 (IH · 직원명 · 처리자)", placeholder="예: 100123  또는  홍길동",
                                  key="btt_hist_kw", label_visibility="collapsed")
    with hs2:
        if st.button("조회", use_container_width=True, key="btt_hist_query"):
            st.session_state["btt_hist_run"] = True

    if st.session_state.get("btt_hist_run"):
        try:
            q = (
                get_supabase().table(HIST_TABLE)
                .select("acted_at,action,ih_code,device_type,sub_type,"
                        "from_employee,to_employee,from_status,to_status,"
                        "extra_ih,acted_by_name")
                .eq("center", sel_center)
                .gte("acted_at", date_from.isoformat())
                .lte("acted_at", (date_to + timedelta(days=1)).isoformat())
                .order("acted_at", desc=True)
                .limit(2000)
                .execute()
            )
            hist_rows = q.data or []
        except Exception:
            hist_rows = []

        if not hist_rows:
            st.info("조회된 이력이 없습니다.")
        else:
            h_df = pd.DataFrame(hist_rows)
            h_df["시각"] = h_df["acted_at"].apply(_ts)
            h_df["액션"] = h_df["action"].map(_ACTION_LABEL)
            h_df["기종"] = h_df.apply(
                lambda r: f"{r['device_type'] or ''} {r['sub_type'] or ''}".strip(), axis=1
            )

            # 단말기: 교체는 "설치IH → 수거IH", 나머지는 IH 단독
            def _ih_display(r):
                if r["action"] == "swap" and r.get("extra_ih"):
                    return f"{r['ih_code']}  →  {r['extra_ih']}"
                return r["ih_code"]

            h_df["단말기"] = h_df.apply(_ih_display, axis=1)

            # 직원: 배정은 "→ 직원명", 이동은 "A → B", 나머지는 from_employee
            def _emp_display(r):
                if r["action"] == "assign":
                    return r.get("to_employee") or ""
                if r["action"] == "transfer":
                    fe = r.get("from_employee") or ""
                    te = r.get("to_employee") or ""
                    return f"{fe} → {te}" if fe and te else fe or te
                return r.get("from_employee") or r.get("to_employee") or ""

            h_df["직원"] = h_df.apply(_emp_display, axis=1)

            h_df["상태변경"] = h_df.apply(
                lambda r: (
                    f"{_STATUS_LABEL.get(r['from_status'] or '', r['from_status'] or '')} → "
                    f"{_STATUS_LABEL.get(r['to_status']   or '', r['to_status']   or '')}"
                    if r.get("from_status") and r.get("to_status")
                    else _STATUS_LABEL.get(r.get("to_status") or r.get("from_status") or "", "")
                ), axis=1
            )

            if action_filter != "전체":
                rev_map = {v: k for k, v in _ACTION_LABEL.items()}
                h_df = h_df[h_df["action"] == rev_map[action_filter]]

            # 검색어 필터 — IH, extra_ih, 직원, 처리자 대상
            kw = search_kw.strip()
            if kw:
                mask = (
                    h_df["ih_code"].str.contains(kw, case=False, na=False) |
                    h_df["extra_ih"].fillna("").str.contains(kw, case=False, na=False) |
                    h_df["직원"].str.contains(kw, case=False, na=False) |
                    h_df["acted_by_name"].fillna("").str.contains(kw, case=False, na=False)
                )
                h_df = h_df[mask]

            disp_h = h_df[["시각", "액션", "단말기", "기종", "직원", "상태변경", "acted_by_name"]].copy()
            disp_h.columns = ["시각", "액션", "단말기(설치→수거)", "기종", "직원", "상태변경", "처리자"]

            st.caption(f"총 {len(disp_h)}건" + (f"  (검색: '{kw}')" if kw else ""))
            st.dataframe(disp_h, use_container_width=True, hide_index=True)

            # 엑셀 다운로드
            import io as _io
            buf = _io.BytesIO()
            disp_h.to_excel(buf, index=False, engine="openpyxl")
            st.download_button(
                "엑셀 다운로드", buf.getvalue(),
                file_name=f"단말기이력_{sel_center}_{date_from}_{date_to}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="btt_hist_dl",
            )


# ─────────────────────────────────────────────────────────────────────────────
# Tab 4: 초기 등록 (admin / materials / manager 전용)
# ─────────────────────────────────────────────────────────────────────────────
if tab_init is not None:
    with tab_init:
        st.markdown("##### 현재 보유 현황 초기 등록")
        st.caption(
            "엑셀 파일(IH번호 + 직원명 컬럼)을 업로드하면 오늘 날짜로 일괄 등록합니다. "
            "시범운영 초기 현황을 맞출 때 사용하세요."
        )

        # 완료 팝업
        if st.session_state.get("btt_init_done"):
            msg = st.session_state.pop("btt_init_done")

            @st.experimental_dialog("✅ 초기 등록 완료")
            def _init_done_popup():
                st.success(msg)
                if st.button("확인", type="primary", use_container_width=True, key="btt_init_done_ok"):
                    st.rerun()
            _init_done_popup()

        # 양식 다운로드
        def _make_template(with_center: bool) -> bytes:
            import io as _io
            import openpyxl
            from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
            wb  = openpyxl.Workbook()
            ws  = wb.active
            ws.title = "초기등록양식"

            data_cols = ["IH번호", "직원명"] + (["센터"] if with_center else [])
            guide_col  = len(data_cols) + 1  # D열 (with_center=True면 4열, False면 3열)

            # 헤더
            headers = data_cols + ["작성 가이드"]
            ws.append(headers)
            hdr_fill = PatternFill("solid", fgColor="D9E1F2")
            guide_fill = PatternFill("solid", fgColor="FFF2CC")
            for ci, hdr in enumerate(headers, 1):
                c = ws.cell(1, ci)
                c.font      = Font(bold=True)
                c.fill      = hdr_fill if ci < guide_col else guide_fill
                c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

            # 예시 데이터
            if with_center:
                ws.append(["100123",    "홍길동", "강서센터"])
                ws.append(["560001234", "김철수", "강북센터"])
                ws.append(["155100001", "",       "강동센터"])
            else:
                ws.append(["100123",    "홍길동"])
                ws.append(["560001234", "김철수"])
                ws.append(["155100001", ""])

            # D열 가이드 내용
            guides = [
                "【 작성 안내 】",
                "▶ IH번호: 단말기 시리얼(IH) 번호 입력 (필수)",
                "▶ 직원명: 단말기를 보유한 직원 이름\n   ※ 비워두면 본인 센터 보유로 등록\n   (배정하기에서 나중에 직원 배정 가능)",
                ("▶ 센터: 등록할 센터명 입력 (필수)\n   허용값: " + ", ".join(TRACKING_CENTERS)) if with_center
                else f"▶ 센터: 자동으로 [{user_center}]에 귀속됩니다.",
            ]
            for ri, txt in enumerate(guides, 1):
                c = ws.cell(ri, guide_col, txt)
                c.font      = Font(color="595959", size=9)
                c.fill      = guide_fill
                c.alignment = Alignment(vertical="top", wrap_text=True)

            # 열 너비
            ws.column_dimensions["A"].width = 18
            ws.column_dimensions["B"].width = 14
            if with_center:
                ws.column_dimensions["C"].width = 14
                ws.column_dimensions["D"].width = 42
            else:
                ws.column_dimensions["C"].width = 42

            # 행 높이
            ws.row_dimensions[1].height = 20
            ws.row_dimensions[3].height = 50   # 직원명 가이드 (줄바꿈)
            ws.row_dimensions[4].height = 40   # 센터 가이드

            buf = _io.BytesIO()
            wb.save(buf)
            return buf.getvalue()

        st.download_button(
            "📥 양식 다운로드",
            data=_make_template(with_center=_can_manage),
            file_name="단말기_초기등록_양식.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="btt_init_template_dl",
        )
        if _can_manage:
            st.caption("관리자·자재센터용 양식 — 센터 컬럼에 등록할 센터를 입력하세요.")
        else:
            st.caption(f"일반 양식 — 업로드 시 **{user_center}**으로 자동 귀속됩니다.")

        st.divider()

        reg_date = st.date_input("등록 기준일", value=_today_kst(), key="btt_init_date")

        uploaded = st.file_uploader(
            "엑셀 파일 (.xlsx / .xls)",
            type=["xlsx", "xls"],
            key="btt_init_file",
        )

        # 허용 센터 결정
        _allowed_centers = TRACKING_CENTERS if _can_manage else [user_center]

        if uploaded:
            try:
                engine = "xlrd" if uploaded.name.lower().endswith(".xls") else "openpyxl"
                raw = pd.read_excel(io.BytesIO(uploaded.read()), engine=engine, dtype=str).fillna("")
            except Exception as e:
                st.error(f"파일 읽기 실패: {e}")
                raw = None

            if raw is not None and not raw.empty:
                ih_kws     = ["ih", "trcn", "단말기", "번호", "ih번호", "serial"]
                name_kws   = ["직원", "이름", "성명", "담당자", "name"]
                center_kws = ["센터", "center"]

                def _find_col(df, keywords):
                    for col in df.columns:
                        nm = str(col).strip().lower().replace(" ", "").replace("_", "")
                        if any(kw in nm for kw in keywords):
                            return col
                    return None

                cols     = raw.columns.tolist()
                ih_col   = _find_col(raw, ih_kws)
                name_col = _find_col(raw, name_kws)
                ctr_col  = _find_col(raw, center_kws)

                ih_col   = st.selectbox("IH번호 컬럼", cols,
                                        index=cols.index(ih_col) if ih_col in cols else 0,
                                        key="btt_init_ih_col")
                # 직원명 컬럼 — 없으면 "없음(미배정)" 선택 가능
                _name_opts  = ["(직원명 없음 — 센터로 등록)"] + cols
                _name_def   = cols.index(name_col) + 1 if name_col in cols else 0
                name_col_sel = st.selectbox("직원명 컬럼", _name_opts,
                                            index=_name_def, key="btt_init_name_col")
                has_name_col = name_col_sel != "(직원명 없음 — 센터로 등록)"
                name_col     = name_col_sel if has_name_col else None
                if not has_name_col:
                    st.info("직원명 없음 — 모든 단말기가 센터 보유로 등록됩니다.")

                if _can_manage:
                    # admin/자재센터: 센터 컬럼 있으면 사용, 없으면 sel_center
                    use_ctr = ctr_col is not None
                    if use_ctr:
                        ctr_col = st.selectbox("센터 컬럼", cols, index=cols.index(ctr_col),
                                               key="btt_init_ctr_col")
                        st.caption(f"센터 컬럼 감지됨 — 허용: **{', '.join(TRACKING_CENTERS)}**")
                    else:
                        st.info(f"센터 컬럼 없음 — 전체 행을 **{sel_center}**으로 등록합니다.")
                else:
                    # 일반 센터: 센터 컬럼 무시, 무조건 본인 센터
                    use_ctr = False
                    if ctr_col is not None:
                        st.warning("센터 컬럼이 감지됐지만 무시됩니다. 모든 행은 **본인 센터**로만 등록됩니다.")

                raw["_ih"]     = raw[ih_col].astype(str).str.strip()
                raw["_name"]   = raw[name_col].astype(str).str.strip() if has_name_col else ""
                raw["_center"] = (
                    raw[ctr_col].astype(str).str.strip() if use_ctr
                    else (user_center if not _can_manage else sel_center)
                )
                raw = raw[
                    (raw["_ih"] != "") & (raw["_ih"] != "nan")
                ].copy()

                # 허용 센터 외 행 차단
                blocked = raw[~raw["_center"].isin(_allowed_centers)]
                raw     = raw[raw["_center"].isin(_allowed_centers)].copy()
                if not blocked.empty:
                    st.error(
                        f"⛔ 등록 불가 센터 **{sorted(blocked['_center'].unique().tolist())}** "
                        f"{len(blocked)}건 제외됐습니다."
                    )
                if raw.empty:
                    st.warning("등록 가능한 데이터가 없습니다.")
                else:
                    raw[["_dtype", "_stype"]] = raw["_ih"].apply(
                        lambda x: pd.Series(classify_terminal(x))
                    )

                    m1, m2, m3, m4 = st.columns(4)
                    m1.metric("등록 대상",   len(raw))
                    m2.metric("제외(권한)",  len(blocked))
                    m3.metric("분류 성공",   int((raw["_dtype"] != "미분류").sum()))
                    m4.metric("미분류",      int((raw["_dtype"] == "미분류").sum()))

                    preview = raw[["_center", "_ih", "_name", "_dtype", "_stype"]].copy()
                    preview.columns = ["센터", "IH", "직원명", "기종", "유형"]
                    st.dataframe(preview, use_container_width=True, hide_index=True)

                    # 센터별 직원 이름→id 매핑 (등장하는 센터만 조회)
                    _ctr_user_map: dict = {}
                    for _c in raw["_center"].unique():
                        for u in fetch_center_users(_c):
                            nm = u.get("name") or u["username"]
                            _ctr_user_map[(nm, _c)] = u["id"]

                    unmatched = [
                        f"{row['_name']}({row['_center']})"
                        for _, row in raw.iterrows()
                        if (row["_name"], row["_center"]) not in _ctr_user_map
                    ]
                    if unmatched:
                        st.warning(
                            f"직원 계정 미매칭 {len(set(unmatched))}명: "
                            f"**{', '.join(sorted(set(unmatched)))}**  \n"
                            "이름 그대로 등록됩니다 (계정 연결 없음)."
                        )

                    st.divider()

                    # 기존 데이터 초기화 옵션 (등록 대상 센터별)
                    target_centers = raw["_center"].unique().tolist()
                    existing_cnt   = sum(
                        len(fetch_assignments(center=c, status="holding"))
                        for c in target_centers
                    )
                    if existing_cnt:
                        do_clear = st.checkbox(
                            f"등록 전 대상 센터({', '.join(target_centers)}) 기존 보유중 {existing_cnt}건 삭제",
                            key="btt_init_clear", value=True,
                        )
                        if do_clear:
                            st.warning(f"저장 시 기존 {existing_cnt}건이 먼저 삭제됩니다.")
                    else:
                        do_clear = False

                    if st.button("✅ 초기 등록 저장", type="primary", key="btt_init_save"):
                        n_del = 0
                        if do_clear:
                            for _c in target_centers:
                                r = clear_center_assignments(_c)
                                if r < 0:
                                    st.stop()
                                n_del += r

                        reg_dt = datetime.combine(reg_date, datetime.min.time()).replace(
                            tzinfo=_KST
                        ).isoformat()

                        records = [
                            {
                                "id":            str(uuid.uuid4()),
                                "ih_code":       row["_ih"],
                                "device_type":   row["_dtype"] if row["_dtype"] != "미분류" else None,
                                "sub_type":      row["_stype"] if row["_dtype"] != "미분류" else None,
                                "center":        row["_center"],
                                "employee_id":   _ctr_user_map.get((row["_name"], row["_center"])) if row["_name"] else None,
                                "employee_name": row["_name"] if row["_name"] else "(미배정)",
                                "assigned_at":   reg_dt,
                                "assigned_by":   user_id,
                                "status":        "holding" if row["_name"] else "unassigned",
                            }
                            for _, row in raw.iterrows()
                        ]

                        n = bulk_register(records)
                        if n > 0:
                            ctr_summary = ", ".join(target_centers)
                            msg = f"{n}건 초기 등록 완료!\n\n기준일: {reg_date}  |  센터: {ctr_summary}"
                            if do_clear:
                                msg += f"\n\n기존 {n_del}건 삭제 후 재등록됐습니다."
                            st.session_state["btt_init_done"] = msg
                            st.rerun()
