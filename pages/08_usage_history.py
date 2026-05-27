# pages/08_usage_history.py
import streamlit as st
import pandas as pd
import io
from utils.auth import require_login, is_role, logout
from utils.db import fetch_usage_history, clear_usage_history_cache
from utils.routing import CENTERS
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

user       = st.session_state.user
user_role  = user["role"]
user_name  = user["name"]
user_center = _get_center(user)

if user_role == "guest":
    st.warning("게스트는 사용내역을 조회할 수 없습니다.")
    st.stop()

# ── 사이드바 ──────────────────────────────────────────────────────────────
with st.sidebar:
    render_sidebar_header()
    if st.button("자재현황(전체)", use_container_width=True):
        st.switch_page("pages/10_dashboard.py")
    if st.button("버스단말기 현황", use_container_width=True):
        st.switch_page("pages/14_terminal_dashboard.py")
    if st.button("택시단말기 현황", use_container_width=True):
        st.switch_page("pages/17_taxi_dashboard.py")
    st.divider()

    render_sidebar_section("재고 관리")
    if st.button("📦 재고 현황", use_container_width=True):
        st.switch_page("pages/15_combined.py")
    if st.button("📋 입출고 이력", use_container_width=True):
        st.switch_page("pages/04_history.py")
    st.button("📊 사용내역", use_container_width=True, type="primary")

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
    if st.button("💬 문의하기", use_container_width=True):
        st.switch_page("pages/12_inquiry.py")
    if st.button("👤 마이페이지", use_container_width=True):
        st.switch_page("pages/06_mypage.py")
    if st.button("🚪 로그아웃", use_container_width=True):
        logout()
    render_sidebar_user(user)

# ── 타이틀 ────────────────────────────────────────────────────────────────
render_top_bar("사용내역", user)
st.markdown("## 📋 센터 사용내역")
st.divider()

# ── 필터 ──────────────────────────────────────────────────────────────────
import datetime

fc1, fc2, fc3, fc4, fc5 = st.columns([1.8, 1.2, 1.2, 2, 1])

with fc1:
    if is_role("admin", "materials"):
        selected_center = st.selectbox(
            "센터", ["전체"] + CENTERS,
            label_visibility="collapsed", key="usage_center_sel"
        )
        query_center = None if selected_center == "전체" else selected_center
    else:
        selected_center = user_center or ""
        query_center    = user_center
        st.selectbox(
            "센터", [selected_center] if selected_center else [""],
            label_visibility="collapsed", disabled=True, key="usage_center_sel"
        )

today = datetime.date.today()
with fc2:
    date_from = st.date_input("시작일", value=today - datetime.timedelta(days=30),
                               label_visibility="collapsed")
with fc3:
    date_to = st.date_input("종료일", value=today, label_visibility="collapsed")

with fc4:
    search = st.text_input(
        "검색", placeholder="자재명 / 담당자 / 사유 검색...",
        label_visibility="collapsed"
    )

with fc5:
    limit = st.selectbox("건수", [100, 200, 500, 1000], label_visibility="collapsed")

# 새로고침
rc1, _ = st.columns([1, 7])
if rc1.button("🔄 새로고침", use_container_width=True):
    clear_usage_history_cache()
    st.rerun()

# ── 데이터 로드 ───────────────────────────────────────────────────────────
raw = fetch_usage_history(center=query_center, limit=limit)

if not raw:
    st.info("사용내역이 없습니다.")
    st.stop()

# ── 가공 ──────────────────────────────────────────────────────────────────
rows = []
for h in raw:
    item_info  = h.get("warehouse") or {}
    actor_info = h.get("users")    or {}
    center_val = (
        h.get("from_center")
        or (item_info.get("location") if isinstance(item_info, dict) else "")
        or ""
    )
    rows.append({
        "일시":    (h.get("acted_at","") or "")[:16].replace("T"," "),
        "센터":    center_val,
        "담당자":  actor_info.get("name","") if isinstance(actor_info, dict) else "",
        "자재명":  item_info.get("item_name","") if isinstance(item_info, dict) else "",
        "사용수량": h.get("quantity", 0),
        "변경전":  h.get("snapshot_qty_before", ""),
        "변경후":  h.get("snapshot_qty_after", ""),
        "사유":    h.get("reason", ""),
    })

df = pd.DataFrame(rows)

# 기간 필터
df["_date"] = pd.to_datetime(df["일시"], errors="coerce").dt.date
df = df[
    (df["_date"] >= date_from) &
    (df["_date"] <= date_to)
].drop(columns=["_date"])

# 검색 필터
if search:
    mask = (
        df["자재명"].str.contains(search, case=False, na=False) |
        df["담당자"].str.contains(search, case=False, na=False) |
        df["사유"].str.contains(search,  case=False, na=False)
    )
    df = df[mask]

st.caption(f"총 {len(df)}건")

# ── 테이블 ────────────────────────────────────────────────────────────────
st.dataframe(
    df,
    use_container_width=True,
    hide_index=True,
    height=min(max(len(df) * 35 + 40, 200), 620),
    column_config={
        "일시":     st.column_config.TextColumn("일시",     width=130),
        "센터":     st.column_config.TextColumn("센터",     width=90),
        "담당자":   st.column_config.TextColumn("담당자",   width=80),
        "자재명":   st.column_config.TextColumn("자재명",   width=200),
        "사용수량": st.column_config.NumberColumn("사용수량", width=80),
        "변경전":   st.column_config.NumberColumn("변경전",  width=70),
        "변경후":   st.column_config.NumberColumn("변경후",  width=70),
        "사유":     st.column_config.TextColumn("사유",     width=220),
    }
)

# ── 엑셀 다운로드 ─────────────────────────────────────────────────────────
buf = io.BytesIO()
with pd.ExcelWriter(buf, engine="openpyxl") as writer:
    df.to_excel(writer, index=False, sheet_name="사용내역")
buf.seek(0)

fname = f"{selected_center or user_center}_사용내역.xlsx"
st.download_button(
    "⬇️ 사용내역 엑셀 다운로드", data=buf,
    file_name=fname,
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    use_container_width=True,
)

