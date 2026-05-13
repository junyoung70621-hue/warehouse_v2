# pages/05_admin.py
import streamlit as st
from utils.auth import require_role
from utils.db import get_supabase
from utils.routing import CENTERS
from utils.ui import apply_global_css, render_sidebar_header, render_sidebar_user, render_top_bar

st.set_page_config(
    page_title="에이텍모빌리티 자재관리",
    page_icon="⚙️",
    layout="wide",
    initial_sidebar_state="expanded",
)

apply_global_css()
require_role("admin")

user      = st.session_state.user
user_name = user["name"]
sb        = get_supabase()

with st.sidebar:
    render_sidebar_header()
    if st.button("📊 대시보드", use_container_width=True):
        st.switch_page("pages/10_dashboard.py")
    st.divider()
    if st.button("📦 재고 현황", use_container_width=True):
        st.switch_page("pages/02_warehouse.py")
    if st.button("🚚 이동 신청 현황", use_container_width=True):
        st.switch_page("pages/03_transfers.py")
    if st.button("📋 입출고 이력", use_container_width=True):
        st.switch_page("pages/04_history.py")
    if st.button("📊 사용내역", use_container_width=True):
        st.switch_page("pages/08_usage_history.py")
    if st.button("📦 자재 요청", use_container_width=True):
        st.switch_page("pages/07_material_requests.py")
    if st.button("🛒 구매 요청", use_container_width=True):
        st.switch_page("pages/11_purchase_requests.py")
    st.button("⚙️ 관리자", use_container_width=True, type="primary")
    st.divider()
    if st.button("👤 마이페이지", use_container_width=True):
        st.switch_page("pages/06_mypage.py")
    if st.button("🚪 로그아웃", use_container_width=True):
        st.session_state.user = None
        st.switch_page("pages/01_login.py")
    render_sidebar_user(st.session_state.user)

render_top_bar("관리자", st.session_state.user)
st.markdown("## ⚙️ 관리자 페이지")
st.divider()

ROLE_OPTIONS = ["admin","materials","manager","user","guest"]
ROLE_LABELS  = {
    "admin":"관리자","materials":"자재파트",
    "manager":"센터장/파트장","user":"사용자","guest":"게스트",
}

tab_users, tab_pending = st.tabs(["👥 전체 회원 목록","✅ 가입 승인 대기"])

with tab_users:
    st.subheader("전체 회원 목록")
    res   = sb.table("users").select("*").order("created_at", desc=True).execute()
    users = res.data or []
    if not users:
        st.info("등록된 회원이 없습니다.")
    else:
        for u in users:
            with st.container(border=True):
                c1, c2, c3, c4 = st.columns([2,2,2,2])
                assigned = u.get("assigned_center","") or u.get("center","")
                c1.markdown(f"**{u['name']}**")
                c1.caption(f"ID: {u.get('username','')}  |  소속: {assigned or '미지정'}")
                c2.write(u.get("email",""))
                c2.caption(u.get("phone","") or "")
                current_role   = u.get("role","guest")
                current_center = u.get("assigned_center","") or ""
                if u["id"] == user["id"]:
                    c3.write(f"**{ROLE_LABELS.get(current_role,current_role)}** (본인)")
                    c3.caption(current_center or "소속 없음")
                else:
                    new_role = c3.selectbox(
                        "권한", ROLE_OPTIONS,
                        index=ROLE_OPTIONS.index(current_role),
                        key=f"role_{u['id']}",
                        format_func=lambda x: ROLE_LABELS.get(x,x),
                        label_visibility="collapsed"
                    )
                    new_center = c3.selectbox(
                        "소속 센터", ["미지정"]+CENTERS,
                        index=(["미지정"]+CENTERS).index(current_center)
                        if current_center in CENTERS else 0,
                        key=f"center_{u['id']}",
                        label_visibility="collapsed"
                    )
                    if c3.button("💾 저장", key=f"save_{u['id']}", use_container_width=True):
                        sb.table("users").update({
                            "role": new_role,
                            "assigned_center": None if new_center=="미지정" else new_center,
                        }).eq("id", u["id"]).execute()
                        st.success(f"{u['name']} 변경 완료!")
                        st.rerun()
                is_approved = u.get("is_approved",False)
                c4.write("✅ 승인됨" if is_approved else "⏳ 미승인")
                if u["id"] != user["id"]:
                    if is_approved:
                        if c4.button("승인 취소", key=f"unapprove_{u['id']}", use_container_width=True):
                            sb.table("users").update({"is_approved":False}).eq("id",u["id"]).execute()
                            st.rerun()
                    else:
                        if c4.button("✅ 승인", key=f"approve_user_{u['id']}",
                                     type="primary", use_container_width=True):
                            sb.table("users").update({"is_approved":True}).eq("id",u["id"]).execute()
                            st.success(f"{u['name']} 승인 완료!")
                            st.rerun()
                    # 계정 삭제
                    del_key = f"del_confirm_{u['id']}"
                    if del_key not in st.session_state:
                        st.session_state[del_key] = False
                    if not st.session_state[del_key]:
                        if c4.button("🗑️ 삭제", key=f"del_btn_{u['id']}",
                                     use_container_width=True):
                            st.session_state[del_key] = True
                            st.rerun()
                    else:
                        c4.warning(f"**{u['name']}** 계정을 삭제합니다.")
                        cc1, cc2 = c4.columns(2)
                        if cc1.button("확인", key=f"del_ok_{u['id']}",
                                      type="primary", use_container_width=True):
                            try:
                                uid = u["id"]
                                # FK 참조 해제 (requester_id는 NOT NULL이므로 NULL 대신 행 삭제)
                                sb.table("transfers").delete().eq("requester_id", uid).execute()
                                sb.table("history").update({"actor_id": None}).eq("actor_id", uid).execute()
                                sb.table("warehouse").update({"last_modified_by": None}).eq("last_modified_by", uid).execute()
                                try:
                                    sb.table("material_requests").delete().eq("requester_id", uid).execute()
                                    sb.table("material_requests").update({"processed_by": None}).eq("processed_by", uid).execute()
                                except Exception:
                                    pass
                                sb.table("users").delete().eq("id", uid).execute()
                                st.session_state[del_key] = False
                                st.success(f"✅ {u['name']} 계정이 삭제됐습니다.")
                                st.rerun()
                            except Exception as e:
                                st.error(f"삭제 실패: {e}")
                        if cc2.button("취소", key=f"del_cancel_{u['id']}",
                                      use_container_width=True):
                            st.session_state[del_key] = False
                            st.rerun()

with tab_pending:
    st.subheader("승인 대기 중인 회원")
    st.caption("권한과 소속 센터를 지정한 후 승인하세요.")
    res     = sb.table("users").select("*").eq("is_approved",False).order("created_at").execute()
    pending = res.data or []
    if not pending:
        st.success("승인 대기 중인 회원이 없습니다.")
    else:
        for u in pending:
            with st.container(border=True):
                c1, c2 = st.columns([3,3])
                c1.markdown(f"**{u['name']}**")
                c1.caption(f"ID: {u.get('username','')}  |  신청 센터: {u.get('center','미지정') or '미지정'}")
                c2.write(u.get("email",""))
                c2.caption(u.get("phone","") or "")
                st.divider()
                a1, a2, a3, a4 = st.columns([2,2,1,1])
                with a1:
                    assign_role = st.selectbox(
                        "부여할 권한 *", ROLE_OPTIONS,
                        index=ROLE_OPTIONS.index(u.get("role","guest")),
                        key=f"arole_{u['id']}",
                        format_func=lambda x: ROLE_LABELS.get(x,x)
                    )
                with a2:
                    req_center  = u.get("center","")
                    default_idx = (["미지정"]+CENTERS).index(req_center) if req_center in CENTERS else 0
                    assign_center = st.selectbox(
                        "소속 센터 지정 *", ["미지정"]+CENTERS,
                        index=default_idx, key=f"acenter_{u['id']}"
                    )
                with a3:
                    if st.button("✅ 승인", key=f"pa_{u['id']}",
                                 type="primary", use_container_width=True):
                        sb.table("users").update({
                            "is_approved":True,
                            "role":assign_role,
                            "assigned_center":None if assign_center=="미지정" else assign_center,
                        }).eq("id",u["id"]).execute()
                        st.success(f"✅ {u['name']} 승인 완료!")
                        st.rerun()
                with a4:
                    if st.button("❌ 거절", key=f"pd_{u['id']}", use_container_width=True):
                        sb.table("users").delete().eq("id",u["id"]).execute()
                        st.rerun()
