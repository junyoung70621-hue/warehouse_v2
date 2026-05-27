# pages/17_taxi_dashboard.py
import io
import re
import uuid
import calendar as _cal
from datetime import date, datetime, timedelta, timezone

_KST = timezone(timedelta(hours=9))

def _today_kst() -> date:
    return datetime.now(_KST).date()

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

_is_admin   = user_role == "admin"
_is_taxi    = user_center == "택시지원파트"   # 불량입고 담당
_is_repair  = user_center == "리페어팀"       # 양품출고 담당

# 업로드 권한 분리
_can_up_in  = _is_admin or (_is_taxi   and user_role != "guest")
_can_up_out = _is_admin or (_is_repair and user_role != "guest")

TABLE = "taxi_movements"
TAXI_DEVICE_ORDER = ["T600", "T300", "미분류"]

_SQL_SETUP = """\
-- Supabase SQL Editor에서 실행하세요
CREATE TABLE IF NOT EXISTS taxi_movements (
    id           uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
    upload_id    uuid        NOT NULL,
    trcn_id      text        NOT NULL,
    device_type  text        NOT NULL,
    direction    text        NOT NULL CHECK (direction IN ('in','out')),
    uploaded_by  uuid        REFERENCES users(id) ON DELETE SET NULL,
    uploaded_at  timestamptz DEFAULT now(),
    upload_date  date        NOT NULL,
    file_name    text,
    notes        text
);
CREATE INDEX IF NOT EXISTS idx_taxi_upload_date ON taxi_movements(upload_date);
CREATE INDEX IF NOT EXISTS idx_taxi_direction   ON taxi_movements(direction);
CREATE INDEX IF NOT EXISTS idx_taxi_trcn_id     ON taxi_movements(trcn_id);
"""

# 기존 테이블에 dealer_name 컬럼이 남아있을 경우 실행
_SQL_MIGRATE = """\
-- 기존 테이블에서 dealer_name 컬럼 제거 (1회만 실행)
ALTER TABLE taxi_movements DROP COLUMN IF EXISTS dealer_name;
"""


# ══════════════════════════════════════════════════════════════════════════════
# 분류·집계·DB 함수
# ══════════════════════════════════════════════════════════════════════════════

def classify_taxi(raw) -> str:
    s = str(raw).strip()
    try:
        s = str(int(float(s)))
    except Exception:
        pass
    digits = "".join(c for c in s if c.isdigit())
    if len(digits) == 9:
        if digits.startswith("1821"):
            return "T600"
        if digits.startswith("1807"):
            return "T300"
    return "미분류"


def device_summary(rows: list) -> pd.DataFrame:
    """기종별 대수 집계표."""
    if not rows:
        return pd.DataFrame(columns=["기종", "대수"])
    df = pd.DataFrame(rows)
    s = df["device_type"].value_counts()
    result = pd.DataFrame({"기종": s.index, "대수": s.values})
    order = [d for d in TAXI_DEVICE_ORDER if d in result["기종"].values]
    rest  = [d for d in result["기종"].values if d not in order]
    result = pd.concat([
        result[result["기종"].isin(order)].set_index("기종").reindex(order).reset_index(),
        result[result["기종"].isin(rest)],
    ]).fillna(0)
    result["대수"] = result["대수"].astype(int)
    total = pd.DataFrame([{"기종": "합계", "대수": result["대수"].sum()}])
    return pd.concat([result, total], ignore_index=True)


def _table_exists() -> bool:
    try:
        get_supabase().table(TABLE).select("id").limit(1).execute()
        return True
    except Exception:
        return False


def _has_dealer_column() -> bool:
    """기존 버전의 dealer_name 컬럼이 남아있는지 확인."""
    try:
        get_supabase().table(TABLE).select("dealer_name").limit(1).execute()
        return True
    except Exception:
        return False


def fetch_taxi(direction=None, upload_date=None, date_from=None, date_to=None, limit=3000) -> list:
    try:
        q = (
            get_supabase().table(TABLE)
            .select("id,upload_id,trcn_id,device_type,direction,uploaded_at,upload_date,file_name,notes")
            .order("uploaded_at", desc=True)
        )
        if direction:   q = q.eq("direction",   direction)
        if upload_date: q = q.eq("upload_date", upload_date.isoformat())
        if date_from:   q = q.gte("upload_date", date_from.isoformat())
        if date_to:     q = q.lte("upload_date", date_to.isoformat())
        return q.limit(limit).execute().data or []
    except Exception:
        return []


def check_taxi_dups(trcn_ids: list[str], upload_date: date, direction: str) -> set[str]:
    if not trcn_ids:
        return set()
    res = (
        get_supabase().table(TABLE)
        .select("trcn_id")
        .eq("upload_date", upload_date.isoformat())
        .eq("direction",   direction)
        .in_("trcn_id",   trcn_ids[:500])
        .execute()
    )
    return {r["trcn_id"] for r in (res.data or [])}


def save_taxi(records: list) -> bool:
    try:
        get_supabase().table(TABLE).insert(records).execute()
        return True
    except Exception as e:
        st.error(f"저장 실패: {e}")
        return False


# ══════════════════════════════════════════════════════════════════════════════
# 업로드 다이얼로그
# ══════════════════════════════════════════════════════════════════════════════
@st.experimental_dialog("📤 택시단말기 업로드", width="large")
def _upload_dialog(sel_date: date, direction: str):
    dir_label = "양품출고" if direction == "out" else "불량입고"
    st.markdown(f"**{dir_label}** 단말기 번호를 등록합니다.")

    mv_date = st.date_input("이동 날짜", value=sel_date, key="dlg_taxi_date")
    notes   = st.text_area("비고 (선택)", key="dlg_taxi_notes", height=60)

    def _parse_ids(series: pd.Series) -> pd.DataFrame:
        def _norm(x):
            s = str(x).strip()
            try:
                return str(int(float(s)))
            except Exception:
                return s
        normed     = series.map(_norm)
        classified = [classify_taxi(v) for v in normed]
        return pd.DataFrame({"_trcn": normed, "_dtype": classified})[
            normed.str.len() > 0
        ]

    def _do_save(new_df: pd.DataFrame, file_name: str):
        uid = str(uuid.uuid4())
        records = [
            {
                "upload_id":   uid,
                "trcn_id":     row["_trcn"],
                "device_type": row["_dtype"],
                "direction":   direction,
                "uploaded_by": user["id"],
                "upload_date": mv_date.isoformat(),
                "file_name":   file_name,
                "notes":       notes.strip() or None,
            }
            for _, row in new_df.iterrows()
        ]
        if save_taxi(records):
            st.session_state["_taxi_upload_done"] = f"✅ {len(records)}건 {dir_label} 저장 완료!"
            st.rerun()

    def _show_dup_and_save(valid_df: pd.DataFrame, file_name: str, key_sfx: str):
        valid_df = valid_df.drop_duplicates(subset="_trcn")
        try:
            dup_ids = check_taxi_dups(valid_df["_trcn"].tolist(), mv_date, direction)
        except Exception as e:
            st.error(f"중복 확인 오류: {e}")
            dup_ids = set()
        dup_df = valid_df[valid_df["_trcn"].isin(dup_ids)]
        new_df = valid_df[~valid_df["_trcn"].isin(dup_ids)]
        if not dup_df.empty:
            st.warning(f"⚠️ 이미 등록된 단말기 {len(dup_df)}건")
            st.dataframe(
                dup_df[["_trcn", "_dtype"]].rename(columns={"_trcn": "단말기번호", "_dtype": "기종"}),
                use_container_width=True, hide_index=True,
            )
            if st.checkbox("중복 무시하고 강제 저장", key=f"dlg_taxi_{key_sfx}_force"):
                new_df = valid_df.copy()
        if new_df.empty:
            st.error("저장할 데이터가 없습니다 (전부 중복).")
            return
        cnt = new_df["_dtype"].value_counts().to_dict()
        st.info(f"저장 예정: **{len(new_df)}건** ({' / '.join(f'{k} {v}대' for k, v in cnt.items())}) / {mv_date} / {dir_label}")
        _sa, _ca = st.columns(2)
        if _ca.button("취소", key=f"dlg_taxi_{key_sfx}_cancel"):
            st.rerun()
        if _sa.button("✅ 저장", type="primary", key=f"dlg_taxi_{key_sfx}_save"):
            _do_save(new_df, file_name)

    tab_xl, tab_ih = st.tabs(["📁 엑셀 업로드", "⌨️ IH 직접 입력"])

    with tab_xl:
        uploaded = st.file_uploader("엑셀 파일 선택 (.xlsx/.xls)", type=["xlsx", "xls"],
                                    key="dlg_taxi_xl_file")
        if uploaded:
            try:
                xdf = pd.read_excel(uploaded, dtype=str, header=None)
                num_col = next(
                    (col for col in xdf.columns if xdf[col].dropna().str.match(r"^\d+").any()),
                    None,
                )
                if num_col is None:
                    st.error("단말기 번호 컬럼을 찾을 수 없습니다.")
                else:
                    valid = _parse_ids(xdf[num_col].dropna())
                    unknown = valid[valid["_dtype"] == "미분류"]
                    valid   = valid[valid["_dtype"] != "미분류"]
                    if not unknown.empty:
                        st.warning(f"미분류 {len(unknown)}건 제외 (T600: 1821×××××, T300: 1807×××××)")
                    if valid.empty:
                        st.error("유효한 단말기 번호가 없습니다.")
                    else:
                        cnt = valid["_dtype"].value_counts().to_dict()
                        st.success(f"파싱 완료: {' / '.join(f'{k} {v}대' for k, v in cnt.items())}")
                        _show_dup_and_save(valid, uploaded.name, "xl")
            except Exception as e:
                st.error(f"파일 읽기 오류: {e}")

    with tab_ih:
        raw_text = st.text_area(
            "단말기 번호 입력 (줄바꿈·쉼표·공백 구분)",
            height=200, key="dlg_taxi_ih_txt",
            placeholder="182100001\n182100002\n180700001",
        )
        if raw_text.strip():
            tokens   = [t.strip() for t in re.split(r"[\n,\s]+", raw_text) if t.strip()]
            valid_ih = _parse_ids(pd.Series(tokens))
            unknown_ih = valid_ih[valid_ih["_dtype"] == "미분류"]
            valid_ih   = valid_ih[valid_ih["_dtype"] != "미분류"]
            if not unknown_ih.empty:
                st.warning(f"미분류 {len(unknown_ih)}건 제외 (T600: 1821로 시작 9자리, T300: 1807로 시작 9자리)")
            if valid_ih.empty:
                st.warning("인식된 단말기가 없습니다.")
            else:
                cnt = valid_ih["_dtype"].value_counts().to_dict()
                st.success(f"인식: {' / '.join(f'{k} {v}대' for k, v in cnt.items())}")
                _show_dup_and_save(valid_ih, "직접입력", "ih")


# ══════════════════════════════════════════════════════════════════════════════
# 사이드바
# ══════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    render_sidebar_header()
    if st.button("자재현황(전체)", use_container_width=True):
        st.switch_page("pages/10_dashboard.py")
    if st.button("버스단말기 현황", use_container_width=True):
        st.switch_page("pages/14_terminal_dashboard.py")
    if st.button("택시단말기 현황", use_container_width=True, type="primary"):
        pass
    st.divider()

    render_sidebar_section("재고 관리")
    if st.button("📦 재고 현황", use_container_width=True):
        st.switch_page("pages/15_combined.py")
    if st.button("📋 입출고 이력", use_container_width=True):
        st.switch_page("pages/04_history.py")
    if not is_role("guest"):
        if st.button("📊 사용내역", use_container_width=True):
            st.switch_page("pages/08_usage_history.py")

    if not is_role("guest"):
        render_sidebar_section("요청")
        if st.button("📦 자재요청현황", use_container_width=True, key="sb_mat"):
            st.switch_page("pages/07_material_requests.py")
        if st.button("🛒 구매 요청", use_container_width=True, key="sb_pur"):
            st.switch_page("pages/11_purchase_requests.py")

    if is_role("admin", "materials"):
        render_sidebar_section("관리")
        if st.button("📍 위치 지도", use_container_width=True):
            st.switch_page("pages/09_rack_map.py")
    if is_role("admin"):
        if st.button("⚙️ 관리자", use_container_width=True):
            st.switch_page("pages/05_admin.py")
        if st.button("🟢 접속 현황", use_container_width=True):
            st.switch_page("pages/13_online_users.py")

    render_sidebar_section("개인")
    if st.button("📢 공지사항", use_container_width=True):
        st.switch_page("pages/16_notices.py")
    if st.button("💬 문의하기", use_container_width=True):
        st.switch_page("pages/12_inquiry.py")
    if st.button("👤 마이페이지", use_container_width=True):
        st.switch_page("pages/06_mypage.py")
    if st.button("🚪 로그아웃", use_container_width=True):
        logout()
    render_sidebar_user(user)


# ══════════════════════════════════════════════════════════════════════════════
# 메인 컨텐츠
# ══════════════════════════════════════════════════════════════════════════════
render_top_bar("대시보드(택시단말기)", user)
st.markdown("## 🚕 택시 단말기 이동 현황 대시보드")
st.divider()

if not _table_exists():
    st.error("⚠️ Supabase 테이블 `taxi_movements` 가 없습니다. 아래 SQL을 실행하세요.")
    st.code(_SQL_SETUP, language="sql")
    st.stop()

if _has_dealer_column():
    st.warning("⚠️ 테이블에 구버전 `dealer_name` 컬럼이 남아있습니다. Supabase SQL Editor에서 아래를 실행하세요.")
    st.code(_SQL_MIGRATE, language="sql")
    st.stop()

_tab_labels = ["📊 오늘의 현황", "📈 월간 현황", "📋 이력 조회"]
if _is_admin:
    _tab_labels.append("⚙️ 관리")
_tabs      = st.tabs(_tab_labels)
tab_dash, tab_monthly, tab_hist = _tabs[0], _tabs[1], _tabs[2]
tab_admin  = _tabs[3] if _is_admin else None


# ══ Tab 1: 오늘의 현황 ════════════════════════════════════════════════════════
with tab_dash:
    _today = _today_kst()
    _dc, _rc = st.columns([6, 1])
    sel_date = _dc.date_input("조회 날짜", value=_today, key="taxi_dash_date")
    _rc.markdown("<div style='height:27px'></div>", unsafe_allow_html=True)
    if _rc.button("새로고침", key="taxi_t1_ref", use_container_width=True):
        st.rerun()

    out_rows = fetch_taxi(direction="out", upload_date=sel_date)
    in_rows  = fetch_taxi(direction="in",  upload_date=sel_date)

    # 수리중 = 누적 불량입고 - 누적 양품출고
    _all_in_cnt  = len(fetch_taxi(direction="in",  limit=50000))
    _all_out_cnt = len(fetch_taxi(direction="out", limit=50000))
    _under_repair = max(_all_in_cnt - _all_out_cnt, 0)

    # 업로드 완료 알림 / 다이얼로그 열기
    if st.session_state.get("_taxi_upload_done"):
        st.success(st.session_state.pop("_taxi_upload_done"))
    _pending_upload = st.session_state.pop("_show_taxi_upload", None)
    if _pending_upload:
        _upload_dialog(_pending_upload["date"], _pending_upload["direction"])

    # ── 메트릭: 수리중 | 양품출고 합계 | 불량입고 합계 ───────────────────────
    km1, km2, km3 = st.columns(3)
    km1.metric("🔧 수리중",       f"{_under_repair:,}대",  help="누적 불량입고 − 누적 양품출고")
    km2.metric("📤 양품출고 합계", f"{_all_out_cnt:,}대",  help="전체 누적 양품출고")
    km3.metric("📥 불량입고 합계", f"{_all_in_cnt:,}대",  help="전체 누적 불량입고")
    st.divider()

    # ── 현황 테이블 3열: 수리중 요약 | 양품출고 현황 | 불량입고 현황 ──────────
    col_repair, col_out, col_in = st.columns(3)

    with col_repair:
        st.markdown("#### 🔧 수리중")
        # 수리중 = 전체 불량입고 목록에서 양품출고된 것 제외
        _all_in_ids  = {r["trcn_id"] for r in fetch_taxi(direction="in",  limit=50000)}
        _all_out_ids = {r["trcn_id"] for r in fetch_taxi(direction="out", limit=50000)}
        _repair_ids  = _all_in_ids - _all_out_ids
        if _repair_ids:
            # 기종별 집계
            _repair_rows = [r for r in fetch_taxi(direction="in", limit=50000)
                            if r["trcn_id"] in _repair_ids]
            _repair_df = device_summary(_repair_rows)
            st.dataframe(_repair_df, use_container_width=True, hide_index=True)
            st.caption(f"현재 수리 중 **{len(_repair_ids):,}대**")
        else:
            st.info("수리 중인 단말기 없음")

    with col_out:
        _out_hdr, _out_btn = st.columns([3, 1])
        _out_hdr.markdown("#### 📤 양품출고 현황")
        if _can_up_out:
            if _out_btn.button("업로드", key="taxi_out_upload_btn", use_container_width=True):
                st.session_state["_show_taxi_upload"] = {"date": sel_date, "direction": "out"}
                st.rerun()
        _out_summary = device_summary(out_rows)
        if not _out_summary.empty and out_rows:
            st.dataframe(_out_summary, use_container_width=True, hide_index=True)
            st.caption(f"오늘 양품출고 **{len(out_rows):,}대**")
        else:
            st.info("📭 해당 날짜 양품출고 없음")

    with col_in:
        _in_hdr, _in_btn = st.columns([3, 1])
        _in_hdr.markdown("#### 📥 불량입고 현황")
        if _can_up_in:
            if _in_btn.button("업로드", key="taxi_in_upload_btn", use_container_width=True):
                st.session_state["_show_taxi_upload"] = {"date": sel_date, "direction": "in"}
                st.rerun()
        _in_summary = device_summary(in_rows)
        if not _in_summary.empty and in_rows:
            st.dataframe(_in_summary, use_container_width=True, hide_index=True)
            st.caption(f"오늘 불량입고 **{len(in_rows):,}대**")
        else:
            st.info("📭 해당 날짜 불량입고 없음")


# ══ Tab 2: 월간 현황 ══════════════════════════════════════════════════════════
with tab_monthly:
    st.markdown("#### 📈 월간 현황")
    _today2  = _today_kst()
    _mc1, _mc2 = st.columns(2)
    _m_year  = _mc1.selectbox("연도", list(range(_today2.year, _today2.year - 3, -1)),
                               index=0, key="taxi_m_year")
    _m_month = _mc2.selectbox("월", list(range(1, 13)),
                               index=_today2.month - 1, key="taxi_m_month")
    _m_first = date(_m_year, _m_month, 1)
    _m_last  = date(_m_year, _m_month, _cal.monthrange(_m_year, _m_month)[1])

    with st.spinner("월간 데이터 조회 중..."):
        _m_out = fetch_taxi(direction="out", date_from=_m_first, date_to=_m_last, limit=10000)
        _m_in  = fetch_taxi(direction="in",  date_from=_m_first, date_to=_m_last, limit=10000)

    _m_days = max(
        len({r["upload_date"] for r in _m_out}),
        len({r["upload_date"] for r in _m_in}),
    )
    mm1, mm2, mm3 = st.columns(3)
    mm1.metric("📤 양품출고 합계", f"{len(_m_out):,}대")
    mm2.metric("📥 불량입고 합계", f"{len(_m_in):,}대")
    mm3.metric("📅 운영일수",     f"{_m_days}일")
    st.divider()

    # 일별 추이
    st.markdown("##### 일별 추이")
    _day_df = pd.DataFrame()
    if _m_out or _m_in:
        _day_map: dict = {}
        for r in _m_out:
            d = str(r["upload_date"])[:10]
            _day_map.setdefault(d, {"날짜": d, "양품출고": 0, "불량입고": 0})["양품출고"] += 1
        for r in _m_in:
            d = str(r["upload_date"])[:10]
            _day_map.setdefault(d, {"날짜": d, "양품출고": 0, "불량입고": 0})["불량입고"] += 1
        _day_df = pd.DataFrame(sorted(_day_map.values(), key=lambda x: x["날짜"]))
        _day_df["합계"] = _day_df["양품출고"] + _day_df["불량입고"]
        st.dataframe(_day_df, use_container_width=True, hide_index=True)
    else:
        st.info("📭 해당 월 데이터가 없습니다.")
    st.divider()

    # 기종별 집계
    st.markdown("##### 기종별 집계")
    _bv1, _bv2 = st.columns(2)
    _d_out = pd.DataFrame()
    _d_in  = pd.DataFrame()
    with _bv1:
        st.caption("📤 양품출고")
        _d_out = device_summary(_m_out)
        if not _d_out.empty and _m_out:
            st.dataframe(_d_out, use_container_width=True, hide_index=True)
        else:
            st.info("데이터 없음")
    with _bv2:
        st.caption("📥 불량입고")
        _d_in = device_summary(_m_in)
        if not _d_in.empty and _m_in:
            st.dataframe(_d_in, use_container_width=True, hide_index=True)
        else:
            st.info("데이터 없음")
    st.divider()

    # 엑셀 다운로드
    _sheets = {
        "일별추이": _day_df,
        "기종별_양품출고": _d_out if _m_out else pd.DataFrame(),
        "기종별_불량입고": _d_in  if _m_in  else pd.DataFrame(),
    }
    _has_data = any(not df.empty for df in _sheets.values())
    if _has_data:
        _xbuf_m = io.BytesIO()
        with pd.ExcelWriter(_xbuf_m, engine="openpyxl") as _xw:
            for _sname, _sdf in _sheets.items():
                if not _sdf.empty:
                    _sdf.to_excel(_xw, index=False, sheet_name=_sname)
        st.download_button(
            "📥 월간 통계 Excel 다운로드",
            data=_xbuf_m.getvalue(),
            file_name=f"택시단말기월간_{_m_year}{_m_month:02d}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="taxi_monthly_dl",
        )


# ══ Tab 3: 이력 조회 ══════════════════════════════════════════════════════════
with tab_hist:
    st.markdown("#### 📋 이력 조회")
    _today3 = _today_kst()
    _hc1, _hc2, _hc3 = st.columns(3)
    h_from = _hc1.date_input("시작일", value=_today3 - timedelta(days=30), key="taxi_h_from")
    h_to   = _hc2.date_input("종료일", value=_today3, key="taxi_h_to")
    h_dir  = _hc3.selectbox("방향", ["전체", "양품출고", "불량입고"], key="taxi_h_dir")

    _h_dir_val = None if h_dir == "전체" else ("out" if "양품출고" in h_dir else "in")
    h_rows = fetch_taxi(direction=_h_dir_val, date_from=h_from, date_to=h_to, limit=5000)

    if h_rows:
        h_df = pd.DataFrame(h_rows)[
            ["upload_date", "direction", "device_type", "trcn_id", "file_name", "notes"]
        ]
        h_df["direction"] = h_df["direction"].map({"out": "양품출고", "in": "불량입고"})
        h_df.columns = ["날짜", "방향", "기종", "단말기번호", "파일명", "비고"]
        st.caption(f"총 **{len(h_df):,}건**")
        st.dataframe(h_df, use_container_width=True, hide_index=True)

        _xbuf_h = io.BytesIO()
        with pd.ExcelWriter(_xbuf_h, engine="openpyxl") as _xw:
            h_df.to_excel(_xw, index=False, sheet_name="이력")
        st.download_button(
            "📥 Excel 다운로드",
            data=_xbuf_h.getvalue(),
            file_name=f"택시단말기이력_{h_from}_{h_to}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="taxi_hist_dl",
        )
    else:
        st.info("📭 조건에 맞는 데이터가 없습니다.")


# ══ Tab 4: 관리 (admin 전용) ══════════════════════════════════════════════════
if _is_admin and tab_admin is not None:
    with tab_admin:
        st.markdown("#### ⚙️ 배치 삭제")
        st.caption("업로드 단위(배치)로 삭제합니다.")
        try:
            res = (
                get_supabase().table(TABLE)
                .select("upload_id,upload_date,direction,file_name")
                .order("uploaded_at", desc=True)
                .limit(500)
                .execute()
            )
            batches: dict = {}
            for r in (res.data or []):
                uid = r["upload_id"]
                if uid not in batches:
                    batches[uid] = r
            batch_list = list(batches.values())
        except Exception as e:
            st.error(f"조회 실패: {e}")
            batch_list = []

        if batch_list:
            for b in batch_list[:50]:
                _dir_lbl = "양품출고" if b["direction"] == "out" else "불량입고"
                label = f"{b['upload_date']} | {_dir_lbl} | {b.get('file_name', '')}"
                if st.button(f"🗑 {label}", key=f"taxi_del_{b['upload_id']}"):
                    try:
                        get_supabase().table(TABLE).delete().eq("upload_id", b["upload_id"]).execute()
                        st.success("삭제 완료")
                        st.rerun()
                    except Exception as e:
                        st.error(f"삭제 실패: {e}")
        else:
            st.info("삭제할 배치가 없습니다.")
