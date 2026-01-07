import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import date, datetime
import time
import io

# ==========================================
# 1. 系統設定 (成本版)
# ==========================================
PAGE_TITLE = "numbertalk 成本與採購系統"
SPREADSHEET_NAME = "numbertalk-system" 

# ==========================================
# 2. Google Sheet 連線核心
# ==========================================
SCOPE = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']

@st.cache_resource
def get_client():
    try:
        creds_dict = st.secrets["gcp_service_account"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, SCOPE)
        client = gspread.authorize(creds)
        return client
    except Exception as e:
        st.error(f"❌ 連線失敗: {e}")
        return None

def get_worksheet(sheet_name):
    client = get_client()
    if not client: return None
    try:
        sh = client.open(SPREADSHEET_NAME)
        return sh.worksheet(sheet_name)
    except Exception as e:
        st.error(f"❌ 讀取錯誤 ({sheet_name}): {e}")
        return None

@st.cache_data(ttl=5)
def load_data(sheet_name):
    ws = get_worksheet(sheet_name)
    if not ws: return pd.DataFrame()
    data = ws.get_all_records()
    return pd.DataFrame(data)

def clear_cache():
    load_data.clear()

# ==========================================
# 3. 核心邏輯
# ==========================================

# --- 廠商管理 ---
def add_supplier(name, contact, phone, note):
    ws = get_worksheet("Suppliers")
    if not ws: return False, "連線失敗"
    df = load_data("Suppliers")
    if not df.empty and name in df['name'].astype(str).values:
        return False, "廠商名稱已存在"
    
    ws.append_row([name, contact, phone, note])
    clear_cache()
    return True, "成功"

def delete_supplier(name):
    ws = get_worksheet("Suppliers")
    try:
        cell = ws.find(name)
        ws.delete_rows(cell.row)
        clear_cache()
        return True, "已刪除"
    except:
        return False, "刪除失敗"

# --- 成本紀錄 (修改邏輯：輸入總價 -> 算單價) ---
def add_cost_log(date_str, sku, supplier, qty, total_cost, note):
    ws = get_worksheet("Cost_Log")
    
    # 自動計算平均單價 (防呆：數量為0時單價為0)
    unit_cost = float(total_cost) / float(qty) if float(qty) > 0 else 0.0
    
    # 寫入資料
    ws.append_row([
        str(date_str), str(sku), supplier, float(qty), float(unit_cost), float(total_cost), note, str(datetime.now())
    ])
    clear_cache()
    return True, "紀錄成功"

def delete_cost_log(row_id_val):
    ws = get_worksheet("Cost_Log")
    try:
        cell = ws.find(str(row_id_val))
        ws.delete_rows(cell.row)
        clear_cache()
        return True, "已刪除"
    except Exception as e:
        return False, f"刪除失敗: {e}"

# --- 報表 ---
def get_cost_summary():
    df = load_data("Cost_Log")
    if df.empty: return pd.DataFrame()
    
    df['total_cost'] = pd.to_numeric(df['total_cost'], errors='coerce').fillna(0)
    df['qty'] = pd.to_numeric(df['qty'], errors='coerce').fillna(0)
    
    summary = df.groupby('sku').agg({
        'total_cost': 'sum',
        'qty': 'sum',
        'unit_cost': 'mean' 
    }).reset_index()
    
    summary['加權平均成本'] = summary['total_cost'] / summary['qty']
    
    df_prod = load_data("Products")
    if not df_prod.empty:
        df_prod['sku'] = df_prod['sku'].astype(str)
        summary['sku'] = summary['sku'].astype(str)
        summary = pd.merge(summary, df_prod[['sku', 'name', 'series']], on='sku', how='left')
    
    return summary

def to_excel_download(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False)
    return output.getvalue()

# ==========================================
# 4. 介面 UI
# ==========================================
st.set_page_config(page_title=PAGE_TITLE, layout="wide", page_icon="💰")
st.title(f"💰 {PAGE_TITLE}")

if "gcp_service_account" not in st.secrets:
    st.error("❌ 未偵測到 secrets 設定。")
    st.stop()

with st.sidebar:
    st.header("功能選單")
    page = st.radio("前往", ["🏭 廠商管理", "📝 進貨成本登錄", "📊 成本分析報表"])
    st.divider()
    if st.button("🔄 重新讀取"):
        clear_cache()
        st.rerun()

# --- 1. 廠商管理 ---
if page == "🏭 廠商管理":
    st.subheader("🏭 廠商資料庫")
    
    with st.form("add_sup"):
        c1, c2 = st.columns(2)
        name = c1.text_input("廠商名稱 *必填")
        contact = c2.text_input("聯絡人")
        c3, c4 = st.columns(2)
        phone = c3.text_input("電話/Line")
        note = c4.text_input("備註")
        
        if st.form_submit_button("新增廠商"):
            if name:
                s, m = add_supplier(name, contact, phone, note)
                if s: st.success("成功"); time.sleep(0.5); st.rerun()
                else: st.error(m)
            else: st.error("請輸入名稱")
    
    st.divider()
    df_sup = load_data("Suppliers")
    if not df_sup.empty:
        for i, row in df_sup.iterrows():
            c1, c2, c3, c4, c5 = st.columns([2, 1.5, 1.5, 2, 1])
            c1.markdown(f"**{row['name']}**")
            c2.text(row['contact'])
            c3.text(row['phone'])
            c4.text(row['note'])
            if c5.button("刪除", key=f"del_sup_{i}"):
                delete_supplier(row['name'])
                st.rerun()
            st.divider()

# --- 2. 進貨成本登錄 ---
elif page == "📝 進貨成本登錄":
    st.subheader("📝 批次進貨成本紀錄")
    
    df_prod = load_data("Products")
    df_sup = load_data("Suppliers")
    
    if df_prod.empty:
        st.warning("⚠️ 找不到商品資料，請先去庫存系統建立商品。")
    elif df_sup.empty:
        st.warning("⚠️ 尚未建立廠商，請先去「廠商管理」新增。")
    else:
        # ★ 修改重點1：選單顯示五欄資訊 (SKU | 系列 | 分類 | 品名 | 規格)
        # 先轉字串避免錯誤
        for col in ['sku', 'series', 'category', 'name', 'spec']:
            df_prod[col] = df_prod[col].astype(str)
            
        prod_list = df_prod['sku'] + " | " + df_prod['series'] + " | " + df_prod['category'] + " | " + df_prod['name'] + " | " + df_prod['spec']
        sup_list = df_sup['name'].tolist()
        
        with st.form("add_cost"):
            st.info("💡 商品選單格式： 貨號 | 系列 | 分類 | 品名 | 規格")
            c1, c2 = st.columns(2)
            sel_prod = c1.selectbox("選擇商品", prod_list)
            sel_sup = c2.selectbox("進貨廠商", sup_list)
            
            c3, c4, c5 = st.columns(3)
            d_val = c3.date_input("進貨日期", date.today())
            qty = c4.number_input("進貨數量", min_value=1)
            
            # ★ 修改重點2：改為輸入「總成本」，系統算單價
            total_cost = c5.number_input("本批總金額 (Total Cost)", min_value=0.0)
            
            note = st.text_input("批號/備註 (Batch No)")
            
            # 即時顯示計算結果
            if qty > 0:
                unit_cost_calc = total_cost / qty
                st.markdown(f"🧮 系統自動計算：平均單價為 **${unit_cost_calc:,.2f}**")
            
            if st.form_submit_button("💾 儲存紀錄"):
                sku = sel_prod.split(" | ")[0]
                s, m = add_cost_log(d_val, sku, sel_sup, qty, total_cost, note)
                if s: st.success(f"已儲存！單價 ${total_cost/qty:,.2f}"); time.sleep(0.5); st.rerun()
        
        st.divider()
        st.markdown("#### 🕒 最近登錄紀錄")
        df_log = load_data("Cost_Log")
        if not df_log.empty:
            df_log = df_log.sort_index(ascending=False).head(10)
            st.dataframe(df_log, use_container_width=True)

# --- 3. 成本報表 ---
elif page == "📊 成本分析報表":
    st.subheader("📊 成本分析")
    
    tab1, tab2 = st.tabs(["加權平均成本", "詳細流水帳"])
    
    with tab1:
        st.info("💡 加權平均成本 = 歷史總進貨金額 / 歷史總數量")
        df_sum = get_cost_summary()
        st.dataframe(df_sum, use_container_width=True)
        if not df_sum.empty:
            st.download_button("下載成本統計表", to_excel_download(df_sum), "Cost_Summary.xlsx")
            
    with tab2:
        df_log = load_data("Cost_Log")
        st.dataframe(df_log, use_container_width=True)
        if not df_log.empty:
            st.download_button("下載完整紀錄", to_excel_download(df_log), "Cost_Log_Full.xlsx")
