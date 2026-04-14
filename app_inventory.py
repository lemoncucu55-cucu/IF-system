import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import date, datetime
import time

# ==========================================
# § 1 核心常數與雲端設定
# ==========================================
SHEET_ID = "1gf-pn034w0oZx8jWDUJvmIyHX_O7eHbiBb9diVSBX0Q"
KEY_FILE = "google_key.json"

COLUMNS = [
    '編號', '批號', '倉庫', '分類', '名稱', '寬度mm', '長度mm', '形狀', '五行',
    '進貨數量(顆)', '進貨日期', '進貨廠商', '庫存(顆)', '成本單價'
]

HISTORY_COLUMNS = [
    '紀錄時間', '單號', '動作', '倉庫', '批號', '編號', '分類', '名稱',
    '規格', '廠商', '數量變動', '成本備註'
]

# ==========================================
# § 2 雲端試算表連線功能
# ==========================================
@st.cache_resource
def get_gs_client():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    try:
        if "gcp_service_account" in st.secrets:
            creds = ServiceAccountCredentials.from_json_keyfile_dict(dict(st.secrets["gcp_service_account"]), scope)
        else:
            creds = ServiceAccountCredentials.from_json_keyfile_name(KEY_FILE, scope)
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"❌ Google 授權失敗：{e}")
        st.stop()

def load_inventory_from_gs():
    try:
        client = get_gs_client()
        ws = client.open_by_key(SHEET_ID).sheet1
        values = ws.get_all_values()
        if not values or len(values) < 2:
            return pd.DataFrame(columns=COLUMNS)
        headers = [str(h).strip().replace("\ufeff", "") for h in values[0]]
        final_headers = []
        for i, h in enumerate(headers):
            if not h: final_headers.append(f"未命名_{i}")
            elif h in final_headers: final_headers.append(f"{h}_{i}")
            else: final_headers.append(h)
        df = pd.DataFrame(values[1:], columns=final_headers)
        mask = df.astype(str).apply(lambda x: x.str.strip() != "").any(axis=1)
        df = df[mask]
        for col in COLUMNS:
            if col not in df.columns:
                df[col] = ""
        return df[COLUMNS].copy()
    except Exception as e:
        st.error(f"讀取庫存失敗: {e}")
        return pd.DataFrame(columns=COLUMNS)

def load_history_from_gs():
    try:
        client = get_gs_client()
        wb = client.open_by_key(SHEET_ID)
        try:
            ws = wb.worksheet("History")
        except gspread.exceptions.WorksheetNotFound:
            return pd.DataFrame(columns=HISTORY_COLUMNS)
        values = ws.get_all_values()
        if not values or len(values) < 2:
            return pd.DataFrame(columns=HISTORY_COLUMNS)
        headers = [str(h).strip().replace("\ufeff", "") for h in values[0]]
        final_headers = []
        for i, h in enumerate(headers):
            if not h: final_headers.append(f"未命名_{i}")
            elif h in final_headers: final_headers.append(f"{h}_{i}")
            else: final_headers.append(h)
        df = pd.DataFrame(values[1:], columns=final_headers)
        mask = df.astype(str).apply(lambda x: x.str.strip() != "").any(axis=1)
        df = df[mask]
        return df if not df.empty else pd.DataFrame(columns=HISTORY_COLUMNS)
    except Exception as e:
        st.error(f"讀取歷史失敗: {e}")
        return pd.DataFrame(columns=HISTORY_COLUMNS)

def save_inventory_to_gs(df):
    try:
        client = get_gs_client()
        ws = client.open_by_key(SHEET_ID).sheet1
        df_to_save = df.fillna("").astype(str)
        values = [df_to_save.columns.tolist()] + df_to_save.values.tolist()
        ws.clear()
        ws.update(range_name='A1', values=values)
    except Exception as e:
        st.error(f"儲存庫存失敗: {e}")

def append_history_batch(log_entries):
    if not log_entries:
        return
    try:
        client = get_gs_client()
        wb = client.open_by_key(SHEET_ID)
        try:
            ws = wb.worksheet("History")
            existing_values = ws.get_all_values()
            if existing_values:
                headers = [str(h).strip().replace("\ufeff", "") for h in existing_values[0]]
                df_hist = pd.DataFrame(existing_values[1:], columns=headers) if len(existing_values) > 1 else pd.DataFrame(columns=headers)
            else:
                df_hist = pd.DataFrame(columns=HISTORY_COLUMNS)
        except gspread.exceptions.WorksheetNotFound:
            ws = wb.add_worksheet(title="History", rows="1000", cols="20")
            df_hist = pd.DataFrame(columns=HISTORY_COLUMNS)
        new_df = pd.DataFrame(log_entries)
        df_hist = pd.concat([df_hist, new_df], ignore_index=True)
        for col in HISTORY_COLUMNS:
            if col not in df_hist.columns:
                df_hist[col] = ""
        df_hist = df_hist[HISTORY_COLUMNS]
        df_to_save = df_hist.fillna("").astype(str)
        values = [df_to_save.columns.tolist()] + df_to_save.values.tolist()
        ws.clear()
        ws.update(range_name='A1', values=values)
    except Exception as e:
        st.error(f"❌ 寫入歷史紀錄失敗: {e}")

# ==========================================
# § 3 業務邏輯工具
# ==========================================
def format_size(row):
    try:
        w = float(row.get('寬度mm', 0))
        l = float(row.get('長度mm', 0))
        return f"{w}x{l}mm" if l > 0 else f"{w}mm"
    except:
        return "0mm"

def create_item_label(row):
    sz = format_size(row)
    stock = int(float(row.get('庫存(顆)', 0)))
    elem = f"({row.get('五行', '-')}) " if row.get('五行') else ""
    shape = f" ({row.get('形狀', '')})" if row.get('形狀') else ""
    return f"[{row.get('倉庫','-')}] {elem}{row.get('名稱','-')} {sz}{shape} 【{row.get('批號','-')}】 | 存:{stock}"

# ==========================================
# § 4 系統初始化
# ==========================================
st.set_page_config(page_title="IF Crystal 進出庫系統", layout="wide", page_icon="💎")

if "inventory" not in st.session_state:
    st.session_state["inventory"] = load_inventory_from_gs()
if "current_design" not in st.session_state:
    st.session_state["current_design"] = []

st.title("💎 IF Crystal 進出庫系統")

with st.sidebar:
    st.title("💎 IF Crystal")
    st.caption("進出庫系統 — 所有人皆可使用")
    page = st.radio("功能導覽", ["📦 庫存總覽", "🧮 設計領料 (出庫)", "📥 歸還入庫", "📜 進出紀錄"])

    if st.button("🔄 刷新庫存資料"):
        get_gs_client.clear()
        st.session_state["inventory"] = load_inventory_from_gs()
        st.rerun()

inv = st.session_state["inventory"]

# ==========================================
# § 5 庫存總覽
# ==========================================
if page == "📦 庫存總覽":
    st.header("📦 目前庫存總覽")

    if not inv.empty:
        # 篩選工具
        c_filter1, c_filter2, c_filter3 = st.columns(3)
        wh_list = ["全部"] + sorted(inv["倉庫"].unique().tolist())
        sel_wh = c_filter1.selectbox("篩選倉庫", wh_list)
        cat_list = ["全部"] + sorted([v for v in inv["分類"].unique().tolist() if v])
        sel_cat = c_filter2.selectbox("篩選分類", cat_list)
        search_text = c_filter3.text_input("搜尋名稱")

        display_df = inv.copy()
        if sel_wh != "全部":
            display_df = display_df[display_df["倉庫"] == sel_wh]
        if sel_cat != "全部":
            display_df = display_df[display_df["分類"] == sel_cat]
        if search_text:
            display_df = display_df[display_df["名稱"].str.contains(search_text, case=False, na=False)]

        # 不顯示成本單價（非主管）
        show_cols = [c for c in COLUMNS if c != "成本單價"]
        st.dataframe(display_df[show_cols], use_container_width=True)

        st.caption(f"共 {len(display_df)} 項商品")
    else:
        st.info("目前沒有庫存資料，請等主管在進貨系統建檔。")

# ==========================================
# § 6 設計領料 (出庫)
# ==========================================
elif page == "🧮 設計領料 (出庫)":
    st.header("🧮 設計領料 — 出庫")

    col_info1, col_info2, col_info3 = st.columns([1, 1, 2])
    order_id = col_info1.text_input("設計單號", f"DES-{date.today().strftime('%m%d')}")
    operator = col_info2.selectbox("領料人", ["Imeng", "千畇"])
    order_note = col_info3.text_input("備註 (用途/客戶)")

    # 待領清單
    if st.session_state["current_design"]:
        st.subheader("🛒 待領清單明細")
        with st.container(border=True):
            for i, item in enumerate(st.session_state["current_design"]):
                c_text, c_del = st.columns([6, 1])
                shape_text = f" ({item.get('形狀', '')})" if item.get('形狀') else ""
                c_text.markdown(f"🔸 **[{item['五行']}] {item['名稱']}** ({item['規格']}){shape_text} x **{item['數量']}** | 批號:{item['批號']}")
                if c_del.button("🗑️", key=f"del_design_{i}"):
                    st.session_state["current_design"].pop(i)
                    st.rerun()

            st.divider()
            if st.button("🚀 確認領出 (扣除庫存)", type="primary", use_container_width=True):
                log_entries = []
                for it in st.session_state["current_design"]:
                    idx = it["idx"]
                    orig_row = st.session_state["inventory"].loc[idx]
                    new_stock = int(float(st.session_state["inventory"].loc[idx, "庫存(顆)"])) - int(it["數量"])
                    st.session_state["inventory"].loc[idx, "庫存(顆)"] = str(new_stock)

                    log_entries.append({
                        "紀錄時間": datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "單號": order_id,
                        "動作": "設計領料(出庫)",
                        "倉庫": orig_row.get("倉庫", ""),
                        "批號": it.get("批號", ""),
                        "編號": orig_row.get("編號", ""),
                        "分類": orig_row.get("分類", ""),
                        "名稱": it.get("名稱", ""),
                        "規格": it.get("規格", ""),
                        "廠商": f"領料人:{operator}" if operator else "",
                        "數量變動": str(-it["數量"]),
                        "成本備註": order_note
                    })

                append_history_batch(log_entries)
                save_inventory_to_gs(st.session_state["inventory"])
                st.session_state["current_design"] = []
                st.success("✅ 領料完成，庫存已扣除！")
                time.sleep(1.5)
                st.rerun()
    else:
        st.info("💡 目前待領清單是空的，請從下方選擇材料加入。")

    st.divider()
    st.subheader("🔍 選擇材料加入")
    if not inv.empty:
        inv_d = inv.copy()
        inv_d["dp"] = inv_d.apply(lambda r: create_item_label(r), axis=1)
        sel_d = st.selectbox("搜尋庫存品名/批號", inv_d["dp"].tolist(), key="design_search")
        target_idx_d = inv_d[inv_d["dp"] == sel_d].index[0]
        target_row_d = inv_d.loc[target_idx_d]
        col_qty, col_btn = st.columns([1, 1])
        pick_q = col_qty.number_input("加入數量", 1, max_value=max(1, int(float(target_row_d.get("庫存(顆)", 1)))), key="pick_qty_box")
        if col_btn.button("➕ 加入清單", use_container_width=True):
            st.session_state["current_design"].append({
                "idx": target_idx_d,
                "名稱": target_row_d["名稱"],
                "五行": target_row_d.get("五行", ""),
                "形狀": target_row_d.get("形狀", ""),
                "規格": format_size(target_row_d),
                "數量": pick_q,
                "批號": target_row_d.get("批號", "")
            })
            st.toast(f"已加入: {target_row_d['名稱']}")
            st.rerun()

# ==========================================
# § 7 歸還入庫
# ==========================================
elif page == "📥 歸還入庫":
    st.header("📥 歸還入庫")
    st.caption("將之前領出的材料歸還回庫存")

    if inv.empty:
        st.warning("目前沒有庫存品項。")
    else:
        inv_r = inv.copy()
        inv_r["dp"] = inv_r.apply(lambda r: create_item_label(r), axis=1)
        sel_r = st.selectbox("選擇要歸還的商品", inv_r["dp"].tolist())
        target_idx_r = inv_r[inv_r["dp"] == sel_r].index[0]
        target_row_r = inv.loc[target_idx_r]

        with st.form("return_form"):
            st.write(f"📍 **歸還商品：** {target_row_r['名稱']} ({format_size(target_row_r)})")
            st.write(f"📦 **現有庫存：** {target_row_r['庫存(顆)']} 顆")

            c1, c2, c3 = st.columns(3)
            return_qty = c1.number_input("歸還數量", min_value=1, value=1)
            return_operator = c2.selectbox("歸還人", ["Imeng", "千畇"])
            return_note = c3.text_input("備註")

            if st.form_submit_button("✅ 確認歸還入庫", use_container_width=True):
                new_stock = int(float(st.session_state["inventory"].loc[target_idx_r, "庫存(顆)"])) + return_qty
                st.session_state["inventory"].loc[target_idx_r, "庫存(顆)"] = str(new_stock)

                log_entry = {
                    "紀錄時間": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "單號": f"RET-{date.today().strftime('%m%d')}",
                    "動作": "歸還入庫",
                    "倉庫": target_row_r["倉庫"],
                    "批號": target_row_r["批號"],
                    "編號": target_row_r["編號"],
                    "分類": target_row_r["分類"],
                    "名稱": target_row_r["名稱"],
                    "規格": format_size(target_row_r),
                    "廠商": f"歸還人:{return_operator}" if return_operator else "",
                    "數量變動": str(return_qty),
                    "成本備註": return_note
                }
                append_history_batch([log_entry])
                save_inventory_to_gs(st.session_state["inventory"])
                st.success(f"✅ {target_row_r['名稱']} 歸還 {return_qty} 顆成功！目前庫存：{new_stock} 顆")
                st.rerun()

# ==========================================
# § 8 進出紀錄
# ==========================================
elif page == "📜 進出紀錄":
    st.header("📜 進出庫紀錄")

    hist_df = load_history_from_gs()

    if hist_df.empty:
        st.info("目前沒有任何紀錄。")
    else:
        # 篩選器
        if "動作" in hist_df.columns:
            action_list = ["全部"] + sorted(hist_df["動作"].unique().tolist())
            sel_action = st.selectbox("篩選動作類型", action_list)

            display_hist = hist_df.copy()
            if sel_action != "全部":
                display_hist = display_hist[display_hist["動作"] == sel_action]

            if display_hist.empty:
                st.info("篩選後沒有紀錄。")
            else:
                st.dataframe(display_hist.iloc[::-1], use_container_width=True)
                st.caption(f"共 {len(display_hist)} 筆紀錄")
        else:
            st.dataframe(hist_df.iloc[::-1], use_container_width=True)
