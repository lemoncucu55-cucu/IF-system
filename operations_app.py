import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import date, datetime
import uuid
import time

# --- 1. 核心設定 ---
SHEET_ID = "1gf-pn034w0oZx8jWDUJvmIyHX_O7eHbiBb9diVSBX0Q"
KEY_FILE = "google_key.json"
COLUMNS = ['編號', '批號', '倉庫', '分類', '名稱', '寬度mm', '長度mm', '形狀', '五行', '進貨數量(顆)', '進貨日期', '進貨廠商', '庫存(顆)', '成本單價']
HISTORY_COLUMNS = ['紀錄時間', '單號', '動作', '倉庫', '批號', '編號', '分類', '名稱', '規格', '廠商', '數量變動', '成本備註']
MANUAL = "➕ 手動輸入"

# --- 2. 連線函式 ---
@st.cache_resource
def get_client():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    try:
        if "gcp_service_account" in st.secrets:
            creds = ServiceAccountCredentials.from_json_keyfile_dict(dict(st.secrets["gcp_service_account"]), scope)
        else:
            creds = ServiceAccountCredentials.from_json_keyfile_name(KEY_FILE, scope)
        return gspread.authorize(creds)
    except:
        st.error("Google 授權失敗"); st.stop()

def load_data(tab=None):
    try:
        ws = get_client().open_by_key(SHEET_ID).worksheet(tab) if tab else get_client().open_by_key(SHEET_ID).sheet1
        df = pd.DataFrame(ws.get_all_records())
        if df.empty: return pd.DataFrame(columns=COLUMNS if not tab else HISTORY_COLUMNS)
        return df
    except: return pd.DataFrame(columns=COLUMNS if not tab else HISTORY_COLUMNS)

def save_data(df, tab=None):
    ws = get_client().open_by_key(SHEET_ID).worksheet(tab) if tab else get_client().open_by_key(SHEET_ID).sheet1
    ws.clear()
    ws.update(range_name="A1", values=[df.columns.tolist()] + df.astype(str).values.tolist())

# --- 3. 工具函式 ---
def fmt_sz(r):
    try:
        w, l = float(r.get('寬度mm', 0)), float(r.get('長度mm', 0))
        return f"{w}x{l}mm" if l > 0 else f"{w}mm"
    except: return "0mm"

def mk_label(r, admin=False):
    c = f" 💰${float(r.get('成本單價', 0)):.2f}" if admin else ""
    return f"[{r.get('倉庫','-')}] ({r.get('五行','-')}) {r.get('名稱','-')} {fmt_sz(r)} 【{r.get('批號','-')}】 | 存:{r.get('庫存(顆)',0)}{c}"

def get_opts(col, defaults, inv):
    exist = {str(v).strip() for v in inv[col].unique() if str(v).strip() and str(v).lower() not in ("nan", "0")}
    return [MANUAL] + sorted(exist | set(defaults))

# --- 4. 初始化 ---
st.set_page_config(page_title="IF Crystal 系統", layout="wide")
if "inventory" not in st.session_state: st.session_state["inventory"] = load_data()
if "current_design" not in st.session_state: st.session_state["current_design"] = []

# --- 5. 側邊欄 ---
with st.sidebar:
    st.header("🔑 權限控制")
    pwd = st.text_input("主管密碼", type="password")
    st.session_state["admin_mode"] = (pwd == "admin123")
    page = st.radio("前往頁面", ["📦 庫存管理", "🧮 設計領料", "📜 歷史紀錄"])
    if st.button("🔄 強制重整"): st.session_state.clear(); st.rerun()

# --- 6. 頁面邏輯 ---
if page == "📦 庫存管理":
    t1, t2, t3 = st.tabs(["🔄 補貨", "✨ 建檔", "🛠️ 修改"])
    inv = st.session_state["inventory"]
    
    with t1: # 補貨功能回歸
        if not inv.empty:
            df_l = inv.copy(); df_l["dp"] = df_l.apply(lambda r: mk_label(r, st.session_state["admin_mode"]), axis=1)
            sel = st.selectbox("選擇補貨商品", df_l["dp"].tolist(), key="r_sel")
            idx = df_l[df_l["dp"] == sel].index[0]; row = inv.loc[idx]
            with st.form("r_f"):
                st.info(f"補貨對象：{row['名稱']} | 目前成本：${row['成本單價']}")
                qty = st.number_input("進貨數量", 1); pri = st.number_input("本次進貨總價", 0.0)
                if st.form_submit_button("確認補貨"):
                    st.session_state["inventory"].at[idx, "庫存(顆)"] += qty
                    st.session_state["inventory"].at[idx, "成本單價"] = round(pri/qty, 2) if qty > 0 else 0
                    save_data(st.session_state["inventory"]); st.success("補貨成功！"); st.rerun()
                    
    with t2: # 建檔功能回歸
        with st.form("c_f"):
            c1, c2, c3 = st.columns(3)
            wh = c1.selectbox("倉庫", ["Imeng", "千畇"])
            n_sel = c2.selectbox("品名選單", get_opts("名稱", ["水晶"], inv))
            n_man = c2.text_input("手動輸入名稱")
            el_sel = c3.selectbox("五行選單", get_opts("五行", ["金","木","水","火","土"], inv))
            el_man = c3.text_input("手動輸入五行")
            qty = st.number_input("初始數量", 1)
            if st.form_submit_button("建立新商品"):
                name = n_man if n_sel == MANUAL else n_sel
                elem = el_man if el_sel == MANUAL else el_sel
                new_r = {"編號": f"ST{uuid.uuid4().hex[:5].upper()}", "批號": "初始", "倉庫": wh, "名稱": name, "五行": elem, "庫存(顆)": qty, "成本單價": 0, "寬度mm": 0, "長度mm": 0, "分類": "天然石", "形狀": "圓珠", "進貨廠商": "自用", "進貨數量(顆)": qty, "進貨日期": str(date.today())}
                st.session_state["inventory"] = pd.concat([inv, pd.DataFrame([new_r])], ignore_index=True)
                save_data(st.session_state["inventory"]); st.success(f"已建立：{name}"); st.rerun()

    with t3: # 修改功能
        if not inv.empty:
            df_l = inv.copy(); df_l["dp"] = df_l.apply(lambda r: mk_label(r, True), axis=1)
            sel_e = st.selectbox("修改項目", df_l["dp"].tolist(), key="e_sel")
            idx_e = df_l[df_l["dp"] == sel_e].index[0]
            with st.form("e_f"):
                new_n = st.text_input("品名修改", inv.at[idx_e, "名稱"])
                new_q = st.number_input("修正庫存", value=int(inv.at[idx_e, "庫存(顆)"]))
                if st.form_submit_button("儲存修改"):
                    st.session_state["inventory"].at[idx_e, "名稱"] = new_n
                    st.session_state["inventory"].at[idx_e, "庫存(顆)"] = new_q
                    save_data(st.session_state["inventory"]); st.rerun()

    st.divider()
    st.dataframe(st.session_state["inventory"], use_container_width=True)

elif page == "🧮 設計領料":
    st.header("🧮 設計單領料")
    # 這裡保留了 v10.11 的強化顯示邏輯
    if st.session_state["current_design"]:
        with st.container(border=True):
            st.subheader("🛒 待領清單明細")
            total_p = 0
            for i, item in enumerate(st.session_state["current_design"]):
                sub = float(item['單價']) * int(item['數量'])
                total_p += sub
                c_txt, c_del = st.columns([6, 1])
                c_txt.write(f"🔸 [{item['五行']}] **{item['名稱']}** ({item['規格']}) x{item['數量']} | 小計:${sub:.2f}")
                if c_del.button("🗑️", key=f"del_{i}"):
                    st.session_state["current_design"].pop(i); st.rerun()
            if st.session_state["admin_mode"]: st.write(f"💰 **總成本: ${total_p:.2f}**")
            if st.button("🚀 確認領出扣庫存", type="primary", use_container_width=True):
                for it in st.session_state["current_design"]:
                    st.session_state["inventory"].at[it["idx"], "庫存(顆)"] -= it["數量"]
                save_data(st.session_state["inventory"]); st.session_state["current_design"] = []; st.success("完成！"); st.rerun()

    st.divider()
    inv_d = st.session_state["inventory"]
    df_ld = inv_d.copy(); df_ld["dp"] = df_ld.apply(lambda r: mk_label(r), axis=1)
    sel_d = st.selectbox("搜尋材料", df_ld["dp"].tolist(), key="ds")
    idx_d = df_ld[df_ld["dp"] == sel_d].index[0]; row_d = inv_d.loc[idx_d]
    qty_d = st.number_input("數量", 1, max_value=max(1, int(row_d["庫存(顆)"])))
    if st.button("⬇️ 加入待領清單"):
        st.session_state["current_design"].append({"idx": idx_d, "名稱": row_d["名稱"], "五行": row_d["五行"], "數量": qty_d, "單價": float(row_d["成本單價"]), "規格": fmt_sz(row_d)})
        st.rerun()

elif page == "📜 歷史紀錄":
    st.dataframe(load_data("History").iloc[::-1], use_container_width=True)
