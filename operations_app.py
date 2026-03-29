from __future__ import annotations
import uuid
from datetime import date, datetime
import pandas as pd
import gspread
import streamlit as st
from oauth2client.service_account import ServiceAccountCredentials
import time

# § 1 常數設定
SHEET_ID = "1gf-pn034w0oZx8jWDUJvmIyHX_O7eHbiBb9diVSBX0Q"
KEY_FILE = "google_key.json"
COLUMNS = ['編號', '批號', '倉庫', '分類', '名稱', '寬度mm', '長度mm', '形狀', '五行', '進貨數量(顆)', '進貨日期', '進貨廠商', '庫存(顆)', '成本單價']
HISTORY_COLUMNS = ['紀錄時間', '單號', '動作', '倉庫', '批號', '編號', '分類', '名稱', '規格', '廠商', '數量變動', '成本備註']
MANUAL = "➕ 手動輸入"

# § 2 核心連線
@st.cache_resource
def _gs_client():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    try:
        if "gcp_service_account" in st.secrets:
            creds = ServiceAccountCredentials.from_json_keyfile_dict(dict(st.secrets["gcp_service_account"]), scope)
        else:
            creds = ServiceAccountCredentials.from_json_keyfile_name(KEY_FILE, scope)
    except:
        st.error("Google 連線失敗"); st.stop()
    return gspread.authorize(creds)

def load_data(tab=None):
    try:
        ws = _gs_client().open_by_key(SHEET_ID).worksheet(tab) if tab else _gs_client().open_by_key(SHEET_ID).sheet1
        df = pd.DataFrame(ws.get_all_records())
        if df.empty: return pd.DataFrame(columns=COLUMNS if not tab else HISTORY_COLUMNS)
        return df
    except: return pd.DataFrame(columns=COLUMNS if not tab else HISTORY_COLUMNS)

def save_data(df, tab=None):
    ws = _gs_client().open_by_key(SHEET_ID).worksheet(tab) if tab else _gs_client().open_by_key(SHEET_ID).sheet1
    ws.clear()
    ws.update(range_name="A1", values=[df.columns.tolist()] + df.astype(str).values.tolist())

# § 3 工具
def fmt_sz(r):
    try: return f"{r.get('寬度mm', 0)}x{r.get('長度mm', 0)}mm" if float(r.get('長度mm', 0)) > 0 else f"{r.get('寬度mm', 0)}mm"
    except: return "0mm"

def mk_label(r, admin=False):
    c = f" 💰${float(r.get('成本單價', 0)):.2f}" if admin else ""
    return f"[{r.get('倉庫', '庫')}] ({r.get('五行', '無')}) {r.get('名稱', '無')} {fmt_sz(r)} 【{r.get('批號', '批')}】 | 存:{r.get('庫存(顆)', 0)}{c}"

# § 4 初始化
st.set_page_config(page_title="IF Crystal 系統", layout="wide")
if "inventory" not in st.session_state: st.session_state["inventory"] = load_data()
if "current_design" not in st.session_state: st.session_state["current_design"] = []

with st.sidebar:
    st.session_state["admin_mode"] = (st.text_input("主管密碼", type="password") == "admin123")
    page = st.radio("前往", ["📦 庫存管理", "📜 紀錄查詢", "🧮 設計領料"])
    if st.button("🔄 重整系統"): st.session_state.clear(); st.rerun()

# --- 庫存管理 ---
if page == "📦 庫存管理":
    t1, t2, t3 = st.tabs(["🔄 補貨", "✨ 建檔", "🛠️ 修改"])
    inv = st.session_state["inventory"]
    with t1:
        if not inv.empty:
            df_l = inv.copy(); df_l["dp"] = df_l.apply(lambda r: mk_label(r, st.session_state["admin_mode"]), axis=1)
            sel = st.selectbox("選擇商品", df_l["dp"].tolist())
            idx = df_l[df_l["dp"] == sel].index[0]
            with st.form("r_f"):
                qty = st.number_input("進貨數量", 1); pri = st.number_input("總價", 0.0)
                if st.form_submit_button("確認補貨"):
                    st.session_state["inventory"].at[idx, "庫存(顆)"] += qty
                    st.session_state["inventory"].at[idx, "成本單價"] = round(pri/qty, 2) if qty > 0 else 0
                    save_data(st.session_state["inventory"]); st.rerun()
    with t2:
        with st.form("c_f"):
            c1, c2 = st.columns(2)
            name = c1.text_input("品名")
            elem = c2.text_input("五行/顏色")
            if st.form_submit_button("建立商品"):
                new_r = {"編號": f"ST{uuid.uuid4().hex[:5].upper()}", "批號": "初始", "倉庫": "Imeng", "名稱": name, "五行": elem, "庫存(顆)": 1, "成本單價": 0, "寬度mm": 0, "長度mm": 0, "分類": "天然石", "形狀": "圓珠", "進貨廠商": "自用", "進貨數量(顆)": 1, "進貨日期": str(date.today())}
                st.session_state["inventory"] = pd.concat([inv, pd.DataFrame([new_r])], ignore_index=True)
                save_data(st.session_state["inventory"]); st.rerun()
    st.dataframe(st.session_state["inventory"], use_container_width=True)

# --- 設計領料 (強制渲染修正版) ---
elif page == "🧮 設計領料":
    st.subheader("🧮 設計單領料")
    ca, cb = st.columns([1, 2])
    oid = ca.text_input("單號", f"DES-{date.today().strftime('%m%d')}")
    note = cb.text_input("備註")
    
    inv = st.session_state["inventory"]
    df_l = inv.copy(); df_l["dp"] = df_l.apply(lambda r: mk_label(r), axis=1)
    sel = st.selectbox("選擇材料", df_l["dp"].tolist())
    idx = df_l[df_l["dp"] == sel].index[0]; row = inv.loc[idx]
    
    qty = st.number_input("加入數量", 1, max_value=max(1, int(row["庫存(顆)"])))
    if st.button("⬇️ 加入待領清單"):
        st.session_state["current_design"].append({
            "idx": idx, "名稱": row["名稱"], "五行": row["五行"], 
            "數量": qty, "單價": float(row["成本單價"]), "規格": fmt_sz(row), "批號": row["批號"]
        })
        st.rerun()
    
    # 建立一個專門顯示清單的容器，確保 100% 渲染
    if st.session_state["current_design"]:
        st.write("---")
        st.markdown("### 🛒 待領清單明細")
        list_container = st.container()
        with list_container:
            total_p = 0
            for i, item in enumerate(st.session_state["current_design"]):
                # 相容性取值
                iname = item.get("名稱", "未知")
                ielem = item.get("五行", item.get("顏色", "無"))
                iqty = item.get("數量", 1)
                ipri = float(item.get("單價", 0))
                isz = item.get("規格", "0mm")
                
                sub = ipri * iqty
                total_p += sub
                
                c_text, c_del = st.columns([6, 1])
                cost_info = f" (小計: ${sub:.2f})" if st.session_state["admin_mode"] else ""
                c_text.markdown(f"🔸 [{ielem}] **{iname}** ({isz}) x{iqty}{cost_info}")
                if c_del.button("🗑️", key=f"del_{i}"):
                    st.session_state["current_design"].pop(i); st.rerun()
            
            st.divider()
            if st.session_state["admin_mode"]: st.metric("預估總成本", f"${total_p:.2f}")
            if st.button("✅ 確認領出 (扣庫存)", type="primary", use_container_width=True):
                for it in st.session_state["current_design"]:
                    st.session_state["inventory"].at[it["idx"], "庫存(顆)"] -= it["數量"]
                save_data(st.session_state["inventory"])
                st.session_state["current_design"] = []
                st.success("領料成功！"); time.sleep(1); st.rerun()

elif page == "📜 紀錄查詢":
    st.dataframe(load_data("History").iloc[::-1], use_container_width=True)
