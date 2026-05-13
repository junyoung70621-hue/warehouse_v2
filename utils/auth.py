# utils/auth.py
import bcrypt
import secrets
import string
import streamlit as st
from utils.db import get_supabase


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def login(username: str, password: str) -> dict | None:
    sb  = get_supabase()
    res = sb.table("users").select("*").eq("username", username).execute()
    if not res.data:
        st.error("아이디 또는 비밀번호가 올바르지 않습니다.")
        return None
    user = res.data[0]
    if not verify_password(password, user["password_hash"]):
        st.error("아이디 또는 비밀번호가 올바르지 않습니다.")
        return None
    if not user["is_approved"]:
        st.warning("관리자 승인 대기 중입니다.")
        return None
    return user


def register(
    username: str, password: str,
    name: str, email: str, phone: str, center: str
) -> bool:
    sb = get_supabase()
    if sb.table("users").select("id").eq("username", username).execute().data:
        st.error("이미 사용 중인 아이디입니다.")
        return False
    if sb.table("users").select("id").eq("email", email).execute().data:
        st.error("이미 등록된 이메일입니다.")
        return False
    try:
        sb.table("users").insert({
            "username":      username,
            "password_hash": hash_password(password),
            "name":          name,
            "email":         email,
            "phone":         phone,
            "center":        center,
            "role":          "guest",
            "is_approved":   False
        }).execute()
        st.success("회원가입 완료! 관리자 승인 후 로그인하세요.")
        return True
    except Exception as e:
        st.error(f"회원가입 오류: {e}")
        return False


def generate_temp_password(length: int = 10) -> str:
    chars = string.ascii_letters + string.digits
    return "".join(secrets.choice(chars) for _ in range(length))


def reset_password(email: str) -> bool:
    from utils.mail import send_temp_password
    sb  = get_supabase()
    res = sb.table("users").select("*").eq("email", email).execute()
    if not res.data:
        st.error("등록된 이메일이 아닙니다.")
        return False
    user   = res.data[0]
    temp_pw = generate_temp_password()
    try:
        send_temp_password(email, user["name"], temp_pw)
        sb.table("users").update({
            "password_hash": hash_password(temp_pw)
        }).eq("id", user["id"]).execute()
        st.success(f"임시 비밀번호를 {email}로 발송했습니다.")
        return True
    except Exception as e:
        st.error(f"메일 발송 실패: {e}\n비밀번호는 변경되지 않았습니다.")
        return False


# ── 권한 체크 헬퍼 ────────────────────────────────────────────────────────
def require_login():
    if not st.session_state.get("user"):
        st.warning("로그인이 필요합니다.")
        st.switch_page("pages/01_login.py")
        st.stop()


def require_role(*roles: str):
    require_login()
    if st.session_state.user.get("role") not in roles:
        st.error("접근 권한이 없습니다.")
        st.stop()


def is_role(*roles: str) -> bool:
    """현재 유저 권한 확인 (True/False)."""
    return st.session_state.get("user", {}).get("role") in roles