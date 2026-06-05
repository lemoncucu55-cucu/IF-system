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

# 進貨訂購單欄位
PO_COLUMNS = [
    '訂購單號', '訂購日期', '編號', '名稱', '規格', '廠商',
    '訂購數量', '訂購總價', '訂購單價', '狀態', '入庫日期', '備註'
]
PO_STATUS = ["待入庫", "已入庫", "已取消"]

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

def load_purchase_orders():
    try:
        client = get_gs_client()
        wb = client.open_by_key(SHEET_ID)
        try:
            ws = wb.worksheet("PurchaseOrders")
        except gspread.exceptions.WorksheetNotFound:
            ws = wb.add_worksheet(title="PurchaseOrders", rows="1000", cols="20")
            ws.update(range_name='A1', values=[PO_COLUMNS])
            return pd.DataFrame(columns=PO_COLUMNS)
        values = ws.get_all_values()
        if not values or len(values) < 2:
            return pd.DataFrame(columns=PO_COLUMNS)
        headers = [str(h).strip().replace("﻿", "") for h in values[0]]
        df = pd.DataFrame(values[1:], columns=headers)
        df = df[df.astype(str).apply(lambda x: x.str.strip() != "").any(axis=1)]
        for col in PO_COLUMNS:
            if col not in df.columns:
                df[col] = ""
        return df[PO_COLUMNS].copy()
    except Exception as e:
        st.error(f"讀取訂購單失敗: {e}")
        return pd.DataFrame(columns=PO_COLUMNS)

def save_purchase_orders(df):
    try:
        client = get_gs_client()
        wb = client.open_by_key(SHEET_ID)
        try:
            ws = wb.worksheet("PurchaseOrders")
        except gspread.exceptions.WorksheetNotFound:
            ws = wb.add_worksheet(title="PurchaseOrders", rows="1000", cols="20")
        data = df.fillna("").astype(str)
        ws.clear()
        ws.update(range_name='A1', values=[data.columns.tolist()] + data.values.tolist())
    except Exception as e:
        st.error(f"儲存訂購單失敗: {e}")

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
    cost = f" 💰${float(row.get('成本單價', 0)):.2f}"
    shape = f" ({row.get('形狀', '')})" if row.get('形狀') else ""
    supplier = f" 📦{row.get('進貨廠商', '')}" if row.get('進貨廠商') else ""
    return f"[{row.get('倉庫','-')}] {elem}{row.get('名稱','-')} {sz}{shape} 【{row.get('批號','-')}】 | 存:{stock}{cost}{supplier}"

def get_unique_options(col, defaults, df):
    existing = {str(v).strip() for v in df[col].unique() if str(v).strip() and str(v).lower() not in ("nan", "0", "")}
    return [MANUAL] + sorted(existing | set(defaults))

# ==========================================
# § 4 系統初始化 — 主管密碼驗證
# ==========================================
st.set_page_config(page_title="IF Crystal 進貨管理系統", layout="wide", page_icon="🔒")

if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

if not st.session_state["authenticated"]:
    st.title("💎 IF Crystal 進貨管理系統")
    st.caption("此系統僅限主管使用，請輸入密碼登入。")
    with st.form("login_form"):
        pwd = st.text_input("請輸入主管密碼", type="password")
        if st.form_submit_button("登入", use_container_width=True):
            if pwd == "admin123":
                st.session_state["authenticated"] = True
                st.rerun()
            else:
                st.error("❌ 密碼錯誤")
    st.stop()

# ---- 已登入 ----
st.title("💎 IF Crystal 進貨管理系統")

if "inventory" not in st.session_state:
    st.session_state["inventory"] = load_inventory_from_gs()
if "current_design" not in st.session_state:
    st.session_state["current_design"] = []

with st.sidebar:
    st.title("💎 IF Crystal")
    st.caption("進貨管理系統 — 主管專用")
    page = st.radio("功能導覽", ["✨ 新品建檔", "📋 進貨訂購", "📦 入庫確認", "🛠️ 資料修改", "📊 庫存總表", "📜 進貨紀錄"])

    if st.button("🔄 強制刷新雲端資料"):
        get_gs_client.clear()
        st.session_state["inventory"] = load_inventory_from_gs()
        st.rerun()

    st.divider()
    if st.button("🚪 登出"):
        st.session_state["authenticated"] = False
        st.rerun()

inv = st.session_state["inventory"]

# ==========================================
# § 5 新品建檔
# ==========================================
if page == "✨ 新品建檔":
    st.header("✨ 新品建檔")

    with st.form("create_form"):
        st.subheader("基本資訊")
        c1, c2, c3 = st.columns(3)
        new_wh = c1.selectbox("倉庫", ["Imeng", "千畇"])

        n_opts = get_unique_options("名稱", ["水晶"], inv)
        n_sel = c2.selectbox("名稱 (選單)", n_opts)
        n_man = c2.text_input("手動輸入名稱")

        el_opts = get_unique_options("五行", ["金", "木", "水", "火", "土"], inv)
        el_sel = c3.selectbox("五行/顏色 (選單)", el_opts)
        el_man = c3.text_input("手動輸入五行")

        st.subheader("規格")
        c4, c5, c6 = st.columns(3)
        sh_opts = get_unique_options("形狀", ["圓珠", "切角", "鑽切", "圓筒", "方體", "長柱", "不規則", "造型", "原礦"], inv)
        sh_sel = c4.selectbox("形狀 (選單)", sh_opts)
        sh_man = c4.text_input("手動輸入形狀")
        new_wh_mm = c5.number_input("寬度 mm", min_value=0.0)
        new_len_mm = c6.number_input("長度 mm", min_value=0.0, value=0.0)

        st.subheader("進貨資訊")
        c7, c8, c9 = st.columns(3)
        new_qty = c7.number_input("進貨數量", min_value=1, value=1)
        new_cost = c8.number_input("單顆成本 ($)", min_value=0.0)
        new_date = c9.date_input("進貨日期", value=date.today())

        sup_opts = get_unique_options("進貨廠商", [], inv)
        sup_sel = st.selectbox("進貨廠商", sup_opts, key="new_sup")
        sup_man = st.text_input("手動輸入廠商", key="new_sup_man")

        batch_note = st.text_input("批號備註", value="初始存貨")

        if st.form_submit_button("✅ 提交建檔", use_container_width=True):
            final_name = n_man if n_sel == MANUAL else n_sel
            final_elem = el_man if el_sel == MANUAL else el_sel
            final_shape = sh_man if sh_sel == MANUAL else sh_sel
            final_supplier = sup_man if sup_sel == MANUAL else sup_sel

            new_data = {
                "編號": f"ST{uuid.uuid4().hex[:6].upper()}",
                "批號": str(batch_note),
                "倉庫": str(new_wh),
                "分類": "天然石",
                "名稱": str(final_name),
                "形狀": str(final_shape),
                "五行": str(final_elem),
                "寬度mm": str(new_wh_mm),
                "長度mm": str(new_len_mm),
                "進貨數量(顆)": str(new_qty),
                "進貨日期": str(new_date),
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
                "數量變動": str(new_qty),
                "成本備註": f"單價 ${new_cost}"
            }
            append_history_batch([log_entry])
            st.session_state["inventory"] = pd.concat([inv, pd.DataFrame([new_data])], ignore_index=True)
            save_inventory_to_gs(st.session_state["inventory"])
            st.success(f"✅ 已成功建立：{final_name}")
            st.rerun()

# ==========================================
# § 6 進貨訂購（紀錄訂購，不影響庫存）
# ==========================================
elif page == "📋 進貨訂購":
    st.header("📋 進貨訂購 — 紀錄訂購資訊")
    st.caption("記錄向廠商訂購的資訊，庫存不會變動。實際收到貨後請到「📦 入庫確認」操作。")

    if inv.empty:
        st.warning("目前沒有庫存品項，請先建檔。")
    else:
        po_df = load_purchase_orders()

        # ── 建立新訂購單 ──
        st.subheader("➕ 建立訂購單")
        df_label = inv.copy()
        df_label["display"] = df_label.apply(lambda r: create_item_label(r), axis=1)
        sel_target = st.selectbox("選擇要訂購的商品", df_label["display"].tolist(), key="po_item")
        target_idx = df_label[df_label["display"] == sel_target].index[0]
        target_row = inv.loc[target_idx]

        with st.form("po_form"):
            st.write(f"📍 **商品：** {target_row['名稱']} ({format_size(target_row)}) | 現有庫存：{target_row['庫存(顆)']} 顆")

            c1, c2, c3 = st.columns(3)
            po_qty = c1.number_input("訂購數量", min_value=1, value=1)
            po_total = c2.number_input("訂購總價 ($)", min_value=0.0)
            po_date = c3.date_input("訂購日期", value=date.today())

            sup_opts = get_unique_options("進貨廠商", [], inv)
            sup_sel = st.selectbox("廠商", sup_opts, key="po_sup")
            sup_man = st.text_input("手動輸入廠商", key="po_sup_man")
            po_note = st.text_input("備註（選填）")

            if st.form_submit_button("✅ 建立訂購單", use_container_width=True):
                final_supplier = sup_man if sup_sel == MANUAL else sup_sel
                unit_price = round(po_total / po_qty, 2) if po_qty > 0 else 0
                po_id = f"PO-{datetime.now().strftime('%m%d%H%M%S')}"

                new_po = {
                    "訂購單號": po_id,
                    "訂購日期": str(po_date),
                    "編號": target_row["編號"],
                    "名稱": target_row["名稱"],
                    "規格": format_size(target_row),
                    "廠商": final_supplier,
                    "訂購數量": str(po_qty),
                    "訂購總價": str(po_total),
                    "訂購單價": str(unit_price),
                    "狀態": "待入庫",
                    "入庫日期": "",
                    "備註": po_note,
                }
                po_df = pd.concat([po_df, pd.DataFrame([new_po])], ignore_index=True)
                save_purchase_orders(po_df)
                st.success(f"✅ 訂購單 {po_id} 已建立！{target_row['名稱']} x{po_qty}（待入庫）")
                time.sleep(1); st.rerun()

        # ── 訂購單列表 ──
        st.divider()
        st.subheader("📋 訂購單列表")
        if po_df.empty:
            st.info("目前沒有訂購單。")
        else:
            # 篩選
            po_filter = st.selectbox("篩選狀態", ["待入庫", "全部", "已入庫", "已取消"], key="po_filter")
            if po_filter != "全部":
                show_po = po_df[po_df["狀態"] == po_filter]
            else:
                show_po = po_df
            if show_po.empty:
                st.info(f"沒有「{po_filter}」的訂購單。")
            else:
                st.dataframe(show_po.iloc[::-1], use_container_width=True, hide_index=True)
                st.caption(f"共 {len(show_po)} 筆")

            # 取消訂購單
            pending_po = po_df[po_df["狀態"] == "待入庫"]
            if not pending_po.empty:
                st.divider()
                st.subheader("❌ 取消訂購單")
                cancel_opts = pending_po.apply(
                    lambda r: f"{r['訂購單號']} — {r['名稱']} x{r['訂購數量']} ({r['廠商']}) ${r['訂購總價']}", axis=1).tolist()
                sel_cancel = st.selectbox("選擇要取消的訂購單", cancel_opts, key="po_cancel")
                if st.button("❌ 確認取消", use_container_width=True):
                    cancel_idx = cancel_opts.index(sel_cancel)
                    real_idx = pending_po.index[cancel_idx]
                    po_df.loc[real_idx, "狀態"] = "已取消"
                    save_purchase_orders(po_df)
                    st.warning("訂購單已取消。")
                    time.sleep(1); st.rerun()

# ==========================================
# § 6.5 入庫確認（實際收到貨，更新庫存）
# ==========================================
elif page == "📦 入庫確認":
    st.header("📦 入庫確認 — 實際收貨入庫")
    st.caption("從待入庫的訂購單中確認收貨，庫存會自動增加。")

    po_df = load_purchase_orders()
    pending_po = po_df[po_df["狀態"] == "待入庫"] if not po_df.empty else pd.DataFrame(columns=PO_COLUMNS)

    if pending_po.empty:
        st.info("🎉 目前沒有待入庫的訂購單。")
        if not po_df.empty:
            st.divider()
            st.subheader("📋 最近入庫紀錄")
            received = po_df[po_df["狀態"] == "已入庫"]
            if not received.empty:
                st.dataframe(received.iloc[::-1].head(10), use_container_width=True, hide_index=True)
    else:
        # ── 待入庫清單 ──
        st.subheader(f"🚚 待入庫訂購單 — 共 {len(pending_po)} 筆")
        st.dataframe(pending_po.iloc[::-1], use_container_width=True, hide_index=True)

        # ── 選擇入庫 ──
        st.divider()
        st.subheader("✅ 確認入庫")
        receive_opts = pending_po.apply(
            lambda r: f"{r['訂購單號']} — {r['名稱']} x{r['訂購數量']} ({r['廠商']}) ${r['訂購總價']}", axis=1).tolist()
        sel_receive = st.selectbox("選擇要入庫的訂購單", receive_opts)
        receive_idx = receive_opts.index(sel_receive)
        po_row = pending_po.iloc[receive_idx]
        real_po_idx = pending_po.index[receive_idx]

        with st.container(border=True):
            rc1, rc2, rc3, rc4 = st.columns(4)
            rc1.metric("商品", po_row["名稱"])
            rc2.metric("訂購數量", f"{po_row['訂購數量']} 顆")
            rc3.metric("單價", f"${float(po_row['訂購單價']) if po_row['訂購單價'] else 0:.2f}")
            rc4.metric("總價", f"${float(po_row['訂購總價']) if po_row['訂購總價'] else 0:.2f}")

        with st.form("receive_form"):
            rf1, rf2 = st.columns(2)
            actual_qty = rf1.number_input("實際收到數量", min_value=1,
                value=int(float(po_row["訂購數量"])) if po_row["訂購數量"] else 1)
            receive_date = rf2.date_input("入庫日期", value=date.today())
            batch_note = st.text_input("批號備註（選填）")

            if st.form_submit_button("📦 確認入庫", type="primary", use_container_width=True):
                inv_id = po_row["編號"]
                inv_match = inv[inv["編號"] == inv_id]

                if inv_match.empty:
                    st.error(f"❌ 找不到編號 {inv_id} 的庫存品項")
                else:
                    inv_idx = inv_match.index[0]
                    po_qty = int(float(po_row["訂購數量"]))
                    po_total = float(po_row["訂購總價"]) if po_row["訂購總價"] else 0
                    new_cost = round(po_total / actual_qty, 2) if actual_qty > 0 else 0

                    # 更新庫存
                    old_stock = int(float(st.session_state["inventory"].loc[inv_idx, "庫存(顆)"]))
                    new_stock = old_stock + actual_qty
                    st.session_state["inventory"].loc[inv_idx, "庫存(顆)"] = str(new_stock)
                    st.session_state["inventory"].loc[inv_idx, "成本單價"] = str(new_cost)
                    st.session_state["inventory"].loc[inv_idx, "進貨廠商"] = str(po_row["廠商"])
                    st.session_state["inventory"].loc[inv_idx, "進貨日期"] = str(receive_date)
                    if batch_note:
                        st.session_state["inventory"].loc[inv_idx, "批號"] = str(batch_note)
                    save_inventory_to_gs(st.session_state["inventory"])

                    # 更新訂購單狀態
                    po_df.loc[real_po_idx, "狀態"] = "已入庫"
                    po_df.loc[real_po_idx, "入庫日期"] = str(receive_date)
                    if actual_qty != po_qty:
                        po_df.loc[real_po_idx, "備註"] = f"{po_row['備註']} | 實收{actual_qty}顆(原訂{po_qty})"
                    save_purchase_orders(po_df)

                    # 寫入歷史紀錄
                    target_row = inv.loc[inv_idx]
                    log_entry = {
                        "紀錄時間": datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "單號": po_row["訂購單號"],
                        "動作": "入庫確認",
                        "倉庫": target_row.get("倉庫", ""),
                        "批號": batch_note or target_row.get("批號", ""),
                        "編號": inv_id,
                        "分類": target_row.get("分類", ""),
                        "名稱": po_row["名稱"],
                        "規格": po_row["規格"],
                        "廠商": po_row["廠商"],
                        "數量變動": str(actual_qty),
                        "成本備註": f"總價${po_total} | 單價${new_cost} | 庫存{old_stock}→{new_stock}"
                    }
                    append_history_batch([log_entry])

                    st.success(f"✅ {po_row['名稱']} 入庫 {actual_qty} 顆！庫存：{old_stock} → {new_stock}")
                    time.sleep(1); st.rerun()




# ==========================================
# § 7 資料修改
# ==========================================
elif page == "🛠️ 資料修改":
    st.header("🛠️ 資料修改")

    if inv.empty:
        st.warning("目前沒有庫存品項。")
    else:
        df_label_e = inv.copy()
        df_label_e["display"] = df_label_e.apply(lambda r: create_item_label(r), axis=1)
        sel_e = st.selectbox("選擇要修改的商品", df_label_e["display"].tolist())
        idx_e = df_label_e[df_label_e["display"] == sel_e].index[0]
        row_e = inv.loc[idx_e]

        with st.form("edit_form"):
            st.subheader("基本資訊")
            ca, cb, cc = st.columns(3)
            edit_name = ca.text_input("名稱", row_e["名稱"])
            edit_elem = cb.text_input("五行", row_e.get("五行", ""))
            edit_shape = cc.text_input("形狀", row_e.get("形狀", ""))

            cd, ce = st.columns(2)
            edit_wh = cd.selectbox("倉庫", ["Imeng", "千畇"], index=["Imeng", "千畇"].index(row_e["倉庫"]) if row_e["倉庫"] in ["Imeng", "千畇"] else 0)
            edit_batch = ce.text_input("批號", row_e.get("批號", ""))

            st.subheader("規格")
            cf, cg = st.columns(2)
            edit_w = cf.number_input("寬度 mm", value=float(row_e.get("寬度mm", 0)))
            edit_l = cg.number_input("長度 mm", value=float(row_e.get("長度mm", 0)))

            st.subheader("進貨與庫存")
            c1, c2, c3 = st.columns(3)
            edit_stock = c1.number_input("庫存數量", value=int(float(row_e["庫存(顆)"])))
            edit_cost = c2.number_input("成本單價", value=float(row_e.get("成本單價", 0)))
            edit_supplier = c3.text_input("廠商", row_e.get("進貨廠商", ""))

            if st.form_submit_button("💾 儲存所有修改", use_container_width=True):
                log_entry = {
                    "紀錄時間": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "單號": "EDIT",
                    "動作": "資料修改",
                    "倉庫": edit_wh,
                    "批號": edit_batch,
                    "編號": row_e["編號"],
                    "分類": row_e["分類"],
                    "名稱": edit_name,
                    "規格": f"{edit_w}x{edit_l}mm" if edit_l > 0 else f"{edit_w}mm",
                    "廠商": edit_supplier,
                    "數量變動": str(edit_stock - int(float(row_e["庫存(顆)"]))),
                    "成本備註": f"原庫存 {row_e['庫存(顆)']} -> {edit_stock}"
                }
                append_history_batch([log_entry])

                st.session_state["inventory"].loc[idx_e, "名稱"] = str(edit_name)
                st.session_state["inventory"].loc[idx_e, "五行"] = str(edit_elem)
                st.session_state["inventory"].loc[idx_e, "形狀"] = str(edit_shape)
                st.session_state["inventory"].loc[idx_e, "倉庫"] = str(edit_wh)
                st.session_state["inventory"].loc[idx_e, "批號"] = str(edit_batch)
                st.session_state["inventory"].loc[idx_e, "寬度mm"] = str(edit_w)
                st.session_state["inventory"].loc[idx_e, "長度mm"] = str(edit_l)
                st.session_state["inventory"].loc[idx_e, "庫存(顆)"] = str(edit_stock)
                st.session_state["inventory"].loc[idx_e, "成本單價"] = str(edit_cost)
                st.session_state["inventory"].loc[idx_e, "進貨廠商"] = str(edit_supplier)

                save_inventory_to_gs(st.session_state["inventory"])
                st.success("✅ 修改已存檔！")
                st.rerun()

# ==========================================
# § 8 庫存總表
# ==========================================
elif page == "📊 庫存總表":
    st.header("📊 目前雲端庫存總表")
    st.dataframe(st.session_state["inventory"], use_container_width=True)

    st.divider()
    st.subheader("📈 庫存摘要")
    if not inv.empty:
        inv_summary = inv.copy()
        inv_summary["庫存(顆)"] = inv_summary["庫存(顆)"].apply(lambda x: int(float(x)) if x else 0)
        inv_summary["成本單價"] = inv_summary["成本單價"].apply(lambda x: float(x) if x else 0.0)
        inv_summary["庫存金額"] = inv_summary["庫存(顆)"] * inv_summary["成本單價"]

        c1, c2, c3 = st.columns(3)
        c1.metric("品項總數", f"{len(inv_summary)} 項")
        c2.metric("總顆數", f"{inv_summary['庫存(顆)'].sum():,} 顆")
        c3.metric("總庫存金額", f"${inv_summary['庫存金額'].sum():,.2f}")

# ==========================================
# § 9 進貨紀錄
# ==========================================
elif page == "📜 進貨紀錄":
    st.header("📜 進貨相關紀錄")

    hist_df = load_history_from_gs()

    if hist_df.empty:
        st.info("目前沒有任何紀錄。")
    else:
        # 篩選進貨相關動作
        purchase_actions = ["新品建檔", "補貨進貨", "入庫確認", "資料修改"]
        if "動作" in hist_df.columns:
            filtered = hist_df[hist_df["動作"].isin(purchase_actions)]
            if filtered.empty:
                st.info("目前沒有進貨相關紀錄。")
                st.dataframe(hist_df.iloc[::-1], use_container_width=True)
            else:
                st.dataframe(filtered.iloc[::-1], use_container_width=True)
        else:
            st.dataframe(hist_df.iloc[::-1], use_container_width=True)
