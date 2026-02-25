import streamlit as st
import pandas as pd
from datetime import date, datetime
import time
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import numpy as np # 引入 numpy 處理 nan

# ==========================================
# 1. 核心設定
# ==========================================

SHEET_ID = "1gf-pn034w0oZx8jWDUJvmIyHX_O7eHbiBb9diVSBX0Q"
KEY_FILE = "google_key.json"

# 庫存表欄位 (順序必須與 Google Sheet 完全一致)
COLUMNS = [
    '編號', '批號', '倉庫', '分類', '名稱', 
    '寬度mm', '長度mm', '形狀', '五行', 
    '進貨數量(顆)', '進貨日期', '進貨廠商', 
    '庫存(顆)', '成本單價'
]

# 歷史紀錄欄位
HISTORY_COLUMNS = [
    '紀錄時間', '單號', '動作', '倉庫', '批號', '編號', '分類', '名稱', '規格', 
    '廠商', '數量變動', '成本備註'
]

DEFAULT_WAREHOUSES = ["Imeng", "千畇"]
DEFAULT_SUPPLIERS = ["小聰頭", "廠商A", "廠商B", "自用", "蝦皮", "淘寶", "TB-東吳天然石坊", "永安", "Rich"]
DEFAULT_SHAPES = ["圓珠", "切角", "鑽切", "圓筒", "方體", "長柱", "不規則", "造型", "原礦"]
DEFAULT_ELEMENTS = ["金", "木", "水", "火", "土", "綜合", "銀", "銅", "14K包金"]

# ==========================================
# 2. Google Sheets 連線與資料處理
# ==========================================

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

# --- 讀取庫存 (Sheet1) ---
def load_inventory_from_gsheet():
    try:
        client = get_google_sheet_client()
        sheet = client.open_by_key(SHEET_ID).sheet1
        data = sheet.get_all_records()
        if not data: return pd.DataFrame(columns=COLUMNS)
        
        df = pd.DataFrame(data)
        df.columns = df.columns.astype(str).str.strip().str.replace('\ufeff', '')
        
        if 'label' in df.columns: df = df.drop(columns=['label'])
        if '批號' not in df.columns: df['批號'] = '初始存貨'
        if '倉庫' not in df.columns: df.insert(1, '倉庫', 'Imeng')
        for col in COLUMNS:
            if col not in df.columns: df[col] = ""
            
        df = df[COLUMNS].copy().fillna("")
        df['名稱'] = df['名稱'].astype(str).str.strip()
        
        for col in ['寬度mm', '長度mm', '進貨數量(顆)', '庫存(顆)', '成本單價']:
            df[col] = pd.to_numeric(df[col].astype(str).str.replace(',', '').str.strip(), errors='coerce').fillna(0)
            
        return df
    except Exception as e:
        st.error(f"❌ 無法讀取庫存表: {e}"); return pd.DataFrame(columns=COLUMNS)

# --- 讀取歷史紀錄 (History) ---
def load_history_from_gsheet():
    try:
        client = get_google_sheet_client()
        try:
            sheet = client.open_by_key(SHEET_ID).worksheet("History")
        except:
            return pd.DataFrame(columns=HISTORY_COLUMNS)
        data = sheet.get_all_records()
        if not data: return pd.DataFrame(columns=HISTORY_COLUMNS)
        df = pd.DataFrame(data)
        for col in HISTORY_COLUMNS:
            if col not in df.columns: df[col] = ""
        return df[HISTORY_COLUMNS].copy()
    except Exception as e:
        st.error(f"❌ 無法讀取歷史紀錄: {e}"); return pd.DataFrame(columns=HISTORY_COLUMNS)

# --- 安全追加單行資料 ---
def append_inventory_row(new_row_dict):
    try:
        client = get_google_sheet_client()
        sheet = client.open_by_key(SHEET_ID).sheet1
        row_values = []
        for col in COLUMNS:
            val = new_row_dict.get(col, "")
            if pd.isna(val) or str(val).lower() == 'nan':
                if col in ['進貨數量(顆)', '庫存(顆)', '成本單價', '寬度mm', '長度mm']: val = 0
                else: val = ""
            row_values.append(str(val))
        sheet.append_row(row_values)
        st.toast("✅ 新資料已安全寫入雲端")
        return True
    except Exception as e:
        st.error(f"❌ 新增資料失敗: {e}")
        return False

# --- 存檔：庫存 ---
def save_inventory_to_gsheet(df):
    try:
        client = get_google_sheet_client()
        sheet = client.open_by_key(SHEET_ID).sheet1
        sheet.clear()
        update_data = [df.columns.values.tolist()] + df.astype(str).values.tolist()
        sheet.update(range_name='A1', values=update_data)
        st.toast("☁️ 庫存更新成功！")
    except Exception as e: 
        st.error(f"❌ 庫存存檔失敗: {e}"); st.stop()

# --- 存檔：歷史紀錄 ---
def save_history_to_gsheet(df):
    try:
        client = get_google_sheet_client()
        sheet = client.open_by_key(SHEET_ID).worksheet("History")
        sheet.clear()
        update_data = [df.columns.values.tolist()] + df.astype(str).values.tolist()
        sheet.update(range_name='A1', values=update_data)
    except Exception as e: st.error(f"❌ 歷史紀錄存檔失敗: {e}")

# ==========================================
# 3. 顯示與輔助函式
# ==========================================

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
    
    cost_str = ""
    if st.session_state.get('admin_mode', False):
        cost = float(row.get('成本單價', 0))
        if cost > 0: cost_str = f" 💰${cost:.2f}"

    return f"[{row.get('倉庫','Imeng')}] {elem_display}{row.get('名稱','')} {sz} ({row.get('形狀','')}) {cost_str} 【{batch}】 | 存:{stock_val}"

def get_dynamic_options(col, defaults):
    opts = set(defaults)
    if not st.session_state['inventory'].empty:
        raw = st.session_state['inventory'][col].astype(str).tolist()
        opts.update([x.strip() for x in raw if x.strip() and x.lower() != 'nan'])
    return ["➕ 手動輸入"] + sorted(list(opts))

# ==========================================
# 4. 初始化與 UI
# ==========================================

st.set_page_config(page_title="IF Crystal 全雲端系統", layout="wide")

if 'inventory' not in st.session_state:
    with st.spinner('連線雲端資料庫 (Inventory)...'):
        st.session_state['inventory'] = load_inventory_from_gsheet()

if 'history' not in st.session_state:
    with st.spinner('連線雲端紀錄 (History)...'):
        st.session_state['history'] = load_history_from_gsheet()

if 'admin_mode' not in st.session_state: st.session_state['admin_mode'] = False
if 'current_design' not in st.session_state: st.session_state['current_design'] = []
if 'order_id_input' not in st.session_state: st.session_state['order_id_input'] = f"DES-{date.today().strftime('%Y%m%d')}-{int(time.time())%1000}"
if 'order_note_input' not in st.session_state: st.session_state['order_note_input'] = ""

st.title("💎 IF Crystal 全雲端系統 (v9.12-彙整版)")

with st.sidebar:
    st.header("🔑 權限與統計")
    pwd = st.text_input("主管密碼", type="password")
    st.session_state['admin_mode'] = (pwd == "admin123")
    
    if st.session_state['admin_mode']:
        st.success("🔓 管理員模式")
        df_inv = st.session_state['inventory']
        if not df_inv.empty:
            total_cost = (df_inv['庫存(顆)'] * df_inv['成本單價']).sum()
            st.metric("💰 庫存總資產", f"${total_cost:,.2f}")
    else:
        st.info("🔒 訪客模式")

    st.divider()
    page = st.radio("功能前往", ["📦 庫存與進貨", "📜 紀錄查詢", "🧮 領料與設計單"])
    st.divider()
    if st.button("🔄 強制重整"): st.session_state.clear(); st.rerun()

# ------------------------------------------
# 頁面 A: 庫存管理
# ------------------------------------------
if page == "📦 庫存與進貨":
    tab1, tab2, tab4, tab3 = st.tabs(["🔄 補貨", "✨ 建檔", "📤 領用", "🛠️ 修改"])
    
    with tab1: # 補貨
        if not st.session_state['inventory'].empty:
            inv_sorted = st.session_state['inventory'].copy()
            inv_sorted['名稱'] = inv_sorted['名稱'].astype(str).str.strip()
            inv_sorted = inv_sorted.sort_values(by=['名稱', '寬度mm', '五行'])
            inv_sorted['label'] = inv_sorted.apply(make_inventory_label, axis=1)
            
            target = st.selectbox("選擇商品", inv_sorted['label'].tolist())
            idx = inv_sorted[inv_sorted['label'] == target].index[0]
            row = st.session_state['inventory'].loc[idx]
            
            with st.form("restock"):
                old_cost = float(row.get('成本單價', 0))
                elem_info = f" ({row.get('五行', '')})" if row.get('五行', '') else ""
                st.info(f"品名：{row['名稱']}{elem_info} | 目前單價成本：${old_cost:.2f}")
                
                c1, c2, c3 = st.columns(3)
                qty = c1.number_input("進貨數量", 1, value=1)
                total_cost_in = c2.number_input("💰 本次進貨總成本 (總價)", min_value=0.0, step=1.0)
                calc_unit_cost = total_cost_in / qty if qty > 0 else 0
                c2.caption(f"換算單價: ${calc_unit_cost:.2f} /顆")
                
                r_type = c3.radio("方式", ["➕ 合併 (更新成本)", "📦 新批號"])
                new_batch = st.text_input("新批號", f"{date.today().strftime('%Y%m%d')}-A") if r_type == "📦 新批號" else row['批號']

                if st.form_submit_button("確認進貨"):
                    final_unit_cost = total_cost_in / qty if qty > 0 else 0
                    if r_type == "➕ 合併 (更新成本)":
                        st.session_state['inventory'].at[idx, '庫存(顆)'] += qty
                        st.session_state['inventory'].at[idx, '成本單價'] = round(final_unit_cost, 2)
                        save_inventory_to_gsheet(st.session_state['inventory'])
                        log_act = f"補貨(總${total_cost_in:.2f})"
                    else:
                        new_r = row.copy()
                        new_r['庫存(顆)'] = int(qty)
                        new_r['進貨數量(顆)'] = int(qty)
                        new_r['進貨日期'] = str(date.today())
                        new_r['批號'] = new_batch
                        new_r['成本單價'] = round(final_unit_cost, 2)
                        success = append_inventory_row(new_r)
                        if success:
                            st.session_state['inventory'] = pd.concat([st.session_state['inventory'], pd.DataFrame([new_r])], ignore_index=True)
                            log_act = f"補貨新批(總${total_cost_in:.2f})"
                        else: st.stop()
                    
                    log = {'紀錄時間': datetime.now().strftime("%Y-%m-%d %H:%M"), '單號': 'IN', '動作': log_act, '倉庫': row['倉庫'], '批號': new_batch if r_type == "📦 新批號" else row['批號'], '編號': row['編號'], '分類': row['分類'], '名稱': row['名稱'], '規格': format_size(row), '廠商': row['進貨廠商'], '數量變動': qty, '成本備註': f"總${total_cost_in:.2f} (單${final_unit_cost:.2f})"}
                    st.session_state['history'] = pd.concat([st.session_state['history'], pd.DataFrame([log])], ignore_index=True)
                    save_history_to_gsheet(st.session_state['history'])
                    st.success(f"已更新！單價: ${final_unit_cost:.2f}"); st.rerun()

    with tab2: # 建檔 (邏輯同原本)
        with st.form("new_item"):
            c1, c2, c3 = st.columns(3)
            wh = c1.selectbox("倉庫", DEFAULT_WAREHOUSES)
            exist_names = sorted(list(set([x for x in st.session_state['inventory']['名稱'].astype(str) if x]))) if not st.session_state['inventory'].empty else []
            name_sel = c2.selectbox("名稱", ["➕ 手動輸入"] + exist_names)
            name = c2.text_input("輸入名稱") if name_sel == "➕ 手動輸入" else name_sel
            cat = c3.selectbox("分類", ["天然石", "配件", "耗材"])
            s1, s2, s3 = st.columns(3)
            w_mm = s1.number_input("寬度", 0.0); l_mm = s2.number_input("長度", 0.0)
            shape = s3.selectbox("形狀", get_dynamic_options('形狀', DEFAULT_SHAPES))
            if shape == "➕ 手動輸入": shape = st.text_input("形狀")
            c4, c5, c6 = st.columns(3)
            elem = c4.selectbox("五行", get_dynamic_options('五行', DEFAULT_ELEMENTS))
            if elem == "➕ 手動輸入": elem = st.text_input("五行")
            sup = c5.selectbox("廠商", get_dynamic_options('進貨廠商', DEFAULT_SUPPLIERS))
            if sup == "➕ 手動輸入": sup = st.text_input("廠商")
            c7, c8 = st.columns(2)
            qty_init = c7.number_input("初始數量", 1); total_cost_init = c8.number_input("💰 初始總成本", min_value=0.0, step=1.0)
            calc_init_unit = total_cost_init / qty_init if qty_init > 0 else 0
            batch = st.text_input("初始批號", f"{date.today().strftime('%Y%m%d')}-01")
            
            if st.form_submit_button("建立商品"):
                if not str(name).strip(): st.error("沒填名稱")
                else:
                    final_unit_cost = total_cost_init / qty_init if qty_init > 0 else 0
                    new_r = {'編號': f"ST{int(time.time())}", '批號': batch, '倉庫': wh, '分類': cat, '名稱': name, '寬度mm': w_mm, '長度mm': l_mm, '形狀': shape, '五行': elem, '進貨廠商': sup, '庫存(顆)': int(qty_init), '進貨數量(顆)': int(qty_init), '進貨日期': str(date.today()), '成本單價': round(final_unit_cost, 2)}
                    if append_inventory_row(new_r):
                        st.session_state['inventory'] = pd.concat([st.session_state['inventory'], pd.DataFrame([new_r])], ignore_index=True)
                        log = {'紀錄時間': datetime.now().strftime("%Y-%m-%d %H:%M"), '單號': 'NEW', '動作': '新商品', '倉庫': wh, '批號': batch, '編號': new_r['編號'], '分類': cat, '名稱': name, '規格': format_size(new_r), '廠商': sup, '數量變動': qty_init, '成本備註': f"總${total_cost_init:.2f} (單${final_unit_cost:.2f})"}
                        st.session_state['history'] = pd.concat([st.session_state['history'], pd.DataFrame([log])], ignore_index=True)
                        save_history_to_gsheet(st.session_state['history'])
                        st.success("已建檔！"); st.rerun()

    with tab4: # 領用 (單品)
        if not st.session_state['inventory'].empty:
            inv_sorted = st.session_state['inventory'].copy()
            inv_sorted['label'] = inv_sorted.apply(make_inventory_label, axis=1)
            target = st.selectbox("選擇商品", inv_sorted['label'].tolist(), key="out_sel")
            idx = inv_sorted[inv_sorted['label'] == target].index[0]
            row = st.session_state['inventory'].loc[idx]
            with st.form("out_form"):
                qty_o = st.number_input("出庫數量", 0, int(float(row['庫存(顆)'])))
                reason = st.selectbox("原因", ["商品", "自用", "損壞", "樣品", "調倉庫", "其它"])
                note_o = st.text_input("備註 (選填)")
                if st.form_submit_button("出庫"):
                    st.session_state['inventory'].at[idx, '庫存(顆)'] -= qty_o
                    save_inventory_to_gsheet(st.session_state['inventory'])
                    log = {'紀錄時間': datetime.now().strftime("%Y-%m-%d %H:%M"), '單號': 'OUT', '動作': f"出庫-{reason}", '倉庫': row['倉庫'], '批號': row['批號'], '編號': row['編號'], '分類': row['分類'], '名稱': row['名稱'], '規格': format_size(row), '廠商': row['進貨廠商'], '數量變動': -qty_o, '成本備註': note_o}
                    st.session_state['history'] = pd.concat([st.session_state['history'], pd.DataFrame([log])], ignore_index=True)
                    save_history_to_gsheet(st.session_state['history']); st.rerun()

    with tab3: # 修改 (盤點)
        if not st.session_state['inventory'].empty:
            inv_sorted = st.session_state['inventory'].copy()
            inv_sorted['label'] = inv_sorted.apply(make_inventory_label, axis=1)
            target = st.selectbox("修正商品", inv_sorted['label'].tolist(), key="edit_sel")
            idx = inv_sorted[inv_sorted['label'] == target].index[0]
            row = st.session_state['inventory'].loc[idx]
            c1, c2 = st.columns(2)
            nm = c1.text_input("名稱", row['名稱'])
            qt = c2.number_input("庫存", value=int(float(row['庫存(顆)'])))
            if st.button("💾 儲存修正"):
                st.session_state['inventory'].at[idx, '名稱'] = nm
                st.session_state['inventory'].at[idx, '庫存(顆)'] = qt
                save_inventory_to_gsheet(st.session_state['inventory'])
                st.success("已修正!"); st.rerun()

    st.divider()
    st.subheader("📊 目前庫存總表")
    search_term = st.text_input("🔍 搜尋 (名稱/編號)", "")
    df_display = st.session_state['inventory'].copy()
    if search_term:
        mask = df_display.astype(str).apply(lambda x: x.str.contains(search_term, case=False)).any(axis=1)
        df_display = df_display[mask]
    if not st.session_state['admin_mode']:
        df_display = df_display.drop(columns=['成本單價', '進貨廠商']) if '成本單價' in df_display.columns else df_display
    st.dataframe(df_display, use_container_width=True)

# ------------------------------------------
# 頁面 B: 紀錄查詢
# ------------------------------------------
elif page == "📜 紀錄查詢":
    df_h = st.session_state['history'].copy()
    if not st.session_state['admin_mode'] and '成本備註' in df_h.columns:
        df_h = df_h.drop(columns=['成本備註'])
    if not df_h.empty: df_h = df_h.iloc[::-1]
    st.dataframe(df_h, use_container_width=True)

# ------------------------------------------
# 頁面 C: 領料與設計單 (更新總價紀錄邏輯)
# ------------------------------------------
elif page == "🧮 領料與設計單":
    st.subheader("🧮 領料與設計單")
    c_oid, c_note = st.columns([1, 2])
    st.session_state['order_id_input'] = c_oid.text_input("自訂單號", st.session_state['order_id_input'])
    st.session_state['order_note_input'] = c_note.text_input("備註 (選填)", st.session_state['order_note_input'])
    
    if not st.session_state['inventory'].empty:
        inv_sorted = st.session_state['inventory'].copy()
        inv_sorted['label'] = inv_sorted.apply(make_inventory_label, axis=1)
        sel = st.selectbox("選擇材料", inv_sorted['label'].tolist(), key="d_sel")
        idx = inv_sorted[inv_sorted['label'] == sel].index[0]
        row = st.session_state['inventory'].loc[idx]
        cur_s = int(float(row['庫存(顆)']))
        c1, c2 = st.columns([1,2])
        qty = c1.number_input("加入數量", min_value=1, max_value=max(1, cur_s), value=1)
        
        if c1.button("⬇️ 加入清單"):
            found = False
            for item in st.session_state['current_design']:
                if item['編號'] == row['編號'] and item['批號'] == row['批號']:
                    item['數量'] += qty
                    found = True; break
            if not found:
                st.session_state['current_design'].append({'編號': row['編號'], '批號': row['批號'], '名稱': row['名稱'], '數量': qty, '倉庫': row.get('倉庫',''), '分類': row.get('分類',''), '規格': format_size(row), '廠商': row.get('進貨廠商','')})
            st.rerun()

    if st.session_state['current_design']:
        st.markdown("---")
        st.subheader("🛒 領料清單")
        delete_index = -1
        grand_total_cost = 0 # 用於加總
        
        for i, item in enumerate(st.session_state['current_design']):
            mask = (st.session_state['inventory']['編號'] == item['編號']) & (st.session_state['inventory']['批號'] == item['批號'])
            u_cost = float(st.session_state['inventory'].loc[mask, '成本單價'].values[0]) if mask.any() else 0
            grand_total_cost += u_cost * item['數量']
            
            with st.container():
                c1, c2, c3, c4 = st.columns([4, 2, 2, 1])
                cost_info = f" | 💰${u_cost:.2f}/顆" if st.session_state['admin_mode'] else ""
                c1.markdown(f"**{item['名稱']}** ({item.get('規格','')}) {cost_info}", unsafe_allow_html=True)
                new_qty = c2.number_input("qty", min_value=1, value=int(item['數量']), label_visibility="collapsed", key=f"d_qty_{i}")
                if new_qty != item['數量']: item['數量'] = new_qty; st.rerun()
                c3.text(item['批號'])
                if c4.button("🗑️", key=f"d_del_{i}"): delete_index = i

        if delete_index != -1: del st.session_state['current_design'][delete_index]; st.rerun()

        st.divider()
        if st.session_state['admin_mode']:
            st.info(f"💰 本單預計總成本: ${grand_total_cost:,.2f}")

        c_confirm, c_clear = st.columns([4, 1])
        if c_confirm.button("✅ 確認領出 (寫入雲端)", type="primary", use_container_width=True):
            final_oid = st.session_state['order_id_input'].strip() or f"DES-{date.today().strftime('%Y%m%d')}"
            
            # 1. 逐筆寫入零件紀錄
            for x in st.session_state['current_design']:
                 mask = (st.session_state['inventory']['編號'] == x['編號']) & (st.session_state['inventory']['批號'] == x['批號'])
                 if mask.any():
                     t_idx = st.session_state['inventory'][mask].index[0]
                     row = st.session_state['inventory'].loc[t_idx]
                     u_cost = float(row['成本單價'])
                     total_item_cost = u_cost * x['數量']
                     cost_log = f"成本${total_item_cost:.2f} (單${u_cost:.2f})"
                     user_n = st.session_state['order_note_input'].strip()
                     final_n = f"{user_n} | {cost_log}" if user_n else cost_log

                     st.session_state['inventory'].at[t_idx, '庫存(顆)'] -= x['數量']
                     log = {'紀錄時間': datetime.now().strftime("%Y-%m-%d %H:%M"), '單號': final_oid, '動作': '設計單領出', '倉庫': row.get('倉庫',''), '批號': x['批號'], '編號': x['編號'], '分類': row.get('分類',''), '名稱': x['名稱'], '規格': format_size(row), '廠商': row.get('進貨廠商',''), '數量變動': -x['數量'], '成本備註': final_n}
                     st.session_state['history'] = pd.concat([st.session_state['history'], pd.DataFrame([log])], ignore_index=True)

            # 2. 寫入總計紀錄 (後台用)
            summary_log = {'紀錄時間': datetime.now().strftime("%Y-%m-%d %H:%M"), '單號': final_oid, '動作': '🏷️ 單據總計', '名稱': '--- 整單彙整 ---', '數量變動': 0, '成本備註': f"💰 本單總計：${grand_total_cost:.2f}"}
            st.session_state['history'] = pd.concat([st.session_state['history'], pd.DataFrame([summary_log])], ignore_index=True)
            
            save_inventory_to_gsheet(st.session_state['inventory'])
            save_history_to_gsheet(st.session_state['history'])
            st.session_state['current_design'] = []
            st.success(f"訂單 {final_oid} 完成，總計成本已同步後台！"); time.sleep(1); st.rerun()
        
        if c_clear.button("🗑️ 清空"): st.session_state['current_design'] = []; st.rerun()
