import streamlit as st
import pandas as pd
from datetime import date, datetime
import time
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import numpy as np

# ==========================================
# 1. 核心設定
# ==========================================

SHEET_ID = "1gf-pn034w0oZx8jWDUJvmIyHX_O7eHbiBb9diVSBX0Q"
KEY_FILE = "google_key.json"

COLUMNS = [
    '編號', '批號', '倉庫', '分類', '名稱', 
    '寬度mm', '長度mm', '形狀', '五行', 
    '進貨數量(顆)', '進貨日期', '進貨廠商', 
    '庫存(顆)', '成本單價'
]

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

def append_inventory_row(new_row_dict):
    try:
        client = get_google_sheet_client()
        sheet = client.open_by_key(SHEET_ID).sheet1
        row_values = [str(new_row_dict.get(col, "")) for col in COLUMNS]
        sheet.append_row(row_values)
        return True
    except Exception as e:
        st.error(f"❌ 新增資料失敗: {e}"); return False

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

def save_history_to_gsheet(df):
    try:
        client = get_google_sheet_client()
        sheet = client.open_by_key(SHEET_ID).worksheet("History")
        sheet.clear()
        update_data = [df.columns.values.tolist()] + df.astype(str).values.tolist()
        sheet.update(range_name='A1', values=update_data)
    except Exception as e: st.error(f"❌ 歷史紀錄存檔失敗: {e}")

# ==========================================
# 3. 輔助函式與動態選單
# ==========================================

def get_dynamic_options(col_name, default_list):
    """從現有資料動態提取選單，實現自動記憶"""
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

# ==========================================
# 4. 初始化與介面
# ==========================================

st.set_page_config(page_title="IF Crystal 全雲端系統", layout="wide")

if 'inventory' not in st.session_state:
    st.session_state['inventory'] = load_inventory_from_gsheet()
if 'history' not in st.session_state:
    st.session_state['history'] = load_history_from_gsheet()
if 'admin_mode' not in st.session_state: st.session_state['admin_mode'] = False
if 'current_design' not in st.session_state: st.session_state['current_design'] = []
if 'order_id_input' not in st.session_state: st.session_state['order_id_input'] = f"DES-{date.today().strftime('%Y%m%d')}"
if 'order_note_input' not in st.session_state: st.session_state['order_note_input'] = ""

st.title("💎 IF Crystal 全雲端系統 (v9.12-全功能標籤管理版)")

with st.sidebar:
    st.header("🔑 權限控制")
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
                r_type = c3.radio("方式", ["➕ 合併", "📦 新批號"])
                new_batch = st.text_input("新批號", f"{date.today().strftime('%Y%m%d')}-A") if r_type == "📦 新批號" else row['批號']

                if st.form_submit_button("確認進貨"):
                    final_unit_cost = total_cost_in / qty if qty > 0 else 0
                    if r_type == "➕ 合併":
                        st.session_state['inventory'].at[idx, '庫存(顆)'] += qty
                        st.session_state['inventory'].at[idx, '成本單價'] = round(final_unit_cost, 2)
                        save_inventory_to_gsheet(st.session_state['inventory'])
                        log_act = "補貨(合併)"
                    else:
                        new_r = row.copy()
                        new_r['庫存(顆)'], new_r['進貨數量(顆)'], new_r['進貨日期'], new_r['批號'], new_r['成本單價'] = int(qty), int(qty), str(date.today()), new_batch, round(final_unit_cost, 2)
                        append_inventory_row(new_r)
                        st.session_state['inventory'] = pd.concat([st.session_state['inventory'], pd.DataFrame([new_r])], ignore_index=True)
                        log_act = "補貨新批"
                    
                    log = {'紀錄時間': datetime.now().strftime("%Y-%m-%d %H:%M"), '單號': 'IN', '動作': log_act, '倉庫': row['倉庫'], '批號': new_batch, '編號': row['編號'], '分類': row['分類'], '名稱': row['名稱'], '規格': format_size(row), '廠商': row['進貨廠商'], '數量變動': qty, '成本備註': f"總${total_cost_in:.2f}"}
                    st.session_state['history'] = pd.concat([st.session_state['history'], pd.DataFrame([log])], ignore_index=True)
                    save_history_to_gsheet(st.session_state['history']); st.rerun()

    with tab2: # ✨ 建檔 (修正：補齊所有手動輸入文字框)
        with st.form("new_item"):
            c1, c2, c3 = st.columns(3)
            wh = c1.selectbox("倉庫", DEFAULT_WAREHOUSES)
            
            # 1. 名稱
            with c2:
                n_opts = get_dynamic_options('名稱', ["水晶"])
                n_sel = st.selectbox("名稱 (選單)", n_opts)
                n_custom = ""
                if n_sel == "➕ 手動輸入":
                    n_custom = st.text_input("輸入新名稱", placeholder="例如：OT扣-麥穗")
                n_final = n_custom if n_sel == "➕ 手動輸入" else n_sel
                
            cat = c3.selectbox("分類", ["天然石", "配件", "耗材"])
            
            c4, c5, c6 = st.columns(3)
            
            # 2. 形狀/規格
            with c4:
                sh_opts = get_dynamic_options('形狀', DEFAULT_SHAPES)
                sh_sel = st.selectbox("形狀/規格 (選單)", sh_opts)
                sh_custom = ""
                if sh_sel == "➕ 手動輸入":
                    sh_custom = st.text_input("輸入新規格") # <--- 修正處
                sh_final = sh_custom if sh_sel == "➕ 手動輸入" else sh_sel
                
            # 3. 五行/顏色
            with c5:
                el_opts = get_dynamic_options('五行', DEFAULT_ELEMENTS)
                el_sel = st.selectbox("五行/顏色 (選單)", el_opts)
                el_custom = ""
                if el_sel == "➕ 手動輸入":
                    el_custom = st.text_input("輸入新顏色")
                el_final = el_custom if el_sel == "➕ 手動輸入" else el_sel
            
            # 4. 進貨廠商
            with c6:
                su_opts = get_dynamic_options('進貨廠商', DEFAULT_SUPPLIERS)
                su_sel = st.selectbox("進貨廠商 (選單)", su_opts)
                su_custom = ""
                if su_sel == "➕ 手動輸入":
                    su_custom = st.text_input("請輸入新廠商名稱")
                su_final = su_custom if su_sel == "➕ 手動輸入" else su_sel

            c7, c8, c9, c10 = st.columns(4)
            w_mm, l_mm = c7.number_input("寬度mm", 0.0, step=0.1), c8.number_input("長度mm", 0.0, step=0.1)
            q_in, cost_in = c9.number_input("初始數量", 1), c10.number_input("💰 初始總成本", 0.0)
            
            if st.form_submit_button("建立商品"):
                if not n_final or not su_final: st.error("❌ 名稱與廠商為必填！"); st.stop()
                final_u_cost = cost_in / q_in if q_in > 0 else 0
                new_r = {
                    '編號': f"ST{int(time.time())%100000}", '批號': '初始存貨', '倉庫': wh, '分類': cat, 
                    '名稱': n_final, '寬度mm': w_mm, '長度mm': l_mm, '形狀': sh_final, '五行': el_final,
                    '進貨數量(顆)': int(q_in), '進貨日期': str(date.today()), '進貨廠商': su_final,
                    '庫存(顆)': int(q_in), '成本單價': round(final_u_cost, 2)
                }
                if append_inventory_row(new_r):
                    st.session_state['inventory'] = pd.concat([st.session_state['inventory'], pd.DataFrame([new_r])], ignore_index=True)
                    st.success("✅ 建檔成功"); time.sleep(1); st.rerun()

    with tab4: # 📤 快速領用
        if not st.session_state['inventory'].empty:
            inv_sorted = st.session_state['inventory'].copy()
            inv_sorted['label'] = inv_sorted.apply(make_inventory_label, axis=1)
            target_out = st.selectbox("選擇領用商品", inv_sorted['label'].tolist(), key="q_out")
            idx_out = inv_sorted[inv_sorted['label'] == target_out].index[0]
            row_out = st.session_state['inventory'].loc[idx_out]
            with st.form("quick_out"):
                q_qty = st.number_input("領用數量", 1, max_value=max(1, int(row_out['庫存(顆)'])))
                if st.form_submit_button("確認領出"):
                    st.session_state['inventory'].at[idx_out, '庫存(顆)'] -= q_qty
                    log = {'紀錄時間': datetime.now().strftime("%Y-%m-%d %H:%M"), '單號': 'OUT', '動作': '快速領用', '倉庫': row_out['倉庫'], '批號': row_out['批號'], '編號': row_out['編號'], '分類': row_out['分類'], '名稱': row_out['名稱'], '規格': format_size(row_out), '廠商': row_out['進貨廠商'], '數量變動': -q_qty, '成本備註': '快速領用'}
                    st.session_state['history'] = pd.concat([st.session_state['history'], pd.DataFrame([log])], ignore_index=True)
                    save_inventory_to_gsheet(st.session_state['inventory'])
                    save_history_to_gsheet(st.session_state['history']); st.rerun()

    with tab3: # 🛠️ 修改
        if not st.session_state['inventory'].empty:
            inv_edit = st.session_state['inventory'].copy()
            inv_edit['label'] = inv_edit.apply(make_inventory_label, axis=1)
            edit_target = st.selectbox("選擇修改項目", inv_edit['label'].tolist())
            idx = inv_edit[inv_edit['label'] == edit_target].index[0]
            e_row = st.session_state['inventory'].loc[idx]
            with st.form("edit_form"):
                c1, c2, c3 = st.columns(3)
                
                # 名稱修改
                with c1:
                    n_m_opts = get_dynamic_options('名稱', ["水晶"])
                    n_m_sel = st.selectbox("名稱", n_m_opts, index=n_m_opts.index(e_row['名稱']) if e_row['名稱'] in n_m_opts else 0)
                    n_m_custom = ""
                    if n_m_sel == "➕ 手動輸入":
                        n_m_custom = st.text_input("新名稱")
                    n_m_final = n_m_custom if n_m_sel == "➕ 手動輸入" else n_m_sel
                    
                ew, el = c2.number_input("寬度mm", value=float(e_row['寬度mm'])), c3.number_input("長度mm", value=float(e_row['長度mm']))
                
                c4, c5, c6, c7 = st.columns(4)
                
                # 形狀修改
                with c4:
                    sh_m_opts = get_dynamic_options('形狀', DEFAULT_SHAPES)
                    sh_m_sel = st.selectbox("形狀", sh_m_opts, index=sh_m_opts.index(e_row['形狀']) if e_row['形狀'] in sh_m_opts else 0)
                    sh_m_custom = ""
                    if sh_m_sel == "➕ 手動輸入":
                        sh_m_custom = st.text_input("新規格")
                    sh_m_final = sh_m_custom if sh_m_sel == "➕ 手動輸入" else sh_m_sel
                    
                # 五行修改
                with c5:
                    el_m_opts = get_dynamic_options('五行', DEFAULT_ELEMENTS)
                    el_m_sel = st.selectbox("五行/顏色", el_m_opts, index=el_m_opts.index(e_row['五行']) if e_row['五行'] in el_m_opts else 0)
                    el_m_custom = ""
                    if el_m_sel == "➕ 手動輸入":
                        el_m_custom = st.text_input("新顏色")
                    el_m_final = el_m_custom if el_m_sel == "➕ 手動輸入" else el_m_sel
                    
                en6, en7 = c6.number_input("修正庫存", value=int(e_row['庫存(顆)'])), c7.number_input("單價成本", value=float(e_row['成本單價']))
                
                if st.form_submit_button("💾 儲存修改"):
                    st.session_state['inventory'].at[idx, '名稱'] = n_m_final
                    st.session_state['inventory'].at[idx, '寬度mm'], st.session_state['inventory'].at[idx, '長度mm'] = ew, el
                    st.session_state['inventory'].at[idx, '形狀'], st.session_state['inventory'].at[idx, '五行'] = sh_m_final, el_m_final
                    st.session_state['inventory'].at[idx, '庫存(顆)'], st.session_state['inventory'].at[idx, '成本單價'] = en6, en7
                    save_inventory_to_gsheet(st.session_state['inventory']); st.rerun()

    st.divider()
    st.subheader("📊 目前庫存表")
    df_dis = st.session_state['inventory'].copy()
    if not st.session_state['admin_mode']: df_dis = df_dis.drop(columns=['成本單價', '進貨廠商'], errors='ignore')
    st.dataframe(df_dis, use_container_width=True)

# ------------------------------------------
# 頁面 B: 紀錄查詢
# ------------------------------------------
elif page == "📜 紀錄查詢":
    st.subheader("📜 歷史紀錄與撤銷")
    df_h = st.session_state['history'].copy()
    if not df_h.empty:
        df_h_rev = df_h.iloc[::-1]
        if not st.session_state['admin_mode']:
            st.dataframe(df_h_rev.drop(columns=['成本備註'], errors='ignore'), use_container_width=True)
        else:
            st.dataframe(df_h_rev, use_container_width=True)
            for idx, row in df_h_rev.iterrows():
                with st.expander(f"{row['紀錄時間']} | {row['動作']} - {row['名稱']}"):
                    c1, c2 = st.columns([4, 1])
                    c1.write(f"倉庫: {row['倉庫']} | 變動: {row['數量變動']} | 備註: {row['成本備註']}")
                    if row['動作'] != '🏷️ 單據總計':
                        if c2.button("🗑️ 撤銷紀錄", key=f"rev_{idx}"):
                            mask = (st.session_state['inventory']['編號'] == row['編號']) & (st.session_state['inventory']['批號'] == row['批號'])
                            if mask.any():
                                i_idx = st.session_state['inventory'][mask].index[0]
                                st.session_state['inventory'].at[i_idx, '庫存(顆)'] -= float(row['數量變動'])
                                st.session_state['history'] = st.session_state['history'].drop(idx)
                                save_inventory_to_gsheet(st.session_state['inventory'])
                                save_history_to_gsheet(st.session_state['history']); st.rerun()

    # --- 批次標籤管理 ---
    if st.session_state['admin_mode']:
        st.divider()
        with st.expander("🛠️ 選單標籤管理 (批次更名/清理)"):
            st.info("💡 在此可將庫存中所有的「金-白K金」一鍵替換為「白K金」。")
            c1, c2, c3 = st.columns(3)
            manage_col = c1.selectbox("1. 選擇欄位", ["五行", "形狀", "進貨廠商", "名稱", "分類"])
            current_tags = sorted(st.session_state['inventory'][manage_col].unique().tolist())
            old_tag = c2.selectbox("2. 選擇舊標籤", current_tags)
            new_tag = c3.text_input("3. 輸入新名稱")
            if st.button("🚀 執行批次替換"):
                if new_tag:
                    mask = st.session_state['inventory'][manage_col] == old_tag
                    count = mask.sum()
                    if count > 0:
                        st.session_state['inventory'].loc[mask, manage_col] = new_tag
                        save_inventory_to_gsheet(st.session_state['inventory'])
                        st.success(f"✅ 已將 {count} 筆資料替換為「{new_tag}」"); time.sleep(1); st.rerun()

# ------------------------------------------
# 頁面 C: 領料與設計單
# ------------------------------------------
elif page == "🧮 領料與設計單":
    st.subheader("🧮 設計單模式")
    c_oid, c_note = st.columns([1, 2])
    st.session_state['order_id_input'] = c_oid.text_input("單號", st.session_state['order_id_input'])
    st.session_state['order_note_input'] = c_note.text_input("備註", st.session_state['order_note_input'])
    
    inv_sorted = st.session_state['inventory'].copy()
    inv_sorted['label'] = inv_sorted.apply(make_inventory_label, axis=1)
    sel = st.selectbox("選擇材料", inv_sorted['label'].tolist())
    idx = inv_sorted[inv_sorted['label'] == sel].index[0]
    row = st.session_state['inventory'].loc[idx]
    
    qty = st.number_input("加入數量", 1, max_value=max(1, int(row['庫存(顆)'])), value=1)
    if st.button("⬇️ 加入清單"):
        st.session_state['current_design'].append({'編號': row['編號'], '批號': row['批號'], '名稱': row['名稱'], '數量': qty, '規格': format_size(row), '倉庫': row['倉庫'], '廠商': row['進貨廠商'], '分類': row['分類']})
        st.rerun()

    if st.session_state['current_design']:
        st.divider()
        st.markdown("### 🛒 待領領料清單")
        grand_total, delete_idx = 0, -1
        for i, item in enumerate(st.session_state['current_design']):
            mask = (st.session_state['inventory']['編號'] == item['編號']) & (st.session_state['inventory']['批號'] == item['批號'])
            u_cost = float(st.session_state['inventory'].loc[mask, '成本單價'].values[0]) if mask.any() else 0
            item_total = u_cost * item['數量']
            grand_total += item_total
            cost_detail = f" (💰單價:${u_cost:.2f} | **小計:${item_total:.2f}**)" if st.session_state['admin_mode'] else ""
            c_txt, c_btn = st.columns([5, 1])
            c_txt.markdown(f"🔸 **{item['名稱']}** ({item['規格']}) x{item['數量']} | 批號: {item['批號']}{cost_detail}")
            if c_btn.button("🗑️", key=f"del_{i}"): delete_idx = i
        
        if delete_idx != -1: st.session_state['current_design'].pop(delete_idx); st.rerun()
            
        st.divider()
        if st.session_state['admin_mode']: st.metric("預估總成本", f"${grand_total:,.2f}")
        
        if st.button("✅ 確認領出 (同步至雲端)", type="primary", use_container_width=True):
            f_oid = st.session_state['order_id_input']
            for x in st.session_state['current_design']:
                mask = (st.session_state['inventory']['編號'] == x['編號']) & (st.session_state['inventory']['批號'] == x['批號'])
                if mask.any():
                    t_idx = st.session_state['inventory'][mask].index[0]
                    st.session_state['inventory'].at[t_idx, '庫存(顆)'] -= x['數量']
                    log = {'紀錄時間': datetime.now().strftime("%Y-%m-%d %H:%M"), '單號': f_oid, '動作': '設計單領出', '倉庫': x['倉庫'], '編號': x['編號'], '批號': x['批號'], '名稱': x['名稱'], '分類': x['分類'], '規格': x['規格'], '廠商': x['廠商'], '數量變動': -x['數量'], '成本備註': st.session_state['order_note_input']}
                    st.session_state['history'] = pd.concat([st.session_state['history'], pd.DataFrame([log])], ignore_index=True)
            
            if st.session_state['admin_mode']:
                s_log = {'紀錄時間': datetime.now().strftime("%Y-%m-%d %H:%M"), '單號': f_oid, '動作': '🏷️ 單據總計', '名稱': '--- 整單彙整 ---', '數量變動': 0, '成本備註': f"💰 管理員紀錄：本單總成本為 ${grand_total:.2f}"}
                st.session_state['history'] = pd.concat([st.session_state['history'], pd.DataFrame([s_log])], ignore_index=True)
            save_inventory_to_gsheet(st.session_state['inventory'])
            save_history_to_gsheet(st.session_state['history'])
            st.session_state['current_design'] = []; st.success("訂單完成！"); time.sleep(1); st.rerun()
