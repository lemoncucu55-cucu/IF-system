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

COLUMNS = ['編號', '批號', '倉庫', '分類', '名稱', '寬度mm', '長度mm', '形狀', '五行', '進貨數量(顆)', '進貨日期', '進貨廠商', '庫存(顆)', '成本單價']
HISTORY_COLUMNS = ['紀錄時間', '單號', '動作', '倉庫', '批號', '編號', '分類', '名稱', '規格', '廠商', '數量變動', '成本備註']

DEFAULT_WAREHOUSES = ["Imeng", "千畇"]
DEFAULT_SUPPLIERS = ["小聰頭", "廠商A", "廠商B", "自用", "蝦皮", "淘寶", "TB-東吳天然石坊", "永安", "Rich"]
DEFAULT_SHAPES = ["圓珠", "切角", "鑽切", "圓筒", "方體", "長柱", "不規則", "造型", "原礦"]
DEFAULT_ELEMENTS = ["金", "木", "水", "火", "土", "綜合", "銀", "銅", "14K包金"]

# ==========================================
# 2. 核心功能函式
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
    return gspread.authorize(creds)

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

# ==========================================
# 3. UI 介面
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

st.title("💎 IF Crystal 全雲端系統 (v9.12-清單優化版)")

with st.sidebar:
    st.header("🔑 權限控制")
    pwd = st.text_input("主管密碼", type="password")
    st.session_state['admin_mode'] = (pwd == "admin123")
    page = st.radio("功能前往", ["📦 庫存與進貨", "📜 紀錄查詢", "🧮 領料與設計單"])
    if st.button("🔄 強制重整"): st.session_state.clear(); st.rerun()

# --- 頁面 A & B 邏輯保持不變 ---
if page == "📦 庫存與進貨":
    tab1, tab2, tab4, tab3 = st.tabs(["🔄 補貨", "✨ 建檔", "📤 領用", "🛠️ 修改"])
    # ... (此處代碼與先前一致，包含修改頁面手動輸入框修復)
    with tab3:
        if not st.session_state['inventory'].empty:
            inv_edit = st.session_state['inventory'].copy()
            inv_edit['label'] = inv_edit.apply(make_inventory_label, axis=1)
            edit_target = st.selectbox("1. 選擇修改項目", inv_edit['label'].tolist())
            idx = inv_edit[inv_edit['label'] == edit_target].index[0]
            e_row = st.session_state['inventory'].loc[idx]
            st.markdown("---")
            c1, c2, c3 = st.columns(3)
            me_opts = get_dynamic_options('名稱', ["水晶"])
            me_sel = c1.selectbox("名稱選單", me_opts, index=me_opts.index(e_row['名稱']) if e_row['名稱'] in me_opts else 0)
            me_final = st.text_input("📝 請輸入新名稱", key="edit_n") if me_sel == "➕ 手動輸入" else me_sel
            
            sh_m_opts = get_dynamic_options('形狀', DEFAULT_SHAPES)
            sh_m_sel = c2.selectbox("形狀/規格選單", sh_m_opts, index=sh_m_opts.index(e_row['形狀']) if e_row['形狀'] in sh_m_opts else 0)
            sh_final = st.text_input("📝 請輸入新規格", key="edit_sh") if sh_m_sel == "➕ 手動輸入" else sh_m_sel
            
            el_m_opts = get_dynamic_options('五行', DEFAULT_ELEMENTS)
            el_m_sel = c3.selectbox("五行/顏色選單", el_m_opts, index=el_m_opts.index(e_row['五行']) if e_row['五行'] in el_m_opts else 0)
            el_final = st.text_input("📝 請輸入新顏色", key="edit_el") if el_m_sel == "➕ 手動輸入" else el_m_sel

            with st.form("edit_submit_form"):
                col_a, col_b, col_c, col_d = st.columns(4)
                new_w = col_a.number_input("寬度mm", value=float(e_row['寬度mm']))
                new_l = col_b.number_input("長度mm", value=float(e_row['長度mm']))
                new_q = col_c.number_input("修正庫存", value=int(e_row['庫存(顆)']))
                new_cost = col_d.number_input("單價成本", value=float(e_row['成本單價']))
                if st.form_submit_button("💾 儲存修改"):
                    st.session_state['inventory'].at[idx, '名稱'] = me_final
                    st.session_state['inventory'].at[idx, '形狀'], st.session_state['inventory'].at[idx, '五行'] = sh_final, el_final
                    st.session_state['inventory'].at[idx, '寬度mm'], st.session_state['inventory'].at[idx, '長度mm'] = new_w, new_l
                    st.session_state['inventory'].at[idx, '庫存(顆)'], st.session_state['inventory'].at[idx, '成本單價'] = new_q, new_cost
                    save_inventory_to_gsheet(st.session_state['inventory']); st.rerun()

elif page == "📜 紀錄查詢":
    st.subheader("📜 歷史紀錄與撤銷")
    df_h = st.session_state['history'].copy()
    if not df_h.empty:
        df_h_rev = df_h.iloc[::-1]
        st.dataframe(df_h_rev if st.session_state['admin_mode'] else df_h_rev.drop(columns=['成本備註'], errors='ignore'), use_container_width=True)

# --- 頁面 C: 領料與設計單 (新增顏色顯示) ---
elif page == "🧮 領料與設計單":
    st.subheader("🧮 設計單模式")
    c_oid, c_note = st.columns([1, 2])
    st.session_state['order_id_input'] = c_oid.text_input("單號", st.session_state['order_id_input'])
    st.session_state['order_note_input'] = c_note.text_input("備註 (設計單紀錄)", st.session_state['order_note_input'])
    
    inv_s = st.session_state['inventory'].copy()
    inv_s['label'] = inv_s.apply(make_inventory_label, axis=1)
    sel = st.selectbox("選擇材料", inv_s['label'].tolist())
    idx = inv_s[inv_s['label'] == sel].index[0]
    row = st.session_state['inventory'].loc[idx]
    
    qty = st.number_input("加入數量", 1, max_value=max(1, int(row['庫存(顆)'])), value=1)
    if st.button("⬇️ 加入清單"):
        st.session_state['current_design'].append({
            '編號': row['編號'], 
            '批號': row['批號'], 
            '名稱': row['名稱'], 
            '數量': qty, 
            '規格': format_size(row), 
            '顏色': row['五行'], # 新增存入顏色資訊
            '倉庫': row['倉庫'], 
            '廠商': row['進貨廠商'], 
            '分類': row['分類']
        })
        st.rerun()

    if st.session_state['current_design']:
        st.divider()
        st.markdown("### 🛒 待領領料清單")
        total, d_idx = 0, -1
        for i, item in enumerate(st.session_state['current_design']):
            mask = (st.session_state['inventory']['編號'] == item['編號']) & (st.session_state['inventory']['批號'] == item['批號'])
            u_cost = float(st.session_state['inventory'].loc[mask, '成本單價'].values[0]) if mask.any() else 0
            item_total = u_cost * item['數量']
            total += item_total
            
            c_txt, c_btn = st.columns([5, 1])
            cost_info = f" (💰${u_cost:.2f} | 小計:${item_total:.2f})" if st.session_state['admin_mode'] else ""
            
            # 修改處：在名稱前方加入顏色顯示
            color_prefix = f"[{item['顏色']}] " if item['顏色'] else ""
            c_txt.markdown(f"🔸 {color_prefix}**{item['名稱']}** ({item['規格']}) x{item['數量']} | {item['批號']}{cost_info}")
            
            if c_btn.button("🗑️", key=f"del_{i}"): d_idx = i
        
        if d_idx != -1: st.session_state['current_design'].pop(d_idx); st.rerun()
        if st.session_state['admin_mode']: st.metric("預估總成本", f"${total:,.2f}")
        
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
                s_log = {'紀錄時間': datetime.now().strftime("%Y-%m-%d %H:%M"), '單號': f_oid, '動作': '🏷️ 單據總計', '名稱': '--- 整單彙整 ---', '數量變動': 0, '成本備註': f"💰 管理員紀錄：本單總成本為 ${total:.2f}"}
                st.session_state['history'] = pd.concat([st.session_state['history'], pd.DataFrame([s_log])], ignore_index=True)
            save_inventory_to_gsheet(st.session_state['inventory'])
            save_history_to_gsheet(st.session_state['history'])
            st.session_state['current_design'] = []; st.success("訂單完成！"); time.sleep(1); st.rerun()
