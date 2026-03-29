from __future__ import annotations
import uuid
from datetime import date, datetime
import pandas as pd
import gspread
import streamlit as st
from oauth2client.service_account import ServiceAccountCredentials
import time

# ==========================================
# § 1 常數與設定
# ==========================================
SHEET_ID = "1gf-pn034w0oZx8jWDUJvmIyHX_O7eHbiBb9diVSBX0Q"
KEY_FILE = "google_key.json"

COLUMNS = ['編號', '批號', '倉庫', '分類', '名稱', '寬度mm', '長度mm', '形狀', '五行',
           '進貨數量(顆)', '進貨日期', '進貨廠商', '庫存(顆)', '成本單價']

HISTORY_COLUMNS = ['紀錄時間', '單號', '動作', '倉庫', '批號', '編號', '分類', '名稱',
                   '規格', '廠商', '數量變動', '成本備註']

NUMERIC_COLS = ['寬度mm', '長度mm', '進貨數量(顆)', '庫存(顆)', '成本單價']
DEFAULT_WAREHOUSES = ["Imeng", "千畇"]
DEFAULT_SUPPLIERS = ["小聰頭", "廠商A", "廠商B", "自用", "蝦皮", "淘寶", "永安", "Rich"]
DEFAULT_SHAPES = ["圓珠", "切角", "鑽切", "圓筒", "方體", "長柱", "不規則", "造型", "原礦"]
DEFAULT_ELEMENTS = ["金", "木", "水", "火", "土", "綜合", "銀", "銅", "14K包金"]
MANUAL = "➕ 手動輸入"

# ==========================================
# § 2 Google Sheet 核心功能
# ==========================================
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

def load_inventory() -> pd.DataFrame:
    try:
        data = _open_sheet().get_all_records()
        if not data: return pd.DataFrame(columns=COLUMNS)
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

def load_history() -> pd.DataFrame:
    try:
        ws = _open_sheet("History")
        data = ws.get_all_records()
        if not data: return pd.DataFrame(columns=HISTORY_COLUMNS)
        df = pd.DataFrame(data)
        for col in HISTORY_COLUMNS:
            if col not in df.columns: df[col] = ""
        return df[HISTORY_COLUMNS].copy()
    except:
        return pd.DataFrame(columns=HISTORY_COLUMNS)

def save_inventory(df: pd.DataFrame):
    ws = _open_sheet()
    ws.clear()
    ws.update(range_name="A1", values=[df.columns.tolist()] + df.astype(str).values.tolist())
    st.session_state["inventory"] = df
    st.toast("☁️ 庫存同步成功")

def save_history(df: pd.DataFrame):
    ws = _open_sheet("History")
    ws.clear()
    ws.update(range_name="A1", values=[df.columns.tolist()] + df.astype(str).values.tolist())
    st.session_state["history"] = df
    st.toast("📜 歷史紀錄同步")

# ==========================================
# § 3 業務工具函式
# ==========================================
def format_size(row) -> str:
    w, l = float(row.get("寬度mm", 0)), float(row.get("長度mm", 0))
    return f"{w}x{l}mm" if l > 0 else f"{w}mm"

def make_inventory_label(row, show_cost=False) -> str:
    sz = format_size(row)
    stock = int(float(row.get("庫存(顆)", 0)))
    elem = f"({row['五行']}) " if row['五行'] else ""
    cost = f" 💰${float(row['成本單價']):.2f}" if show_cost else ""
    return f"[{row['倉庫']}] {elem}{row['名稱']} {sz} ({row['形狀']}){cost} 【{row['批號']}】 | 存:{stock}"

def get_options(col_name: str, defaults: list, inv: pd.DataFrame) -> list:
    existing = {str(v).strip() for v in inv[col_name].unique() if str(v).strip() and str(v).lower() not in ("nan", "0", "0.0")}
    return [MANUAL] + sorted(existing | set(defaults))

# ==========================================
# § 4 初始化
# ==========================================
st.set_page_config(page_title="IF Crystal 全雲端系統", layout="wide")

if "inventory" not in st.session_state: st.session_state["inventory"] = load_inventory()
if "history" not in st.session_state: st.session_state["history"] = load_history()
if "admin_mode" not in st.session_state: st.session_state["admin_mode"] = False
if "current_design" not in st.session_state: st.session_state["current_design"] = []
if "order_id_input" not in st.session_state: st.session_state["order_id_input"] = f"DES-{date.today().strftime('%Y%m%d')}"
if "order_note_input" not in st.session_state: st.session_state["order_note_input"] = ""

with st.sidebar:
    st.header("🔑 權限控制")
    pwd = st.text_input("主管密碼", type="password")
    st.session_state["admin_mode"] = (pwd == "admin123")
    page = st.radio("功能前往", ["📦 庫存與進貨", "📜 紀錄查詢", "🧮 領料與設計單"])
    if st.button("🔄 強制重整"):
        st.session_state.clear()
        st.rerun()

# ==========================================
# § 5 庫存與進貨頁面
# ==========================================
if page == "📦 庫存與進貨":
    tab_r, tab_c, tab_u, tab_e = st.tabs(["🔄 補貨", "✨ 建檔", "📤 領用", "🛠️ 修改"])
    
    with tab_r: # 🔄 補貨
        inv = st.session_state["inventory"]
        if not inv.empty:
            df_l = inv.copy()
            df_l["display"] = df_l.apply(lambda r: make_inventory_label(r, st.session_state["admin_mode"]), axis=1)
            sel = st.selectbox("選擇商品", df_l["display"].tolist(), key="r_sel")
            idx = df_l[df_l["display"] == sel].index[0]
            row = inv.loc[idx]
            with st.form("r_form"):
                st.info(f"品名：{row['名稱']} | 目前單價：${row['成本單價']}")
                c1, c2, c3 = st.columns(3)
                qty = c1.number_input("進貨數量", 1, value=1)
                price = c2.number_input("本次進貨總價", 0.0)
                mode = c3.radio("方式", ["➕ 合併", "📦 新批號"])
                batch = st.text_input("批號", f"{date.today().strftime('%Y%m%d')}-A") if mode == "📦 新批號" else row["批號"]
                if st.form_submit_button("確認進貨"):
                    unit_cost = round(price / qty, 2) if qty > 0 else 0
                    if mode == "➕ 合併":
                        st.session_state["inventory"].at[idx, "庫存(顆)"] += qty
                        st.session_state["inventory"].at[idx, "成本單價"] = unit_cost
                    else:
                        new_r = row.copy()
                        new_r.update({"批號": batch, "進貨數量(顆)": qty, "庫存(顆)": qty, "成本單價": unit_cost, "進貨日期": str(date.today())})
                        st.session_state["inventory"] = pd.concat([st.session_state["inventory"], pd.DataFrame([new_r])], ignore_index=True)
                    log = {"紀錄時間": datetime.now().strftime("%Y-%m-%d %H:%M"), "單號": "IN", "動作": f"補貨({mode})", "倉庫": row["倉庫"], "批號": batch, "編號": row["編號"], "名稱": row["名稱"], "數量變動": qty, "成本備註": f"總價${price}"}
                    st.session_state["history"] = pd.concat([st.session_state['history'], pd.DataFrame([log])], ignore_index=True)
                    save_inventory(st.session_state["inventory"]); save_history(st.session_state["history"])
                    st.rerun()

    with tab_c: # ✨ 建檔
        inv = st.session_state["inventory"]
        with st.form("c_form"):
            c1, c2, c3 = st.columns(3)
            wh = c1.selectbox("倉庫", DEFAULT_WAREHOUSES, key="c_wh")
            n_opts = get_options("名稱", ["水晶"], inv)
            n_sel = c2.selectbox("名稱 (選單)", n_opts, key="c_n_sel")
            n_man = c2.text_input("或手動輸入名稱", key="c_n_man")
            cat = c3.selectbox("分類", ["天然石", "配件", "耗材"], key="c_cat")
            c4, c5, c6 = st.columns(3)
            sh_opts = get_options("形狀", DEFAULT_SHAPES, inv)
            sh_sel = c4.selectbox("形狀 (選單)", sh_opts, key="c_sh_sel")
            sh_man = c4.text_input("或手動輸入形狀", key="c_sh_man")
            el_opts = get_options("五行", DEFAULT_ELEMENTS, inv)
            el_sel = c5.selectbox("五行 (選單)", el_opts, key="c_el_sel")
            el_man = c5.text_input("或手動輸入五行", key="c_el_man")
            su_opts = get_options("進貨廠商", DEFAULT_SUPPLIERS, inv)
            su_sel = c6.selectbox("廠商 (選單)", su_opts, key="c_su_sel")
            su_man = c6.text_input("或手動輸入廠商", key="c_su_man")
            c7, c8, c9, c10 = st.columns(4)
            w, l, q, p = c7.number_input("寬度mm", 0.0), c8.number_input("長度mm", 0.0), c9.number_input("初始數量", 1), c10.number_input("總成本", 0.0)
            if st.form_submit_button("✅ 建立商品"):
                fn, fsu = (n_man if n_sel == MANUAL else n_sel), (su_man if su_sel == MANUAL else su_sel)
                if not fn or not fsu: st.error("名稱與廠商必填"); st.stop()
                new_item = {"編號": f"ST{uuid.uuid4().hex[:8].upper()}", "批號": "初始存貨", "倉庫": wh, "分類": cat, "名稱": fn, "形狀": (sh_man if sh_sel == MANUAL else sh_sel), "五行": (el_man if el_sel == MANUAL else el_sel), "寬度mm": w, "長度mm": l, "進貨數量(顆)": q, "庫存(顆)": q, "成本單價": round(p/q, 2) if q>0 else 0, "進貨廠商": fsu, "進貨日期": str(date.today())}
                st.session_state["inventory"] = pd.concat([st.session_state["inventory"], pd.DataFrame([new_item])], ignore_index=True)
                save_inventory(st.session_state["inventory"]); st.rerun()

    with tab_e: # 🛠️ 修改 (修正手動輸入顯示)
        inv = st.session_state["inventory"]
        if not inv.empty:
            df_l = inv.copy()
            df_l["display"] = df_l.apply(lambda r: make_inventory_label(r, True), axis=1)
            esel = st.selectbox("選擇修改商品", df_l["display"].tolist(), key="e_sel")
            eidx = df_l[df_l["display"] == esel].index[0]
            erow = inv.loc[eidx]

            # 選單在表單外確保即時重新渲染
            c1, c2, c3 = st.columns(3)
            me_opts = get_options("名稱", ["水晶"], inv)
            me_sel = c1.selectbox("名稱選單", me_opts, index=me_opts.index(erow['名稱']) if erow['名稱'] in me_opts else 0, key="me_sel")
            me_final = st.text_input("新名稱", key="me_man") if me_sel == MANUAL else me_sel

            sh_opts = get_options("形狀", DEFAULT_SHAPES, inv)
            sh_sel = c2.selectbox("形狀選單", sh_opts, index=sh_opts.index(erow['形狀']) if erow['形狀'] in sh_opts else 0, key="sh_sel")
            sh_final = st.text_input("新規格", key="sh_man") if sh_sel == MANUAL else sh_sel

            el_opts = get_options("五行", DEFAULT_ELEMENTS, inv)
            el_sel = c3.selectbox("五行選單", el_opts, index=el_opts.index(erow['五行']) if erow['五行'] in el_opts else 0, key="el_sel")
            el_final = st.text_input("新顏色", key="el_man") if el_sel == MANUAL else el_sel

            with st.form("e_form"):
                cc1, cc2, cc3, cc4 = st.columns(4)
                ew = cc1.number_input("寬度", value=float(erow["寬度mm"]))
                el = cc2.number_input("長度", value=float(erow["長度mm"]))
                eq = cc3.number_input("庫存", value=int(erow["庫存(顆)"]))
                ep = cc4.number_input("成本單價", value=float(erow["成本單價"]), step=0.1)
                if st.form_submit_button("💾 儲存修改"):
                    st.session_state["inventory"].at[eidx, "名稱"] = me_final
                    st.session_state["inventory"].at[eidx, "形狀"] = sh_final
                    st.session_state["inventory'].at[eidx, "五行"] = el_final
                    st.session_state["inventory"].at[eidx, "寬度mm"] = ew
                    st.session_state["inventory"].at[eidx, "長度mm"] = el
                    st.session_state["inventory"].at[eidx, "庫存(顆)"] = eq
                    st.session_state["inventory"].at[eidx, "成本單價"] = ep
                    save_inventory(st.session_state["inventory"]); st.rerun()

    st.subheader("📊 目前庫存表")
    st.dataframe(st.session_state["inventory"], use_container_width=True)

# ==========================================
# § 6 紀錄查詢頁面
# ==========================================
elif page == "📜 紀錄查詢":
    st.subheader("📜 歷史紀錄")
    df_h = st.session_state["history"]
    if not df_h.empty:
        st.dataframe(df_h.iloc[::-1], use_container_width=True)

# ==========================================
# § 7 領料與設計單頁面 (修復數量與小計顯示)
# ==========================================
elif page == "🧮 領料與設計單":
    st.subheader("🧮 設計單模式")
    ca, cb = st.columns([1, 2])
    oid = ca.text_input("單號", st.session_state["order_id_input"])
    note = cb.text_input("備註", st.session_state["order_note_input"])
    
    inv = st.session_state["inventory"]
    df_l = inv.copy()
    df_l["display"] = df_l.apply(lambda r: make_inventory_label(r, False), axis=1)
    sel = st.selectbox("選擇材料", df_l["display"].tolist(), key="d_sel")
    ridx = df_l[df_l["display"] == sel].index[0]
    row = inv.loc[ridx]
    
    qty = st.number_input("數量", 1, max_value=int(row["庫存(顆)"]), value=1)
    if st.button("⬇️ 加入清單"):
        st.session_state["current_design"].append({
            "idx": ridx, 
            "名稱": row["名稱"], 
            "規格": format_size(row), 
            "顏色": row["五行"], 
            "數量": qty, 
            "單價": float(row["成本單價"]), 
            "批號": row["批號"]
        })
        st.rerun()

    if st.session_state["current_design"]:
        st.write("---")
        total_p = 0
        for i, item in enumerate(st.session_state["current_design"]):
            item_total = item["單價"] * item["數量"]
            total_p += item_total
            cc1, cc2 = st.columns([5, 1])
            
            # 核心顯示邏輯：包含數量與小計
            cost_info = f" (💰單價:${item['單價']:.2f} | 小計:${item_total:.2f})" if st.session_state["admin_mode"] else ""
            cc1.write(f"🔸 [{item['顏色']}] **{item['名稱']}** ({item['規格']}) x{item['數量']} | {item['批號']}{cost_info}")
            
            if cc2.button("🗑️", key=f"del_{i}"):
                st.session_state["current_design"].pop(i)
                st.rerun()
        
        if st.session_state["admin_mode"]: 
            st.metric("預估總成本", f"${total_p:.2f}")
        
        if st.button("✅ 確認領出 (扣庫存)", type="primary", use_container_width=True):
            for item in st.session_state["current_design"]:
                st.session_state["inventory"].at[item["idx"], "庫存(顆)"] -= item["數量"]
                log = {"紀錄時間": datetime.now().strftime("%Y-%m-%d %H:%M"), "單號": oid, "動作": "設計領料", "倉庫": "庫存", "名稱": item["名稱"], "數量變動": -item["數量"], "成本備註": note}
                st.session_state["history"] = pd.concat([st.session_state["history"], pd.DataFrame([log])], ignore_index=True)
            save_inventory(st.session_state["inventory"])
            save_history(st.session_state["history"])
            st.session_state["current_design"] = []
            st.success("✅ 領料完成！")
            time.sleep(1)
            st.rerun()
