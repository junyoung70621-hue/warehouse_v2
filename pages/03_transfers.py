# pages/03_transfers.py
import streamlit as st
from utils.auth import require_login, is_role, logout
from utils.db import (
    fetch_transfers, approve_transfer,
    clear_transfer_cache, clear_warehouse_cache, get_supabase
)
from utils.permissions import can_approve_transfer, filter_transfers_for_user, get_viewable_centers
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
user_name = user["name"]

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
    selected_center = st.selectbox("센터", viewable, label_visibility="collapsed", key="sidebar_center")

    render_sidebar_section("재고 관리")
    if st.button("📦 재고 현황", use_container_width=True):
        st.switch_page("pages/02_warehouse.py")
    st.button("🚚 이동 신청 현황", use_container_width=True, type="primary")
    if st.button("📋 입출고 이력", use_container_width=True):
        st.switch_page("pages/04_history.py")
    if not is_role("guest"):
        if st.button("📊 사용내역", use_container_width=True):
            st.switch_page("pages/08_usage_history.py")

    if not is_role("guest"):
        render_sidebar_section("요청")
        if st.button("📦 자재 요청", use_container_width=True, key="sidebar_mat_req"):
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
    if st.button("👤 마이페이지", use_container_width=True):
        st.switch_page("pages/06_mypage.py")
    if st.button("🚪 로그아웃", use_container_width=True):
        logout()
    render_sidebar_user(user)

render_top_bar("이동 신청 현황", user)

# ── 타센터→자재센터 승인 다이얼로그 ─────────────────────────────────────────
_st_dialog = getattr(st, "dialog", getattr(st, "experimental_dialog", None))

if _st_dialog:
    @_st_dialog("자재센터 입고 위치 지정", width="large")
    def approve_to_hub_dialog(transfer_id: int, item_name: str, from_center: str, qty: int):
        _user = st.session_state.user
        sb_tmp = get_supabase()

        st.markdown(
            f"**{item_name}** &nbsp; {from_center} → 자재센터 &nbsp; **{qty}개**"
        )
        st.caption("자재센터에서 보관할 위치(렉/단수/박스)를 지정하세요.")
        st.divider()

        existing = sb_tmp.table("warehouse").select(
            "rack_no, shelf, box_no, quantity"
        ).eq("item_name", item_name).eq("location", "자재센터").execute().data

        rack_no = shelf = box_no = ""
        show_new_inputs = True

        if existing:
            mode = st.radio(
                "입고 위치",
                ["기존 위치에 추가", "새 위치 지정"],
                horizontal=True,
                key=f"hub_mode_{transfer_id}",
            )
            if mode == "기존 위치에 추가":
                opts = {}
                for r in existing:
                    lbl = (f"렉 {r.get('rack_no','?')}  "
                           f"{r.get('shelf','?')}단  "
                           f"박스 {r.get('box_no','?')}  "
                           f"(현재: {r['quantity']}개)")
                    opts[lbl] = r
                chosen = st.selectbox(
                    "위치 선택", list(opts.keys()), key=f"hub_sel_{transfer_id}"
                )
                picked = opts[chosen]
                rack_no = str(picked.get("rack_no") or "")
                shelf   = str(picked.get("shelf")   or "")
                box_no  = str(picked.get("box_no")  or "")
                show_new_inputs = False
        else:
            st.info("자재센터에 해당 자재가 없습니다. 새 위치를 지정하면 신규 등록됩니다.")

        if show_new_inputs:
            c1, c2, c3 = st.columns(3)
            rack_no = c1.text_input("렉 번호", key=f"hub_rack_{transfer_id}")
            shelf   = c2.text_input("단수",    key=f"hub_shelf_{transfer_id}")
            box_no  = c3.text_input("박스 번호", key=f"hub_box_{transfer_id}")

        st.divider()
        ca, cb = st.columns(2)
        if ca.button("✅ 승인", type="primary", use_container_width=True,
                     key=f"hub_confirm_{transfer_id}"):
            if approve_transfer(transfer_id, _user,
                                rack_no=rack_no, shelf=shelf, box_no=box_no):
                clear_warehouse_cache()
                st.success("승인 완료!")
                st.rerun()
        if cb.button("취소", use_container_width=True, key=f"hub_cancel_{transfer_id}"):
            st.rerun()

st.markdown("## 🚚 센터 간 이동 신청 현황")
st.divider()

if user_role == "manager":
    center = user.get("assigned_center") or user.get("center","")
    st.info(f"📌 **{center}** 관련 이동 내역만 표시됩니다. "
            f"**{center}으로 들어오는** 이동 건만 승인할 수 있습니다.")
elif user_role == "materials":
    st.info("📌 **자재센터** 관련 이동 내역이 표시됩니다.")
elif user_role == "user":
    st.info("📌 본인이 신청한 이동 내역만 표시됩니다.")

tab_pending, tab_approved, tab_rejected, tab_all = st.tabs([
    "⏳ 대기중", "✅ 승인됨", "❌ 거절됨", "📋 전체"
])

def render_transfers(status_filter=None):
    all_data = fetch_transfers(status_filter)
    data     = filter_transfers_for_user(user, all_data)
    if not data:
        st.info("해당 신청 내역이 없습니다.")
        return
    for tr in data:
        item_info = tr.get("warehouse", {})
        item_name = item_info.get("item_name", "알 수 없음") if isinstance(item_info, dict) else str(item_info)
        user_info = tr.get("users", {})
        requester_name = user_info.get("name", "알 수 없음") if isinstance(user_info, dict) else str(user_info)
        status = tr.get("status","")
        status_label = {
            "pending":"⏳ 대기중","approved":"✅ 승인됨",
            "rejected":"❌ 거절됨","cancelled":"🚫 취소됨"
        }.get(status, status)
        i_can_approve = can_approve_transfer(user, tr.get("from_center",""), tr.get("to_center",""))

        with st.container(border=True):
            c1, c2, c3, c4, c5 = st.columns([3, 2, 2, 1.5, 2])
            c1.markdown(f"**{item_name}**")
            c1.caption(f"신청자: {requester_name}")
            c2.write(f"📤 {tr.get('from_center','')}")
            c2.write(f"📥 {tr.get('to_center','')}")
            c3.metric("수량", tr.get("quantity",0))
            c4.write(status_label)
            with c5:
                if status == "pending" and i_can_approve:
                    if st.button("✅ 승인", key=f"approve_{status_filter}_{tr['id']}",
                                 type="primary", use_container_width=True):
                        if tr.get("to_center") == "자재센터" and _st_dialog:
                            # 타센터→자재센터: rack/shelf/box 위치 지정 팝업
                            _iname = item_info.get("item_name","") if isinstance(item_info, dict) else ""
                            approve_to_hub_dialog(
                                tr["id"], _iname,
                                tr.get("from_center",""), tr.get("quantity",0)
                            )
                        else:
                            # 자재센터→타 또는 타→타: 바로 승인
                            if approve_transfer(tr["id"], user):
                                st.success("✅ 승인 완료!")
                                clear_transfer_cache()
                                st.rerun()
                    if st.button("❌ 거절", key=f"reject_{status_filter}_{tr['id']}",
                                 use_container_width=True):
                        if not can_approve_transfer(user, tr.get("from_center",""), tr.get("to_center","")):
                            st.error("거절 권한이 없습니다.")
                        else:
                            sb = get_supabase()
                            sb.table("transfers").update({
                                "status":"rejected","processed_at":"now()"
                            }).eq("id", tr["id"]).execute()
                            clear_transfer_cache()
                            st.rerun()
                elif status == "pending" and tr.get("requester_id") == user_id:
                    if st.button("🚫 취소", key=f"cancel_{status_filter}_{tr['id']}",
                                 use_container_width=True):
                        sb = get_supabase()
                        sb.table("transfers").update({
                            "status":"cancelled","processed_at":"now()"
                        }).eq("id", tr["id"]).execute()
                        clear_transfer_cache()
                        st.rerun()
                elif status == "pending" and not i_can_approve:
                    st.caption("🔒 승인 권한 없음")
            req_at = tr.get("requested_at","")
            if req_at: st.caption(f"신청일: {req_at[:16].replace('T',' ')}")
            proc_at = tr.get("processed_at")
            if proc_at: st.caption(f"처리일: {proc_at[:16].replace('T',' ')}")

with tab_pending:  render_transfers("pending")
with tab_approved: render_transfers("approved")
with tab_rejected: render_transfers("rejected")
with tab_all:      render_transfers(None)
