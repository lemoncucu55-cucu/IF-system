import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import date, datetime
import uuid
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

MANUAL = "➕ 手動輸入"

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
            error_df = pd.DataFrame([{"紀錄時間": "錯誤", "動作": "找不到 History 分頁"}])
            return error_df

        values = ws.get_all_values()
        if not values or len(values) < 2:
            empty_df = pd.DataFrame([{"紀錄時間": "系統提示", "動作": "History 分頁內目前沒有資料列"}])
            return empty_df

        headers = [str(h).strip().replace("\ufeff", "") for h in values[0]]
        final_headers = []
        for i, h in enumerate(headers):
            if not h: final_headers.append(f"未命名_{i}")
            elif h in final_headers: final_headers.append(f"{h}_{i}")
            else: final_headers.append(h)

        df = pd.DataFrame(values[1:], columns=final_headers)
        mask = df.astype(str).apply(lambda x: x.str.strip() != "").any(axis=1)
        df = df[mask]

        if df.empty:
            return pd.DataFrame([{"紀錄時間": "系統提示", "動作": "過濾後沒有有效資料"}])

        return df
    except Exception as e:
        error_df = pd.DataFrame([{"紀錄時間": "嚴重異常", "動作": str(e)}])
        return error_df

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
    if not log_entries: return
    try:
        client = get_gs_client()
        wb = client.open_by_key(SHEET_ID)
        try:
            ws = wb.worksheet("History")
            existing_values = ws.get_all_values()

            if existing_values:
                headers = [str(h).strip().replace("\ufeff", "") for h in existing_values[0]]
                if len(existing_values) > 1:
                    df_hist = pd.DataFrame(existing_values[1:], columns=headers)
                else:
                    df_hist = pd.DataFrame(columns=headers)
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

def create_item_label(row, is_admin=False):
    sz = format_size(row)
    stock = int(float(row.get('庫存(顆)', 0)))
    elem = f"({row.get('五行', '-')}) " if row.get('五行') else ""
    cost = f" 💰${float(row.get('成本單價', 0)):.2f}" if is_admin else ""
    shape = f" ({row.get('形狀', '')})" if row.get('形狀') else ""
    return f"[{row.get('倉庫','-')}] {elem}{row.get('名稱','-')} {sz}{shape} 【{row.get('批號','-')}】 | 存:{stock}{cost}"

def get_unique_options(col, defaults, df):
    existing = {str(v).strip() for v in df[col].unique() if str(v).strip() and str(v).lower() not in ("nan", "0")}
    return [MANUAL] + sorted(existing | set(defaults))

# ==========================================
# § 4 系統初始化
# ==========================================
st.set_page_config(page_title="IF Crystal 系統", layout="wide")

if "inventory" not in st.session_state:
    st.session_state["inventory"] = load_inventory_from_gs()
if "current_design" not in st.session_state:
    st.session_state["current_design"] = []

with st.sidebar:
    st.title("💎 管理控制台")
    pwd = st.text_input("主管模式密碼", type="password")
    st.session_state["admin_mode"] = (pwd == "admin123")
    page = st.radio("功能導覽", ["📦 庫存管理", "🧮 設計領料", "📜 歷史紀錄"])

    if st.button("🔄 強制刷新雲端資料"):
        get_gs_client.clear()
        st.session_state["inventory"] = load_inventory_from_gs()
        st.rerun()

# ==========================================
# § 5 庫存管理頁面
# ==========================================
if page == "📦 庫存管理":
    st.header("📦 庫存與進貨管理")
    t1, t2, t3 = st.tabs(["🔄 補貨進貨", "✨ 新品建檔", "🛠️ 資料修改"])
    inv = st.session_state["inventory"]

    with t1:
        if not inv.empty:
            df_label = inv.copy()
            df_label["display"] = df_label.apply(lambda r: create_item_label(r, st.session_state["admin_mode"]), axis=1)
            sel_target = st.selectbox("選擇要補貨的商品", df_label["display"].tolist(), key="tab1_sel")
            target_idx = df_label[df_label["display"] == sel_target].index[0]
            target_row = inv.loc[target_idx]

            with st.form("restock_form"):
                st.write(f"📍 **當前商品：** {target_row['名稱']} ({format_size(target_row)})")
                col_a, col_b, col_c = st.columns(3)
                add_qty = col_a.number_input("進貨數量", min_value=1, value=1)
                add_total_price = col_b.number_input("本次進貨總成本 ($)", min_value=0.0)
                sup_opts = get_unique_options("進貨廠商", [], inv)
                sup_sel = col_c.selectbox("進貨廠商", sup_opts, key="restock_sup")
                sup_man = col_c.text_input("手動輸入廠商", key="restock_sup_man")

                if st.form_submit_button("確認補貨"):
                    final_supplier = sup_man if sup_sel == MANUAL else sup_sel
                    new_cost = round(add_total_price / add_qty, 2) if add_qty > 0 else 0

                    new_stock = int(float(st.session_state["inventory"].loc[target_idx, "庫存(顆)"])) + add_qty
                    st.session_state["inventory"].loc[target_idx, "庫存(顆)"] = str(new_stock)
                    st.session_state["inventory"].loc[target_idx, "成本單價"] = str(new_cost)
                    st.session_state["inventory"].loc[target_idx, "進貨廠商"] = str(final_supplier)

                    log_entry = {
                        "紀錄時間": datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "單號": "IN",
                        "動作": "補貨進貨",
                        "倉庫": target_row["倉庫"],
                        "批號": target_row["批號"],
                        "編號": target_row["編號"],
                        "分類": target_row["分類"],
                        "名稱": target_row["名稱"],
                        "規格": format_size(target_row),
                        "廠商": final_supplier,
                        "數量變動": add_qty,
                        "成本備註": f"總價 ${add_total_price}"
                    }
                    append_history_batch([log_entry])
                    save_inventory_to_gs(st.session_state["inventory"])
                    st.success(f"✅ {target_row['名稱']} 補貨成功！")
                    st.rerun()

    with t2:
        with st.form("create_form"):
            st.write("✨ **建立全新庫存品項**")
            c1, c2, c3 = st.columns(3)
            new_wh = c1.selectbox("倉庫", ["Imeng", "千畇"])

            n_opts = get_unique_options("名稱", ["水晶"], inv)
            n_sel = c2.selectbox("名稱 (選單)", n_opts)
            n_man = c2.text_input("手動輸入名稱")

            el_opts = get_unique_options("五行", ["金", "木", "水", "火", "土"], inv)
            el_sel = c3.selectbox("五行/顏色 (選單)", el_opts)
            el_man = c3.text_input("手動輸入五行")

            c4, c5, c6 = st.columns(3)
            sh_opts = get_unique_options("形狀", ["圓珠", "切角", "鑽切", "圓筒", "方體", "長柱", "不規則", "造型", "原礦"], inv)
            sh_sel = c4.selectbox("形狀 (選單)", sh_opts)
            sh_man = c4.text_input("手動輸入形狀")

            c7, c8, c9 = st.columns(3)
            new_qty = c7.number_input("初始數量", min_value=1, value=1)
            new_cost = c8.number_input("單顆成本", min_value=0.0)
            new_wh_mm = c9.number_input("寬度 mm", min_value=0.0)

            sup_opts2 = get_unique_options("進貨廠商", [], inv)
            sup_sel2 = st.selectbox("進貨廠商", sup_opts2, key="new_sup")
            sup_man2 = st.text_input("手動輸入廠商", key="new_sup_man")

            if st.form_submit_button("✅ 提交建檔"):
                final_name = n_man if n_sel == MANUAL else n_sel
                final_elem = el_man if el_sel == MANUAL else el_sel
                final_shape = sh_man if sh_sel == MANUAL else sh_sel
                final_supplier = sup_man2 if sup_sel2 == MANUAL else sup_sel2

                new_data = {
                    "編號": f"ST{uuid.uuid4().hex[:6].upper()}",
                    "批號": "初始存貨",
                    "倉庫": str(new_wh),
                    "分類": "天然石",
                    "名稱": str(final_name),
                    "形狀": str(final_shape),
                    "五行": str(final_elem),
                    "寬度mm": str(new_wh_mm),
                    "長度mm": "0",
                    "進貨數量(顆)": str(new_qty),
                    "進貨日期": str(date.today()),
                    "進貨廠商": str(final_supplier),
                    "庫存(顆)": str(new_qty),
                    "成本單價": str(new_cost)
                }

                log_entry = {
                    "紀錄時間": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "單號": "NEW",
                    "動作": "新品建檔",
                    "倉庫": new_data["倉庫"],
                    "批號": new_data["批號"],
                    "編號": new_data["編號"],
                    "分類": new_data["分類"],
                    "名稱": new_data["名稱"],
                    "規格": format_size(new_data),
                    "廠商": new_data["進貨廠商"],
                    "數量變動": new_data["庫存(顆)"],
                    "成本備註": f"單價 ${new_cost}"
                }
                append_history_batch([log_entry])
                st.session_state["inventory"] = pd.concat([inv, pd.DataFrame([new_data])], ignore_index=True)
                save_inventory_to_gs(st.session_state["inventory"])
                st.success(f"已成功建立：{final_name}")
                st.rerun()

    with t3:
        if not inv.empty:
            df_label_e = inv.copy()
            df_label_e["display"] = df_label_e.apply(lambda r: create_item_label(r, True), axis=1)
            sel_e = st.selectbox("選擇要修改的商品", df_label_e["display"].tolist(), key="tab3_sel")
            idx_e = df_label_e[df_label_e["display"] == sel_e].index[0]
            row_e = inv.loc[idx_e]

            with st.form("edit_form_final"):
                ca, cb, cc = st.columns(3)
                edit_name = ca.text_input("修改名稱", row_e["名稱"])
                edit_elem = cb.text_input("修改五行", row_e.get("五行", ""))
                edit_shape = cc.text_input("修改形狀", row_e.get("形狀", ""))

                edit_supplier = st.text_input("修改廠商", row_e.get("進貨廠商", ""))

                c1, c2 = st.columns(2)
                edit_stock = c1.number_input("修正庫存數量", value=int(float(row_e["庫存(顆)"])))
                edit_cost = c2.number_input("修正成本單價", value=float(row_e.get("成本單價", 0)))

                if st.form_submit_button("💾 儲存所有修改"):
                    log_entry = {
                        "紀錄時間": datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "單號": "EDIT",
                        "動作": "資料修改",
                        "倉庫": row_e["倉庫"],
                        "批號": row_e["批號"],
                        "編號": row_e["編號"],
                        "分類": row_e["分類"],
                        "名稱": edit_name,
                        "規格": format_size(row_e),
                        "廠商": edit_supplier,
                        "數量變動": edit_stock - int(float(row_e["庫存(顆)"])),
                        "成本備註": f"原庫存 {row_e['庫存(顆)']} -> {edit_stock}"
                    }
                    append_history_batch([log_entry])

                    st.session_state["inventory"].loc[idx_e, "名稱"] = str(edit_name)
                    st.session_state["inventory"].loc[idx_e, "五行"] = str(edit_elem)
                    st.session_state["inventory"].loc[idx_e, "形狀"] = str(edit_shape)
                    st.session_state["inventory"].loc[idx_e, "庫存(顆)"] = str(edit_stock)
                    st.session_state["inventory"].loc[idx_e, "成本單價"] = str(edit_cost)
                    st.session_state["inventory"].loc[idx_e, "進貨廠商"] = str(edit_supplier)

                    save_inventory_to_gs(st.session_state["inventory"])
                    st.success("修改已存檔！")
                    st.rerun()

    st.divider()
    st.subheader("📊 目前雲端庫存總表")
    st.dataframe(st.session_state["inventory"], use_container_width=True)

# ==========================================
# § 6 設計領料頁面
# ==========================================
elif page == "🧮 設計領料":
    st.header("🧮 設計單領料模式")

    col_info1, col_info2 = st.columns([1, 2])
    order_id = col_info1.text_input("設計單號", f"DES-{date.today().strftime('%m%d')}")
    order_note = col_info2.text_input("備註 (用途/客戶)")

    if st.session_state["current_design"]:
        st.subheader("🛒 待領清單明細")
        total_p = 0.0
        with st.container(border=True):
            for i, item in enumerate(st.session_state["current_design"]):
                subtotal = float(item["單價"]) * int(item["數量"])
                total_p += subtotal
                c_text, c_del = st.columns([6, 1])
                cost_text = f" (💰單價:${item['單價']:.2f} | 小計:${subtotal:.2f})" if st.session_state["admin_mode"] else f" (小計: ${subtotal:.2f})"
                shape_text = f" ({item.get('形狀', '')})" if item.get('形狀') else ""
                c_text.markdown(f"🔸 **[{item['五行']}] {item['名稱']}** ({item['規格']}){shape_text} x **{item['數量']}** | 批號:{item['批號']}{cost_text}")
                if c_del.button("🗑️", key=f"del_design_{i}"):
                    st.session_state["current_design"].pop(i)
                    st.rerun()
            st.divider()
            if st.session_state["admin_mode"]:
                st.metric("預估總成本", f"${total_p:.2f}")
            else:
                st.write(f"### 預估總額: ${total_p:.2f}")

            if st.button("🚀 確認領出 (同步扣除庫存並直接紀錄)", type="primary", use_container_width=True):
                log_entries = []
                for it in st.session_state["current_design"]:
                    idx = it["idx"]
                    orig_row = st.session_state["inventory"].loc[idx]

                    new_stock = int(float(st.session_state["inventory"].loc[idx, "庫存(顆)"])) - int(it["數量"])
                    st.session_state["inventory"].loc[idx, "庫存(顆)"] = str(new_stock)

                    log_entries.append({
                        "紀錄時間": datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "單號": order_id,
                        "動作": "設計領料",
                        "倉庫": orig_row.get("倉庫", ""),
                        "批號": it.get("批號", ""),
                        "編號": orig_row.get("編號", ""),
                        "分類": orig_row.get("分類", ""),
                        "名稱": it.get("名稱", ""),
                        "規格": it.get("規格", ""),
                        "廠商": orig_row.get("進貨廠商", ""),
                        "數量變動": -it["數量"],
                        "成本備註": order_note
                    })

                append_history_batch(log_entries)
                save_inventory_to_gs(st.session_state["inventory"])

                st.session_state["current_design"] = []
                st.success("✅ 領料完成！")
                time.sleep(1.5)
                st.rerun()
    else:
        st.info("💡 目前待領清單是空的，請從下方選擇材料加入。")

    st.divider()
    st.subheader("🔍 選擇材料加入")
    inv_d = st.session_state["inventory"]
    if not inv_d.empty:
        inv_d["dp"] = inv_d.apply(lambda r: create_item_label(r, False), axis=1)
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
                "單價": float(target_row_d.get("成本單價", 0)),
                "批號": target_row_d.get("批號", "")
            })
            st.toast(f"已加入: {target_row_d['名稱']}")
            st.rerun()

# ==========================================
# § 7 歷史紀錄頁面
# ==========================================
elif page == "📜 歷史紀錄":
    st.header("📜 歷史出入庫紀錄")

    st.info("正在嘗試抓取雲端資料...")
    hist_df = load_history_from_gs()

    st.write("---")

    if not hist_df.empty and "紀錄時間" in hist_df.columns:
        try:
            st.success("✅ 成功讀取並顯示最新紀錄！")
            st.dataframe(hist_df.iloc[::-1], use_container_width=True)
        except Exception as e:
            st.warning(f"⚠️ 反轉排序時發生錯誤: {e}，請看下方的原始資料表。")
            st.dataframe(hist_df, use_container_width=True)
    else:
        st.error("❌ 系統仍然判定這個表格是『空的』或者『格式異常』。")
        st.warning("👉 請檢查上方印出來的表格，看它到底長什麼樣子。")
        st.dataframe(hist_df, use_container_width=True)
