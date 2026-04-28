import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import time

# ==========================================
# § 1 核心常數與雲端設定
# ==========================================
SHEET_ID = "1gf-pn034w0oZx8jWDUJvmIyHX_O7eHbiBb9diVSBX0Q"
KEY_FILE = "google_key.json"

ORDER_COLUMNS = [
    '訂單編號', '建立時間', '客戶名稱', '客戶電話', '商品種類',
    '手圍', '流年', '階段數', '喜神', '忌神',
    '總售價', '備註', '狀態', '建單人'
]

CUSTOMER_COLUMNS = [
    '客戶名稱', '客戶電話', '手圍', '喜神', '忌神',
    '流年2024', '流年2025', '流年2026'
]

STATUS_FLOW = ["待確認", "已確認", "已出貨", "已完成", "已取消"]
WUXING_OPTS = ["金", "木", "水", "火", "土"]
YEAR_OPTS = ["2024", "2025", "2026"]

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

def _load_sheet(tab_name, columns):
    try:
        client = get_gs_client()
        wb = client.open_by_key(SHEET_ID)
        try:
            ws = wb.worksheet(tab_name)
        except gspread.exceptions.WorksheetNotFound:
            ws = wb.add_worksheet(title=tab_name, rows="1000", cols="20")
            ws.update(range_name='A1', values=[columns])
            return pd.DataFrame(columns=columns)
        values = ws.get_all_values()
        if not values or len(values) < 2:
            return pd.DataFrame(columns=columns)
        headers = [str(h).strip().replace("﻿", "") for h in values[0]]
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
        st.error(f"讀取 {tab_name} 失敗: {e}")
        return pd.DataFrame(columns=columns)

def _save_sheet(tab_name, df):
    try:
        client = get_gs_client()
        wb = client.open_by_key(SHEET_ID)
        try:
            ws = wb.worksheet(tab_name)
        except gspread.exceptions.WorksheetNotFound:
            ws = wb.add_worksheet(title=tab_name, rows="1000", cols="20")
        df_to_save = df.fillna("").astype(str)
        values = [df_to_save.columns.tolist()] + df_to_save.values.tolist()
        ws.clear()
        ws.update(range_name='A1', values=values)
    except Exception as e:
        st.error(f"儲存 {tab_name} 失敗: {e}")

def load_orders():
    return _load_sheet("Orders", ORDER_COLUMNS)

def save_orders(df):
    _save_sheet("Orders", df)

def load_customers():
    return _load_sheet("Customers", CUSTOMER_COLUMNS)

def save_customers(df):
    _save_sheet("Customers", df)

def generate_order_id():
    return f"ORD-{datetime.now().strftime('%m%d%H%M%S')}"

def get_current_year_key():
    yr = datetime.now().year
    return f"流年{yr}" if f"流年{yr}" in CUSTOMER_COLUMNS else "流年2026"

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
        "📜 訂單紀錄",
        "👥 客戶管理",
    ])
    if st.button("🔄 刷新資料"):
        get_gs_client.clear()
        st.rerun()

# ==========================================
# § 4 建立訂單
# ==========================================
if page == "📝 建立訂單":
    st.header("📝 建立新訂單")

    customers_df = load_customers()
    customer_list = customers_df["客戶名稱"].tolist() if not customers_df.empty else []

    # ── 選擇客戶 ──
    st.subheader("👤 客戶選擇")
    use_existing = st.toggle("從現有客戶帶入資料", value=bool(customer_list))

    prefill = {}
    if use_existing and customer_list:
        sel_customer = st.selectbox("選擇客戶", ["── 請選擇 ──"] + customer_list)
        if sel_customer != "── 請選擇 ──":
            row = customers_df[customers_df["客戶名稱"] == sel_customer].iloc[0]
            prefill = row.to_dict()
            yr_key = get_current_year_key()
            with st.container(border=True):
                ci1, ci2, ci3 = st.columns(3)
                ci1.write(f"**手圍：** {prefill.get('手圍', '-')}")
                ci2.write(f"**喜神：** {prefill.get('喜神', '-')}")
                ci3.write(f"**忌神：** {prefill.get('忌神', '-')}")
                ci4, ci5 = st.columns(2)
                ci4.write(f"**電話：** {prefill.get('客戶電話', '-')}")
                ci5.write(f"**今年流年：** {prefill.get(yr_key, '-')}")

    st.divider()

    with st.form("create_order_form"):
        st.subheader("客戶資訊")
        c1, c2 = st.columns(2)
        default_name = prefill.get("客戶名稱", "")
        default_phone = prefill.get("客戶電話", "")
        customer_name = c1.text_input("客戶名稱 *", value=default_name)
        customer_phone = c2.text_input("客戶電話", value=default_phone)

        st.subheader("訂單資訊")
        c3, c4, c5 = st.columns(3)
        product_type = c3.selectbox("商品種類", ["客製", "公版"])
        order_creator = c4.selectbox("建單人", ["Imeng", "千畇"])
        total_price = c5.number_input("總售價 ($)（可之後再填）", min_value=0.0, value=0.0)

        st.subheader("手鍊資訊")
        b1, b2, b3 = st.columns(3)
        wrist_size = b1.text_input("手圍", value=prefill.get("手圍", ""))

        # 流年：從客戶資料帶入今年流年，也可手動選
        yr_key = get_current_year_key()
        default_liunnian = prefill.get(yr_key, "")
        liunnian_input = b2.text_input("流年", value=default_liunnian,
                                       help="例如：木、火（可填文字）")
        stage_num = b3.number_input("階段數", min_value=1, value=1, step=1,
                                    help="此客戶今年第幾次訂購")

        st.subheader("五行")
        default_xi = [x for x in prefill.get("喜神", "").split("、") if x in WUXING_OPTS] if prefill.get("喜神") else []
        default_ji = [x for x in prefill.get("忌神", "").split("、") if x in WUXING_OPTS] if prefill.get("忌神") else []
        c6, c7 = st.columns(2)
        xi_shen = c6.multiselect("喜神", WUXING_OPTS, default=default_xi)
        ji_shen = c7.multiselect("忌神", WUXING_OPTS, default=default_ji)

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
                    "手圍": wrist_size,
                    "流年": liunnian_input,
                    "階段數": str(int(stage_num)),
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

        st.divider()
        st.subheader("✏️ 修改訂單")

        all_ids = orders_df["訂單編號"].tolist()
        sel_edit_id = st.selectbox("選擇要修改的訂單", all_ids[::-1], key="list_edit_sel")
        edit_idx = orders_df[orders_df["訂單編號"] == sel_edit_id].index[0]
        edit_row = orders_df.loc[edit_idx]

        with st.container(border=True):
            st.write(f"**客戶：** {edit_row['客戶名稱']} | **狀態：** {edit_row['狀態']} | **建立時間：** {edit_row['建立時間']}")

        with st.form("list_edit_form"):
            c1, c2 = st.columns(2)
            e_name = c1.text_input("客戶名稱", value=edit_row["客戶名稱"])
            e_phone = c2.text_input("客戶電話", value=edit_row["客戶電話"])

            c3, c4, c5 = st.columns(3)
            e_type = c3.selectbox("商品種類", ["客製", "公版"],
                index=["客製", "公版"].index(edit_row["商品種類"]) if edit_row["商品種類"] in ["客製", "公版"] else 0)
            e_creator = c4.selectbox("建單人", ["Imeng", "千畇"],
                index=["Imeng", "千畇"].index(edit_row["建單人"]) if edit_row["建單人"] in ["Imeng", "千畇"] else 0)
            e_price = c5.number_input("總售價 ($)", value=float(edit_row["總售價"]) if edit_row["總售價"] else 0.0)

            b1, b2, b3 = st.columns(3)
            e_wrist = b1.text_input("手圍", value=edit_row.get("手圍", ""))
            e_liunnian = b2.text_input("流年", value=edit_row.get("流年", ""))
            e_stage = b3.number_input("階段數", min_value=1,
                value=int(edit_row["階段數"]) if str(edit_row.get("階段數", "")).isdigit() else 1)

            c6, c7 = st.columns(2)
            current_xi = [x for x in edit_row["喜神"].split("、") if x in WUXING_OPTS] if edit_row["喜神"] else []
            current_ji = [x for x in edit_row["忌神"].split("、") if x in WUXING_OPTS] if edit_row["忌神"] else []
            e_xi = c6.multiselect("喜神", WUXING_OPTS, default=current_xi)
            e_ji = c7.multiselect("忌神", WUXING_OPTS, default=current_ji)

            e_status = st.selectbox("狀態", STATUS_FLOW,
                index=STATUS_FLOW.index(edit_row["狀態"]) if edit_row["狀態"] in STATUS_FLOW else 0)
            e_note = st.text_area("備註", value=edit_row["備註"])

            if st.form_submit_button("💾 儲存修改", use_container_width=True):
                orders_df.loc[edit_idx, "客戶名稱"] = str(e_name)
                orders_df.loc[edit_idx, "客戶電話"] = str(e_phone)
                orders_df.loc[edit_idx, "商品種類"] = str(e_type)
                orders_df.loc[edit_idx, "建單人"] = str(e_creator)
                orders_df.loc[edit_idx, "總售價"] = str(e_price)
                orders_df.loc[edit_idx, "手圍"] = str(e_wrist)
                orders_df.loc[edit_idx, "流年"] = str(e_liunnian)
                orders_df.loc[edit_idx, "階段數"] = str(int(e_stage))
                orders_df.loc[edit_idx, "喜神"] = "、".join(e_xi)
                orders_df.loc[edit_idx, "忌神"] = "、".join(e_ji)
                orders_df.loc[edit_idx, "狀態"] = str(e_status)
                orders_df.loc[edit_idx, "備註"] = str(e_note)
                save_orders(orders_df)
                st.success(f"✅ 訂單 {sel_edit_id} 已更新！")
                time.sleep(1)
                st.rerun()

# ==========================================
# § 6 訂單管理（狀態變更）
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
                lambda r: f"[{r['狀態']}] {r['訂單編號']} — {r['客戶名稱']} | {r['商品種類']} | 第{r.get('階段數','?')}階 | ${r['總售價']}", axis=1
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
                st.write(
                    f"**電話：** {sel_order['客戶電話']} | "
                    f"**商品種類：** {sel_order['商品種類']} | "
                    f"**手圍：** {sel_order.get('手圍','-')} | "
                    f"**流年：** {sel_order.get('流年','-')} | "
                    f"**階段數：** {sel_order.get('階段數','-')} | "
                    f"**建單人：** {sel_order['建單人']} | "
                    f"**建立時間：** {sel_order['建立時間']}"
                )
                st.write(
                    f"**喜神：** {sel_order['喜神'] if sel_order['喜神'] else '-'} | "
                    f"**忌神：** {sel_order['忌神'] if sel_order['忌神'] else '-'}"
                )
                if sel_order["備註"]:
                    st.write(f"**備註：** {sel_order['備註']}")

            st.divider()
            st.subheader("✏️ 修改訂單")
            with st.form("edit_order_form"):
                c_e1, c_e2, c_e3 = st.columns(3)
                edit_price = c_e1.number_input("修改總售價 ($)", value=float(sel_order["總售價"]) if sel_order["總售價"] else 0.0)
                edit_wrist = c_e2.text_input("手圍", value=sel_order.get("手圍", ""))
                edit_liunnian = c_e3.text_input("流年", value=sel_order.get("流年", ""))
                edit_note = st.text_input("備註", value=sel_order["備註"])

                c_e4, c_e5 = st.columns(2)
                current_xi = [x for x in sel_order["喜神"].split("、") if x in WUXING_OPTS] if sel_order["喜神"] else []
                current_ji = [x for x in sel_order["忌神"].split("、") if x in WUXING_OPTS] if sel_order["忌神"] else []
                edit_xi = c_e4.multiselect("修改喜神", WUXING_OPTS, default=current_xi)
                edit_ji = c_e5.multiselect("修改忌神", WUXING_OPTS, default=current_ji)

                if st.form_submit_button("💾 儲存修改"):
                    orders_df.loc[sel_idx, "總售價"] = str(edit_price)
                    orders_df.loc[sel_idx, "手圍"] = str(edit_wrist)
                    orders_df.loc[sel_idx, "流年"] = str(edit_liunnian)
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
                    time.sleep(1.5); st.rerun()
                if col_b.button("❌ 取消訂單", use_container_width=True):
                    orders_df.loc[sel_idx, "狀態"] = "已取消"
                    save_orders(orders_df)
                    st.warning(f"訂單 {order_id} 已取消。")
                    time.sleep(1.5); st.rerun()

            elif current_status == "已確認":
                col_a, col_b = st.columns(2)
                if col_a.button("📦 標記為已出貨", type="primary", use_container_width=True):
                    orders_df.loc[sel_idx, "狀態"] = "已出貨"
                    save_orders(orders_df)
                    st.success(f"✅ 訂單 {order_id} 已出貨！")
                    time.sleep(1.5); st.rerun()
                if col_b.button("❌ 取消訂單", use_container_width=True):
                    orders_df.loc[sel_idx, "狀態"] = "已取消"
                    save_orders(orders_df)
                    st.warning(f"訂單 {order_id} 已取消。")
                    time.sleep(1.5); st.rerun()

            elif current_status == "已出貨":
                if st.button("✅ 標記為已完成", type="primary", use_container_width=True):
                    orders_df.loc[sel_idx, "狀態"] = "已完成"
                    save_orders(orders_df)
                    st.success(f"🎉 訂單 {order_id} 已完成！")
                    time.sleep(1.5); st.rerun()

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
            total_revenue = orders_df[orders_df["狀態"] == "已完成"]["總售價"].apply(
                lambda x: float(x) if x else 0).sum()
            c4.metric("已完成總營收", f"${total_revenue:,.2f}")
        except:
            c4.metric("已完成總營收", "$0")

        st.divider()
        st.dataframe(orders_df.iloc[::-1], use_container_width=True)

# ==========================================
# § 8 客戶管理
# ==========================================
elif page == "👥 客戶管理":
    st.header("👥 客戶資料管理")
    customers_df = load_customers()

    tab1, tab2 = st.tabs(["➕ 新增客戶", "✏️ 查看 / 編輯客戶"])

    # ── 新增客戶 ──
    with tab1:
        st.subheader("新增客戶基本資料")
        with st.form("add_customer_form"):
            a1, a2 = st.columns(2)
            new_name = a1.text_input("客戶名稱 *")
            new_phone = a2.text_input("客戶電話")

            a3 = st.text_input("手圍")

            a4, a5 = st.columns(2)
            new_xi = a4.multiselect("喜神", WUXING_OPTS)
            new_ji = a5.multiselect("忌神", WUXING_OPTS)

            st.markdown("**各年流年**")
            y1, y2, y3 = st.columns(3)
            ln2024 = y1.text_input("流年 2024")
            ln2025 = y2.text_input("流年 2025")
            ln2026 = y3.text_input("流年 2026")

            if st.form_submit_button("✅ 新增客戶", use_container_width=True):
                if not new_name:
                    st.error("❌ 請填寫客戶名稱")
                elif new_name in customers_df["客戶名稱"].values:
                    st.error(f"❌ 客戶「{new_name}」已存在，請至「查看 / 編輯客戶」修改")
                else:
                    new_cust = {
                        "客戶名稱": new_name,
                        "客戶電話": new_phone,
                        "手圍": a3,
                        "喜神": "、".join(new_xi),
                        "忌神": "、".join(new_ji),
                        "流年2024": ln2024,
                        "流年2025": ln2025,
                        "流年2026": ln2026,
                    }
                    customers_df = pd.concat([customers_df, pd.DataFrame([new_cust])], ignore_index=True)
                    save_customers(customers_df)
                    st.success(f"✅ 客戶「{new_name}」已新增！")
                    time.sleep(1.5)
                    st.rerun()

    # ── 查看 / 編輯客戶 ──
    with tab2:
        if customers_df.empty:
            st.info("尚未建立任何客戶資料。")
        else:
            # 搜尋
            search = st.text_input("搜尋客戶名稱")
            view_df = customers_df.copy()
            if search:
                view_df = view_df[view_df["客戶名稱"].str.contains(search, case=False, na=False)]

            st.dataframe(view_df, use_container_width=True)
            st.caption(f"共 {len(customers_df)} 位客戶")

            st.divider()
            st.subheader("✏️ 編輯客戶資料")

            cust_names = customers_df["客戶名稱"].tolist()
            sel_cust = st.selectbox("選擇客戶", cust_names)
            cust_idx = customers_df[customers_df["客戶名稱"] == sel_cust].index[0]
            cust_row = customers_df.loc[cust_idx]

            with st.form("edit_customer_form"):
                ec1, ec2 = st.columns(2)
                ec_name = ec1.text_input("客戶名稱", value=cust_row["客戶名稱"])
                ec_phone = ec2.text_input("客戶電話", value=cust_row["客戶電話"])
                ec_wrist = st.text_input("手圍", value=cust_row["手圍"])

                ec3, ec4 = st.columns(2)
                cur_xi = [x for x in cust_row["喜神"].split("、") if x in WUXING_OPTS] if cust_row["喜神"] else []
                cur_ji = [x for x in cust_row["忌神"].split("、") if x in WUXING_OPTS] if cust_row["忌神"] else []
                ec_xi = ec3.multiselect("喜神", WUXING_OPTS, default=cur_xi)
                ec_ji = ec4.multiselect("忌神", WUXING_OPTS, default=cur_ji)

                st.markdown("**各年流年**")
                ey1, ey2, ey3 = st.columns(3)
                ec_ln2024 = ey1.text_input("流年 2024", value=cust_row["流年2024"])
                ec_ln2025 = ey2.text_input("流年 2025", value=cust_row["流年2025"])
                ec_ln2026 = ey3.text_input("流年 2026", value=cust_row["流年2026"])

                col_save, col_del = st.columns(2)
                save_btn = col_save.form_submit_button("💾 儲存修改", use_container_width=True)
                del_btn  = col_del.form_submit_button("🗑️ 刪除此客戶", use_container_width=True)

                if save_btn:
                    customers_df.loc[cust_idx, "客戶名稱"] = str(ec_name)
                    customers_df.loc[cust_idx, "客戶電話"] = str(ec_phone)
                    customers_df.loc[cust_idx, "手圍"] = str(ec_wrist)
                    customers_df.loc[cust_idx, "喜神"] = "、".join(ec_xi)
                    customers_df.loc[cust_idx, "忌神"] = "、".join(ec_ji)
                    customers_df.loc[cust_idx, "流年2024"] = str(ec_ln2024)
                    customers_df.loc[cust_idx, "流年2025"] = str(ec_ln2025)
                    customers_df.loc[cust_idx, "流年2026"] = str(ec_ln2026)
                    save_customers(customers_df)
                    st.success(f"✅ 客戶「{sel_cust}」資料已更新！")
                    time.sleep(1)
                    st.rerun()

                if del_btn:
                    customers_df = customers_df.drop(index=cust_idx).reset_index(drop=True)
                    save_customers(customers_df)
                    st.warning(f"客戶「{sel_cust}」已刪除。")
                    time.sleep(1)
                    st.rerun()
