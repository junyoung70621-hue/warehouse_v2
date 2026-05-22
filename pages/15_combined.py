# pages/15_combined.py  — 재고 현황 + 이동 신청 통합 뷰
import streamlit as st
import pandas as pd
import io
import re
from utils.auth import require_login, is_role, logout
from utils.db import (
    fetch_warehouse, fetch_categories, fetch_transfers,
    approve_transfer, create_transfer, stock_in, stock_out,
    clear_warehouse_cache, clear_transfer_cache, clear_history_cache,
    get_supabase, fetch_item_history, update_item, submit_material_request,
)
from utils.routing import get_allowed_destinations, NO_WAREHOUSE_CENTERS, CATEGORY_DESTINATIONS, CENTERS as _ALL_CENTERS_ROUTING
from utils.rack_map import RACK_COORD
from utils.permissions import (
    can_stock_in_out, can_request_transfer,
    can_approve_transfer, filter_transfers_for_user,
    get_viewable_centers, get_center as _get_center,
)
from utils.ui import (
    apply_global_css, render_sidebar_header,
    render_sidebar_section, render_sidebar_user, render_top_bar,
)
from utils.uploads import (
    EXCEL_COL_MAP, USAGE_COL_MAP,
    make_excel_buffer, make_usage_template_buffer,
    clean_records, validate_upload, process_usage_upload,
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
    "cv_page": 1, "cv_page_size": 20, "cv_kpi_filter": None,
    "_cv_detail_item": None,
    "cv_tr_cat": "전체", "cv_tr_cart": [],
    "cv_in_cart": [], "cv_out_cart": [],
    "cv_in_reason_mode": "통합", "cv_out_reason_mode": "통합",
    "cv_mat_req_cart": [],
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
    @_st_dialog("⬆️ 엑셀 업로드", width="large")
    def _cv_upload_dialog(center: str, usr_id: str, usr_role: str, usr: dict):
        st.caption("📋 양식을 다운로드한 후 채워서 업로드하세요.")
        sample_buf = make_excel_buffer(
            pd.DataFrame(columns=list(EXCEL_COL_MAP.values())), "양식"
        )
        st.download_button("📋 업로드 양식 다운로드", data=sample_buf,
            file_name="WMS_업로드_양식.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True, key="cv_dlg_sample_dl")
        if usr_role != "admin":
            assigned = usr.get("assigned_center") or usr.get("center", "")
            st.info(f"ℹ️ **{assigned}** 센터 데이터만 업로드 가능합니다.")
        st.divider()
        uploaded = st.file_uploader("파일 선택", type=["xlsx"],
                                    label_visibility="collapsed", key="cv_dlg_upload_file")
        if uploaded:
            try:
                from utils.routing import CENTERS as _CENTERS_UP
                up_df = pd.read_excel(uploaded)
                col_map = {v: k for k, v in EXCEL_COL_MAP.items()}
                col_map["수리담당자명"] = "repair_manager"
                col_map["수리담당자"]   = "repair_manager"
                up_df.rename(columns=col_map, inplace=True)
                if "quantity" in up_df.columns:
                    up_df["quantity"] = pd.to_numeric(up_df["quantity"], errors="coerce").fillna(0).astype(int)
                if "location" not in up_df.columns:
                    up_df["location"] = center
                passed, err_msg = validate_upload(up_df, usr_role, usr, _CENTERS_UP)
                if not passed:
                    st.error(err_msg)
                    return
                total_rows = len(up_df)
                up_df = up_df[up_df["item_name"].notna()]
                up_df = up_df[up_df["item_name"].astype(str).str.strip() != ""]
                removed = total_rows - len(up_df)
                up_df["last_modified_by"] = usr_id
                valid_cols = {"item_name","quantity","rack_no","shelf","box_no",
                              "category_large","category_mid","category_small","location",
                              "erp_name","erp_code","repair_manager","notes","item_location","last_modified_by"}
                up_df   = up_df[[c for c in up_df.columns if c in valid_cols]]
                records = clean_records(up_df.where(pd.notnull(up_df), None).to_dict("records"))
                if removed: st.warning(f"⚠️ 자재명 없는 {removed}개 행 제외")
                qty_empty = sum(1 for r in records if not r.get("quantity"))
                if qty_empty: st.info(f"ℹ️ 수량 미입력 {qty_empty}개 → 수량 0으로 등록")
                st.success(f"✅ 업로드 예정: **{len(records)}개** → **{center}**")
                prev = up_df[[c for c in ["item_name","quantity","category_large","category_mid","location"] if c in up_df.columns]].copy()
                prev.columns = [{"item_name":"자재명","quantity":"수량","category_large":"대분류","category_mid":"중분류","location":"센터"}.get(c,c) for c in prev.columns]
                st.dataframe(prev, use_container_width=True, hide_index=True, height=260)
                st.caption(f"전체 {len(records)}개 항목")
                st.divider()
                ca, cb = st.columns(2)
                if ca.button("✅ 업로드 확정", type="primary", use_container_width=True, key="cv_dlg_confirm_upload"):
                    sb = get_supabase()
                    def _norm2(v): return str(v or "").strip()
                    existing_rows = sb.table("warehouse").select("id,item_name,quantity,rack_no,shelf,box_no,erp_code").eq("location", center).execute().data or []
                    ex_map  = {(_norm2(r.get("rack_no")), _norm2(r.get("shelf")), _norm2(r.get("box_no"))): r for r in existing_rows}
                    ex_erp  = {str(r.get("erp_code") or "").strip(): r for r in existing_rows if (r.get("erp_code") or "").strip()}
                    ex_name = {str(r.get("item_name") or "").strip(): r for r in existing_rows if (r.get("item_name") or "").strip()}
                    to_insert, to_update = [], []
                    for r in records:
                        key = (_norm2(r.get("rack_no")), _norm2(r.get("shelf")), _norm2(r.get("box_no")))
                        add_qty = int(r.get("quantity") or 0)
                        ex = ex_map.get(key) if key != ("","","") else None
                        if ex is None:
                            ec = str(r.get("erp_code") or "").strip()
                            ex = ex_erp.get(ec) if ec else None
                        if ex is None:
                            nm = str(r.get("item_name") or "").strip()
                            ex = ex_name.get(nm) if nm else None
                        if ex:
                            before = int(ex["quantity"] or 0)
                            meta = {k: v for k, v in r.items() if k in ("item_name","erp_code","erp_name","category_large","category_mid","category_small")}
                            to_update.append({"id": ex["id"], "before": before, "add_qty": add_qty, "after": before+add_qty, "meta": meta})
                        else:
                            to_insert.append(r)
                    _CK = 500
                    inserted_recs = []
                    if to_insert:
                        for _i in range(0, len(to_insert), _CK):
                            inserted_recs.extend(sb.table("warehouse").insert(to_insert[_i:_i+_CK]).execute().data or [])
                        hist_ins = [{"actor_id": usr_id, "item_id": rec["id"], "action_type": "in",
                                     "quantity": int(rec.get("quantity") or 0), "reason": "엑셀 업로드 신규 등록",
                                     "from_center": rec.get("location", center),
                                     "snapshot_qty_before": 0, "snapshot_qty_after": int(rec.get("quantity") or 0)}
                                    for rec in inserted_recs if int(rec.get("quantity") or 0) > 0]
                        for _i in range(0, len(hist_ins), _CK):
                            sb.table("history").insert(hist_ins[_i:_i+_CK]).execute()
                    hist_upd = []
                    for upd in to_update:
                        sb.table("warehouse").update({**upd["meta"], "quantity": upd["after"], "last_modified_by": usr_id, "last_modified_at": "now()"}).eq("id", upd["id"]).execute()
                        if upd["add_qty"] > 0:
                            hist_upd.append({"actor_id": usr_id, "item_id": upd["id"], "action_type": "in", "quantity": upd["add_qty"],
                                             "reason": "엑셀 업로드 입고", "from_center": center, "snapshot_qty_before": upd["before"], "snapshot_qty_after": upd["after"]})
                    for _i in range(0, len(hist_upd), _CK):
                        sb.table("history").insert(hist_upd[_i:_i+_CK]).execute()
                    clear_warehouse_cache(); clear_history_cache()
                    st.session_state["_cv_done_msg"] = f"🎉 {len(inserted_recs)+len(to_update)}개 자재 업로드 완료!"
                    st.rerun()
                if cb.button("❌ 취소", use_container_width=True, key="cv_dlg_cancel_upload"):
                    st.rerun()
            except Exception as e:
                st.error(f"업로드 오류: {e}")

    @_st_dialog("📋 사용내역 업로드", width="large")
    def _cv_usage_upload_dialog(center: str, usr_id: str, usr: dict, df_template):
        st.caption("재고목록을 다운로드한 후 **사용수량** 열에 수량을 입력하세요. 수량이 있는 행만 차감됩니다.")
        _dl = df_template[["item_name","erp_code"]].copy() if not df_template.empty \
              else pd.DataFrame(columns=["item_name","erp_code"])
        _dl = _dl.sort_values("item_name", ignore_index=True)
        _dl.rename(columns={"item_name":"자재명","erp_code":"ERP코드"}, inplace=True)
        _dl["사용수량"] = ""; _dl["사용사유"] = ""
        st.download_button("⬇️ 재고목록 다운로드 (수량 입력용)",
            data=make_usage_template_buffer(_dl, center),
            file_name=f"{center}_사용내역_양식.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True, key="cv_dlg_usage_dl")
        st.divider()
        usage_file = st.file_uploader("파일 선택", type=["xlsx"],
                                      label_visibility="collapsed", key="cv_dlg_usage_file")
        if usage_file:
            try:
                u_df = pd.read_excel(usage_file)
                u_df.rename(columns={v: k for k, v in USAGE_COL_MAP.items()}, inplace=True)
                if "quantity" in u_df.columns:
                    u_df["quantity"] = pd.to_numeric(u_df["quantity"], errors="coerce").fillna(0).astype(int)
                u_df = u_df[u_df.get("item_name", pd.Series(dtype=str)).notna() |
                            u_df.get("erp_code",  pd.Series(dtype=str)).notna()]
                u_df = u_df[u_df.get("quantity", pd.Series(dtype=int)).fillna(0) > 0]
                if u_df.empty:
                    st.warning("처리할 유효한 행이 없습니다.")
                    return
                records = clean_records(u_df.where(pd.notnull(u_df), None).to_dict("records"))
                st.success(f"✅ 처리 예정: **{len(records)}개** → **{center}** 재고에서 차감")
                prev = u_df[[c for c in ["item_name","erp_code","quantity","reason"] if c in u_df.columns]].copy()
                prev.columns = [USAGE_COL_MAP.get(c, c) for c in prev.columns]
                st.dataframe(prev, use_container_width=True, hide_index=True, height=260)
                st.caption(f"전체 {len(records)}개 항목")
                st.divider()
                ca, cb = st.columns(2)
                if ca.button("✅ 차감 확정", type="primary", use_container_width=True, key="cv_dlg_confirm_usage"):
                    ok, not_found, insufficient = process_usage_upload(records, center, usr)
                    parts = [f"✅ {ok}개 차감 완료"]
                    if not_found:    parts.append(f"⚠️ 미발견 {len(not_found)}개: {', '.join(not_found[:3])}{'...' if len(not_found)>3 else ''}")
                    if insufficient: parts.append(f"⚠️ 재고부족 {len(insufficient)}개: {', '.join(insufficient[:2])}{'...' if len(insufficient)>2 else ''}")
                    st.session_state["_cv_done_msg"] = " / ".join(parts)
                    st.rerun()
                if cb.button("❌ 취소", use_container_width=True, key="cv_dlg_cancel_usage"):
                    st.rerun()
            except Exception as e:
                st.error(f"파일 처리 오류: {e}")

    def _stock_dialog_body(
        mode_key, cart_key, pick_key, qty_key, add_key,
        action_label, confirm_key, cancel_key, fn_stock, done_msg_prefix,
        all_rows
    ):
        """입고/출고 공용 다이얼로그 본문."""
        cart = st.session_state.get(cart_key, [])

        def _lbl(row):
            qty_v = int(row.get("quantity", 0) or 0)
            rack  = str(row.get("rack_no", "") or "").strip()
            box_v = str(row.get("box_no",  "") or "").strip()
            parts = [f"현재 {qty_v}개"]
            if rack:  parts.append(f"렉 {rack}")
            if box_v: parts.append(f"박스 {box_v}")
            return f"{row['item_name']}  |  {' · '.join(parts)}"

        _id_map = {_lbl(r): int(r["id"]) for r in all_rows if r.get("item_name")}
        _opts   = list(_id_map.keys())

        # ── 항목 추가 행 ──────────────────────────────────────────────────
        _c1, _c2, _c3 = st.columns([5, 1.5, 1.5])
        _pick = _c1.selectbox("자재 선택", [""] + _opts,
                               label_visibility="collapsed", key=pick_key)
        _qty  = _c2.number_input("수량", min_value=1, value=1,
                                  label_visibility="collapsed", key=qty_key)
        if _c3.button("➕ 추가", use_container_width=True,
                      key=add_key, disabled=not _pick):
            _iid = _id_map.get(_pick)
            if _iid and _iid not in [x["item_id"] for x in cart]:
                cart.append({"label": _pick, "item_id": _iid, "qty": int(_qty), "reason": ""})
                st.session_state[cart_key] = cart
            elif _iid:
                st.warning("이미 추가된 항목입니다.")

        # ── 사유 방식 선택 ────────────────────────────────────────────────
        _mode = st.radio("사유 입력 방식", ["통합 사유", "개별 사유"],
                         horizontal=True,
                         index=0 if st.session_state.get(mode_key, "통합") == "통합" else 1,
                         key=f"{mode_key}_radio",
                         label_visibility="collapsed")
        _is_unified = (_mode == "통합 사유")
        if st.session_state.get(mode_key) != ("통합" if _is_unified else "개별"):
            st.session_state[mode_key] = "통합" if _is_unified else "개별"

        # ── 목록 ──────────────────────────────────────────────────────────
        if cart:
            st.markdown(f"**{action_label} 목록**")
            for _ci, _it in enumerate(cart):
                if _is_unified:
                    _lc1, _lc2, _lc3 = st.columns([5, 1.5, 1])
                else:
                    _lc1, _lc2, _lc3, _lc4 = st.columns([3, 1.2, 2.8, 0.8])
                _lc1.markdown(
                    f"<span style='font-size:12px;'>{_it['label']}</span>",
                    unsafe_allow_html=True,
                )
                _nq = _lc2.number_input("수량", min_value=1, value=_it["qty"],
                                         label_visibility="collapsed",
                                         key=f"{cart_key}_qty_{_ci}")
                if _nq != _it["qty"]:
                    cart[_ci]["qty"] = int(_nq)
                    st.session_state[cart_key] = cart
                if not _is_unified:
                    _nr = _lc3.text_input("사유", value=_it.get("reason", ""),
                                          placeholder="사유 입력",
                                          label_visibility="collapsed",
                                          key=f"{cart_key}_reason_{_ci}")
                    if _nr != _it.get("reason", ""):
                        cart[_ci]["reason"] = _nr
                        st.session_state[cart_key] = cart
                    _rm_col = _lc4
                else:
                    _rm_col = _lc3
                if _rm_col.button("✕", key=f"{cart_key}_rm_{_ci}", use_container_width=True):
                    cart.pop(_ci)
                    st.session_state[cart_key] = cart
                    st.rerun()

        st.divider()

        # ── 통합 사유 입력 ─────────────────────────────────────────────────
        _unified_reason = ""
        if _is_unified:
            _unified_reason = st.text_input(
                f"{action_label} 사유 *",
                placeholder="예: 신규 입고, 반납, 재고 조정" if action_label == "입고"
                            else "예: 현장 출고, 이동, 폐기",
                key=f"{cart_key}_unified_reason",
            )

        # ── 확정/취소 ──────────────────────────────────────────────────────
        _sa, _sb2 = st.columns(2)
        if _sa.button(f"✅ {action_label} 확정", type="primary",
                      use_container_width=True, key=confirm_key,
                      disabled=not cart):
            if _is_unified and not _unified_reason.strip():
                st.error(f"{action_label} 사유를 입력해 주세요.")
            elif not _is_unified and any(not _it.get("reason", "").strip() for _it in cart):
                st.error("모든 항목의 사유를 입력해 주세요.")
            else:
                _ok = 0
                for _it in cart:
                    _r = _unified_reason.strip() if _is_unified else _it.get("reason", "").strip()
                    if fn_stock(_it["item_id"], _it["qty"], st.session_state.user, _r):
                        _ok += 1
                if _ok:
                    st.session_state[cart_key] = []
                    st.session_state["_cv_done_msg"] = f"✅ {_ok}개 항목 {action_label} 완료"
                    st.rerun()
        if _sb2.button("❌ 취소", use_container_width=True, key=cancel_key):
            st.session_state[cart_key] = []
            st.rerun()

    @_st_dialog("📥 입고", width="large")
    def _cv_stock_in_dialog(center: str, usr: dict, all_rows: list):
        _stock_dialog_body(
            mode_key="cv_in_reason_mode", cart_key="cv_in_cart",
            pick_key="cv_in_pick", qty_key="cv_in_qty", add_key="cv_in_add",
            action_label="입고", confirm_key="cv_in_confirm", cancel_key="cv_in_cancel",
            fn_stock=stock_in, done_msg_prefix="입고", all_rows=all_rows,
        )

    @_st_dialog("📤 출고", width="large")
    def _cv_stock_out_dialog(center: str, usr: dict, all_rows: list):
        _stock_dialog_body(
            mode_key="cv_out_reason_mode", cart_key="cv_out_cart",
            pick_key="cv_out_pick", qty_key="cv_out_qty", add_key="cv_out_add",
            action_label="출고", confirm_key="cv_out_confirm", cancel_key="cv_out_cancel",
            fn_stock=stock_out, done_msg_prefix="출고", all_rows=all_rows,
        )

    @_st_dialog("📦 자재 요청", width="large")
    def _cv_mat_req_dialog(center: str, usr_id: str, usr_name: str, usr_email: str):
        from utils.mail import send_material_request as _send_req

        _CENTER_CATEGORY_RESTRICT = {
            "강서센터": "버스", "강북센터": "버스",
            "강동센터": "버스", "강남센터": "버스",
            "고속/시외": "버스", "택시지원파트": "택시", "AFC지원파트": "철도",
        }
        _restrict = _CENTER_CATEGORY_RESTRICT.get(center)

        hub_items = fetch_warehouse("자재센터")
        if not hub_items:
            st.warning("자재센터에 등록된 자재가 없습니다.")
            return

        hub_df = pd.DataFrame(hub_items)
        if _restrict and "category_large" in hub_df.columns:
            hub_df = hub_df[hub_df["category_large"] == _restrict]
            st.info(f"ℹ️ **{center}** 는 **{_restrict} 자재**만 요청 가능합니다.")

        # 자재명 기준 수량 합산
        _agg = {"quantity": "sum"}
        for _c in ["category_large", "category_mid", "category_small", "erp_code", "erp_name"]:
            if _c in hub_df.columns:
                _agg[_c] = "first"
        hub_agg = hub_df.groupby("item_name", as_index=False).agg(_agg)

        # 검색
        _ph = (f"{_restrict} 자재명 / 중분류 / ERP코드 검색..."
               if _restrict else "자재명 / 대분류 / 중분류 / ERP코드...")
        _qs = st.text_input("검색", placeholder=_ph,
                            label_visibility="collapsed", key="cv_mr_search")
        _fhub = hub_agg.copy()
        if _qs.strip():
            _cols = (["item_name", "category_mid", "erp_code"] if _restrict
                     else ["item_name", "category_large", "category_mid", "erp_code"])
            _mask = pd.Series([False] * len(_fhub), index=_fhub.index)
            for _c in _cols:
                if _c in _fhub.columns:
                    _mask |= _fhub[_c].fillna("").str.contains(_qs, case=False, na=False)
            _fhub = _fhub[_mask]

        if _fhub.empty:
            st.info("검색 결과가 없습니다.")
        else:
            _opts = {f"{r['item_name']}  (재고: {int(r['quantity'])}개)": r.to_dict()
                     for _, r in _fhub.iterrows()}
            _sel_lbl = st.selectbox("자재 선택", list(_opts.keys()),
                                    label_visibility="collapsed", key="cv_mr_sel")
            _sel_item = _opts[_sel_lbl]
            _rc1, _rc2 = st.columns([1, 3])
            _req_qty = _rc1.number_input("요청수량", min_value=1, step=1,
                                          value=1, key="cv_mr_qty")
            if _rc2.button("🛒 목록에 추가", use_container_width=True, key="cv_mr_add"):
                _cart = st.session_state.cv_mat_req_cart
                _idx  = next((i for i, x in enumerate(_cart)
                               if x["item_name"] == _sel_item["item_name"]), None)
                if _idx is not None:
                    _cart[_idx]["requested_qty"] = _req_qty
                else:
                    _cart.append({
                        "item_name":     _sel_item["item_name"],
                        "erp_code":      _sel_item.get("erp_code") or "",
                        "current_qty":   int(_sel_item["quantity"]),
                        "requested_qty": _req_qty,
                    })
                st.session_state.cv_mat_req_cart = _cart
                st.rerun()

        # 요청 목록
        _cart = st.session_state.cv_mat_req_cart
        if _cart:
            st.divider()
            st.markdown("**요청 목록**")
            _rows = [{"자재명": x["item_name"], "현재재고": x["current_qty"],
                      "요청수량": x["requested_qty"],
                      "재고상태": "⚠️ 재고부족" if x["current_qty"] < x["requested_qty"] else "✅ 충분"}
                     for x in _cart]
            st.dataframe(pd.DataFrame(_rows), use_container_width=True, hide_index=True)

            _notes = st.text_area("비고 (선택)", placeholder="담당자에게 전달할 내용을 입력하세요.",
                                  height=72, key="cv_mr_notes")

            _b1, _b2, _b3 = st.columns([2, 1, 1])
            if _b1.button("📨 요청 발송", type="primary",
                          use_container_width=True, key="cv_mr_send"):
                _sb = get_supabase()
                _mat_emails = list({
                    u["email"]
                    for _res in (
                        _sb.table("users").select("email,assigned_center").eq("role","materials").eq("is_approved",True).execute(),
                        _sb.table("users").select("email,assigned_center").eq("role","admin").eq("is_approved",True).execute(),
                    )
                    for u in (_res.data or [])
                    if u.get("email") and u.get("assigned_center") != "고객지원사업부"
                })
                if not _mat_emails:
                    st.error("자재파트 담당자 이메일을 찾을 수 없습니다.")
                else:
                    try:
                        submit_material_request(
                            requester_id=usr_id, requester_name=usr_name,
                            requester_email=usr_email, from_center=center,
                            items=_cart, notes=_notes,
                        )
                        _send_req(_mat_emails, center, usr_name, _cart, notes=_notes)
                        st.session_state.cv_mat_req_cart = []
                        st.session_state["_cv_done_msg"] = "📨 자재 요청이 발송되었습니다."
                        st.rerun()
                    except Exception as _e:
                        st.error(f"발송 오류: {_e}")

            if _b2.button("🗑️ 초기화", use_container_width=True, key="cv_mr_clear"):
                st.session_state.cv_mat_req_cart = []
                st.rerun()
            if _b3.button("✖️ 닫기", use_container_width=True, key="cv_mr_close"):
                st.session_state.cv_mat_req_cart = []
                st.rerun()

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

    @_st_dialog("자재 상세 정보", width="large")
    def _cv_item_detail_modal(item_id: int, item_name: str, item_loc: str):
        _user   = st.session_state.user
        _role   = _user.get("role", "guest")
        _center = _get_center(_user)
        can_edit = (_role == "admin")
        can_view = (
            can_edit or
            (item_loc == _center) or
            (_center == "자재센터" and _role != "guest")
        )
        if not can_view:
            st.error("🔒 이 자재의 이력을 볼 권한이 없습니다. (본인 센터 자재만 조회 가능)")
            return
        st.markdown(
            f"<span style='font-size:15px;font-weight:700;'>{item_name}</span>"
            f"<span style='font-size:12px;color:#666;margin-left:8px;'>· {item_loc}</span>",
            unsafe_allow_html=True,
        )
        st.divider()

        _pre     = get_supabase().table("warehouse").select("rack_no").eq("id", item_id).execute().data
        _rack_no = str((_pre[0].get("rack_no") or "") if _pre else "").strip()
        _show_map = (item_loc == "자재센터") and (_rack_no in RACK_COORD) and (_role in ("admin", "materials"))

        _tab_labels = ["🔍 이력 조회"]
        if _show_map:
            _tab_labels.append("📍 위치 보기")
        if can_edit:
            _tab_labels.append("✏️ 자재 수정")
            _tab_labels.append("🗑️ 삭제")

        if not can_edit:
            st.caption("ℹ️ 이력 조회만 가능합니다. 수정은 관리자에게 문의하세요.")

        _dtabs = st.tabs(_tab_labels)
        _tidx  = 0
        tab_hist = _dtabs[_tidx]; _tidx += 1
        if _show_map:
            tab_map = _dtabs[_tidx]; _tidx += 1
        if can_edit:
            tab_edit = _dtabs[_tidx]; _tidx += 1
            tab_del  = _dtabs[_tidx]

        with tab_hist:
            hist = fetch_item_history(item_id, limit=50)
            if not hist:
                st.info("이력이 없습니다.")
            else:
                ACTION_LABEL = {"in": "📥 입고", "out": "📤 출고",
                                "transfer": "🚚 이동", "edit": "✏️ 수정"}
                h_rows = []
                for h in hist:
                    actor = h.get("users", {}) or {}
                    h_rows.append({
                        "일시":     (h.get("acted_at", "") or "")[:16].replace("T", " "),
                        "작업자":   actor.get("name", "") if isinstance(actor, dict) else "",
                        "작업유형": ACTION_LABEL.get(h.get("action_type", ""), h.get("action_type", "")),
                        "수량":     h.get("quantity", 0),
                        "변경전":   h.get("snapshot_qty_before", ""),
                        "변경후":   h.get("snapshot_qty_after", ""),
                        "사유":     h.get("reason", ""),
                    })
                st.dataframe(
                    pd.DataFrame(h_rows),
                    use_container_width=True, hide_index=True,
                    column_config={
                        "일시":     st.column_config.TextColumn("일시",     width=120),
                        "작업자":   st.column_config.TextColumn("작업자",   width=80),
                        "작업유형": st.column_config.TextColumn("작업유형", width=80),
                        "수량":     st.column_config.NumberColumn("수량",   width=60),
                        "변경전":   st.column_config.NumberColumn("변경전", width=60),
                        "변경후":   st.column_config.NumberColumn("변경후", width=60),
                        "사유":     st.column_config.TextColumn("사유",     width=230),
                    },
                )

        if _show_map:
            with tab_map:
                st.markdown(
                    f"<div style='font-size:14px;margin-bottom:8px;'>"
                    f"📍 <b>랙번호:</b> <code>{_rack_no}</code></div>",
                    unsafe_allow_html=True,
                )
                st.caption("전체 지도에서 정확한 위치를 확인하세요.")
                if st.button("🗺️ 전체 지도에서 보기", key=f"cv_map_goto_{item_id}",
                             type="primary", use_container_width=True):
                    st.session_state.map_rack_no   = _rack_no
                    st.session_state.map_item_name = item_name
                    st.switch_page("pages/09_rack_map.py")

        if can_edit:
            with tab_edit:
                _sb2     = get_supabase()
                row_data = _sb2.table("warehouse").select("*").eq("id", item_id).single().execute().data
                if not row_data:
                    st.error("자재 정보를 불러올 수 없습니다.")
                    return
                cat_raw  = _sb2.table("warehouse").select(
                    "category_large,category_mid,category_small"
                ).execute().data or []

                NONE_OPT = "(없음)"; NEW_OPT = "+ 직접 입력"
                all_lg   = sorted({r["category_large"] for r in cat_raw if r.get("category_large")})
                mid_by_lg, sm_by_md = {}, {}
                for r in cat_raw:
                    lg, md, sm = r.get("category_large",""), r.get("category_mid","") or "", r.get("category_small","") or ""
                    if lg and md: mid_by_lg.setdefault(lg, set()).add(md)
                    if sm:        sm_by_md.setdefault((lg, md), set()).add(sm)

                pfx     = f"cv_ei_{item_id}"
                _cur_lg = str(row_data.get("category_large", "") or "")
                _cur_md = str(row_data.get("category_mid",   "") or "")
                _cur_sm = str(row_data.get("category_small", "") or "")

                r1c1, r1c2, r1c3 = st.columns([3, 1, 2])
                new_name = r1c1.text_input("자재명 *",  value=str(row_data.get("item_name","") or ""),  key=f"{pfx}_name")
                new_qty  = r1c2.number_input("수량 *",  min_value=0, step=1, value=int(row_data.get("quantity", 0)), key=f"{pfx}_qty")
                _cur_loc2 = str(row_data.get("location", _ALL_CENTERS_ROUTING[0]))
                new_loc  = r1c3.selectbox("센터 *", _ALL_CENTERS_ROUTING,
                                          index=_ALL_CENTERS_ROUTING.index(_cur_loc2) if _cur_loc2 in _ALL_CENTERS_ROUTING else 0,
                                          key=f"{pfx}_loc")

                ec1, ec2, ec3 = st.columns(3)
                lg_opts = [NONE_OPT] + all_lg + [NEW_OPT]
                sel_lg  = ec1.selectbox("대분류", lg_opts,
                                        index=lg_opts.index(_cur_lg) if _cur_lg in lg_opts else 0,
                                        key=f"{pfx}_lg")
                if sel_lg == NEW_OPT:
                    final_lg = ec1.text_input("새 대분류명", key=f"{pfx}_lg_new",
                                              label_visibility="collapsed", placeholder="새 대분류명 입력").strip() or None
                else:
                    final_lg = sel_lg if sel_lg != NONE_OPT else None

                avail_md = sorted(mid_by_lg.get(final_lg or "", set()))
                md_opts  = [NONE_OPT] + avail_md + [NEW_OPT]
                sel_md   = ec2.selectbox("중분류", md_opts,
                                         index=md_opts.index(_cur_md) if _cur_md in md_opts else 0,
                                         key=f"{pfx}_md")
                if sel_md == NEW_OPT:
                    final_md = ec2.text_input("새 중분류명", key=f"{pfx}_md_new",
                                              label_visibility="collapsed", placeholder="새 중분류명 입력").strip() or None
                else:
                    final_md = sel_md if sel_md != NONE_OPT else None

                avail_sm = sorted(sm_by_md.get((final_lg or "", final_md or ""), set()))
                sm_opts  = [NONE_OPT] + avail_sm + [NEW_OPT]
                sel_sm   = ec3.selectbox("소분류", sm_opts,
                                         index=sm_opts.index(_cur_sm) if _cur_sm in sm_opts else 0,
                                         key=f"{pfx}_sm")
                if sel_sm == NEW_OPT:
                    final_sm = ec3.text_input("새 소분류명", key=f"{pfx}_sm_new",
                                              label_visibility="collapsed", placeholder="새 소분류명 입력").strip() or None
                else:
                    final_sm = sel_sm if sel_sm != NONE_OPT else None

                r3c1, r3c2, r3c3 = st.columns(3)
                new_rack  = r3c1.text_input("랙번호",   value=str(row_data.get("rack_no","") or ""),   key=f"{pfx}_rack")
                new_shelf = r3c2.text_input("단",       value=str(row_data.get("shelf","")  or ""),    key=f"{pfx}_shelf")
                new_box   = r3c3.text_input("박스번호", value=str(row_data.get("box_no","") or ""),    key=f"{pfx}_box")

                r4c1, r4c2 = st.columns(2)
                new_erp_n  = r4c1.text_input("ERP품명", value=str(row_data.get("erp_name","") or ""), key=f"{pfx}_erpn")
                new_erp_c  = r4c2.text_input("ERP코드", value=str(row_data.get("erp_code","") or ""), key=f"{pfx}_erpc")

                r5c1, r5c2 = st.columns(2)
                new_repair = r5c1.text_input("수리담당자",   value=str(row_data.get("repair_manager","") or ""), key=f"{pfx}_repair")
                new_i_loc  = r5c2.text_input("지역(사용처)", value=str(row_data.get("item_location","")  or ""), key=f"{pfx}_iloc")
                new_notes  = st.text_area("비고", value=str(row_data.get("notes","") or ""), height=60, key=f"{pfx}_notes")
                edit_reason = st.text_input("✏️ 수정 사유 * (필수)",
                                            placeholder="예: 오입력 수정, 정기 재고 조정",
                                            key=f"{pfx}_reason")

                if st.button("💾 저장", type="primary", use_container_width=True, key=f"{pfx}_save"):
                    if not new_name.strip():
                        st.error("자재명은 필수입니다.")
                    elif not edit_reason.strip():
                        st.error("⚠️ 수정 사유를 반드시 입력해야 합니다.")
                    else:
                        updates = {
                            "item_name": new_name.strip(), "quantity": new_qty,
                            "location": new_loc, "category_large": final_lg,
                            "category_mid": final_md, "category_small": final_sm,
                            "rack_no": new_rack or None, "shelf": new_shelf or None,
                            "box_no": new_box or None, "erp_name": new_erp_n or None,
                            "erp_code": new_erp_c or None, "repair_manager": new_repair or None,
                            "item_location": new_i_loc or None, "notes": new_notes or None,
                        }
                        if update_item(item_id, updates, _user, edit_reason):
                            st.success("✅ 자재 정보가 수정됐습니다!")
                            st.rerun()

            with tab_del:
                st.warning(
                    f"⚠️ **{item_name}** 을(를) 영구 삭제합니다.\n\n"
                    "삭제 후 복구할 수 없으며, 관련 이동·이력 기록은 보존됩니다."
                )
                del_confirm = st.checkbox(f'"{item_name}" 삭제에 동의합니다', key=f"cv_del_chk_{item_id}")
                if st.button("🗑️ 삭제 실행", type="primary", use_container_width=True,
                             disabled=not del_confirm, key=f"cv_del_exec_{item_id}"):
                    _sb3 = get_supabase()
                    _qty_res = _sb3.table("warehouse").select("quantity").eq("id", item_id).execute()
                    _qty_v   = int(_qty_res.data[0]["quantity"]) if _qty_res.data else 0
                    if _qty_v > 0:
                        try:
                            _sb3.table("history").insert({
                                "actor_id": _user["id"], "item_id": item_id,
                                "action_type": "out", "quantity": _qty_v,
                                "reason": "관리자 삭제", "from_center": item_loc,
                                "snapshot_qty_before": _qty_v, "snapshot_qty_after": 0,
                            }).execute()
                        except Exception:
                            pass
                    _sb3.table("warehouse").delete().eq("id", item_id).execute()
                    clear_warehouse_cache(); clear_history_cache()
                    st.success(f"✅ '{item_name}' 삭제 완료")
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
_tab_list = ["📦 재고 현황", "🚚 이동 신청 현황"]
if user_role == "admin":
    _tab_list.append("⚙️ 관리자")
_tabs = st.tabs(_tab_list)
tab_wh = _tabs[0]
tab_tr = _tabs[1]
tab_admin = _tabs[2] if user_role == "admin" else None


# ══ 탭 1: 재고 현황 ════════════════════════════════════════════════════════
with tab_wh:
    IS_HUB   = selected_center == "자재센터"
    CAN_TRANSFER_WH = can_request_transfer(user, selected_center)

    # ── 데이터 로드 ─────────────────────────────────────────────────────
    raw_data   = fetch_warehouse(selected_center)
    categories = fetch_categories()
    df_all     = pd.DataFrame(raw_data) if raw_data else pd.DataFrame()

    # ── KPI 카드 ─────────────────────────────────────────────────────────
    if not df_all.empty:
        _q_s     = df_all["quantity"].fillna(0).astype(int)
        _kv_all  = len(df_all)
        _kv_low  = int(_q_s.between(1, 9).sum())
        _kv_zero = int((_q_s == 0).sum())
        _tr_pending   = fetch_transfers("pending")
        _tr_center    = [t for t in _tr_pending
                         if t.get("from_center") == selected_center
                         or t.get("to_center")   == selected_center]
        _tr_pending_cnt = len(_tr_center)
        _tr_item_ids  = {t["item_id"] for t in _tr_center if t.get("item_id")}
        _kpi_specs = [
            (None,      "📦 전체 품목",       _kv_all,         "#4A9EFF"),
            ("low",     "⚠️ 재고 부족 (1~9)", _kv_low,          "#FFAA00"),
            ("zero",    "🚨 재고 없음",        _kv_zero,         "#FF4444"),
            ("transit", "🚚 이동 중 (대기)",   _tr_pending_cnt,  "#6C757D"),
        ]
        _kf_now = st.session_state.get("cv_kpi_filter")
        _kms    = st.columns(4)
        for _ki, (_fv, _lbl, _cnt, _clr) in enumerate(_kpi_specs):
            _active = (_kf_now == _fv) and (_fv is not None)
            _brd    = f"2px solid {_clr}" if _active else f"1px solid {_clr}55"
            _bg     = f"{_clr}22"          if _active else f"{_clr}11"
            _kms[_ki].markdown(
                f"<div style='padding:10px 14px;border-radius:8px;background:{_bg};"
                f"border:{_brd};text-align:center;margin-bottom:4px;'>"
                f"<div style='font-size:11px;color:#aaa;'>{_lbl}</div>"
                f"<div style='font-size:24px;font-weight:700;color:{_clr};'>{_cnt:,}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )
            if _fv is not None:
                if _kms[_ki].button(
                    "필터 해제" if _active else "필터",
                    key=f"cv_kpi_btn_{_fv}",
                    use_container_width=True,
                ):
                    st.session_state.cv_kpi_filter = None if _active else _fv
                    st.session_state.cv_page = 1
                    st.rerun()
        _kpi_labels = {"low": "재고 부족 (1~9)", "zero": "재고 없음", "transit": "이동 중 (대기)"}
        if _kf_now in _kpi_labels:
            st.caption(f"📌 KPI 필터 적용 중 — {_kpi_labels[_kf_now]}")
        st.divider()

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
    fc[0].caption("자재 검색")
    search = fc[0].text_input("검색", placeholder="자재명 / ERP코드 / 분류명 검색...",
                              label_visibility="collapsed", key="cv_search")

    fc[1].caption("대분류")
    new_lg = fc[1].selectbox("대분류", large_cats,
                              index=large_cats.index(_sl) if _sl in large_cats else 0,
                              label_visibility="collapsed", key="cv_filter_lg")
    if new_lg != _sl:
        st.session_state.cv_large = new_lg
        st.session_state.cv_mid   = "전체"
        st.session_state.cv_small = "전체"
        st.session_state.cv_page  = 1
        st.rerun()

    fc[2].caption("중분류")
    _cur_mid = _sm if _sm in mid_cats else "전체"
    new_md   = fc[2].selectbox("중분류", mid_cats, index=mid_cats.index(_cur_mid),
                                label_visibility="collapsed", key="cv_filter_md")
    if new_md != _sm:
        st.session_state.cv_mid   = new_md
        st.session_state.cv_small = "전체"
        st.session_state.cv_page  = 1
        st.rerun()

    fc[3].caption("소분류")
    _cur_sm = st.session_state.get("cv_small", "전체")
    _cur_sm = _cur_sm if _cur_sm in small_cats else "전체"
    new_sm  = fc[3].selectbox("소분류", small_cats, index=small_cats.index(_cur_sm),
                               label_visibility="collapsed", key="cv_filter_sm")
    if new_sm != _cur_sm:
        st.session_state.cv_small = new_sm
        st.session_state.cv_page  = 1
        st.rerun()

    fc[4].markdown('<div style="height:2.2rem"></div>', unsafe_allow_html=True)
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
        # KPI 필터 적용
        _kf_active = st.session_state.get("cv_kpi_filter")
        if _kf_active == "low":
            filtered = filtered[filtered["quantity"].fillna(0).astype(int).between(1, 9)]
        elif _kf_active == "zero":
            filtered = filtered[filtered["quantity"].fillna(0).astype(int) == 0]
        elif _kf_active == "transit":
            filtered = filtered[filtered["id"].isin(_tr_item_ids)]
    else:
        filtered = pd.DataFrame()

    # ── 권한 계산 ────────────────────────────────────────────────────────
    total            = len(filtered)
    CAN_STOCK_WH     = can_stock_in_out(user, selected_center)
    SHOW_STOCK_BTNS  = CAN_STOCK_WH and IS_HUB
    CAN_USAGE_UP     = (not IS_HUB and
                        (user_role == "admin" or
                         (user_role == "manager" and my_center == selected_center)))
    CAN_MAT_REQ      = (not IS_HUB and user_role not in ("guest", "materials"))

    st.caption(f"**{selected_center}** — 총 {total:,}개 품목" +
               (f"  (검색: {search})" if search else ""))

    # ── 액션 바 ──────────────────────────────────────────────────────────
    def _cv_excel(df, sheet="Sheet1"):
        safe = re.sub(r'[\\/*?:\[\]]', '_', sheet)[:31] or "Sheet1"
        buf  = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name=safe)
        buf.seek(0)
        return buf

    _COLS = {"item_name":"자재명","quantity":"수량","rack_no":"렉번호",
             "category_large":"대분류","category_mid":"중분류","category_small":"소분류",
             "erp_code":"ERP코드","location":"자재위치"}

    _ab = st.columns(6)
    _bi = 0

    # 업로드 (admin/materials + 자재센터)
    if user_role in ("admin", "materials") and IS_HUB and _st_dialog:
        if _ab[_bi].button("⬆️ 업로드", use_container_width=True, key="cv_ab_upload"):
            _cv_upload_dialog(selected_center, user_id, user_role, user)
        _bi += 1

    # 다운로드 (비게스트)
    if user_role != "guest" and not df_all.empty:
        _dl = df_all[[c for c in _COLS if c in df_all.columns]].copy().rename(columns=_COLS)
        _ab[_bi].download_button("⬇️ 다운로드", data=_cv_excel(_dl, selected_center),
            file_name=f"{selected_center}_재고현황.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True)
        _bi += 1

    # 입고 / 출고 (자재센터 + CAN_STOCK)
    if SHOW_STOCK_BTNS and _st_dialog:
        if _ab[_bi].button("📥 입고", use_container_width=True, key="cv_ab_in"):
            _cv_stock_in_dialog(selected_center, user, raw_data)
        _bi += 1
        if _ab[_bi].button("📤 출고", use_container_width=True, key="cv_ab_out"):
            _cv_stock_out_dialog(selected_center, user, raw_data)
        _bi += 1

    # 사용내역 (비자재센터 + admin/manager)
    if CAN_USAGE_UP and _st_dialog:
        if _ab[_bi].button("📋 사용내역", use_container_width=True, key="cv_ab_usage"):
            _cv_usage_upload_dialog(selected_center, user_id, user, df_all)
        _bi += 1

    # 자재 요청 (비자재센터 + 권한 있는 역할)
    if CAN_MAT_REQ and _st_dialog:
        if _ab[_bi % 6].button("📦 자재 요청", use_container_width=True, key="cv_ab_matreq"):
            _cv_mat_req_dialog(
                selected_center, user_id, user_name,
                user.get("email", ""),
            )

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
                        st.session_state.cv_tr_cart = []

                # 선택된 카테고리로 항목 필터링
                _tr_filtered = filtered.copy()
                if st.session_state.cv_tr_cat != "전체" and "category_large" in _tr_filtered.columns:
                    _tr_filtered = _tr_filtered[_tr_filtered["category_large"] == st.session_state.cv_tr_cat]

                # 라벨: 자재명  |  수량 N  렉 A1  박스 3
                def _tr_label(row):
                    qty_v = int(row.get("quantity", 0) or 0)
                    rack  = str(row.get("rack_no", "") or "").strip()
                    box_v = str(row.get("box_no",  "") or "").strip()
                    parts = [f"수량 {qty_v}"]
                    if rack:  parts.append(f"렉 {rack}")
                    if box_v: parts.append(f"박스 {box_v}")
                    return f"{row['item_name']}  |  {' · '.join(parts)}"

                _label_to_id = {}
                _label_opts  = []
                for _, _row in _tr_filtered.iterrows():
                    _lbl = _tr_label(_row)
                    _label_to_id[_lbl] = int(_row["id"])
                    _label_opts.append(_lbl)

                # ── 항목 추가 행 ───────────────────────────────────────
                _c1, _c2, _c3 = st.columns([5, 1.5, 1.5])
                _pick = _c1.selectbox(
                    "자재 선택", [""] + _label_opts,
                    label_visibility="collapsed", key="cv_tr_pick"
                )
                _pick_qty = _c2.number_input(
                    "수량", min_value=1, value=1,
                    label_visibility="collapsed", key="cv_tr_pick_qty"
                )
                if _c3.button("➕ 항목 추가", use_container_width=True,
                              key="cv_tr_add", disabled=not _pick):
                    if _pick in _label_to_id:
                        _existing_ids = [x["item_id"] for x in st.session_state.cv_tr_cart]
                        _new_id = _label_to_id[_pick]
                        if _new_id in _existing_ids:
                            st.warning("이미 추가된 항목입니다.")
                        else:
                            st.session_state.cv_tr_cart.append({
                                "label":   _pick,
                                "item_id": _new_id,
                                "qty":     int(_pick_qty),
                            })

                # ── 신청 목록 ──────────────────────────────────────────
                if st.session_state.cv_tr_cart:
                    st.markdown("**신청 목록**")
                    for _ci, _cart_item in enumerate(st.session_state.cv_tr_cart):
                        _lc1, _lc2, _lc3 = st.columns([5, 1.5, 1])
                        _lc1.markdown(
                            f"<span style='font-size:12px;'>{_cart_item['label']}</span>",
                            unsafe_allow_html=True
                        )
                        _new_qty = _lc2.number_input(
                            "수량", min_value=1,
                            value=_cart_item["qty"],
                            label_visibility="collapsed",
                            key=f"cv_cart_qty_{_ci}",
                        )
                        if _new_qty != _cart_item["qty"]:
                            st.session_state.cv_tr_cart[_ci]["qty"] = int(_new_qty)
                        if _lc3.button("✕", key=f"cv_cart_rm_{_ci}",
                                       use_container_width=True):
                            st.session_state.cv_tr_cart.pop(_ci)

                    st.divider()
                    _sa, _sb = st.columns(2)
                    if _sb.button("🗑️ 전체 삭제", use_container_width=True,
                                  key="cv_cart_clear"):
                        st.session_state.cv_tr_cart = []
                    if _sa.button("✅ 이동 신청", type="primary",
                                  use_container_width=True, key="cv_tr_submit"):
                        _ok = 0
                        for _ci in st.session_state.cv_tr_cart:
                            try:
                                create_transfer(_ci["item_id"], selected_center,
                                                dst, _ci["qty"], user_id)
                                _ok += 1
                            except Exception:
                                pass
                        if _ok:
                            st.session_state.cv_tr_cart = []
                            clear_transfer_cache()
                            st.session_state["_cv_done_msg"] = f"✅ {_ok}개 이동 신청 완료 → {dst}"
                            st.rerun()
                else:
                    st.caption("항목을 추가한 뒤 이동 신청하세요.")

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

        # 페이지네이션 (테이블 위)
        st.divider()
        pa, pb, pc, pd_, pe = st.columns([2, 2, 3, 2, 2])
        pa.caption("이전")
        pb.caption("페이지")
        pc.caption(" ")
        pd_.caption("다음")
        pe.caption("개수")
        if pa.button("◀◀" if False else "◀", key="cv_prev", disabled=page_num <= 1,
                     use_container_width=True):
            st.session_state.cv_page -= 1
            st.rerun()
        _page_opts = list(range(1, total_pages + 1))
        _cur_idx   = page_num - 1
        _sel_page  = pb.selectbox("페이지", _page_opts, index=_cur_idx,
                                   label_visibility="collapsed", key="cv_page_sel")
        if _sel_page != page_num:
            st.session_state.cv_page = _sel_page
            st.rerun()
        pc.markdown(
            f"<div style='text-align:center;padding-top:4px;font-size:15px;font-weight:600;'>"
            f"/ {total_pages} 페이지</div>",
            unsafe_allow_html=True,
        )
        if pd_.button("▶", key="cv_next", disabled=page_num >= total_pages,
                      use_container_width=True):
            st.session_state.cv_page += 1
            st.rerun()
        _PAGE_SIZES = [20, 50, 100, 200]
        pe.selectbox("페이지 크기", _PAGE_SIZES, label_visibility="collapsed",
                     index=_PAGE_SIZES.index(PAGE_SIZE) if PAGE_SIZE in _PAGE_SIZES else 0,
                     key="cv_page_size_sel",
                     on_change=lambda: st.session_state.update(
                         cv_page_size=st.session_state.cv_page_size_sel, cv_page=1))
        st.divider()

        # 표시 컬럼 선택 (자재센터는 렉/단/박스 추가)
        if IS_HUB:
            _base_cols = ["item_name", "quantity", "category_large", "category_mid",
                          "category_small", "rack_no", "shelf", "box_no",
                          "item_location", "erp_name", "erp_code"]
        else:
            _base_cols = ["item_name", "quantity", "category_large",
                          "category_mid", "category_small", "rack_no", "erp_code"]
        show_cols = [c for c in _base_cols if c in page_df.columns]
        col_labels = {
            "item_name":      "자재명",
            "quantity":       "수량",
            "category_large": "대분류",
            "category_mid":   "중분류",
            "category_small": "소분류",
            "rack_no":        "렉번호",
            "shelf":          "단",
            "box_no":         "박스",
            "item_location":  "지역",
            "erp_name":       "ERP품명",
            "erp_code":       "ERP코드",
        }
        disp = page_df[show_cols].rename(columns=col_labels)
        st.caption("💡 행을 클릭하면 자재 상세 정보(이력·수정)를 볼 수 있습니다.")
        _tbl_sel = st.dataframe(
            disp, use_container_width=True, hide_index=True, height=500,
            on_select="rerun", selection_mode="single-row",
        )
        if _tbl_sel and _tbl_sel.selection.rows and _st_dialog:
            _sel_idx = _tbl_sel.selection.rows[0]
            _sel_row = page_df.iloc[_sel_idx]
            _cv_item_detail_modal(
                int(_sel_row["id"]),
                str(_sel_row.get("item_name", "")),
                str(_sel_row.get("location", selected_center)),
            )


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


# ══ 탭 3: 관리자 메뉴 ═════════════════════════════════════════════════════
if tab_admin:
    with tab_admin:
        from utils.routing import CENTERS as _ALL_CENTERS

        _EXP_COLS = {"item_name":"자재명","quantity":"수량","rack_no":"렉번호",
                     "shelf":"단","box_no":"박스번호","category_large":"대분류",
                     "category_mid":"중분류","category_small":"소분류",
                     "item_location":"지역","location":"자재위치",
                     "erp_name":"ERP품명","erp_code":"ERP코드",
                     "repair_manager":"수리담당자명","notes":"비고"}

        adm_export, adm_delete = st.tabs(["💾 내보내기", "🗑️ 삭제"])

        # ── 내보내기 ──────────────────────────────────────────────────────
        with adm_export:
            st.markdown("#### 💾 전체 데이터 내보내기")
            _exp_center = st.selectbox(
                "내보낼 센터",
                ["전체 (모든 센터)"] + [c for c in _ALL_CENTERS if c not in NO_WAREHOUSE_CENTERS],
                key="cv_adm_exp_center"
            )
            if _exp_center == "전체 (모든 센터)":
                _exp_raw = []
                for _c in _ALL_CENTERS:
                    _exp_raw.extend(fetch_warehouse(_c))
                _exp_fname, _exp_sheet = "WMS_전체_데이터.xlsx", "전체"
            else:
                _exp_raw   = fetch_warehouse(_exp_center)
                _exp_fname = f"{_exp_center}_전체_데이터.xlsx"
                _exp_sheet = _exp_center

            _exp_df = pd.DataFrame(_exp_raw) if _exp_raw else pd.DataFrame()
            if _exp_df.empty:
                st.warning("내보낼 데이터가 없습니다.")
            else:
                _dl_df = _exp_df[[c for c in _EXP_COLS if c in _exp_df.columns]].copy()
                _dl_df.rename(columns=_EXP_COLS, inplace=True)
                st.info(f"총 **{len(_dl_df)}개** 항목")
                st.download_button(
                    f"⬇️ 다운로드 ({_exp_fname})",
                    data=_cv_excel(_dl_df, _exp_sheet),
                    file_name=_exp_fname,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                )

        # ── 삭제 ──────────────────────────────────────────────────────────
        with adm_delete:
            st.markdown("#### 🗑️ 센터 자재 목록 삭제")
            st.warning("⚠️ 삭제 후 복구할 수 없습니다. 삭제 전 반드시 내보내기로 백업하세요.")
            _del_center = st.selectbox(
                "삭제할 센터",
                [c for c in _ALL_CENTERS if c not in NO_WAREHOUSE_CENTERS],
                key="cv_adm_del_center"
            )
            _del_raw = fetch_warehouse(_del_center)
            _del_df  = pd.DataFrame(_del_raw) if _del_raw else pd.DataFrame()

            if _del_df.empty:
                st.info("해당 센터에 자재 데이터가 없습니다.")
            else:
                # 백업 다운로드
                _bak_df = _del_df[[c for c in _EXP_COLS if c in _del_df.columns]].copy()
                _bak_df.rename(columns=_EXP_COLS, inplace=True)
                _bak_fname = f"{_del_center}_삭제전_백업.xlsx"
                st.download_button(
                    f"⬇️ 삭제 전 백업 ({_bak_fname})",
                    data=_cv_excel(_bak_df, _del_center),
                    file_name=_bak_fname,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                )
                st.info(f"**{_del_center}** — {len(_del_df)}개 항목")

                _del_key = f"cv_del_confirm_{_del_center}"
                if _del_key not in st.session_state:
                    st.session_state[_del_key] = False

                if not st.session_state[_del_key]:
                    if st.button("🗑️ 삭제 실행", type="primary",
                                 use_container_width=True, key="cv_del_exec"):
                        st.session_state[_del_key] = True
                        st.rerun()
                else:
                    st.error(f"**{_del_center}** 자재 목록 전체를 삭제합니다. 정말 진행하시겠습니까?")
                    _dc1, _dc2 = st.columns(2)
                    if _dc1.button("✅ 확인 — 삭제", type="primary",
                                   use_container_width=True, key="cv_del_ok"):
                        _sb2  = get_supabase()
                        _iids = [int(r["id"]) for r in _del_raw]
                        _deleted = 0
                        for _iid in _iids:
                            _qty_r = _sb2.table("warehouse").select("quantity").eq("id", _iid).execute()
                            _qty   = int(_qty_r.data[0]["quantity"]) if _qty_r.data else 0
                            if _qty > 0:
                                try:
                                    _sb2.table("history").insert({
                                        "actor_id": user_id, "item_id": _iid,
                                        "action_type": "out", "quantity": _qty,
                                        "reason": f"관리자 삭제 ({_del_center})",
                                        "snapshot_qty_before": _qty, "snapshot_qty_after": 0,
                                    }).execute()
                                except Exception: pass
                            try:
                                _sb2.table("transfers").update({"item_id": None}).eq("item_id", _iid).execute()
                                _sb2.table("history").update({"item_id": None}).eq("item_id", _iid).execute()
                                _sb2.table("warehouse").delete().eq("id", _iid).execute()
                                _deleted += 1
                            except Exception: pass
                        clear_warehouse_cache()
                        clear_history_cache()
                        st.session_state[_del_key] = False
                        st.session_state["_cv_done_msg"] = f"✅ {_deleted}개 삭제 완료"
                        st.rerun()
                    if _dc2.button("❌ 취소", use_container_width=True, key="cv_del_cancel"):
                        st.session_state[_del_key] = False
                        st.rerun()
