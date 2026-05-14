# pages/02_warehouse.py
import streamlit as st
import pandas as pd
import io
import hashlib
from utils.auth import require_login, is_role
from utils.db import (
    fetch_warehouse, fetch_categories,
    stock_in, stock_out, create_transfer,
    clear_warehouse_cache, clear_history_cache, clear_usage_history_cache,
    get_supabase, fetch_item_history, update_item,
    submit_material_request,
)
from utils.routing import get_allowed_destinations, CENTERS
from utils.permissions import (
    can_stock_in_out,
    can_request_transfer,
    get_viewable_centers,
    get_center as _get_center,
)
from utils.rack_map import RACK_COORD
from utils.ui import apply_global_css, render_sidebar_header, render_sidebar_user, render_top_bar

st.set_page_config(
    page_title="에이텍모빌리티 자재관리",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded",
)

require_login()
apply_global_css()

user      = st.session_state.user
user_id   = user["id"]
user_role = user["role"]
user_name = user["name"]

# ── 세션 초기화 ───────────────────────────────────────────────────────────
defaults = {
    "selected_mid":      "전체",
    "selected_large":    "전체",
    "selected_small":    "전체",
    "bulk_mode":         None,
    "checked_ids":       [],
    "upload_done":       None,
    "show_upload":       False,
    "show_export":       False,
    "show_transfer":     False,
    "show_usage_upload":     False,
    "usage_upload_done":     None,
    "show_material_request": False,
    "material_request_cart": [],
    "sort_col":              "item_name",
    "sort_dir":              "asc",
    "page_num":              1,
    "page_size":             20,
    "filter_hash":           "",
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ── CSS ──────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;600;700&display=swap');

/* ───── 전체 폰트 ───── */
html, body, * { font-family:'Noto Sans KR', sans-serif !important; }

/* ───── 페이지 전환 페이드인 ───── */
body, [data-testid="stAppViewContainer"] { animation: wms-fadein 0.12s ease-out !important; }
@keyframes wms-fadein { from { opacity:0; } to { opacity:1; } }

/* ───── 숨김 요소 ───── */
[data-testid="stSidebarNav"],
[data-testid="stSidebarHeader"]                  { display:none!important; height:0!important; overflow:hidden!important; padding:0!important; margin:0!important; }
[data-testid="collapsedControl"]                 { display:none!important; }
[data-testid="stSidebarCollapseButton"]          { display:none!important; }
button[data-testid="baseButton-headerNoPadding"] { display:none!important; }
[data-testid="stSidebarUserContent"]             { padding-top:0!important; margin-top:0!important; }

/* ───── 기본 헤더 숨김 (커스텀 헤더로 대체) ───── */
header[data-testid="stHeader"]                   { visibility:hidden!important; }

/* ───── 다크 사이드바 (#212529) ───── */
section[data-testid="stSidebar"],
section[data-testid="stSidebar"] > div,
section[data-testid="stSidebar"] > div > div    { background:#212529!important; }
section[data-testid="stSidebar"]                {
    width:220px!important; min-width:220px!important;
    top:58px!important; height:calc(100vh - 58px)!important;
}

/* 최상단 공백 제거 — apply_global_css()에서 처리 */

/* 폰트 +2pt (드롭다운 제외) */
section[data-testid="stSidebar"] p,
section[data-testid="stSidebar"] label          { color:#adb5bd!important; font-size:17px!important; }
/* 드롭다운 크기 고정 */
section[data-testid="stSidebar"] [data-testid="stSelectbox"] *,
section[data-testid="stSidebar"] [data-baseweb="select"] *  { font-size:13px!important; }
section[data-testid="stSidebar"] hr             { border-color:#343a40!important; margin:8px 0!important; }

/* 셀렉트박스 — 위아래 여백 + 선택된 값 포함 모든 텍스트 흰색 */
section[data-testid="stSidebar"] [data-testid="stSelectbox"] {
    margin-bottom:6px!important;
}
section[data-testid="stSidebar"] [data-baseweb="select"] > div {
    background:#2b3035!important; border-color:#495057!important;
}
section[data-testid="stSidebar"] [data-baseweb="select"] span,
section[data-testid="stSidebar"] [data-baseweb="select"] div,
section[data-testid="stSidebar"] [data-baseweb="singleValue"],
section[data-testid="stSidebar"] [data-baseweb="select"] [data-baseweb="singleValue"],
section[data-testid="stSidebar"] [class*="single-value"],
section[data-testid="stSidebar"] [data-baseweb="select"] input { color:#fff!important; }
section[data-testid="stSidebar"] [data-baseweb="select"] svg   { fill:#adb5bd!important; }

/* 버튼 — 세로 간격 축소 (스크롤 없이 전체 표시) */
section[data-testid="stSidebar"] button {
    background:transparent!important; border:none!important;
    color:#adb5bd!important; text-align:left!important;
    justify-content:flex-start!important;
    padding:5px 12px!important; border-radius:7px!important;
    font-size:16px!important; height:auto!important;
    min-height:36px!important; white-space:nowrap!important;
    margin:2px 0!important; width:100%!important;
}
section[data-testid="stSidebar"] button:hover {
    background:rgba(255,255,255,0.07)!important; color:#f8f9fa!important;
}
/* 활성 메뉴 — 와인색 #D81B60 */
section[data-testid="stSidebar"] button[kind="primary"] {
    background:#D81B60!important; color:#fff!important; font-weight:600!important;
    border-left:3px solid #ff4081!important;
}

/* 사이드바 스크롤바 완전 숨김 */
section[data-testid="stSidebar"]              { overflow-y:hidden!important; overflow-x:hidden!important; }
section[data-testid="stSidebar"] > div        { overflow:hidden!important; }
section[data-testid="stSidebar"] > div > div  { overflow-y:auto!important; scrollbar-width:none!important; }
section[data-testid="stSidebar"] > div > div::-webkit-scrollbar { display:none!important; }

/* ───── 스크롤 ───── */
html, body { overflow-y:auto!important; min-height:100vh!important; }
[data-testid="stAppViewContainer"],
[data-testid="stAppViewBlockContainer"] { overflow-y:auto!important; height:auto!important; }
.main { overflow-y:auto!important; min-height:100vh!important; }
[data-testid="stTabsContent"] { overflow-y:visible!important; padding-bottom:2rem!important; }

/* ───── 메인 레이아웃 ───── */
.main .block-container {
    padding-top:0.8rem!important; padding-bottom:3rem!important;
    overflow:visible!important; max-width:100%!important;
}
hr { margin:2px 0 4px 0!important; }

/* ───── 필터 바 입력 ───── */
div[data-testid="stTextInput"] input {
    font-size:13px!important; height:34px!important;
    border-color:#dee2e6!important; border-radius:6px!important;
}
div[data-testid="stSelectbox"] [data-baseweb="select"] > div {
    height:34px!important; min-height:34px!important;
    border-color:#dee2e6!important; border-radius:6px!important;
    font-size:13px!important;
}

/* ───── 툴바·공통 버튼 (메인 컨텐츠 한정, 사이드바 제외) ───── */
.main div[data-testid="stHorizontalBlock"] button,
.main div[data-testid="stHorizontalBlock"] [data-testid="stDownloadButton"] button {
    white-space:nowrap!important; font-size:12px!important;
    padding:0 8px!important; height:32px!important; min-height:32px!important;
    border-radius:6px!important;
}

/* ───── 테이블 헤더 — 연한 회색(#f1f3f5) + 진한 텍스트 ───── */
[data-testid="stDataEditor"] th {
    background-color:#f1f3f5!important; color:#333!important;
    font-weight:700!important; font-size:12px!important;
    border-bottom:2px solid #dee2e6!important; white-space:nowrap!important;
    position:sticky!important; top:0!important; z-index:10!important;
}
[data-testid="stDataEditor"] td { font-size:12px!important; padding:2px 6px!important; }

/* ───── 기타 ───── */
div[data-testid="stRadio"] label       { font-size:12px!important; }
div[data-testid="stCaptionContainer"] p { font-size:11px!important; }
div[data-testid="column"]              { padding:0px 2px!important; }

@keyframes wms-page-fade-out {
    0%   { opacity: 1; }
    100% { opacity: 0; }
}
</style>
<div style="position:fixed;inset:0;background:#fff;z-index:1000;
            pointer-events:none;
            animation:wms-page-fade-out 0.18s ease-out forwards;"></div>
""", unsafe_allow_html=True)

# ── 컬럼 매핑 ─────────────────────────────────────────────────────────────
EXCEL_COL_MAP = {
    "item_name":      "자재명",
    "quantity":       "수량",
    "rack_no":        "랙번호",
    "shelf":          "단",
    "box_no":         "박스번호",
    "category_large": "대분류",
    "category_mid":   "중분류",
    "category_small": "소분류",
    "item_location":  "지역",
    "location":       "자재위치",
    "erp_name":       "ERP품명",
    "erp_code":       "ERP코드",
    "repair_manager": "수리담당자명",
    "notes":          "비고",
}

USAGE_COL_MAP = {
    "item_name": "자재명",
    "erp_code":  "ERP코드",
    "quantity":  "사용수량",
    "reason":    "사용사유",
}

SORT_MAP = {
    "자재명":  "item_name",
    "수량":   "quantity",
    "대분류":  "category_large",
    "중분류":  "category_mid",
    "소분류":  "category_small",
}

# ── 공통 유틸 ─────────────────────────────────────────────────────────────
def make_excel_buffer(df_export, sheet_name="Sheet1"):
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df_export.to_excel(writer, index=False, sheet_name=sheet_name)
    buf.seek(0)
    return buf

def clean_records(records):
    return [{k: (None if (v != v or str(v) in ("nan","NaN","None")) else v)
             for k, v in r.items()} for r in records]

def validate_upload(up_df):
    if "location" not in up_df.columns:
        return True, ""
    invalid = set(up_df["location"].dropna().unique()) - set(CENTERS)
    if invalid:
        return False, (
            f"❌ 등록되지 않은 센터명이 포함되어 있습니다: {', '.join(invalid)}\n\n"
            f"허용된 센터: {', '.join(CENTERS)}"
        )
    if user_role != "admin":
        assigned  = user.get("assigned_center") or user.get("center","")
        different = set(up_df["location"].dropna().unique()) - {assigned}
        if different:
            return False, (
                f"❌ 소속 센터({assigned}) 데이터만 업로드 가능합니다.\n\n"
                f"업로드 파일에 포함된 다른 센터: {', '.join(different)}"
            )
    return True, ""

def process_usage_upload(records: list, center: str, actor: dict):
    """사용내역 처리: 자재명/ERP코드로 매칭 후 수량 차감 + 이력 기록."""
    sb = get_supabase()
    ok, not_found, insufficient = 0, [], []

    for r in records:
        item_name = str(r.get("item_name","") or "").strip()
        erp_code  = str(r.get("erp_code","")  or "").strip()
        qty       = int(r.get("quantity", 0)  or 0)
        reason    = str(r.get("reason","사용내역 업로드") or "사용내역 업로드").strip()

        if (not item_name and not erp_code) or qty <= 0:
            continue

        # ERP코드 우선 → 자재명 순으로 검색
        item = None
        if erp_code:
            res = sb.table("warehouse").select("id, quantity") \
                    .eq("erp_code", erp_code).eq("location", center).execute()
            if res.data:
                item = res.data[0]
        if not item and item_name:
            res = sb.table("warehouse").select("id, quantity") \
                    .eq("item_name", item_name).eq("location", center).execute()
            if res.data:
                item = res.data[0]

        label = item_name or erp_code
        if not item:
            not_found.append(label)
            continue

        before = item["quantity"]
        if before < qty:
            insufficient.append(f"{label} (현재:{before} / 요청:{qty})")
            continue

        after = before - qty
        sb.table("warehouse").update({
            "quantity":         after,
            "last_modified_by": actor["id"],
            "last_modified_at": "now()",
        }).eq("id", item["id"]).execute()

        sb.table("history").insert({
            "actor_id":            actor["id"],
            "item_id":             item["id"],
            "action_type":         "out",
            "quantity":            qty,
            "reason":              reason,
            "from_center":         center,
            "snapshot_qty_before": before,
            "snapshot_qty_after":  after,
        }).execute()

        ok += 1

    clear_warehouse_cache()
    clear_history_cache()
    clear_usage_history_cache()
    return ok, not_found, insufficient

# ── 팝업 다이얼로그 (자재 상세 / 이력 / 수정) ────────────────────────────
_st_dialog = getattr(st, "dialog", getattr(st, "experimental_dialog", None))

if _st_dialog is not None:
    @_st_dialog("자재 상세 정보", width="large")
    def item_detail_modal(item_id: int, item_name: str, item_loc: str):
        _user      = st.session_state.user
        _role      = _user.get("role","guest")
        _center    = _get_center(_user)

        can_edit = (_role == "admin")
        can_view = can_edit or (item_loc == _center)

        if not can_view:
            st.error("🔒 이 자재의 이력을 볼 권한이 없습니다. (본인 센터 자재만 조회 가능)")
            return

        st.markdown(
            f"<span style='font-size:15px; font-weight:700;'>{item_name}</span>"
            f"<span style='font-size:12px; color:#666; margin-left:8px;'>· {item_loc}</span>",
            unsafe_allow_html=True
        )
        st.divider()

        # 랙 위치 표시 여부 확인
        _pre     = get_supabase().table("warehouse").select("rack_no") \
                                 .eq("id", item_id).execute().data
        _rack_no = str((_pre[0].get("rack_no") or "") if _pre else "").strip()
        _show_map = (item_loc == "자재센터") and (_rack_no in RACK_COORD) and (_role in ("admin", "materials"))

        # 동적 탭 구성
        _tab_labels = ["🔍 이력 조회"]
        if _show_map:
            _tab_labels.append("📍 위치 보기")
        if can_edit:
            _tab_labels.append("✏️ 자재 수정")
            _tab_labels.append("🗑️ 삭제")

        if not can_edit:
            st.caption("ℹ️ 이력 조회만 가능합니다. 수정은 관리자에게 문의하세요.")

        _tabs = st.tabs(_tab_labels)
        _tidx = 0
        tab_hist = _tabs[_tidx]; _tidx += 1
        if _show_map:
            tab_map  = _tabs[_tidx]; _tidx += 1
        if can_edit:
            tab_edit = _tabs[_tidx]; _tidx += 1
            tab_del  = _tabs[_tidx]

        # ── 이력 탭 ────────────────────────────────────────────────────
        with tab_hist:
            hist = fetch_item_history(item_id, limit=50)
            if not hist:
                st.info("이력이 없습니다.")
            else:
                ACTION_LABEL = {
                    "in":       "📥 입고",
                    "out":      "📤 출고",
                    "transfer": "🚚 이동",
                    "edit":     "✏️ 수정",
                }
                h_rows = []
                for h in hist:
                    actor = h.get("users",{}) or {}
                    h_rows.append({
                        "일시":     (h.get("acted_at","") or "")[:16].replace("T"," "),
                        "작업자":   actor.get("name","") if isinstance(actor,dict) else "",
                        "작업유형": ACTION_LABEL.get(h.get("action_type",""), h.get("action_type","")),
                        "수량":     h.get("quantity",0),
                        "변경전":   h.get("snapshot_qty_before",""),
                        "변경후":   h.get("snapshot_qty_after",""),
                        "사유":     h.get("reason",""),
                    })
                st.dataframe(
                    pd.DataFrame(h_rows),
                    use_container_width=True, hide_index=True,
                    column_config={
                        "일시":     st.column_config.TextColumn("일시",     width=120),
                        "작업자":   st.column_config.TextColumn("작업자",   width=80),
                        "작업유형": st.column_config.TextColumn("작업유형", width=80),
                        "수량":     st.column_config.NumberColumn("수량",   width=60),
                        "변경전":   st.column_config.NumberColumn("변경전", width=60),
                        "변경후":   st.column_config.NumberColumn("변경후", width=60),
                        "사유":     st.column_config.TextColumn("사유",     width=230),
                    }
                )

        # ── 위치 탭 (자재센터 + 랙번호 있을 때, admin·materials 전용) ────
        if _show_map:
            with tab_map:
                st.markdown(
                    f"<div style='font-size:14px; margin-bottom:8px;'>"
                    f"📍 <b>랙번호:</b> <code>{_rack_no}</code></div>",
                    unsafe_allow_html=True
                )
                st.caption("전체 지도에서 정확한 위치를 확인하세요.")
                if st.button(
                    "🗺️ 전체 지도에서 보기",
                    key=f"map_goto_{item_id}",
                    type="primary",
                    use_container_width=True,
                ):
                    st.session_state.map_rack_no   = _rack_no
                    st.session_state.map_item_name = item_name
                    st.switch_page("pages/09_rack_map.py")

        # ── 수정 탭 (관리자 전용) ───────────────────────────────────────
        if can_edit:
            with tab_edit:
                sb       = get_supabase()
                row_data = sb.table("warehouse").select("*").eq(
                    "id", item_id
                ).single().execute().data

                if not row_data:
                    st.error("자재 정보를 불러올 수 없습니다.")
                    return

                # ── 분류 데이터 로드 ────────────────────────────────────
                cat_raw = sb.table("warehouse").select(
                    "category_large,category_mid,category_small"
                ).execute().data or []

                NONE_OPT = "(없음)"
                NEW_OPT  = "+ 직접 입력"

                all_lg = sorted({r["category_large"] for r in cat_raw if r.get("category_large")})
                mid_by_lg, sm_by_md = {}, {}
                for r in cat_raw:
                    lg = r.get("category_large") or ""
                    md = r.get("category_mid")   or ""
                    sm = r.get("category_small") or ""
                    if lg and md:
                        mid_by_lg.setdefault(lg, set()).add(md)
                    if sm:
                        sm_by_md.setdefault((lg, md), set()).add(sm)

                pfx     = f"ei_{item_id}"
                _cur_lg = str(row_data.get("category_large","") or "")
                _cur_md = str(row_data.get("category_mid","")   or "")
                _cur_sm = str(row_data.get("category_small","") or "")

                # ── 기본 정보 ────────────────────────────────────────────
                r1c1, r1c2, r1c3 = st.columns([3, 1, 2])
                new_name = r1c1.text_input(
                    "자재명 *", value=str(row_data.get("item_name","") or ""),
                    key=f"{pfx}_name")
                new_qty  = r1c2.number_input(
                    "수량 *", min_value=0, step=1,
                    value=int(row_data.get("quantity", 0)),
                    key=f"{pfx}_qty")
                _cur_loc = str(row_data.get("location", CENTERS[0]))
                new_loc  = r1c3.selectbox(
                    "센터 *", CENTERS,
                    index=CENTERS.index(_cur_loc) if _cur_loc in CENTERS else 0,
                    key=f"{pfx}_loc")

                # ── 분류 (대→중→소 캐스케이딩 드롭다운) ─────────────────
                ec1, ec2, ec3 = st.columns(3)

                # 대분류
                lg_opts = [NONE_OPT] + all_lg + [NEW_OPT]
                lg_idx  = lg_opts.index(_cur_lg) if _cur_lg in lg_opts else 0
                sel_lg  = ec1.selectbox("대분류", lg_opts, index=lg_idx, key=f"{pfx}_lg")
                if sel_lg == NEW_OPT:
                    new_lg_txt = ec1.text_input(
                        "새 대분류명", key=f"{pfx}_lg_new",
                        label_visibility="collapsed", placeholder="새 대분류명 입력")
                    final_lg = new_lg_txt.strip() or None
                else:
                    final_lg = sel_lg if sel_lg != NONE_OPT else None

                # 중분류 (대분류 기준 필터)
                avail_md = sorted(mid_by_lg.get(final_lg or "", set()))
                md_opts  = [NONE_OPT] + avail_md + [NEW_OPT]
                md_idx   = md_opts.index(_cur_md) if _cur_md in md_opts else 0
                sel_md   = ec2.selectbox("중분류", md_opts, index=md_idx, key=f"{pfx}_md")
                if sel_md == NEW_OPT:
                    new_md_txt = ec2.text_input(
                        "새 중분류명", key=f"{pfx}_md_new",
                        label_visibility="collapsed", placeholder="새 중분류명 입력")
                    final_md = new_md_txt.strip() or None
                else:
                    final_md = sel_md if sel_md != NONE_OPT else None

                # 소분류 (대분류+중분류 기준 필터)
                avail_sm = sorted(sm_by_md.get((final_lg or "", final_md or ""), set()))
                sm_opts  = [NONE_OPT] + avail_sm + [NEW_OPT]
                sm_idx   = sm_opts.index(_cur_sm) if _cur_sm in sm_opts else 0
                sel_sm   = ec3.selectbox("소분류", sm_opts, index=sm_idx, key=f"{pfx}_sm")
                if sel_sm == NEW_OPT:
                    new_sm_txt = ec3.text_input(
                        "새 소분류명", key=f"{pfx}_sm_new",
                        label_visibility="collapsed", placeholder="새 소분류명 입력")
                    final_sm = new_sm_txt.strip() or None
                else:
                    final_sm = sel_sm if sel_sm != NONE_OPT else None

                # ── 위치 / ERP / 기타 ────────────────────────────────────
                r3c1, r3c2, r3c3 = st.columns(3)
                new_rack  = r3c1.text_input("랙번호",  value=str(row_data.get("rack_no","") or ""),  key=f"{pfx}_rack")
                new_shelf = r3c2.text_input("단",      value=str(row_data.get("shelf","") or ""),    key=f"{pfx}_shelf")
                new_box   = r3c3.text_input("박스번호", value=str(row_data.get("box_no","") or ""),  key=f"{pfx}_box")

                r4c1, r4c2 = st.columns(2)
                new_erp_n  = r4c1.text_input("ERP품명", value=str(row_data.get("erp_name","") or ""), key=f"{pfx}_erpn")
                new_erp_c  = r4c2.text_input("ERP코드", value=str(row_data.get("erp_code","") or ""), key=f"{pfx}_erpc")

                r5c1, r5c2 = st.columns(2)
                new_repair = r5c1.text_input("수리담당자",   value=str(row_data.get("repair_manager","") or ""), key=f"{pfx}_repair")
                new_i_loc  = r5c2.text_input("지역(사용처)", value=str(row_data.get("item_location","") or ""), key=f"{pfx}_iloc")

                new_notes   = st.text_area("비고", value=str(row_data.get("notes","") or ""), height=60, key=f"{pfx}_notes")
                edit_reason = st.text_input(
                    "✏️ 수정 사유 * (필수)",
                    placeholder="예: 오입력 수정, 정기 재고 조정, 랙 변경 등",
                    key=f"{pfx}_reason")

                if st.button("💾 저장", type="primary", use_container_width=True, key=f"{pfx}_save"):
                    if not new_name.strip():
                        st.error("자재명은 필수입니다.")
                    elif not edit_reason.strip():
                        st.error("⚠️ 수정 사유를 반드시 입력해야 합니다.")
                    else:
                        updates = {
                            "item_name":      new_name.strip(),
                            "quantity":       new_qty,
                            "location":       new_loc,
                            "category_large": final_lg,
                            "category_mid":   final_md,
                            "category_small": final_sm,
                            "rack_no":        new_rack   or None,
                            "shelf":          new_shelf  or None,
                            "box_no":         new_box    or None,
                            "erp_name":       new_erp_n  or None,
                            "erp_code":       new_erp_c  or None,
                            "repair_manager": new_repair or None,
                            "item_location":  new_i_loc  or None,
                            "notes":          new_notes  or None,
                        }
                        if update_item(item_id, updates, _user, edit_reason):
                            st.success("✅ 자재 정보가 수정됐습니다!")
                            st.rerun()

        # ── 삭제 탭 (관리자 전용) ────────────────────────────────────────
        if can_edit:
            with tab_del:
                st.warning(
                    f"⚠️ **{item_name}** 을(를) 영구 삭제합니다.\n\n"
                    "삭제 후 복구할 수 없으며, 관련 이동·이력 기록은 보존됩니다."
                )
                del_confirm = st.checkbox(
                    f'"{item_name}" 삭제에 동의합니다',
                    key=f"del_chk_{item_id}"
                )
                if st.button(
                    "🗑️ 삭제 실행", type="primary",
                    use_container_width=True,
                    disabled=not del_confirm,
                    key=f"del_exec_{item_id}"
                ):
                    _sb = get_supabase()
                    _qty_res = _sb.table("warehouse").select("quantity") \
                                  .eq("id", item_id).execute()
                    _qty = int(_qty_res.data[0]["quantity"]) if _qty_res.data else 0
                    if _qty > 0:
                        try:
                            _sb.table("history").insert({
                                "actor_id":            _user["id"],
                                "item_id":             item_id,
                                "action_type":         "out",
                                "quantity":            _qty,
                                "reason":              "관리자 삭제",
                                "from_center":         item_loc,
                                "snapshot_qty_before": _qty,
                                "snapshot_qty_after":  0,
                            }).execute()
                        except Exception:
                            pass
                    _sb.table("warehouse").delete().eq("id", item_id).execute()
                    clear_warehouse_cache()
                    clear_history_cache()
                    st.success(f"✅ '{item_name}' 삭제 완료")
                    st.rerun()

else:
    # Fallback: st.dialog 미지원 버전 (거의 없음)
    def item_detail_modal(item_id, item_name, item_loc):
        st.error("이 Streamlit 버전은 다이얼로그를 지원하지 않습니다. 버전을 1.29+ 로 업그레이드하세요.")

# ── 사이드바 ──────────────────────────────────────────────────────────────
with st.sidebar:
    render_sidebar_header()
    if st.button("📊 대시보드", use_container_width=True):
        st.switch_page("pages/10_dashboard.py")
    st.divider()

    # 센터 선택 (페이지 이동 후에도 선택값 유지)
    viewable = get_viewable_centers(user)
    if st.session_state.get("sidebar_center") not in viewable:
        st.session_state.pop("sidebar_center", None)
    selected_center = st.selectbox("센터", viewable, label_visibility="collapsed", key="sidebar_center")
    st.divider()

    st.button("📦 재고 현황", use_container_width=True, type="primary")
    if st.button("🚚 이동 신청 현황", use_container_width=True):
        st.switch_page("pages/03_transfers.py")
    if st.button("📋 입출고 이력", use_container_width=True):
        st.switch_page("pages/04_history.py")
    if not is_role("guest"):
        if st.button("📊 사용내역", use_container_width=True):
            st.switch_page("pages/08_usage_history.py")
    if not is_role("guest"):
        if st.button("📦 자재 요청", use_container_width=True, key="sidebar_mat_req"):
            st.switch_page("pages/07_material_requests.py")
    if not is_role("guest"):
        if st.button("🛒 구매 요청", use_container_width=True, key="sidebar_pur_req"):
            st.switch_page("pages/11_purchase_requests.py")
    if is_role("admin", "materials"):
        if st.button("📍 위치 지도", use_container_width=True):
            st.switch_page("pages/09_rack_map.py")
    if is_role("admin"):
        if st.button("⚙️ 관리자", use_container_width=True):
            st.switch_page("pages/05_admin.py")
    st.divider()
    if st.button("👤 마이페이지", use_container_width=True):
        st.switch_page("pages/06_mypage.py")
    if st.button("🚪 로그아웃", use_container_width=True):
        st.session_state.user = None
        st.switch_page("pages/01_login.py")
    render_sidebar_user(user)

# ── 상단바 ────────────────────────────────────────────────────────────────
render_top_bar(f"{selected_center} 재고 현황", user)
st.divider()

# ── 권한 계산 ─────────────────────────────────────────────────────────────
IS_MAIN_HUB = (selected_center == "자재센터")
CAN_STOCK   = can_stock_in_out(user, selected_center)
CAN_TRANSFER = can_request_transfer(user, selected_center)

# 자재센터는 기존 입고/출고. 그 외 센터는 사용내역 업로드(관리자 + 본인센터 manager)
SHOW_STOCK_BUTTONS   = CAN_STOCK and IS_MAIN_HUB
CAN_USAGE_UPLOAD     = (
    not IS_MAIN_HUB and
    (user_role == "admin" or
     (user_role == "manager" and _get_center(user) == selected_center))
)
# 자재 요청: 비자재센터에서 자재파트·게스트 제외한 모든 역할
CAN_MATERIAL_REQUEST = (
    not IS_MAIN_HUB and
    user_role not in ("guest", "materials")
)

# ── 데이터 로드 ───────────────────────────────────────────────────────────
raw_data   = fetch_warehouse(selected_center)
categories = fetch_categories()
df_all     = pd.DataFrame(raw_data) if raw_data else pd.DataFrame()
if not df_all.empty and "item_name" in df_all.columns:
    df_all = df_all.drop_duplicates(subset=["item_name"], keep="first")

# ── 필터 바 (1행: 검색 + 대/중/소 분류 드롭다운) ─────────────────────────
n_checked = len(st.session_state.checked_ids)

# 드롭다운 옵션 계산
_sl = st.session_state.selected_large
_sm = st.session_state.selected_mid
large_cats_f = ["전체"] + sorted(categories.keys())
mid_cats_f   = (["전체"] + categories.get(_sl, [])) if _sl != "전체" else ["전체"]
small_cats_f = ["전체"] + sorted({
    r.get("category_small") for r in raw_data
    if r.get("category_small")
    and (_sl == "전체" or r.get("category_large") == _sl)
    and (_sm == "전체" or r.get("category_mid") == _sm)
})

fb = st.columns([2.5, 1.0, 1.0, 1.0, 0.85])
with fb[0]:
    search_query = st.text_input(
        "검색", placeholder="자재명 / ERP코드 / 분류명 / 랙번호 검색...",
        label_visibility="collapsed"
    )
with fb[1]:
    _lg_idx = large_cats_f.index(_sl) if _sl in large_cats_f else 0
    new_lg  = st.selectbox("대분류", large_cats_f, index=_lg_idx,
                            label_visibility="collapsed", key="filter_large")
    if new_lg != _sl:
        st.session_state.selected_large = new_lg
        st.session_state.selected_mid   = "전체"
        st.session_state.selected_small = "전체"
        st.rerun()
with fb[2]:
    _cur_mid = _sm if _sm in mid_cats_f else "전체"
    _md_idx  = mid_cats_f.index(_cur_mid)
    new_md   = st.selectbox("중분류", mid_cats_f, index=_md_idx,
                             label_visibility="collapsed", key="filter_mid")
    if new_md != _sm:
        st.session_state.selected_mid   = new_md
        st.session_state.selected_small = "전체"
        st.rerun()
with fb[3]:
    _cur_sm  = st.session_state.get("selected_small","전체")
    _cur_sm  = _cur_sm if _cur_sm in small_cats_f else "전체"
    _sm_idx  = small_cats_f.index(_cur_sm)
    new_sm   = st.selectbox("소분류", small_cats_f, index=_sm_idx,
                             label_visibility="collapsed", key="filter_small")
    if new_sm != st.session_state.get("selected_small","전체"):
        st.session_state.selected_small = new_sm
        st.rerun()
with fb[4]:
    st.write("")
    if st.button("필터 초기화", use_container_width=True):
        clear_warehouse_cache()
        st.session_state.checked_ids    = []
        st.session_state.selected_large = "전체"
        st.session_state.selected_mid   = "전체"
        st.session_state.selected_small = "전체"
        st.rerun()

# ── 액션 바 (2행: 기능 버튼) ─────────────────────────────────────────────
if SHOW_STOCK_BUTTONS:
    ab = st.columns([0.72, 0.72, 0.82, 0.78, 0.78, 0.82, 4.0])
else:
    ab = st.columns([0.72, 0.72, 0.82, 0.95, 0.95, 0.82, 4.0])

with ab[0]:
    sample_buf = make_excel_buffer(
        pd.DataFrame(columns=list(EXCEL_COL_MAP.values())), "양식"
    )
    st.download_button("📋 양식", data=sample_buf,
        file_name="WMS_업로드_양식.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True)
with ab[1]:
    if user_role in ("admin", "materials"):
        if st.button("⬆️ 업로드", use_container_width=True):
            st.session_state.show_upload = not st.session_state.show_upload
    else:
        st.button("⬆️ 업로드", use_container_width=True, disabled=True,
                  help="관리자 및 자재파트만 업로드 가능")
with ab[2]:
    if not df_all.empty:
        dl_df = df_all[[c for c in EXCEL_COL_MAP if c in df_all.columns]].copy()
        dl_df.rename(columns=EXCEL_COL_MAP, inplace=True)
        st.download_button("⬇️ 다운로드",
            data=make_excel_buffer(dl_df, selected_center),
            file_name=f"{selected_center}_재고현황.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True)
    else:
        st.button("⬇️ 다운로드", disabled=True, use_container_width=True)

if SHOW_STOCK_BUTTONS:
    with ab[3]:
        label_in = "📥 입고" + (f"({n_checked})" if n_checked else "")
        if st.button(label_in, use_container_width=True,
                     type="primary" if n_checked > 0 else "secondary"):
            st.session_state.bulk_mode = "in"
    with ab[4]:
        label_out = "📤 출고" + (f"({n_checked})" if n_checked else "")
        if st.button(label_out, use_container_width=True,
                     type="primary" if n_checked > 0 else "secondary"):
            st.session_state.bulk_mode = "out"
    with ab[5]:
        if is_role("admin"):
            if st.button("💾 내보내기", use_container_width=True):
                st.session_state.show_export = not st.session_state.show_export
else:
    with ab[3]:
        if CAN_USAGE_UPLOAD:
            if st.button("📋 사용내역", use_container_width=True):
                st.session_state.show_usage_upload = not st.session_state.show_usage_upload
    with ab[4]:
        if CAN_MATERIAL_REQUEST:
            if st.button("📦 자재 요청", use_container_width=True, key="toolbar_mat_req"):
                st.session_state.show_material_request = not st.session_state.show_material_request
    with ab[5]:
        if is_role("admin"):
            if st.button("💾 내보내기", use_container_width=True):
                st.session_state.show_export = not st.session_state.show_export

# ── 알림 메시지 ──────────────────────────────────────────────────────────
if st.session_state.upload_done:
    st.success(f"🎉 {st.session_state.upload_done}개 자재 업로드 완료!")
    st.session_state.upload_done = None

if st.session_state.usage_upload_done:
    st.success(st.session_state.usage_upload_done)
    st.session_state.usage_upload_done = None

# ── 관리자 내보내기 패널 ──────────────────────────────────────────────────
if is_role("admin") and st.session_state.show_export:
    with st.container(border=True):
        st.markdown("#### 💾 전체 데이터 내보내기")
        export_center = st.selectbox(
            "내보낼 센터", ["전체 (모든 센터)"] + CENTERS,
            key="export_center_select"
        )
        from utils.db import fetch_warehouse as fw
        if export_center == "전체 (모든 센터)":
            all_data = []
            for c in CENTERS: all_data.extend(fw(c))
            export_raw, fname, sheet = all_data, "WMS_전체_데이터.xlsx", "전체"
        else:
            export_raw = fw(export_center)
            fname, sheet = f"{export_center}_전체_데이터.xlsx", export_center
        export_df  = pd.DataFrame(export_raw) if export_raw else pd.DataFrame()
        deduct_key = "export_deduct_confirm"
        if deduct_key not in st.session_state:
            st.session_state[deduct_key] = False

        if export_df.empty:
            st.warning("내보낼 데이터가 없습니다.")
        else:
            st.info(f"총 **{len(export_df)}개** 항목")
            exp_df = export_df[[c for c in EXCEL_COL_MAP if c in export_df.columns]].copy()
            exp_df.rename(columns=EXCEL_COL_MAP, inplace=True)
            excel_buf = make_excel_buffer(exp_df, sheet)

            # ── 다운로드만 ─────────────────────────────────────────────
            st.download_button(
                f"⬇️ 다운로드만 ({fname})", data=excel_buf,
                file_name=fname,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )

            # ── 삭제 포함 내보내기 ──────────────────────────────────────
            st.divider()
            st.warning(
                "⚠️ **삭제 포함 내보내기**: 선택한 센터의 모든 자재 목록을 **완전 삭제**합니다. "
                "이력은 기록되며 되돌릴 수 없습니다."
            )
            if not st.session_state[deduct_key]:
                if st.button("📤 삭제 + 내보내기", type="primary",
                             use_container_width=True, key="export_deduct_btn"):
                    st.session_state[deduct_key] = True
                    st.rerun()
            else:
                st.error(f"**{export_center}** 자재 목록 전체를 삭제합니다. 정말 진행하시겠습니까?")
                cc1, cc2 = st.columns(2)
                if cc1.button("✅ 확인 — 삭제 + 다운로드", type="primary",
                              use_container_width=True, key="export_deduct_ok"):
                    sb_ex   = get_supabase()
                    deleted = 0

                    # 루프 전 단일 쿼리로 실제 존재하는 ID 일괄 확인
                    all_iids = [int(r["id"]) for _, r in export_df.iterrows()]
                    try:
                        _chk = sb_ex.table("warehouse").select("id").in_("id", all_iids).execute()
                    except Exception:
                        clear_warehouse_cache()
                        sb_ex = get_supabase()
                        try:
                            _chk = sb_ex.table("warehouse").select("id").in_("id", all_iids).execute()
                        except Exception:
                            st.error("DB 연결 오류가 발생했습니다. 잠시 후 다시 시도하세요.")
                            st.stop()
                    existing_iids = {int(r["id"]) for r in (_chk.data or [])}

                    for _, ex_row in export_df.iterrows():
                        iid = int(ex_row["id"])
                        qty = int(ex_row.get("quantity", 0))
                        if iid not in existing_iids:
                            continue
                        # 이력 먼저 기록 (삭제 전)
                        if qty > 0:
                            try:
                                sb_ex.table("history").insert({
                                    "actor_id":            user_id,
                                    "item_id":             iid,
                                    "action_type":         "out",
                                    "quantity":            qty,
                                    "reason":              f"관리자 내보내기 삭제 ({export_center})",
                                    "snapshot_qty_before": qty,
                                    "snapshot_qty_after":  0,
                                }).execute()
                            except Exception:
                                pass
                        # FK 참조 해제 후 삭제
                        try:
                            sb_ex.table("transfers").update({"item_id": None}).eq("item_id", iid).execute()
                        except Exception:
                            pass
                        try:
                            sb_ex.table("history").update({"item_id": None}).eq("item_id", iid).execute()
                        except Exception:
                            pass
                        try:
                            sb_ex.table("warehouse").delete().eq("id", iid).execute()
                            deleted += 1
                        except Exception:
                            pass
                    clear_warehouse_cache()
                    st.session_state[deduct_key] = False
                    st.success(f"✅ {deleted}개 자재 목록 삭제 완료. 아래 버튼으로 파일을 다운로드하세요.")
                    st.download_button(
                        f"⬇️ {fname} 다운로드", data=excel_buf,
                        file_name=fname,
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True, type="primary",
                        key="export_deduct_dl",
                    )
                if cc2.button("❌ 취소", use_container_width=True, key="export_deduct_cancel"):
                    st.session_state[deduct_key] = False
                    st.rerun()

        if st.button("✖️ 닫기", key="close_export"):
            st.session_state[deduct_key] = False
            st.session_state.show_export = False
            st.rerun()

# ── 엑셀 업로드 패널 ──────────────────────────────────────────────────────
if st.session_state.show_upload and user_role not in ("admin", "materials"):
    st.session_state.show_upload = False

if st.session_state.show_upload:
    with st.container(border=True):
        st.markdown("#### ⬆️ 엑셀 업로드")
        st.caption("📋 양식 버튼으로 빈 양식을 받아서 채운 후 업로드하세요.")
        if user_role != "admin":
            assigned = user.get("assigned_center") or user.get("center","")
            st.info(f"ℹ️ **{assigned}** 센터 데이터만 업로드 가능합니다.")
        uploaded = st.file_uploader("파일 선택", type=["xlsx"], label_visibility="collapsed")
        if uploaded:
            try:
                up_df = pd.read_excel(uploaded)
                col_map = {v: k for k, v in EXCEL_COL_MAP.items()}
                col_map["수리담당자명"] = "repair_manager"
                col_map["수리담당자"]   = "repair_manager"
                up_df.rename(columns=col_map, inplace=True)
                if "quantity" in up_df.columns:
                    up_df["quantity"] = pd.to_numeric(
                        up_df["quantity"], errors="coerce"
                    ).fillna(0).astype(int)
                if "location" not in up_df.columns:
                    up_df["location"] = selected_center
                passed, err_msg = validate_upload(up_df)
                if not passed:
                    st.error(err_msg)
                    st.stop()
                total_rows = len(up_df)
                up_df = up_df[up_df["item_name"].notna()]
                up_df = up_df[up_df["item_name"].astype(str).str.strip() != ""]
                removed = total_rows - len(up_df)
                up_df["last_modified_by"] = user_id
                valid_cols = {
                    "item_name","quantity","rack_no","shelf","box_no",
                    "category_large","category_mid","category_small","location",
                    "erp_name","erp_code","repair_manager","notes",
                    "item_location","last_modified_by"
                }
                up_df   = up_df[[c for c in up_df.columns if c in valid_cols]]
                records = clean_records(up_df.where(pd.notnull(up_df), None).to_dict("records"))
                if removed > 0: st.warning(f"⚠️ 자재명 없는 {removed}개 행 제외")
                qty_empty = sum(1 for r in records if not r.get("quantity"))
                if qty_empty > 0: st.info(f"ℹ️ 수량 미입력 {qty_empty}개 → 수량 0으로 등록")
                st.success(f"✅ 업로드 예정: **{len(records)}개** → **{selected_center}**")
                preview_cols = ["item_name","quantity","category_large","category_mid","location"]
                preview_df = up_df[[c for c in preview_cols if c in up_df.columns]].head(5).copy()
                preview_df.columns = [{"item_name":"자재명","quantity":"수량",
                    "category_large":"대분류","category_mid":"중분류","location":"센터"
                    }.get(c,c) for c in preview_df.columns]
                st.dataframe(preview_df, use_container_width=True, hide_index=True)
                st.caption(f"상위 5개 미리보기 (전체 {len(records)}개)")
                c1, c2 = st.columns(2)
                if c1.button("✅ 업로드 확정", type="primary",
                             use_container_width=True, key="confirm_upload"):
                    sb = get_supabase()

                    def _norm(v):
                        return str(v or "").strip()

                    # 기존 재고 조회 — (rack_no, shelf, box_no) 위치 기반 매칭
                    existing_rows = sb.table("warehouse").select(
                        "id, item_name, quantity, rack_no, shelf, box_no"
                    ).eq("location", selected_center).execute().data or []
                    existing_map = {
                        (_norm(r.get("rack_no")), _norm(r.get("shelf")), _norm(r.get("box_no"))): r
                        for r in existing_rows
                    }

                    to_insert, to_update = [], []
                    for r in records:
                        key = (
                            _norm(r.get("rack_no")),
                            _norm(r.get("shelf")),
                            _norm(r.get("box_no")),
                        )
                        add_qty = int(r.get("quantity") or 0)
                        if key in existing_map:
                            ex = existing_map[key]
                            before = int(ex["quantity"] or 0)
                            # 위치(rack/shelf/box)는 유지, 자재명·분류·ERP정보 갱신
                            meta = {k: v for k, v in r.items()
                                    if k in ("item_name", "erp_code", "erp_name",
                                             "category_large", "category_mid", "category_small")}
                            to_update.append({
                                "id":      ex["id"],
                                "before":  before,
                                "add_qty": add_qty,
                                "after":   before + add_qty,
                                "meta":    meta,
                            })
                        else:
                            to_insert.append(r)

                    # 신규 등록 + 입고 이력
                    if to_insert:
                        res = sb.table("warehouse").insert(to_insert).execute()
                        hist_ins = [
                            {
                                "actor_id":            user_id,
                                "item_id":             rec["id"],
                                "action_type":         "in",
                                "quantity":            int(rec.get("quantity") or 0),
                                "reason":              "엑셀 업로드 신규 등록",
                                "from_center":         rec.get("location", selected_center),
                                "snapshot_qty_before": 0,
                                "snapshot_qty_after":  int(rec.get("quantity") or 0),
                            }
                            for rec in (res.data or [])
                            if int(rec.get("quantity") or 0) > 0
                        ]
                        if hist_ins:
                            sb.table("history").insert(hist_ins).execute()

                    # 기존 항목: 수량 추가 + 입고 이력
                    hist_upd = []
                    for upd in to_update:
                        sb.table("warehouse").update({
                            **upd["meta"],
                            "quantity":         upd["after"],
                            "last_modified_by": user_id,
                            "last_modified_at": "now()",
                        }).eq("id", upd["id"]).execute()
                        if upd["add_qty"] > 0:
                            hist_upd.append({
                                "actor_id":            user_id,
                                "item_id":             upd["id"],
                                "action_type":         "in",
                                "quantity":            upd["add_qty"],
                                "reason":              "엑셀 업로드 입고",
                                "from_center":         selected_center,
                                "snapshot_qty_before": upd["before"],
                                "snapshot_qty_after":  upd["after"],
                            })
                    if hist_upd:
                        sb.table("history").insert(hist_upd).execute()

                    clear_warehouse_cache()
                    clear_history_cache()
                    st.session_state.upload_done = len(to_insert) + len(to_update)
                    st.session_state.show_upload = False
                if c2.button("❌ 취소", use_container_width=True, key="cancel_upload"):
                    st.session_state.show_upload = False
                    st.rerun()
            except Exception as e:
                st.error(f"업로드 오류: {e}")

# ── 사용내역 업로드 패널 (비자재센터) ────────────────────────────────────
if CAN_USAGE_UPLOAD and st.session_state.show_usage_upload:
    with st.container(border=True):
        st.markdown("#### 📋 사용내역 업로드")
        st.caption(
            "자재명 또는 ERP코드로 자재를 찾아 사용수량만큼 재고에서 차감합니다.\n\n"
            "**필수 컬럼:** 자재명(또는 ERP코드), 사용수량, 사용사유"
        )

        # 사용내역 양식 다운로드
        usage_sample = make_excel_buffer(
            pd.DataFrame(columns=list(USAGE_COL_MAP.values())), "사용내역양식"
        )
        st.download_button("📋 사용내역 양식 다운로드", data=usage_sample,
            file_name="사용내역_업로드_양식.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

        usage_file = st.file_uploader("사용내역 파일 선택", type=["xlsx"],
                                       label_visibility="collapsed", key="usage_uploader")
        if usage_file:
            try:
                u_df = pd.read_excel(usage_file)
                # 한글 컬럼명 → 영문 매핑
                col_map = {v: k for k, v in USAGE_COL_MAP.items()}
                u_df.rename(columns=col_map, inplace=True)

                # 수량 변환
                if "quantity" in u_df.columns:
                    u_df["quantity"] = pd.to_numeric(
                        u_df["quantity"], errors="coerce"
                    ).fillna(0).astype(int)

                # 유효 행만
                u_df = u_df[u_df.get("item_name", pd.Series(dtype=str)).notna() |
                            u_df.get("erp_code",  pd.Series(dtype=str)).notna()]
                u_df = u_df[u_df.get("quantity", pd.Series(dtype=int)).fillna(0) > 0]

                if u_df.empty:
                    st.warning("처리할 유효한 행이 없습니다.")
                else:
                    records = clean_records(
                        u_df.where(pd.notnull(u_df), None).to_dict("records")
                    )
                    st.success(f"✅ 처리 예정: **{len(records)}개** 항목 → **{selected_center}** 재고에서 차감")

                    # 미리보기
                    preview_cols = [c for c in ["item_name","erp_code","quantity","reason"] if c in u_df.columns]
                    prev = u_df[preview_cols].head(5).copy()
                    prev.columns = [USAGE_COL_MAP.get(c,c) for c in prev.columns]
                    st.dataframe(prev, use_container_width=True, hide_index=True)
                    st.caption(f"상위 5개 미리보기 (전체 {len(records)}개)")

                    c1, c2 = st.columns(2)
                    if c1.button("✅ 차감 확정", type="primary",
                                 use_container_width=True, key="confirm_usage"):
                        ok, not_found, insufficient = process_usage_upload(
                            records, selected_center, user
                        )
                        msg_parts = [f"✅ {ok}개 차감 완료"]
                        if not_found:
                            msg_parts.append(f"⚠️ 미발견 {len(not_found)}개: {', '.join(not_found[:3])}{'...' if len(not_found)>3 else ''}")
                        if insufficient:
                            msg_parts.append(f"⚠️ 재고부족 {len(insufficient)}개: {', '.join(insufficient[:2])}{'...' if len(insufficient)>2 else ''}")
                        st.session_state.usage_upload_done = " / ".join(msg_parts)
                        st.session_state.show_usage_upload = False
                    if c2.button("❌ 취소", use_container_width=True, key="cancel_usage"):
                        st.session_state.show_usage_upload = False
                        st.rerun()
            except Exception as e:
                st.error(f"파일 처리 오류: {e}")

# ── 자재 요청 패널 (비자재센터, 자재파트·게스트 제외) ────────────────────
if CAN_MATERIAL_REQUEST and st.session_state.show_material_request:
    with st.container(border=True):
        st.markdown("#### 📦 자재 요청")
        st.caption(
            "자재센터 보유 자재 목록에서 필요한 자재를 선택하고 수량을 입력하세요. "
            "확인 후 자재파트 담당자에게 메일이 발송됩니다."
        )

        hub_items = fetch_warehouse("자재센터")
        if not hub_items:
            st.warning("자재센터에 등록된 자재가 없습니다.")
        else:
            hub_df = pd.DataFrame(hub_items)

            _BUS_ONLY_CENTERS = {"강서센터", "강북센터", "강동센터", "강남센터"}
            if selected_center in _BUS_ONLY_CENTERS:
                if "category_large" in hub_df.columns:
                    hub_df = hub_df[hub_df["category_large"] == "버스"]
                st.info("ℹ️ 해당 센터는 **버스 자재**만 요청 가능합니다.")

            # 검색 필터
            _is_bus_restricted = selected_center in _BUS_ONLY_CENTERS
            _req_placeholder = (
                "버스 자재명 / 중분류 / ERP코드 검색..."
                if _is_bus_restricted
                else "자재명 / 대분류 / 중분류 / ERP코드..."
            )
            req_search = st.text_input(
                "자재 검색", placeholder=_req_placeholder,
                key="req_search_input", label_visibility="collapsed"
            )
            filtered_hub = hub_df.copy()
            if req_search.strip():
                if _is_bus_restricted:
                    mask = (
                        filtered_hub.get("item_name", pd.Series(dtype=str)).str.contains(req_search, case=False, na=False) |
                        filtered_hub.get("category_mid", pd.Series(dtype=str)).str.contains(req_search, case=False, na=False) |
                        filtered_hub.get("erp_code",  pd.Series(dtype=str)).str.contains(req_search, case=False, na=False)
                    )
                else:
                    mask = (
                        filtered_hub.get("item_name",      pd.Series(dtype=str)).str.contains(req_search, case=False, na=False) |
                        filtered_hub.get("category_large", pd.Series(dtype=str)).str.contains(req_search, case=False, na=False) |
                        filtered_hub.get("category_mid",   pd.Series(dtype=str)).str.contains(req_search, case=False, na=False) |
                        filtered_hub.get("erp_code",       pd.Series(dtype=str)).str.contains(req_search, case=False, na=False)
                    )
                filtered_hub = filtered_hub[mask]

            if filtered_hub.empty:
                st.info("검색 결과가 없습니다.")
            else:
                def _label(r):
                    return f"{r['item_name']}  (재고: {int(r['quantity'])}개)"
                options = {_label(r): r.to_dict() for _, r in filtered_hub.iterrows()}

                sel_label = st.selectbox(
                    "자재 선택", list(options.keys()),
                    key="req_item_select", label_visibility="collapsed"
                )
                sel_item = options[sel_label]

                rc1, rc2 = st.columns([1, 3])
                req_qty = rc1.number_input("요청수량", min_value=1, step=1,
                                           value=1, key="req_qty")
                if rc2.button("🛒 목록에 추가", key="req_add", use_container_width=True):
                    cart = st.session_state.material_request_cart
                    idx  = next((i for i, x in enumerate(cart)
                                 if x["item_id"] == int(sel_item["id"])), None)
                    if idx is not None:
                        cart[idx]["requested_qty"] = req_qty
                    else:
                        cart.append({
                            "item_id":       int(sel_item["id"]),
                            "item_name":     sel_item["item_name"],
                            "erp_code":      sel_item.get("erp_code") or "",
                            "current_qty":   int(sel_item["quantity"]),
                            "requested_qty": req_qty,
                        })
                    st.session_state.material_request_cart = cart
                    st.rerun()

        # ── 요청 목록 ─────────────────────────────────────────────────
        cart = st.session_state.material_request_cart
        if cart:
            st.divider()
            st.markdown("**요청 목록**")
            cart_rows = []
            for x in cart:
                short = x["current_qty"] < x["requested_qty"]
                cart_rows.append({
                    "자재명":   x["item_name"],
                    "현재재고": x["current_qty"],
                    "요청수량": x["requested_qty"],
                    "재고상태": "⚠️ 재고부족" if short else "✅ 충분",
                })
            st.dataframe(pd.DataFrame(cart_rows),
                         use_container_width=True, hide_index=True)

            bc1, bc2, bc3 = st.columns([2, 1, 1])
            if bc1.button("📨 요청 발송", type="primary",
                          use_container_width=True, key="req_send"):
                sb = get_supabase()
                _res_mat   = sb.table("users").select("email") \
                               .eq("role", "materials").eq("is_approved", True).execute()
                _res_adm   = sb.table("users").select("email") \
                               .eq("role", "admin").eq("is_approved", True).execute()
                mat_emails = list({
                    u["email"]
                    for res in (_res_mat, _res_adm)
                    for u in (res.data or [])
                    if u.get("email")
                })

                if not mat_emails:
                    st.error("자재파트 담당자 이메일을 찾을 수 없습니다. 관리자에게 문의하세요.")
                else:
                    from utils.mail import send_material_request as _send_req
                    try:
                        # DB 저장
                        submit_material_request(
                            requester_id    = user_id,
                            requester_name  = user_name,
                            requester_email = user.get("email",""),
                            from_center     = selected_center,
                            items           = cart,
                        )
                        # 메일 발송
                        _send_req(mat_emails, selected_center, user_name, cart)
                        any_short = any(x["current_qty"] < x["requested_qty"] for x in cart)
                        if any_short:
                            st.success(
                                "✅ 요청 메일이 발송됐습니다.\n\n"
                                "⚠️ 일부 자재는 재고가 부족합니다. 구매 검토 내용이 함께 전달됐습니다."
                            )
                        else:
                            st.success("✅ 자재 요청 메일이 자재파트에 발송됐습니다.")
                        st.session_state.material_request_cart   = []
                        st.session_state.show_material_request   = False
                        st.rerun()
                    except Exception as e:
                        st.error(f"메일 발송 오류: {e}")

            if bc2.button("🗑️ 초기화", use_container_width=True, key="req_clear"):
                st.session_state.material_request_cart = []
                st.rerun()
            if bc3.button("✖️ 닫기", use_container_width=True, key="req_close"):
                st.session_state.show_material_request = False
                st.session_state.material_request_cart = []
                st.rerun()
        else:
            if st.button("✖️ 닫기", use_container_width=True, key="req_close_empty"):
                st.session_state.show_material_request = False
                st.rerun()

# ── 벌크 입출고 패널 (자재센터 전용) ─────────────────────────────────────
if SHOW_STOCK_BUTTONS and st.session_state.bulk_mode:
    mode  = st.session_state.bulk_mode
    ids   = st.session_state.checked_ids
    title = "📥 일괄 입고" if mode == "in" else "📤 일괄 출고"
    with st.container(border=True):
        st.markdown(f"#### {title} — 선택된 자재 {len(ids)}개")
        if not ids:
            st.warning("⚠️ 목록에서 체크박스로 자재를 먼저 선택해주세요.")
            if st.button("닫기", key="bulk_close_empty"):
                st.session_state.bulk_mode = None
                st.rerun()
            st.stop()
        if not df_all.empty and ids:
            sel_rows = df_all[df_all["id"].isin(ids)]
            if not sel_rows.empty:
                st.dataframe(
                    sel_rows[["item_name","quantity","category_large","category_mid"]
                    ].rename(columns={"item_name":"자재명","quantity":"현재수량",
                                      "category_large":"대분류","category_mid":"중분류"}),
                    use_container_width=True, hide_index=True)
        c_qty, c_reason = st.columns([1, 3])
        with c_qty:
            bulk_qty = st.number_input("수량 (전체 동일 적용)", min_value=1, step=1,
                                       value=1, key="bulk_qty")
        with c_reason:
            bulk_reason = st.text_input("사유 * (필수)",
                placeholder="예: 현장 납품, 불량 반입, 정기 재고 조정 등",
                key="bulk_reason")
        c1, c2 = st.columns(2)
        if c1.button("✅ 확정", type="primary", use_container_width=True,
                     key="bulk_confirm"):
            if not bulk_reason.strip():
                st.error("⚠️ 사유를 반드시 입력해야 합니다.")
            else:
                ok_count, fail_count = 0, 0
                for rid in ids:
                    ok = stock_in(rid, bulk_qty, user, bulk_reason) if mode == "in" \
                         else stock_out(rid, bulk_qty, user, bulk_reason)
                    if ok: ok_count += 1
                    else:  fail_count += 1
                st.session_state.bulk_mode   = None
                st.session_state.checked_ids = []
                msg = f"✅ {ok_count}개 처리 완료"
                if fail_count: msg += f" / ⚠️ {fail_count}개 실패"
                st.success(msg)
                st.rerun()
        if c2.button("❌ 취소", use_container_width=True, key="bulk_cancel"):
            st.session_state.bulk_mode = None
            st.rerun()

# ── 이동 신청 패널 ────────────────────────────────────────────────────────
if st.session_state.checked_ids and st.session_state.show_transfer:
    allowed = get_allowed_destinations(selected_center)
    with st.container(border=True):
        st.markdown(f"#### 🚚 이동 신청 — 선택된 자재 {len(st.session_state.checked_ids)}개")
        if not allowed:
            st.error("이 센터에서는 이동 신청이 불가합니다.")
        else:
            c1, c2, c3 = st.columns([2, 1, 1])
            with c1:
                to_center = st.selectbox("받는 센터", allowed, key="mv_to_center")
            with c2:
                mv_qty = st.number_input("수량", min_value=1, step=1, value=1, key="mv_qty")
            with c3:
                st.write("")
                st.write("")
                if st.button("✅ 신청 확정", type="primary",
                             use_container_width=True, key="mv_confirm"):
                    ok_count = 0
                    for rid in st.session_state.checked_ids:
                        if create_transfer(user_id, selected_center, to_center, rid, mv_qty):
                            ok_count += 1
                    st.session_state.checked_ids  = []
                    st.session_state.show_transfer = False
                    st.success(f"🚚 {ok_count}개 자재 이동 신청 완료!")
                    st.rerun()

# ── 분류 필터 값 읽기 (필터 바에서 이미 설정됨) ─────────────────────────
selected_large = st.session_state.selected_large
selected_small = st.session_state.get("selected_small", "전체")

# ── 데이터 필터링 ─────────────────────────────────────────────────────────
df = df_all.copy() if not df_all.empty else pd.DataFrame()
if not df.empty:
    if search_query:
        mask = (
            df.get("item_name",      pd.Series(dtype=str)).str.contains(search_query, case=False, na=False) |
            df.get("erp_code",       pd.Series(dtype=str)).str.contains(search_query, case=False, na=False) |
            df.get("category_large", pd.Series(dtype=str)).str.contains(search_query, case=False, na=False) |
            df.get("category_mid",   pd.Series(dtype=str)).str.contains(search_query, case=False, na=False) |
            df.get("rack_no",        pd.Series(dtype=str)).str.contains(search_query, case=False, na=False)
        )
        df = df[mask]
    if selected_large != "전체":
        df = df[df.get("category_large","") == selected_large]
    if st.session_state.selected_mid != "전체":
        df = df[df.get("category_mid","") == st.session_state.selected_mid]
    if selected_small != "전체":
        df = df[df.get("category_small","") == selected_small]

# ── 정렬 적용 ─────────────────────────────────────────────────────────────
if not df.empty:
    sc  = st.session_state.sort_col
    asc = (st.session_state.sort_dir == "asc")
    if sc in df.columns:
        df = df.sort_values(sc, ascending=asc, na_position="last")

# ── 필터 변경 감지 → 1페이지로 리셋 ──────────────────────────────────────
_fhash = f"{search_query}|{selected_large}|{st.session_state.selected_mid}|{selected_small}|{selected_center}|{st.session_state.sort_col}|{st.session_state.sort_dir}"
if st.session_state.filter_hash != _fhash:
    st.session_state.filter_hash = _fhash
    st.session_state.page_num    = 1

# ── 페이지 계산 ───────────────────────────────────────────────────────────
total_items = len(df)
page_size   = st.session_state.page_size
total_pages = max(1, (total_items + page_size - 1) // page_size)
if st.session_state.page_num > total_pages:
    st.session_state.page_num = 1
pg = st.session_state.page_num
p_start = (pg - 1) * page_size
df_page = df.iloc[p_start : p_start + page_size] if not df.empty else df

n_checked = len(st.session_state.checked_ids)
hint = f"  ·  {n_checked}개 선택됨" if n_checked else ""
st.caption(f"총 {total_items}개 항목  ·  {p_start + 1}–{min(p_start + page_size, total_items)}번째{hint}")

# ── 이동 신청 버튼 ────────────────────────────────────────────────────────
if st.session_state.checked_ids and CAN_TRANSFER:
    col_mv, _ = st.columns([2, 6])
    with col_mv:
        mv_label = "🚚 이동 신청 닫기" if st.session_state.show_transfer else "🚚 이동 신청"
        if st.button(mv_label, use_container_width=True, type="primary"):
            st.session_state.show_transfer = not st.session_state.show_transfer
            st.rerun()

# ── 페이지 컨트롤 ─────────────────────────────────────────────────────────
if total_items > 0:
    pg_c1, pg_c2, pg_c3, pg_c4, pg_c5 = st.columns([0.7, 1.2, 1.4, 1.3, 0.7])
    with pg_c1:
        if st.button("◀ 이전", use_container_width=True, disabled=(pg <= 1)):
            st.session_state.page_num -= 1
            st.rerun()
    with pg_c2:
        sel_page = st.selectbox(
            "page", list(range(1, total_pages + 1)),
            index=pg - 1, label_visibility="collapsed", key="page_select"
        )
        if sel_page != pg:
            st.session_state.page_num = sel_page
            st.rerun()
    with pg_c3:
        st.markdown(
            f"<div style='text-align:center;padding-top:6px;font-size:13px;'>"
            f"/ {total_pages} 페이지</div>",
            unsafe_allow_html=True
        )
    with pg_c4:
        sel_size = st.selectbox(
            "size", [20, 50, 100, 200],
            index=[20, 50, 100, 200].index(page_size) if page_size in [20,50,100,200] else 1,
            label_visibility="collapsed", key="page_size_select",
            format_func=lambda x: f"{x}개씩"
        )
        if sel_size != page_size:
            st.session_state.page_size = sel_size
            st.session_state.page_num  = 1
            st.rerun()
    with pg_c5:
        if st.button("다음 ▶", use_container_width=True, disabled=(pg >= total_pages)):
            st.session_state.page_num += 1
            st.rerun()

# ── 자재 목록 테이블 ──────────────────────────────────────────────────────
if df.empty:
    st.info("📭 등록된 자재가 없습니다.")
else:
    # ① 현재 페이지 데이터 준비
    page_rows, id_col = [], []
    for _row_idx, (_, row) in enumerate(df_page.iterrows(), start=p_start + 1):
        row_id = int(row["id"])
        id_col.append(row_id)
        base = {
            "☑":    row_id in st.session_state.checked_ids,
            "No":   _row_idx,
            "자재명": str(row.get("item_name", "") or ""),
            "수량":  int(row.get("quantity", 0)),
            "대분류": str(row.get("category_large", "") or ""),
            "중분류": str(row.get("category_mid",   "") or ""),
            "소분류": str(row.get("category_small", "") or ""),
        }
        if IS_MAIN_HUB:
            base.update({
                "위치(랙)": str(row.get("rack_no",       "") or ""),
                "지역":     str(row.get("item_location", "") or ""),
                "단":       str(row.get("shelf",         "") or ""),
                "박스":     str(row.get("box_no",        "") or ""),
                "ERP품명":  str(row.get("erp_name",      "") or ""),
                "ERP코드":  str(row.get("erp_code",      "") or ""),
            })
        else:
            base["지역"] = str(row.get("item_location", "") or "")
        page_rows.append(base)

    item_labels = [r["자재명"] for r in page_rows if r.get("자재명")]
    item_id_map = {r["자재명"]: id_col[i] for i, r in enumerate(page_rows) if r.get("자재명")}

    # ② 자재 상세 보기 — 테이블 위에 배치해서 항상 노출
    if item_labels:
        default_nm = None
        if st.session_state.checked_ids:
            for sel_id in st.session_state.checked_ids:
                if sel_id in id_col:
                    default_nm = page_rows[id_col.index(sel_id)].get("자재명")
                    break
        default_idx = item_labels.index(default_nm) if default_nm in item_labels else 0

        dc1, dc2 = st.columns([5, 1])
        with dc1:
            chosen_nm = st.selectbox(
                "자재 상세 선택", item_labels, index=default_idx,
                label_visibility="collapsed", key="detail_item_sel"
            )
        with dc2:
            if st.button("📋 상세 보기", use_container_width=True, key="open_detail_btn"):
                chosen_id = item_id_map.get(chosen_nm)
                if chosen_id:
                    r = df_page[df_page["id"] == chosen_id]
                    item_loc = str(r.iloc[0].get("location", "")) if not r.empty else ""
                    item_detail_modal(chosen_id, chosen_nm, item_loc)

    # ③ 테이블 렌더링
    disp_df = pd.DataFrame(page_rows)
    if "단" in disp_df.columns:
        disp_df["단"] = pd.to_numeric(disp_df["단"].replace("", None), errors="coerce")

    if IS_MAIN_HUB:
        col_cfg = {
            "☑":       st.column_config.CheckboxColumn("☑",      width=30),
            "No":      st.column_config.NumberColumn("No",       width=45),
            "자재명":  st.column_config.TextColumn("자재명",      width=200),
            "수량":    st.column_config.NumberColumn("수량",      width=65),
            "대분류":  st.column_config.TextColumn("대분류",      width=90),
            "중분류":  st.column_config.TextColumn("중분류",      width=90),
            "소분류":  st.column_config.TextColumn("소분류",      width=90),
            "위치(랙)": st.column_config.TextColumn("위치(랙)",  width=80),
            "지역":    st.column_config.TextColumn("지역",        width=65),
            "단":      st.column_config.NumberColumn("단",         width=50, format="%.0f"),
            "박스":    st.column_config.TextColumn("박스",        width=65),
            "ERP품명": st.column_config.TextColumn("ERP품명",    width=130),
            "ERP코드": st.column_config.TextColumn("ERP코드",    width=110),
        }
    else:
        col_cfg = {
            "☑":      st.column_config.CheckboxColumn("☑",       width=30),
            "No":     st.column_config.NumberColumn("No",        width=45),
            "자재명": st.column_config.TextColumn("자재명",       width=260),
            "수량":   st.column_config.NumberColumn("수량",       width=65),
            "대분류": st.column_config.TextColumn("대분류",       width=110),
            "중분류": st.column_config.TextColumn("중분류",       width=110),
            "소분류": st.column_config.TextColumn("소분류",       width=110),
            "지역":   st.column_config.TextColumn("지역",         width=90),
        }

    _tbl_key = "wh_tbl_" + hashlib.md5(
        (selected_center + str(pg) + search_query
         + selected_large + st.session_state.selected_mid + selected_small
        ).encode()
    ).hexdigest()[:10]

    edited = st.data_editor(
        disp_df,
        use_container_width=True,
        hide_index=True,
        height=min(max(len(disp_df) * 35 + 40, 200), 620),
        column_config=col_cfg,
        disabled=[c for c in disp_df.columns if c != "☑"],
        key=_tbl_key,
    )

    # ④ 체크박스 변경 감지 → checked_ids 동기화
    new_ids = [id_col[i] for i, v in enumerate(edited["☑"].tolist()) if v and i < len(id_col)]
    if set(new_ids) != set(st.session_state.checked_ids):
        st.session_state.checked_ids = new_ids
        st.rerun()
