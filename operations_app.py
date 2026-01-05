import streamlit as st
import pandas as pd
from datetime import date, datetime
import time
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# ==========================================
# 1. 核心設定 (Google Sheets)
# ==========================================

SHEET_NAME = "IFcrystal_inventory"
KEY_FILE = "google_key.json"

# v7.0 新增 '成本單價'
COLUMNS = [
    '編號', '批號', '倉庫', '分類', '名稱', 
    '寬度mm', '長度mm', '形狀', '五行', 
    '進貨數量(顆)', '進貨日期', '進貨廠商', 
    '庫存(顆)', '成本單價'
]

SENSITIVE_COLUMNS = ['進貨廠商', '廠商', '成本單價']

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
    creds = ServiceAccountCredentials.from_json_keyfile_name(KEY_FILE, scope)
    client = gspread.authorize(creds)
    return client

def robust_import_inventory(df):
    df.columns = df.columns.astype(str).str.strip().str.replace('\ufeff', '')
    if 'label' in df.columns: df = df.drop(columns=['label'])
    
    if '批號' not in df.columns: df['批號'] = '初始存貨'
    if '倉庫' not in df.columns: df.insert(1, '倉庫', 'Imeng')
    for col in COLUMNS:
        if col not in df.columns: df[col] = ""
    df = df[COLUMNS].copy()
    
    df = df.fillna("")
    for col in df.columns:
        df[col] = df[col].astype(str).str.strip()
        
    # 數值轉換：包含成本單價
    for col in ['寬度mm', '長度mm', '進貨數量(顆)', '庫存(顆)', '成本單價']:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        
    return df

def load_data_from_gsheet():
    try:
        client = get_google_sheet_client()
        sheet = client.open(SHEET_NAME).sheet1
        data = sheet.get_all_records()
        if not data: return pd.DataFrame(columns=COLUMNS)
        return robust_import_inventory(pd.DataFrame(data))
    except Exception as e:
        st.error(f"❌ 無法讀取: {e}"); return pd.DataFrame(columns=COLUMNS)

def save_data_to_gsheet(df):
    try:
        client = get_google_sheet_client()
        sheet = client.open(SHEET_NAME).sheet1
        sheet.clear()
        update_data = [df.columns.values.tolist()] + df.astype(str).values.tolist()
        sheet.update(update_data)
        st.toast("☁️ 雲端存檔成功！")
    except Exception as e: st.error(f"❌ 存檔失敗: {e}")

def save_history_local():
    try:
        if 'history' in st.session_state:
            st.session_state['history'].to_csv('inventory_history.csv', index=False, encoding='utf-8-sig')
    except Exception: pass

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
    
    # 只有主管模式才在選單顯示成本，避免員工看到
    cost_str = ""
    if st.session_state.get('admin_mode', False):
        cost = float(row.get('成本單價', 0))
        if cost > 0: cost_str = f" 💰${cost}"

    return f"[{row.get('倉庫','Imeng')}] {row.get('名稱','')} {sz} ({row.get('形狀','')}) {cost_str} | 存:{stock_val}"

def get_dynamic_options(col, defaults):
    opts = set(defaults)
    if not st.session_state['inventory'].empty:
        raw = st.session_state['inventory'][col].astype(str).tolist()
        opts.update([x.strip() for x in raw if x.strip() and x.lower() != 'nan'])
    return ["➕ 手動輸入"] + sorted(list(opts))

# ==========================================
# 4. 初始化與 UI
# ==========================================

st.set_page_config(page_title="GemCraft 成本控管系統", layout="wide")

if 'inventory' not in st.session_state:
    with st.spinner('連線雲端中...'):
        st.session_state['inventory'] = load_data_from_gsheet()

if 'history' not in st.session_state:
    try: st.session_state['history'] = pd.read_csv('inventory_history.csv', encoding='utf-8-sig')
    except: st.session_state['history'] = pd.DataFrame(columns=HISTORY_COLUMNS)

if 'admin_mode' not in st.session_state: st.session_state['admin_mode'] = False
if 'current_design' not in st.session_state: st.session_state['current_design'] = []

# 初始化變數
if 'order_id_input' not in st.session_state: 
    st.session_state['order_id_input'] = f"DES-{date.today().strftime('%Y%m%d')}-{int(time.time())%1000}"

st.title("💎 GemCraft 成本控管系統 (v7.0)")

# --- 側邊欄：總資產統計 ---
with st.sidebar:
    st.header("🔑 權限與統計")
    pwd = st.text_input("主管密碼", type="password")
    st.session_state['admin_mode'] = (pwd == "admin123")
    
    if st.session_state['admin_mode']:
        st.success("🔓 管理員模式")
        # 計算總成本
        df_inv = st.session_state['inventory']
        if not df_inv.empty:
            total_cost = (df_inv['庫存(顆)'] * df_inv['成本單價']).sum()
            st.metric("💰 目前庫存總成本", f"${total_cost:,.0f}")
            st.caption("*計算公式：Σ (庫存數量 × 成本單價)")
    else:
        st.info("🔒 訪客模式 (隱藏成本)")

    st.divider()
    page = st.radio("功能前往", ["📦 庫存與進貨", "📜 紀錄查詢", "🧮 領料與設計"])
    st.divider()
    if st.button("🔄 強制重整"): st.session_state.clear(); st.rerun()

# ------------------------------------------
# 頁面 A: 庫存管理
# ------------------------------------------
if page == "📦 庫存與進貨":
    tab1, tab2, tab4, tab3 = st.tabs(["🔄 補貨(含成本)", "✨ 建檔(含成本)", "📤 領用", "🛠️ 修改"])
    
    with tab1: # 補貨
        inv = st.session_state['inventory']
        if not inv.empty:
            inv['label'] = inv.apply(make_inventory_label, axis=1)
            target = st.selectbox("選擇商品", inv['label'].tolist())
            idx = inv[inv['label'] == target].index[0]
            row = inv.loc[idx]
            
            with st.form("restock"):
                old_cost = float(row.get('成本單價', 0))
                st.info(f"品名：{row['名稱']} | 目前成本：${old_cost} /顆")
                
                c1, c2, c3 = st.columns(3)
                qty = c1.number_input("進貨數量", 1, value=1)
                cost_in = c2.number_input("本次進貨成本(單價)", min_value=0.0, value=old_cost, step=0.1)
                r_type = c3.radio("方式", ["➕ 合併 (更新成本)", "📦 新批號"])
                
                new_batch = st.text_input("新批號", f"{date.today().strftime('%Y%m%d')}-A") if r_type == "📦 新批號" else row['批號']

                if st.form_submit_button("確認進貨"):
                    if r_type == "➕ 合併 (更新成本)":
                        # 加權平均成本或是直接覆蓋？這裡選擇直接更新為最新成本
                        st.session_state['inventory'].at[idx, '庫存(顆)'] += qty
                        st.session_state['inventory'].at[idx, '成本單價'] = cost_in
                        log_act = f"補貨(成本${cost_in})"
                    else:
                        new_r = row.copy()
                        new_r['庫存(顆)'] = qty
                        new_r['進貨數量(顆)'] = qty
                        new_r['進貨日期'] = date.today()
                        new_r['批號'] = new_batch
                        new_r['成本單價'] = cost_in
                        st.session_state['inventory'] = pd.concat([st.session_state['inventory'], pd.DataFrame([new_r])], ignore_index=True)
                        log_act = f"補貨新批(成本${cost_in})"
                    
                    save_data_to_gsheet(st.session_state['inventory'])
                    
                    log = {'紀錄時間': datetime.now().strftime("%Y-%m-%d %H:%M"), '單號': 'IN', 
                           '動作': log_act, '名稱': row['名稱'], '數量變動': qty, '成本備註': f"單價${cost_in}"}
                    st.session_state['history'] = pd.concat([st.session_state['history'], pd.DataFrame([log])], ignore_index=True)
                    save_history_local(); st.success("已更新！"); st.rerun()

    with tab2: # 建檔
        with st.form("new_item"):
            c1, c2, c3 = st.columns(3)
            wh = c1.selectbox("倉庫", DEFAULT_WAREHOUSES)
            # 名稱處理
            exist_names = sorted(list(set([x for x in st.session_state['inventory']['名稱'].astype(str) if x]))) if not st.session_state['inventory'].empty else []
            name_sel = c2.selectbox("名稱", ["➕ 手動輸入"] + exist_names)
            name = c2.text_input("輸入名稱") if name_sel == "➕ 手動輸入" else name_sel
            cat = c3.selectbox("分類", ["天然石", "配件", "耗材"])
            
            s1, s2, s3 = st.columns(3)
            w_mm = s1.number_input("寬度", 0.0)
            l_mm = s2.number_input("長度", 0.0)
            shape = s3.selectbox("形狀", get_dynamic_options('形狀', DEFAULT_SHAPES))
            if shape == "➕ 手動輸入": shape = st.text_input("形狀")
            
            c4, c5, c6 = st.columns(3)
            elem = c4.selectbox("五行", get_dynamic_options('五行', DEFAULT_ELEMENTS))
            if elem == "➕ 手動輸入": elem = st.text_input("五行")
            sup = c5.selectbox("廠商", get_dynamic_options('進貨廠商', DEFAULT_SUPPLIERS))
            if sup == "➕ 手動輸入": sup = st.text_input("廠商")
            cost_new = c6.number_input("💰 成本單價", min_value=0.0, step=0.1)
            
            c7, c8 = st.columns(2)
            qty_init = c7.number_input("初始數量", 1)
            batch = c8.text_input("初始批號", f"{date.today().strftime('%Y%m%d')}-01")
            
            if st.form_submit_button("建立商品"):
                if not name: st.error("沒填名稱")
                else:
                    new_r = {
                        '編號': f"ST{int(time.time())}", '批號': batch, '倉庫': wh, '分類': cat, '名稱': name, 
                        '寬度mm': w_mm, '長度mm': l_mm, '形狀': shape, '五行': elem, 
                        '進貨廠商': sup, '庫存(顆)': qty_init, '進貨日期': date.today(),
                        '成本單價': cost_new
                    }
                    st.session_state['inventory'] = pd.concat([st.session_state['inventory'], pd.DataFrame([new_r])], ignore_index=True)
                    save_data_to_gsheet(st.session_state['inventory'])
                    
                    log = {'紀錄時間': datetime.now().strftime("%Y-%m-%d %H:%M"), '單號': 'NEW', '動作': '新商品', 
                           '名稱': name, '數量變動': qty_init, '成本備註': f"初始成本${cost_new}"}
                    st.session_state['history'] = pd.concat([st.session_state['history'], pd.DataFrame([log])], ignore_index=True)
                    save_history_local(); st.success("已建檔！"); st.rerun()

    with tab4: # 領用
        inv_o = st.session_state['inventory'].copy()
        if not inv_o.empty:
            inv_o['label'] = inv_o.apply(make_inventory_label, axis=1)
            target = st.selectbox("選擇商品", inv_o['label'].tolist(), key="out_sel")
            idx = inv_o[inv_o['label'] == target].index[0]
            row = st.session_state['inventory'].loc[idx]
            
            with st.form("out_form"):
                qty_o = st.number_input("出庫數量", 0, int(float(row['庫存(顆)'])))
                reason = st.selectbox("原因", ["商品", "自用", "損壞", "樣品"])
                if st.form_submit_button("出庫"):
                    st.session_state['inventory'].at[idx, '庫存(顆)'] -= qty_o
                    save_data_to_gsheet(st.session_state['inventory'])
                    log = {'紀錄時間': datetime.now().strftime("%Y-%m-%d %H:%M"), '單號': 'OUT', '動作': f"出庫-{reason}", 
                           '名稱': row['名稱'], '數量變動': -qty_o}
                    st.session_state['history'] = pd.concat([st.session_state['history'], pd.DataFrame([log])], ignore_index=True)
                    save_history_local(); st.rerun()

    with tab3: # 修改 (包含修改成本)
        if not st.session_state['inventory'].empty:
            inv_e = st.session_state['inventory'].copy()
            inv_e['label'] = inv_e.apply(make_inventory_label, axis=1)
            target = st.selectbox("修正商品", inv_e['label'].tolist(), key="edit_sel")
            idx = inv_e[inv_e['label'] == target].index[0]
            row = st.session_state['inventory'].loc[idx]
            
            with st.form("edit_form"):
                c1, c2 = st.columns(2)
                nm = c1.text_input("名稱", row['名稱'])
                qt = c2.number_input("庫存", value=int(float(row['庫存(顆)'])))
                ct = st.number_input("💰 成本單價", value=float(row.get('成本單價', 0)))
                
                if st.form_submit_button("儲存修正"):
                    st.session_state['inventory'].at[idx, '名稱'] = nm
                    st.session_state['inventory'].at[idx, '庫存(顆)'] = qt
                    st.session_state['inventory'].at[idx, '成本單價'] = ct
                    save_data_to_gsheet(st.session_state['inventory'])
                    st.success("已修正"); st.rerun()

# ------------------------------------------
# 頁面 B & C (維持原樣，但隱藏敏感資料)
# ------------------------------------------
elif page == "📜 紀錄查詢":
    df_h = st.session_state['history'].copy()
    if not st.session_state['admin_mode'] and '成本備註' in df_h.columns:
        df_h = df_h.drop(columns=['成本備註'])
    st.dataframe(df_h, use_container_width=True)

elif page == "🧮 領料與設計單":
    st.subheader("🧮 領料單")
    # ... (領料邏輯與 v6.0 相同，這裡省略重複代碼，保留核心功能) ...
    # 為保持長度精簡，領料部分功能直接沿用，若需要看成本計算利潤可再擴充
    
    items = st.session_state['inventory'].copy()
    if not items.empty:
        items['lbl'] = items.apply(make_inventory_label, axis=1)
        sel = st.selectbox("選擇材料", items['lbl'], key="d_sel")
        idx = items[items['lbl'] == sel].index[0]
        cur_s = int(float(items.loc[idx, '庫存(顆)']))
        
        c1, c2 = st.columns([1,2])
        qty = c1.number_input("數量", 0, max(0, cur_s))
        if c1.button("⬇️ 加入"):
            if qty > 0:
                st.session_state['current_design'].append({
                    '編號': items.loc[idx, '編號'], '批號': items.loc[idx, '批號'],
                    '名稱': items.loc[idx, '名稱'], '數量': qty,
                    '成本小計': float(items.loc[idx, '成本單價']) * qty # 偷記成本
                })
                st.rerun()

    if st.session_state['current_design']:
        df_d = pd.DataFrame(st.session_state['current_design'])
        # 只有管理員看得到成本小計
        if not st.session_state['admin_mode'] and '成本小計' in df_d.columns:
            df_d = df_d.drop(columns=['成本小計'])
            
        st.table(df_d)
        
        if st.session_state['admin_mode']:
            total_cost = pd.DataFrame(st.session_state['current_design'])['成本小計'].sum()
            st.info(f"💰 本單總成本: ${total_cost:,.0f}")

        if st.button("✅ 確認領出"):
            # (執行扣庫存與存檔邏輯，同 v6.0)
            for x in st.session_state['current_design']:
                 mask = (st.session_state['inventory']['編號'] == x['編號']) & \
                        (st.session_state['inventory']['批號'] == x['批號'])
                 if mask.any():
                     t_idx = st.session_state['inventory'][mask].index[0]
                     st.session_state['inventory'].at[t_idx, '庫存(顆)'] -= x['數量']
                     log = {'紀錄時間': datetime.now().strftime("%Y-%m-%d %H:%M"), '單號': 'DES', '動作': '設計單', 
                            '名稱': x['名稱'], '數量變動': -x['數量']}
                     st.session_state['history'] = pd.concat([st.session_state['history'], pd.DataFrame([log])], ignore_index=True)
            save_data_to_gsheet(st.session_state['inventory'])
            save_history_local()
            st.session_state['current_design'] = []
            st.success("完成！"); st.rerun()
        
        if st.button("🗑️ 清空"): st.session_state['current_design'] = []; st.rerun()
