# pages/16_notices.py — 공지사항
import streamlit as st
from datetime import datetime
from utils.auth import require_login, is_role, logout
from utils.db import (
    fetch_notices, fetch_unread_notice_count,
    mark_notice_read, create_notice, update_notice, delete_notice,
    clear_notice_cache, upload_notice_file,
)
from utils.ui import (
    apply_global_css, render_sidebar_header,
    render_sidebar_section, render_sidebar_user, render_top_bar,
)

st.set_page_config(
    page_title="에이텍모빌리티 자재관리",
    page_icon="favicon_32.png",
    layout="wide",
    initial_sidebar_state="expanded",
)
apply_global_css()
require_login()

user    = st.session_state.user
user_id = user["id"]
role    = user["role"]

# ── 사이드바 ──────────────────────────────────────────────────────────────
with st.sidebar:
    render_sidebar_header()
    if st.button("자재현황(전체)", use_container_width=True):
        st.switch_page("pages/10_dashboard.py")
    if st.button("버스단말기 현황", use_container_width=True):
        st.switch_page("pages/14_terminal_dashboard.py")
    st.divider()

    from utils.permissions import get_viewable_centers
    viewable = get_viewable_centers(user)
    if st.session_state.get("sidebar_center") not in viewable:
        st.session_state.pop("sidebar_center", None)
    st.selectbox("센터", viewable, label_visibility="collapsed", key="sidebar_center")

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
    st.button("📢 공지사항", use_container_width=True, type="primary")
    if st.button("💬 문의하기", use_container_width=True):
        st.switch_page("pages/12_inquiry.py")
    if st.button("👤 마이페이지", use_container_width=True):
        st.switch_page("pages/06_mypage.py")
    if st.button("🚪 로그아웃", use_container_width=True):
        logout()
    render_sidebar_user(user)

render_top_bar("공지사항", user)

# ── 세션 초기화 ───────────────────────────────────────────────────────────
if "notice_edit_id" not in st.session_state:
    st.session_state.notice_edit_id = None
if "notice_edit_attachments" not in st.session_state:
    st.session_state.notice_edit_attachments = []
if "notice_attach_for" not in st.session_state:
    st.session_state.notice_attach_for = None

# ── 관리자 작성 폼 ────────────────────────────────────────────────────────
if is_role("admin"):
    with st.expander("✏️ 공지 작성 / 수정", expanded=bool(st.session_state.notice_edit_id)):
        editing = st.session_state.notice_edit_id
        if editing:
            notices_all = fetch_notices(active_only=False)
            target = next((n for n in notices_all if n["id"] == editing), None)
        else:
            target = None

        # 첨부파일 목록 초기화 (편집 대상 변경 시)
        if editing != st.session_state.get("notice_attach_for"):
            st.session_state.notice_edit_attachments = (target.get("attachments") or []) if target else []
            st.session_state.notice_attach_for = editing

        col1, col2 = st.columns([4, 1])
        with col1:
            title_val = target["title"] if target else ""
            new_title = st.text_input("제목", value=title_val, key="notice_title_input")
        with col2:
            active_val = target["is_active"] if target else True
            new_active = st.checkbox("활성", value=active_val, key="notice_active_input")

        content_val = target["content"] if target else ""
        new_content = st.text_area("내용", value=content_val, height=120, key="notice_content_input")

        # 기존 첨부파일 (편집 모드)
        if editing and st.session_state.notice_edit_attachments:
            st.caption("기존 첨부파일")
            _to_remove = None
            for _i, _att in enumerate(st.session_state.notice_edit_attachments):
                _c1, _c2 = st.columns([9, 1])
                _c1.markdown(f"📎 {_att['name']}")
                if _c2.button("❌", key=f"notice_rm_att_{_i}", use_container_width=True):
                    _to_remove = _i
            if _to_remove is not None:
                st.session_state.notice_edit_attachments = [
                    a for j, a in enumerate(st.session_state.notice_edit_attachments) if j != _to_remove
                ]
                st.rerun()

        new_files = st.file_uploader("📎 첨부파일 추가", accept_multiple_files=True, key="notice_file_uploader")

        ba, bb = st.columns(2)
        if ba.button("💾 저장", type="primary", use_container_width=True, key="notice_save"):
            if not new_title.strip():
                st.warning("제목을 입력해 주세요.")
            else:
                _final_atts = list(st.session_state.get("notice_edit_attachments", []))
                if editing:
                    for _f in (new_files or []):
                        _url = upload_notice_file(editing, _f.name, _f.read())
                        if _url:
                            _final_atts.append({"name": _f.name, "url": _url})
                    if update_notice(editing, new_title.strip(), new_content.strip(), new_active, _final_atts):
                        st.session_state.notice_edit_id = None
                        st.session_state.notice_edit_attachments = []
                        st.session_state.notice_attach_for = None
                        st.success("수정됐습니다.")
                        st.rerun()
                else:
                    _nid = create_notice(new_title.strip(), new_content.strip(), user_id)
                    if _nid:
                        for _f in (new_files or []):
                            _url = upload_notice_file(_nid, _f.name, _f.read())
                            if _url:
                                _final_atts.append({"name": _f.name, "url": _url})
                        if _final_atts:
                            update_notice(_nid, new_title.strip(), new_content.strip(), True, _final_atts)
                        st.success("공지가 등록됐습니다.")
                        st.rerun()
        if bb.button("취소", use_container_width=True, key="notice_cancel"):
            st.session_state.notice_edit_id = None
            st.session_state.notice_edit_attachments = []
            st.session_state.notice_attach_for = None
            st.rerun()

st.divider()

# ── 공지 목록 ─────────────────────────────────────────────────────────────
notices = fetch_notices(active_only=not is_role("admin"))

if not notices:
    st.info("등록된 공지사항이 없습니다.")
    st.stop()

# 읽음 상태 일괄 조회
from utils.db import get_supabase
_read_rows = get_supabase().table("notice_reads").select("notice_id").eq("user_id", user_id).execute().data or []
_read_ids  = {r["notice_id"] for r in _read_rows}

for n in notices:
    nid       = n["id"]
    is_read   = nid in _read_ids
    is_active = n.get("is_active", True)
    author    = (n.get("users") or {}).get("name", "관리자") if isinstance(n.get("users"), dict) else "관리자"
    created   = (n.get("created_at") or "")[:16].replace("T", " ")

    # 제목 행
    status_dot = "" if is_read else "🔴 "
    inactive_tag = " [비활성]" if not is_active else ""
    header_label = f"{status_dot}{n['title']}{inactive_tag}  —  {author}  |  {created}"

    with st.expander(header_label, expanded=False):
        st.markdown(
            f"<div style='background:#F8F9FA;padding:14px 16px;border-radius:4px;"
            f"border-left:3px solid #D3004F;font-size:13px;white-space:pre-wrap;'>"
            f"{n['content'] or ''}</div>",
            unsafe_allow_html=True,
        )

        # 첨부파일 다운로드
        _atts = n.get("attachments") or []
        if _atts:
            st.markdown("**📎 첨부파일**")
            for _att in _atts:
                st.markdown(f"[📥 {_att['name']}]({_att['url']})")

        # 읽음 처리
        if not is_read:
            mark_notice_read(nid, user_id)
            _read_ids.add(nid)

        # 관리자 액션
        if is_role("admin"):
            ca, cb = st.columns(2)
            if ca.button("✏️ 수정", key=f"notice_edit_{nid}", use_container_width=True):
                st.session_state.notice_edit_id = nid
                st.rerun()
            if cb.button("🗑️ 삭제", key=f"notice_del_{nid}", use_container_width=True):
                if delete_notice(nid):
                    st.success("삭제됐습니다.")
                    st.rerun()

# 읽음 처리 후 카운트 캐시 초기화
fetch_unread_notice_count.clear()
