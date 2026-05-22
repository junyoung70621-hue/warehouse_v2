# pages/06_mypage.py
import streamlit as st
from utils.auth import require_login, verify_password, hash_password, is_role, logout
from utils.db import get_supabase
from utils.routing import CENTERS
from utils.permissions import get_viewable_centers
from utils.ui import apply_global_css, render_sidebar_header, render_sidebar_section, render_sidebar_user, render_top_bar

st.set_page_config(
    page_title="에이텍모빌리티 자재관리",
    page_icon="favicon_32.png",
    layout="centered",
    initial_sidebar_state="expanded",
)

apply_global_css()
st.markdown("""
<style>
.main .block-container { max-width:520px!important; }
</style>
""", unsafe_allow_html=True)

require_login()

user      = st.session_state.user
user_id   = user["id"]
user_name = user["name"]
user_role = user["role"]
sb        = get_supabase()

ROLE_LABELS = {
    "admin":"관리자","materials":"자재파트",
    "manager":"센터장/파트장","user":"사용자","guest":"게스트",
}

with st.sidebar:
    render_sidebar_header()
    if st.button("자재현황(전체)", use_container_width=True):
        st.switch_page("pages/10_dashboard.py")
    if st.button("버스단말기 현황", use_container_width=True):
        st.switch_page("pages/14_terminal_dashboard.py")
    st.divider()
    viewable = get_viewable_centers(user)
    if st.session_state.get("sidebar_center") not in viewable:
        st.session_state.pop("sidebar_center", None)
    st.selectbox("센터", viewable, label_visibility="collapsed", key="sidebar_center")

    render_sidebar_section("재고 관리")
    if st.button("📦 재고 현황", use_container_width=True):
        st.switch_page("pages/15_combined.py")
    if st.button("🚚 이동 신청 현황", use_container_width=True):
        st.switch_page("pages/15_combined.py")
    if st.button("🗂️ 통합 뷰", use_container_width=True):
        st.switch_page("pages/15_combined.py")
    if st.button("📋 입출고 이력", use_container_width=True):
        st.switch_page("pages/04_history.py")
    if not is_role("guest"):
        if st.button("📊 사용내역", use_container_width=True):
            st.switch_page("pages/08_usage_history.py")

    if not is_role("guest"):
        render_sidebar_section("요청")
        if st.button("📦 자재요청현황", use_container_width=True, key="sidebar_mat_req"):
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
    st.button("👤 마이페이지", use_container_width=True, type="primary")
    if st.button("🚪 로그아웃", use_container_width=True):
        logout()
    render_sidebar_user(user)

render_top_bar("마이페이지", user)
st.markdown("## 👤 마이페이지")
st.divider()

tab_info, tab_pw = st.tabs(["📋 내 정보 수정","🔑 비밀번호 변경"])

with tab_info:
    st.subheader("내 정보")
    st.info(
        f"**아이디:** {user.get('username','')}  |  "
        f"**권한:** {ROLE_LABELS.get(user_role,user_role)}  |  "
        f"**소속:** {user.get('assigned_center') or user.get('center','미지정')}  |  "
        f"**승인:** {'✅' if user.get('is_approved') else '⏳'}"
    )
    with st.form("form_myinfo"):
        new_name   = st.text_input("이름 *",        value=user.get("name",""))
        new_email  = st.text_input("회사 이메일 *", value=user.get("email",""))
        new_phone  = st.text_input("연락처",         value=user.get("phone","") or "")
        submitted  = st.form_submit_button("저장", use_container_width=True, type="primary")
    if submitted:
        if not new_name or not new_email:
            st.warning("이름과 이메일은 필수입니다.")
        else:
            try:
                sb.table("users").update({
                    "name":  new_name,
                    "email": new_email,
                    "phone": new_phone,
                }).eq("id", user_id).execute()
                st.session_state.user["name"]  = new_name
                st.session_state.user["email"] = new_email
                st.session_state.user["phone"] = new_phone
                st.success("정보가 업데이트됐습니다!")
            except Exception as e:
                st.error(f"저장 오류: {e}")

with tab_pw:
    st.subheader("비밀번호 변경")
    with st.form("form_pw"):
        current_pw = st.text_input("현재 비밀번호",          type="password")
        new_pw     = st.text_input("새 비밀번호 (6자 이상)", type="password")
        new_pw2    = st.text_input("새 비밀번호 확인",        type="password")
        pw_submit  = st.form_submit_button("변경", use_container_width=True, type="primary")
    if pw_submit:
        if not all([current_pw, new_pw, new_pw2]):
            st.warning("모든 항목을 입력하세요.")
        elif new_pw != new_pw2:
            st.error("새 비밀번호가 일치하지 않습니다.")
        elif len(new_pw) < 6:
            st.error("비밀번호는 6자 이상이어야 합니다.")
        else:
            res = sb.table("users").select("password_hash").eq("id",user_id).single().execute()
            if not verify_password(current_pw, res.data["password_hash"]):
                st.error("현재 비밀번호가 올바르지 않습니다.")
            else:
                sb.table("users").update({
                    "password_hash": hash_password(new_pw)
                }).eq("id",user_id).execute()
                st.success("비밀번호가 변경됐습니다!")

