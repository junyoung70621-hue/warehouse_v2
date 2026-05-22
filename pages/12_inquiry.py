# pages/12_inquiry.py
import streamlit as st
from datetime import datetime
from utils.auth import require_login, is_role, logout
from utils.db import (
    fetch_inquiries, submit_inquiry, answer_inquiry,
    clear_inquiry_cache, get_supabase,
)
from utils.mail import send_inquiry_to_admin, send_inquiry_reply
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
user_id   = user["id"]
user_role = user["role"]
user_name = user.get("name", "")
user_email= user.get("email", "")
user_center = user.get("assigned_center") or user.get("center", "")


# ── 관리자 이메일 목록 조회 ────────────────────────────────────────────────
@st.cache_data(ttl=300)
def _get_admin_emails():
    rows = get_supabase().table("users").select("email, assigned_center").eq("role", "admin").eq("is_approved", True).execute().data or []
    return [r["email"] for r in rows if r.get("email") and r.get("assigned_center") != "고객지원사업부"]


# ── 답변 다이얼로그 ────────────────────────────────────────────────────────
@st.experimental_dialog("문의 답변", width="large")
def reply_dialog(inq: dict):
    st.markdown(f"**제목:** {inq['title']}")
    st.markdown(f"**작성자:** {inq['requester_name']} ({inq['from_center']})")
    st.caption(f"접수일: {inq['created_at'][:16].replace('T', ' ')}")
    st.markdown("---")
    st.markdown("**문의 내용**")
    st.markdown(
        f"<div style='background:#F8F9FA;padding:12px 16px;border-radius:4px;"
        f"border-left:3px solid #D3004F;font-size:13px;white-space:pre-wrap;'>"
        f"{inq['content']}</div>",
        unsafe_allow_html=True,
    )
    st.markdown("---")
    existing = inq.get("reply") or ""
    reply = st.text_area("답변 내용", value=existing, height=150, key=f"reply_{inq['id']}")
    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("답변 등록", type="primary", use_container_width=True, key=f"submit_reply_{inq['id']}"):
            if not reply.strip():
                st.warning("답변 내용을 입력해 주세요.")
            elif answer_inquiry(inq["id"], reply.strip(), user_name):
                if inq.get("requester_email"):
                    send_inquiry_reply(
                        inq["requester_email"],
                        inq.get("requester_name", ""),
                        inq["title"],
                        inq["content"],
                        reply.strip(),
                        user_name,
                    )
                st.success("답변이 등록되었습니다. 창을 닫으면 목록이 갱신됩니다.")
    with col2:
        if st.button("닫기", use_container_width=True, key=f"close_reply_{inq['id']}"):
            st.rerun()


# ── 사이드바 ──────────────────────────────────────────────────────────────
with st.sidebar:
    render_sidebar_header()
    if st.button("자재현황(전체)", use_container_width=True):
        st.switch_page("pages/10_dashboard.py")
    if st.button("버스단말기 현황", use_container_width=True):
        st.switch_page("pages/14_terminal_dashboard.py")
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

    render_sidebar_section("개인")
    if st.button("📢 공지사항", use_container_width=True):
        st.switch_page("pages/16_notices.py")
    st.button("💬 문의하기", use_container_width=True, type="primary")
    if st.button("👤 마이페이지", use_container_width=True):
        st.switch_page("pages/06_mypage.py")
    if st.button("🚪 로그아웃", use_container_width=True):
        logout()
    render_sidebar_user(user)


render_top_bar("문의하기", user)
st.divider()


# ══════════════════════════════════════════════════════════════════════════
# 관리자 뷰
# ══════════════════════════════════════════════════════════════════════════
if is_role("admin"):
    st.markdown("### 전체 문의 목록")
    all_inqs = fetch_inquiries()

    tab_pending, tab_all = st.tabs([f"미답변 ({sum(1 for i in all_inqs if i['status']=='pending')})", f"전체 ({len(all_inqs)})"])

    def _render_inquiry_list(inqs, tab_key):
        if not inqs:
            st.info("문의 내역이 없습니다.")
            return
        for inq in inqs:
            status_label = "⏳ 미답변" if inq["status"] == "pending" else "✅ 답변완료"
            status_color = "#D3004F" if inq["status"] == "pending" else "#0284C7"
            with st.expander(
                f"{status_label}  |  {inq['title']}  —  {inq['requester_name']} ({inq['from_center']})  |  {inq['created_at'][:10]}",
                expanded=False,
            ):
                col_info, col_btn = st.columns([6, 1])
                with col_info:
                    st.markdown(
                        f"<span style='font-size:11px;color:{status_color};font-weight:700;'>{status_label}</span>"
                        f"&nbsp;&nbsp;<span style='font-size:11px;color:#64748B;'>{inq['created_at'][:16].replace('T',' ')}</span>",
                        unsafe_allow_html=True,
                    )
                    st.markdown("**문의 내용**")
                    st.markdown(
                        f"<div style='background:#F8F9FA;padding:12px 16px;border-radius:4px;"
                        f"border-left:3px solid #D3004F;font-size:13px;white-space:pre-wrap;'>"
                        f"{inq['content']}</div>",
                        unsafe_allow_html=True,
                    )
                    if inq.get("reply"):
                        st.markdown("**답변**")
                        st.markdown(
                            f"<div style='background:#F8F9FA;padding:12px 16px;border-radius:4px;"
                            f"border-left:3px solid #0284C7;font-size:13px;white-space:pre-wrap;'>"
                            f"{inq['reply']}</div>",
                            unsafe_allow_html=True,
                        )
                        st.caption(f"답변자: {inq.get('answered_by_name','')}  |  {(inq.get('answered_at') or '')[:16].replace('T',' ')}")
                with col_btn:
                    if st.button("답변", key=f"reply_btn_{tab_key}_{inq['id']}", use_container_width=True):
                        reply_dialog(inq)

    with tab_pending:
        _render_inquiry_list([i for i in all_inqs if i["status"] == "pending"], "pending")
    with tab_all:
        _render_inquiry_list(all_inqs, "all")


# ══════════════════════════════════════════════════════════════════════════
# 일반 사용자 뷰
# ══════════════════════════════════════════════════════════════════════════
else:
    col_form, col_list = st.columns([1, 1], gap="large")

    with col_form:
        st.markdown("### 문의 작성")
        title   = st.text_input("제목", placeholder="문의 제목을 입력해주세요.", key="inq_title")
        content = st.text_area("내용", placeholder="문의 내용을 상세히 입력해주세요.", height=180, key="inq_content")

        if st.button("제출", type="primary", use_container_width=True, key="inq_submit"):
            if not title.strip():
                st.warning("제목을 입력해 주세요.")
            elif not content.strip():
                st.warning("내용을 입력해 주세요.")
            else:
                if submit_inquiry(user_id, user_name, user_email, user_center, title.strip(), content.strip()):
                    try:
                        admin_emails = _get_admin_emails()
                        send_inquiry_to_admin(admin_emails, user_name, user_center, title.strip(), content.strip())
                    except Exception:
                        pass
                    st.success("문의가 접수되었습니다. 관리자 확인 후 답변드립니다.")
                    st.rerun()

    with col_list:
        st.markdown("### 내 문의 내역")
        my_inqs = fetch_inquiries(requester_id=user_id)
        if not my_inqs:
            st.info("접수된 문의가 없습니다.")
        else:
            for inq in my_inqs:
                status_label = "⏳ 미답변" if inq["status"] == "pending" else "✅ 답변완료"
                status_color = "#D3004F" if inq["status"] == "pending" else "#0284C7"
                with st.expander(f"{status_label}  |  {inq['title']}  |  {inq['created_at'][:10]}", expanded=False):
                    st.markdown(
                        f"<span style='font-size:11px;color:{status_color};font-weight:700;'>{status_label}</span>"
                        f"&nbsp;&nbsp;<span style='font-size:11px;color:#64748B;'>{inq['created_at'][:16].replace('T',' ')}</span>",
                        unsafe_allow_html=True,
                    )
                    st.markdown("**문의 내용**")
                    st.markdown(
                        f"<div style='background:#F8F9FA;padding:12px 16px;border-radius:4px;"
                        f"border-left:3px solid #D3004F;font-size:13px;white-space:pre-wrap;'>"
                        f"{inq['content']}</div>",
                        unsafe_allow_html=True,
                    )
                    if inq.get("reply"):
                        st.markdown("**답변**")
                        st.markdown(
                            f"<div style='background:#F8F9FA;padding:12px 16px;border-radius:4px;"
                            f"border-left:3px solid #0284C7;font-size:13px;white-space:pre-wrap;'>"
                            f"{inq['reply']}</div>",
                            unsafe_allow_html=True,
                        )
                        st.caption(f"답변자: {inq.get('answered_by_name','')}  |  {(inq.get('answered_at') or '')[:16].replace('T',' ')}")

