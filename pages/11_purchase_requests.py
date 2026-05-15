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
from utils.mail import send_purchase_request, send_purchase_request_reply

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
    if st.button("📊 대시보드", use_container_width=True):
        st.switch_page("pages/10_dashboard.py")
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
def _make_excel(items: list, name: str, center: str, reason_txt: str) -> bytes:
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
    ]
    for ref, val in info:
        ws[ref] = val
    ws.merge_cells("B5:D5")
    for ref in ("A3", "C3", "A4", "A5"):
        ws[ref].font = Font(bold=True)

    header_fill = PatternFill("solid", fgColor="E8EDF5")
    thin = Side(style="thin", color="CCCCCC")
    bdr  = Border(left=thin, right=thin, top=thin, bottom=thin)
    for col, h in enumerate(["No", "품명", "수량", "링크"], 1):
        c = ws.cell(row=7, column=col, value=h)
        c.font = Font(bold=True, color="1A237E")
        c.fill = header_fill
        c.alignment = Alignment(horizontal="center")
        c.border = bdr

    for i, item in enumerate(items, 1):
        for col, val in enumerate([i, item.get("품명",""), item.get("수량",""), item.get("링크","")], 1):
            c = ws.cell(row=7 + i, column=col, value=val)
            c.border = bdr

    ws.column_dimensions["A"].width = 6
    ws.column_dimensions["B"].width = 30
    ws.column_dimensions["C"].width = 8
    ws.column_dimensions["D"].width = 50

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.getvalue()


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
    reason = st.text_area("구매사유", placeholder="품의서에 들어갈 구매사유 문구를 입력해주세요.", key="pr_reason")

    _mask = df_edit["품명"].notna() & (df_edit["품명"].astype(str).str.strip() != "")
    _df_valid = df_edit[_mask].copy()
    _df_valid["수량"] = _df_valid["수량"].fillna(1).astype(int)
    _df_valid["링크"] = _df_valid["링크"].fillna("").astype(str)
    valid_items = _df_valid.to_dict("records")

    col_submit, col_excel = st.columns(2)

    # 엑셀 다운로드 (항상 활성화)
    _excel_data = _make_excel(valid_items, user_name, user_center, reason)
    col_excel.download_button(
        "📥 엑셀 다운로드",
        data=_excel_data,
        file_name=f"구매요청서_{user_name}_{datetime.now().strftime('%Y%m%d')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )

    if col_submit.button("📨 요청 제출", type="primary", use_container_width=True):
        if not valid_items:
            st.error("구매 목록을 1개 이상 입력해 주세요.")
        elif not reason.strip():
            st.error("구매사유를 입력해 주세요.")
        else:
            sb = get_supabase()
            try:
                sb.table("purchase_requests").insert({
                    "requester_id":     user_id,
                    "requester_name":   user_name,
                    "requester_center": user_center,
                    "items":            valid_items,
                    "reason":           reason.strip(),
                    "status":           "pending",
                }).execute()

                # 알림 메일: admin + materials 역할 전체
                _target_emails = [
                    u["email"] for u in
                    (sb.table("users").select("email")
                       .in_("role", ["admin", "materials"])
                       .eq("is_approved", True)
                       .execute().data or [])
                    if u.get("email")
                ]
                if _target_emails:
                    send_purchase_request(
                        to_emails=_target_emails,
                        requester_name=user_name,
                        requester_center=user_center,
                        items=valid_items,
                        reason=reason.strip(),
                        requested_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
                    )

                clear_purchase_request_cache()
                st.success("✅ 구매 요청이 제출됐습니다. 관리자 및 자재파트에 알림 메일을 발송했습니다.")
                st.rerun()
            except Exception as e:
                st.error(f"제출 실패: {e}")


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

                    # 해당 요청 엑셀 다운로드
                    _dl = _make_excel(items, req["requester_name"], req["requester_center"], req.get("reason",""))
                    st.download_button(
                        "📥 요청서 엑셀",
                        data=_dl,
                        file_name=f"구매요청서_{req['requester_name']}_{req_date[:10]}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        key=f"pr_dl_{req['id']}",
                    )


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

                _dl = _make_excel(items, req["requester_name"], req["requester_center"], req.get("reason",""))
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
