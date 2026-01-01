import streamlit as st
import pandas as pd
from datetime import date, datetime
import os
import time

# ==========================================
# 1. 核心設定
# ==========================================

COLUMNS = [
    '編號', '批號', '倉庫', '分類', '名稱', 
    '寬度mm', '長度mm', '形狀', '五行', 
    '進貨數量(顆)', '進貨日期', '進貨廠商', 
    '庫存(顆)'
]

SENSITIVE_COLUMNS = ['進貨廠商', '廠商']

HISTORY_COLUMNS = [
    '紀錄時間', '單號', '動作', '倉庫', '批號', '編號', '分類', '名稱', '規格', 
    '廠商', '數量變動'
]

DEFAULT_CSV_FILE = 'inventory_backup_v2.csv'
HISTORY_FILE = 'inventory_history.csv'
DEFAULT_WAREHOUSES = ["Imeng", "千畇"]
DEFAULT_SUPPLIERS = ["小聰頭", "廠商A", "廠商B", "自用", "蝦皮", "淘寶", "TB-東吳天然石坊", "永安", "Rich"]
DEFAULT_SHAPES = ["圓珠", "切角", "鑽切", "圓筒", "方體", "長柱", "不規則", "造型", "原礦"]
DEFAULT_ELEMENTS = ["金", "木", "水", "火", "土", "綜合", "銀", "銅", "14K包金"]

# ==========================================
# 2. 核心函式
# ==========================================

def save_inventory():
    try:
        if 'inventory' in st.session_state:
            st.session_state['inventory'].to_csv(DEFAULT_CSV_FILE, index=False, encoding='utf-8-sig')
    except Exception: pass

def save_history():
    try:
        if 'history' in st.session_state:
            st.session_state['history'].to_csv(HISTORY_FILE, index=False, encoding='utf-8-sig')
    except Exception: pass

def robust_import_inventory(df):
    df.columns = df.columns.astype(str).str.strip().str.replace('\ufeff', '')
    if 'label' in df.columns: df = df.drop(columns=['label'])
    if '批號' not in df.columns: df['批號'] = '初始存貨'
    if '倉庫' not in df.columns: df.insert(1, '倉庫', 'Imeng')
    for col in COLUMNS:
        if col not in df.columns: df[col] = ""
    df = df[COLUMNS].copy()
    for col in ['寬度mm', '長度mm', '進貨數量(顆)', '庫存(顆)']:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    df['批號'] = df['批號'].astype(str)
    return df

def format_size(row):
    try:
        w = float(row.get('寬度mm', 0))
        l = float(row.get('長度mm', 0))
        if l > 0: return f"{w}x{l}mm"
        return f"{w}mm"
    except: return "0mm"

def make_inventory_label(row):
    sz = format_size(row)
    elem = f"({row.get('五行','')})" if row.get('五行','') else ""
    sup = f" | {row.get('進貨廠商','')}" if st.session_state.get('admin_mode', False) else ""
    stock_val = int(float(row.get('庫存(顆)', 0)))
    batch_str = f"【批:{row.get('批號', '無')}】"
    return f"[{row.get('倉庫','Imeng')}] {batch_str} {elem}{row.get('編號','')} | {row.get('名稱','')} | {row.get('形狀','')} ({sz}){sup} | 存:{stock_val}"

def get_dynamic_options(col, defaults):
    opts = set(defaults)
    if not st.session_state['inventory'].empty:
        exist = st.session_state['inventory'][col].astype(str).dropna().unique().tolist()
        opts.update([x for x in exist if x.strip() and x != 'nan'])
    return ["➕ 手動輸入/新增"] + sorted(list(opts))

# ==========================================
# 3. 初始化與 UI
# ==========================================

st.set_page_config(page_title="GemCraft 庫存管理系統", layout="wide")

if 'inventory' not in st.session_state:
    if os.path.exists(DEFAULT_CSV_FILE):
        try: st.session_state['inventory'] = robust_import_inventory(pd.read_csv(DEFAULT_CSV_FILE, encoding='utf-8-sig'))
        except: st.session_state['inventory'] = pd.DataFrame(columns=COLUMNS)
    else: st.session_state['inventory'] = pd.DataFrame(columns=COLUMNS)

if 'history' not in st.session_state:
    if os.path.exists(HISTORY_FILE):
        try: st.session_state['history'] = pd.read_csv(HISTORY_FILE, encoding='utf-8-sig')
        except: st.session_state['history'] = pd.DataFrame(columns=HISTORY_COLUMNS)
    else: st.session_state['history'] = pd.DataFrame(columns=HISTORY_COLUMNS)

if 'admin_mode' not in st.session_state: st.session_state['admin_mode'] = False
if 'current_design' not in st.session_state: st.session_state['current_design'] = []

st.title("💎 GemCraft 庫存管理系統 (v3.4 修正版)")

with st.sidebar:
    st.header("🔑 權限驗證")
    pwd = st.text_input("主管密碼", type="password")
    st.session_state['admin_mode'] = (pwd == "admin123")
    
    st.header("功能導航")
    page = st.radio("前往", ["📦 庫存管理與進貨", "📜 紀錄明細查詢", "🧮 領料與設計單"])
    
    st.divider()
    st.header("📥 下載報表")
    if not st.session_state['inventory'].empty:
        csv_inv = st.session_state['inventory'].to_csv(index=False).encode('utf-8-sig')
        st.download_button("📥 下載目前庫存總表", csv_inv, f'inventory_{date.today()}.csv', "text/csv")
    if not st.session_state['history'].empty:
        csv_hist = st.session_state['history'].to_csv(index=False).encode('utf-8-sig')
        st.download_button("📜 下載出入庫紀錄表", csv_hist, f'history_{date.today()}.csv', "text/csv")

    st.divider()
    uploaded_file = st.file_uploader("📤 上傳資料修正位移", type=['csv'])
    if uploaded_file and st.button("🚨 執行修正匯入"):
        try:
            df = pd.read_csv(uploaded_file, encoding='utf-8-sig')
            st.session_state['inventory'] = robust_import_inventory(df)
            save_inventory(); st.success("資料已匯入！"); time.sleep(1); st.rerun()
        except Exception as e: st.error(f"匯入失敗: {e}")

    if st.button("🔴 重置系統", type="secondary"):
        st.session_state.clear(); st.rerun()

# ------------------------------------------
# 頁面 A: 庫存管理
# ------------------------------------------
if page == "📦 庫存管理與進貨":
    tab1, tab2, tab4, tab3 = st.tabs(["🔄 舊品補貨", "✨ 建立新商品", "📤 領用與出庫", "🛠️ 修改與盤點"])
    
    with tab1: # 補貨
        inv = st.session_state['inventory']
        if not inv.empty:
            inv_l = inv.copy()
            inv_l['label'] = inv_l.apply(make_inventory_label, axis=1)
            target = st.selectbox("選擇商品", inv_l['label'].tolist(), key="t1_sel")
            idx = inv_l[inv_l['label'] == target].index[0]
            row = inv.loc[idx]
            
            with st.form("restock_form"):
                st.info(f"商品：{row['名稱']} | 批號：{row['批號']}")
                c1, c2 = st.columns(2)
                qty = c1.number_input("進貨數量", min_value=1, value=1)
                restock_type = c2.radio("入庫方式", ["📦 建立新批號", "➕ 合併入此批號"])
                
                default_new_batch = f"{date.today().strftime('%Y%m%d')}-A"
                new_batch_id = st.text_input("新批號", value=default_new_batch) if restock_type == "📦 建立新批號" else row['批號']

                if st.form_submit_button("確認入庫"):
                    if restock_type == "➕ 合併入此批號":
                        st.session_state['inventory'].at[idx, '庫存(顆)'] += qty
                        log_action = "補貨(合併)"
                        current_batch = row.get('批號', '無')
                    else:
                        new_row = row.copy()
                        new_row['庫存(顆)'] = qty
                        new_row['進貨數量(顆)'] = qty
                        new_row['進貨日期'] = date.today()
                        new_row['批號'] = new_batch_id
                        st.session_state['inventory'] = pd.concat([st.session_state['inventory'], pd.DataFrame([new_row])], ignore_index=True)
                        log_action = f"補貨(新批號)"
                        current_batch = new_batch_id
                    
                    log = {
                        '紀錄時間': datetime.now().strftime("%Y-%m-%d %H:%M"), 
                        '單號': 'IN', '動作': log_action, 
                        '倉庫': row['倉庫'], '編號': row['編號'], '批號': current_batch,
                        '分類': row['分類'], '名稱': row['名稱'], 
                        '規格': format_size(row), '廠商': row['進貨廠商'], 
                        '數量變動': qty
                    }
                    st.session_state['history'] = pd.concat([st.session_state['history'], pd.DataFrame([log])], ignore_index=True)
                    save_inventory(); save_history(); st.success(f"已完成：{log_action}"); st.rerun()

    with tab2: # ✨ 建立新商品
        with st.form("add_new"):
            c1, c2, c3 = st.columns(3)
            wh = c1.selectbox("倉庫", DEFAULT_WAREHOUSES)
            cat = c2.selectbox("分類", ["天然石", "配件", "耗材"])
            
            # --- 🔴 修正：強制顯示庫存中的名稱選單 ---
            # 直接讀取目前的庫存，確保抓到最新的名稱列表
            current_inv = st.session_state['inventory']
            if not current_inv.empty:
                # 抓取不重複的名稱，並排除空值
                exist_names = current_inv['名稱'].dropna().unique().tolist()
                exist_names = sorted([x for x in exist_names if str(x).strip() != ''])
            else:
                exist_names = []
            
            # 建立選單選項
            name_options = ["➕ 手動輸入/新增"] + exist_names
            
            # 使用 selectbox
            name_sel = c3.selectbox("名稱 (選現有或新增)", name_options, help="選擇『手動輸入/新增』可輸入新名字")
            
            # 如果選了手動輸入，則顯示文字框
            if name_sel == "➕ 手動輸入/新增":
                name = c3.text_input("輸入新名稱", placeholder="例如：白水晶")
            else:
                name = name_sel
            # ---------------------------------------
            
            s1, s2, s3 = st.columns(3)
            w_mm = s1.number_input("寬度 (mm)", min_value=0.0, step=0.1, value=0.0)
            l_mm = s2.number_input("長度 (mm)", min_value=0.0, step=0.1, value=0.0)
            shape = s3.selectbox("形狀", get_dynamic_options('形狀', DEFAULT_SHAPES))
            if shape == "➕ 手動輸入/新增": shape = st.text_input("輸入自定義形狀")
            
            c4, c5, c6 = st.columns(3)
            elem = c4.selectbox("五行", get_dynamic_options('五行', DEFAULT_ELEMENTS))
            if elem == "➕ 手動輸入/新增": elem = st.text_input("輸入自定義五行")
            sup = c5.selectbox("進貨廠商", get_dynamic_options('進貨廠商', DEFAULT_SUPPLIERS))
            if sup == "➕ 手動輸入/新增": sup = st.text_input("輸入自定義廠商")
            
            c7, c8 = st.columns(2)
            qty_init = c7.number_input("初始數量", min_value=1, value=1)
            batch_init = c8.text_input("初始批號", value=f"{date.today().strftime('%Y%m%d')}-01")
            
            if st.form_submit_button("➕ 建立商品"):
                if not name:
                    st.error("名稱不能為空！")
                else:
                    nid = f"ST{int(time.time())}"
                    new_r = {
                        '編號': nid, '批號': batch_init, '倉庫': wh, '分類': cat, '名稱': name, 
                        '寬度mm': w_mm, '長度mm': l_mm, '形狀': shape, '五行': elem, 
                        '進貨廠商': sup, '庫存(顆)': qty_init, '進貨日期': date.today()
                    }
                    st.session_state['inventory'] = pd.concat([st.session_state['inventory'], pd.DataFrame([new_r])], ignore_index=True)
                    
                    log = {
                        '紀錄時間': datetime.now().strftime("%Y-%m-%d %H:%M"), 
                        '單號': 'NEW', '動作': '新商品建檔', 
                        '倉庫': wh, '編號': nid, '批號': batch_init,
                        '分類': cat, '名稱': name, 
                        '規格': f"{w_mm}x{l_mm}mm", '廠商': sup, 
                        '數量變動': qty_init
                    }
                    st.session_state['history'] = pd.concat([st.session_state['history'], pd.DataFrame([log])], ignore_index=True)
                    
                    save_inventory(); save_history(); st.success(f"已建立：{name}"); st.rerun()

    with tab4: # 📤 領用與出庫
        inv_o = st.session_state['inventory'].copy()
        if not inv_o.empty:
            inv_o['label'] = inv_o.apply(make_inventory_label, axis=1)
            target = st.selectbox("選擇出庫商品", inv_o['label'].tolist(), key="t4_sel")
            idx = inv_o[inv_o['label'] == target].index[0]
            row = st.session_state['inventory'].loc[idx]
            cur_s = int(float(row['庫存(顆)']))
            with st.form("out_form"):
                st.write(f"[{row['倉庫']}] {row['名稱']} | 批號:{row['批號']} | 存:{cur_s}")
                qty_o = st.number_input("出庫數量", min_value=0, max_value=max(0, cur_s), value=0)
              reason = st.selectbox("出庫類別", ["商品", "自用", "損壞", "樣品", "其他"])
                note_out = st.text_area("備註")
                if st.form_submit_button("確認出庫"):
                    if qty_o > 0:
                        st.session_state['inventory'].at[idx, '庫存(顆)'] -= qty_o
                        action_msg = f"領用出庫({reason})" + (f" - {note_out}" if note_out else "")
                        log = {
                            '紀錄時間': datetime.now().strftime("%Y-%m-%d %H:%M"), 
                            '單號': 'OUT', '動作': action_msg, 
                            '倉庫': row['倉庫'], '編號': row['編號'], '批號': row['批號'],
                            '分類': row['分類'], '名稱': row['名稱'], 
                            '規格': format_size(row), '廠商': row['進貨廠商'], 
                            '數量變動': -qty_o
                        }
                        st.session_state['history'] = pd.concat([st.session_state['history'], pd.DataFrame([log])], ignore_index=True)
                        save_inventory(); save_history(); st.warning("已出庫"); st.rerun()

    with tab3: # 🛠️ 修改與盤點
        if not st.session_state['inventory'].empty:
            inv_e = st.session_state['inventory'].copy()
            inv_e['label'] = inv_e.apply(make_inventory_label, axis=1)
            target = st.selectbox("修正商品", inv_e['label'].tolist(), key="t3_sel")
            idx = inv_e[inv_e['label'] == target].index[0]
            orig = st.session_state['inventory'].loc[idx]
            val = int(float(orig['庫存(顆)']))
            with st.form("edit_manual_form"):
                st.write(f"修正: {orig['編號']} ({orig['名稱']})")
                c1, c2, c3 = st.columns(3)
                nm = c1.text_input("名稱修正", orig['名稱'])
                wh = c2.selectbox("倉庫", DEFAULT_WAREHOUSES, index=DEFAULT_WAREHOUSES.index(orig['倉庫']) if orig['倉庫'] in DEFAULT_WAREHOUSES else 0)
                bt = c3.text_input("批號", orig['批號']) 
                
                c4, c5, c6 = st.columns(3)
                wm = c4.number_input("寬mm", value=float(orig['寬度mm']))
                lm = c5.number_input("長mm", value=float(orig['長度mm']))
                qt = c6.number_input("庫存修正", min_value=min(0, val), value=val)
                
                el = st.selectbox("五行", get_dynamic_options('五行', DEFAULT_ELEMENTS), index=0)
                note_edit = st.text_area("修正原因")
                
                if st.form_submit_button("儲存修正"):
                    st.session_state['inventory'].at[idx, '名稱'] = nm
                    st.session_state['inventory'].at[idx, '倉庫'] = wh
                    st.session_state['inventory'].at[idx, '批號'] = bt
                    st.session_state['inventory'].at[idx, '寬度mm'] = wm
                    st.session_state['inventory'].at[idx, '長度mm'] = lm
                    st.session_state['inventory'].at[idx, '庫存(顆)'] = qt
                    st.session_state['inventory'].at[idx, '五行'] = el if el != "➕ 手動輸入/新增" else orig['五行']
                    
                    action_msg = "盤點修正" + (f" - {note_edit}" if note_edit else "")
                    log = {
                        '紀錄時間': datetime.now().strftime("%Y-%m-%d %H:%M"), 
                        '單號': 'ADJUST', '動作': action_msg, 
                        '倉庫': wh, '編號': orig['編號'], '批號': bt,
                        '分類': orig['分類'], '名稱': nm, 
                        '規格': format_size(orig), '廠商': orig['進貨廠商'], 
                        '數量變動': (qt - val)
                    }
                    st.session_state['history'] = pd.concat([st.session_state['history'], pd.DataFrame([log])], ignore_index=True)
                    save_inventory(); save_history(); st.success("已修正"); st.rerun()
            
            if st.button("🗑️ 刪除該商品"):
                if st.session_state['admin_mode']:
                    st.session_state['inventory'] = st.session_state['inventory'].drop(idx).reset_index(drop=True)
                    save_inventory(); st.warning("已刪除"); st.rerun()
                else: st.error("權限不足")
        else: st.info("無資料")

    st.divider()
    if not st.session_state['inventory'].empty:
        df_s = st.session_state['inventory'].copy()
        df_s['庫存(顆)'] = pd.to_numeric(df_s['庫存(顆)'], errors='coerce').fillna(0)
        sum_df = df_s.groupby('倉庫').agg({'編號': 'count', '庫存(顆)': 'sum'}).rename(columns={'編號': '品項數量', '庫存(顆)': '顆數總計'})
        st.table(sum_df.astype(int))
    vdf = st.session_state['inventory'].copy()
    if not vdf.empty:
        if not st.session_state['admin_mode']:
            vdf = vdf.drop(columns=[c for c in SENSITIVE_COLUMNS if c in vdf.columns])
        st.dataframe(vdf, use_container_width=True)

# ------------------------------------------
# 頁面 B: 紀錄查詢
# ------------------------------------------
elif page == "📜 紀錄明細查詢":
    st.subheader("📜 歷史出入庫明細")
    df_h = st.session_state['history'].copy()
    if not df_h.empty:
        if not st.session_state['admin_mode']:
            df_h = df_h.drop(columns=[c for c in SENSITIVE_COLUMNS if c in df_h.columns])
        st.dataframe(df_h, use_container_width=True)
    else: st.info("尚無紀錄")

# ------------------------------------------
# 頁面 C: 領料與設計單
# ------------------------------------------
elif page == "🧮 領料與設計單":
    st.subheader("🧮 作品設計/領料單")
    items = st.session_state['inventory'].copy()
    if not items.empty:
        items['lbl'] = items.apply(make_inventory_label, axis=1)
        sel = st.selectbox("選擇材料", items['lbl'], key="design_sel")
        idx = items[items['lbl'] == sel].index[0]
        cur_s = int(float(items.loc[idx, '庫存(顆)']))
        
        col1, col2 = st.columns([1, 2])
        qty = col1.number_input("數量", min_value=0, max_value=max(0, cur_s), value=0)
        
        if col1.button("⬇️ 加入清單"):
            if qty > 0:
                st.session_state['current_design'].append({
                    '編號':items.loc[idx, '編號'], '批號':items.loc[idx, '批號'],
                    '名稱':items.loc[idx, '名稱'], '數量':qty
                })
                st.rerun()
        
        if st.session_state['current_design']:
            ddf = pd.DataFrame(st.session_state['current_design'])
            st.markdown("##### 🛒 領料清單")
            st.table(ddf)
            
            st.markdown("---")
            st.markdown("##### 💰 額外費用計算")
            c_fee1, c_fee2, c_fee3 = st.columns(3)
            shipping_fee = c_fee1.number_input("🚚 運費", min_value=0, value=0, step=10)
            misc_fee = c_fee2.number_input("📦 雜支", min_value=0, value=0, step=10)
            total_fee = shipping_fee + misc_fee
            
            c_fee3.metric(label="💵 費用總計", value=f"${total_fee}")
            design_note = st.text_input("📝 備註")

            st.markdown("---")
            
            if st.button("✅ 領出/售出"):
                fee_note = f" (額外費用:${total_fee})" if total_fee > 0 else ""
                user_note = f" [{design_note}]" if design_note else ""
                
                for x in st.session_state['current_design']:
                    mask = (st.session_state['inventory']['編號'] == x['編號']) & \
                           (st.session_state['inventory']['批號'] == x['批號'])
                    if mask.any():
                        target_idx = st.session_state['inventory'][mask].index[0]
                        st.session_state['inventory'].at[target_idx, '庫存(顆)'] -= x['數量']
                        log = {
                            '紀錄時間': datetime.now().strftime("%Y-%m-%d %H:%M"), 
                            '單號': 'DESIGN', '動作': f"設計單領出{user_note}{fee_note}", 
                            '倉庫': st.session_state['inventory'].at[target_idx, '倉庫'], 
                            '編號': x['編號'], '批號': x['批號'],
                            '分類': st.session_state['inventory'].at[target_idx, '分類'], 
                            '名稱': x['名稱'], 
                            '規格': format_size(st.session_state['inventory'].loc[target_idx]), 
                            '廠商': st.session_state['inventory'].at[target_idx, '進貨廠商'], 
                            '數量變動': -x['數量']
                        }
                        st.session_state['history'] = pd.concat([st.session_state['history'], pd.DataFrame([log])], ignore_index=True)
                
                save_inventory(); save_history()
                st.session_state['current_design'] = []; st.success("庫存已扣除"); st.rerun()
            
            if st.button("🗑️ 清空清單", type="secondary"):
                st.session_state['current_design'] = []; st.rerun()
