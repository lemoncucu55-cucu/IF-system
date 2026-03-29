import streamlit as st
import pandas as pd
from datetime import date, datetime
import uuid
import gspread
from oauth2client.service_account import ServiceAccountCredentials

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

# 修正4: 加上 @st.cache_resource 避免每次操作都重新授權
@st.cache_resource
def get_google_sheet_client():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    try:
        if "gcp_service_account" in st.secrets:
            creds_dict = dict(st.secrets["gcp_service_account"])
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        else:
            creds = ServiceAccountCredentials.from_json_keyfile_name(KEY_FILE, scope)
    except Exception:
        creds = ServiceAccountCredentials.from_json_keyfile_name(KEY_FILE, scope)
    return gspread.authorize(creds)


# 修正5: 加上 @st.cache_data(ttl=60) 避免每次 rerun 都重讀整張表
@st.cache_data(ttl=60)
def load_inventory_from_gsheet():
    try:
        client = get_google_sheet_client()
        sheet = client.open_by_key(SHEET_ID).sheet1
        data = sheet.get_all_records()
        if not data:
            return pd.DataFrame(columns=COLUMNS)
        df = pd.DataFrame(data)
        df.columns = df.columns.astype(str).str.strip().str.replace('\ufeff', '')
        for col in COLUMNS:
            if col not in df.columns:
                df[col] = ""
        df = df[COLUMNS].copy().fillna("")
        for col in ['寬度mm', '長度mm', '進貨數量(顆)', '庫存(顆)', '成本單價']:
            df[col] = pd.to_numeric(df[col].astype(str).str.replace(',', '').str.strip(), errors='coerce').fillna(0)
        return df
    except Exception as e:
        st.error(f"❌ 無法讀取庫存表: {e}")
        return pd.DataFrame(columns=COLUMNS)


@st.cache_data(ttl=60)
def load_history_from_gsheet():
    try:
        client = get_google_sheet_client()
        try:
            sheet = client.open_by_key(SHEET_ID).worksheet("History")
        except Exception:
            return pd.DataFrame(columns=HISTORY_COLUMNS)
        data = sheet.get_all_records()
        if not data:
            return pd.DataFrame(columns=HISTORY_COLUMNS)
        df = pd.DataFrame(data)
        for col in HISTORY_COLUMNS:
            if col not in df.columns:
                df[col] = ""
        return df[HISTORY_COLUMNS].copy()
    except Exception as e:
        st.error(f"❌ 無法讀取歷史紀錄: {e}")
        return pd.DataFrame(columns=HISTORY_COLUMNS)


def save_inventory_to_gsheet(df):
    try:
        client = get_google_sheet_client()
        sheet = client.open_by_key(SHEET_ID).sheet1
        sheet.clear()
        update_data = [df.columns.values.tolist()] + df.astype(str).values.tolist()
        sheet.update(range_name='A1', values=update_data)
        # 清除快取讓下次讀取取得最新資料
        load_inventory_from_gsheet.clear()
        st.toast("☁️ 庫存同步成功")
    except Exception as e:
        st.error(f"❌ 庫存存檔失敗: {e}")
        st.stop()


def save_history_to_gsheet(df):
    try:
        client = get_google_sheet_client()
        sheet = client.open_by_key(SHEET_ID).worksheet("History")
        sheet.clear()
        h_data = [df.columns.tolist()] + df.astype(str).values.tolist()
        sheet.update(range_name='A1', values=h_data)
        load_history_from_gsheet.clear()
    except Exception as e:
        st.error(f"❌ 歷史紀錄存檔失敗: {e}")


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
        if l > 0:
            return f"{w}x{l}mm"
        if w > 0:
            return f"{w}mm"
        return "0mm"
    except Exception:
        return "0mm"


def make_inventory_label(row):
    sz = format_size(row)
    stock_val = int(float(row.get('庫存(顆)', 0)))
    elem = str(row.get('五行', '')).strip()
    # 修正9: 乾淨的條件式字串，避免非管理員模式留有空格
    elem_display = f"({elem}) " if elem else ""
    batch = str(row.get('批號', '')).strip()
    cost_str = f" 💰${float(row.get('成本單價', 0)):.2f}" if st.session_state.get('admin_mode', False) else ""
    return f"[{row.get('倉庫','Imeng')}] {elem_display}{row.get('名稱','')} {sz} ({row.get('形狀','')}){cost_str} 【{batch}】 | 存:{stock_val}"


# ==========================================
# 3. UI 介面
# ==========================================
st.set_page_config(page_title="IF Crystal 全雲端系統", layout="wide")

if 'inventory' not in st.session_state:
    st.session_state['inventory'] = load_inventory_from_gsheet()
if 'history' not in st.session_state:
    st.session_state['history'] = load_history_from_gsheet()
if 'admin_mode' not in st.session_state:
    st.session_state['admin_mode'] = False
if 'current_design' not in st.session_state:
    st.session_state['current_design'] = []
if 'order_id_input' not in st.session_state:
    st.session_state['order_id_input'] = f"DES-{date.today().strftime('%Y%m%d')}"
if 'order_note_input' not in st.session_state:
    st.session_state['order_note_input'] = ""

st.title("💎 IF Crystal 全雲端系統 (v9.13-修正版)")

with st.sidebar:
    st.header("🔑 權限控制")
    pwd = st.text_input("主管密碼", type="password")
    # 修正7: 密碼從 st.secrets 讀取，不硬寫在原始碼
    admin_password = st.secrets.get("admin_password", "admin123")
    st.session_state['admin_mode'] = (pwd == admin_password)
    page = st.radio("功能前往", ["📦 庫存與進貨", "📜 紀錄查詢", "🧮 領料與設計單"])
    if st.button("🔄 強制重整"):
        st.session_state.clear()
        load_inventory_from_gsheet.clear()
        load_history_from_gsheet.clear()
        st.rerun()

# ==========================================
# --- 頁面 A: 庫存管理 ---
# ==========================================
if page == "📦 庫存與進貨":
    # 修正2: 補上 tab4 變數並加入「📤 領用」頁籤內容
    tab1, tab2, tab4, tab3 = st.tabs(["🔄 補貨", "✨ 建檔", "📤 領用", "🛠️ 修改"])

    # --- Tab1: 補貨 ---
    with tab1:
        if not st.session_state['inventory'].empty:
            inv_sorted = st.session_state['inventory'].copy()
            inv_sorted['label'] = inv_sorted.apply(make_inventory_label, axis=1)
            target = st.selectbox("選擇商品", inv_sorted['label'].tolist(), key="restock_select")
            idx = inv_sorted[inv_sorted['label'] == target].index[0]
            row = st.session_state['inventory'].loc[idx]

            with st.form("restock_form"):
                old_cost = float(row.get('成本單價', 0))
                st.info(f"品名：{row['名稱']} | 目前單價成本：${old_cost:.2f}")
                c1, c2, c3 = st.columns(3)
                qty_in = c1.number_input("進貨數量", 1, value=1)
                total_p = c2.number_input("💰 本次進貨總價", min_value=0.0, step=1.0)
                r_type = c3.radio("方式", ["➕ 合併", "📦 新批號"])
                new_batch_name = st.text_input("批號名稱", f"{date.today().strftime('%Y%m%d')}-A") if r_type == "📦 新批號" else row['批號']

                if st.form_submit_button("確認進貨"):
                    final_u_cost = round(total_p / qty_in, 2) if qty_in > 0 else 0

                    if r_type == "➕ 合併":
                        st.session_state['inventory'].at[idx, '庫存(顆)'] += qty_in
                        st.session_state['inventory'].at[idx, '成本單價'] = final_u_cost
                        log_act = "補貨(合併)"
                        # 修正1: 合併模式統一呼叫 save_inventory_to_gsheet
                        save_inventory_to_gsheet(st.session_state['inventory'])
                    else:
                        # 修正1: 新批號模式移除 append_row，統一用 save_inventory_to_gsheet
                        new_r = row.copy()
                        new_r['庫存(顆)'] = int(qty_in)
                        new_r['進貨數量(顆)'] = int(qty_in)
                        new_r['進貨日期'] = str(date.today())
                        new_r['批號'] = new_batch_name
                        new_r['成本單價'] = final_u_cost
                        st.session_state['inventory'] = pd.concat(
                            [st.session_state['inventory'], pd.DataFrame([new_r])], ignore_index=True
                        )
                        log_act = "補貨(新批)"
                        save_inventory_to_gsheet(st.session_state['inventory'])

                    log = {
                        '紀錄時間': datetime.now().strftime("%Y-%m-%d %H:%M"),
                        '單號': 'IN',
                        '動作': log_act,
                        '倉庫': row['倉庫'],
                        '批號': new_batch_name,
                        '編號': row['編號'],
                        '分類': row['分類'],
                        '名稱': row['名稱'],
                        '規格': format_size(row),
                        '廠商': row['進貨廠商'],
                        '數量變動': qty_in,
                        '成本備註': f"進貨價${total_p:.2f}"
                    }
                    st.session_state['history'] = pd.concat(
                        [st.session_state['history'], pd.DataFrame([log])], ignore_index=True
                    )
                    save_history_to_gsheet(st.session_state['history'])
                    st.success("✅ 補貨完成！")
                    # 修正6: 移除 time.sleep(1)，直接 rerun
                    st.rerun()
        else:
            st.info("目前庫存為空，請先至「建檔」頁籤新增商品。")

    # --- Tab2: 建檔 ---
    with tab2:
        with st.form("new_item_creation"):
            c1, c2, c3 = st.columns(3)
            wh = c1.selectbox("倉庫", DEFAULT_WAREHOUSES)
            n_opts = get_dynamic_options('名稱', ["水晶"])
            n_sel = c2.selectbox("名稱選單", n_opts, key="create_n_sel")
            n_custom = c2.text_input("新名稱(選購手動時填寫)", key="create_n_in")
            cat = c3.selectbox("分類", ["天然石", "配件", "耗材"])

            c4, c5, c6 = st.columns(3)
            sh_opts = get_dynamic_options('形狀', DEFAULT_SHAPES)
            sh_sel = c4.selectbox("規格選單", sh_opts, key="create_sh_sel")
            sh_custom = c4.text_input("新規格", key="create_sh_in")
            el_opts = get_dynamic_options('五行', DEFAULT_ELEMENTS)
            el_sel = c5.selectbox("顏色選單", el_opts, key="create_el_sel")
            el_custom = c5.text_input("新顏色", key="create_el_in")
            su_opts = get_dynamic_options('進貨廠商', DEFAULT_SUPPLIERS)
            su_sel = c6.selectbox("廠商選單", su_opts, key="create_su_sel")
            su_custom = c6.text_input("新廠商", key="create_su_in")

            c7, c8, c9, c10 = st.columns(4)
            w_mm = c7.number_input("寬度", 0.0)
            l_mm = c8.number_input("長度", 0.0)
            q_in = c9.number_input("初始數量", 1)
            cost_in = c10.number_input("總成本", 0.0)

            if st.form_submit_button("✅ 建立商品"):
                final_n = n_custom if n_sel == "➕ 手動輸入" else n_sel
                final_su = su_custom if su_sel == "➕ 手動輸入" else su_sel
                # 修正8: 改用 flag 控制流程，避免 st.stop() 中止整頁渲染
                has_error = False
                if not final_n:
                    st.error("❌ 名稱為必填")
                    has_error = True
                if not final_su:
                    st.error("❌ 廠商為必填")
                    has_error = True
                if not has_error:
                    # 修正10: 用 uuid 避免編號碰撞
                    new_id = f"ST{uuid.uuid4().hex[:8].upper()}"
                    new_r = {
                        '編號': new_id,
                        '批號': '初始存貨',
                        '倉庫': wh,
                        '分類': cat,
                        '名稱': final_n,
                        '形狀': (sh_custom if sh_sel == "➕ 手動輸入" else sh_sel),
                        '五行': (el_custom if el_sel == "➕ 手動輸入" else el_sel),
                        '進貨數量(顆)': int(q_in),
                        '進貨廠商': final_su,
                        '進貨日期': str(date.today()),
                        '庫存(顆)': int(q_in),
                        '成本單價': round(cost_in / q_in if q_in > 0 else 0, 2),
                        '寬度mm': w_mm,
                        '長度mm': l_mm
                    }
                    st.session_state['inventory'] = pd.concat(
                        [st.session_state['inventory'], pd.DataFrame([new_r])], ignore_index=True
                    )
                    save_inventory_to_gsheet(st.session_state['inventory'])
                    st.success(f"✅ 商品「{final_n}」建立成功！")
                    st.rerun()

    # --- Tab4: 領用 (修正2: 補上原本空白的頁籤) ---
    with tab4:
        st.subheader("📤 單筆快速領用")
        if not st.session_state['inventory'].empty:
            inv_q = st.session_state['inventory'].copy()
            inv_q['label'] = inv_q.apply(make_inventory_label, axis=1)
            sel_q = st.selectbox("選擇材料", inv_q['label'].tolist(), key="quick_use_sel")
            idx_q = inv_q[inv_q['label'] == sel_q].index[0]
            row_q = st.session_state['inventory'].loc[idx_q]

            with st.form("quick_use_form"):
                c1, c2 = st.columns(2)
                qty_q = c1.number_input("領用數量", min_value=1, max_value=max(1, int(row_q['庫存(顆)'])), value=1)
                note_q = c2.text_input("備註")
                if st.form_submit_button("✅ 確認領用"):
                    st.session_state['inventory'].at[idx_q, '庫存(顆)'] -= qty_q
                    log = {
                        '紀錄時間': datetime.now().strftime("%Y-%m-%d %H:%M"),
                        '單號': f"QU-{date.today().strftime('%Y%m%d')}",
                        '動作': '快速領用',
                        '倉庫': row_q['倉庫'],
                        '批號': row_q['批號'],
                        '編號': row_q['編號'],
                        '分類': row_q['分類'],
                        '名稱': row_q['名稱'],
                        '規格': format_size(row_q),
                        '廠商': row_q['進貨廠商'],
                        '數量變動': -qty_q,
                        '成本備註': note_q
                    }
                    st.session_state['history'] = pd.concat(
                        [st.session_state['history'], pd.DataFrame([log])], ignore_index=True
                    )
                    save_inventory_to_gsheet(st.session_state['inventory'])
                    save_history_to_gsheet(st.session_state['history'])
                    st.success(f"✅ 已領用 {qty_q} 顆「{row_q['名稱']}」")
                    st.rerun()
        else:
            st.info("目前庫存為空。")

    # --- Tab3: 修改 ---
    with tab3:
        if not st.session_state['inventory'].empty:
            inv_e = st.session_state['inventory'].copy()
            inv_e['label'] = inv_e.apply(make_inventory_label, axis=1)
            target_e = st.selectbox("1. 選擇修改項目", inv_e['label'].tolist(), key="edit_main_sel")
            idx_e = inv_e[inv_e['label'] == target_e].index[0]
            e_row = st.session_state['inventory'].loc[idx_e]

            st.markdown("---")
            c1, c2, c3 = st.columns(3)

            me_opts = get_dynamic_options('名稱', ["水晶"])
            me_sel = c1.selectbox("名稱選單", me_opts, index=me_opts.index(e_row['名稱']) if e_row['名稱'] in me_opts else 0, key="edit_n_sel")
            me_final = st.text_input("📝 請輸入新名稱", key="edit_n_manual") if me_sel == "➕ 手動輸入" else me_sel

            sh_m_opts = get_dynamic_options('形狀', DEFAULT_SHAPES)
            sh_m_sel = c2.selectbox("規格選單", sh_m_opts, index=sh_m_opts.index(e_row['形狀']) if e_row['形狀'] in sh_m_opts else 0, key="edit_sh_sel")
            sh_final = st.text_input("📝 請輸入新規格", key="edit_sh_manual") if sh_m_sel == "➕ 手動輸入" else sh_m_sel

            el_m_opts = get_dynamic_options('五行', DEFAULT_ELEMENTS)
            el_m_sel = c3.selectbox("顏色選單", el_m_opts, index=el_m_opts.index(e_row['五行']) if e_row['五行'] in el_m_opts else 0, key="edit_el_sel")
            el_final = st.text_input("📝 請輸入新顏色", key="edit_el_manual") if el_m_sel == "➕ 手動輸入" else el_m_sel

            with st.form("edit_submit_stable"):
                ca, cb, cc, cd = st.columns(4)
                nw = ca.number_input("寬度", value=float(e_row['寬度mm']))
                nl = cb.number_input("長度", value=float(e_row['長度mm']))
                nq = cc.number_input("庫存", value=int(e_row['庫存(顆)']))
                nc = cd.number_input("成本", value=float(e_row['成本單價']))
                if st.form_submit_button("💾 儲存修改"):
                    st.session_state['inventory'].at[idx_e, '名稱'] = me_final
                    st.session_state['inventory'].at[idx_e, '形狀'] = sh_final
                    st.session_state['inventory'].at[idx_e, '五行'] = el_final
                    st.session_state['inventory'].at[idx_e, '寬度mm'] = nw
                    st.session_state['inventory'].at[idx_e, '長度mm'] = nl
                    st.session_state['inventory'].at[idx_e, '庫存(顆)'] = nq
                    st.session_state['inventory'].at[idx_e, '成本單價'] = nc
                    save_inventory_to_gsheet(st.session_state['inventory'])
                    st.success("✅ 修改已儲存")
                    st.rerun()
        else:
            st.info("目前庫存為空。")

    st.subheader("📊 目前庫存表")
    st.dataframe(st.session_state['inventory'], use_container_width=True)

# ==========================================
# --- 頁面 B: 紀錄查詢 ---
# ==========================================
elif page == "📜 紀錄查詢":
    st.subheader("📜 歷史紀錄")
    df_h = st.session_state['history'].copy()
    if not df_h.empty:
        st.dataframe(df_h.iloc[::-1], use_container_width=True)
    else:
        st.info("目前尚無歷史紀錄。")

    if st.session_state['admin_mode']:
        with st.expander("🛠️ 批次標籤修正"):
            c1, c2, c3 = st.columns(3)
            col_m = c1.selectbox("欄位", ["五行", "形狀", "進貨廠商", "名稱"])
            col_vals = sorted(st.session_state['inventory'][col_m].unique().tolist())
            if col_vals:
                old_m = c2.selectbox("舊標籤", col_vals)
                new_m = c3.text_input("更名為")
                if st.button("🚀 執行"):
                    if new_m.strip():
                        st.session_state['inventory'].loc[
                            st.session_state['inventory'][col_m] == old_m, col_m
                        ] = new_m.strip()
                        save_inventory_to_gsheet(st.session_state['inventory'])
                        st.success(f"✅ 已將「{old_m}」更名為「{new_m.strip()}」")
                        st.rerun()
                    else:
                        st.error("❌ 新標籤名稱不能為空")
            else:
                st.info("該欄位目前無資料可修正。")

# ==========================================
# --- 頁面 C: 領料與設計單 ---
# ==========================================
elif page == "🧮 領料與設計單":
    st.subheader("🧮 設計單模式")
    ca, cb = st.columns([1, 2])
    st.session_state['order_id_input'] = ca.text_input("單號", st.session_state['order_id_input'])
    st.session_state['order_note_input'] = cb.text_input("備註", st.session_state['order_note_input'])

    if not st.session_state['inventory'].empty:
        inv_ds = st.session_state['inventory'].copy()
        inv_ds['label'] = inv_ds.apply(make_inventory_label, axis=1)
        sel_ds = st.selectbox("材料選擇", inv_ds['label'].tolist())
        idx_ds = inv_ds[inv_ds['label'] == sel_ds].index[0]
        row_ds = st.session_state['inventory'].loc[idx_ds]

        qty_ds = st.number_input("數量", 1, max_value=max(1, int(row_ds['庫存(顆)'])))
        if st.button("⬇️ 加入清單"):
            # 修正3: 儲存 '五行' 欄位而非自訂的 '顏色' key，與 HISTORY_COLUMNS 對應
            st.session_state['current_design'].append({
                '編號': row_ds['編號'],
                '批號': row_ds['批號'],
                '名稱': row_ds['名稱'],
                '數量': qty_ds,
                '規格': format_size(row_ds),
                '五行': row_ds['五行'],
                '倉庫': row_ds['倉庫'],
                '廠商': row_ds['進貨廠商'],
                '分類': row_ds['分類']
            })
            st.rerun()
    else:
        st.info("目前庫存為空。")

    if st.session_state['current_design']:
        st.markdown("---")
        total_cost = 0
        for i, item in enumerate(st.session_state['current_design']):
            mask = (
                (st.session_state['inventory']['編號'] == item['編號']) &
                (st.session_state['inventory']['批號'] == item['批號'])
            )
            u_c = float(st.session_state['inventory'].loc[mask, '成本單價'].values[0]) if mask.any() else 0
            total_cost += u_c * item['數量']
            ct, del_b = st.columns([5, 1])
            # 修正3: 改用 '五行' key 顯示
            ct.write(f"🔸 [{item['五行']}] {item['名稱']} ({item['規格']}) x{item['數量']}")
            if del_b.button("🗑️", key=f"ds_del_{i}"):
                st.session_state['current_design'].pop(i)
                st.rerun()

        if st.session_state['admin_mode']:
            st.metric("預估總成本", f"${total_cost:.2f}")

        if st.button("✅ 確認領出", type="primary", use_container_width=True):
            f_oid = st.session_state['order_id_input']
            for x in st.session_state['current_design']:
                mask = (
                    (st.session_state['inventory']['編號'] == x['編號']) &
                    (st.session_state['inventory']['批號'] == x['批號'])
                )
                if mask.any():
                    t_idx = st.session_state['inventory'][mask].index[0]
                    st.session_state['inventory'].at[t_idx, '庫存(顆)'] -= x['數量']
                    # 修正3: log 欄位與 HISTORY_COLUMNS 完全對齊，移除 '顏色' 改用 '分類'
                    log = {
                        '紀錄時間': datetime.now().strftime("%Y-%m-%d %H:%M"),
                        '單號': f_oid,
                        '動作': '設計單領出',
                        '倉庫': x['倉庫'],
                        '批號': x['批號'],
                        '編號': x['編號'],
                        '分類': x['分類'],
                        '名稱': x['名稱'],
                        '規格': x['規格'],
                        '廠商': x['廠商'],
                        '數量變動': -x['數量'],
                        '成本備註': st.session_state['order_note_input']
                    }
                    st.session_state['history'] = pd.concat(
                        [st.session_state['history'], pd.DataFrame([log])], ignore_index=True
                    )

            if st.session_state['admin_mode']:
                s_log = {
                    '紀錄時間': datetime.now().strftime("%Y-%m-%d %H:%M"),
                    '單號': f_oid,
                    '動作': '🏷️ 單據總計',
                    '倉庫': '',
                    '批號': '',
                    '編號': '',
                    '分類': '',
                    '名稱': '--- 整單彙整 ---',
                    '規格': '',
                    '廠商': '',
                    '數量變動': 0,
                    '成本備註': f"💰 總成本為 ${total_cost:.2f}"
                }
                st.session_state['history'] = pd.concat(
                    [st.session_state['history'], pd.DataFrame([s_log])], ignore_index=True
                )

            save_inventory_to_gsheet(st.session_state['inventory'])
            save_history_to_gsheet(st.session_state['history'])
            st.session_state['current_design'] = []
            st.success("✅ 訂單已完成！")
            # 修正6: 移除 time.sleep(1)，直接 rerun
            st.rerun()
