# pages/04_history.py
import streamlit as st
import pandas as pd
import io
from utils.auth import require_login, is_role
from utils.db import fetch_history
from utils.permissions import get_viewable_centers
from utils.ui import apply_global_css, render_sidebar_header, render_sidebar_section, render_sidebar_user, render_top_bar

st.set_page_config(
    page_title="에이텍모빌리티 자재관리",
    page_icon="favicon_32.png",
    layout="wide",
    initial_sidebar_state="expanded",
)

apply_global_css()
require_login()

user      = st.session_state.user
user_role = user["role"]
user_name = user["name"]

with st.sidebar:
    render_sidebar_header()
    if st.button("📊 대시보드(자재)", use_container_width=True):
        st.switch_page("pages/10_dashboard.py")
    if is_role("admin"):
        if st.button("📟 대시보드(단말기)", use_container_width=True):
            st.switch_page("pages/14_terminal_dashboard.py")
    st.divider()
    viewable = get_viewable_centers(user)
    if st.session_state.get("sidebar_center") not in viewable:
        st.session_state.pop("sidebar_center", None)
    selected_center = st.selectbox("센터", viewable, label_visibility="collapsed", key="sidebar_center")

    render_sidebar_section("재고 관리")
    if st.button("📦 재고 현황", use_container_width=True):
        st.switch_page("pages/02_warehouse.py")
    if st.button("🚚 이동 신청 현황", use_container_width=True):
        st.switch_page("pages/03_transfers.py")
    st.button("📋 입출고 이력", use_container_width=True, type="primary")
    if not is_role("guest"):
        if st.button("📊 사용내역", use_container_width=True):
            st.switch_page("pages/08_usage_history.py")

    if not is_role("guest"):
        render_sidebar_section("요청")
        if st.button("📦 자재 요청", use_container_width=True, key="sidebar_mat_req"):
            st.switch_page("pages/07_material_requests.py")
        if st.button("🛒 구매 요청", use_container_width=True, key="sidebar_pur_req"):
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

    st.divider()
    if st.button("💬 문의하기", use_container_width=True):
        st.switch_page("pages/12_inquiry.py")
    if st.button("👤 마이페이지", use_container_width=True):
        st.switch_page("pages/06_mypage.py")
    if st.button("🚪 로그아웃", use_container_width=True):
        st.session_state.user = None
        st.switch_page("pages/01_login.py")
    render_sidebar_user(user)

render_top_bar("입출고 이력", user)
st.markdown("## 📋 입출고 이력")
st.divider()

fc1, fc2, fc3 = st.columns([2, 2, 1])
with fc1:
    filter_action = st.selectbox(
        "작업 유형",
        ["전체","입고(in)","출고(out)","이동(transfer)","수정(edit)"],
        label_visibility="collapsed"
    )
with fc2:
    filter_search = st.text_input(
        "검색", placeholder="자재명 / 작업자 / 사유 검색...",
        label_visibility="collapsed"
    )
with fc3:
    filter_limit = st.selectbox(
        "표시 건수", [100,200,500,1000],
        label_visibility="collapsed"
    )

action_map = {
    "전체":None,"입고(in)":"in","출고(out)":"out",
    "이동(transfer)":"transfer","수정(edit)":"edit"
}
action_filter = action_map[filter_action]

raw = fetch_history(action_type=action_filter, limit=filter_limit)

# 선택 센터로 필터링
if selected_center:
    raw = [h for h in raw if
           h.get("from_center") == selected_center or
           h.get("to_center") == selected_center or
           (isinstance(h.get("warehouse"), dict) and h["warehouse"].get("location") == selected_center)]

if not raw:
    st.info("이력이 없습니다.")
    st.stop()

rows = []
for h in raw:
    item_info  = h.get("warehouse",{}) or {}
    actor_info = h.get("users",{})    or {}
    action_label = {"in":"📥 입고","out":"📤 출고",
                    "transfer":"🚚 이동","edit":"✏️ 수정"}.get(
        h.get("action_type",""), h.get("action_type",""))
    route = ""
    if h.get("from_center") and h.get("to_center"):
        route = f"{h['from_center']} → {h['to_center']}"
    rows.append({
        "일시":    (h.get("acted_at","") or "")[:16].replace("T"," "),
        "작업자":  actor_info.get("name","") if isinstance(actor_info,dict) else "",
        "자재명":  item_info.get("item_name","") if isinstance(item_info,dict) else "",
        "센터":    item_info.get("location","") if isinstance(item_info,dict) else "",
        "작업유형": action_label,
        "수량":    h.get("quantity",0),
        "변경전":  h.get("snapshot_qty_before",""),
        "변경후":  h.get("snapshot_qty_after",""),
        "이동경로": route,
        "사유":    h.get("reason",""),
    })

df_hist = pd.DataFrame(rows)
if filter_search:
    mask = (
        df_hist["자재명"].str.contains(filter_search, case=False, na=False) |
        df_hist["작업자"].str.contains(filter_search, case=False, na=False) |
        df_hist["사유"].str.contains(filter_search, case=False, na=False)
    )
    df_hist = df_hist[mask]

st.caption(f"총 {len(df_hist)}건")

st.dataframe(
    df_hist,
    use_container_width=True,
    hide_index=True,
    height=min(max(len(df_hist)*35+40, 200), 600),
    column_config={
        "일시":     st.column_config.TextColumn("일시",     width=130),
        "작업자":   st.column_config.TextColumn("작업자",   width=80),
        "자재명":   st.column_config.TextColumn("자재명",   width=200),
        "센터":     st.column_config.TextColumn("센터",     width=90),
        "작업유형": st.column_config.TextColumn("작업유형", width=90),
        "수량":     st.column_config.NumberColumn("수량",   width=60),
        "변경전":   st.column_config.NumberColumn("변경전", width=60),
        "변경후":   st.column_config.NumberColumn("변경후", width=60),
        "이동경로": st.column_config.TextColumn("이동경로", width=160),
        "사유":     st.column_config.TextColumn("사유",     width=200),
    }
)

buf = io.BytesIO()
with pd.ExcelWriter(buf, engine="openpyxl") as writer:
    df_hist.to_excel(writer, index=False, sheet_name="이력")
buf.seek(0)
st.download_button(
    "⬇️ 이력 엑셀 다운로드", data=buf,
    file_name="WMS_입출고이력.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    use_container_width=True
)
