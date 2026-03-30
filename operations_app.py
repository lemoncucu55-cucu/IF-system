import streamlit as st
import pandas as pd
from datetime import date, datetime
import uuid
import gspread
# ✅ 優化1: 棄用 oauth2client，改用官方維護的 google-auth
from google.oauth2.service_account import Credentials

# ==========================================
# 1. 核心設定
# ==========================================
SHEET_ID = "1gf-pn034w0oZx8jWDUJvmIyHX_O7eHbiBb9diVSBX0Q"
KEY_FILE = "google_key.json"
COLUMNS = ['編號', '批號', '倉庫', '分類', '名稱', '寬度mm', '長度mm', '形狀', '五行',
           '進貨數量(顆)', '進貨日期', '進貨廠商', '庫存(顆)', '成本單價']
HISTORY_COLUMNS = ['紀錄時間', '單號', '動作', '倉庫', '批號', '編號', '分類', '名稱',
                   '規格', '廠商', '數量變動', '成本備註']
DEFAULT_WAREHOUSES = ["Imeng", "千畇"]
DEFAULT_SUPPLIERS  = ["小聰頭", "廠商A", "廠商B", "自用", "蝦皮", "淘寶",
                       "TB-東吳天然石坊", "永安", "Rich"]
DEFAULT_SHAPES     = ["圓珠", "切角", "鑽切", "圓筒", "方體", "長柱", "不規則", "造型", "原礦"]
DEFAULT_ELEMENTS   = ["金", "木", "水", "火", "土", "綜合", "銀", "銅", "14K包金"]

# ✅ 優化6: 魔術字串提取為常數，避免多處分散、難以維護
MANUAL_INPUT_OPTION = "➕ 手動輸入"

# ==========================================
# 2. 核心功能函式
# ==========================================

@st.cache_resource
def get_google_sheet_client():
    """
    ✅ 優化1: 改用 google-auth (Credentials)，oauth2client 已停止維護。
    使用 @st.cache_resource 確保連線物件全 session 共用，不重複建立。
    """
    scope = [
        'https://spreadsheets.google.com/feeds',
        'https://www.googleapis.com/auth/drive'
    ]
    if "gcp_service_account" in st.secrets:
        creds = Credentials.from_service_account_info(
            dict(st.secrets["gcp_service_account"]), scopes=scope
        )
    else:
        creds = Credentials.from_service_account_file(KEY_FILE, scopes=scope)
    return gspread.authorize(creds)


@st.cache_data(ttl=60)
def load_inventory_from_gsheet():
    """從 Google Sheet 讀取庫存，每 60 秒快取一次。"""
    try:
        client = get_google_sheet_client()
        sheet  = client.open_by_key(SHEET_ID).sheet1
        data   = sheet.get_all_records()
        if not data:
            return pd.DataFrame(columns=COLUMNS)
        df = pd.DataFrame(data)
        df.columns = df.columns.astype(str).str.strip().str.replace('\ufeff', '', regex=False)
        for col in COLUMNS:
            if col not in df.columns:
                df[col] = ""
        df = df[COLUMNS].copy().fillna("")
        for col in ['寬度mm', '長度mm', '進貨數量(顆)', '庫存(顆)', '成本單價']:
            df[col] = pd.to_numeric(
                df[col].astype(str).str.replace(',', '', regex=False).str.strip(),
                errors='coerce'
            ).fillna(0)
        return df
    except Exception as e:
        st.error(f"❌ 無法讀取庫存表: {e}")
        return pd.DataFrame(columns=COLUMNS)


@st.cache_data(ttl=60)
def load_history_from_gsheet():
    """從 Google Sheet 讀取歷史紀錄，每 60 秒快取一次。"""
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
    """
    全量覆寫庫存表（庫存會被修改，需全量更新）。
    ✅ 優化2: 移除 st.stop()，改為顯示錯誤後 return False，不中止整頁渲染。
    """
    try:
        client = get_google_sheet_client()
        sheet  = client.open_by_key(SHEET_ID).sheet1
        sheet.clear()
        update_data = [df.columns.values.tolist()] + df.astype(str).values.tolist()
        sheet.update(range_name='A1', values=update_data)
        load_inventory_from_gsheet.clear()
        st.toast("☁️ 庫存同步成功")
        return True
    except Exception as e:
        st.error(f"❌ 庫存存檔失敗: {e}")
        return False


def append_history_to_gsheet(new_rows_df):
    """
    ✅ 優化1 (歷史紀錄): 改用 append_rows 取代全量 clear+update。
    - 避免 clear() 後崩潰導致資料遺失的風險。
    - 隨紀錄增多，效能大幅優於全量覆寫。
    """
    try:
        client = get_google_sheet_client()
        sheet  = client.open_by_key(SHEET_ID).worksheet("History")
        rows   = new_rows_df.astype(str).values.tolist()
        sheet.append_rows(rows, value_input_option='USER_ENTERED')
        load_history_from_gsheet.clear()
    except Exception as e:
        st.error(f"❌ 歷史紀錄存檔失敗: {e}")


def save_history_to_gsheet(df):
    """
    全量覆寫歷史表（僅在批次標籤修正等需要全量更新時使用）。
    一般新增紀錄請改用 append_history_to_gsheet()。
    """
    try:
        client = get_google_sheet_client()
        sheet  = client.open_by_key(SHEET_ID).worksheet("History")
        sheet.clear()
        h_data = [df.columns.tolist()] + df.astype(str).values.tolist()
        sheet.update(range_name='A1', values=h_data)
        load_history_from_gsheet.clear()
    except Exception as e:
        st.error(f"❌ 歷史紀錄存檔失敗: {e}")


def get_dynamic_options(col_name, default_list):
    """從庫存動態取得選項，合併預設清單。"""
    options = set(default_list)
    if 'inventory' in st.session_state and not st.session_state['inventory'].empty:
        for v in st.session_state['inventory'][col_name].astype(str).unique():
            if v.strip() and v.lower() != 'nan' and v not in ('0', '0.0'):
                options.add(v.strip())
    return [MANUAL_INPUT_OPTION] + sorted(options)


def format_size(row):
    """將寬/長度格式化為顯示字串。"""
    try:
        w = float(row.get('寬度mm', 0))
        l = float(row.get('長度mm', 0))
        if l > 0:
            return f"{w}x{l}mm"
        if w > 0:
            return f"{w}mm"
        return "0mm"
    except Exception:
        return "0mm"


def make_inventory_labels_vectorized(df: pd.DataFrame, admin_mode: bool) -> pd.Series:
    """
    ✅ 優化4: 向量化標籤生成，取代逐行 apply()，大幅提升大量品項時的效能。
    """
    w = pd.to_numeric(df['寬度mm'], errors='coerce').fillna(0)
    l = pd.to_numeric(df['長度mm'], errors='coerce').fillna(0)

    size = w.astype(str) + "x" + l.astype(str) + "mm"
    size = size.where(l > 0, w.astype(str) + "mm")
    size = size.where(w > 0, "0mm")

    elem_display = df['五行'].astype(str).str.strip().apply(
        lambda e: f"({e}) " if e and e.lower() != 'nan' else ""
    )
    stock_int = pd.to_numeric(df['庫存(顆)'], errors='coerce').fillna(0).astype(int)

    if admin_mode:
        cost = pd.to_numeric(df['成本單價'], errors='coerce').fillna(0)
        cost_str = cost.apply(lambda c: f" 💰${c:.2f}")
    else:
        cost_str = pd.Series([""] * len(df), index=df.index)

    return (
        "[" + df['倉庫'].astype(str) + "] "
        + elem_display
        + df['名稱'].astype(str) + " "
        + size + " ("
        + df['形狀'].astype(str) + ")"
        + cost_str
        + " 【" + df['批號'].astype(str) + "】"
        + " | 存:" + stock_int.astype(str)
    )


# ==========================================
# 3. UI 介面
# ==========================================
st.set_page_config(page_title="IF Crystal 全雲端系統", layout="wide")

# --- Session State 初始化 ---
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

st.title("💎 IF Crystal 全雲端系統 (v9.14-優化版)")

with st.sidebar:
    st.header("🔑 權限控制")
    pwd = st.text_input("主管密碼", type="password")
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
    # ✅ 優化7: 改用語意清晰的 tab 變數名稱，避免 tab4/tab3 排序混淆
    tab_restock, tab_create, tab_use, tab_edit = st.tabs(
        ["🔄 補貨", "✨ 建檔", "📤 領用", "🛠️ 修改"]
    )

    # --- Tab: 補貨 ---
    with tab_restock:
        if not st.session_state['inventory'].empty:
            inv_sorted = st.session_state['inventory'].copy()
            inv_sorted['label'] = make_inventory_labels_vectorized(
                inv_sorted, st.session_state['admin_mode']
            )
            target = st.selectbox("選擇商品", inv_sorted['label'].tolist(), key="restock_select")
            idx    = inv_sorted[inv_sorted['label'] == target].index[0]
            row    = st.session_state['inventory'].loc[idx]

            with st.form("restock_form"):
                old_cost = float(row.get('成本單價', 0))
                st.info(f"品名：{row['名稱']} | 目前單價成本：${old_cost:.2f}")
                c1, c2, c3 = st.columns(3)
                qty_in       = c1.number_input("進貨數量", 1, value=1)
                total_p      = c2.number_input("💰 本次進貨總價", min_value=0.0, step=1.0)
                r_type       = c3.radio("方式", ["➕ 合併", "📦 新批號"])
                new_batch_name = (
                    st.text_input("批號名稱", f"{date.today().strftime('%Y%m%d')}-A")
                    if r_type == "📦 新批號" else row['批號']
                )

                if st.form_submit_button("確認進貨"):
                    final_u_cost = round(total_p / qty_in, 2) if qty_in > 0 else 0

                    if r_type == "➕ 合併":
                        st.session_state['inventory'].at[idx, '庫存(顆)']   += qty_in
                        st.session_state['inventory'].at[idx, '成本單價']    = final_u_cost
                        log_act = "補貨(合併)"
                    else:
                        new_r = row.copy()
                        new_r['庫存(顆)']     = int(qty_in)
                        new_r['進貨數量(顆)'] = int(qty_in)
                        new_r['進貨日期']     = str(date.today())
                        new_r['批號']         = new_batch_name
                        new_r['成本單價']     = final_u_cost
                        st.session_state['inventory'] = pd.concat(
                            [st.session_state['inventory'], pd.DataFrame([new_r])],
                            ignore_index=True
                        )
                        log_act = "補貨(新批)"

                    save_inventory_to_gsheet(st.session_state['inventory'])

                    # ✅ 優化1: 改用 append_history_to_gsheet，不再全量覆寫歷史表
                    log_row = pd.DataFrame([{
                        '紀錄時間': datetime.now().strftime("%Y-%m-%d %H:%M"),
                        '單號':     'IN',
                        '動作':     log_act,
                        '倉庫':     row['倉庫'],
                        '批號':     new_batch_name,
                        '編號':     row['編號'],
                        '分類':     row['分類'],
                        '名稱':     row['名稱'],
                        '規格':     format_size(row),
                        '廠商':     row['進貨廠商'],
                        '數量變動': qty_in,
                        '成本備註': f"進貨價${total_p:.2f}"
                    }])
                    st.session_state['history'] = pd.concat(
                        [st.session_state['history'], log_row], ignore_index=True
                    )
                    append_history_to_gsheet(log_row)
                    st.success("✅ 補貨完成！")
                    st.rerun()
        else:
            st.info("目前庫存為空，請先至「建檔」頁籤新增商品。")

    # --- Tab: 建檔 ---
    with tab_create:
        with st.form("new_item_creation"):
            c1, c2, c3 = st.columns(3)
            wh    = c1.selectbox("倉庫", DEFAULT_WAREHOUSES)
            n_opts = get_dynamic_options('名稱', ["水晶"])
            n_sel  = c2.selectbox("名稱選單", n_opts, key="create_n_sel")
            n_custom = c2.text_input("新名稱(選購手動時填寫)", key="create_n_in")
            cat   = c3.selectbox("分類", ["天然石", "配件", "耗材"])

            c4, c5, c6 = st.columns(3)
            sh_opts   = get_dynamic_options('形狀', DEFAULT_SHAPES)
            sh_sel    = c4.selectbox("規格選單", sh_opts, key="create_sh_sel")
            sh_custom = c4.text_input("新規格", key="create_sh_in")
            el_opts   = get_dynamic_options('五行', DEFAULT_ELEMENTS)
            el_sel    = c5.selectbox("顏色選單", el_opts, key="create_el_sel")
            el_custom = c5.text_input("新顏色", key="create_el_in")
            su_opts   = get_dynamic_options('進貨廠商', DEFAULT_SUPPLIERS)
            su_sel    = c6.selectbox("廠商選單", su_opts, key="create_su_sel")
            su_custom = c6.text_input("新廠商", key="create_su_in")

            c7, c8, c9, c10 = st.columns(4)
            w_mm    = c7.number_input("寬度", 0.0)
            l_mm    = c8.number_input("長度", 0.0)
            q_in    = c9.number_input("初始數量", 1)
            cost_in = c10.number_input("總成本", 0.0)

            if st.form_submit_button("✅ 建立商品"):
                final_n  = n_custom  if n_sel  == MANUAL_INPUT_OPTION else n_sel
                final_su = su_custom if su_sel == MANUAL_INPUT_OPTION else su_sel

                has_error = False
                if not final_n:
                    st.error("❌ 名稱為必填")
                    has_error = True
                if not final_su:
                    st.error("❌ 廠商為必填")
                    has_error = True

                if not has_error:
                    new_id = f"ST{uuid.uuid4().hex[:8].upper()}"
                    new_r  = {
                        '編號':       new_id,
                        '批號':       '初始存貨',
                        '倉庫':       wh,
                        '分類':       cat,
                        '名稱':       final_n,
                        '形狀':       (sh_custom if sh_sel == MANUAL_INPUT_OPTION else sh_sel),
                        '五行':       (el_custom if el_sel == MANUAL_INPUT_OPTION else el_sel),
                        '進貨數量(顆)': int(q_in),
                        '進貨廠商':   final_su,
                        '進貨日期':   str(date.today()),
                        '庫存(顆)':   int(q_in),
                        '成本單價':   round(cost_in / q_in if q_in > 0 else 0, 2),
                        '寬度mm':     w_mm,
                        '長度mm':     l_mm
                    }
                    st.session_state['inventory'] = pd.concat(
                        [st.session_state['inventory'], pd.DataFrame([new_r])],
                        ignore_index=True
                    )
                    save_inventory_to_gsheet(st.session_state['inventory'])
                    st.success(f"✅ 商品「{final_n}」建立成功！")
                    st.rerun()

    # --- Tab: 領用 ---
    with tab_use:
        st.subheader("📤 單筆快速領用")
        if not st.session_state['inventory'].empty:
            inv_q = st.session_state['inventory'].copy()
            inv_q['label'] = make_inventory_labels_vectorized(
                inv_q, st.session_state['admin_mode']
            )
            sel_q  = st.selectbox("選擇材料", inv_q['label'].tolist(), key="quick_use_sel")
            idx_q  = inv_q[inv_q['label'] == sel_q].index[0]
            row_q  = st.session_state['inventory'].loc[idx_q]

            # ✅ 優化3: 庫存為 0 時提示並禁止領用，避免 max_value 邏輯漏洞
            stock_q = int(row_q['庫存(顆)'])
            if stock_q <= 0:
                st.warning("⚠️ 此品項庫存為 0，無法領用。")
            else:
                with st.form("quick_use_form"):
                    c1, c2  = st.columns(2)
                    qty_q   = c1.number_input("領用數量", min_value=1, max_value=stock_q, value=1)
                    note_q  = c2.text_input("備註")

                    if st.form_submit_button("✅ 確認領用"):
                        st.session_state['inventory'].at[idx_q, '庫存(顆)'] -= qty_q
                        log_row = pd.DataFrame([{
                            '紀錄時間': datetime.now().strftime("%Y-%m-%d %H:%M"),
                            '單號':     f"QU-{date.today().strftime('%Y%m%d')}",
                            '動作':     '快速領用',
                            '倉庫':     row_q['倉庫'],
                            '批號':     row_q['批號'],
                            '編號':     row_q['編號'],
                            '分類':     row_q['分類'],
                            '名稱':     row_q['名稱'],
                            '規格':     format_size(row_q),
                            '廠商':     row_q['進貨廠商'],
                            '數量變動': -qty_q,
                            '成本備註': note_q
                        }])
                        st.session_state['history'] = pd.concat(
                            [st.session_state['history'], log_row], ignore_index=True
                        )
                        save_inventory_to_gsheet(st.session_state['inventory'])
                        append_history_to_gsheet(log_row)
                        st.success(f"✅ 已領用 {qty_q} 顆「{row_q['名稱']}」")
                        st.rerun()
        else:
            st.info("目前庫存為空。")

    # --- Tab: 修改 ---
    with tab_edit:
        if not st.session_state['inventory'].empty:
            inv_e = st.session_state['inventory'].copy()
            inv_e['label'] = make_inventory_labels_vectorized(
                inv_e, st.session_state['admin_mode']
            )
            target_e = st.selectbox("1. 選擇修改項目", inv_e['label'].tolist(), key="edit_main_sel")
            idx_e    = inv_e[inv_e['label'] == target_e].index[0]
            e_row    = st.session_state['inventory'].loc[idx_e]
            st.markdown("---")

            c1, c2, c3 = st.columns(3)
            me_opts  = get_dynamic_options('名稱', ["水晶"])
            me_sel   = c1.selectbox(
                "名稱選單", me_opts,
                index=me_opts.index(e_row['名稱']) if e_row['名稱'] in me_opts else 0,
                key="edit_n_sel"
            )
            me_final = st.text_input("📝 請輸入新名稱", key="edit_n_manual") \
                if me_sel == MANUAL_INPUT_OPTION else me_sel

            sh_m_opts = get_dynamic_options('形狀', DEFAULT_SHAPES)
            sh_m_sel  = c2.selectbox(
                "規格選單", sh_m_opts,
                index=sh_m_opts.index(e_row['形狀']) if e_row['形狀'] in sh_m_opts else 0,
                key="edit_sh_sel"
            )
            sh_final = st.text_input("📝 請輸入新規格", key="edit_sh_manual") \
                if sh_m_sel == MANUAL_INPUT_OPTION else sh_m_sel

            el_m_opts = get_dynamic_options('五行', DEFAULT_ELEMENTS)
            el_m_sel  = c3.selectbox(
                "顏色選單", el_m_opts,
                index=el_m_opts.index(e_row['五行']) if e_row['五行'] in el_m_opts else 0,
                key="edit_el_sel"
            )
            el_final = st.text_input("📝 請輸入新顏色", key="edit_el_manual") \
                if el_m_sel == MANUAL_INPUT_OPTION else el_m_sel

            with st.form("edit_submit_stable"):
                ca, cb, cc, cd = st.columns(4)
                nw = ca.number_input("寬度", value=float(e_row['寬度mm']))
                nl = cb.number_input("長度", value=float(e_row['長度mm']))
                nq = cc.number_input("庫存", value=int(e_row['庫存(顆)']))
                nc = cd.number_input("成本", value=float(e_row['成本單價']))

                if st.form_submit_button("💾 儲存修改"):
                    st.session_state['inventory'].at[idx_e, '名稱']    = me_final
                    st.session_state['inventory'].at[idx_e, '形狀']    = sh_final
                    st.session_state['inventory'].at[idx_e, '五行']    = el_final
                    st.session_state['inventory'].at[idx_e, '寬度mm']  = nw
                    st.session_state['inventory'].at[idx_e, '長度mm']  = nl
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
            c1, c2, c3  = st.columns(3)
            col_m      = c1.selectbox("欄位", ["五行", "形狀", "進貨廠商", "名稱"])
            col_vals   = sorted(st.session_state['inventory'][col_m].unique().tolist())
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
    st.session_state['order_id_input']   = ca.text_input("單號",   st.session_state['order_id_input'])
    st.session_state['order_note_input'] = cb.text_input("備註",   st.session_state['order_note_input'])

    if not st.session_state['inventory'].empty:
        inv_ds = st.session_state['inventory'].copy()
        inv_ds['label'] = make_inventory_labels_vectorized(
            inv_ds, st.session_state['admin_mode']
        )
        sel_ds = st.selectbox("材料選擇", inv_ds['label'].tolist())
        idx_ds = inv_ds[inv_ds['label'] == sel_ds].index[0]
        row_ds = st.session_state['inventory'].loc[idx_ds]

        # ✅ 優化3: 同樣對設計單的材料選擇加上庫存為 0 的防護
        stock_ds = int(row_ds['庫存(顆)'])
        if stock_ds <= 0:
            st.warning("⚠️ 此品項庫存為 0，無法加入清單。")
        else:
            qty_ds = st.number_input("數量", 1, max_value=stock_ds)
            if st.button("⬇️ 加入清單"):
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
            u_c = float(st.session_state['inventory'].loc[mask, '成本單價'].values[0]) \
                  if mask.any() else 0
            total_cost += u_c * item['數量']

            ct, del_b = st.columns([5, 1])
            ct.write(f"🔸 [{item['五行']}] {item['名稱']} ({item['規格']}) x{item['數量']}")
            if del_b.button("🗑️", key=f"ds_del_{i}"):
                st.session_state['current_design'].pop(i)
                st.rerun()

        if st.session_state['admin_mode']:
            st.metric("預估總成本", f"${total_cost:.2f}")

        if st.button("✅ 確認領出", type="primary", use_container_width=True):
            f_oid   = st.session_state['order_id_input']
            new_logs = []

            for x in st.session_state['current_design']:
                mask = (
                    (st.session_state['inventory']['編號'] == x['編號']) &
                    (st.session_state['inventory']['批號'] == x['批號'])
                )
                if mask.any():
                    t_idx = st.session_state['inventory'][mask].index[0]
                    st.session_state['inventory'].at[t_idx, '庫存(顆)'] -= x['數量']
                    new_logs.append({
                        '紀錄時間': datetime.now().strftime("%Y-%m-%d %H:%M"),
                        '單號':     f_oid,
                        '動作':     '設計單領出',
                        '倉庫':     x['倉庫'],
                        '批號':     x['批號'],
                        '編號':     x['編號'],
                        '分類':     x['分類'],
                        '名稱':     x['名稱'],
                        '規格':     x['規格'],
                        '廠商':     x['廠商'],
                        '數量變動': -x['數量'],
                        '成本備註': st.session_state['order_note_input']
                    })

            if st.session_state['admin_mode']:
                new_logs.append({
                    '紀錄時間': datetime.now().strftime("%Y-%m-%d %H:%M"),
                    '單號':     f_oid,
                    '動作':     '🏷️ 單據總計',
                    '倉庫':     '',
                    '批號':     '',
                    '編號':     '',
                    '分類':     '',
                    '名稱':     '--- 整單彙整 ---',
                    '規格':     '',
                    '廠商':     '',
                    '數量變動': 0,
                    '成本備註': f"💰 總成本為 ${total_cost:.2f}"
                })

            # ✅ 優化1: 一次性 append 所有紀錄，取代多次寫入
            if new_logs:
                log_df = pd.DataFrame(new_logs)
                st.session_state['history'] = pd.concat(
                    [st.session_state['history'], log_df], ignore_index=True
                )
                save_inventory_to_gsheet(st.session_state['inventory'])
                append_history_to_gsheet(log_df)

            st.session_state['current_design'] = []
            st.success("✅ 訂單已完成！")
            st.rerun()
