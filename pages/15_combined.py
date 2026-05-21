# pages/15_combined.py  — 재고 현황 + 이동 신청 통합 뷰
import streamlit as st
import pandas as pd
from utils.auth import require_login, is_role, logout
from utils.db import (
    fetch_warehouse, fetch_categories, fetch_transfers,
    approve_transfer, create_transfer,
    clear_warehouse_cache, clear_transfer_cache, clear_history_cache,
    get_supabase,
)
from utils.routing import get_allowed_destinations, NO_WAREHOUSE_CENTERS, CATEGORY_DESTINATIONS
from utils.permissions import (
    can_stock_in_out, can_request_transfer,
    can_approve_transfer, filter_transfers_for_user,
    get_viewable_centers, get_center as _get_center,
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

# ── 세션 초기화 (cv_ 프리픽스로 기존 페이지와 충돌 방지) ─────────────────────
_cv_defaults = {
    "cv_large": "전체", "cv_mid": "전체", "cv_small": "전체",
    "cv_page": 1, "cv_page_size": 20,
}
for k, v in _cv_defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ── 완료 팝업 ─────────────────────────────────────────────────────────────
@st.experimental_dialog("✅ 처리 완료")
def _cv_done_popup(msg: str):
    st.markdown(msg)
    st.write("")
    if st.button("확인", use_container_width=True, type="primary", key="cv_done_ok"):
        st.session_state.pop("_cv_done_msg", None)
        st.rerun()

# ── 이동 신청 승인 다이얼로그 ──────────────────────────────────────────────
_st_dialog = getattr(st, "dialog", getattr(st, "experimental_dialog", None))

if _st_dialog:
    @_st_dialog("자재센터 입고 위치 지정", width="large")
    def _cv_hub_dialog(transfer_id, item_name, from_center, qty):
        _u  = st.session_state.user
        _sb = get_supabase()
        st.markdown(f"**{item_name}** &nbsp; {from_center} → 자재센터 &nbsp; **{qty}개**")
        st.caption("자재센터에서 보관할 위치(렉/단수/박스)를 지정하세요.")
        st.divider()
        existing = _sb.table("warehouse").select("rack_no,shelf,box_no,quantity") \
            .eq("item_name", item_name).eq("location", "자재센터").execute().data
        rack_no = shelf = box_no = ""
        show_new = True
        if existing:
            mode = st.radio("입고 위치", ["기존 위치에 추가", "새 위치 지정"],
                            horizontal=True, key=f"cv_hub_mode_{transfer_id}")
            if mode == "기존 위치에 추가":
                opts = {f"렉 {r.get('rack_no','?')}  {r.get('shelf','?')}단  박스 {r.get('box_no','?')}  (현재: {r['quantity']}개)": r
                        for r in existing}
                picked = opts[st.selectbox("위치 선택", list(opts.keys()), key=f"cv_hub_sel_{transfer_id}")]
                rack_no, shelf, box_no = str(picked.get("rack_no","") or ""), str(picked.get("shelf","") or ""), str(picked.get("box_no","") or "")
                show_new = False
        else:
            st.info("자재센터에 해당 자재가 없습니다. 새 위치를 지정하면 신규 등록됩니다.")
        if show_new:
            c1, c2, c3 = st.columns(3)
            rack_no = c1.text_input("렉 번호", key=f"cv_rack_{transfer_id}")
            shelf   = c2.text_input("단수",   key=f"cv_shelf_{transfer_id}")
            box_no  = c3.text_input("박스 번호", key=f"cv_box_{transfer_id}")
        st.divider()
        ca, cb = st.columns(2)
        if ca.button("✅ 승인", type="primary", use_container_width=True, key=f"cv_hub_ok_{transfer_id}"):
            if approve_transfer(transfer_id, _u, rack_no=rack_no, shelf=shelf, box_no=box_no):
                clear_warehouse_cache()
                st.session_state["_cv_done_msg"] = "✅ 승인 완료!"
                st.rerun()
        if cb.button("취소", use_container_width=True, key=f"cv_hub_cancel_{transfer_id}"):
            st.rerun()

# 이동 신청 완료 팝업 표시
if st.session_state.get("_cv_done_msg"):
    _cv_done_popup(st.session_state["_cv_done_msg"])

# ── 사용자 정보 ───────────────────────────────────────────────────────────
user       = st.session_state.user
user_id    = user["id"]
user_role  = user["role"]
user_name  = user["name"]
my_center  = _get_center(user)

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
    selected_center = st.selectbox("센터", viewable, label_visibility="collapsed", key="sidebar_center")

    render_sidebar_section("재고 관리")
    if st.button("📦 재고 현황", use_container_width=True):
        st.switch_page("pages/02_warehouse.py")
    if st.button("🚚 이동 신청 현황", use_container_width=True):
        st.switch_page("pages/03_transfers.py")
    st.button("🗂️ 통합 뷰", use_container_width=True, type="primary")
    if st.button("📋 입출고 이력", use_container_width=True):
        st.switch_page("pages/04_history.py")
    if not is_role("guest"):
        if st.button("📊 사용내역", use_container_width=True):
            st.switch_page("pages/08_usage_history.py")
    if not is_role("guest"):
        render_sidebar_section("요청")
        if st.button("📦 자재요청현황", use_container_width=True, key="cv_mat"):
            st.switch_page("pages/07_material_requests.py")
        if st.button("🛒 구매 요청", use_container_width=True, key="cv_pur"):
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

render_top_bar("통합 뷰", user)

# ══════════════════════════════════════════════════════════════════════════
# 메인 탭
# ══════════════════════════════════════════════════════════════════════════
tab_wh, tab_tr = st.tabs(["📦 재고 현황", "🚚 이동 신청 현황"])


# ══ 탭 1: 재고 현황 ════════════════════════════════════════════════════════
with tab_wh:
    IS_HUB   = selected_center == "자재센터"
    CAN_TRANSFER_WH = can_request_transfer(user, selected_center)

    # ── 데이터 로드 ─────────────────────────────────────────────────────
    raw_data   = fetch_warehouse(selected_center)
    categories = fetch_categories()
    df_all     = pd.DataFrame(raw_data) if raw_data else pd.DataFrame()

    # ── 필터 바 ─────────────────────────────────────────────────────────
    large_cats = ["전체"] + sorted(categories.keys())
    _sl = st.session_state.cv_large
    _sm = st.session_state.cv_mid

    mid_cats = (["전체"] + categories.get(_sl, [])) if _sl != "전체" else ["전체"]
    small_cats = ["전체"] + sorted({
        r.get("category_small") for r in raw_data
        if r.get("category_small")
        and (_sl == "전체" or r.get("category_large") == _sl)
        and (_sm == "전체" or r.get("category_mid") == _sm)
    })

    fc = st.columns([2.5, 1, 1, 1, 0.9])
    search = fc[0].text_input("검색", placeholder="자재명 / ERP코드 / 분류명 검색...",
                              label_visibility="collapsed", key="cv_search")

    new_lg = fc[1].selectbox("대분류", large_cats,
                              index=large_cats.index(_sl) if _sl in large_cats else 0,
                              label_visibility="collapsed", key="cv_filter_lg")
    if new_lg != _sl:
        st.session_state.cv_large = new_lg
        st.session_state.cv_mid   = "전체"
        st.session_state.cv_small = "전체"
        st.session_state.cv_page  = 1
        st.rerun()

    _cur_mid = _sm if _sm in mid_cats else "전체"
    new_md   = fc[2].selectbox("중분류", mid_cats, index=mid_cats.index(_cur_mid),
                                label_visibility="collapsed", key="cv_filter_md")
    if new_md != _sm:
        st.session_state.cv_mid   = new_md
        st.session_state.cv_small = "전체"
        st.session_state.cv_page  = 1
        st.rerun()

    _cur_sm = st.session_state.get("cv_small", "전체")
    _cur_sm = _cur_sm if _cur_sm in small_cats else "전체"
    new_sm  = fc[3].selectbox("소분류", small_cats, index=small_cats.index(_cur_sm),
                               label_visibility="collapsed", key="cv_filter_sm")
    if new_sm != _cur_sm:
        st.session_state.cv_small = new_sm
        st.session_state.cv_page  = 1
        st.rerun()

    if fc[4].button("초기화", use_container_width=True, key="cv_reset"):
        for k in ("cv_large", "cv_mid", "cv_small"):
            st.session_state[k] = "전체"
        st.session_state.cv_page = 1
        clear_warehouse_cache()
        st.rerun()

    # ── 데이터 필터링 ────────────────────────────────────────────────────
    if not df_all.empty:
        filtered = df_all.copy()
        if st.session_state.cv_large != "전체":
            filtered = filtered[filtered["category_large"] == st.session_state.cv_large]
        if st.session_state.cv_mid != "전체":
            filtered = filtered[filtered["category_mid"] == st.session_state.cv_mid]
        if st.session_state.get("cv_small", "전체") != "전체":
            filtered = filtered[filtered["category_small"] == st.session_state.cv_small]
        if search:
            q = search.lower()
            mask = (
                filtered.get("item_name",   pd.Series(dtype=str)).fillna("").str.lower().str.contains(q) |
                filtered.get("erp_code",    pd.Series(dtype=str)).fillna("").str.lower().str.contains(q) |
                filtered.get("category_large", pd.Series(dtype=str)).fillna("").str.lower().str.contains(q) |
                filtered.get("category_mid",   pd.Series(dtype=str)).fillna("").str.lower().str.contains(q) |
                filtered.get("rack_no",     pd.Series(dtype=str)).fillna("").str.lower().str.contains(q)
            )
            filtered = filtered[mask]
    else:
        filtered = pd.DataFrame()

    # ── 요약 + 링크 ──────────────────────────────────────────────────────
    total = len(filtered)
    r1, r2 = st.columns([6, 1])
    r1.caption(f"**{selected_center}** — 총 {total:,}개 품목" +
               (f"  (검색: {search})" if search else ""))
    if r2.button("전체 페이지", use_container_width=True, key="cv_goto_wh",
                 help="전체 기능 보기 (입출고, 업로드 등)"):
        st.switch_page("pages/02_warehouse.py")

    # ── 이동 신청 패널 ───────────────────────────────────────────────────
    if CAN_TRANSFER_WH and not filtered.empty:
        with st.expander("🚚 이동 신청", expanded=False):
            allowed_dst = get_allowed_destinations(selected_center)
            if not allowed_dst:
                st.info("이동 가능한 목적지가 없습니다.")
            else:
                # 카테고리 선택 시 도착센터 필터링
                _sel_cat = st.session_state.get("cv_tr_cat", "전체")
                if _sel_cat in CATEGORY_DESTINATIONS:
                    _cat_dsts = CATEGORY_DESTINATIONS[_sel_cat]
                    _dst_opts = [d for d in allowed_dst if d in _cat_dsts]
                    if not _dst_opts:
                        _dst_opts = allowed_dst
                else:
                    _dst_opts = allowed_dst

                dst = st.selectbox("도착 센터", _dst_opts, key="cv_tr_dst")

                # ── 버스 / 택시 카테고리 필터 ──────────────────────────
                if "cv_tr_cat" not in st.session_state:
                    st.session_state.cv_tr_cat = "전체"

                _cats_in_data = []
                if "category_large" in filtered.columns:
                    _cats_in_data = sorted(filtered["category_large"].dropna().unique().tolist())

                _cat_btns = ["전체"] + _cats_in_data
                _btn_cols = st.columns(len(_cat_btns))
                for _i, _cat in enumerate(_cat_btns):
                    _is_active = st.session_state.cv_tr_cat == _cat
                    if _btn_cols[_i].button(
                        _cat, key=f"cv_tr_cat_{_cat}",
                        type="primary" if _is_active else "secondary",
                        use_container_width=True,
                    ):
                        st.session_state.cv_tr_cat = _cat
                        st.session_state.pop("cv_tr_items", None)

                # 선택된 카테고리로 항목 필터링
                _tr_filtered = filtered.copy()
                if st.session_state.cv_tr_cat != "전체" and "category_large" in _tr_filtered.columns:
                    _tr_filtered = _tr_filtered[_tr_filtered["category_large"] == st.session_state.cv_tr_cat]

                # 라벨: 자재명  |  수량 N  렉 A1  박스 3
                def _tr_label(row):
                    qty_v  = int(row.get("quantity", 0) or 0)
                    rack   = str(row.get("rack_no", "") or "").strip()
                    box_v  = str(row.get("box_no",  "") or "").strip()
                    parts  = [f"수량 {qty_v}"]
                    if rack:  parts.append(f"렉 {rack}")
                    if box_v: parts.append(f"박스 {box_v}")
                    return f"{row['item_name']}  |  {' · '.join(parts)}"

                _label_to_id = {}
                _label_opts  = []
                for _, _row in _tr_filtered.iterrows():
                    _lbl = _tr_label(_row)
                    _label_to_id[_lbl] = int(_row["id"])
                    _label_opts.append(_lbl)

                sel_labels = st.multiselect(
                    f"이동할 자재 선택 ({st.session_state.cv_tr_cat})",
                    options=_label_opts,
                    key="cv_tr_items"
                )
                qty = st.number_input("수량", min_value=1, value=1, key="cv_tr_qty")
                if st.button("✅ 이동 신청", type="primary",
                             use_container_width=True, key="cv_tr_submit",
                             disabled=not sel_labels):
                    ok_count = 0
                    for lbl in sel_labels:
                        item_id = _label_to_id.get(lbl)
                        if item_id is None:
                            continue
                        try:
                            create_transfer(item_id, selected_center, dst, qty, user_id)
                            ok_count += 1
                        except Exception:
                            pass
                    if ok_count:
                        clear_transfer_cache()
                        st.success(f"✅ {ok_count}개 이동 신청 완료 → {dst}")

    # ── 데이터 테이블 ────────────────────────────────────────────────────
    if filtered.empty:
        st.info("📭 해당 조건의 재고가 없습니다.")
    else:
        PAGE_SIZE = st.session_state.cv_page_size
        page_num  = st.session_state.cv_page
        total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
        page_num    = min(page_num, total_pages)
        st.session_state.cv_page = page_num

        start = (page_num - 1) * PAGE_SIZE
        end   = start + PAGE_SIZE
        page_df = filtered.iloc[start:end]

        # 표시 컬럼 선택
        show_cols = [c for c in ["item_name", "quantity", "category_large",
                                  "category_mid", "category_small",
                                  "rack_no", "erp_code"] if c in page_df.columns]
        col_labels = {
            "item_name":      "자재명",
            "quantity":       "수량",
            "category_large": "대분류",
            "category_mid":   "중분류",
            "category_small": "소분류",
            "rack_no":        "렉번호",
            "erp_code":       "ERP코드",
        }
        disp = page_df[show_cols].rename(columns=col_labels)
        st.dataframe(disp, use_container_width=True, hide_index=True, height=520)

        # 페이지네이션
        pa, pb, pc, pd_ = st.columns([1, 3, 1, 1])
        if pa.button("◀", key="cv_prev", disabled=page_num <= 1):
            st.session_state.cv_page -= 1
            st.rerun()
        pb.markdown(f"<div style='text-align:center;padding-top:6px;font-size:12px;'>"
                    f"{page_num} / {total_pages} 페이지</div>", unsafe_allow_html=True)
        if pc.button("▶", key="cv_next", disabled=page_num >= total_pages):
            st.session_state.cv_page += 1
            st.rerun()
        pd_.selectbox("페이지 크기", [20, 50, 100], label_visibility="collapsed",
                      index=[20, 50, 100].index(PAGE_SIZE) if PAGE_SIZE in [20, 50, 100] else 0,
                      key="cv_page_size_sel",
                      on_change=lambda: st.session_state.update(
                          cv_page_size=st.session_state.cv_page_size_sel, cv_page=1))


# ══ 탭 2: 이동 신청 현황 ══════════════════════════════════════════════════
with tab_tr:
    if user_role == "manager":
        _ctr = user.get("assigned_center") or user.get("center", "")
        st.info(f"📌 **{_ctr}** 관련 이동 내역만 표시됩니다. **{_ctr}으로 들어오는** 이동 건만 승인할 수 있습니다.")
    elif user_role == "materials":
        st.info("📌 **자재센터** 관련 이동 내역이 표시됩니다.")
    elif user_role == "user":
        st.info("📌 본인이 신청한 이동 내역만 표시됩니다.")

    tr_pending, tr_approved, tr_rejected, tr_all = st.tabs([
        "⏳ 대기중", "✅ 승인됨", "❌ 거절됨", "📋 전체"
    ])

    def _cv_render_transfers(status_filter):
        all_data = fetch_transfers(status_filter)
        data     = filter_transfers_for_user(user, all_data)
        if not data:
            st.info("해당 신청 내역이 없습니다.")
            return
        for tr in data:
            item_info = tr.get("warehouse", {})
            item_name = item_info.get("item_name", "알 수 없음") if isinstance(item_info, dict) else str(item_info)
            user_info = tr.get("requester") or tr.get("users") or {}
            req_name  = user_info.get("name", "알 수 없음") if isinstance(user_info, dict) else str(user_info)
            status    = tr.get("status", "")
            status_label = {
                "pending":   "⏳ 대기중",
                "approved":  "✅ 승인됨",
                "rejected":  "❌ 거절됨",
                "cancelled": "🚫 취소됨",
            }.get(status, status)
            i_can_approve = can_approve_transfer(user, tr.get("from_center",""), tr.get("to_center",""))

            with st.container(border=True):
                c1, c2, c3, c4, c5 = st.columns([3, 2, 2, 1.5, 2])
                c1.markdown(f"**{item_name}**")
                c1.caption(f"신청자: {req_name}")
                c2.write(f"📤 {tr.get('from_center','')}")
                c2.write(f"📥 {tr.get('to_center','')}")
                c3.metric("수량", tr.get("quantity", 0))
                c4.write(status_label)
                with c5:
                    if status == "pending" and i_can_approve:
                        if st.button("✅ 승인", key=f"cv_approve_{status_filter}_{tr['id']}",
                                     type="primary", use_container_width=True):
                            if tr.get("to_center") == "자재센터" and _st_dialog:
                                _iname = item_info.get("item_name","") if isinstance(item_info, dict) else ""
                                _cv_hub_dialog(tr["id"], _iname,
                                               tr.get("from_center",""), tr.get("quantity",0))
                            else:
                                if approve_transfer(tr["id"], user):
                                    st.session_state["_cv_done_msg"] = "✅ 승인 완료!"
                                    clear_transfer_cache()
                                    st.rerun()
                        if st.button("❌ 거절", key=f"cv_reject_{status_filter}_{tr['id']}",
                                     use_container_width=True):
                            sb = get_supabase()
                            sb.table("transfers").update({
                                "status": "rejected", "processed_at": "now()",
                                "approver_id": user_id,
                            }).eq("id", tr["id"]).execute()
                            clear_transfer_cache()
                            st.rerun()
                    elif status == "pending" and tr.get("requester_id") == user_id:
                        if st.button("🚫 취소", key=f"cv_cancel_{status_filter}_{tr['id']}",
                                     use_container_width=True):
                            sb = get_supabase()
                            sb.table("transfers").update({
                                "status": "cancelled", "processed_at": "now()"
                            }).eq("id", tr["id"]).execute()
                            clear_transfer_cache()
                            st.rerun()
                    elif status == "pending":
                        st.caption("🔒 승인 권한 없음")

                req_at  = tr.get("requested_at", "")
                proc_at = tr.get("processed_at")
                if req_at:  st.caption(f"신청일: {req_at[:16].replace('T',' ')}")
                if proc_at: st.caption(f"처리일: {proc_at[:16].replace('T',' ')}")
                if status in ("approved", "rejected"):
                    approver = tr.get("approver") or {}
                    if approver.get("name"):
                        a_ctr = approver.get("assigned_center") or approver.get("center","")
                        st.caption(f"처리자: {approver['name']}" + (f" ({a_ctr})" if a_ctr else ""))

    with tr_pending:
        _cv_render_transfers("pending")
    with tr_approved:
        _cv_render_transfers("approved")
    with tr_rejected:
        _cv_render_transfers("rejected")
    with tr_all:
        _cv_render_transfers(None)
