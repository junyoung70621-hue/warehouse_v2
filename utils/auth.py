# utils/auth.py
import bcrypt
import secrets
import string
import hmac
import hashlib
import streamlit as st
from datetime import datetime
from utils.db import get_supabase

SESSION_TIMEOUT = 1800  # 30분 (초)


def _make_session_token(user_id: str, password_hash: str) -> str:
    """비밀번호 해시를 키로 한 HMAC-SHA256 토큰. 비밀번호 변경 시 자동 무효화."""
    return hmac.new(
        password_hash.encode(),
        user_id.encode(),
        hashlib.sha256
    ).hexdigest()


def try_restore_session() -> bool:
    """query_params의 토큰으로 세션 복구 (새로고침 대응). 복구 성공 시 True 반환."""
    if st.session_state.get("user"):
        return True
    uid = st.query_params.get("uid")
    t   = st.query_params.get("t")
    if not uid or not t:
        return False
    try:
        sb  = get_supabase()
        res = sb.table("users").select("*").eq("id", uid).eq("is_approved", True).execute()
        if res.data:
            user     = res.data[0]
            expected = _make_session_token(user["id"], user["password_hash"])
            if hmac.compare_digest(t, expected):
                st.session_state.user          = user
                st.session_state.last_activity = datetime.now()
                return True
    except Exception:
        pass
    return False


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
        try:
            from utils.mail import send_register_complete, send_register_notify_admin
            send_register_complete(email, name, center)
            admin_emails = [
                u["email"]
                for u in (sb.table("users").select("email, assigned_center")
                            .eq("role", "admin").eq("is_approved", True).execute().data or [])
                if u.get("email") and u.get("assigned_center") != "고객지원사업부"
            ]
            if admin_emails:
                send_register_notify_admin(admin_emails, name, username, email, center)
        except Exception:
            pass
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
    try:
        if not st.session_state.get("user"):
            if not try_restore_session():
                st.switch_page("pages/01_login.py")
                st.stop()

        user = st.session_state.get("user")
        now  = datetime.now()
        last = st.session_state.get("last_activity")
        # 유휴 타임아웃 체크
        if last and (now - last).total_seconds() > SESSION_TIMEOUT:
            saved_id = st.session_state.get("saved_id")
            st.session_state.clear()
            try:
                st.query_params.clear()
            except Exception:
                pass
            if saved_id:
                st.session_state["saved_id"] = saved_id
            st.warning("세션이 만료되었습니다. 다시 로그인해 주세요.")
            st.switch_page("pages/01_login.py")
            st.stop()
        st.session_state.last_activity = now
        # 새로고침 대응용 query_params 유지
        if "t" not in st.query_params and user:
            token = _make_session_token(user["id"], user["password_hash"])
            st.query_params["uid"] = user["id"]
            st.query_params["t"]   = token
        try:
            from utils.db import update_last_seen
            update_last_seen(st.session_state.user["id"])
        except Exception:
            pass
    except Exception:
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


def logout():
    """세션 전체 정리 후 로그인 페이지로 이동. 아이디 저장값은 유지."""
    saved_id = st.session_state.get("saved_id")
    st.session_state.clear()
    try:
        st.query_params.clear()
    except Exception:
        pass
    if saved_id:
        st.session_state["saved_id"] = saved_id
    st.switch_page("pages/01_login.py")