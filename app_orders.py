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

ORDER_COLUMNS = [
    '訂單編號', '建立時間', '客戶名稱', '客戶電話', '商品種類', '喜神', '忌神', '總售價', '備註', '狀態', '建單人'
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

def load_orders():
    try:
        client = get_gs_client()
        wb = client.open_by_key(SHEET_ID)
        try:
            ws = wb.worksheet("Orders")
        except gspread.exceptions.WorksheetNotFound:
            ws = wb.add_worksheet(title="Orders", rows="1000", cols="20")
            ws.update(range_name='A1', values=[ORDER_COLUMNS])
            return pd.DataFrame(columns=ORDER_COLUMNS)
        values = ws.get_all_values()
        if not values or len(values) < 2:
            return pd.DataFrame(columns=ORDER_COLUMNS)
        headers = [str(h).strip().replace("\ufeff", "") for h in values[0]]
        final_headers = []
        for i, h in enumerate(headers):
            if not h: final_headers.append(f"未命名_{i}")
            elif h in final_headers: final_headers.append(f"{h}_{i}")
            else: final_headers.append(h)
        df = pd.DataFrame(values[1:], columns=final_headers)
        mask = df.astype(str).apply(lambda x: x.str.strip() != "").any(axis=1)
        df = df[mask]
        for col in ORDER_COLUMNS:
            if col not in df.columns:
                df[col] = ""
        return df[ORDER_COLUMNS].copy()
    except Exception as e:
        st.error(f"讀取訂單失敗: {e}")
        return pd.DataFrame(columns=ORDER_COLUMNS)

def save_orders(df):
    try:
        client = get_gs_client()
        wb = client.open_by_key(SHEET_ID)
        try:
            ws = wb.worksheet("Orders")
        except gspread.exceptions.WorksheetNotFound:
            ws = wb.add_worksheet(title="Orders", rows="1000", cols="20")
        df_to_save = df.fillna("").astype(str)
        values = [df_to_save.columns.tolist()] + df_to_save.values.tolist()
        ws.clear()
        ws.update(range_name='A1', values=values)
    except Exception as e:
        st.error(f"儲存訂單失敗: {e}")

def generate_order_id():
    now = datetime.now()
    return f"ORD-{now.strftime('%m%d%H%M%S')}"

# ==========================================
# § 3 系統初始化
# ==========================================
st.set_page_config(page_title="IF Crystal 訂單系統", layout="wide", page_icon="📋")

st.title("💎 IF Crystal 訂單系統")

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
        st.rerun()

# ==========================================
# § 4 建立訂單
# ==========================================
if page == "📝 建立訂單":
    st.header("📝 建立新訂單")

    with st.form("create_order_form"):
        st.subheader("客戶資訊")
        c1, c2 = st.columns(2)
        customer_name = c1.text_input("客戶名稱")
        customer_phone = c2.text_input("客戶電話")

        st.subheader("訂單資訊")
        c3, c4, c5 = st.columns(3)
        product_type = c3.selectbox("商品種類", ["客製", "公版"])
        order_creator = c4.selectbox("建單人", ["Imeng", "千畇"])
        total_price = c5.number_input("總售價 ($)（可之後再填）", min_value=0.0, value=0.0)

        st.subheader("五行")
        wuxing_opts = ["金", "木", "水", "火", "土"]
        c6, c7 = st.columns(2)
        xi_shen = c6.multiselect("喜神", wuxing_opts)
        ji_shen = c7.multiselect("忌神", wuxing_opts)

        order_note = st.text_area("備註")

        if st.form_submit_button("✅ 建立訂單", use_container_width=True):
            if not customer_name:
                st.error("❌ 請填寫客戶名稱")
            else:
                order_id = generate_order_id()
                orders_df = load_orders()
                new_order = {
                    "訂單編號": order_id,
                    "建立時間": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "客戶名稱": customer_name,
                    "客戶電話": customer_phone,
                    "商品種類": product_type,
                    "喜神": "、".join(xi_shen),
                    "忌神": "、".join(ji_shen),
                    "總售價": str(total_price),
                    "備註": order_note,
                    "狀態": "待確認",
                    "建單人": order_creator
                }
                orders_df = pd.concat([orders_df, pd.DataFrame([new_order])], ignore_index=True)
                save_orders(orders_df)
                st.success(f"✅ 訂單 {order_id} 已建立！")
                time.sleep(1.5)
                st.rerun()

# ==========================================
# § 5 訂單列表
# ==========================================
elif page == "📋 訂單列表":
    st.header("📋 所有訂單列表")

    orders_df = load_orders()

    if orders_df.empty:
        st.info("目前沒有任何訂單。")
    else:
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
            st.dataframe(display_df.iloc[::-1], use_container_width=True)
            st.caption(f"共 {len(display_df)} 筆訂單")

# ==========================================
# § 6 訂單管理（狀態變更 + 修改售價）
# ==========================================
elif page == "🔄 訂單管理":
    st.header("🔄 訂單管理")

    orders_df = load_orders()

    if orders_df.empty:
        st.info("目前沒有任何訂單。")
    else:
        active_orders = orders_df[~orders_df["狀態"].isin(["已完成", "已取消"])]
        if active_orders.empty:
            st.success("🎉 所有訂單都已處理完成！")
        else:
            active_orders = active_orders.copy()
            active_orders["display"] = active_orders.apply(
                lambda r: f"[{r['狀態']}] {r['訂單編號']} — {r['客戶名稱']} | {r['商品種類']} | ${r['總售價']}", axis=1
            )
            sel_order_display = st.selectbox("選擇要管理的訂單", active_orders["display"].tolist()[::-1])
            sel_idx = active_orders[active_orders["display"] == sel_order_display].index[0]
            sel_order = orders_df.loc[sel_idx]
            order_id = sel_order["訂單編號"]

            with st.container(border=True):
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("訂單編號", order_id)
                c2.metric("客戶", sel_order["客戶名稱"])
                c3.metric("總售價", f"${float(sel_order['總售價']):,.2f}" if sel_order["總售價"] else "$0")
                c4.metric("目前狀態", sel_order["狀態"])

                st.write(f"**電話：** {sel_order['客戶電話']} | **商品種類：** {sel_order['商品種類']} | **建單人：** {sel_order['建單人']} | **建立時間：** {sel_order['建立時間']}")
                st.write(f"**喜神：** {sel_order['喜神'] if sel_order['喜神'] else '-'} | **忌神：** {sel_order['忌神'] if sel_order['忌神'] else '-'}")
                if sel_order["備註"]:
                    st.write(f"**備註：** {sel_order['備註']}")

            st.divider()

            st.subheader("✏️ 修改訂單")
            with st.form("edit_order_form"):
                c_e1, c_e2 = st.columns(2)
                edit_price = c_e1.number_input("修改總售價 ($)", value=float(sel_order["總售價"]) if sel_order["總售價"] else 0.0)
                edit_note = c_e2.text_input("修改備註", value=sel_order["備註"])

                wuxing_opts = ["金", "木", "水", "火", "土"]
                c_e3, c_e4 = st.columns(2)
                current_xi = [x for x in sel_order["喜神"].split("、") if x] if sel_order["喜神"] else []
                current_ji = [x for x in sel_order["忌神"].split("、") if x] if sel_order["忌神"] else []
                edit_xi = c_e3.multiselect("修改喜神", wuxing_opts, default=current_xi)
                edit_ji = c_e4.multiselect("修改忌神", wuxing_opts, default=current_ji)

                if st.form_submit_button("💾 儲存修改"):
                    orders_df.loc[sel_idx, "總售價"] = str(edit_price)
                    orders_df.loc[sel_idx, "備註"] = str(edit_note)
                    orders_df.loc[sel_idx, "喜神"] = "、".join(edit_xi)
                    orders_df.loc[sel_idx, "忌神"] = "、".join(edit_ji)
                    save_orders(orders_df)
                    st.success("✅ 訂單已更新！")
                    time.sleep(1)
                    st.rerun()

            st.divider()

            st.subheader("📌 變更狀態")
            current_status = sel_order["狀態"]

            if current_status == "待確認":
                col_a, col_b = st.columns(2)
                if col_a.button("✅ 確認訂單", type="primary", use_container_width=True):
                    orders_df.loc[sel_idx, "狀態"] = "已確認"
                    save_orders(orders_df)
                    st.success(f"✅ 訂單 {order_id} 已確認！")
                    time.sleep(1.5)
                    st.rerun()
                if col_b.button("❌ 取消訂單", use_container_width=True):
                    orders_df.loc[sel_idx, "狀態"] = "已取消"
                    save_orders(orders_df)
                    st.warning(f"訂單 {order_id} 已取消。")
                    time.sleep(1.5)
                    st.rerun()

            elif current_status == "已確認":
                col_a, col_b = st.columns(2)
                if col_a.button("📦 標記為已出貨", type="primary", use_container_width=True):
                    orders_df.loc[sel_idx, "狀態"] = "已出貨"
                    save_orders(orders_df)
                    st.success(f"✅ 訂單 {order_id} 已出貨！")
                    time.sleep(1.5)
                    st.rerun()
                if col_b.button("❌ 取消訂單", use_container_width=True):
                    orders_df.loc[sel_idx, "狀態"] = "已取消"
                    save_orders(orders_df)
                    st.warning(f"訂單 {order_id} 已取消。")
                    time.sleep(1.5)
                    st.rerun()

            elif current_status == "已出貨":
                if st.button("✅ 標記為已完成", type="primary", use_container_width=True):
                    orders_df.loc[sel_idx, "狀態"] = "已完成"
                    save_orders(orders_df)
                    st.success(f"🎉 訂單 {order_id} 已完成！")
                    time.sleep(1.5)
                    st.rerun()

# ==========================================
# § 7 訂單紀錄
# ==========================================
elif page == "📜 訂單紀錄":
    st.header("📜 訂單紀錄總覽")

    orders_df = load_orders()

    if orders_df.empty:
        st.info("目前沒有任何訂單。")
    else:
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
