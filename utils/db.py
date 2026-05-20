# utils/db.py
import os
import streamlit as st
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()


# ── Supabase 연결 ─────────────────────────────────────────────────────────
@st.cache_resource
def get_supabase() -> Client:
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
    except Exception:
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_KEY")
    return create_client(url, key)


_WAREHOUSE_COPY_SKIP = frozenset(
    {"id", "quantity", "location", "last_modified_by", "last_modified_at"}
)


def _query_with_retry(query_fn):
    """쿼리 실행 — RemoteProtocolError(서버 연결 끊김) 시 클라이언트 재생성 후 1회 재시도."""
    try:
        return query_fn(get_supabase())
    except Exception as e:
        if "RemoteProtocol" in type(e).__name__ or "Server disconnected" in str(e):
            get_supabase.clear()
            return query_fn(get_supabase())
        raise


# ══════════════════════════════════════════════════════════════════════════
# 창고 (warehouse)
# ══════════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=60)
def fetch_warehouse(location: str = None) -> list:
    def _q(sb):
        q = sb.table("warehouse").select(
            "id, item_name, quantity, rack_no, shelf, box_no, "
            "category_large, category_mid, category_small, "
            "location, erp_name, erp_code, repair_manager, item_location, notes"
        ).order("item_name")
        if location:
            q = q.eq("location", location)
        return q.execute().data or []
    return _query_with_retry(_q)


@st.cache_data(ttl=300)
def fetch_categories() -> dict:
    def _q(sb):
        return sb.table("warehouse").select(
            "category_large, category_mid"
        ).execute().data or []
    rows = _query_with_retry(_q)
    cats = {}
    for r in rows:
        lg = r.get("category_large") or "미분류"
        md = r.get("category_mid")   or "미분류"
        cats.setdefault(lg, set()).add(md)
    return {k: sorted(v) for k, v in cats.items()}


def clear_warehouse_cache():
    fetch_warehouse.clear()
    fetch_categories.clear()


# ── 입고 ──────────────────────────────────────────────────────────────────
def stock_in(item_id: int, qty: int, user: dict, reason: str) -> bool:
    """
    자재센터 전용 입고.
    백엔드에서 권한 2중 검증 후 수량 증가 + history 기록.
    """
    from utils.permissions import can_stock_in_out

    if not reason or not reason.strip():
        st.error("사유를 입력해야 합니다.")
        return False
    try:
        sb  = get_supabase()
        cur = sb.table("warehouse").select(
            "quantity, location"
        ).eq("id", item_id).single().execute().data

        # 백엔드 권한 검증
        if not can_stock_in_out(user, cur["location"]):
            st.error("해당 센터의 입고 권한이 없습니다.")
            return False

        before = cur["quantity"]
        after  = before + qty
        sb.table("warehouse").update({
            "quantity":         after,
            "last_modified_by": user["id"],
            "last_modified_at": "now()"
        }).eq("id", item_id).execute()

        _write_history(sb, user["id"], item_id, "in",
                       qty, reason, before, after)
        clear_warehouse_cache()
        return True
    except Exception as e:
        st.error(f"입고 오류: {e}")
        return False


# ── 출고 ──────────────────────────────────────────────────────────────────
def stock_out(item_id: int, qty: int, user: dict, reason: str) -> bool:
    """
    자재센터 전용 출고.
    백엔드에서 권한 2중 검증 후 수량 차감 + history 기록.
    """
    from utils.permissions import can_stock_in_out

    if not reason or not reason.strip():
        st.error("사유를 입력해야 합니다.")
        return False
    try:
        sb  = get_supabase()
        cur = sb.table("warehouse").select(
            "quantity, location"
        ).eq("id", item_id).single().execute().data

        # 백엔드 권한 검증
        if not can_stock_in_out(user, cur["location"]):
            st.error("해당 센터의 출고 권한이 없습니다.")
            return False

        before = cur["quantity"]
        if before < qty:
            st.warning(f"재고 부족: 현재 {before}개, 출고 요청 {qty}개")
            return False

        after = before - qty
        sb.table("warehouse").update({
            "quantity":         after,
            "last_modified_by": user["id"],
            "last_modified_at": "now()"
        }).eq("id", item_id).execute()

        _write_history(sb, user["id"], item_id, "out",
                       qty, reason, before, after)
        clear_warehouse_cache()
        return True
    except Exception as e:
        st.error(f"출고 오류: {e}")
        return False


# ══════════════════════════════════════════════════════════════════════════
# 이동 신청 (transfers)
# ══════════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=30)
def fetch_transfers(status: str = None) -> list:
    def _q(sb):
        def _run(sel):
            q = sb.table("transfers").select(sel).order("requested_at", desc=True)
            if status:
                q = q.eq("status", status)
            return q.execute().data or []
        try:
            return _run(
                "id, requester_id, approver_id, item_id, from_center, to_center, "
                "quantity, status, requested_at, processed_at, "
                "warehouse(item_name), "
                "requester:users!requester_id(name), "
                "approver:users!approver_id(name, center, assigned_center)"
            )
        except Exception:
            return _run(
                "id, requester_id, item_id, from_center, to_center, "
                "quantity, status, requested_at, processed_at, "
                "warehouse(item_name), users(name)"
            )
    return _query_with_retry(_q)


def clear_transfer_cache():
    fetch_transfers.clear()


def create_transfer(
    requester_id: str, from_center: str,
    to_center: str, item_id: int, qty: int
) -> bool:
    try:
        sb = get_supabase()
        sb.table("transfers").insert({
            "requester_id": requester_id,
            "from_center":  from_center,
            "to_center":    to_center,
            "item_id":      item_id,
            "quantity":     qty,
            "status":       "pending"
        }).execute()
        clear_transfer_cache()
        return True
    except Exception as e:
        st.error(f"이동 신청 오류: {e}")
        return False


def approve_transfer(
    transfer_id: int,
    approver: dict,
    rack_no: str = None,
    shelf: str = None,
    box_no: str = None,
) -> bool:
    """
    이동 승인 처리.
    - rack_no/shelf/box_no: 타센터→자재센터 방향일 때 도착 위치 지정
    - 자재센터→타센터 방향: 도착지는 rack 정보 없이 item_name 기준 합산
    """
    from utils.permissions import can_approve_transfer

    try:
        sb = get_supabase()

        tr = sb.table("transfers").select("*").eq(
            "id", transfer_id
        ).single().execute().data
        if not tr:
            st.error("이동 신청 정보를 찾을 수 없습니다.")
            return False

        if not can_approve_transfer(approver, tr["from_center"], tr["to_center"]):
            st.error("해당 이동 건의 승인 권한이 없습니다.")
            return False

        approver_id = approver["id"]
        item_id     = tr["item_id"]
        qty         = tr["quantity"]
        reason      = f"센터 이동 승인 ({tr['from_center']} → {tr['to_center']})"
        to_hub  = (tr["to_center"] == "자재센터")
        rack_no = str(rack_no or "") if rack_no is not None else None
        shelf   = str(shelf   or "") if shelf   is not None else None
        box_no  = str(box_no  or "") if box_no  is not None else None

        if not item_id:
            st.error("연결된 자재가 삭제되어 처리할 수 없습니다. 관리자에게 문의하세요.")
            return False

        src = sb.table("warehouse").select("*").eq(
            "id", item_id
        ).single().execute().data
        if not src:
            st.error("출발지 자재를 찾을 수 없습니다.")
            return False
        if src["quantity"] < qty:
            st.warning(f"재고 부족: 현재 {src['quantity']}개, 이동 요청 {qty}개")
            return False

        before_src = src["quantity"]
        after_src  = before_src - qty
        sb.table("warehouse").update({
            "quantity":         after_src,
            "last_modified_by": approver_id,
            "last_modified_at": "now()"
        }).eq("id", item_id).execute()
        _write_history(sb, approver_id, item_id, "transfer",
                       qty, reason, before_src, after_src,
                       tr["from_center"], tr["to_center"])

        if to_hub:
            q = sb.table("warehouse").select("id, quantity") \
                  .eq("item_name", src["item_name"]).eq("location", "자재센터")
            if rack_no is not None:
                q = q.eq("rack_no", rack_no)
            if shelf is not None:
                q = q.eq("shelf", shelf)
            if box_no is not None:
                q = q.eq("box_no", box_no)
            dest_list = q.execute().data
        else:
            dest_list = sb.table("warehouse").select("id, quantity") \
                          .eq("item_name", src["item_name"]) \
                          .eq("location", tr["to_center"]).execute().data

        if dest_list:
            dest       = max(dest_list, key=lambda r: int(r.get("quantity") or 0))
            before_dst = int(dest["quantity"])
            after_dst  = before_dst + qty
            sb.table("warehouse").update({
                "quantity":         after_dst,
                "last_modified_by": approver_id,
                "last_modified_at": "now()"
            }).eq("id", dest["id"]).execute()
            _write_history(sb, approver_id, dest["id"], "transfer",
                           qty, reason, before_dst, after_dst,
                           tr["from_center"], tr["to_center"])
        else:
            new_item = {k: v for k, v in src.items() if k not in _WAREHOUSE_COPY_SKIP}
            new_item["quantity"]         = qty
            new_item["location"]         = tr["to_center"]
            new_item["last_modified_by"] = approver_id
            new_item["rack_no"] = rack_no or "" if to_hub else ""
            new_item["shelf"]   = shelf   or "" if to_hub else ""
            new_item["box_no"]  = box_no  or "" if to_hub else ""
            result = sb.table("warehouse").insert(new_item).execute()
            new_id = result.data[0]["id"]
            _write_history(sb, approver_id, new_id, "transfer",
                           qty, reason, 0, qty,
                           tr["from_center"], tr["to_center"])

        sb.table("transfers").update({
            "status":       "approved",
            "processed_at": "now()",
            "approver_id":  approver_id,
        }).eq("id", transfer_id).execute()

        clear_warehouse_cache()
        clear_transfer_cache()
        return True

    except Exception as e:
        st.error(f"승인 처리 오류: {e}")
        return False


# ══════════════════════════════════════════════════════════════════════════
# 이력 (history)
# ══════════════════════════════════════════════════════════════════════════

def _write_history(
    sb, actor_id: str, item_id: int,
    action_type: str, qty: int, reason: str,
    before: int, after: int,
    from_center: str = None, to_center: str = None
):
    """내부 전용 — history 테이블 기록."""
    sb.table("history").insert({
        "actor_id":            actor_id,
        "item_id":             item_id,
        "action_type":         action_type,
        "quantity":            qty,
        "reason":              reason,
        "from_center":         from_center,
        "to_center":           to_center,
        "snapshot_qty_before": before,
        "snapshot_qty_after":  after,
    }).execute()


@st.cache_data(ttl=30)
def fetch_history(
    item_id: int = None,
    action_type: str = None,
    limit: int = 200
) -> list:
    def _q(sb):
        q = sb.table("history").select(
            "id, actor_id, item_id, action_type, quantity, reason, "
            "from_center, to_center, snapshot_qty_before, snapshot_qty_after, acted_at, "
            "warehouse(item_name, location), users(name)"
        ).order("acted_at", desc=True).limit(limit)
        if item_id:
            q = q.eq("item_id", item_id)
        if action_type:
            q = q.eq("action_type", action_type)
        return q.execute().data or []
    return _query_with_retry(_q)


def clear_history_cache():
    fetch_history.clear()


@st.cache_data(ttl=30)
def fetch_usage_history(center: str = None, limit: int = 200) -> list:
    """사용내역(action_type=out) 조회. center 지정 시 DB에서 바로 필터링."""
    def _q(sb):
        q = sb.table("history").select(
            "id, item_id, action_type, quantity, reason, "
            "from_center, snapshot_qty_before, snapshot_qty_after, acted_at, "
            "warehouse(item_name, location), users(name)"
        ).eq("action_type", "out").order("acted_at", desc=True)
        if center:
            q = q.eq("from_center", center)
        return q.limit(limit).execute().data or []
    return _query_with_retry(_q)


def clear_usage_history_cache():
    fetch_usage_history.clear()


# ══════════════════════════════════════════════════════════════════════════
# 접속 현황 (last_seen)
# ══════════════════════════════════════════════════════════════════════════

def update_last_seen(user_id: str):
    """현재 사용자의 last_seen_at 갱신 — 페이지 로드마다 호출."""
    try:
        get_supabase().table("users").update(
            {"last_seen_at": "now()"}
        ).eq("id", user_id).execute()
    except Exception:
        pass


def fetch_users_online_status() -> list:
    """전체 승인된 사용자 목록 + last_seen_at 반환 (캐시 없음 — 항상 최신)."""
    try:
        return get_supabase().table("users").select(
            "id, name, role, center, assigned_center, last_seen_at"
        ).eq("is_approved", True).order("last_seen_at", desc=True, nullsfirst=False).execute().data or []
    except Exception:
        return []


# ══════════════════════════════════════════════════════════════════════════
# 문의하기 (inquiries)
# ══════════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=30)
def fetch_inquiries(requester_id: str = None) -> list:
    def _q(sb):
        q = sb.table("inquiries").select("*").order("created_at", desc=True)
        if requester_id:
            q = q.eq("requester_id", requester_id)
        return q.execute().data or []
    return _query_with_retry(_q)


def submit_inquiry(requester_id: str, requester_name: str, requester_email: str,
                   from_center: str, title: str, content: str) -> bool:
    try:
        get_supabase().table("inquiries").insert({
            "requester_id":    requester_id,
            "requester_name":  requester_name,
            "requester_email": requester_email,
            "from_center":     from_center,
            "title":           title,
            "content":         content,
            "status":          "pending",
        }).execute()
        clear_inquiry_cache()
        return True
    except Exception as e:
        st.error(f"문의 등록 오류: {e}")
        return False


def answer_inquiry(inquiry_id: str, reply: str, answered_by_name: str) -> bool:
    try:
        get_supabase().table("inquiries").update({
            "reply":            reply,
            "status":           "answered",
            "answered_at":      "now()",
            "answered_by_name": answered_by_name,
        }).eq("id", inquiry_id).execute()
        clear_inquiry_cache()
        return True
    except Exception as e:
        st.error(f"답변 등록 오류: {e}")
        return False


def clear_inquiry_cache():
    fetch_inquiries.clear()


# ══════════════════════════════════════════════════════════════════════════
# 구매 요청 (purchase_requests)
# ══════════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=30)
def fetch_purchase_requests(requester_id: str = None) -> list:
    def _q(sb):
        def _run(sel):
            q = sb.table("purchase_requests").select(sel).order("requested_at", desc=True)
            if requester_id:
                q = q.eq("requester_id", requester_id)
            return q.execute().data or []
        try:
            return _run("*, processor:users!processed_by(name, center, assigned_center)")
        except Exception:
            return _run("*")
    return _query_with_retry(_q)


def clear_purchase_request_cache():
    fetch_purchase_requests.clear()


# ── 개별 자재 이력 조회 (팝업 전용 — 캐시 없음) ──────────────────────────
def fetch_item_history(item_id: int, limit: int = 50) -> list:
    """
    특정 자재의 이력만 조회. 팝업이 열릴 때만 호출.
    캐시 없음 — 항상 최신 데이터 반환.
    """
    sb = get_supabase()
    return sb.table("history").select(
        "*, users(name)"
    ).eq("item_id", item_id).order(
        "acted_at", desc=True
    ).limit(limit).execute().data or []


# ── 자재 정보 수정 ────────────────────────────────────────────────────────
def update_item(item_id: int, updates: dict, user: dict, reason: str) -> bool:
    """
    자재 정보 수정 + history 기록.
    updates: 변경할 컬럼:값 dict
    reason : 수정 사유 (필수)
    """
    from utils.permissions import can_stock_in_out

    if not reason or not reason.strip():
        st.error("수정 사유를 입력해야 합니다.")
        return False

    try:
        sb  = get_supabase()
        cur = sb.table("warehouse").select(
            "quantity, location"
        ).eq("id", item_id).single().execute().data

        # 백엔드 권한 검증
        role = user.get("role","guest")
        if role != "admin":
            assigned = user.get("assigned_center") or user.get("center","")
            if cur.get("location") != assigned:
                st.error("본인 소속 센터의 자재만 수정할 수 있습니다.")
                return False

        # 수정 적용
        updates["last_modified_by"] = user["id"]
        updates["last_modified_at"] = "now()"
        sb.table("warehouse").update(updates).eq("id", item_id).execute()

        # history 기록 (action_type: "edit")
        sb.table("history").insert({
            "actor_id":            user["id"],
            "item_id":             item_id,
            "action_type":         "edit",
            "quantity":            cur.get("quantity", 0),
            "reason":              reason,
            "snapshot_qty_before": cur.get("quantity", 0),
            "snapshot_qty_after":  updates.get("quantity", cur.get("quantity", 0)),
        }).execute()

        clear_warehouse_cache()
        return True

    except Exception as e:
        st.error(f"수정 오류: {e}")
        return False


# ══════════════════════════════════════════════════════════════════════════
# 자재 요청 (material_requests)
# ══════════════════════════════════════════════════════════════════════════

def submit_material_request(
    requester_id: str,
    requester_name: str,
    requester_email: str,
    from_center: str,
    items: list,
    notes: str = "",
) -> int | None:
    """자재 요청 DB 저장. 생성된 id 반환."""
    def _do_insert(sb, include_notes: bool):
        payload = {
            "requester_id":    requester_id,
            "requester_name":  requester_name,
            "requester_email": requester_email,
            "from_center":     from_center,
            "status":          "pending",
            "items":           items,
        }
        if include_notes:
            payload["notes"] = notes or None
        return sb.table("material_requests").insert(payload).execute()

    try:
        sb     = get_supabase()
        try:
            result = _do_insert(sb, include_notes=True)
        except Exception:
            # notes 컬럼 미생성 환경 대비 — 컬럼 없이 재시도
            result = _do_insert(sb, include_notes=False)
        return result.data[0]["id"] if result.data else None
    except Exception as e:
        st.error(f"자재 요청 저장 오류: {e}")
        return None


@st.cache_data(ttl=30)
def fetch_material_requests(status: str = None, from_center: str = None) -> list:
    """자재 요청 목록 조회 (최신순)."""
    def _q(sb):
        def _run(sel):
            q = sb.table("material_requests").select(sel).order("requested_at", desc=True)
            if status:
                q = q.eq("status", status)
            if from_center:
                q = q.eq("from_center", from_center)
            return q.execute().data or []
        try:
            return _run("*, processor:users!processed_by(name, center, assigned_center)")
        except Exception:
            return _run("*")
    return _query_with_retry(_q)


def clear_material_request_cache():
    fetch_material_requests.clear()


def update_material_request_status(
    request_id: int,
    status: str,
    processed_by: str,
) -> bool:
    """자재 요청 상태(승인·거절·보류) 변경."""
    try:
        get_supabase().table("material_requests").update({
            "status":       status,
            "processed_at": "now()",
            "processed_by": processed_by,
        }).eq("id", request_id).execute()
        clear_material_request_cache()
        return True
    except Exception as e:
        st.error(f"상태 변경 오류: {e}")
        return False


def approve_material_request_with_stock(
    request_id: int,
    approver: dict,
    row_selections: dict = None,
) -> tuple[bool, list, list]:
    """
    자재 요청 승인 처리.
    row_selections: {item_name: warehouse_row_id} — 자재센터에서 차감할 row 지정.
                    없으면 자재센터에서 item_name으로 찾아 수량 최대 row 선택.
    반환: (성공여부, 처리된 항목, 실패 항목)
    """
    try:
        sb          = get_supabase()
        req         = sb.table("material_requests").select("*") \
                        .eq("id", request_id).single().execute().data
        if not req:
            return False, [], ["요청 정보를 찾을 수 없습니다."]

        from_center  = req["from_center"]
        items        = req.get("items") or []
        approver_id  = approver["id"]
        reason       = f"자재 요청 승인 ({from_center})"
        ok_items, fail_items = [], []

        for item in items:
            item_name = item.get("item_name", "")
            req_qty   = int(item.get("requested_qty", 0))

            if row_selections and item_name in row_selections:
                src_id   = row_selections[item_name]
                src_data = sb.table("warehouse").select("*").eq("id", src_id).execute().data
                if not src_data:
                    fail_items.append(f"{item_name} (선택한 위치를 찾을 수 없음)")
                    continue
                src = src_data[0]
            else:
                src_data = sb.table("warehouse").select("*") \
                             .eq("item_name", item_name).eq("location", "자재센터") \
                             .order("quantity", desc=True).limit(1).execute().data
                if not src_data:
                    fail_items.append(f"{item_name} (자재센터에서 찾을 수 없음)")
                    continue
                src = src_data[0]

            if src.get("location") != "자재센터":
                fail_items.append(f"{item_name} (자재센터 소속 자재가 아님)")
                continue

            src_item_id = src["id"]

            before_src = int(src["quantity"])
            if before_src < req_qty:
                loc_str = f"렉{src.get('rack_no','')} {src.get('shelf','')}단 박스{src.get('box_no','')}"
                fail_items.append(f"{item_name} ({loc_str} 재고 부족: 현재 {before_src}개, 요청 {req_qty}개)")
                continue
            after_src = before_src - req_qty
            upd_src = sb.table("warehouse").update({
                "quantity":         after_src,
                "last_modified_by": approver_id,
                "last_modified_at": "now()",
            }).eq("id", src_item_id).execute()
            if not upd_src.data:
                fail_items.append(f"{item_name} (자재센터 차감 실패)")
                continue
            _write_history(sb, approver_id, src_item_id, "transfer",
                           req_qty, reason, before_src, after_src,
                           "자재센터", from_center)

            dest_res = sb.table("warehouse").select("id, quantity") \
                         .eq("item_name", item_name).eq("location", from_center).execute()
            if dest_res.data:
                dest       = max(dest_res.data, key=lambda r: int(r["quantity"]))
                before_dst = int(dest["quantity"])
                after_dst  = before_dst + req_qty
                upd_dst = sb.table("warehouse").update({
                    "quantity":         after_dst,
                    "last_modified_by": approver_id,
                    "last_modified_at": "now()",
                }).eq("id", dest["id"]).execute()
                if not upd_dst.data:
                    sb.table("warehouse").update({
                        "quantity": before_src, "last_modified_at": "now()",
                    }).eq("id", src_item_id).execute()
                    fail_items.append(f"{item_name} (요청센터 증가 실패, 자재센터 롤백됨)")
                    continue
                _write_history(sb, approver_id, dest["id"], "transfer",
                               req_qty, reason, before_dst, after_dst,
                               "자재센터", from_center)
            else:
                new_item = {k: v for k, v in src.items() if k not in _WAREHOUSE_COPY_SKIP}
                new_item["quantity"]         = req_qty
                new_item["location"]         = from_center
                new_item["last_modified_by"] = approver_id
                new_item["rack_no"] = ""
                new_item["shelf"]   = ""
                new_item["box_no"]  = ""
                result = sb.table("warehouse").insert(new_item).execute()
                new_id = result.data[0]["id"]
                _write_history(sb, approver_id, new_id, "transfer",
                               req_qty, reason, 0, req_qty,
                               "자재센터", from_center)

            ok_items.append(item_name)

        sb.table("material_requests").update({
            "status":       "approved",
            "processed_at": "now()",
            "processed_by": approver_id,
        }).eq("id", request_id).execute()

        clear_warehouse_cache()
        clear_material_request_cache()
        return True, ok_items, fail_items

    except Exception as e:
        st.error(f"승인 처리 오류: {e}")
        return False, [], [str(e)]


def save_reply_message(request_id: int, message: str) -> bool:
    """회신 메시지 저장."""
    try:
        get_supabase().table("material_requests").update({
            "reply_message": message
        }).eq("id", request_id).execute()
        clear_material_request_cache()
        return True
    except Exception as e:
        st.error(f"회신 저장 오류: {e}")
        return False
