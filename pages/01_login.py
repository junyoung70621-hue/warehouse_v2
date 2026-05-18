# pages/01_login.py
import streamlit as st
import os
import base64
from datetime import datetime
from utils.auth import login, register, reset_password
from utils.routing import CENTERS
from utils.ui import apply_global_css

def _logo_b64(filename: str) -> str:
    _p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), filename)
    try:
        with open(_p, "rb") as f:
            return base64.b64encode(f.read()).decode()
    except Exception:
        return ""

_LOGIN_LOGO = _logo_b64("logo.png")

st.set_page_config(
    page_title="에이텍모빌리티 자재관리",
    page_icon="favicon_32.png",
    layout="centered"
)

apply_global_css()
st.markdown("""
<style>
.main .block-container { max-width:480px!important; padding-top:3rem!important; }
div[data-testid="stTextInput"] input {
    background:#F1F5F9 !important;
    border:1px solid #D3004F !important;
    color:#1E293B !important;
    font-size:14px !important;
    height:40px !important;
}
div[data-testid="stTextInput"] input::placeholder {
    color:#94A3B8 !important;
}
div[data-testid="stTextInput"] input:focus {
    border-color:#D3004F !important;
    box-shadow:0 0 0 2px rgba(211,0,79,0.12) !important;
    background:#FFFFFF !important;
}
</style>
""", unsafe_allow_html=True)

if st.session_state.get("user"):
    st.switch_page("pages/14_terminal_dashboard.py")

if _LOGIN_LOGO:
    st.markdown(
        f'<img src="data:image/png;base64,{_LOGIN_LOGO}" '
        f'style="max-width:320px;width:100%;height:auto;display:block;margin:0 auto 8px auto;">',
        unsafe_allow_html=True
    )
else:
    st.markdown("## ATEC 에이텍모빌리티")
st.markdown(
    "<p style='text-align:center;color:#6c757d;font-size:15px;margin-top:4px;'>자재관리 시스템</p>",
    unsafe_allow_html=True
)
st.divider()

tab_login, tab_register, tab_reset = st.tabs([
    "🔑 로그인", "✏️ 회원가입", "🔓 비밀번호 찾기"
])

with tab_login:
    # localStorage에 저장된 아이디 불러오기 (페이지 로드 시 입력창 자동 완성)
    st.markdown("""
    <script>
    (function(){
        function loadSavedId(){
            var saved = localStorage.getItem('wms_saved_id');
            if(!saved) return;
            var inputs = document.querySelectorAll('[data-testid="stTextInput"] input[type="text"]');
            if(!inputs.length) return;
            var inp = inputs[0];
            if(inp.value) return;
            var setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;
            setter.call(inp, saved);
            inp.dispatchEvent(new Event('input',{bubbles:true}));
            inp.dispatchEvent(new Event('change',{bubbles:true}));
        }
        [500,1100,2200].forEach(function(t){ setTimeout(loadSavedId, t); });
    })();
    </script>
    """, unsafe_allow_html=True)

    remember_me = st.checkbox(
        "아이디 저장",
        value=bool(st.session_state.get("saved_id")),
        key="remember_cb"
    )

    with st.form("form_login"):
        username  = st.text_input("아이디", value=st.session_state.get("saved_id", ""))
        password  = st.text_input("비밀번호", type="password")
        submitted = st.form_submit_button("로그인", use_container_width=True)

    if submitted:
        if not username or not password:
            st.warning("아이디와 비밀번호를 입력하세요.")
        else:
            if remember_me:
                st.session_state.saved_id = username
                import json as _json
                st.markdown(
                    f"<script>localStorage.setItem('wms_saved_id',{_json.dumps(username)});</script>",
                    unsafe_allow_html=True
                )
            else:
                st.session_state.pop("saved_id", None)
                st.markdown(
                    "<script>localStorage.removeItem('wms_saved_id');</script>",
                    unsafe_allow_html=True
                )
            user = login(username, password)
            if user:
                st.session_state.user = user
                st.session_state.login_time    = datetime.now()
                st.session_state.last_activity = datetime.now()
                st.success(f"환영합니다, {user['name']}님!")
                st.switch_page("pages/14_terminal_dashboard.py")

with tab_register:
    with st.form("form_register"):
        r_username  = st.text_input("아이디 *")
        r_password  = st.text_input("비밀번호 * (6자 이상)", type="password")
        r_password2 = st.text_input("비밀번호 확인 *", type="password")
        r_name      = st.text_input("이름 *")
        r_email     = st.text_input("회사 이메일 *")
        r_phone     = st.text_input("연락처")
        r_center    = st.selectbox("소속 센터 *", CENTERS)
        r_submit    = st.form_submit_button("회원가입 신청", use_container_width=True)
    if r_submit:
        if not all([r_username, r_password, r_password2, r_name, r_email]):
            st.warning("* 표시 항목은 필수입니다.")
        elif r_password != r_password2:
            st.error("비밀번호가 일치하지 않습니다.")
        elif len(r_password) < 6:
            st.error("비밀번호는 6자 이상이어야 합니다.")
        else:
            register(r_username, r_password, r_name, r_email, r_phone, r_center)

with tab_reset:
    st.caption("가입 시 등록한 회사 이메일로 임시 비밀번호를 발송합니다.")
    with st.form("form_reset"):
        reset_email  = st.text_input("회사 이메일")
        reset_submit = st.form_submit_button("임시 비밀번호 발송", use_container_width=True)
    if reset_submit:
        if not reset_email:
            st.warning("이메일을 입력하세요.")
        else:
            reset_password(reset_email)
