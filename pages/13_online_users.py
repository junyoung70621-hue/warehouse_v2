# pages/13_online_users.py
import streamlit as st
from datetime import datetime, timezone, timedelta
from utils.auth import require_role, is_role
from utils.db import fetch_users_online_status
from utils.ui import apply_global_css, render_sidebar_header, render_sidebar_section, render_sidebar_user, render_top_bar

st.set_page_config(
    page_title="에이텍모빌리티 자재관리",
    page_icon="favicon_32.png",
    layout="wide",
    initial_sidebar_state="expanded",
)

apply_global_css()
require_role("admin")

user = st.session_state.user

_RL_MAP = {"admin":"관리자","materials":"자재파트","manager":"센터장","user":"일반","guest":"게스트"}

def _status(last_seen_str):
    if not last_seen_str:
        return "offline", "오프라인", "#94A3B8"
    try:
        ts = datetime.fromisoformat(last_seen_str.replace("Z", "+00:00"))
        diff = datetime.now(timezone.utc) - ts
        mins = diff.total_seconds() / 60
        if mins <= 5:
            return "online",  "온라인",   "#0284C7"
        elif mins <= 30:
            return "away",    "자리비움", "#f59e0b"
        else:
            return "offline", "오프라인", "#94A3B8"
    except Exception:
        return "offline", "오프라인", "#94A3B8"

def _since(last_seen_str):
    if not last_seen_str:
        return "기록 없음"
    try:
        ts = datetime.fromisoformat(last_seen_str.replace("Z", "+00:00"))
        diff = datetime.now(timezone.utc) - ts
        s = int(diff.total_seconds())
        if s < 60:
            return f"{s}초 전"
        elif s < 3600:
            return f"{s // 60}분 전"
        elif s < 86400:
            return f"{s // 3600}시간 전"
        else:
            return f"{s // 86400}일 전"
    except Exception:
        return "알 수 없음"

# ── 사이드바 ──────────────────────────────────────────────────────────────
with st.sidebar:
    render_sidebar_header()
    if st.button("📊 대시보드(자재)", use_container_width=True):
        st.switch_page("pages/10_dashboard.py")
    if is_role("admin"):
        if st.button("📟 대시보드(단말기)", use_container_width=True):
            st.switch_page("pages/14_terminal_dashboard.py")
    st.divider()

    render_sidebar_section("재고 관리")
    if st.button("📦 재고 현황", use_container_width=True):
        st.switch_page("pages/02_warehouse.py")
    if st.button("🚚 이동 신청 현황", use_container_width=True):
        st.switch_page("pages/03_transfers.py")
    if st.button("📋 입출고 이력", use_container_width=True):
        st.switch_page("pages/04_history.py")
    if st.button("📊 사용내역", use_container_width=True):
        st.switch_page("pages/08_usage_history.py")

    render_sidebar_section("요청")
    if st.button("📦 자재 요청", use_container_width=True, key="sidebar_mat_req"):
        st.switch_page("pages/07_material_requests.py")
    if st.button("🛒 구매 요청", use_container_width=True, key="sidebar_pur_req"):
        st.switch_page("pages/11_purchase_requests.py")

    render_sidebar_section("관리")
    if st.button("📍 위치 지도", use_container_width=True):
        st.switch_page("pages/09_rack_map.py")
    if st.button("⚙️ 관리자", use_container_width=True):
        st.switch_page("pages/05_admin.py")
    st.button("🟢 접속 현황", use_container_width=True, type="primary")

    st.divider()
    if st.button("💬 문의하기", use_container_width=True):
        st.switch_page("pages/12_inquiry.py")
    if st.button("👤 마이페이지", use_container_width=True):
        st.switch_page("pages/06_mypage.py")
    if st.button("🚪 로그아웃", use_container_width=True):
        st.session_state.user = None
        st.switch_page("pages/01_login.py")
    render_sidebar_user(user)

render_top_bar("접속 현황", user)
st.divider()

# ── 헤더 ──────────────────────────────────────────────────────────────────
col_title, col_refresh = st.columns([8, 1])
with col_title:
    now_str = datetime.now().strftime("%H:%M:%S")
    st.caption(f"마지막 갱신: {now_str}  ·  5분 이내 = 온라인 / 30분 이내 = 자리비움 / 그 이상 = 오프라인")
with col_refresh:
    if st.button("새로고침", use_container_width=True):
        st.rerun()

# ── 데이터 ────────────────────────────────────────────────────────────────
users = fetch_users_online_status()

online  = [u for u in users if _status(u.get("last_seen_at"))[0] == "online"]
away    = [u for u in users if _status(u.get("last_seen_at"))[0] == "away"]
offline = [u for u in users if _status(u.get("last_seen_at"))[0] == "offline"]

# ── 요약 카드 ─────────────────────────────────────────────────────────────
c1, c2, c3 = st.columns(3)
with c1:
    st.markdown(
        f"<div style='background:#F8F9FA;border:1px solid rgba(2,132,199,0.2);border-radius:6px;"
        f"padding:14px 18px;border-left:3px solid #0284C7;'>"
        f"<div style='font-size:11px;color:#64748B;letter-spacing:0.1em;'>온라인</div>"
        f"<div style='font-size:28px;font-weight:700;color:#0284C7;margin-top:4px;'>{len(online)}</div>"
        f"</div>", unsafe_allow_html=True)
with c2:
    st.markdown(
        f"<div style='background:#F8F9FA;border:1px solid rgba(217,119,6,0.2);border-radius:6px;"
        f"padding:14px 18px;border-left:3px solid #D97706;'>"
        f"<div style='font-size:11px;color:#64748B;letter-spacing:0.1em;'>자리비움</div>"
        f"<div style='font-size:28px;font-weight:700;color:#D97706;margin-top:4px;'>{len(away)}</div>"
        f"</div>", unsafe_allow_html=True)
with c3:
    st.markdown(
        f"<div style='background:#F8F9FA;border:1px solid rgba(148,163,184,0.3);border-radius:6px;"
        f"padding:14px 18px;border-left:3px solid #94A3B8;'>"
        f"<div style='font-size:11px;color:#64748B;letter-spacing:0.1em;'>오프라인</div>"
        f"<div style='font-size:28px;font-weight:700;color:#94A3B8;margin-top:4px;'>{len(offline)}</div>"
        f"</div>", unsafe_allow_html=True)

st.divider()

# ── 사용자 목록 ───────────────────────────────────────────────────────────
def _render_user_row(u):
    _, color = _status(u.get("last_seen_at"))[1], _status(u.get("last_seen_at"))[2]
    status_label = _status(u.get("last_seen_at"))[1]
    center = u.get("assigned_center") or u.get("center") or "-"
    role_label = _RL_MAP.get(u.get("role",""), u.get("role",""))
    since = _since(u.get("last_seen_at"))
    st.markdown(
        f"<div style='display:flex;align-items:center;gap:12px;padding:8px 12px;"
        f"background:#F8F9FA;border-radius:4px;margin-bottom:4px;"
        f"border-left:3px solid {color};'>"
        f"<div style='width:8px;height:8px;border-radius:50%;background:{color};flex-shrink:0;'></div>"
        f"<div style='flex:1;min-width:0;'>"
        f"<span style='font-size:13px;font-weight:600;color:#1E293B;'>{u.get('name','')}</span>"
        f"&nbsp;<span style='font-size:11px;color:#64748B;'>({role_label} · {center})</span>"
        f"</div>"
        f"<span style='font-size:11px;color:{color};font-weight:600;white-space:nowrap;'>{status_label}</span>"
        f"<span style='font-size:11px;color:#94A3B8;white-space:nowrap;margin-left:8px;'>{since}</span>"
        f"</div>",
        unsafe_allow_html=True,
    )

for group, label in [(online, "온라인"), (away, "자리비움"), (offline, "오프라인")]:
    if group:
        st.markdown(f"**{label} ({len(group)}명)**")
        for u in group:
            _render_user_row(u)
        st.write("")
