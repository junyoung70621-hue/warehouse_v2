"""
창고 데이터 export + 중복 row 분석 스크립트
실행: python export_warehouse.py
출력: warehouse_export_YYYYMMDD_HHMMSS.xlsx
"""
import os, sys
from datetime import datetime
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# .streamlit/secrets.toml 에서 키 읽기
def _load_secrets():
    import re
    path = os.path.join(os.path.dirname(__file__), ".streamlit", "secrets.toml")
    with open(path, encoding="utf-8") as f:
        text = f.read()
    url = re.search(r'SUPABASE_URL\s*=\s*"([^"]+)"', text).group(1)
    key = re.search(r'SUPABASE_KEY\s*=\s*"([^"]+)"', text).group(1)
    return url, key

try:
    import pandas as pd
    from supabase import create_client
except ImportError as e:
    sys.exit(f"[오류] 패키지 없음: {e}\n  pip install supabase pandas openpyxl")

url, key = _load_secrets()
sb = create_client(url, key)

print("Supabase 연결 완료. 데이터 조회 중...")

# ── warehouse 전체 조회 ────────────────────────────────────────────────────
wh_cols = (
    "id, item_name, quantity, rack_no, shelf, box_no, "
    "category_large, category_mid, category_small, "
    "location, erp_name, erp_code, "
    "repair_manager, item_location, notes, "
    "last_modified_at"
)
wh_data = sb.table("warehouse").select(wh_cols).order("item_name").execute().data
df_wh = pd.DataFrame(wh_data)
print(f"  warehouse: {len(df_wh)} rows")

# ── history 최근 500건 ────────────────────────────────────────────────────
hist_cols = (
    "id, action_type, quantity, reason, "
    "from_center, to_center, "
    "snapshot_qty_before, snapshot_qty_after, acted_at, "
    "warehouse(item_name, location), users(name)"
)
hist_data = sb.table("history").select(hist_cols).order("acted_at", desc=True).limit(500).execute().data
hist_rows = []
for h in hist_data:
    wh = h.get("warehouse") or {}
    us = h.get("users")    or {}
    hist_rows.append({
        "id":           h["id"],
        "자재명":       wh.get("item_name",""),
        "센터":         wh.get("location",""),
        "작업유형":     h["action_type"],
        "수량":         h["quantity"],
        "사유":         h.get("reason",""),
        "from_center":  h.get("from_center",""),
        "to_center":    h.get("to_center",""),
        "변경전":       h.get("snapshot_qty_before",""),
        "변경후":       h.get("snapshot_qty_after",""),
        "작업자":       us.get("name",""),
        "일시":         (h.get("acted_at","") or "")[:19].replace("T"," "),
    })
df_hist = pd.DataFrame(hist_rows)
print(f"  history: {len(df_hist)} rows (최근 500건)")

# ── 중복 분석 (item_name + location 기준) ────────────────────────────────
if not df_wh.empty:
    dup_key = df_wh.groupby(["item_name", "location"]).size().reset_index(name="row_count")
    dup_key = dup_key[dup_key["row_count"] > 1].sort_values("row_count", ascending=False)

    if not dup_key.empty:
        dup_detail = df_wh[
            df_wh.set_index(["item_name","location"]).index.isin(
                dup_key.set_index(["item_name","location"]).index
            )
        ].sort_values(["item_name","location","box_no"])
    else:
        dup_detail = pd.DataFrame()
else:
    dup_key    = pd.DataFrame()
    dup_detail = pd.DataFrame()

print(f"  중복 item_name+location 조합: {len(dup_key)}건 / 중복 row 합계: {len(dup_detail)}행")

# ── 수량 0 row ────────────────────────────────────────────────────────────
df_zero = df_wh[df_wh["quantity"] == 0].copy() if not df_wh.empty else pd.DataFrame()
print(f"  수량=0 row: {len(df_zero)}행")

# ── Excel 저장 ────────────────────────────────────────────────────────────
ts       = datetime.now().strftime("%Y%m%d_%H%M%S")
out_path = os.path.join(os.path.dirname(__file__), f"warehouse_export_{ts}.xlsx")

with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
    df_wh.to_excel(writer,      sheet_name="전체_warehouse",  index=False)
    df_hist.to_excel(writer,    sheet_name="history_500",      index=False)
    dup_key.to_excel(writer,    sheet_name="중복_요약",        index=False)
    dup_detail.to_excel(writer, sheet_name="중복_상세",        index=False)
    df_zero.to_excel(writer,    sheet_name="수량0",            index=False)

print(f"\n[완료] 저장: {out_path}")
print("\n[시트 구성]")
print("  전체_warehouse  - 창고 전체 raw 데이터")
print("  history_500     - 최근 500건 이력")
print("  중복_요약       - item_name+location 중복 조합 목록 (row_count)")
print("  중복_상세       - 중복 row 실제 내용 (box_no별)")
print("  수량0           - 수량 0인 row 목록")
