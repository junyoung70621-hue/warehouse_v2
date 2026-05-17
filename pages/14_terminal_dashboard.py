# pages/14_terminal_dashboard.py
import io
import uuid
from datetime import date, datetime, timedelta

import openpyxl
import pandas as pd
import streamlit as st
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

from utils.auth import is_role, require_login
from utils.db import get_supabase
from utils.permissions import get_center as _get_center
from utils.routing import CENTERS
from utils.ui import (
    apply_global_css,
    render_sidebar_header,
    render_sidebar_section,
    render_sidebar_user,
    render_top_bar,
)

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

if user_role != "admin":
    st.error("접근 권한이 없습니다.")
    st.stop()

_is_admin   = user_role == "admin"
_is_jjae    = user_center == "자재센터"
_can_up_out = user_role in ("admin", "materials")           # 출고 업로드 권한
_can_up_in  = user_role in ("admin", "manager", "user")     # 입고 업로드 권한

NON_HUB_CENTERS = [c for c in CENTERS if c != "자재센터"]

TABLE = "terminal_movements"

# ── SQL 안내문 (테이블 미생성 시 표시) ────────────────────────────────────────
_SQL_SETUP = """\
-- Supabase SQL Editor에서 실행하세요
CREATE TABLE IF NOT EXISTS terminal_movements (
    id           uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
    upload_id    uuid        NOT NULL,
    trcn_id      text        NOT NULL,
    device_type  text        NOT NULL,
    sub_type     text        NOT NULL,
    from_center  text        NOT NULL,
    to_center    text        NOT NULL,
    direction    text        NOT NULL CHECK (direction IN ('in','out')),
    uploaded_by  uuid        REFERENCES users(id) ON DELETE SET NULL,
    uploaded_at  timestamptz DEFAULT now(),
    upload_date  date        NOT NULL,
    file_name    text
);
CREATE INDEX IF NOT EXISTS idx_tm_upload_date ON terminal_movements(upload_date);
CREATE INDEX IF NOT EXISTS idx_tm_direction   ON terminal_movements(direction);
CREATE INDEX IF NOT EXISTS idx_tm_trcn_id     ON terminal_movements(trcn_id);
"""


# ══════════════════════════════════════════════════════════════════════════════
# 단말기 분류 로직
# ══════════════════════════════════════════════════════════════════════════════

def classify_terminal(raw) -> tuple[str, str]:
    """TRCN_ID → (단말기종류, 유형).  숫자만 추출 후 길이·prefix 기준 분류."""
    digits = "".join(c for c in str(raw) if c.isdigit())
    if not digits:
        return "미분류", "알 수 없음"

    n = len(digits)

    # ── 승하차·운전자 계열 (8~9자리) ──
    if n in (8, 9):
        if digits.startswith("1560"):  return "B800", "승하차"
        if digits.startswith("1553"):  return "B710", "승하차"
        if digits.startswith("1551"):  return "B620", "승하차"
        if digits.startswith("1451"):  return "B620", "운전자"

    # ── 표출기·통합단말기 계열 (9자리) ──
    if n == 9:
        if digits.startswith("5600"):  return "B800", "표출기"
        if digits.startswith("5500"):  return "B800", "통합단말기"
        if digits.startswith("4550"):  return "B710", "표출기"
        if digits.startswith("4450"):  return "B710", "통합단말기"
        if digits.startswith("4500"):  return "B700", "표출기"
        if digits.startswith("4400"):  return "B700", "통합단말기"

    # ── 6자리 모뎀 (더 구체적인 prefix 먼저) ──
    if n == 6:
        if digits.startswith("100"):                           return "B800", "모뎀"
        if digits.startswith("6"):                             return "B710", "모뎀"
        if digits.startswith("4") or digits.startswith("5"):  return "B700", "모뎀"
        if digits.startswith("1"):                             return "B620", "모뎀"

    return "미분류", "알 수 없음"


DEVICE_ORDER = ["B800", "B700", "B710", "B620", "미분류"]
SUB_ORDER    = ["표출기", "통합단말기", "승하차", "운전자", "모뎀", "알 수 없음"]


def _apply_classifications(series: pd.Series) -> pd.DataFrame:
    """pd.Series → DataFrame[_dtype, _stype]"""
    results = [classify_terminal(v) for v in series]
    if results:
        return pd.DataFrame(results, columns=["_dtype", "_stype"], index=series.index)
    return pd.DataFrame({"_dtype": pd.Series(dtype=str), "_stype": pd.Series(dtype=str)})


def build_pivot(rows: list) -> pd.DataFrame:
    """행 목록 → 단말기종류 x 유형 pivot 테이블."""
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    df["device_type"] = pd.Categorical(df["device_type"], categories=DEVICE_ORDER, ordered=True)
    df["sub_type"]    = pd.Categorical(df["sub_type"],    categories=SUB_ORDER,    ordered=True)
    pivot = df.pivot_table(
        index="device_type", columns="sub_type",
        values="trcn_id", aggfunc="count", fill_value=0, observed=False,
    )
    pivot.index.name   = "종류"
    pivot.columns.name = None
    present = [c for c in SUB_ORDER if c in pivot.columns]
    pivot   = pivot[present]
    pivot["합계"] = pivot.sum(axis=1)
    return pivot[pivot["합계"] > 0]


# ══════════════════════════════════════════════════════════════════════════════
# Excel 파싱
# ══════════════════════════════════════════════════════════════════════════════

def parse_terminal_excel(uploaded_file) -> pd.DataFrame | None:
    """헤더=3번 행(header=2) 기준으로 파싱. xlsx→openpyxl, xls→xlrd."""
    fname = getattr(uploaded_file, "name", "")
    engine = "xlrd" if fname.lower().endswith(".xls") else "openpyxl"
    try:
        return pd.read_excel(
            uploaded_file, engine=engine, header=2, dtype=str
        ).dropna(how="all").reset_index(drop=True)
    except Exception as e:
        st.error(f"파일 읽기 실패: {e}")
        return None


def find_trcn_col(df: pd.DataFrame) -> str | None:
    """단말기ID 컬럼 자동 감지."""
    kws = ["trcn_id", "trcnid", "단말기id", "단말기번호", "단말기 id", "단말기 번호",
           "ih번호", "ih", "단말기", "번호"]
    for col in df.columns:
        nm = str(col).strip().lower().replace(" ", "").replace("_", "")
        for kw in kws:
            if kw in nm:
                return col
    return None


# ══════════════════════════════════════════════════════════════════════════════
# DB 함수
# ══════════════════════════════════════════════════════════════════════════════

def _table_exists() -> bool:
    try:
        get_supabase().table(TABLE).select("id").limit(1).execute()
        return True
    except Exception:
        return False


def fetch_terminal(
    direction: str = None,
    upload_date: date = None,
    date_from: date = None,
    date_to: date = None,
    limit: int = 3000,
) -> list:
    try:
        q = (
            get_supabase().table(TABLE)
            .select("id,upload_id,trcn_id,device_type,sub_type,"
                    "from_center,to_center,direction,"
                    "uploaded_at,upload_date,file_name,uploaded_by")
            .order("uploaded_at", desc=True)
        )
        if direction:   q = q.eq("direction",   direction)
        if upload_date: q = q.eq("upload_date", upload_date.isoformat())
        if date_from:   q = q.gte("upload_date", date_from.isoformat())
        if date_to:     q = q.lte("upload_date", date_to.isoformat())
        return q.limit(limit).execute().data or []
    except Exception:
        return []


def check_dups(trcn_ids: list[str], upload_date: date, direction: str) -> set[str]:
    """이미 등록된 TRCN_ID 집합 반환 (같은 날짜·방향 기준)."""
    if not trcn_ids:
        return set()
    try:
        res = (
            get_supabase().table(TABLE)
            .select("trcn_id")
            .eq("upload_date", upload_date.isoformat())
            .eq("direction",   direction)
            .in_("trcn_id",    trcn_ids[:500])
            .execute()
        )
        return {r["trcn_id"] for r in (res.data or [])}
    except Exception:
        return set()


def save_terminal(records: list) -> bool:
    try:
        get_supabase().table(TABLE).insert(records).execute()
        return True
    except Exception as e:
        st.error(f"저장 실패: {e}")
        return False


# ══════════════════════════════════════════════════════════════════════════════
# 인수인계증 Excel 생성
# ══════════════════════════════════════════════════════════════════════════════

def gen_handover_xlsx(rows: list, from_c: str, to_c: str, mv_date: date) -> bytes:
    from openpyxl.worksheet.pagebreak import Break

    wb  = openpyxl.Workbook()
    ws  = wb.active
    ws.title = "인수인계증"

    bold14     = Font(name="맑은 고딕", bold=True, size=14)
    bold11     = Font(name="맑은 고딕", bold=True, size=11)
    bold10     = Font(name="맑은 고딕", bold=True, size=10)
    norm10     = Font(name="맑은 고딕", size=10)
    ca         = Alignment(horizontal="center", vertical="center")
    la         = Alignment(horizontal="left",   vertical="center")
    thin       = Side(style="thin")
    bdr        = Border(left=thin, right=thin, top=thin, bottom=thin)
    gray       = PatternFill("solid", fgColor="D9D9D9")
    lblue      = PatternFill("solid", fgColor="BDD7EE")
    total_fill = PatternFill("solid", fgColor="FFF2CC")

    date_str = mv_date.strftime("%Y-%m-%d")

    # A열 153px ≈ 20 Excel 문자 너비 (7.5px/char 기준)
    for col, w in zip("ABCD", [10, 20, 14, 14]):
        ws.column_dimensions[col].width = w

    def _header(start_r: int, title: str):
        # 제목
        ws.merge_cells(f"A{start_r}:D{start_r}")
        c = ws.cell(start_r, 1, title); c.font = bold14; c.alignment = ca
        ws.row_dimensions[start_r].height = 30

        # 출발센터 / 도착센터 → 2행
        for ci, (lbl, val) in enumerate([("출발센터", from_c), ("도착센터", to_c)], start=1):
            ws.cell(start_r + 1, ci * 2 - 1, lbl).font = bold11
            ws.cell(start_r + 1, ci * 2 - 1).alignment = la
            ws.cell(start_r + 1, ci * 2,     val).font = norm10
            ws.cell(start_r + 1, ci * 2    ).alignment = la

        # 날짜 / 총수량 → 3행 (4열 내 배치)
        ws.cell(start_r + 2, 1, "날짜").font    = bold11
        ws.cell(start_r + 2, 1).alignment       = la
        ws.cell(start_r + 2, 2, date_str).font  = norm10
        ws.cell(start_r + 2, 2).alignment       = la
        ws.cell(start_r + 2, 3, "총 수량").font = bold11
        ws.cell(start_r + 2, 3).alignment       = la
        ws.cell(start_r + 2, 4, f"{len(rows):,}대").font = norm10
        ws.cell(start_r + 2, 4).alignment       = la

    # ── 1페이지: 요약 ─────────────────────────────────────────────────────────
    _header(1, "단말기 이동 인수인계증 — 요약")

    r = 5
    ws.merge_cells(f"A{r}:D{r}")
    h = ws.cell(r, 1, "종류별 수량 요약"); h.font = bold11; h.alignment = ca; h.fill = lblue
    r += 1
    for ci, hdr in enumerate(["No", "단말기종류", "유형", "수량"], 1):
        c = ws.cell(r, ci, hdr); c.font = bold11; c.alignment = ca
        c.fill = gray; c.border = bdr
    r += 1

    if rows:
        s_df = (
            pd.DataFrame(rows)
            .groupby(["device_type", "sub_type"], sort=False)
            .size().reset_index(name="cnt")
        )
        for idx, row in enumerate(s_df.itertuples(), 1):
            for ci, val in enumerate([idx, row.device_type, row.sub_type, row.cnt], 1):
                c = ws.cell(r, ci, val); c.font = norm10; c.alignment = ca; c.border = bdr
            r += 1
        # 합계 행
        ws.merge_cells(f"A{r}:C{r}")
        c = ws.cell(r, 1, "합계"); c.font = bold10; c.alignment = ca
        c.fill = total_fill; c.border = bdr
        for col in (2, 3):
            ws.cell(r, col).fill = total_fill; ws.cell(r, col).border = bdr
        c4 = ws.cell(r, 4, len(rows)); c4.font = bold10; c4.alignment = ca
        c4.fill = total_fill; c4.border = bdr
        r += 1

    r += 3
    for ci, lbl in [(1, "인계자"), (3, "인수자")]:
        ws.cell(r, ci, lbl).font = bold11
    r += 1
    ws.cell(r, 1, "(서명)").alignment = ca
    ws.cell(r, 3, "(서명)").alignment = ca
    r += 1

    # ── 페이지 나누기 ─────────────────────────────────────────────────────────
    ws.row_breaks.append(Break(id=r))
    r += 1

    # ── 2페이지: 상세 ─────────────────────────────────────────────────────────
    _header(r, "단말기 이동 인수인계증 — 상세")
    r += 3

    r += 1
    ws.merge_cells(f"A{r}:B{r}")
    h = ws.cell(r, 1, "단말기 IH 목록"); h.font = bold11; h.alignment = ca; h.fill = lblue
    r += 1
    for ci, hdr in enumerate(["No", "IH (TRCN_ID)"], 1):
        c = ws.cell(r, ci, hdr); c.font = bold11; c.alignment = ca
        c.fill = gray; c.border = bdr
    r += 1

    for idx, trcn in enumerate(sorted(row.get("trcn_id", "") for row in rows), 1):
        ws.cell(r, 1, idx).font  = norm10; ws.cell(r, 1).alignment = ca; ws.cell(r, 1).border = bdr
        ws.cell(r, 2, trcn).font = norm10; ws.cell(r, 2).alignment = ca; ws.cell(r, 2).border = bdr
        r += 1

    ws.print_area       = f"A1:D{r}"
    ws.page_setup.fitToPage   = True
    ws.page_setup.fitToWidth  = 1
    ws.page_setup.fitToHeight = 0

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ══════════════════════════════════════════════════════════════════════════════
# 업로드 처리 (공통 로직)
# ══════════════════════════════════════════════════════════════════════════════

def _upload_section(direction: str, from_c: str, to_c_fixed: str | None, key_prefix: str):
    """direction='out' or 'in'. to_c_fixed=None → 선택박스."""
    dir_label = "출고" if direction == "out" else "입고"

    if to_c_fixed is None:
        to_c = st.selectbox("도착 센터", NON_HUB_CENTERS, key=f"{key_prefix}_to")
    else:
        to_c = to_c_fixed
        st.markdown(f"**도착 센터:** `{to_c}`")

    mv_date = st.date_input("이동 날짜", value=date.today(), key=f"{key_prefix}_date")
    uploaded = st.file_uploader(
        "엑셀 파일 (.xls / .xlsx, 3번 행 = 헤더)",
        type=["xls", "xlsx"],
        key=f"{key_prefix}_file",
        help="단말기 이동신청서 양식. 1·2번 행은 제목으로 간주해 자동 건너뜁니다.",
    )

    if not uploaded:
        return

    df = parse_terminal_excel(uploaded)
    if df is None or df.empty:
        st.warning("데이터를 읽지 못했습니다.")
        return

    auto_col = find_trcn_col(df)
    all_cols = df.columns.tolist()
    default_idx = all_cols.index(auto_col) if auto_col in all_cols else 0
    trcn_col = st.selectbox(
        "단말기ID 컬럼 선택",
        all_cols,
        index=default_idx,
        key=f"{key_prefix}_col",
    )

    df["_trcn"] = df[trcn_col].astype(str).str.strip()
    cls = _apply_classifications(df["_trcn"])
    df = pd.concat([df, cls], axis=1)

    valid = df[df["_dtype"] != "미분류"].copy()
    inv   = df[df["_dtype"] == "미분류"]

    c1, c2 = st.columns(2)
    c1.metric("✅ 분류 성공", f"{len(valid)}")
    c2.metric("⚠️ 미분류", f"{len(inv)}")

    if not inv.empty:
        st.warning(f"⚠️ 미분류 {len(inv)}건 — 규칙 미매칭, 저장 제외")
        inv_show = inv[[trcn_col, "_trcn"]].copy()
        inv_show.columns = ["원본값", "추출값(숫자)"]
        inv_show["자릿수"] = inv_show["추출값(숫자)"].str.len()
        st.dataframe(inv_show, use_container_width=True, hide_index=True)

    if valid.empty:
        st.warning("분류 가능한 단말기가 없습니다. 컬럼을 확인하세요.")
        return

    s_df = (
        valid.groupby(["_dtype", "_stype"]).size()
        .reset_index(name="수량")
        .rename(columns={"_dtype": "종류", "_stype": "유형"})
    )
    st.caption("분류 요약")
    st.dataframe(s_df, use_container_width=True, hide_index=True)

    dups   = check_dups(valid["_trcn"].tolist(), mv_date, direction)
    dup_df = valid[valid["_trcn"].isin(dups)]
    new_df = valid[~valid["_trcn"].isin(dups)]

    if not dup_df.empty:
        st.warning(f"⚠️ {len(dup_df)}건이 같은 날짜·방향으로 이미 DB에 존재합니다.")
        dup_show = dup_df[[trcn_col, "_trcn", "_dtype", "_stype"]].copy()
        dup_show.columns = ["원본값", "TRCN_ID", "기종", "유형"]
        st.dataframe(dup_show, use_container_width=True, hide_index=True)
        force = st.checkbox("중복 무시하고 강제 저장", key=f"{key_prefix}_force")
        if force:
            new_df = valid.copy()

    if new_df.empty:
        st.error("저장할 데이터가 없습니다.")
        return

    st.info(f"저장 예정: **{len(new_df)}건** / {from_c} → {to_c} / {mv_date}")

    if st.button(f"✅ {dir_label} 데이터 저장", type="primary", key=f"{key_prefix}_save"):
        uid = str(uuid.uuid4())
        records = [
            {
                "upload_id":   uid,
                "trcn_id":     row["_trcn"],
                "device_type": row["_dtype"],
                "sub_type":    row["_stype"],
                "from_center": from_c,
                "to_center":   to_c,
                "direction":   direction,
                "uploaded_by": user["id"],
                "upload_date": mv_date.isoformat(),
                "file_name":   uploaded.name,
            }
            for _, row in new_df.iterrows()
        ]
        if save_terminal(records):
            st.success(f"✅ {len(records)}건 저장 완료!")
            st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# 사이드바
# ══════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    render_sidebar_header()
    if st.button("📊 대시보드(자재)", use_container_width=True):
        st.switch_page("pages/10_dashboard.py")
    st.button("📟 대시보드(단말기)", use_container_width=True, type="primary")
    st.divider()

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
        if st.button("📦 자재 요청", use_container_width=True, key="sb_mat"):
            st.switch_page("pages/07_material_requests.py")
        if st.button("🛒 구매 요청", use_container_width=True, key="sb_pur"):
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


# ══════════════════════════════════════════════════════════════════════════════
# 메인 컨텐츠
# ══════════════════════════════════════════════════════════════════════════════
render_top_bar("대시보드(단말기)", user)
st.markdown("## 📟 단말기 이동 현황 대시보드")
st.divider()

# 테이블 존재 확인
if not _table_exists():
    st.error("⚠️ Supabase 테이블 `terminal_movements` 가 없습니다. 아래 SQL을 실행하세요.")
    st.code(_SQL_SETUP, language="sql")
    st.stop()

tab_dash, tab_hist, tab_cert = st.tabs(["📊 오늘의 현황", "📋 이력 조회", "📄 인수인계증"])


# ══ Tab 1: 오늘의 현황 ════════════════════════════════════════════════════════
with tab_dash:
    today = date.today()
    rc, _ = st.columns([1, 11])
    if rc.button("🔄", key="t1_ref", help="새로고침"):
        st.rerun()

    out_rows = fetch_terminal(direction="out", upload_date=today)
    in_rows  = fetch_terminal(direction="in",  upload_date=today)

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("📤 출고 (오늘)", f"{len(out_rows):,}대")
    k2.metric("📥 입고 (오늘)", f"{len(in_rows):,}대")
    k3.metric("📅 날짜",        today.strftime("%Y-%m-%d"))
    k4.metric("👤 소속",        user_center)
    st.divider()

    left_col, right_col = st.columns(2)

    # ── 출고 현황 ──────────────────────────────────────────────────────────
    with left_col:
        st.markdown("#### 📤 출고 현황 &nbsp; `자재센터 → 타센터`")
        if out_rows:
            st.dataframe(build_pivot(out_rows), use_container_width=True)
            out_df  = pd.DataFrame(out_rows)
            ctr_out = out_df.groupby("to_center").size().reset_index(name="수량")
            ctr_out.columns = ["도착 센터", "수량"]
            st.caption("▸ 센터별")
            st.dataframe(ctr_out, use_container_width=True, hide_index=True)
        else:
            st.info("📭 오늘 출고 데이터가 없습니다.")

        if _can_up_out:
            with st.expander("📤 출고 데이터 업로드", expanded=False):
                _upload_section("out", "자재센터", None, "out")

    # ── 입고 현황 ──────────────────────────────────────────────────────────
    with right_col:
        st.markdown("#### 📥 입고 현황 &nbsp; `타센터 → 자재센터`")
        if in_rows:
            st.dataframe(build_pivot(in_rows), use_container_width=True)
            in_df   = pd.DataFrame(in_rows)
            ctr_in  = in_df.groupby("from_center").size().reset_index(name="수량")
            ctr_in.columns = ["출발 센터", "수량"]
            st.caption("▸ 센터별")
            st.dataframe(ctr_in, use_container_width=True, hide_index=True)
        else:
            st.info("📭 오늘 입고 데이터가 없습니다.")

        if _can_up_in:
            with st.expander("📥 입고 데이터 업로드", expanded=False):
                _from_fixed = None if _is_admin else user_center
                if not _is_admin:
                    st.markdown(f"**출발 센터:** `{user_center}`")
                else:
                    _from_fixed = st.selectbox("출발 센터", NON_HUB_CENTERS, key="in_from_admin")
                _upload_section("in", _from_fixed or user_center, "자재센터", "in")


# ══ Tab 2: 이력 조회 ══════════════════════════════════════════════════════════
with tab_hist:
    f1, f2, f3, f4 = st.columns([2, 2, 3, 1])
    h_from  = f1.date_input("시작일", value=date.today() - timedelta(days=30), key="h_from")
    h_to    = f2.date_input("종료일", value=date.today(),                       key="h_to")
    h_dir   = f3.selectbox("방향", ["전체", "출고 (자재→센터)", "입고 (센터→자재)"],  key="h_dir")
    if f4.button("🔄", key="h_ref"):
        st.rerun()

    _dir_map = {"전체": None, "출고 (자재→센터)": "out", "입고 (센터→자재)": "in"}
    hist_rows = fetch_terminal(direction=_dir_map[h_dir], date_from=h_from, date_to=h_to)

    if not hist_rows:
        st.info("조회 결과가 없습니다.")
    else:
        h_df = pd.DataFrame(hist_rows)
        h_df["방향"] = h_df["direction"].map({"out": "출고", "in": "입고"})
        show = h_df.rename(columns={
            "upload_date": "이동날짜", "from_center": "출발센터",
            "to_center": "도착센터", "device_type": "종류",
            "sub_type": "유형", "trcn_id": "TRCN_ID", "file_name": "파일명",
        })[["이동날짜", "방향", "출발센터", "도착센터", "종류", "유형", "TRCN_ID", "파일명"]]

        st.markdown(f"**총 {len(show):,}건**")
        st.dataframe(show, use_container_width=True, hide_index=True, height=480)

        xbuf = io.BytesIO()
        with pd.ExcelWriter(xbuf, engine="openpyxl") as xw:
            show.to_excel(xw, index=False, sheet_name="이력")
        st.download_button(
            "📥 Excel 다운로드",
            data=xbuf.getvalue(),
            file_name=f"단말기이력_{h_from}_{h_to}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="hist_dl",
        )


# ══ Tab 3: 인수인계증 ══════════════════════════════════════════════════════════
with tab_cert:
    st.markdown("#### 📄 인수인계증 생성")
    c1, c2, c3 = st.columns(3)
    cert_date   = c1.date_input("이동 날짜", value=date.today(), key="cert_date")
    cert_dir    = c2.selectbox("방향", ["출고 (자재→센터)", "입고 (센터→자재)"], key="cert_dir")
    cert_center = c3.selectbox("센터 필터 (선택)", ["전체"] + NON_HUB_CENTERS, key="cert_center")

    if st.button("📋 미리보기 & 다운로드 준비", key="cert_go"):
        _cv = "out" if "출고" in cert_dir else "in"
        c_rows = fetch_terminal(direction=_cv, upload_date=cert_date)
        if cert_center != "전체":
            c_rows = [r for r in c_rows if (
                r["to_center"] == cert_center if _cv == "out" else r["from_center"] == cert_center
            )]
        st.session_state.update({
            "cert_rows": c_rows, "cert_dv": _cv,
            "cert_dt": cert_date, "cert_cc": cert_center,
        })

    if st.session_state.get("cert_rows") is not None:
        c_rows = st.session_state["cert_rows"]
        _cv    = st.session_state["cert_dv"]
        _dt    = st.session_state["cert_dt"]
        _cc    = st.session_state["cert_cc"]

        _from_c = "자재센터" if _cv == "out" else (_cc if _cc != "전체" else "타센터")
        _to_c   = (_cc if _cc != "전체" else "타센터") if _cv == "out" else "자재센터"

        if not c_rows:
            st.warning("해당 조건의 데이터가 없습니다.")
        else:
            st.markdown(
                f"**{_from_c} → {_to_c}** &nbsp;|&nbsp; {_dt} &nbsp;|&nbsp; 총 **{len(c_rows):,}대**"
            )
            st.dataframe(build_pivot(c_rows).reset_index(), use_container_width=True, hide_index=True)

            xlsx_data = gen_handover_xlsx(c_rows, _from_c, _to_c, _dt)
            st.download_button(
                "📥 인수인계증 Excel 다운로드",
                data=xlsx_data,
                file_name=f"인수인계증_{_dt}_{_from_c}→{_to_c}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="cert_dl",
            )
