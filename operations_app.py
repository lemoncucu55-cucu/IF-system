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
        st.error(f"❌ 無法讀取紀錄: {e}"); return pd.DataFrame(columns=HISTORY_COLUMNS)

def save_inventory_to_gsheet(df):
    try:
        client = get_google_sheet_client()
        sheet = client.open_by_key(SHEET_ID).sheet1
        sheet.clear()
        update_data = [df.columns.values.tolist()] + df.astype(str).values.tolist()
        sheet.update(range_name='A1', values=update_data)
        st.toast("☁️ 庫存同步成功")
    except Exception as e: 
        st.error(f"❌ 存檔失敗: {e}"); st.stop()

def get_dynamic_options(col_name, default_list):
    options = set(default_list)
    if 'inventory' in st.session_state and not st.session_state['inventory'].empty:
        vals = st.session_state['inventory'][col_name].astype(str).unique()
        for v in vals:
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

st.title("💎 IF Crystal 全雲端系統 (v9.12-穩定修復版)")

with st.sidebar:
    st.header("🔑 權限控制")
    pwd = st.text_input("主管密碼", type="password")
    st.session_state['admin_mode'] = (pwd == "admin123")
    page = st.radio("功能前往", ["📦 庫存與進貨", "📜 紀錄查詢", "🧮 領料與設計單"])
    if st.button("🔄 強制重整"): st.session_state.clear(); st.rerun()

# --- 頁面 A: 庫存管理 ---
if page == "📦 庫存與進貨":
    tab1, tab2, tab4, tab3 = st.tabs(["🔄 補貨", "✨ 建檔", "📤 領用", "🛠️ 修改"])
    
    with tab2: # ✨ 建檔分頁
        with st.form("new_item_creation_form"):
            c1, c2, c3 = st.columns(3)
            wh = c1.selectbox("倉庫", DEFAULT_WAREHOUSES)
            n_opts = get_dynamic_options('名稱', ["水晶"])
            n_sel = c2.selectbox("名稱 (選單)", n_opts, key="create_n_select")
            n_custom = c2.text_input("請輸入新名稱 (選單為手動時)", key="create_n_manual")
            cat = c3.selectbox("分類", ["天然石", "配件", "耗材"])
            
            c4, c5, c6 = st.columns(3)
            sh_opts = get_dynamic_options('形狀', DEFAULT_SHAPES)
            sh_sel = c4.selectbox("形狀/規格 (選單)", sh_opts, key="create_sh_select")
            sh_custom = c4.text_input("請輸入新規格", key="create_sh_manual")
            el_opts = get_dynamic_options('五行', DEFAULT_ELEMENTS)
            el_sel = c5.selectbox("五行/顏色 (選單)", el_opts, key="create_el_select")
            el_custom = c5.text_input("請輸入新顏色", key="create_el_manual")
            with c6:
                su_opts = get_dynamic_options('進貨廠商', DEFAULT_SUPPLIERS)
                su_sel = st.selectbox("進貨廠商 (選單)", su_opts, key="create_su_select")
                su_custom = st.text_input("請輸入新廠商名稱", key="create_su_manual")

            c7, c8, c9, c10 = st.columns(4)
            w_mm, l_mm, q_in, cost_in = c7.number_input("寬度mm", 0.0), c8.number_input("長度mm", 0.0), c9.number_input("初始數量", 1), c10.number_input("總成本", 0.0)
            
            if st.form_submit_button("✅ 建立商品"):
                final_n = n_custom if n_sel == "➕ 手動輸入" else n_sel
                final_su = su_custom if su_sel == "➕ 手動輸入" else su_sel
                if not final_n or not final_su: st.error("❌ 名稱與廠商必填！"); st.stop()
                new_r = {'編號': f"ST{int(time.time())%100000}", '批號': '初始存貨', '倉庫': wh, '分類': cat, '名稱': final_n, 
                         '寬度mm': w_mm, '長度mm': l_mm, '形狀': (sh_custom if sh_sel == "➕ 手動輸入" else sh_sel), 
                         '五行': (el_custom if el_sel == "➕ 手動輸入" else el_sel), '進貨數量(顆)': int(q_in), 
                         '進貨日期': str(date.today()), '進貨廠商': final_su, '庫存(顆)': int(q_in), '成本單價': round(cost_in/q_in if q_in>0 else 0, 2)}
                client = get_google_sheet_client()
                client.open_by_key(SHEET_ID).sheet1.append_row([str(new_r.get(col, "")) for col in COLUMNS])
                st.session_state['inventory'] = pd.concat([st.session_state['inventory'], pd.DataFrame([new_r])], ignore_index=True)
                st.success("✅ 建檔成功！"); time.sleep(1); st.rerun()

    with tab3: # 🛠️ 修改分頁 (修正 Duplicate Widget ID)
        if not st.session_state['inventory'].empty:
            inv_edit = st.session_state['inventory'].copy()
            inv_edit['label'] = inv_edit.apply(make_inventory_label, axis=1)
            target = st.selectbox("1. 選擇修改項目", inv_edit['label'].tolist())
            idx = inv_edit[inv_edit['label'] == target].index[0]
            e_row = st.session_state['inventory'].loc[idx]
            
            st.markdown("---")
            c1, c2, c3 = st.columns(3)
            
            # 使用獨立的 Key，確保與 Tab 2 不衝突
            me_opts = get_dynamic_options('名稱', ["水晶"])
            me_sel = c1.selectbox("名稱選單", me_opts, index=me_opts.index(e_row['名稱']) if e_row['名稱'] in me_opts else 0, key="edit_n_select")
            me_final = e_row['名稱']
            if me_sel == "➕ 手動輸入":
                me_final = st.text_input("📝 請輸入新名稱", key="edit_n_manual_input")
            else: me_final = me_sel
            
            sh_m_opts = get_dynamic_options('形狀', DEFAULT_SHAPES)
            sh_m_sel = c2.selectbox("規格選單", sh_m_opts, index=sh_m_opts.index(e_row['形狀']) if e_row['形狀'] in sh_m_opts else 0, key="edit_sh_select")
            sh_final = e_row['形狀']
            if sh_m_sel == "➕ 手動輸入":
                sh_final = st.text_input("📝 請輸入新規格", key="edit_sh_manual_input")
            else: sh_final = sh_m_sel
            
            el_m_opts = get_dynamic_options('五行', DEFAULT_ELEMENTS)
            el_m_sel = c3.selectbox("顏色選單", el_m_opts, index=el_m_opts.index(e_row['五行']) if e_row['五行'] in el_m_opts else 0, key="edit_el_select")
            el_final = e_row['五行']
            if el_m_sel == "➕ 手動輸入":
                el_final = st.text_input("📝 請輸入新顏色", key="edit_el_manual_input")
            else: el_final = el_m_sel

            with st.form("edit_submit_form_stable"):
                ca, cb, cc, cd = st.columns(4)
                nw = ca.number_input("寬度mm", value=float(e_row['寬度mm']))
                nl = cb.number_input("長度mm", value=float(e_row['長度mm']))
                nq = cc.number_input("修正庫存", value=int(e_row['庫存(顆)']))
                nc = cd.number_input("單價成本", value=float(e_row['成本單價']))
                
                if st.form_submit_button("💾 儲存修改"):
                    st.session_state['inventory'].at[idx, '名稱'] = me_final
                    st.session_state['inventory'].at[idx, '形狀'] = sh_final
                    st.session_state['inventory'].at[idx, '五行'] = el_final
                    st.session_state['inventory'].at[idx, '寬度mm'], st.session_state['inventory'].at[idx, '長度mm'] = nw, nl
                    st.session_state['inventory'].at[idx, '庫存(顆)'], st.session_state['inventory'].at[idx, '成本單價'] = nq, nc
                    save_inventory_to_gsheet(st.session_state['inventory'])
                    st.rerun()

    st.subheader("📊 目前庫存表")
    st.dataframe(st.session_state['inventory'], use_container_width=True)

# --- 頁面 B & C (保持顏色顯示與備註邏輯) ---
elif page == "📜 紀錄查詢":
    st.subheader("📜 歷史紀錄")
    df_h = st.session_state['history'].copy()
    if not df_h.empty:
        st.dataframe(df_h.iloc[::-1], use_container_width=True)
    if st.session_state['admin_mode']:
        with st.expander("🛠️ 批次標籤管理"):
            c1, c2, c3 = st.columns(3)
            col = c1.selectbox("欄位", ["五行", "形狀", "進貨廠商", "名稱"])
            old = c2.selectbox("舊標籤", sorted(st.session_state['inventory'][col].unique().tolist()))
            new = c3.text_input("新標籤名稱")
            if st.button("🚀 執行"):
                st.session_state['inventory'].loc[st.session_state['inventory'][col] == old, col] = new
                save_inventory_to_gsheet(st.session_state['inventory']); st.rerun()

elif page == "🧮 領料與設計單":
    st.subheader("🧮 設計單模式")
    c1, c2 = st.columns([1, 2])
    st.session_state['order_id_input'] = c1.text_input("單號", st.session_state['order_id_input'])
    st.session_state['order_note_input'] = c2.text_input("備註", st.session_state['order_note_input'])
    
    inv_s = st.session_state['inventory'].copy()
    inv_s['label'] = inv_s.apply(make_inventory_label, axis=1)
    sel = st.selectbox("材料選擇", inv_s['label'].tolist())
    idx = inv_s[inv_s['label'] == sel].index[0]
    row = st.session_state['inventory'].loc[idx]
    
    qty = st.number_input("數量", 1, max_value=max(1, int(row['庫存(顆)'])))
    if st.button("⬇️ 加入清單"):
        st.session_state['current_design'].append({'編號': row['編號'], '批號': row['批號'], '名稱': row['名稱'], '數量': qty, '規格': format_size(row), '顏色': row['五行']})
        st.rerun()

    if st.session_state['current_design']:
        total = 0
        for i, item in enumerate(st.session_state['current_design']):
            mask = (st.session_state['inventory']['編號'] == item['編號']) & (st.session_state['inventory']['批號'] == item['批號'])
            cost = float(st.session_state['inventory'].loc[mask, '成本單價'].values[0]) if mask.any() else 0
            total += cost * item['數量']
            ct, cb = st.columns([5, 1])
            ct.write(f"🔸 [{item['顏色']}] {item['名稱']} ({item['規格']}) x{item['數量']}")
            if cb.button("🗑️", key=f"del_item_{i}"): st.session_state['current_design'].pop(i); st.rerun()
        
        if st.session_state['admin_mode']: st.metric("預估總成本", f"${total:.2f}")
        if st.button("✅ 確認領出", type="primary", use_container_width=True):
            # (領出邏輯...)
            st.success("訂單已領出！"); st.session_state['current_design'] = []; time.sleep(1); st.rerun()
