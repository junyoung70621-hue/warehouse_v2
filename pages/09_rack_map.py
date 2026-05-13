# pages/09_rack_map.py
import streamlit as st
from utils.auth import require_login, is_role
from utils.rack_map import RACK_COORD, get_rack_map_image
from utils.ui import apply_global_css, render_sidebar_header, render_sidebar_user, render_top_bar
from utils.permissions import get_center as _get_center, get_viewable_centers

st.set_page_config(
    page_title="에이텍모빌리티 자재관리",
    page_icon="📍",
    layout="wide",
    initial_sidebar_state="expanded",
)

apply_global_css()
require_login()

user      = st.session_state.user
user_role = user["role"]
user_name = user["name"]
user_center = _get_center(user)

if user_role not in ("admin", "materials"):
    st.error("🔒 관리자 및 자재파트만 접근 가능합니다.")
    st.stop()

# ── 사이드바 ──────────────────────────────────────────────────────────────
with st.sidebar:
    render_sidebar_header()
    if st.button("📊 대시보드", use_container_width=True):
        st.switch_page("pages/10_dashboard.py")
    st.divider()
    viewable = get_viewable_centers(user)
    if st.session_state.get("sidebar_center") not in viewable:
        st.session_state.pop("sidebar_center", None)
    st.selectbox("센터", viewable, label_visibility="collapsed", key="sidebar_center")
    st.divider()
    if st.button("📦 재고 현황", use_container_width=True):
        st.switch_page("pages/02_warehouse.py")
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
        if st.button("🛒 구매 요청", use_container_width=True):
            st.switch_page("pages/11_purchase_requests.py")
    if is_role("admin", "materials"):
        st.button("📍 위치 지도", use_container_width=True, type="primary")
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

render_top_bar("위치 지도", user)

# ── 타이틀 ────────────────────────────────────────────────────────────────
st.markdown("## 📍 자재센터 랙 위치 지도")
st.divider()

# ── 랙 선택 ───────────────────────────────────────────────────────────────
rack_from_session = st.session_state.get("map_rack_no", "")
item_name_hint    = st.session_state.get("map_item_name", "")

all_racks = sorted(RACK_COORD.keys(), key=lambda x: (
    int(x.split("-")[0]) if "-" in x else int(x),
    int(x.split("-")[1]) if "-" in x else 0,
))

col_sel, col_back = st.columns([3, 1])
with col_sel:
    default_idx = all_racks.index(rack_from_session) if rack_from_session in all_racks else 0
    selected_rack = st.selectbox(
        "랙 선택",
        all_racks,
        index=default_idx,
        label_visibility="collapsed",
        format_func=lambda r: f"랙 {r}" + (f"  ← {item_name_hint}" if r == rack_from_session and item_name_hint else ""),
    )
with col_back:
    if st.button("◀ 창고 목록으로", use_container_width=True):
        st.switch_page("pages/02_warehouse.py")

if item_name_hint and selected_rack == rack_from_session:
    st.caption(f"🔍 **{item_name_hint}** 위치")

# ── 지도 렌더링 ───────────────────────────────────────────────────────────
buf = get_rack_map_image(selected_rack, marker_size=55)

if buf is None:
    st.warning("map.jpg 파일이 없거나 Pillow 패키지가 설치되지 않았습니다.")
else:
    st.image(buf, caption=f"📍 랙 {selected_rack} 위치", use_column_width=True)
