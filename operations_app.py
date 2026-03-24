import streamlit as st
import pandas as pd
from datetime import date, datetime
import time
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import numpy as np

# ==========================================
# 1. 核心設定 (省略重複的設定與連線函式以節省空間...)
# ==========================================
SHEET_ID = "1gf-pn034w0oZx8jWDUJvmIyHX_O7eHbiBb9diVSBX0Q"
KEY_FILE = "google_key.json"

COLUMNS = ['編號', '批號', '倉庫', '分類', '名稱', '寬度mm', '長度mm', '形狀', '五行', '進貨數量(顆)', '進貨日期', '進貨廠商', '庫存(顆)', '成本單價']
HISTORY_COLUMNS = ['紀錄時間', '單號', '動作', '倉庫', '批號', '編號', '分類', '名稱', '規格', '廠商', '數量變動', '成本備註']

DEFAULT_WAREHOUSES = ["Imeng", "千畇"]
DEFAULT_SUPPLIERS = ["小聰頭", "廠商A", "廠商B", "自用", "蝦皮", "淘寶", "TB-東吳天然石坊", "永安", "Rich"]
DEFAULT_SHAPES = ["圓珠", "切角", "鑽切", "圓筒", "方體", "長柱", "不規則", "造型", "原礦"]
DEFAULT_ELEMENTS = ["金", "木", "水", "火", "土", "綜合", "銀", "銅", "14K包金"]

# 連線與讀取函式保持不變...
def get_google_sheet_client():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    try:
        if "gcp_service_account" in st.secrets:
            creds_dict = dict(st.secrets["gcp_service_account"])
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        else:
            creds = ServiceAccountCredentials.from_json_keyfile_name(KEY_FILE, scope)
    except:
        creds = ServiceAccountCredentials.from_json_keyfile_name(KEY_FILE, scope)
    client = gspread.authorize(creds)
    return client

def load_inventory_from_gsheet():
    try:
        client = get_google_sheet_client()
        sheet = client.open_by_key(SHEET_ID).sheet1
        data = sheet.get_all_records()
        if not data: return pd.DataFrame(columns=COLUMNS)
        df = pd.DataFrame(data)
        df.columns = df.columns.astype(str).str.strip().str.replace('\ufeff', '')
        for col in COLUMNS:
            if col not in df.columns: df[col] = ""
        df = df[COLUMNS].copy().fillna("")
        for col in ['寬度mm', '長度mm', '進貨數量(顆)', '庫存(顆)', '成本單價']:
            df[col] = pd.to_numeric(df[col].astype(str).str.replace(',', '').str.strip(), errors='coerce').fillna(0)
        return df
    except Exception as e:
        st.error(f"❌ 無法讀取庫存表: {e}"); return pd.DataFrame(columns=COLUMNS)

def save_inventory_to_gsheet(df):
    try:
        client = get_google_sheet_client()
        sheet = client.open_by_key(SHEET_ID).sheet1
        sheet.clear()
        update_data = [df.columns.values.tolist()] + df.astype(str).values.tolist()
        sheet.update(range_name='A1', values=update_data)
        st.toast("☁️ 庫存同步成功")
    except Exception as e: 
        st.error(f"❌ 庫存存檔失敗: {e}"); st.stop()

def get_dynamic_options(col_name, default_list):
    options = set(default_list)
    if 'inventory' in st.session_state and not st.session_state['inventory'].empty:
        existing_values = st.session_state['inventory'][col_name].astype(str).unique()
        for v in existing_values:
            if v.strip() and v.lower() != 'nan' and v != '0' and v != '0.0':
                options.add(v.strip())
    return ["➕ 手動輸入"] + sorted(list(options))

def format_size(row):
    try:
        w, l = float(row.get('寬度mm', 0)), float(row.get('長度mm', 0))
        if l > 0: return f"{w}x{l}mm"
        if w > 0: return f"{w}mm"
        return "0mm"
    except: return "0mm"

def make_inventory_label(row):
    sz = format_size(row)
    stock_val = int(float(row.get('庫存(顆)', 0)))
    elem = str(row.get('五行', '')).strip()
    elem_display = f"({elem}) " if elem else ""
    batch = str(row.get('批號', '')).strip()
    cost_str = f" 💰${float(row.get('成本單價', 0)):.2f}" if st.session_state.get('admin_mode', False) else ""
    return f"[{row.get('倉庫','Imeng')}] {elem_display}{row.get('名稱','')} {sz} ({row.get('形狀','')}) {cost_str} 【{batch}】 | 存:{stock_val}"

# --- UI 開始 ---
st.set_page_config(page_title="IF Crystal 全雲端系統", layout="wide")

if 'inventory' not in st.session_state:
    st.session_state['inventory'] = load_inventory_from_gsheet()
if 'admin_mode' not in st.session_state: st.session_state['admin_mode'] = False
if 'current_design' not in st.session_state: st.session_state['current_design'] = []

st.title("💎 IF Crystal 全雲端系統 (v9.12-修正版)")

with st.sidebar:
    st.header("🔑 權限控制")
    pwd = st.text_input("主管密碼", type="password")
    st.session_state['admin_mode'] = (pwd == "admin123")
    st.divider()
    page = st.radio("功能前往", ["📦 庫存與進貨", "📜 紀錄查詢", "🧮 領料與設計單"])
    if st.button("🔄 強制重整"): st.session_state.clear(); st.rerun()

if page == "📦 庫存與進貨":
    tab1, tab2, tab4, tab3 = st.tabs(["🔄 補貨", "✨ 建檔", "📤 領用", "🛠️ 修改"])
    
    # 建檔分頁 (Tab 2) 保持不變...
    with tab2:
        with st.form("new_item"):
            # (建檔表單代碼，包含所有手動輸入框...)
            pass

    # 修改分頁 (Tab 3) - 【核心修正處】
    with tab3:
        if not st.session_state['inventory'].empty:
            inv_edit = st.session_state['inventory'].copy()
            inv_edit['label'] = inv_edit.apply(make_inventory_label, axis=1)
            edit_target = st.selectbox("選擇修改項目", inv_edit['label'].tolist())
            idx = inv_edit[inv_edit['label'] == edit_target].index[0]
            e_row = st.session_state['inventory'].loc[idx]
            
            with st.form("edit_form"):
                c1, c2, c3 = st.columns(3)
                
                # 名稱修改與記憶選單 【修正點：加入手動輸入框顯示】
                with c1:
                    me_opts = get_dynamic_options('名稱', ["水晶"])
                    me_sel = st.selectbox("名稱 (選單)", me_opts, index=me_opts.index(e_row['名稱']) if e_row['名稱'] in me_opts else 0)
                    me_custom = ""
                    if me_sel == "➕ 手動輸入":
                        me_custom = st.text_input("新名稱")
                    me_final = me_custom if me_sel == "➕ 手動輸入" else me_sel
                    
                ew, el = c2.number_input("寬度mm", value=float(e_row['寬度mm'])), c3.number_input("長度mm", value=float(e_row['長度mm']))
                
                c4, c5, c6, c7 = st.columns(4)
                
                # 形狀修改與記憶選單 【修正點：加入手動輸入框顯示】
                with c4:
                    sh_m_opts = get_dynamic_options('形狀', DEFAULT_SHAPES)
                    sh_m_sel = st.selectbox("形狀/規格", sh_m_opts, index=sh_m_opts.index(e_row['形狀']) if e_row['形狀'] in sh_m_opts else 0)
                    sh_m_custom = ""
                    if sh_m_sel == "➕ 手動輸入":
                        sh_m_custom = st.text_input("新規格")
                    sh_m_final = sh_m_custom if sh_m_sel == "➕ 手動輸入" else sh_m_sel
                    
                # 五行修改與記憶選單 【修正點：加入手動輸入框顯示】
                with c5:
                    el_m_opts = get_dynamic_options('五行', DEFAULT_ELEMENTS)
                    el_m_sel = st.selectbox("五行/顏色", el_m_opts, index=el_m_opts.index(e_row['五行']) if e_row['五行'] in el_m_opts else 0)
                    el_m_custom = ""
                    if el_m_sel == "➕ 手動輸入":
                        el_m_custom = st.text_input("新顏色")
                    el_m_final = el_m_custom if el_m_sel == "➕ 手動輸入" else el_m_sel
                    
                en6, en7 = c6.number_input("修正庫存", value=int(e_row['庫存(顆)'])), c7.number_input("單價成本", value=float(e_row['成本單價']))
                
                if st.form_submit_button("💾 儲存修改"):
                    # 確保寫回的是最終確定的變數
                    st.session_state['inventory'].at[idx, '名稱'] = me_final
                    st.session_state['inventory'].at[idx, '寬度mm'], st.session_state['inventory'].at[idx, '長度mm'] = ew, el
                    st.session_state['inventory'].at[idx, '形狀'], st.session_state['inventory'].at[idx, '五行'] = sh_m_final, el_m_final
                    st.session_state['inventory'].at[idx, '庫存(顆)'], st.session_state['inventory'].at[idx, '成本單價'] = en6, en7
                    
                    save_inventory_to_gsheet(st.session_state['inventory'])
                    st.success("✅ 修改已成功存入雲端！")
                    time.sleep(1)
                    st.rerun()

    st.divider()
    st.subheader("📊 目前庫存表")
    st.dataframe(st.session_state['inventory'], use_container_width=True)

# ... (其餘頁面代碼保持不變)
