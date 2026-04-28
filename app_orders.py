import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, date
import time

# ==========================================
# § 1 核心常數
# ==========================================
SHEET_ID = "1gf-pn034w0oZx8jWDUJvmIyHX_O7eHbiBb9diVSBX0Q"
KEY_FILE  = "google_key.json"

ORDER_COLUMNS = [
    '訂單編號', '建立時間', '客戶名稱', '客戶電話', '商品種類',
    '手圍', '生日', '喜神', '忌神',
    '總售價', '備註', '狀態', '建單人'
]

CUSTOMER_COLUMNS = [
    '客戶名稱', '客戶電話', '手圍', '喜神', '忌神', '生日'
]

STATUS_FLOW  = ["待確認", "已確認", "已出貨", "已完成", "已取消"]
WUXING_OPTS  = ["金", "木", "水", "火", "土"]

# ==========================================
# § 2 數字學計算工具
# ==========================================
def _digit_sum(n: int) -> int:
    """單步數字相加 e.g. 19 → 10"""
    return sum(int(d) for d in str(n))

def _reduce_chain(n: int) -> list[int]:
    """持續縮減到個位，回傳過程列表 e.g. [19, 10, 1]"""
    chain = [n]
    while n >= 10:
        n = _digit_sum(n)
        chain.append(n)
    return chain

def calc_liunian(year: int, birth_month: int, birth_day: int) -> str:
    """
    流年 = 把 year / birth_month / birth_day 所有位數相加後縮減
    e.g. 2025/5/5 → 2+0+2+5+5+5=19 → 10 → 1  顯示為 "19/10/1"
    """
    digits_str = str(year) + str(birth_month) + str(birth_day)
    total = sum(int(d) for d in digits_str)
    chain = _reduce_chain(total)
    return "/".join(str(x) for x in chain)

def calc_jieduan(birth_year: int, birth_month: int) -> str:
    """
    階段數 = 把出生年 / 生日月 所有位數相加後縮減（個人固定數）
    e.g. 1979/5 → 1+9+7+9+5=31 → 4  顯示為 "31/4"
    """
    digits_str = str(birth_year) + str(birth_month)
    total = sum(int(d) for d in digits_str)
    chain = _reduce_chain(total)
    return "/".join(str(x) for x in chain)

def personal_year_range(birth_month: int, birth_day: int, today: date = None) -> list[int]:
    """
    依據生日是否已過，決定要顯示的三個年份
    ・未過生日 → 個人年 = 本曆年-1  → [個人年-1, 個人年, 個人年+1]
    ・已過生日 → 個人年 = 本曆年    → [個人年-1, 個人年, 個人年+1]
    例：今天 2026-04-28
      生日 5/5 未到 → 個人年=2025 → [2024,2025,2026]
      生日 3/1 已過 → 個人年=2026 → [2025,2026,2027]
    """
    if today is None:
        today = datetime.now().date()
    cal_year = today.year
    birthday_passed = (today.month, today.day) >= (birth_month, birth_day)
    personal_year = cal_year if birthday_passed else cal_year - 1
    return [personal_year - 1, personal_year, personal_year + 1]

def parse_birthday(bday_str: str):
    """
    解析生日字串（支援 YYYY/MM/DD 或 YYYY-MM-DD）
    回傳 (birth_year, birth_month, birth_day) 或 None
    """
    if not bday_str:
        return None
    for fmt in ("%Y/%m/%d", "%Y-%m-%d"):
        try:
            d = datetime.strptime(bday_str.strip(), fmt)
            return d.year, d.month, d.day
        except ValueError:
            pass
    return None

def render_numerology_table(bday_str: str):
    """
    根據生日字串渲染流年 + 階段數三年對照表
    回傳是否成功
    """
    parsed = parse_birthday(bday_str)
    if not parsed:
        return False
    by, bm, bd = parsed
    years = personal_year_range(bm, bd)
    labels = ["去年", "今年", "明年"]
    jieduan = calc_jieduan(by, bm)

    rows = []
    for yr, lbl in zip(years, labels):
        liunian = calc_liunian(yr, bm, bd)
        rows.append({
            "年份": f"{yr}（{lbl}）",
            "流年": liunian,
            "流年最終數": liunian.split("/")[-1],
            "階段數": jieduan,
            "階段最終數": jieduan.split("/")[-1],
        })
    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)
    return True

# ==========================================
# § 3 Google Sheets 連線
# ==========================================
@st.cache_resource
def get_gs_client():
    scope = ["https://spreadsheets.google.com/feeds",
             "https://www.googleapis.com/auth/drive"]
    try:
        if "gcp_service_account" in st.secrets:
            creds = ServiceAccountCredentials.from_json_keyfile_dict(
                dict(st.secrets["gcp_service_account"]), scope)
        else:
            creds = ServiceAccountCredentials.from_json_keyfile_name(KEY_FILE, scope)
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"❌ Google 授權失敗：{e}")
        st.stop()

def _load_sheet(tab: str, columns: list) -> pd.DataFrame:
    try:
        wb = get_gs_client().open_by_key(SHEET_ID)
        try:
            ws = wb.worksheet(tab)
        except gspread.exceptions.WorksheetNotFound:
            ws = wb.add_worksheet(title=tab, rows="1000", cols="20")
            ws.update(range_name='A1', values=[columns])
            return pd.DataFrame(columns=columns)
        values = ws.get_all_values()
        if not values or len(values) < 2:
            return pd.DataFrame(columns=columns)
        headers = [str(h).strip().replace("﻿", "") for h in values[0]]
        final_h = []
        for i, h in enumerate(headers):
            if not h:          final_h.append(f"未命名_{i}")
            elif h in final_h: final_h.append(f"{h}_{i}")
            else:              final_h.append(h)
        df = pd.DataFrame(values[1:], columns=final_h)
        df = df[df.astype(str).apply(lambda x: x.str.strip() != "").any(axis=1)]
        for col in columns:
            if col not in df.columns:
                df[col] = ""
        return df[columns].copy()
    except Exception as e:
        st.error(f"讀取 {tab} 失敗: {e}")
        return pd.DataFrame(columns=columns)

def _save_sheet(tab: str, df: pd.DataFrame):
    try:
        wb = get_gs_client().open_by_key(SHEET_ID)
        try:   ws = wb.worksheet(tab)
        except gspread.exceptions.WorksheetNotFound:
            ws = wb.add_worksheet(title=tab, rows="1000", cols="20")
        data = df.fillna("").astype(str)
        ws.clear()
        ws.update(range_name='A1', values=[data.columns.tolist()] + data.values.tolist())
    except Exception as e:
        st.error(f"儲存 {tab} 失敗: {e}")

def load_orders():    return _load_sheet("Orders",    ORDER_COLUMNS)
def save_orders(df):  _save_sheet("Orders", df)
def load_customers(): return _load_sheet("Customers", CUSTOMER_COLUMNS)
def save_customers(df): _save_sheet("Customers", df)

def generate_order_id():
    return f"ORD-{datetime.now().strftime('%m%d%H%M%S')}"

# ==========================================
# § 4 系統初始化
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
# § 5 建立訂單
# ==========================================
if page == "📝 建立訂單":
    st.header("📝 建立新訂單")

    customers_df = load_customers()
    customer_list = customers_df["客戶名稱"].tolist() if not customers_df.empty else []

    # ── 選擇舊客戶 ──
    st.subheader("👤 客戶選擇")
    use_existing = st.toggle("從現有客戶帶入資料", value=bool(customer_list))

    prefill: dict = {}
    if use_existing and customer_list:
        sel_customer = st.selectbox("選擇客戶", ["── 請選擇 ──"] + customer_list)
        if sel_customer != "── 請選擇 ──":
            prefill = customers_df[customers_df["客戶名稱"] == sel_customer].iloc[0].to_dict()

            # 顯示客戶數字學對照表
            bday_str = prefill.get("生日", "")
            if bday_str:
                st.markdown("#### 📊 流年 × 階段數 對照（自動計算）")
                render_numerology_table(bday_str)
            else:
                with st.container(border=True):
                    ci1, ci2, ci3, ci4 = st.columns(4)
                    ci1.write(f"**電話：** {prefill.get('客戶電話','-')}")
                    ci2.write(f"**手圍：** {prefill.get('手圍','-')}")
                    ci3.write(f"**喜神：** {prefill.get('喜神','-')}")
                    ci4.write(f"**忌神：** {prefill.get('忌神','-')}")

    st.divider()

    with st.form("create_order_form"):
        st.subheader("客戶資訊")
        c1, c2 = st.columns(2)
        customer_name  = c1.text_input("客戶名稱 *", value=prefill.get("客戶名稱", ""))
        customer_phone = c2.text_input("客戶電話",   value=prefill.get("客戶電話", ""))

        st.subheader("訂單資訊")
        c3, c4, c5 = st.columns(3)
        product_type  = c3.selectbox("商品種類", ["客製", "公版"])
        order_creator = c4.selectbox("建單人",   ["Imeng", "千畇"])
        total_price   = c5.number_input("總售價 ($)（可之後再填）", min_value=0.0, value=0.0)

        st.subheader("手鍊資訊")
        b1, b2 = st.columns(2)
        wrist_size = b1.text_input("手圍", value=prefill.get("手圍", ""))
        birthday   = b2.text_input("生日（YYYY/MM/DD）", value=prefill.get("生日", ""),
                                   placeholder="例：1979/05/05")

        st.subheader("五行")
        default_xi = [x for x in prefill.get("喜神","").split("、") if x in WUXING_OPTS]
        default_ji = [x for x in prefill.get("忌神","").split("、") if x in WUXING_OPTS]
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
                    "訂單編號":  order_id,
                    "建立時間":  datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "客戶名稱":  customer_name,
                    "客戶電話":  customer_phone,
                    "商品種類":  product_type,
                    "手圍":     wrist_size,
                    "生日":     birthday,
                    "喜神":     "、".join(xi_shen),
                    "忌神":     "、".join(ji_shen),
                    "總售價":   str(total_price),
                    "備註":     order_note,
                    "狀態":     "待確認",
                    "建單人":   order_creator,
                }
                orders_df = pd.concat([orders_df, pd.DataFrame([new_order])], ignore_index=True)
                save_orders(orders_df)
                st.success(f"✅ 訂單 {order_id} 已建立！")
                time.sleep(1.5)
                st.rerun()

# ==========================================
# § 6 訂單列表
# ==========================================
elif page == "📋 訂單列表":
    st.header("📋 所有訂單列表")
    orders_df = load_orders()

    if orders_df.empty:
        st.info("目前沒有任何訂單。")
    else:
        c1, c2 = st.columns(2)
        status_filter   = c1.selectbox("篩選狀態", ["全部"] + STATUS_FLOW)
        search_customer = c2.text_input("搜尋客戶名稱")

        disp = orders_df.copy()
        if status_filter != "全部":
            disp = disp[disp["狀態"] == status_filter]
        if search_customer:
            disp = disp[disp["客戶名稱"].str.contains(search_customer, case=False, na=False)]

        if disp.empty:
            st.info("篩選後沒有訂單。")
        else:
            st.dataframe(disp.iloc[::-1], use_container_width=True)
            st.caption(f"共 {len(disp)} 筆訂單")

        st.divider()
        st.subheader("✏️ 修改訂單")

        all_ids     = orders_df["訂單編號"].tolist()
        sel_edit_id = st.selectbox("選擇要修改的訂單", all_ids[::-1], key="list_edit_sel")
        edit_idx    = orders_df[orders_df["訂單編號"] == sel_edit_id].index[0]
        edit_row    = orders_df.loc[edit_idx]

        with st.container(border=True):
            st.write(f"**客戶：** {edit_row['客戶名稱']} | **狀態：** {edit_row['狀態']} | **建立時間：** {edit_row['建立時間']}")
            if edit_row.get("生日"):
                st.markdown("**📊 流年 × 階段數 對照**")
                render_numerology_table(edit_row["生日"])

        with st.form("list_edit_form"):
            c1, c2 = st.columns(2)
            e_name  = c1.text_input("客戶名稱",        value=edit_row["客戶名稱"])
            e_phone = c2.text_input("客戶電話",        value=edit_row["客戶電話"])
            b1, b2 = st.columns(2)
            e_wrist = b1.text_input("手圍",            value=edit_row.get("手圍",""))
            e_bday  = b2.text_input("生日（YYYY/MM/DD）", value=edit_row.get("生日",""))

            c3, c4, c5 = st.columns(3)
            e_type    = c3.selectbox("商品種類", ["客製","公版"],
                index=["客製","公版"].index(edit_row["商品種類"]) if edit_row["商品種類"] in ["客製","公版"] else 0)
            e_creator = c4.selectbox("建單人", ["Imeng","千畇"],
                index=["Imeng","千畇"].index(edit_row["建單人"]) if edit_row["建單人"] in ["Imeng","千畇"] else 0)
            e_price   = c5.number_input("總售價 ($)",
                value=float(edit_row["總售價"]) if edit_row["總售價"] else 0.0)

            c6, c7 = st.columns(2)
            cur_xi = [x for x in edit_row["喜神"].split("、") if x in WUXING_OPTS] if edit_row["喜神"] else []
            cur_ji = [x for x in edit_row["忌神"].split("、") if x in WUXING_OPTS] if edit_row["忌神"] else []
            e_xi = c6.multiselect("喜神", WUXING_OPTS, default=cur_xi)
            e_ji = c7.multiselect("忌神", WUXING_OPTS, default=cur_ji)

            e_status = st.selectbox("狀態", STATUS_FLOW,
                index=STATUS_FLOW.index(edit_row["狀態"]) if edit_row["狀態"] in STATUS_FLOW else 0)
            e_note = st.text_area("備註", value=edit_row["備註"])

            if st.form_submit_button("💾 儲存修改", use_container_width=True):
                orders_df.loc[edit_idx, "客戶名稱"] = str(e_name)
                orders_df.loc[edit_idx, "客戶電話"] = str(e_phone)
                orders_df.loc[edit_idx, "手圍"]    = str(e_wrist)
                orders_df.loc[edit_idx, "生日"]    = str(e_bday)
                orders_df.loc[edit_idx, "商品種類"] = str(e_type)
                orders_df.loc[edit_idx, "建單人"]  = str(e_creator)
                orders_df.loc[edit_idx, "總售價"]  = str(e_price)
                orders_df.loc[edit_idx, "喜神"]    = "、".join(e_xi)
                orders_df.loc[edit_idx, "忌神"]    = "、".join(e_ji)
                orders_df.loc[edit_idx, "狀態"]    = str(e_status)
                orders_df.loc[edit_idx, "備註"]    = str(e_note)
                save_orders(orders_df)
                st.success(f"✅ 訂單 {sel_edit_id} 已更新！")
                time.sleep(1)
                st.rerun()

# ==========================================
# § 7 訂單管理（狀態變更）
# ==========================================
elif page == "🔄 訂單管理":
    st.header("🔄 訂單管理")
    orders_df = load_orders()

    if orders_df.empty:
        st.info("目前沒有任何訂單。")
    else:
        active = orders_df[~orders_df["狀態"].isin(["已完成","已取消"])].copy()
        if active.empty:
            st.success("🎉 所有訂單都已處理完成！")
        else:
            active["display"] = active.apply(
                lambda r: f"[{r['狀態']}] {r['訂單編號']} — {r['客戶名稱']} | {r['商品種類']} | ${r['總售價']}", axis=1)
            sel_disp  = st.selectbox("選擇要管理的訂單", active["display"].tolist()[::-1])
            sel_idx   = active[active["display"] == sel_disp].index[0]
            sel_order = orders_df.loc[sel_idx]
            order_id  = sel_order["訂單編號"]

            with st.container(border=True):
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("訂單編號", order_id)
                c2.metric("客戶",    sel_order["客戶名稱"])
                c3.metric("總售價",  f"${float(sel_order['總售價']):,.2f}" if sel_order["總售價"] else "$0")
                c4.metric("目前狀態", sel_order["狀態"])
                st.write(
                    f"**電話：** {sel_order['客戶電話']} | "
                    f"**商品種類：** {sel_order['商品種類']} | "
                    f"**手圍：** {sel_order.get('手圍','-')} | "
                    f"**建單人：** {sel_order['建單人']} | "
                    f"**建立時間：** {sel_order['建立時間']}")
                st.write(
                    f"**喜神：** {sel_order['喜神'] or '-'} | "
                    f"**忌神：** {sel_order['忌神'] or '-'}")
                if sel_order["備註"]:
                    st.write(f"**備註：** {sel_order['備註']}")
                if sel_order.get("生日"):
                    st.markdown("**📊 流年 × 階段數 對照**")
                    render_numerology_table(sel_order["生日"])

            st.divider()
            st.subheader("✏️ 修改訂單")
            with st.form("edit_order_form"):
                ce1, ce2, ce3 = st.columns(3)
                edit_price = ce1.number_input("修改總售價 ($)",
                    value=float(sel_order["總售價"]) if sel_order["總售價"] else 0.0)
                edit_wrist = ce2.text_input("手圍", value=sel_order.get("手圍",""))
                edit_bday  = ce3.text_input("生日（YYYY/MM/DD）", value=sel_order.get("生日",""))
                edit_note  = st.text_input("備註", value=sel_order["備註"])

                ce4, ce5 = st.columns(2)
                cx = [x for x in sel_order["喜神"].split("、") if x in WUXING_OPTS] if sel_order["喜神"] else []
                cj = [x for x in sel_order["忌神"].split("、") if x in WUXING_OPTS] if sel_order["忌神"] else []
                edit_xi = ce4.multiselect("喜神", WUXING_OPTS, default=cx)
                edit_ji = ce5.multiselect("忌神", WUXING_OPTS, default=cj)

                if st.form_submit_button("💾 儲存修改"):
                    orders_df.loc[sel_idx, "總售價"] = str(edit_price)
                    orders_df.loc[sel_idx, "手圍"]   = str(edit_wrist)
                    orders_df.loc[sel_idx, "生日"]   = str(edit_bday)
                    orders_df.loc[sel_idx, "備註"]   = str(edit_note)
                    orders_df.loc[sel_idx, "喜神"]   = "、".join(edit_xi)
                    orders_df.loc[sel_idx, "忌神"]   = "、".join(edit_ji)
                    save_orders(orders_df)
                    st.success("✅ 訂單已更新！")
                    time.sleep(1); st.rerun()

            st.divider()
            st.subheader("📌 變更狀態")
            cur_status = sel_order["狀態"]

            if cur_status == "待確認":
                ca, cb = st.columns(2)
                if ca.button("✅ 確認訂單", type="primary", use_container_width=True):
                    orders_df.loc[sel_idx,"狀態"] = "已確認"
                    save_orders(orders_df); st.success(f"✅ {order_id} 已確認！")
                    time.sleep(1.5); st.rerun()
                if cb.button("❌ 取消訂單", use_container_width=True):
                    orders_df.loc[sel_idx,"狀態"] = "已取消"
                    save_orders(orders_df); st.warning(f"{order_id} 已取消。")
                    time.sleep(1.5); st.rerun()

            elif cur_status == "已確認":
                ca, cb = st.columns(2)
                if ca.button("📦 標記為已出貨", type="primary", use_container_width=True):
                    orders_df.loc[sel_idx,"狀態"] = "已出貨"
                    save_orders(orders_df); st.success(f"✅ {order_id} 已出貨！")
                    time.sleep(1.5); st.rerun()
                if cb.button("❌ 取消訂單", use_container_width=True):
                    orders_df.loc[sel_idx,"狀態"] = "已取消"
                    save_orders(orders_df); st.warning(f"{order_id} 已取消。")
                    time.sleep(1.5); st.rerun()

            elif cur_status == "已出貨":
                if st.button("✅ 標記為已完成", type="primary", use_container_width=True):
                    orders_df.loc[sel_idx,"狀態"] = "已完成"
                    save_orders(orders_df); st.success(f"🎉 {order_id} 已完成！")
                    time.sleep(1.5); st.rerun()

# ==========================================
# § 8 訂單紀錄
# ==========================================
elif page == "📜 訂單紀錄":
    st.header("📜 訂單紀錄總覽")
    orders_df = load_orders()

    if orders_df.empty:
        st.info("目前沒有任何訂單。")
    else:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("總訂單數", f"{len(orders_df)} 筆")
        c2.metric("已完成",   f"{len(orders_df[orders_df['狀態']=='已完成'])} 筆")
        c3.metric("進行中",   f"{len(orders_df[orders_df['狀態'].isin(['待確認','已確認','已出貨'])])} 筆")
        try:
            rev = orders_df[orders_df["狀態"]=="已完成"]["總售價"].apply(
                lambda x: float(x) if x else 0).sum()
            c4.metric("已完成總營收", f"${rev:,.2f}")
        except:
            c4.metric("已完成總營收", "$0")

        st.divider()
        st.dataframe(orders_df.iloc[::-1], use_container_width=True)

# ==========================================
# § 9 客戶管理
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
            new_name  = a1.text_input("客戶名稱 *")
            new_phone = a2.text_input("客戶電話")

            a3, a4 = st.columns(2)
            new_wrist = a3.text_input("手圍")
            new_bday  = a4.text_input("生日（YYYY/MM/DD）", placeholder="例：1979/05/05")

            a5, a6 = st.columns(2)
            new_xi = a5.multiselect("喜神", WUXING_OPTS)
            new_ji = a6.multiselect("忌神", WUXING_OPTS)

            if st.form_submit_button("✅ 新增客戶", use_container_width=True):
                if not new_name:
                    st.error("❌ 請填寫客戶名稱")
                elif new_name in customers_df["客戶名稱"].values:
                    st.error(f"❌ 客戶「{new_name}」已存在")
                else:
                    row = {
                        "客戶名稱": new_name,
                        "客戶電話": new_phone,
                        "手圍":    new_wrist,
                        "喜神":    "、".join(new_xi),
                        "忌神":    "、".join(new_ji),
                        "生日":    new_bday,
                    }
                    customers_df = pd.concat([customers_df, pd.DataFrame([row])], ignore_index=True)
                    save_customers(customers_df)
                    st.success(f"✅ 客戶「{new_name}」已新增！")
                    time.sleep(1.5); st.rerun()

        # 即時預覽計算（表單外）
        st.divider()
        st.subheader("🔢 數字學預覽（輸入生日後顯示）")
        preview_bday = st.text_input("生日預覽（YYYY/MM/DD）", key="preview_bday",
                                     placeholder="例：1979/05/05")
        if preview_bday:
            parsed = parse_birthday(preview_bday)
            if parsed:
                by, bm, bd = parsed
                years  = personal_year_range(bm, bd)
                labels = ["去年", "今年", "明年"]
                rows = []
                for yr, lbl in zip(years, labels):
                    ln = calc_liunian(yr, bm, bd)
                    jd = calc_jieduan(by, bm)
                    rows.append({
                        "年份": f"{yr}（{lbl}）",
                        "流年計算過程": f"{yr}{bm}{bd} → {ln}",
                        "流年": ln.split('/')[-1],
                        "階段數計算過程": f"{by}{bm} → {jd}",
                        "階段數": jd.split('/')[-1],
                    })
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
            else:
                st.warning("⚠️ 格式不正確，請使用 YYYY/MM/DD")

    # ── 查看 / 編輯客戶 ──
    with tab2:
        if customers_df.empty:
            st.info("尚未建立任何客戶資料。")
        else:
            search = st.text_input("搜尋客戶名稱")
            view_df = customers_df.copy()
            if search:
                view_df = view_df[view_df["客戶名稱"].str.contains(search, case=False, na=False)]
            st.dataframe(view_df, use_container_width=True)
            st.caption(f"共 {len(customers_df)} 位客戶")

            st.divider()
            st.subheader("✏️ 編輯客戶資料")

            sel_cust = st.selectbox("選擇客戶", customers_df["客戶名稱"].tolist())
            cust_idx = customers_df[customers_df["客戶名稱"] == sel_cust].index[0]
            cust_row = customers_df.loc[cust_idx]

            if cust_row.get("生日"):
                st.markdown("#### 📊 流年 × 階段數 對照（自動計算）")
                render_numerology_table(cust_row["生日"])

            with st.form("edit_customer_form"):
                ec1, ec2 = st.columns(2)
                ec_name  = ec1.text_input("客戶名稱", value=cust_row["客戶名稱"])
                ec_phone = ec2.text_input("客戶電話", value=cust_row["客戶電話"])
                eb1, eb2 = st.columns(2)
                ec_wrist = eb1.text_input("手圍",              value=cust_row["手圍"])
                ec_bday  = eb2.text_input("生日（YYYY/MM/DD）", value=cust_row["生日"])

                ec3, ec4 = st.columns(2)
                cur_xi = [x for x in cust_row["喜神"].split("、") if x in WUXING_OPTS] if cust_row["喜神"] else []
                cur_ji = [x for x in cust_row["忌神"].split("、") if x in WUXING_OPTS] if cust_row["忌神"] else []
                ec_xi = ec3.multiselect("喜神", WUXING_OPTS, default=cur_xi)
                ec_ji = ec4.multiselect("忌神", WUXING_OPTS, default=cur_ji)

                col_save, col_del = st.columns(2)
                save_btn = col_save.form_submit_button("💾 儲存修改", use_container_width=True)
                del_btn  = col_del.form_submit_button( "🗑️ 刪除此客戶", use_container_width=True)

                if save_btn:
                    customers_df.loc[cust_idx, "客戶名稱"] = str(ec_name)
                    customers_df.loc[cust_idx, "客戶電話"] = str(ec_phone)
                    customers_df.loc[cust_idx, "手圍"]    = str(ec_wrist)
                    customers_df.loc[cust_idx, "生日"]    = str(ec_bday)
                    customers_df.loc[cust_idx, "喜神"]    = "、".join(ec_xi)
                    customers_df.loc[cust_idx, "忌神"]    = "、".join(ec_ji)
                    save_customers(customers_df)
                    st.success(f"✅ 客戶「{sel_cust}」資料已更新！")
                    time.sleep(1); st.rerun()

                if del_btn:
                    customers_df = customers_df.drop(index=cust_idx).reset_index(drop=True)
                    save_customers(customers_df)
                    st.warning(f"客戶「{sel_cust}」已刪除。")
                    time.sleep(1); st.rerun()
