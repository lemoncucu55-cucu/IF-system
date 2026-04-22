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

ORDER_COLUMNS = [
    '訂單編號', '建立時間', '客戶名稱', '客戶電話', '商品種類', '總售價', '備註', '狀態', '建單人'
]

ORDER_ITEM_COLUMNS = [
    '訂單編號', '庫存編號', '名稱', '規格', '五行', '形狀', '數量', '批號'
]

HISTORY_COLUMNS = [
    '紀錄時間', '單號', '動作', '倉庫', '批號', '編號', '分類', '名稱',
    '規格', '廠商', '數量變動', '成本備註'
]

STATUS_FLOW = ["待確認", "已確認", "已出貨", "已完成", "已取消"]

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

def get_or_create_worksheet(name, columns):
    client = get_gs_client()
    wb = client.open_by_key(SHEET_ID)
    try:
        ws = wb.worksheet(name)
    except gspread.exceptions.WorksheetNotFound:
        ws = wb.add_worksheet(title=name, rows="1000", cols="20")
        ws.update(range_name='A1', values=[columns])
    return ws

def load_sheet_data(sheet_name, columns):
    try:
        client = get_gs_client()
        wb = client.open_by_key(SHEET_ID)
        try:
            ws = wb.worksheet(sheet_name)
        except gspread.exceptions.WorksheetNotFound:
            ws = wb.add_worksheet(title=sheet_name, rows="1000", cols="20")
            ws.update(range_name='A1', values=[columns])
            return pd.DataFrame(columns=columns)
        values = ws.get_all_values()
        if not values or len(values) < 2:
            return pd.DataFrame(columns=columns)
        headers = [str(h).strip().replace("\ufeff", "") for h in values[0]]
        final_headers = []
        for i, h in enumerate(headers):
            if not h: final_headers.append(f"未命名_{i}")
            elif h in final_headers: final_headers.append(f"{h}_{i}")
            else: final_headers.append(h)
        df = pd.DataFrame(values[1:], columns=final_headers)
        mask = df.astype(str).apply(lambda x: x.str.strip() != "").any(axis=1)
        df = df[mask]
        for col in columns:
            if col not in df.columns:
                df[col] = ""
        return df[columns].copy()
    except Exception as e:
        st.error(f"讀取 {sheet_name} 失敗: {e}")
        return pd.DataFrame(columns=columns)

def save_sheet_data(sheet_name, df):
    try:
        ws = get_or_create_worksheet(sheet_name, df.columns.tolist())
        df_to_save = df.fillna("").astype(str)
        values = [df_to_save.columns.tolist()] + df_to_save.values.tolist()
        ws.clear()
        ws.update(range_name='A1', values=values)
    except Exception as e:
        st.error(f"儲存 {sheet_name} 失敗: {e}")

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

def generate_order_id():
    now = datetime.now()
    return f"ORD-{now.strftime('%m%d%H%M%S')}"

# ==========================================
# § 4 系統初始化
# ==========================================
st.set_page_config(page_title="IF Crystal 訂單系統", layout="wide", page_icon="📋")

st.title("💎 IF Crystal 訂單系統")

if "inventory" not in st.session_state:
    st.session_state["inventory"] = load_inventory_from_gs()
if "order_items" not in st.session_state:
    st.session_state["order_items"] = []

with st.sidebar:
    st.title("💎 IF Crystal")
    st.caption("訂單管理系統 — 所有人皆可使用")
    page = st.radio("功能導覽", [
        "📝 建立訂單",
        "📋 訂單列表",
        "🔄 訂單管理",
        "📜 訂單紀錄"
    ])

    if st.button("🔄 刷新資料"):
        get_gs_client.clear()
        st.session_state["inventory"] = load_inventory_from_gs()
        st.rerun()

inv = st.session_state["inventory"]

# ==========================================
# § 5 建立訂單
# ==========================================
if page == "📝 建立訂單":
    st.header("📝 建立新訂單")

    st.subheader("客戶資訊")
    c1, c2, c3 = st.columns(3)
    customer_name = c1.text_input("客戶名稱")
    customer_phone = c2.text_input("客戶電話")
    product_type = c3.selectbox("商品種類", ["客製", "公版"])

    c4, c5, c6 = st.columns(3)
    total_price = c4.number_input("總售價 ($)", min_value=0.0, value=0.0)
    order_creator = c5.selectbox("建單人", ["Imeng", "千畇"])
    order_note = c6.text_input("備註")

    st.divider()

    # 待加入的商品清單
    if st.session_state["order_items"]:
        st.subheader("🛒 訂單品項明細")
        with st.container(border=True):
            for i, item in enumerate(st.session_state["order_items"]):
                c_text, c_del = st.columns([6, 1])
                shape_text = f" ({item.get('形狀', '')})" if item.get('形狀') else ""
                c_text.markdown(
                    f"🔸 **[{item['五行']}] {item['名稱']}** ({item['規格']}){shape_text} "
                    f"x **{item['數量']}** | 批號:{item['批號']}"
                )
                if c_del.button("🗑️", key=f"del_order_item_{i}"):
                    st.session_state["order_items"].pop(i)
                    st.rerun()

            st.divider()
            st.write(f"**共 {len(st.session_state['order_items'])} 項商品**")

        if st.button("🚀 確認建立訂單", type="primary", use_container_width=True):
            if not customer_name:
                st.error("❌ 請填寫客戶名稱")
            else:
                order_id = generate_order_id()

                # 儲存訂單主表
                orders_df = load_sheet_data("Orders", ORDER_COLUMNS)
                new_order = {
                    "訂單編號": order_id,
                    "建立時間": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "客戶名稱": customer_name,
                    "客戶電話": customer_phone,
                    "商品種類": product_type,
                    "總售價": str(total_price),
                    "備註": order_note,
                    "狀態": "待確認",
                    "建單人": order_creator
                }
                orders_df = pd.concat([orders_df, pd.DataFrame([new_order])], ignore_index=True)
                save_sheet_data("Orders", orders_df)

                # 儲存訂單品項
                items_df = load_sheet_data("OrderItems", ORDER_ITEM_COLUMNS)
                new_items = []
                for it in st.session_state["order_items"]:
                    new_items.append({
                        "訂單編號": order_id,
                        "庫存編號": it.get("庫存編號", ""),
                        "名稱": it["名稱"],
                        "規格": it["規格"],
                        "五行": it.get("五行", ""),
                        "形狀": it.get("形狀", ""),
                        "數量": str(it["數量"]),
                        "批號": it.get("批號", "")
                    })
                items_df = pd.concat([items_df, pd.DataFrame(new_items)], ignore_index=True)
                save_sheet_data("OrderItems", items_df)

                st.session_state["order_items"] = []
                st.success(f"✅ 訂單 {order_id} 已建立！狀態：待確認")
                time.sleep(1.5)
                st.rerun()
    else:
        st.info("💡 請從下方選擇商品加入訂單。")

    st.divider()
    st.subheader("🔍 選擇商品加入訂單")
    if not inv.empty:
        inv_d = inv.copy()
        inv_d["dp"] = inv_d.apply(lambda r: create_item_label(r), axis=1)
        sel_d = st.selectbox("搜尋庫存品名/批號", inv_d["dp"].tolist(), key="order_item_search")
        target_idx = inv_d[inv_d["dp"] == sel_d].index[0]
        target_row = inv_d.loc[target_idx]
        col_qty, col_btn = st.columns([1, 1])
        pick_q = col_qty.number_input("數量", 1, max_value=max(1, int(float(target_row.get("庫存(顆)", 1)))), key="order_pick_qty")
        if col_btn.button("➕ 加入訂單", use_container_width=True):
            st.session_state["order_items"].append({
                "idx": target_idx,
                "庫存編號": target_row.get("編號", ""),
                "名稱": target_row["名稱"],
                "五行": target_row.get("五行", ""),
                "形狀": target_row.get("形狀", ""),
                "規格": format_size(target_row),
                "數量": pick_q,
                "批號": target_row.get("批號", ""),
                "倉庫": target_row.get("倉庫", ""),
                "分類": target_row.get("分類", "")
            })
            st.toast(f"已加入: {target_row['名稱']}")
            st.rerun()

# ==========================================
# § 6 訂單列表
# ==========================================
elif page == "📋 訂單列表":
    st.header("📋 所有訂單列表")

    orders_df = load_sheet_data("Orders", ORDER_COLUMNS)

    if orders_df.empty:
        st.info("目前沒有任何訂單。")
    else:
        # 篩選
        c1, c2 = st.columns(2)
        status_filter = c1.selectbox("篩選狀態", ["全部"] + STATUS_FLOW)
        search_customer = c2.text_input("搜尋客戶名稱")

        display_df = orders_df.copy()
        if status_filter != "全部":
            display_df = display_df[display_df["狀態"] == status_filter]
        if search_customer:
            display_df = display_df[display_df["客戶名稱"].str.contains(search_customer, case=False, na=False)]

        if display_df.empty:
            st.info("篩選後沒有訂單。")
        else:
            # 狀態標記顏色
            st.dataframe(display_df.iloc[::-1], use_container_width=True)
            st.caption(f"共 {len(display_df)} 筆訂單")

        # 點選查看訂單明細
        st.divider()
        st.subheader("🔍 查看訂單明細")
        order_ids = display_df["訂單編號"].tolist()
        if order_ids:
            sel_order = st.selectbox("選擇訂單編號", order_ids[::-1])
            order_info = orders_df[orders_df["訂單編號"] == sel_order].iloc[0]

            with st.container(border=True):
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("客戶", order_info["客戶名稱"])
                c2.metric("電話", order_info["客戶電話"] if order_info["客戶電話"] else "-")
                c3.metric("總售價", f"${float(order_info['總售價']):,.2f}" if order_info["總售價"] else "$0")
                c4.metric("狀態", order_info["狀態"])

                st.write(f"**商品種類：** {order_info['商品種類']} | **建單人：** {order_info['建單人']} | **建立時間：** {order_info['建立時間']}")
                if order_info["備註"]:
                    st.write(f"**備註：** {order_info['備註']}")

            # 顯示品項
            items_df = load_sheet_data("OrderItems", ORDER_ITEM_COLUMNS)
            order_items = items_df[items_df["訂單編號"] == sel_order]
            if not order_items.empty:
                st.write("**訂單品項：**")
                st.dataframe(order_items[["名稱", "規格", "五行", "形狀", "數量", "批號"]], use_container_width=True)
            else:
                st.info("此訂單沒有品項紀錄。")

# ==========================================
# § 7 訂單管理（狀態變更）
# ==========================================
elif page == "🔄 訂單管理":
    st.header("🔄 訂單管理")

    orders_df = load_sheet_data("Orders", ORDER_COLUMNS)

    if orders_df.empty:
        st.info("目前沒有任何訂單。")
    else:
        # 只顯示未完成的訂單
        active_orders = orders_df[~orders_df["狀態"].isin(["已完成", "已取消"])]
        if active_orders.empty:
            st.success("🎉 所有訂單都已完成！")
        else:
            # 建立選單標籤
            active_orders = active_orders.copy()
            active_orders["display"] = active_orders.apply(
                lambda r: f"[{r['狀態']}] {r['訂單編號']} — {r['客戶名稱']} (${r['總售價']})", axis=1
            )
            sel_order_display = st.selectbox("選擇要管理的訂單", active_orders["display"].tolist()[::-1])
            sel_idx = active_orders[active_orders["display"] == sel_order_display].index[0]
            sel_order = orders_df.loc[sel_idx]
            order_id = sel_order["訂單編號"]

            # 顯示訂單資訊
            with st.container(border=True):
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("訂單編號", order_id)
                c2.metric("客戶", sel_order["客戶名稱"])
                c3.metric("總售價", f"${float(sel_order['總售價']):,.2f}" if sel_order["總售價"] else "$0")
                c4.metric("目前狀態", sel_order["狀態"])

                st.write(f"**電話：** {sel_order['客戶電話']} | **商品種類：** {sel_order['商品種類']} | **建單人：** {sel_order['建單人']}")
                if sel_order["備註"]:
                    st.write(f"**備註：** {sel_order['備註']}")

            # 顯示品項
            items_df = load_sheet_data("OrderItems", ORDER_ITEM_COLUMNS)
            order_items = items_df[items_df["訂單編號"] == order_id]
            if not order_items.empty:
                st.write("**訂單品項：**")
                st.dataframe(order_items[["名稱", "規格", "五行", "形狀", "數量", "批號"]], use_container_width=True)

            st.divider()

            # 狀態操作按鈕
            current_status = sel_order["狀態"]

            if current_status == "待確認":
                col_a, col_b = st.columns(2)
                if col_a.button("✅ 確認訂單（自動扣庫存）", type="primary", use_container_width=True):
                    # 自動從庫存扣料
                    success = True
                    log_entries = []
                    inventory = st.session_state["inventory"]

                    for _, item_row in order_items.iterrows():
                        stock_id = item_row["庫存編號"]
                        qty = int(item_row["數量"])
                        match = inventory[inventory["編號"] == stock_id]
                        if match.empty:
                            st.error(f"❌ 找不到庫存編號 {stock_id}（{item_row['名稱']}），請確認庫存。")
                            success = False
                            break
                        match_idx = match.index[0]
                        current_stock = int(float(inventory.loc[match_idx, "庫存(顆)"]))
                        if current_stock < qty:
                            st.error(f"❌ {item_row['名稱']} 庫存不足（需要 {qty}，現有 {current_stock}）")
                            success = False
                            break
                        # 扣庫存
                        new_stock = current_stock - qty
                        st.session_state["inventory"].loc[match_idx, "庫存(顆)"] = str(new_stock)

                        log_entries.append({
                            "紀錄時間": datetime.now().strftime("%Y-%m-%d %H:%M"),
                            "單號": order_id,
                            "動作": "訂單扣料",
                            "倉庫": inventory.loc[match_idx, "倉庫"],
                            "批號": item_row.get("批號", ""),
                            "編號": stock_id,
                            "分類": inventory.loc[match_idx, "分類"],
                            "名稱": item_row["名稱"],
                            "規格": item_row.get("規格", ""),
                            "廠商": f"客戶:{sel_order['客戶名稱']}",
                            "數量變動": str(-qty),
                            "成本備註": f"訂單售價 ${sel_order['總售價']}"
                        })

                    if success:
                        # 更新訂單狀態
                        orders_df.loc[sel_idx, "狀態"] = "已確認"
                        save_sheet_data("Orders", orders_df)
                        save_inventory_to_gs(st.session_state["inventory"])
                        append_history_batch(log_entries)
                        st.success(f"✅ 訂單 {order_id} 已確認，庫存已自動扣除！")
                        time.sleep(1.5)
                        st.rerun()

                if col_b.button("❌ 取消訂單", use_container_width=True):
                    orders_df.loc[sel_idx, "狀態"] = "已取消"
                    save_sheet_data("Orders", orders_df)
                    st.warning(f"訂單 {order_id} 已取消。")
                    time.sleep(1.5)
                    st.rerun()

            elif current_status == "已確認":
                col_a, col_b = st.columns(2)
                if col_a.button("📦 標記為已出貨", type="primary", use_container_width=True):
                    orders_df.loc[sel_idx, "狀態"] = "已出貨"
                    save_sheet_data("Orders", orders_df)
                    st.success(f"✅ 訂單 {order_id} 已標記為出貨！")
                    time.sleep(1.5)
                    st.rerun()

                if col_b.button("↩️ 取消訂單（退回庫存）", use_container_width=True):
                    # 退回庫存
                    inventory = st.session_state["inventory"]
                    log_entries = []
                    for _, item_row in order_items.iterrows():
                        stock_id = item_row["庫存編號"]
                        qty = int(item_row["數量"])
                        match = inventory[inventory["編號"] == stock_id]
                        if not match.empty:
                            match_idx = match.index[0]
                            current_stock = int(float(inventory.loc[match_idx, "庫存(顆)"]))
                            st.session_state["inventory"].loc[match_idx, "庫存(顆)"] = str(current_stock + qty)
                            log_entries.append({
                                "紀錄時間": datetime.now().strftime("%Y-%m-%d %H:%M"),
                                "單號": order_id,
                                "動作": "訂單取消退庫",
                                "倉庫": inventory.loc[match_idx, "倉庫"],
                                "批號": item_row.get("批號", ""),
                                "編號": stock_id,
                                "分類": inventory.loc[match_idx, "分類"],
                                "名稱": item_row["名稱"],
                                "規格": item_row.get("規格", ""),
                                "廠商": f"客戶:{sel_order['客戶名稱']}",
                                "數量變動": str(qty),
                                "成本備註": f"訂單取消退回"
                            })

                    orders_df.loc[sel_idx, "狀態"] = "已取消"
                    save_sheet_data("Orders", orders_df)
                    save_inventory_to_gs(st.session_state["inventory"])
                    if log_entries:
                        append_history_batch(log_entries)
                    st.warning(f"訂單 {order_id} 已取消，庫存已退回。")
                    time.sleep(1.5)
                    st.rerun()

            elif current_status == "已出貨":
                if st.button("✅ 標記為已完成", type="primary", use_container_width=True):
                    orders_df.loc[sel_idx, "狀態"] = "已完成"
                    save_sheet_data("Orders", orders_df)
                    st.success(f"🎉 訂單 {order_id} 已完成！")
                    time.sleep(1.5)
                    st.rerun()

# ==========================================
# § 8 訂單紀錄
# ==========================================
elif page == "📜 訂單紀錄":
    st.header("📜 訂單紀錄總覽")

    orders_df = load_sheet_data("Orders", ORDER_COLUMNS)

    if orders_df.empty:
        st.info("目前沒有任何訂單。")
    else:
        # 統計
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("總訂單數", f"{len(orders_df)} 筆")
        completed = len(orders_df[orders_df["狀態"] == "已完成"])
        c2.metric("已完成", f"{completed} 筆")
        pending = len(orders_df[orders_df["狀態"].isin(["待確認", "已確認", "已出貨"])])
        c3.metric("進行中", f"{pending} 筆")
        try:
            total_revenue = orders_df[orders_df["狀態"] == "已完成"]["總售價"].apply(lambda x: float(x) if x else 0).sum()
            c4.metric("已完成總營收", f"${total_revenue:,.2f}")
        except:
            c4.metric("已完成總營收", "$0")

        st.divider()
        st.dataframe(orders_df.iloc[::-1], use_container_width=True)
