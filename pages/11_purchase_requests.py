# pages/11_purchase_requests.py
import io
import streamlit as st
import pandas as pd
from datetime import datetime
from utils.auth import require_login, is_role
from utils.db import get_supabase, fetch_purchase_requests, clear_purchase_request_cache
from utils.permissions import get_viewable_centers, get_center as _get_center
from utils.routing import CENTERS
from utils.ui import apply_global_css, render_sidebar_header, render_sidebar_section, render_sidebar_user, render_top_bar
from utils.mail import send_purchase_request, send_purchase_request_reply, send_purchase_request_submitted

st.set_page_config(
    page_title="에이텍모빌리티 자재관리",
    page_icon="favicon_32.png",
    layout="wide",
    initial_sidebar_state="expanded",
)

apply_global_css()
require_login()

user        = st.session_state.user
user_id     = user["id"]
user_role   = user["role"]
user_name   = user["name"]
user_center = _get_center(user)

IS_MANAGER  = is_role("admin", "materials")

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
    if st.button("📋 입출고 이력", use_container_width=True):
        st.switch_page("pages/04_history.py")
    if not is_role("guest"):
        if st.button("📊 사용내역", use_container_width=True):
            st.switch_page("pages/08_usage_history.py")

    if not is_role("guest"):
        render_sidebar_section("요청")
        if st.button("📦 자재 요청", use_container_width=True, key="sidebar_mat_req"):
            st.switch_page("pages/07_material_requests.py")
        st.button("🛒 구매 요청", use_container_width=True, type="primary")

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
        st.session_state.user = None
        st.switch_page("pages/01_login.py")
    render_sidebar_user(user)

render_top_bar("구매 요청", user)

if user_role == "guest":
    st.warning("게스트는 구매 요청을 할 수 없습니다.")
    st.stop()


# ── 엑셀 생성 헬퍼 ────────────────────────────────────────────────────────
def _make_excel(items: list, name: str, center: str, reason_txt: str, cost_note_txt: str = "") -> bytes:
    import openpyxl
    from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "구매요청서"

    ws.merge_cells("A1:D1")
    ws["A1"] = "구매 요청서"
    ws["A1"].font = Font(size=16, bold=True)
    ws["A1"].alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[1].height = 32

    info = [
        ("A3", "요청자"), ("B3", name),
        ("C3", "소속"),   ("D3", center),
        ("A4", "요청일"), ("B4", datetime.now().strftime("%Y-%m-%d %H:%M")),
        ("A5", "구매사유"), ("B5", reason_txt or "-"),
        ("A6", "원가반영"), ("B6", cost_note_txt or "-"),
    ]
    for ref, val in info:
        ws[ref] = val
    ws.merge_cells("B5:D5")
    ws.merge_cells("B6:D6")
    for ref in ("A3", "C3", "A4", "A5", "A6"):
        ws[ref].font = Font(bold=True)

    header_fill = PatternFill("solid", fgColor="E8EDF5")
    thin = Side(style="thin", color="CCCCCC")
    bdr  = Border(left=thin, right=thin, top=thin, bottom=thin)
    for col, h in enumerate(["No", "품명", "수량", "링크"], 1):
        c = ws.cell(row=8, column=col, value=h)
        c.font = Font(bold=True, color="1A237E")
        c.fill = header_fill
        c.alignment = Alignment(horizontal="center")
        c.border = bdr

    for i, item in enumerate(items, 1):
        for col, val in enumerate([i, item.get("품명",""), item.get("수량",""), item.get("링크","")], 1):
            c = ws.cell(row=8 + i, column=col, value=val)
            c.border = bdr

    ws.column_dimensions["A"].width = 14
    ws.column_dimensions["B"].width = 30
    ws.column_dimensions["C"].width = 8
    ws.column_dimensions["D"].width = 50

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.getvalue()


# ── 사용 가이드 ──────────────────────────────────────────────────────────
with st.expander("💡 사용 가이드", expanded=True):
    _guide = []
    _guide.append(("📝 새 요청 작성",   "품명·수량·링크를 입력하고 구매사유를 작성한 후 요청을 제출합니다. 관리자 및 자재파트에 알림 메일이 자동 발송됩니다."))
    _guide.append(("📥 엑셀 다운로드",  "작성 중인 요청서를 엑셀 양식으로 저장합니다. 품의서 첨부용으로 활용할 수 있습니다."))
    _guide.append(("👤 내 요청 현황",   "제출한 요청의 처리 상태를 조회합니다. 처리 결과(처리중·완료·거절)는 이메일로 자동 안내됩니다."))
    if IS_MANAGER:
        _guide.append(("📋 전체 요청 현황", "모든 센터의 구매 요청을 확인하고 상태를 변경합니다. (관리자·자재파트 전용)"))
        _guide.append(("상태 변경",         "처리중·완료·거절로 변경하면 신청자에게 회신 메일이 자동 발송됩니다."))

    _rows_html = "".join(
        f"<tr>"
        f"<td style='padding:3px 14px 3px 0;font-weight:600;font-size:12px;white-space:nowrap;'>{b}</td>"
        f"<td style='padding:3px 0;font-size:12px;color:#64748B;'>— {d}</td>"
        f"</tr>"
        for b, d in _guide
    )
    st.markdown(
        f"<table style='border-collapse:collapse;width:100%;'>{_rows_html}</table>",
        unsafe_allow_html=True
    )

# ── 구매 요청 완료 팝업 ────────────────────────────────────────────────────
@st.experimental_dialog("📨 구매 요청 완료")
def _purchase_success_dialog():
    items_done = st.session_state.get("_pr_success_items", [])
    st.success("요청이 정상적으로 접수되었습니다.")
    st.markdown(f"**{user_name}** ({user_center})님의 구매 요청이 관리자 및 자재파트에 전달되었습니다.")
    if items_done:
        st.markdown("**요청 품목**")
        for i, it in enumerate(items_done, 1):
            st.caption(f"{i}. {it.get('품명','')} — {it.get('수량','')}개")
    if st.button("확인", type="primary", use_container_width=True, key="_pr_dialog_ok"):
        st.session_state.pop("_pr_success_items", None)
        st.session_state.pop("_pr_success", None)
        st.rerun()


# ── 탭 ────────────────────────────────────────────────────────────────────
if IS_MANAGER:
    tab_new, tab_all, tab_mine = st.tabs(["📝 새 요청 작성", "📋 전체 요청 현황", "👤 내 요청"])
else:
    tab_new, tab_mine = st.tabs(["📝 새 요청 작성", "👤 내 요청 현황"])
    tab_all = None


# ══════════════════════════════════════════════════════════════════════════
# 탭 1: 새 요청 작성
# ══════════════════════════════════════════════════════════════════════════
with tab_new:
    st.markdown("### 📝 구매요청서 작성")
    c1, c2 = st.columns(2)
    c1.text_input("요청자", value=user_name,   disabled=True, key="pr_req_name")
    c2.text_input("소속",   value=user_center, disabled=True, key="pr_req_center")

    st.markdown("**구매 목록**")
    _default = pd.DataFrame({"품명": [""], "수량": [1], "링크": [""]})
    df_edit = st.data_editor(
        _default,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "품명": st.column_config.TextColumn("품명", width="medium"),
            "수량": st.column_config.NumberColumn("수량", min_value=1, step=1, format="%d", width="small"),
            "링크": st.column_config.TextColumn("링크 (URL)", width="large"),
        },
        key="pr_items_editor",
        hide_index=True,
    )
    reason    = st.text_area("구매사유 *", placeholder="품의서에 들어갈 구매사유 문구를 입력해주세요.", key="pr_reason")
    cost_note = st.text_area("원가반영 *", placeholder="원가반영 내용을 입력해주세요.", key="pr_cost_note", height=120)

    _mask = df_edit["품명"].notna() & (df_edit["품명"].astype(str).str.strip() != "")
    _df_valid = df_edit[_mask].copy()
    _df_valid["수량"] = _df_valid["수량"].fillna(1).astype(int)
    _df_valid["링크"] = _df_valid["링크"].fillna("").astype(str)
    valid_items = _df_valid.to_dict("records")

    if st.button("📨 요청 제출", type="primary", use_container_width=True):
        _last_submit = st.session_state.get("_pr_last_submit_time")
        _cooldown_sec = 60
        if _last_submit and (datetime.now() - _last_submit).total_seconds() < _cooldown_sec:
            _remain = int(_cooldown_sec - (datetime.now() - _last_submit).total_seconds())
            st.error(f"요청이 이미 제출되었습니다. {_remain}초 후 다시 시도해 주세요.")
        elif not valid_items:
            st.error("구매 목록을 1개 이상 입력해 주세요.")
        elif not reason.strip():
            st.error("구매사유를 입력해 주세요.")
        elif not cost_note.strip():
            st.error("원가반영을 입력해 주세요.")
        else:
            sb = get_supabase()
            try:
                _now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
                sb.table("purchase_requests").insert({
                    "requester_id":     user_id,
                    "requester_name":   user_name,
                    "requester_center": user_center,
                    "items":            valid_items,
                    "reason":           reason.strip(),
                    "cost_note":        cost_note.strip() or None,
                    "status":           "pending",
                }).execute()

                # 엑셀 첨부파일 생성
                _fname = f"구매요청서_{user_name}_{datetime.now().strftime('%Y%m%d')}.xlsx"
                _attach = (_fname, _make_excel(valid_items, user_name, user_center, reason.strip(), cost_note.strip()))

                # 관리자·자재파트 알림 메일
                _target_emails = [
                    u["email"] for u in
                    (sb.table("users").select("email, assigned_center")
                       .in_("role", ["admin", "materials"])
                       .eq("is_approved", True)
                       .execute().data or [])
                    if u.get("email") and u.get("assigned_center") != "고객지원사업부"
                ]
                if _target_emails:
                    send_purchase_request(
                        to_emails=_target_emails,
                        requester_name=user_name,
                        requester_center=user_center,
                        items=valid_items,
                        reason=reason.strip(),
                        requested_at=_now_str,
                        cost_note=cost_note.strip(),
                        attachment=_attach,
                    )

                # 신청자 접수 확인 메일
                _requester_email = user.get("email", "")
                if _requester_email:
                    send_purchase_request_submitted(
                        to_email=_requester_email,
                        requester_name=user_name,
                        requester_center=user_center,
                        items=valid_items,
                        reason=reason.strip(),
                        requested_at=_now_str,
                        cost_note=cost_note.strip(),
                        attachment=_attach,
                    )

                st.session_state["_pr_last_submit_time"] = datetime.now()
                st.session_state["_pr_success"] = True
                st.session_state["_pr_success_items"] = valid_items
                clear_purchase_request_cache()
            except Exception as e:
                st.error(f"제출 실패: {e}")

    if st.session_state.get("_pr_success"):
        _purchase_success_dialog()


# ══════════════════════════════════════════════════════════════════════════
# 탭 2: 전체 요청 현황 (admin / materials)
# ══════════════════════════════════════════════════════════════════════════
STATUS_KO = {
    "pending":     "⏳ 대기중",
    "in_progress": "🔄 처리중",
    "completed":   "✅ 완료",
    "rejected":    "❌ 거절",
}

if tab_all is not None:
    with tab_all:
        rc1, rc2 = st.columns([1, 7])
        if rc1.button("🔄 새로고침", use_container_width=True, key="pr_all_refresh"):
            clear_purchase_request_cache()
            st.rerun()

        all_data = fetch_purchase_requests()
        if not all_data:
            st.info("접수된 구매 요청이 없습니다.")
        else:
            for req in all_data:
                items    = req.get("items") or []
                status   = req.get("status", "pending")
                req_date = (req.get("requested_at") or "")[:16].replace("T", " ")
                with st.container(border=True):
                    h1, h2, h3, h4 = st.columns([3, 2, 2, 2])
                    h1.markdown(f"**{req['requester_name']}** ({req['requester_center']})")
                    h1.caption(f"📅 {req_date}")
                    h2.markdown(f"품목 **{len(items)}**개")
                    h2.caption(req.get("reason", "")[:40])
                    h3.markdown(STATUS_KO.get(status, status))

                    with h4:
                        new_status = st.selectbox(
                            "상태 변경",
                            list(STATUS_KO.keys()),
                            index=list(STATUS_KO.keys()).index(status) if status in STATUS_KO else 0,
                            format_func=lambda s: STATUS_KO[s],
                            label_visibility="collapsed",
                            key=f"pr_status_{req['id']}",
                        )
                        if new_status != status:
                            _reply_msg = ""
                            if new_status in ("in_progress", "completed", "rejected"):
                                _reply_msg = st.text_input(
                                    "메시지 (선택)",
                                    key=f"pr_msg_{req['id']}",
                                    placeholder="신청자에게 전달할 메시지",
                                )
                            if st.button("저장", key=f"pr_save_{req['id']}", use_container_width=True):
                                try:
                                    _sb = get_supabase()
                                    _sb.table("purchase_requests").update({
                                        "status": new_status,
                                        "processed_at": datetime.utcnow().isoformat(),
                                    }).eq("id", req["id"]).execute()

                                    # 처리중·완료·거절 → 신청자 회신 메일
                                    if new_status in ("in_progress", "completed", "rejected"):
                                        _req_id = req.get("requester_id")
                                        if _req_id:
                                            _u = _sb.table("users").select("email").eq("id", _req_id).execute().data
                                            if _u and _u[0].get("email"):
                                                send_purchase_request_reply(
                                                    to_email=_u[0]["email"],
                                                    requester_name=req["requester_name"],
                                                    items=req.get("items") or [],
                                                    status=new_status,
                                                    reply_msg=_reply_msg,
                                                )

                                    clear_purchase_request_cache()
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"상태 변경 실패: {e}")

                    # 구매 목록 상세
                    with st.expander("구매 목록 보기"):
                        for i, it in enumerate(items, 1):
                            link = str(it.get("링크") or "")
                            link_md = f"[링크]({link})" if link else "-"
                            st.markdown(f"{i}. **{it.get('품명','')}** — {it.get('수량','')}개 &nbsp; {link_md}")
                        if req.get("cost_note"):
                            st.markdown(f"**원가반영:** {req['cost_note']}")

                    # 해당 요청 엑셀 다운로드
                    _dl = _make_excel(items, req["requester_name"], req["requester_center"], req.get("reason",""), req.get("cost_note",""))
                    _col_dl, _col_del = st.columns([3, 1])
                    _col_dl.download_button(
                        "📥 요청서 엑셀",
                        data=_dl,
                        file_name=f"구매요청서_{req['requester_name']}_{req_date[:10]}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        key=f"pr_dl_{req['id']}",
                        use_container_width=True,
                    )

                    # 관리자 삭제
                    if user_role == "admin":
                        _del_key = f"pr_del_confirm_{req['id']}"
                        if not st.session_state.get(_del_key):
                            if _col_del.button("🗑️ 삭제", key=f"pr_del_{req['id']}",
                                               use_container_width=True):
                                st.session_state[_del_key] = True
                                st.rerun()
                        else:
                            st.error(f"**{req['requester_name']}** ({req_date}) 요청을 삭제합니다. 되돌릴 수 없습니다.")
                            _dc1, _dc2 = st.columns(2)
                            if _dc1.button("✅ 확인 삭제", key=f"pr_del_ok_{req['id']}",
                                           type="primary", use_container_width=True):
                                try:
                                    get_supabase().table("purchase_requests").delete().eq(
                                        "id", req["id"]
                                    ).execute()
                                    st.session_state.pop(_del_key, None)
                                    clear_purchase_request_cache()
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"삭제 실패: {e}")
                            if _dc2.button("❌ 취소", key=f"pr_del_cancel_{req['id']}",
                                           use_container_width=True):
                                st.session_state.pop(_del_key, None)
                                st.rerun()


# ══════════════════════════════════════════════════════════════════════════
# 탭 3(일반) / 탭 2(관리자): 내 요청 현황
# ══════════════════════════════════════════════════════════════════════════
with tab_mine:
    if st.button("🔄 새로고침", use_container_width=True, key="pr_mine_refresh"):
        clear_purchase_request_cache()
        st.rerun()

    mine_data = fetch_purchase_requests(requester_id=user_id)
    if not mine_data:
        st.info("제출한 구매 요청이 없습니다.")
    else:
        for req in mine_data:
            items    = req.get("items") or []
            status   = req.get("status", "pending")
            req_date = (req.get("requested_at") or "")[:16].replace("T", " ")
            with st.container(border=True):
                m1, m2, m3 = st.columns([4, 2, 2])
                m1.markdown(f"**{req_date}** — 품목 {len(items)}개")
                m1.caption(req.get("reason", "")[:60])
                m2.markdown(STATUS_KO.get(status, status))

                _dl = _make_excel(items, req["requester_name"], req["requester_center"], req.get("reason",""), req.get("cost_note",""))
                m3.download_button(
                    "📥 엑셀",
                    data=_dl,
                    file_name=f"구매요청서_{req_date[:10]}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key=f"pr_mine_dl_{req['id']}",
                )

                with st.expander("구매 목록"):
                    for i, it in enumerate(items, 1):
                        link = str(it.get("링크") or "")
                        link_md = f"[링크]({link})" if link else "-"
                        st.markdown(f"{i}. **{it.get('품명','')}** — {it.get('수량','')}개 &nbsp; {link_md}")
