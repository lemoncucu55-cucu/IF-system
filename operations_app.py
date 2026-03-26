# ╔══════════════════════════════════════════════════════════════╗
# ║         IF Crystal 全雲端系統  v10  (單檔完整版)              ║
# ║                                                              ║
# ║  架構說明（方便維護，各區段用 # ══ 分隔）：                   ║
# ║    § 1  常數與設定                                           ║
# ║    § 2  Google Sheet 存取層                                  ║
# ║    § 3  純業務邏輯（不依賴 Streamlit，可獨立測試）            ║
# ║    § 4  Session State 初始化                                 ║
# ║    § 5  頁面 A：庫存與進貨                                   ║
# ║    § 6  頁面 B：紀錄查詢                                     ║
# ║    § 7  頁面 C：領料與設計單                                 ║
# ║    § 8  主進入點（路由）                                     ║
# ║                                                              ║
# ║  執行：streamlit run app.py                                  ║
# ╚══════════════════════════════════════════════════════════════╝

from __future__ import annotations

import uuid
from datetime import date, datetime

import pandas as pd
import gspread
import streamlit as st
from oauth2client.service_account import ServiceAccountCredentials


# ══════════════════════════════════════════════════════════════
# § 1  常數與設定
#      ↳ 新增倉庫 / 廠商 / 形狀：只需修改這裡
# ══════════════════════════════════════════════════════════════

SHEET_ID = "1gf-pn034w0oZx8jWDUJvmIyHX_O7eHbiBb9diVSBX0Q"
KEY_FILE  = "google_key.json"

COLUMNS = [
    '編號', '批號', '倉庫', '分類', '名稱',
    '寬度mm', '長度mm', '形狀', '五行',
    '進貨數量(顆)', '進貨日期', '進貨廠商',
    '庫存(顆)', '成本單價',
]
HISTORY_COLUMNS = [
    '紀錄時間', '單號', '動作', '倉庫', '批號',
    '編號', '分類', '名稱', '規格', '廠商',
    '數量變動', '成本備註',
]
NUMERIC_COLS = ['寬度mm', '長度mm', '進貨數量(顆)', '庫存(顆)', '成本單價']

DEFAULT_WAREHOUSES = ["Imeng", "千畇"]
DEFAULT_SUPPLIERS  = ["小聰頭", "廠商A", "廠商B", "自用", "蝦皮", "淘寶",
                      "TB-東吳天然石坊", "永安", "Rich"]
DEFAULT_SHAPES     = ["圓珠", "切角", "鑽切", "圓筒", "方體", "長柱",
                      "不規則", "造型", "原礦"]
DEFAULT_ELEMENTS   = ["金", "木", "水", "火", "土", "綜合", "銀", "銅", "14K包金"]

MANUAL = "➕ 手動輸入"   # 選單「手動輸入」項目的固定字串


# ══════════════════════════════════════════════════════════════
# § 2  Google Sheet 存取層
#      ↳ 日後若要換成資料庫，只需改這個區段
# ══════════════════════════════════════════════════════════════

@st.cache_resource
def _gsheet_client() -> gspread.Client:
    """建立並快取 gspread 連線，整個 session 只授權一次。"""
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]
    try:
        if "gcp_service_account" in st.secrets:
            creds = ServiceAccountCredentials.from_json_keyfile_dict(
                dict(st.secrets["gcp_service_account"]), scope
            )
        else:
            creds = ServiceAccountCredentials.from_json_keyfile_name(KEY_FILE, scope)
    except Exception as exc:
        st.error(f"❌ Google 授權失敗：{exc}")
        st.stop()
    return gspread.authorize(creds)


def _open_sheet(tab: str | None = None):
    """開啟工作表；tab=None 時回傳第一張（庫存表）。"""
    wb = _gsheet_client().open_by_key(SHEET_ID)
    return wb.worksheet(tab) if tab else wb.sheet1


@st.cache_data(ttl=60)
def load_inventory() -> pd.DataFrame:
    """讀取庫存表，60 秒內不重複呼叫 API。"""
    try:
        data = _open_sheet().get_all_records()
        if not data:
            return pd.DataFrame(columns=COLUMNS)
        df = pd.DataFrame(data)
        df.columns = df.columns.astype(str).str.strip().str.replace("\ufeff", "")
        for col in COLUMNS:
            if col not in df.columns:
                df[col] = ""
        df = df[COLUMNS].copy().fillna("")
        for col in NUMERIC_COLS:
            df[col] = (
                pd.to_numeric(
                    df[col].astype(str).str.replace(",", "").str.strip(),
                    errors="coerce",
                ).fillna(0)
            )
        return df
    except Exception as exc:
        st.error(f"❌ 無法讀取庫存：{exc}")
        return pd.DataFrame(columns=COLUMNS)


@st.cache_data(ttl=60)
def load_history() -> pd.DataFrame:
    """讀取歷史紀錄表，60 秒內不重複呼叫 API。"""
    try:
        ws = _open_sheet("History")
    except Exception:
        return pd.DataFrame(columns=HISTORY_COLUMNS)
    try:
        data = ws.get_all_records()
        if not data:
            return pd.DataFrame(columns=HISTORY_COLUMNS)
        df = pd.DataFrame(data)
        for col in HISTORY_COLUMNS:
            if col not in df.columns:
                df[col] = ""
        return df[HISTORY_COLUMNS].copy()
    except Exception as exc:
        st.error(f"❌ 無法讀取歷史紀錄：{exc}")
        return pd.DataFrame(columns=HISTORY_COLUMNS)


def save_inventory(df: pd.DataFrame) -> None:
    """將庫存寫回 Google Sheet，並清除快取讓下次讀取取得最新資料。"""
    try:
        ws = _open_sheet()
        ws.clear()
        ws.update(
            range_name="A1",
            values=[df.columns.tolist()] + df.astype(str).values.tolist(),
        )
        load_inventory.clear()
        st.toast("☁️ 庫存同步成功")
    except Exception as exc:
        st.error(f"❌ 庫存存檔失敗：{exc}")
        st.stop()


def save_history(df: pd.DataFrame) -> None:
    """將歷史紀錄寫回 Google Sheet。"""
    try:
        ws = _open_sheet("History")
        ws.clear()
        ws.update(
            range_name="A1",
            values=[df.columns.tolist()] + df.astype(str).values.tolist(),
        )
        load_history.clear()
    except Exception as exc:
        st.error(f"❌ 歷史紀錄存檔失敗：{exc}")


# ══════════════════════════════════════════════════════════════
# § 3  純業務邏輯
#      ↳ 此區段不使用任何 Streamlit API，方便抽出做單元測試
# ══════════════════════════════════════════════════════════════

# ── 格式化 ─────────────────────────────────────────────────────

def format_size(row: dict | pd.Series) -> str:
    """把寬度/長度欄位轉成可讀字串，例如 8x10mm 或 8mm。"""
    try:
        w = float(row.get("寬度mm", 0))
        l = float(row.get("長度mm", 0))
        if l > 0:
            return f"{w}x{l}mm"
        if w > 0:
            return f"{w}mm"
    except Exception:
        pass
    return "0mm"


def item_label(row: dict | pd.Series, *, show_cost: bool = False) -> str:
    """產生下拉選單顯示文字。show_cost 由呼叫端決定，不直接讀 session_state。"""
    stock  = int(float(row.get("庫存(顆)", 0)))
    elem   = str(row.get("五行", "")).strip()
    elem_s = f"({elem}) " if elem else ""
    cost_s = f" 💰${float(row.get('成本單價', 0)):.2f}" if show_cost else ""
    return (
        f"[{row.get('倉庫', 'Imeng')}] {elem_s}"
        f"{row.get('名稱', '')} {format_size(row)} "
        f"({row.get('形狀', '')}){cost_s} "
        f"【{str(row.get('批號', '')).strip()}】 | 存:{stock}"
    )


# ── 歷史紀錄產生器 ─────────────────────────────────────────────

def make_log(
    action: str,
    row: dict | pd.Series,
    qty_delta: int,
    *,
    order_id: str = "",
    note: str = "",
) -> dict:
    """統一產生一筆歷史紀錄字典（欄位完全對應 HISTORY_COLUMNS）。"""
    r = row if isinstance(row, dict) else row.to_dict()
    return {
        "紀錄時間": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "單號":    order_id or action,
        "動作":    action,
        "倉庫":    r.get("倉庫", ""),
        "批號":    r.get("批號", ""),
        "編號":    r.get("編號", ""),
        "分類":    r.get("分類", ""),
        "名稱":    r.get("名稱", ""),
        "規格":    format_size(r),
        "廠商":    r.get("進貨廠商", r.get("廠商", "")),
        "數量變動": qty_delta,
        "成本備註": note,
    }


def make_summary_log(order_id: str, total_cost: float) -> dict:
    """設計單「整單彙整」專用的 log，補滿所有空欄位。"""
    return {
        **{k: "" for k in HISTORY_COLUMNS},
        "紀錄時間": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "單號":    order_id,
        "動作":    "🏷️ 單據總計",
        "名稱":    "--- 整單彙整 ---",
        "成本備註": f"💰 總成本為 ${total_cost:.2f}",
    }


# ── 庫存操作 ───────────────────────────────────────────────────

def new_item_record(
    *, wh: str, cat: str, name: str, shape: str, element: str,
    supplier: str, w_mm: float, l_mm: float, qty: int, total_cost: float,
) -> dict:
    """建立一筆新商品資料列（尚未寫入 DataFrame）。"""
    return {
        "編號":       f"ST{uuid.uuid4().hex[:8].upper()}",
        "批號":       "初始存貨",
        "倉庫":       wh,
        "分類":       cat,
        "名稱":       name,
        "形狀":       shape,
        "五行":       element,
        "進貨數量(顆)": qty,
        "進貨廠商":   supplier,
        "進貨日期":   str(date.today()),
        "庫存(顆)":   qty,
        "成本單價":   round(total_cost / qty if qty > 0 else 0, 2),
        "寬度mm":     w_mm,
        "長度mm":     l_mm,
    }


def restock_existing(inv: pd.DataFrame, idx: int, qty: int, unit_cost: float) -> pd.DataFrame:
    """合併補貨：在原批號上增加庫存並更新成本。"""
    inv = inv.copy()
    inv.at[idx, "庫存(顆)"] += qty
    inv.at[idx, "成本單價"]  = unit_cost
    return inv


def restock_new_batch(
    inv: pd.DataFrame, template: pd.Series,
    batch_name: str, qty: int, unit_cost: float,
) -> pd.DataFrame:
    """新批號補貨：複製原列並附加到 DataFrame 尾端。"""
    new_r = template.copy()
    new_r["庫存(顆)"]    = qty
    new_r["進貨數量(顆)"] = qty
    new_r["進貨日期"]    = str(date.today())
    new_r["批號"]        = batch_name
    new_r["成本單價"]    = unit_cost
    return pd.concat([inv, pd.DataFrame([new_r])], ignore_index=True)


def deduct_stock(inv: pd.DataFrame, idx: int, qty: int) -> pd.DataFrame:
    """從指定列扣除庫存數量。"""
    inv = inv.copy()
    inv.at[idx, "庫存(顆)"] -= qty
    return inv


def calc_design_cost(design: list[dict], inv: pd.DataFrame) -> float:
    """計算設計清單的預估總成本。"""
    total = 0.0
    for item in design:
        mask = (inv["編號"] == item["編號"]) & (inv["批號"] == item["批號"])
        if mask.any():
            total += float(inv.loc[mask, "成本單價"].values[0]) * item["數量"]
    return total


# ── 選單工具 ───────────────────────────────────────────────────

def get_options(col_name: str, defaults: list, inv: pd.DataFrame) -> list:
    """合併預設清單與庫存現有值，首項為「手動輸入」。"""
    existing: set[str] = set()
    if not inv.empty and col_name in inv.columns:
        for v in inv[col_name].astype(str).unique():
            v = v.strip()
            if v and v.lower() not in ("nan", "0", "0.0"):
                existing.add(v)
    return [MANUAL] + sorted(existing | set(defaults))


def resolve(sel: str, manual: str) -> str:
    """依選單值決定回傳手動輸入值或選單值。"""
    return manual.strip() if sel == MANUAL else sel


def labelled_inv(inv: pd.DataFrame, *, show_cost: bool = False) -> pd.DataFrame:
    """回傳附帶 'label' 欄位的庫存副本，供下拉選單使用。"""
    df = inv.copy()
    df["label"] = df.apply(lambda r: item_label(r, show_cost=show_cost), axis=1)
    return df


def row_by_label(df_l: pd.DataFrame, label: str, inv: pd.DataFrame) -> tuple[int, pd.Series]:
    """由 label 字串取得原始 inventory 的 (index, Series)。"""
    idx = df_l[df_l["label"] == label].index[0]
    return idx, inv.loc[idx]


# ══════════════════════════════════════════════════════════════
# § 4  Session State 初始化
#      ↳ 新增全域狀態只需在 _DEFAULTS 加一行
# ══════════════════════════════════════════════════════════════

def _init_state() -> None:
    _DEFAULTS: dict = {
        "inventory":        load_inventory,
        "history":          load_history,
        "admin_mode":       False,
        "current_design":   list,
        "order_id_input":   lambda: f"DES-{date.today().strftime('%Y%m%d')}",
        "order_note_input": str,
    }
    for key, factory in _DEFAULTS.items():
        if key not in st.session_state:
            st.session_state[key] = factory() if callable(factory) else factory


def _append_history(log: dict) -> None:
    """將單筆 log dict 附加至 session_state['history']。"""
    st.session_state["history"] = pd.concat(
        [st.session_state["history"], pd.DataFrame([log])],
        ignore_index=True,
    )


# ══════════════════════════════════════════════════════════════
# § 5  頁面 A：庫存與進貨
#
#      每個 Tab 用 @st.fragment 包裝：
#      → 表單提交後只重跑該 fragment，不觸發整頁 rerun
# ══════════════════════════════════════════════════════════════

@st.fragment
def _tab_restock() -> None:
    inv = st.session_state["inventory"]
    if inv.empty:
        st.info("目前庫存為空，請先至「建檔」頁籤新增商品。")
        return

    df_l  = labelled_inv(inv, show_cost=st.session_state["admin_mode"])
    label = st.selectbox("選擇商品", df_l["label"].tolist(), key="restock_sel")
    idx, row = row_by_label(df_l, label, inv)

    with st.form("restock_form"):
        st.info(f"品名：{row['名稱']} | 目前單價成本：${float(row.get('成本單價', 0)):.2f}")
        c1, c2, c3 = st.columns(3)
        qty_in   = c1.number_input("進貨數量", min_value=1, value=1)
        total_p  = c2.number_input("💰 本次進貨總價", min_value=0.0, step=1.0)
        r_type   = c3.radio("方式", ["➕ 合併", "📦 新批號"])
        new_batch = (
            st.text_input("批號名稱", f"{date.today().strftime('%Y%m%d')}-A")
            if r_type == "📦 新批號" else row["批號"]
        )

        if st.form_submit_button("確認進貨"):
            unit_cost = round(total_p / qty_in, 2) if qty_in > 0 else 0.0
            if r_type == "➕ 合併":
                st.session_state["inventory"] = restock_existing(inv, idx, qty_in, unit_cost)
                action = "補貨(合併)"
            else:
                st.session_state["inventory"] = restock_new_batch(
                    inv, row, new_batch, qty_in, unit_cost
                )
                action = "補貨(新批)"
            log_row = row.to_dict()
            log_row["批號"] = new_batch
            _append_history(make_log(action, log_row, qty_in, note=f"進貨價${total_p:.2f}"))
            save_inventory(st.session_state["inventory"])
            save_history(st.session_state["history"])
            st.success("✅ 補貨完成！")
            st.rerun(scope="fragment")


@st.fragment
def _tab_create() -> None:
    inv = st.session_state["inventory"]

    with st.form("create_form"):
        c1, c2, c3 = st.columns(3)
        wh       = c1.selectbox("倉庫", DEFAULT_WAREHOUSES)
        n_opts   = get_options("名稱", ["水晶"], inv)
        n_sel    = c2.selectbox("名稱選單", n_opts, key="cn_sel")
        n_custom = c2.text_input("新名稱（手動輸入時填寫）")
        cat      = c3.selectbox("分類", ["天然石", "配件", "耗材"])

        c4, c5, c6 = st.columns(3)
        sh_opts   = get_options("形狀", DEFAULT_SHAPES, inv)
        sh_sel    = c4.selectbox("規格選單", sh_opts, key="csh_sel")
        sh_custom = c4.text_input("新規格")
        el_opts   = get_options("五行", DEFAULT_ELEMENTS, inv)
        el_sel    = c5.selectbox("顏色選單", el_opts, key="cel_sel")
        el_custom = c5.text_input("新顏色")
        su_opts   = get_options("進貨廠商", DEFAULT_SUPPLIERS, inv)
        su_sel    = c6.selectbox("廠商選單", su_opts, key="csu_sel")
        su_custom = c6.text_input("新廠商")

        c7, c8, c9, c10 = st.columns(4)
        w_mm    = c7.number_input("寬度 mm", 0.0)
        l_mm    = c8.number_input("長度 mm", 0.0)
        q_in    = c9.number_input("初始數量", min_value=1, value=1)
        cost_in = c10.number_input("總成本", min_value=0.0, step=1.0)

        if st.form_submit_button("✅ 建立商品"):
            final_n  = resolve(n_sel,  n_custom)
            final_su = resolve(su_sel, su_custom)
            errors   = []
            if not final_n:  errors.append("❌ 名稱為必填")
            if not final_su: errors.append("❌ 廠商為必填")
            if errors:
                for e in errors:
                    st.error(e)
            else:
                new_r = new_item_record(
                    wh=wh, cat=cat, name=final_n,
                    shape=resolve(sh_sel, sh_custom),
                    element=resolve(el_sel, el_custom),
                    supplier=final_su,
                    w_mm=w_mm, l_mm=l_mm,
                    qty=int(q_in), total_cost=cost_in,
                )
                st.session_state["inventory"] = pd.concat(
                    [inv, pd.DataFrame([new_r])], ignore_index=True
                )
                save_inventory(st.session_state["inventory"])
                st.success(f"✅ 商品「{final_n}」建立成功！")
                st.rerun(scope="fragment")


@st.fragment
def _tab_use() -> None:
    inv = st.session_state["inventory"]
    if inv.empty:
        st.info("目前庫存為空。")
        return

    df_l  = labelled_inv(inv, show_cost=st.session_state["admin_mode"])
    label = st.selectbox("選擇材料", df_l["label"].tolist(), key="use_sel")
    idx, row = row_by_label(df_l, label, inv)

    with st.form("quick_use_form"):
        c1, c2 = st.columns(2)
        qty_q  = c1.number_input("領用數量", min_value=1,
                                  max_value=max(1, int(row["庫存(顆)"])), value=1)
        note_q = c2.text_input("備註")
        if st.form_submit_button("✅ 確認領用"):
            st.session_state["inventory"] = deduct_stock(inv, idx, qty_q)
            _append_history(make_log(
                "快速領用", row.to_dict(), -qty_q,
                order_id=f"QU-{date.today().strftime('%Y%m%d')}",
                note=note_q,
            ))
            save_inventory(st.session_state["inventory"])
            save_history(st.session_state["history"])
            st.success(f"✅ 已領用 {qty_q} 顆「{row['名稱']}」")
            st.rerun(scope="fragment")


@st.fragment
def _tab_edit() -> None:
    inv = st.session_state["inventory"]
    if inv.empty:
        st.info("目前庫存為空。")
        return

    df_l  = labelled_inv(inv, show_cost=st.session_state["admin_mode"])
    label = st.selectbox("1. 選擇修改項目", df_l["label"].tolist(), key="edit_sel")
    idx, e_row = row_by_label(df_l, label, inv)
    st.markdown("---")

    c1, c2, c3 = st.columns(3)
    me_opts   = get_options("名稱", ["水晶"], inv)
    me_sel    = c1.selectbox("名稱選單", me_opts,
                              index=me_opts.index(e_row["名稱"]) if e_row["名稱"] in me_opts else 0,
                              key="en_sel")
    me_custom = st.text_input("📝 請輸入新名稱", key="en_in") if me_sel == MANUAL else ""

    sh_opts   = get_options("形狀", DEFAULT_SHAPES, inv)
    sh_sel    = c2.selectbox("規格選單", sh_opts,
                              index=sh_opts.index(e_row["形狀"]) if e_row["形狀"] in sh_opts else 0,
                              key="esh_sel")
    sh_custom = st.text_input("📝 請輸入新規格", key="esh_in") if sh_sel == MANUAL else ""

    el_opts   = get_options("五行", DEFAULT_ELEMENTS, inv)
    el_sel    = c3.selectbox("顏色選單", el_opts,
                              index=el_opts.index(e_row["五行"]) if e_row["五行"] in el_opts else 0,
                              key="eel_sel")
    el_custom = st.text_input("📝 請輸入新顏色", key="eel_in") if el_sel == MANUAL else ""

    with st.form("edit_form"):
        ca, cb, cc, cd = st.columns(4)
        nw = ca.number_input("寬度", value=float(e_row["寬度mm"]))
        nl = cb.number_input("長度", value=float(e_row["長度mm"]))
        nq = cc.number_input("庫存", value=int(e_row["庫存(顆)"]))
        nc = cd.number_input("成本", value=float(e_row["成本單價"]))

        if st.form_submit_button("💾 儲存修改"):
            updates = {
                "名稱":    resolve(me_sel, me_custom),
                "形狀":    resolve(sh_sel, sh_custom),
                "五行":    resolve(el_sel, el_custom),
                "寬度mm":  nw, "長度mm": nl,
                "庫存(顆)": nq, "成本單價": nc,
            }
            upd = inv.copy()
            for col, val in updates.items():
                upd.at[idx, col] = val
            st.session_state["inventory"] = upd
            save_inventory(st.session_state["inventory"])
            st.success("✅ 修改已儲存")
            st.rerun(scope="fragment")


def _page_inventory() -> None:
    tab_r, tab_c, tab_u, tab_e = st.tabs(["🔄 補貨", "✨ 建檔", "📤 領用", "🛠️ 修改"])
    with tab_r: _tab_restock()
    with tab_c: _tab_create()
    with tab_u: _tab_use()
    with tab_e: _tab_edit()

    st.subheader("📊 目前庫存表")
    st.dataframe(st.session_state["inventory"], use_container_width=True)


# ══════════════════════════════════════════════════════════════
# § 6  頁面 B：紀錄查詢
# ══════════════════════════════════════════════════════════════

@st.fragment
def _hist_search_panel() -> None:
    """搜尋 + 表格：輸入關鍵字只重跑此 fragment。"""
    df_h = st.session_state["history"]
    if df_h.empty:
        st.info("目前尚無歷史紀錄。")
        return

    keyword = st.text_input("🔍 搜尋（名稱 / 單號 / 動作）", key="hist_search")
    display = df_h.iloc[::-1].reset_index(drop=True)
    if keyword.strip():
        mask = (
            display["名稱"].astype(str).str.contains(keyword, na=False)
            | display["單號"].astype(str).str.contains(keyword, na=False)
            | display["動作"].astype(str).str.contains(keyword, na=False)
        )
        display = display[mask]
    st.dataframe(display, use_container_width=True)


@st.fragment
def _hist_rename_panel() -> None:
    """管理員專用：批次標籤更名。"""
    inv = st.session_state["inventory"]
    with st.expander("🛠️ 批次標籤修正"):
        c1, c2, c3 = st.columns(3)
        col_m    = c1.selectbox("欄位", ["五行", "形狀", "進貨廠商", "名稱"])
        col_vals = sorted(v for v in inv[col_m].unique() if str(v).strip())
        if not col_vals:
            st.info("該欄位目前無資料可修正。")
            return
        old_m = c2.selectbox("舊標籤", col_vals)
        new_m = c3.text_input("更名為")
        if st.button("🚀 執行"):
            if not new_m.strip():
                st.error("❌ 新標籤名稱不能為空")
                return
            upd = inv.copy()
            upd.loc[upd[col_m] == old_m, col_m] = new_m.strip()
            st.session_state["inventory"] = upd
            save_inventory(upd)
            st.success(f"✅ 已將「{old_m}」更名為「{new_m.strip()}」")
            st.rerun(scope="fragment")


def _page_history() -> None:
    st.subheader("📜 歷史紀錄")
    _hist_search_panel()
    if st.session_state.get("admin_mode"):
        _hist_rename_panel()


# ══════════════════════════════════════════════════════════════
# § 7  頁面 C：領料與設計單
# ══════════════════════════════════════════════════════════════

@st.fragment
def _design_add_panel() -> None:
    """選料並加入清單，只重跑此 fragment。"""
    inv = st.session_state["inventory"]
    if inv.empty:
        st.info("目前庫存為空。")
        return

    df_l  = labelled_inv(inv, show_cost=st.session_state["admin_mode"])
    label = st.selectbox("材料選擇", df_l["label"].tolist(), key="ds_sel")
    idx, row_ds = row_by_label(df_l, label, inv)
    qty_ds = st.number_input("數量", min_value=1,
                              max_value=max(1, int(row_ds["庫存(顆)"])), value=1)

    if st.button("⬇️ 加入清單"):
        st.session_state["current_design"].append({
            "編號": row_ds["編號"],
            "批號": row_ds["批號"],
            "名稱": row_ds["名稱"],
            "數量": qty_ds,
            "規格": format_size(row_ds),
            "五行": row_ds["五行"],
            "倉庫": row_ds["倉庫"],
            "廠商": row_ds["進貨廠商"],
            "分類": row_ds["分類"],
        })
        st.rerun(scope="fragment")


@st.fragment
def _design_list_panel() -> None:
    """清單預覽 + 確認領出，只重跑此 fragment。"""
    design = st.session_state["current_design"]
    if not design:
        st.info("清單為空，請先加入材料。")
        return

    inv        = st.session_state["inventory"]
    total_cost = calc_design_cost(design, inv)

    st.markdown("#### 📋 設計清單")
    for i, item in enumerate(design):
        col_t, col_del = st.columns([5, 1])
        col_t.write(f"🔸 [{item['五行']}] {item['名稱']} ({item['規格']}) x{item['數量']}")
        if col_del.button("🗑️", key=f"del_{i}"):
            st.session_state["current_design"].pop(i)
            st.rerun(scope="fragment")

    if st.session_state["admin_mode"]:
        st.metric("預估總成本", f"${total_cost:.2f}")

    if st.button("✅ 確認領出", type="primary", use_container_width=True):
        oid  = st.session_state["order_id_input"]
        note = st.session_state["order_note_input"]
        upd_inv = inv.copy()

        for x in design:
            mask = (upd_inv["編號"] == x["編號"]) & (upd_inv["批號"] == x["批號"])
            if mask.any():
                t_idx = upd_inv[mask].index[0]
                upd_inv = deduct_stock(upd_inv, t_idx, x["數量"])
                _append_history(make_log("設計單領出", x, -x["數量"], order_id=oid, note=note))

        if st.session_state["admin_mode"]:
            _append_history(make_summary_log(oid, total_cost))

        st.session_state["inventory"] = upd_inv
        save_inventory(upd_inv)
        save_history(st.session_state["history"])
        st.session_state["current_design"] = []
        st.success("✅ 訂單已完成！")
        st.rerun(scope="fragment")


def _page_design() -> None:
    st.subheader("🧮 設計單模式")
    ca, cb = st.columns([1, 2])
    st.session_state["order_id_input"]   = ca.text_input("單號",  st.session_state["order_id_input"])
    st.session_state["order_note_input"] = cb.text_input("備註",  st.session_state["order_note_input"])
    st.markdown("---")
    _design_add_panel()
    st.markdown("---")
    _design_list_panel()


# ══════════════════════════════════════════════════════════════
# § 8  主進入點
#      ↳ 只做頁面設定、側邊欄、路由三件事
# ══════════════════════════════════════════════════════════════

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

if   page == "📦 庫存與進貨":   _page_inventory()
elif page == "📜 紀錄查詢":     _page_history()
elif page == "🧮 領料與設計單": _page_design()
