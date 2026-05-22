# pages/07_material_requests.py
import streamlit as st
import pandas as pd
from utils.auth import require_login, is_role, logout
from utils.db import (
    fetch_material_requests,
    update_material_request_status,
    approve_material_request_with_stock,
    save_reply_message,
    clear_material_request_cache,
    get_supabase,
)
from utils.mail import (
    send_material_request_reply,
    send_material_request_approved_to_center,
    send_material_request_cancelled,
)
from utils.permissions import get_center as _get_center, get_viewable_centers
from utils.ui import apply_global_css, render_sidebar_header, render_sidebar_section, render_sidebar_user, render_top_bar

st.set_page_config(
    page_title="에이텍모빌리티 자재관리",
    page_icon="favicon_32.png",
    layout="wide",
    initial_sidebar_state="expanded",
)

apply_global_css()
require_login()

@st.experimental_dialog("✅ 처리 완료")
def _done_popup(msg: str):
    st.markdown(msg)
    st.write("")
    if st.button("확인", use_container_width=True, type="primary", key="mr_done_ok"):
        st.session_state.pop("_done_popup_msg", None)
        st.rerun()

user      = st.session_state.user
user_id   = user["id"]
user_name = user["name"]
user_role = user["role"]
IS_MANAGER = user_role in ("admin", "materials")   # 관리 권한
user_center = _get_center(user)

STATUS_KO = {
    "pending":   "⏳ 대기중",
    "approved":  "✅ 승인",
    "rejected":  "❌ 거절",
    "on_hold":   "⏸️ 보류",
    "cancelled": "🚫 취소됨",
}
STATUS_COLOR = {
    "pending":   "#f57c00",
    "approved":  "#2e7d32",
    "rejected":  "#c62828",
    "on_hold":   "#1565c0",
    "cancelled": "#757575",
}

def _get_center_emails(sb, center: str) -> list:
    r1 = sb.table("users").select("email").eq("assigned_center", center).eq("is_approved", True).execute()
    r2 = sb.table("users").select("email").eq("center", center).eq("is_approved", True).execute()
    return list({u["email"] for res in [r1, r2] for u in (res.data or []) if u.get("email")})

# ── 관리자용 액션 다이얼로그 ──────────────────────────────────────────────
_st_dialog = getattr(st, "dialog", getattr(st, "experimental_dialog", None))

if _st_dialog:
    @_st_dialog("📋 자재 요청 처리", width="large")
    def action_dialog(req_id, req_email, req_name, from_center, action, items, tab_key, notes=""):
        _user  = st.session_state.user
        _uid   = _user["id"]
        _uname = _user["name"]

        action_label = STATUS_KO.get(action, action)
        color        = STATUS_COLOR.get(action, "#555")

        st.markdown(
            f"<span style='font-size:18px;font-weight:700;color:{color};'>{action_label} 처리</span>",
            unsafe_allow_html=True
        )
        st.markdown(
            f"**신청자:** {req_name} "
            f"<span style='font-size:12px;color:#666;'>({req_email})</span>  "
            f"· **센터:** {from_center}",
            unsafe_allow_html=True
        )
        if items:
            item_rows = [{"자재명": it.get("item_name",""),
                          "현재재고": it.get("current_qty",0),
                          "요청수량": it.get("requested_qty",0),
                          "재고상태": "⚠️ 재고부족" if it.get("current_qty",0) < it.get("requested_qty",0) else "✅ 충분"}
                         for it in items]
            st.dataframe(pd.DataFrame(item_rows), use_container_width=True, hide_index=True)
        if notes and notes.strip():
            st.info(f"📝 비고: {notes.strip()}")

        row_selections = {}
        if action == "approved" and items:
            st.divider()
            st.markdown("**차감 위치 선택** (자재센터 렉/단수/박스)")

            # 자재센터 재고를 한 번에 일괄 조회
            item_names = [it.get("item_name", "") for it in items if it.get("item_name")]
            hub_all = get_supabase().table("warehouse").select(
                "id, rack_no, shelf, box_no, quantity, item_name"
            ).in_("item_name", item_names).eq("location", "자재센터") \
             .order("quantity", desc=True).execute().data if item_names else []
            hub_map: dict[str, list] = {}
            for _r in hub_all:
                hub_map.setdefault(_r["item_name"], []).append(_r)

            for it in items:
                iname = it.get("item_name", "")
                req_q = int(it.get("requested_qty", 0))
                hub_rows = hub_map.get(iname, [])

                if not hub_rows:
                    st.warning(f"⚠️ {iname}: 자재센터에 재고 없음")
                    continue

                if len(hub_rows) == 1:
                    row_selections[iname] = hub_rows[0]["id"]
                    r = hub_rows[0]
                    avail = int(r["quantity"])
                    status_icon = "✅" if avail >= req_q else "⚠️"
                    st.caption(
                        f"{status_icon} {iname}  —  "
                        f"렉 {r.get('rack_no','')} "
                        f"{r.get('shelf','')}단 "
                        f"박스 {r.get('box_no','')}  "
                        f"(재고: {avail}개)"
                    )
                else:
                    safe_key = f"row_sel_{req_id}_{abs(hash(iname)) % 100000}"
                    opts = {}
                    for r in hub_rows:
                        avail = int(r["quantity"])
                        row_lbl = (f"렉 {r.get('rack_no','?')}  "
                                   f"{r.get('shelf','?')}단  "
                                   f"박스 {r.get('box_no','?')}  "
                                   f"(재고: {avail}개)"
                                   + ("  ⚠️ 부족" if avail < req_q else ""))
                        opts[row_lbl] = r["id"]
                    chosen = st.selectbox(iname, list(opts.keys()), key=safe_key)
                    row_selections[iname] = opts[chosen]

        st.divider()
        reply_msg = st.text_area("신청자에게 보낼 메일 메시지", height=100,
                                  label_visibility="collapsed",
                                  placeholder="추가 안내사항을 입력하세요. 비워두면 처리 결과만 전달됩니다.")
        c1, c2 = st.columns(2)
        confirm_label = {
            "approved": "✅ 승인 + 발송",
            "rejected": "❌ 거절 + 발송",
            "on_hold":  "⏸️ 보류 + 발송",
        }.get(action, "확인")

        if c1.button(confirm_label, type="primary", use_container_width=True,
                     key=f"dlg_ok_{req_id}_{action}"):
            sb = get_supabase()
            if action == "approved":
                ok, ok_items, fail_items = approve_material_request_with_stock(
                    req_id, _user, row_selections
                )
                if not ok:
                    st.error("재고 반영 중 오류가 발생했습니다.")
                    return
                if req_email:
                    try:
                        send_material_request_reply(req_email, req_name, from_center, action, items, reply_msg)
                    except Exception: pass
                center_emails = _get_center_emails(sb, from_center)
                if center_emails:
                    try:
                        send_material_request_approved_to_center(center_emails, from_center, items, _uname)
                    except Exception: pass
                result_msg = f"✅ 승인 완료 — {len(ok_items)}개 재고 반영"
                if fail_items:
                    result_msg += f"  /  ⚠️ {len(fail_items)}개 실패: {', '.join(fail_items[:3])}"
            else:
                update_material_request_status(req_id, action, _uid)
                if req_email:
                    try:
                        send_material_request_reply(req_email, req_name, from_center, action, items, reply_msg)
                    except Exception: pass
                result_msg = f"{action_label} 처리 완료"
            if reply_msg.strip():
                save_reply_message(req_id, reply_msg.strip())
            st.session_state["_mat_dlg_result"] = result_msg
            st.session_state.pop("_mat_dlg_args", None)
            st.rerun()

        if c2.button("취소", use_container_width=True, key=f"dlg_cancel_{req_id}"):
            st.session_state.pop("_mat_dlg_args", None)
            st.rerun()

# ── 사이드바 ──────────────────────────────────────────────────────────────
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
        st.switch_page("pages/02_warehouse.py")
    if st.button("🚚 이동 신청 현황", use_container_width=True):
        st.switch_page("pages/03_transfers.py")
    if st.button("🗂️ 통합 뷰", use_container_width=True):
        st.switch_page("pages/15_combined.py")
    if st.button("📋 입출고 이력", use_container_width=True):
        st.switch_page("pages/04_history.py")
    if not is_role("guest"):
        if st.button("📊 사용내역", use_container_width=True):
            st.switch_page("pages/08_usage_history.py")

    if not is_role("guest"):
        render_sidebar_section("요청")
        st.button("📦 자재요청현황", use_container_width=True, type="primary")
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

render_top_bar("자재 요청", user)

# ── Dialog: top-level에서 호출해야 안정적으로 렌더링됨 ─────────────────────
if _st_dialog and "_mat_dlg_args" in st.session_state:
    action_dialog(*st.session_state["_mat_dlg_args"])

# ── 처리 완료 팝업 ────────────────────────────────────────────────────────
if "_mat_dlg_result" in st.session_state:
    st.session_state["_done_popup_msg"] = st.session_state.pop("_mat_dlg_result")
if st.session_state.get("_done_popup_msg"):
    _done_popup(st.session_state["_done_popup_msg"])

# ── 타이틀 ────────────────────────────────────────────────────────────────
if IS_MANAGER:
    st.markdown("## 📦 자재 요청 관리")
else:
    st.markdown(f"## 📦 자재 요청 현황 — {user_center}")
st.divider()

rc1, _ = st.columns([2, 6])
if rc1.button("🔄 새로고침", use_container_width=True):
    clear_material_request_cache()
    st.rerun()

# ══════════════════════════════════════════════════════════════════════════
# 관리자 / 자재파트 뷰
# ══════════════════════════════════════════════════════════════════════════
if IS_MANAGER:
    tab_pending, tab_approved, tab_rejected, tab_hold, tab_all = st.tabs([
        "⏳ 대기중", "✅ 승인", "❌ 거절", "⏸️ 보류", "📋 전체"
    ])

    def render_manager(status_filter=None):
        tab_key = status_filter or "all"
        try:
            data = fetch_material_requests(status_filter)
        except Exception as e:
            st.error("자재 요청 테이블이 없습니다. Supabase에서 `material_requests` 테이블을 생성해 주세요.")
            st.code(str(e), language="text")
            return
        if not data:
            st.info("해당 요청 내역이 없습니다.")
            return

        for req in data:
            req_id     = req["id"]
            status     = req.get("status", "pending")
            items      = req.get("items") or []
            req_name   = req.get("requester_name", "")
            req_email  = req.get("requester_email", "")
            center     = req.get("from_center", "")
            req_at     = (req.get("requested_at","") or "")[:16].replace("T"," ")
            proc_at    = (req.get("processed_at","") or "")[:16].replace("T"," ")
            prev_reply = req.get("reply_message","") or ""
            req_notes  = req.get("notes","") or ""

            with st.container(border=True):
                hc1, hc2 = st.columns([5, 2])
                with hc1:
                    st.markdown(
                        f"**{req_name}** &nbsp;·&nbsp; {center} &nbsp;"
                        f"<span style='font-size:12px;color:#666;'>신청: {req_at}</span>",
                        unsafe_allow_html=True
                    )
                    if proc_at: st.caption(f"처리일: {proc_at}")
                    if status not in ("pending", "cancelled"):
                        proc_by = req.get("processor") or {}
                        if proc_by.get("name"):
                            p_center = proc_by.get("assigned_center") or proc_by.get("center", "")
                            st.caption(f"처리자: {proc_by['name']}" + (f" ({p_center})" if p_center else ""))
                    if req_email: st.caption(f"📧 {req_email}")
                with hc2:
                    c = STATUS_COLOR.get(status, "#555")
                    st.markdown(
                        f"<div style='font-size:15px;font-weight:700;color:{c};"
                        f"text-align:right;padding-top:4px;'>{STATUS_KO.get(status, status)}</div>",
                        unsafe_allow_html=True
                    )

                if items:
                    rows = [{"자재명": it.get("item_name",""),
                             "현재재고": it.get("current_qty",0),
                             "요청수량": it.get("requested_qty",0),
                             "재고상태": "⚠️ 재고부족" if it.get("current_qty",0) < it.get("requested_qty",0) else "✅ 충분"}
                            for it in items]
                    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

                if req_notes:
                    st.caption(f"📝 비고: {req_notes}")
                if prev_reply:
                    st.caption(f"💬 회신: {prev_reply}")

                st.divider()

                if status == "pending":
                    # 대기중: 승인/거절/보류 버튼
                    ac1, ac2, ac3 = st.columns(3)
                    if ac1.button("✅ 승인", key=f"appr_{tab_key}_{req_id}",
                                   use_container_width=True, type="primary"):
                        st.session_state["_mat_dlg_args"] = (req_id, req_email, req_name, center, "approved", items, tab_key, req_notes)
                        st.rerun()
                    if ac2.button("❌ 거절", key=f"reje_{tab_key}_{req_id}",
                                   use_container_width=True):
                        st.session_state["_mat_dlg_args"] = (req_id, req_email, req_name, center, "rejected", items, tab_key, req_notes)
                        st.rerun()
                    if ac3.button("⏸️ 보류", key=f"hold_{tab_key}_{req_id}",
                                   use_container_width=True):
                        st.session_state["_mat_dlg_args"] = (req_id, req_email, req_name, center, "on_hold", items, tab_key, req_notes)
                        st.rerun()

                elif status == "on_hold":
                    rc1b, _ = st.columns([2, 4])
                    if rc1b.button("🔄 대기중으로 되돌리기", key=f"revert_{tab_key}_{req_id}",
                                   use_container_width=True):
                        update_material_request_status(req_id, "pending", user_id)
                        clear_material_request_cache()
                        st.rerun()
                else:
                    st.caption("처리 완료된 요청입니다.")

                if user_role == "admin":
                    del_key = f"mat_del_{tab_key}_{req_id}"
                    if del_key not in st.session_state:
                        st.session_state[del_key] = False
                    if not st.session_state[del_key]:
                        da, _ = st.columns([1, 5])
                        if da.button("🗑️ 삭제", key=f"mat_del_btn_{tab_key}_{req_id}",
                                     use_container_width=True):
                            st.session_state[del_key] = True
                            st.rerun()
                    else:
                        st.warning(f"**{req_name}({center})** 자재 요청을 삭제하시겠습니까?")
                        da, db, _ = st.columns([1, 1, 4])
                        if da.button("✅ 확인", key=f"mat_del_ok_{tab_key}_{req_id}",
                                     type="primary", use_container_width=True):
                            get_supabase().table("material_requests").delete().eq("id", req_id).execute()
                            st.session_state[del_key] = False
                            clear_material_request_cache()
                            st.rerun()
                        if db.button("취소", key=f"mat_del_no_{tab_key}_{req_id}",
                                     use_container_width=True):
                            st.session_state[del_key] = False
                            st.rerun()

    with tab_pending:  render_manager("pending")
    with tab_approved: render_manager("approved")
    with tab_rejected: render_manager("rejected")
    with tab_hold:     render_manager("on_hold")
    with tab_all:      render_manager(None)

# ══════════════════════════════════════════════════════════════════════════
# 센터 사용자 뷰 (읽기 전용)
# ══════════════════════════════════════════════════════════════════════════
else:
    if user_role == "guest":
        st.warning("게스트는 자재 요청 현황을 조회할 수 없습니다.")
        st.stop()

    if not user_center:
        st.warning("소속 센터가 지정되지 않아 조회할 수 없습니다. 관리자에게 문의하세요.")
        st.stop()

    tab_all2, tab_pend2, tab_appr2, tab_reje2, tab_hold2, tab_cancel2 = st.tabs([
        "📋 전체", "⏳ 대기중", "✅ 승인", "❌ 거절", "⏸️ 보류", "🚫 취소됨"
    ])

    def render_user(status_filter=None):
        tab_key = status_filter or "all"
        try:
            data = fetch_material_requests(status=status_filter, from_center=user_center)
        except Exception as e:
            st.error("자재 요청 테이블이 없습니다. 관리자에게 문의하세요.")
            return
        if not data:
            st.info("해당 요청 내역이 없습니다.")
            return

        for req in data:
            req_id       = req["id"]
            status       = req.get("status", "pending")
            items        = req.get("items") or []
            req_name     = req.get("requester_name", "")
            req_uid      = req.get("requester_id", "")
            center       = req.get("from_center", "")
            req_at       = (req.get("requested_at","") or "")[:16].replace("T"," ")
            proc_at      = (req.get("processed_at","") or "")[:16].replace("T"," ")
            prev_reply   = req.get("reply_message","") or ""
            is_mine      = (req_uid == user_id)

            c = STATUS_COLOR.get(status, "#555")
            with st.container(border=True):
                hc1, hc2 = st.columns([5, 2])
                with hc1:
                    st.markdown(
                        f"**{req_name}** &nbsp;·&nbsp; {center} &nbsp;"
                        f"<span style='font-size:12px;color:#666;'>신청: {req_at}</span>",
                        unsafe_allow_html=True
                    )
                    if proc_at: st.caption(f"처리일: {proc_at}")
                    if status not in ("pending", "cancelled"):
                        proc_by = req.get("processor") or {}
                        if proc_by.get("name"):
                            p_center = proc_by.get("assigned_center") or proc_by.get("center", "")
                            st.caption(f"처리자: {proc_by['name']}" + (f" ({p_center})" if p_center else ""))
                with hc2:
                    st.markdown(
                        f"<div style='font-size:15px;font-weight:700;color:{c};"
                        f"text-align:right;padding-top:4px;'>{STATUS_KO.get(status, status)}</div>",
                        unsafe_allow_html=True
                    )

                if items:
                    rows = [{"자재명": it.get("item_name",""),
                             "요청수량": it.get("requested_qty",0)}
                            for it in items]
                    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

                if prev_reply:
                    st.info(f"💬 담당자 회신: {prev_reply}")

                # 본인의 대기중 요청만 취소 가능
                if status == "pending" and is_mine:
                    st.divider()
                    cancel_key = f"cancel_confirm_{tab_key}_{req_id}"
                    if cancel_key not in st.session_state:
                        st.session_state[cancel_key] = False

                    if not st.session_state[cancel_key]:
                        if st.button("🚫 요청 취소", key=f"cancel_btn_{tab_key}_{req_id}",
                                     use_container_width=True):
                            st.session_state[cancel_key] = True
                            st.rerun()
                    else:
                        st.warning("이 자재 요청을 취소하시겠습니까?")
                        cc1, cc2 = st.columns(2)
                        if cc1.button("✅ 확인", key=f"cancel_ok_{tab_key}_{req_id}",
                                      type="primary", use_container_width=True):
                            update_material_request_status(req_id, "cancelled", user_id)
                            # 자재파트 + 관리자에게 취소 알림 메일
                            try:
                                sb_c = get_supabase()
                                r_mat = sb_c.table("users").select("email, assigned_center") \
                                            .eq("role", "materials").eq("is_approved", True).execute()
                                r_adm = sb_c.table("users").select("email, assigned_center") \
                                            .eq("role", "admin").eq("is_approved", True).execute()
                                notify_emails = list({
                                    u["email"]
                                    for res in [r_mat, r_adm]
                                    for u in (res.data or [])
                                    if u.get("email") and u.get("assigned_center") != "고객지원사업부"
                                })
                                if notify_emails:
                                    send_material_request_cancelled(
                                        notify_emails, center, req_name, items
                                    )
                            except Exception:
                                pass
                            st.session_state[cancel_key] = False
                            st.success("요청이 취소됐습니다. 자재파트/관리자에게 취소 알림이 발송됐습니다.")
                            st.rerun()
                        if cc2.button("❌ 아니오", key=f"cancel_no_{tab_key}_{req_id}",
                                      use_container_width=True):
                            st.session_state[cancel_key] = False
                            st.rerun()

    with tab_all2:    render_user(None)
    with tab_pend2:   render_user("pending")
    with tab_appr2:   render_user("approved")
    with tab_reje2:   render_user("rejected")
    with tab_hold2:   render_user("on_hold")
    with tab_cancel2: render_user("cancelled")

