# pages/10_dashboard.py
import streamlit as st
import pandas as pd
from utils.auth import require_login, is_role
from utils.db import fetch_warehouse, get_supabase
from utils.routing import CENTERS
from utils.permissions import get_center as _get_center
from utils.ui import apply_global_css, render_sidebar_header, render_sidebar_section, render_sidebar_user, render_top_bar

st.set_page_config(
    page_title="에이텍모빌리티 자재관리",
    page_icon="favicon_32.png",
    layout="wide",
    initial_sidebar_state="expanded",
)

apply_global_css()
require_login()

user        = st.session_state.user
user_role   = user["role"]
user_center = _get_center(user)

# ── 사이드바 ──────────────────────────────────────────────────────────────
with st.sidebar:
    render_sidebar_header()
    st.button("📊 대시보드(자재)", use_container_width=True, type="primary")
    if is_role("admin"):
        if st.button("📟 대시보드(단말기)", use_container_width=True):
            st.switch_page("pages/14_terminal_dashboard.py")
    st.divider()

    if user_role in ("admin", "materials"):
        centers_opt = ["전체"] + CENTERS
        if st.session_state.get("sidebar_center") not in centers_opt:
            st.session_state.pop("sidebar_center", None)
        selected_center = st.selectbox("센터", centers_opt, label_visibility="collapsed", key="sidebar_center")
    else:
        selected_center = user_center
        st.markdown(
            f"<div style='color:#adb5bd;font-size:13px;padding:4px 8px;'>📌 {user_center}</div>",
            unsafe_allow_html=True,
        )

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
        st.session_state.user = None
        st.switch_page("pages/01_login.py")
    render_sidebar_user(user)

render_top_bar("대시보드(자재)", user)
st.markdown("## 📊 자재 현황 대시보드")
st.divider()

# ── 데이터 로드 ───────────────────────────────────────────────────────────
def _load(center: str) -> pd.DataFrame:
    if center == "전체":
        rows = []
        for c in CENTERS:
            rows.extend(fetch_warehouse(c) or [])
    else:
        rows = fetch_warehouse(center) or []
    return pd.DataFrame(rows) if rows else pd.DataFrame()

df = _load(selected_center)

# ── 새로고침 ──────────────────────────────────────────────────────────────
rc1, _ = st.columns([1, 9])
if rc1.button("🔄 새로고침", use_container_width=True):
    from utils.db import clear_warehouse_cache
    clear_warehouse_cache()
    st.rerun()

# ── KPI 카드 ──────────────────────────────────────────────────────────────
k1, k2, k3, k4 = st.columns(4)

if df.empty:
    total_items = total_qty = out_stock = low_stock = 0
else:
    total_items = len(df)
    total_qty   = int(df["quantity"].sum())
    out_stock   = int((df["quantity"] == 0).sum())
    low_stock   = int(((df["quantity"] > 0) & (df["quantity"] <= 3)).sum())

k1.metric("📦 자재 종류",    f"{total_items:,}개")
k2.metric("🗃️ 총 재고 수량", f"{total_qty:,}개")
k3.metric("❌ 품절 항목",    f"{out_stock}개",
          delta=f"-{out_stock}" if out_stock else "없음",
          delta_color="inverse" if out_stock else "off")
k4.metric("⚠️ 재고 부족",   f"{low_stock}개",
          delta=f"-{low_stock}" if low_stock else "없음",
          delta_color="inverse" if low_stock else "off")

if df.empty:
    st.info("📭 등록된 자재가 없습니다.")
    st.stop()

st.divider()

# ── 분류별 현황 / 센터별 현황 ─────────────────────────────────────────────
left_col, right_col = st.columns([3, 2])

with left_col:
    st.markdown("#### 📋 대분류별 현황")
    cat_df = (
        df.assign(대분류=df["category_large"].fillna("미분류"))
        .groupby("대분류", sort=False)
        .agg(자재수=("item_name", "count"),
             총수량=("quantity", "sum"),
             품절=("quantity", lambda x: (x == 0).sum()))
        .reset_index()
        .sort_values("총수량", ascending=False)
    )
    st.dataframe(
        cat_df, use_container_width=True, hide_index=True,
        height=min(len(cat_df) * 35 + 40, 380),
        column_config={
            "대분류": st.column_config.TextColumn("대분류", width=130),
            "자재수": st.column_config.NumberColumn("자재수", width=70),
            "총수량": st.column_config.NumberColumn("총수량", width=80),
            "품절":   st.column_config.NumberColumn("품절",   width=60),
        },
    )

with right_col:
    if selected_center == "전체":
        st.markdown("#### 🏢 센터별 현황")
        ctr_df = (
            df.assign(센터=df["location"].fillna("미지정"))
            .groupby("센터", sort=False)
            .agg(자재수=("item_name", "count"),
                 총수량=("quantity", "sum"),
                 품절=("quantity", lambda x: (x == 0).sum()))
            .reset_index()
            .sort_values("총수량", ascending=False)
        )
        st.dataframe(
            ctr_df, use_container_width=True, hide_index=True,
            height=min(len(ctr_df) * 35 + 40, 380),
            column_config={
                "센터":   st.column_config.TextColumn("센터",   width=110),
                "자재수": st.column_config.NumberColumn("자재수", width=70),
                "총수량": st.column_config.NumberColumn("총수량", width=80),
                "품절":   st.column_config.NumberColumn("품절",   width=60),
            },
        )
    else:
        st.markdown("#### ❌ 품절 자재 목록")
        oos = (
            df[df["quantity"] == 0][["item_name", "category_large", "category_mid"]]
            .rename(columns={"item_name": "자재명",
                             "category_large": "대분류",
                             "category_mid": "중분류"})
        )
        if oos.empty:
            st.success("✅ 품절 자재 없음")
        else:
            st.dataframe(
                oos, use_container_width=True, hide_index=True,
                height=min(len(oos) * 35 + 40, 380),
            )

st.divider()

# ── 대분류별 재고 수량 차트 ───────────────────────────────────────────────
st.markdown("#### 📊 대분류별 재고 수량")
chart_df = cat_df.set_index("대분류")[["총수량"]].head(15)
st.bar_chart(chart_df, height=280)

st.divider()

# ── 최근 입출고 이력 ──────────────────────────────────────────────────────
st.markdown("#### 📋 최근 입출고 이력 (최근 30건)")
try:
    sb     = get_supabase()
    ACTION = {"in": "📥 입고", "out": "📤 출고",
               "transfer": "🚚 이동", "edit": "✏️ 수정"}
    q = (
        sb.table("history")
        .select("acted_at,action_type,quantity,reason,from_center,"
                "users(name),warehouse(item_name)")
        .order("acted_at", desc=True)
        .limit(30)
    )
    if selected_center != "전체":
        q = q.eq("from_center", selected_center)
    hist_raw = q.execute().data or []

    hist_rows = []
    for h in hist_raw:
        actor = h.get("users")    or {}
        item  = h.get("warehouse") or {}
        hist_rows.append({
            "일시":    (h.get("acted_at", "") or "")[:16].replace("T", " "),
            "유형":    ACTION.get(h.get("action_type", ""), h.get("action_type", "")),
            "자재명":  item.get("item_name", "") if isinstance(item, dict) else "",
            "수량":    h.get("quantity", 0),
            "담당자":  actor.get("name", "") if isinstance(actor, dict) else "",
            "센터":    h.get("from_center", ""),
            "사유":    h.get("reason", ""),
        })

    if hist_rows:
        st.dataframe(
            pd.DataFrame(hist_rows),
            use_container_width=True, hide_index=True,
            height=min(len(hist_rows) * 35 + 40, 500),
            column_config={
                "일시":   st.column_config.TextColumn("일시",   width=130),
                "유형":   st.column_config.TextColumn("유형",   width=80),
                "자재명": st.column_config.TextColumn("자재명", width=200),
                "수량":   st.column_config.NumberColumn("수량",  width=60),
                "담당자": st.column_config.TextColumn("담당자", width=80),
                "센터":   st.column_config.TextColumn("센터",   width=80),
                "사유":   st.column_config.TextColumn("사유",   width=200),
            },
        )
    else:
        st.info("이력이 없습니다.")
except Exception as e:
    st.warning(f"이력 조회 실패: {e}")
