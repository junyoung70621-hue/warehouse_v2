# pages/05_admin.py
import streamlit as st
from utils.auth import require_role, is_role
from utils.db import get_supabase
from utils.routing import CENTERS
from utils.ui import apply_global_css, render_sidebar_header, render_sidebar_section, render_sidebar_user, render_top_bar

st.set_page_config(
    page_title="에이텍모빌리티 자재관리",
    page_icon="favicon_32.png",
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
    st.button("⚙️ 관리자", use_container_width=True, type="primary")

    st.divider()
    if st.button("💬 문의하기", use_container_width=True):
        st.switch_page("pages/12_inquiry.py")
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


def _users_to_df(users_list):
    rows = []
    for u in users_list:
        assigned = u.get("assigned_center","") or u.get("center","")
        rows.append({
            "이름":     u.get("name",""),
            "아이디":   u.get("username",""),
            "이메일":   u.get("email",""),
            "연락처":   u.get("phone","") or "",
            "소속 센터": assigned or "미지정",
            "권한":     ROLE_LABELS.get(u.get("role","guest"), u.get("role","guest")),
            "승인 상태": "✅ 승인" if u.get("is_approved") else "⏳ 미승인",
        })
    return rows


def render_user_list(users_list, tab_key):
    """회원 목록을 상단 관리 패널 + 데이터프레임으로 표시."""
    import pandas as pd

    if not users_list:
        st.info("해당 조건의 회원이 없습니다.")
        return

    # ── 상단 관리 패널 ──────────────────────────────────────────────────────
    name_map  = {u["name"]: u for u in users_list}
    sel_names = [u["name"] for u in users_list if u["id"] != user["id"]]
    if not sel_names:
        st.caption("관리 가능한 회원이 없습니다.")
        return

    mc1, mc2 = st.columns([4, 1])
    with mc1:
        sel_name = st.selectbox(
            "회원 선택", sel_names,
            label_visibility="collapsed",
            key=f"sel_user_{tab_key}"
        )
    with mc2:
        show_panel = st.button("📋 관리", use_container_width=True, key=f"open_panel_{tab_key}")

    if show_panel or st.session_state.get(f"panel_open_{tab_key}"):
        st.session_state[f"panel_open_{tab_key}"] = True
        u = name_map.get(sel_name)
        if not u:
            return

        with st.container(border=True):
            st.markdown(f"**{u['name']}** · {u.get('email','')} · {u.get('assigned_center','') or u.get('center','')}")
            pa1, pa2, pa3 = st.columns([2, 2, 2])

            current_role   = u.get("role","guest")
            current_center = u.get("assigned_center","") or ""
            new_role = pa1.selectbox(
                "권한", ROLE_OPTIONS,
                index=ROLE_OPTIONS.index(current_role) if current_role in ROLE_OPTIONS else 0,
                format_func=lambda x: ROLE_LABELS.get(x, x),
                key=f"pr_{tab_key}_{u['id']}"
            )
            new_center = pa2.selectbox(
                "소속 센터", ["미지정"] + CENTERS,
                index=(["미지정"] + CENTERS).index(current_center) if current_center in CENTERS else 0,
                key=f"pc_{tab_key}_{u['id']}"
            )

            ba1, ba2, ba3, ba4 = st.columns(4)
            if ba1.button("💾 저장", key=f"psave_{tab_key}_{u['id']}", type="primary", use_container_width=True):
                try:
                    sb.table("users").update({
                        "role": new_role,
                        "assigned_center": None if new_center == "미지정" else new_center,
                    }).eq("id", u["id"]).execute()
                    st.success(f"{u['name']} 저장 완료!")
                    st.session_state[f"panel_open_{tab_key}"] = False
                    st.rerun()
                except Exception as e:
                    st.error(f"저장 실패: {e}")

            is_approved = u.get("is_approved", False)
            if is_approved:
                if ba2.button("승인 취소", key=f"punapprove_{tab_key}_{u['id']}", use_container_width=True):
                    sb.table("users").update({"is_approved": False}).eq("id", u["id"]).execute()
                    st.session_state[f"panel_open_{tab_key}"] = False
                    st.rerun()
            else:
                if ba2.button("✅ 승인", key=f"papprove_{tab_key}_{u['id']}", use_container_width=True):
                    sb.table("users").update({"is_approved": True}).eq("id", u["id"]).execute()
                    try:
                        from utils.mail import send_register_approved
                        send_register_approved(u.get("email",""), u["name"],
                                               u.get("assigned_center","") or u.get("center",""))
                    except Exception:
                        pass
                    st.success(f"{u['name']} 승인 완료!")
                    st.session_state[f"panel_open_{tab_key}"] = False
                    st.rerun()

            del_key = f"pdel_{tab_key}_{u['id']}"
            if del_key not in st.session_state:
                st.session_state[del_key] = False
            if not st.session_state[del_key]:
                if ba3.button("🗑️ 삭제", key=f"pdelbtn_{tab_key}_{u['id']}", use_container_width=True):
                    st.session_state[del_key] = True
                    st.rerun()
            else:
                ba3.warning("정말 삭제?")
                if ba3.button("확인 삭제", key=f"pdelok_{tab_key}_{u['id']}", type="primary", use_container_width=True):
                    try:
                        uid = u["id"]
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
                        st.session_state[f"panel_open_{tab_key}"] = False
                        st.success(f"✅ {u['name']} 삭제 완료")
                        st.rerun()
                    except Exception as e:
                        st.error(f"삭제 실패: {e}")

            if ba4.button("✖ 닫기", key=f"pclose_{tab_key}_{u['id']}", use_container_width=True):
                st.session_state[f"panel_open_{tab_key}"] = False
                st.rerun()

    st.divider()
    st.caption(f"총 **{len(users_list)}명**")

    df_rows = _users_to_df(users_list)
    df = pd.DataFrame(df_rows)

    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        height=min(max(len(df) * 35 + 40, 160), 500),
        column_config={
            "이름":     st.column_config.TextColumn("이름",     width=90),
            "아이디":   st.column_config.TextColumn("아이디",   width=100),
            "이메일":   st.column_config.TextColumn("이메일",   width=200),
            "연락처":   st.column_config.TextColumn("연락처",   width=120),
            "소속 센터": st.column_config.TextColumn("소속 센터", width=110),
            "권한":     st.column_config.TextColumn("권한",     width=90),
            "승인 상태": st.column_config.TextColumn("승인 상태", width=80),
        }
    )


tab_search, tab_users, tab_pending = st.tabs(["🔍 회원 검색", "👥 전체 회원 목록", "✅ 가입 승인 대기"])

with tab_search:
    st.subheader("회원 검색")

    # ── 검색 필터 ──────────────────────────────────────────────────────────
    sc1, sc2, sc3, sc4 = st.columns([3, 1.5, 1.5, 1.5])
    with sc1:
        search_q = st.text_input(
            "검색어", placeholder="이름 / 아이디 / 이메일 검색...",
            label_visibility="collapsed"
        )
    with sc2:
        filter_role = st.selectbox(
            "권한", ["전체"] + ROLE_OPTIONS,
            format_func=lambda x: "전체 권한" if x == "전체" else ROLE_LABELS.get(x, x),
            label_visibility="collapsed"
        )
    with sc3:
        filter_center = st.selectbox(
            "센터", ["전체"] + CENTERS,
            format_func=lambda x: "전체 센터" if x == "전체" else x,
            label_visibility="collapsed"
        )
    with sc4:
        filter_status = st.selectbox(
            "상태", ["전체", "승인됨", "미승인"],
            label_visibility="collapsed"
        )

    # ── 데이터 로드 ────────────────────────────────────────────────────────
    try:
        all_res = sb.table("users").select("*").order("created_at", desc=True).execute()
    except Exception:
        all_res = sb.table("users").select("*").execute()
    all_users = all_res.data or []

    # ── 필터 적용 ──────────────────────────────────────────────────────────
    filtered = all_users
    if search_q.strip():
        q = search_q.strip().lower()
        filtered = [
            u for u in filtered
            if q in (u.get("name","") or "").lower()
            or q in (u.get("username","") or "").lower()
            or q in (u.get("email","") or "").lower()
        ]
    if filter_role != "전체":
        filtered = [u for u in filtered if u.get("role") == filter_role]
    if filter_center != "전체":
        filtered = [
            u for u in filtered
            if u.get("assigned_center") == filter_center
            or u.get("center") == filter_center
        ]
    if filter_status == "승인됨":
        filtered = [u for u in filtered if u.get("is_approved")]
    elif filter_status == "미승인":
        filtered = [u for u in filtered if not u.get("is_approved")]

    render_user_list(filtered, "search")

with tab_users:
    st.subheader("전체 회원 목록")
    try:
        res = sb.table("users").select("*").order("created_at", desc=True).execute()
    except Exception:
        res = sb.table("users").select("*").execute()
    users = res.data or []
    render_user_list(users, "all")

with tab_pending:
    st.subheader("승인 대기 중인 회원")
    st.caption("권한과 소속 센터를 지정한 후 승인하세요.")
    try:
        res = sb.table("users").select("*").eq("is_approved",False).order("created_at").execute()
    except Exception:
        res = sb.table("users").select("*").eq("is_approved",False).execute()
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
                        try:
                            from utils.mail import send_register_approved
                            send_register_approved(
                                u.get("email",""),
                                u["name"],
                                None if assign_center=="미지정" else assign_center,
                            )
                        except Exception:
                            pass
                        st.success(f"✅ {u['name']} 승인 완료!")
                        st.rerun()
                with a4:
                    if st.button("❌ 거절", key=f"pd_{u['id']}", use_container_width=True):
                        sb.table("users").delete().eq("id",u["id"]).execute()
                        st.rerun()
