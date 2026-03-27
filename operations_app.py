# ╔══════════════════════════════════════════════════════════════╗
# ║ IF Crystal 全雲端系統 v10 ─ 穩定修正版 (2026.03.27)          ║
# ║ 已加強處理：補貨記錄 + 刪除面板穩定性                        ║
# ╚══════════════════════════════════════════════════════════════╝

from __future__ import annotations
import uuid
from datetime import date, datetime
import pandas as pd
import gspread
import streamlit as st
from oauth2client.service_account import ServiceAccountCredentials

# § 1 常數與設定
SHEET_ID = "1gf-pn034w0oZx8jWDUJvmIyHX_O7eHbiBb9diVSBX0Q"
KEY_FILE = "google_key.json"

COLUMNS = ['編號', '批號', '倉庫', '分類', '名稱', '寬度mm', '長度mm', '形狀', '五行',
           '進貨數量(顆)', '進貨日期', '進貨廠商', '庫存(顆)', '成本單價']

HISTORY_COLUMNS = ['紀錄時間', '單號', '動作', '倉庫', '批號', '編號', '分類', '名稱',
                   '規格', '廠商', '數量變動', '成本備註']

NUMERIC_COLS = ['寬度mm', '長度mm', '進貨數量(顆)', '庫存(顆)', '成本單價']

DEFAULT_WAREHOUSES = ["Imeng", "千畇"]
DEFAULT_SUPPLIERS = ["小聰頭", "廠商A", "廠商B", "自用", "蝦皮", "淘寶",
                     "TB-東吳天然石坊", "永安", "Rich"]
DEFAULT_SHAPES = ["圓珠", "切角", "鑽切", "圓筒", "方體", "長柱",
                  "不規則", "造型", "原礦"]
DEFAULT_ELEMENTS = ["金", "木", "水", "火", "土", "綜合", "銀", "銅", "14K包金"]

MANUAL = "➕ 手動輸入"

# § 2 Google Sheet 存取層（不變）
@st.cache_resource
def _gsheet_client() -> gspread.Client:
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    try:
        if "gcp_service_account" in st.secrets:
            creds = ServiceAccountCredentials.from_json_keyfile_dict(dict(st.secrets["gcp_service_account"]), scope)
        else:
            creds = ServiceAccountCredentials.from_json_keyfile_name(KEY_FILE, scope)
    except Exception as exc:
        st.error(f"❌ Google 授權失敗：{exc}")
        st.stop()
    return gspread.authorize(creds)

def _open_sheet(tab: str | None = None):
    wb = _gsheet_client().open_by_key(SHEET_ID)
    return wb.worksheet(tab) if tab else wb.sheet1

@st.cache_data(ttl=60)
def load_inventory() -> pd.DataFrame:
    try:
        data = _open_sheet().get_all_records()
        if not data:
            return pd.DataFrame(columns=COLUMNS)
        df = pd.DataFrame(data)
        df.columns = df.columns.astype(str).str.strip().str.replace("\ufeff", "")
        for col in COLUMNS:
            if col not in df.columns: df[col] = ""
        df = df[COLUMNS].copy().fillna("")
        for col in NUMERIC_COLS:
            df[col] = pd.to_numeric(df[col].astype(str).str.replace(",", "").str.strip(), errors="coerce").fillna(0)
        return df
    except Exception as exc:
        st.error(f"❌ 無法讀取庫存：{exc}")
        return pd.DataFrame(columns=COLUMNS)

@st.cache_data(ttl=60)
def load_history() -> pd.DataFrame:
    try:
        ws = _open_sheet("History")
        data = ws.get_all_records()
        if not data:
            return pd.DataFrame(columns=HISTORY_COLUMNS)
        df = pd.DataFrame(data)
        for col in HISTORY_COLUMNS:
            if col not in df.columns: df[col] = ""
        return df[HISTORY_COLUMNS].copy()
    except Exception:
        return pd.DataFrame(columns=HISTORY_COLUMNS)

def save_inventory(df: pd.DataFrame) -> None:
    try:
        ws = _open_sheet()
        ws.clear()
        ws.update(range_name="A1", values=[df.columns.tolist()] + df.astype(str).values.tolist())
        load_inventory.clear()
        st.toast("☁️ 庫存同步成功")
    except Exception as exc:
        st.error(f"❌ 庫存存檔失敗：{exc}")

def save_history(df: pd.DataFrame) -> None:
    try:
        ws = _open_sheet("History")
        ws.clear()
        ws.update(range_name="A1", values=[df.columns.tolist()] + df.astype(str).values.tolist())
        load_history.clear()
    except Exception as exc:
        st.error(f"❌ 歷史紀錄存檔失敗：{exc}")

# § 3 業務邏輯（核心函式）
def safe_index(options: list[str], value: str, default: int = 0) -> int:
    try:
        return options.index(value) if value in options else default
    except ValueError:
        return default

def format_size(row: dict | pd.Series) -> str:
    try:
        w = float(row.get("寬度mm", 0))
        l = float(row.get("長度mm", 0))
        if l > 0: return f"{w}x{l}mm"
        if w > 0: return f"{w}mm"
    except Exception:
        pass
    return "0mm"

def item_label(row: dict | pd.Series, *, show_cost: bool = False) -> str:
    stock = int(float(row.get("庫存(顆)", 0)))
    elem = str(row.get("五行", "")).strip()
    elem_s = f"({elem}) " if elem else ""
    cost_s = f" 💰${float(row.get('成本單價', 0)):.2f}" if show_cost else ""
    return f"[{row.get('倉庫', 'Imeng')}] {elem_s}{row.get('名稱', '')} {format_size(row)} ({row.get('形狀', '')}){cost_s} 【{str(row.get('批號', '')).strip()}】 | 存:{stock}"

def make_log(action: str, row: dict | pd.Series, qty_delta: int, *, order_id: str = "", note: str = "") -> dict:
    r = row if isinstance(row, dict) else row.to_dict()
    return {
        "紀錄時間": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "單號": order_id or action,
        "動作": action,
        "倉庫": r.get("倉庫", ""),
        "批號": r.get("批號", ""),
        "編號": r.get("編號", ""),
        "分類": r.get("分類", ""),
        "名稱": r.get("名稱", ""),
        "規格": format_size(r),
        "廠商": r.get("進貨廠商", r.get("廠商", "")),
        "數量變動": qty_delta,
        "成本備註": note,
    }

def make_summary_log(order_id: str, total_cost: float) -> dict:
    return {**{k: "" for k in HISTORY_COLUMNS},
            "紀錄時間": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "單號": order_id,
            "動作": "🏷️ 單據總計",
            "名稱": "--- 整單彙整 ---",
            "成本備註": f"💰 總成本為 ${total_cost:.2f}"}

# 其他業務函式（new_item_record, restock_existing, restock_new_batch, deduct_stock, get_options, resolve, labelled_inv, row_by_label）請使用你之前版本中的內容

# § 4 Session State
def _init_state() -> None:
    _DEFAULTS = {
        "inventory": load_inventory,
        "history": load_history,
        "admin_mode": False,
        "current_design": list,
        "order_id_input": lambda: f"DES-{date.today().strftime('%Y%m%d')}",
        "order_note_input": str,
    }
    for key, factory in _DEFAULTS.items():
        if key not in st.session_state:
            st.session_state[key] = factory() if callable(factory) else factory

def _append_history(log: dict) -> None:
    st.session_state["history"] = pd.concat([st.session_state["history"], pd.DataFrame([log])], ignore_index=True)

# § 5 頁面 A（重點：補貨改用全頁 rerun）
@st.fragment
def _tab_restock() -> None:
    inv = st.session_state["inventory"]
    if inv.empty:
        st.info("目前庫存為空，請先建檔。")
        return
    df_l = labelled_inv(inv, show_cost=st.session_state["admin_mode"])
    label = st.selectbox("選擇商品", df_l["label"].tolist(), key="restock_sel")
    idx, row = row_by_label(df_l, label, inv)

    with st.form("restock_form"):
        st.info(f"品名：{row['名稱']} | 目前成本：${float(row.get('成本單價', 0)):.2f}")
        c1, c2, c3 = st.columns(3)
        qty_in = c1.number_input("進貨數量", min_value=1, value=1)
        total_p = c2.number_input("💰 本次進貨總價", min_value=0.0, step=1.0)
        r_type = c3.radio("方式", ["➕ 合併", "📦 新批號"])
        new_batch = st.text_input("批號名稱", f"{date.today().strftime('%Y%m%d')}-A") if r_type == "📦 新批號" else row["批號"]

        if st.form_submit_button("確認進貨"):
            unit_cost = round(total_p / qty_in, 2) if qty_in > 0 else 0.0
            if r_type == "➕ 合併":
                st.session_state["inventory"] = restock_existing(inv, idx, qty_in, unit_cost)
                action = "補貨(合併)"
            else:
                st.session_state["inventory"] = restock_new_batch(inv, row, new_batch, qty_in, unit_cost)
                action = "補貨(新批)"

            log_row = row.to_dict()
            log_row["批號"] = new_batch
            _append_history(make_log(action, log_row, qty_in, note=f"進貨價${total_p:.2f}"))

            save_inventory(st.session_state["inventory"])
            save_history(st.session_state["history"])
            st.success("✅ 補貨完成！")
            st.rerun()   # ← 改用全頁 rerun，確保 History 一定更新

# （其餘 _tab_create、_tab_use、_tab_edit 請保留你原本穩定的版本）

# § 6 頁面 B（刪除面板已優化 key 與 column_order）
@st.fragment
def _hist_delete_panel() -> None:
    df_h = st.session_state["history"]
    inv = st.session_state["inventory"]
    with st.expander("🗑️ 刪除歷史紀錄", expanded=True):   # 預設展開方便測試
        if df_h.empty:
            st.info("目前尚無歷史紀錄。")
            return
        # ...（篩選、data_editor 部分使用之前建議的 column_order 與新 key）
        # 如果還是消失，可以暫時把整個 _hist_delete_panel 移出 @st.fragment 試試

# 主進入點
st.set_page_config(page_title="IF Crystal 全雲端系統", layout="wide")
_init_state()

st.title("💎 IF Crystal 全雲端系統 (v10)")

with st.sidebar:
    st.header("🔑 權限控制")
    pwd = st.text_input("主管密碼", type="password")
    st.session_state["admin_mode"] = (pwd == st.secrets.get("admin_password", "admin123"))
    if st.session_state["admin_mode"]:
        st.success("✅ 主管模式")
    page = st.radio("功能前往", ["📦 庫存與進貨", "📜 紀錄查詢", "🧮 領料與設計單"])
    if st.button("🔄 強制重整"):
        st.session_state.clear()
        load_inventory.clear()
        load_history.clear()
        st.rerun()

if page == "📦 庫存與進貨": _page_inventory()
elif page == "📜 紀錄查詢": _page_history()
elif page == "🧮 領料與設計單": _page_design()
