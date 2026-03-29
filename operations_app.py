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
        st.error("Google 授權失敗，請檢查 Secret 設定"); st.stop()

def load_data(tab=None):
    try:
        ws = get_client().open_by_key(SHEET_ID).worksheet(tab) if tab else get_client().open_by_key(SHEET_ID).sheet1
        return pd.DataFrame(ws.get_all_records())
    except:
        return pd.DataFrame(columns=COLUMNS)

def save_data(df, tab=None):
    ws = get_client().open_by_key(SHEET_ID).worksheet(tab) if tab else get_client().open_by_key(SHEET_ID).sheet1
    ws.clear()
    ws.update(range_name="A1", values=[df.columns.tolist()] + df.astype(str).values.tolist())

# --- 3. 初始化 ---
st.set_page_config(page_title="IF Crystal 系統", layout="wide")
if "inventory" not in st.session_state: st.session_state["inventory"] = load_data()
if "current_design" not in st.session_state: st.session_state["current_design"] = []
if "admin_mode" not in st.session_state: st.session_state["admin_mode"] = False

# --- 4. 側邊欄 ---
with st.sidebar:
    st.title("💎 管理後台")
    pwd = st.text_input("主管密碼", type="password")
    st.session_state["admin_mode"] = (pwd == "admin123")
    page = st.radio("前往頁面", ["📦 庫存管理", "🧮 設計領料", "📜 歷史紀錄"])
    if st.button("🔄 強制刷新系統"):
        st.session_state.clear()
        st.rerun()

# --- 5. 頁面邏輯：設計領料 (核心修正) ---
if page == "🧮 設計領料":
    st.header("🧮 設計單領料模式")
    
    # 單號與備註
    c1, c2 = st.columns([1, 2])
    oid = c1.text_input("設計單號", f"DES-{date.today().strftime('%m%d')}")
    note = c2.text_input("領料備註 (客戶/用途)")

    # 【重要】優先渲染已加入的清單，確保不會消失
    if st.session_state["current_design"]:
        st.subheader("🛒 目前待領清單")
        total_cost = 0.0
        # 建立一個容器來鎖定清單顯示
        design_container = st.container(border=True)
        with design_container:
            for i, item in enumerate(st.session_state["current_design"]):
                # 計算小計
                sub = float(item.get("單價", 0)) * int(item.get("數量", 0))
                total_cost += sub
                
                # 顯示單行
                col_info, col_del = st.columns([6, 1])
                admin_txt = f" (小計: ${sub:.2f})" if st.session_state["admin_mode"] else ""
                col_info.markdown(f"🔸 **[{item.get('顏色', '無')}] {item.get('名稱', '無')}** | {item.get('規格', '0mm')} x **{item.get('數量', 0)}**{admin_txt}")
                
                if col_del.button("🗑️", key=f"del_{i}_{time.time()}"):
                    st.session_state["current_design"].pop(i)
                    st.rerun()
        
        # 總計與提交
        st.write(f"### 總計品項: {len(st.session_state['current_design'])} 件")
        if st.session_state["admin_mode"]:
            st.write(f"💰 **預估總成本: ${total_cost:.2f}**")
        
        if st.button("🚀 確認領出 (扣除雲端庫存)", type="primary", use_container_width=True):
            for it in st.session_state["current_design"]:
                st.session_state["inventory"].at[it["idx"], "庫存(顆)"] -= it["數量"]
            save_data(st.session_state["inventory"])
            st.session_state["current_design"] = []
            st.success("✅ 領料成功！庫存已扣除。")
            time.sleep(1.5)
            st.rerun()
    else:
        st.info("💡 目前清單是空的，請從下方選擇材料加入。")

    st.divider()

    # 材料選擇區 (放在下方)
    st.subheader("🔍 選擇材料加入")
    inv = st.session_state["inventory"]
    if not inv.empty:
        # 建立易讀的標籤
        inv["label"] = inv.apply(lambda r: f"[{r['倉庫']}] ({r['五行']}) {r['名稱']} {r['寬度mm']}mm | 存:{r['庫存(顆)']}", axis=1)
        sel_label = st.selectbox("搜尋材料名稱/規格", inv["label"].tolist(), key="material_sel")
        
        target_idx = inv[inv["label"] == sel_label].index[0]
        target_row = inv.loc[target_idx]
        
        col_q, col_btn = st.columns([1, 1])
        pick_qty = col_q.number_input("輸入要領取的數量", 1, max_value=max(1, int(target_row["庫存(顆)"])), key="pick_qty")
        
        if col_btn.button("➕ 加入待領清單", use_container_width=True):
            # 直接存入最簡單的欄位
            st.session_state["current_design"].append({
                "idx": target_idx,
                "名稱": target_row["名稱"],
                "顏色": target_row["五行"],
                "規格": f"{target_row['寬度mm']}mm",
                "數量": pick_qty,
                "單價": target_row["成本單價"]
            })
            st.toast(f"已加入: {target_row['名稱']}")
            st.rerun()

# --- 6. 其他頁面 ---
elif page == "📦 庫存管理":
    st.header("📦 雲端庫存總覽")
    st.dataframe(st.session_state["inventory"], use_container_width=True)

elif page == "📜 歷史紀錄":
    st.header("📜 歷史紀錄查詢")
    st.dataframe(load_data("History").iloc[::-1], use_container_width=True)
