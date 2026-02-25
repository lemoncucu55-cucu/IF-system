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

st.title("💎 IF Crystal 全雲端系統 (v9.12-撤銷功能版)")

with st.sidebar:
    st.header("🔑 權限與統計")
    pwd = st.text_input("主管密碼", type="password")
    st.session_state['admin_mode'] = (pwd == "admin123")
    
    if st.session_state['admin_mode']:
        st.success("🔓 管理員模式")
        df_inv = st.session_state['inventory']
        if not df_inv.empty:
            total_cost_inv = (df_inv['庫存(顆)'] * df_inv['成本單價']).sum()
            st.metric("💰 庫存總資產", f"${total_cost_inv:,.2f}")
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
            inv_sorted['label'] = inv_sorted.apply(make_inventory_label, axis=1)
            target = st.selectbox("選擇商品", inv_sorted['label'].tolist())
            idx = inv_sorted[inv_sorted['label'] == target].index[0]
            row = st.session_state['inventory'].loc[idx]
            
            with st.form("restock"):
                old_cost = float(row.get('成本單價', 0))
                st.info(f"品名：{row['名稱']} | 目前單價成本：${old_cost:.2f}")
                c1, c2, c3 = st.columns(3)
                qty = c1.number_input("進貨數量", 1, value=1)
                total_cost_in = c2.number_input("💰 本次進貨總價", min_value=0.0, step=1.0)
                calc_unit_cost = total_cost_in / qty if qty > 0 else 0
                r_type = c3.radio("方式", ["➕ 合併", "📦 新批號"])
                new_batch = st.text_input("新批號", f"{date.today().strftime('%Y%m%d')}-A") if r_type == "📦 新批號" else row['批號']

                if st.form_submit_button("確認進貨"):
                    final_unit_cost = total_cost_in / qty if qty > 0 else 0
                    if r_type == "➕ 合併":
                        st.session_state['inventory'].at[idx, '庫存(顆)'] += qty
                        st.session_state['inventory'].at[idx, '成本單價'] = round(final_unit_cost, 2)
                        save_inventory_to_gsheet(st.session_state['inventory'])
                        log_act = f"補貨(總${total_cost_in:.2f})"
                    else:
                        new_r = row.copy()
                        new_r['庫存(顆)'], new_r['進貨數量(顆)'], new_r['進貨日期'], new_r['批號'], new_r['成本單價'] = int(qty), int(qty), str(date.today()), new_batch, round(final_unit_cost, 2)
                        if append_inventory_row(new_r):
                            st.session_state['inventory'] = pd.concat([st.session_state['inventory'], pd.DataFrame([new_r])], ignore_index=True)
                            log_act = "補貨新批"
                        else: st.stop()
                    
                    log = {'紀錄時間': datetime.now().strftime("%Y-%m-%d %H:%M"), '單號': 'IN', '動作': log_act, '倉庫': row['倉庫'], '批號': new_batch, '編號': row['編號'], '分類': row['分類'], '名稱': row['名稱'], '規格': format_size(row), '廠商': row['進貨廠商'], '數量變動': qty, '成本備註': f"總${total_cost_in:.2f}"}
                    st.session_state['history'] = pd.concat([st.session_state['history'], pd.DataFrame([log])], ignore_index=True)
                    save_history_to_gsheet(st.session_state['history']); st.rerun()

    with tab2: # 建檔
        with st.form("new_item"):
            c1, c2, c3 = st.columns(3)
            wh, name_sel, cat = c1.selectbox("倉庫", DEFAULT_WAREHOUSES), c2.selectbox("名稱", ["➕ 手動輸入"]), c3.selectbox("分類", ["天然石", "配件", "耗材"])
            name = c2.text_input("輸入名稱") if name_sel == "➕ 手動輸入" else name_sel
            qty_init, total_cost_init = st.number_input("初始數量", 1), st.number_input("💰 初始總成本", 0.0)
            if st.form_submit_button("建立商品"):
                final_unit_cost = total_cost_init / qty_init if qty_init > 0 else 0
                new_r = {'編號': f"ST{int(time.time())}", '批號': 'INIT', '倉庫': wh, '分類': cat, '名稱': name, '庫存(顆)': int(qty_init), '成本單價': round(final_unit_cost, 2), '進貨日期': str(date.today())}
                if append_inventory_row(new_r):
                    st.session_state['inventory'] = pd.concat([st.session_state['inventory'], pd.DataFrame([new_r])], ignore_index=True)
                    st.success("已建檔！"); st.rerun()

    st.divider()
    st.subheader("📊 目前庫存總表")
    df_display = st.session_state['inventory'].copy()
    if not st.session_state['admin_mode']:
        df_display = df_display.drop(columns=['成本單價', '進貨廠商'], errors='ignore')
    st.dataframe(df_display, use_container_width=True)

# ------------------------------------------
# 頁面 B: 紀錄查詢 (新增取消/撤銷功能)
# ------------------------------------------
elif page == "📜 紀錄查詢":
    st.subheader("📜 歷史紀錄與撤銷 (管理員專用)")
    df_h = st.session_state['history'].copy()
    
    if not st.session_state['admin_mode']:
        # 訪客模式：僅顯示唯讀表格
        df_h_display = df_h.drop(columns=['成本備註'], errors='ignore')
        if not df_h_display.empty: df_h_display = df_h_display.iloc[::-1]
        st.dataframe(df_h_display, use_container_width=True)
    else:
        # 管理員模式：顯示具備取消功能的清單
        if df_h.empty:
            st.info("目前尚無紀錄。")
        else:
            # 倒序顯示，最近的在上面
            df_h_rev = df_h.iloc[::-1]
            
            # 使用列表方式呈現，方便放置按鈕
            for idx, row in df_h_rev.iterrows():
                with st.expander(f"{row['紀錄時間']} | {row['單號']} | {row['動作']} - {row['名稱']}"):
                    c1, c2 = st.columns([4, 1])
                    with c1:
                        # 顯示詳細資訊
                        st.write(f"**倉庫**: {row['倉庫']} | **編號**: {row['編號']} | **批號**: {row['批號']}")
                        st.write(f"**數量變動**: {row['數量變動']} | **備註**: {row['成本備註']}")
                    
                    with c2:
                        # 針對可以撤銷的動作增加按鈕 (排除 🏷️單據總計)
                        if row['動作'] != '🏷️ 單據總計':
                            if st.button("🗑️ 撤銷紀錄", key=f"rev_{idx}"):
                                # 1. 數量回滾邏輯
                                mask = (st.session_state['inventory']['編號'] == row['編號']) & \
                                       (st.session_state['inventory']['批號'] == row['批號'])
                                
                                if mask.any():
                                    inv_idx = st.session_state['inventory'][mask].index[0]
                                    # 反向扣除變動 (例如原本 -5，撤銷變 +5)
                                    st.session_state['inventory'].at[inv_idx, '庫存(顆)'] -= float(row['數量變動'])
                                    
                                    # 2. 刪除該筆紀錄
                                    st.session_state['history'] = st.session_state['history'].drop(idx)
                                    
                                    # 3. 如果是設計單，嘗試連帶刪除「單據總計」那一列
                                    oid = row['單號']
                                    summary_mask = (st.session_state['history']['單號'] == oid) & \
                                                   (st.session_state['history']['動作'] == '🏷️ 單據總計')
                                    if summary_mask.any():
                                        st.session_state['history'] = st.session_state['history'][~summary_mask]

                                    # 4. 同步至雲端
                                    save_inventory_to_gsheet(st.session_state['inventory'])
                                    save_history_to_gsheet(st.session_state['history'])
                                    
                                    st.success(f"已撤銷 {row['名稱']} 並回撥庫存！")
                                    time.sleep(1)
                                    st.rerun()
                                else:
                                    st.error("找不到對應庫存品項，無法自動回撥。")

# ------------------------------------------
# 頁面 C: 領料與設計單
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
                st.session_state['current_design'].append({
                    '編號': row['編號'], '批號': row['批號'], '名稱': row['名稱'], 
                    '數量': qty, '倉庫': row.get('倉庫',''), '分類': row.get('分類',''), 
                    '規格': format_size(row), '廠商': row.get('進貨廠商','')
                })
            st.rerun()

    if st.session_state['current_design']:
        st.markdown("---")
        st.subheader("🛒 領料清單")
        delete_index = -1
        grand_total_cost = 0 
        
        for i, item in enumerate(st.session_state['current_design']):
            mask = (st.session_state['inventory']['編號'] == item['編號']) & (st.session_state['inventory']['批號'] == item['批號'])
            u_cost = float(st.session_state['inventory'].loc[mask, '成本單價'].values[0]) if mask.any() else 0
            item_subtotal = u_cost * item['數量']
            grand_total_cost += item_subtotal
            
            with st.container():
                c1, c2, c3, c4 = st.columns([4, 2, 2, 1])
                cost_info = f" | 💰${u_cost:.2f}/顆 | **小計: ${item_subtotal:.2f}**" if st.session_state['admin_mode'] else ""
                c1.markdown(f"**{item['名稱']}** ({item.get('規格','')}) {cost_info}", unsafe_allow_html=True)
                new_qty = c2.number_input("qty", min_value=1, value=int(item['數量']), label_visibility="collapsed", key=f"d_qty_{i}")
                if new_qty != item['數量']: item['數量'] = new_qty; st.rerun()
                c3.text(item['批號'])
                if c4.button("🗑️", key=f"d_del_{i}"): delete_index = i

        if delete_index != -1: del st.session_state['current_design'][delete_index]; st.rerun()

        st.divider()
        if st.session_state['admin_mode']:
            st.metric("💰 本張設計單預估總成本", f"${grand_total_cost:,.2f}")
        else:
            st.caption("🔒 成本明細已受保護")

        c_confirm, c_clear = st.columns([4, 1])
        if c_confirm.button("✅ 確認領出 (寫入雲端)", type="primary", use_container_width=True):
            final_oid = st.session_state['order_id_input'].strip() or f"DES-{date.today().strftime('%Y%m%d')}"
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
            summary_log = {'紀錄時間': datetime.now().strftime("%Y-%m-%d %H:%M"), '單號': final_oid, '動作': '🏷️ 單據總計', '名稱': '--- 整單彙整 ---', '數量變動': 0, '成本備註': f"💰 本單總計：${grand_total_cost:.2f}"}
            st.session_state['history'] = pd.concat([st.session_state['history'], pd.DataFrame([summary_log])], ignore_index=True)
            save_inventory_to_gsheet(st.session_state['inventory'])
            save_history_to_gsheet(st.session_state['history'])
            st.session_state['current_design'] = []
            st.success("訂單完成！"); time.sleep(1); st.rerun()
        
        if c_clear.button("🗑️ 清空"): st.session_state['current_design'] = []; st.rerun()
