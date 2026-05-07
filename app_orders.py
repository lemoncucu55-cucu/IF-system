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
    '訂單編號', '建立時間', '客戶名稱', '客戶電話', '商品種類', '客製品項',
    '手圍', '生日', '出生時間', '喜神', '忌神',
    '流年去年', '流年今年', '流年明年', '階段數',
    '總售價', '備註', '狀態', '付款狀態', '出貨狀態', '建單人'
]

CUSTOM_ITEMS = ["手鍊", "項鍊", "鑰匙圈"]

CUSTOMER_COLUMNS = [
    '客戶名稱', '客戶電話', '手圍', '喜神', '忌神', '生日', '出生時間',
    '流年去年', '流年今年', '流年明年', '階段數',
    '收件人姓名', '收件電話', '收件類型', '收件地址', '超商名稱門市'
]

DELIVERY_TYPES = ["🏠 住家", "🏪 超商"]

STATUS_FLOW    = ["待確認", "已確認", "已付款", "已出貨", "已付款已出貨", "已完成", "已取消"]
WUXING_OPTS    = ["金", "木", "水", "火", "土"]

RELATIONSHIP_COLUMNS = ['客戶A', '關係類型', '客戶B', '備註', '建立時間']
RELATION_TYPES = [
    "👫 夫妻／伴侶", "👨‍👩‍👧 親子", "👫 兄弟姊妹",
    "👯 朋友", "🤝 介紹人→被介紹", "💼 同事", "🔗 其他"
]

# ==========================================
# § 2 數字學計算工具
# ==========================================
def _digit_sum(n):
    return sum(int(d) for d in str(n))

def _reduce_chain(n):
    chain = [n]
    while n >= 10:
        n = _digit_sum(n)
        chain.append(n)
    return chain

def calc_liunian(year, birth_month, birth_day):
    digits_str = str(year) + str(birth_month) + str(birth_day)
    total = sum(int(d) for d in digits_str)
    chain = _reduce_chain(total)
    return "/".join(str(x) for x in chain)

def calc_jieduan(birth_year, birth_month):
    digits_str = str(birth_year) + str(birth_month)
    total = sum(int(d) for d in digits_str)
    chain = _reduce_chain(total)
    return "/".join(str(x) for x in chain)

def personal_year_range(birth_month, birth_day, today=None):
    if today is None:
        today = datetime.now().date()
    birthday_passed = (today.month, today.day) >= (birth_month, birth_day)
    personal_year = today.year if birthday_passed else today.year - 1
    return [personal_year - 1, personal_year, personal_year + 1]

def parse_birthday(bday_str):
    if not bday_str or not str(bday_str).strip():
        return None
    for fmt in ("%Y/%m/%d", "%Y-%m-%d"):
        try:
            d = datetime.strptime(str(bday_str).strip(), fmt)
            return d.year, d.month, d.day
        except ValueError:
            pass
    return None

def render_numerology_table(bday_str):
    parsed = parse_birthday(bday_str)
    if not parsed:
        st.warning("⚠️ 生日格式錯誤，請使用 YYYY/MM/DD（例：2000/10/10）")
        return False
    by, bm, bd = parsed
    years  = personal_year_range(bm, bd)
    labels = ["去年", "今年", "明年"]
    jieduan = calc_jieduan(by, bm)
    jd_final = jieduan.split("/")[-1]

    rows = []
    for yr, lbl in zip(years, labels):
        ln = calc_liunian(yr, bm, bd)
        ln_final = ln.split("/")[-1]
        rows.append({
            "年份":      f"{yr}（{lbl}）",
            "流年計算":  f"{yr}年 + {bm}月 + {bd}日 → {ln}",
            "流年數":    ln_final,
            "階段數計算": f"{by}年 + {bm}月 → {jieduan}",
            "階段數":    jd_final,
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
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

def _load_sheet(tab, columns):
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

def _save_sheet(tab, df):
    try:
        wb = get_gs_client().open_by_key(SHEET_ID)
        try:
            ws = wb.worksheet(tab)
        except gspread.exceptions.WorksheetNotFound:
            ws = wb.add_worksheet(title=tab, rows="1000", cols="20")
        data = df.fillna("").astype(str)
        ws.clear()
        ws.update(range_name='A1', values=[data.columns.tolist()] + data.values.tolist())
    except Exception as e:
        st.error(f"儲存 {tab} 失敗: {e}")

def fill_numerology(df):
    df = df.copy()
    for col in ["流年去年", "流年今年", "流年明年", "階段數"]:
        if col not in df.columns:
            df[col] = ""
    for idx, row in df.iterrows():
        bday_str = str(row.get("生日", "")).strip()
        parsed = parse_birthday(bday_str)
        if not parsed:
            df.loc[idx, ["流年去年", "流年今年", "流年明年", "階段數"]] = ""
            continue
        by, bm, bd = parsed
        years = personal_year_range(bm, bd)
        df.loc[idx, "流年去年"] = calc_liunian(years[0], bm, bd)
        df.loc[idx, "流年今年"] = calc_liunian(years[1], bm, bd)
        df.loc[idx, "流年明年"] = calc_liunian(years[2], bm, bd)
        df.loc[idx, "階段數"]   = calc_jieduan(by, bm)
    return df

def fill_order_substatus(df):
    """根據「狀態」欄位自動填入付款狀態 / 出貨狀態"""
    df = df.copy()
    for col in ["付款狀態", "出貨狀態"]:
        if col not in df.columns:
            df[col] = ""
    status_map = {
        "待確認":      ("未付款", "未出貨"),
        "已確認":      ("未付款", "未出貨"),
        "已付款":      ("已付款", "未出貨"),
        "已出貨":      ("未付款", "已出貨"),
        "已付款已出貨": ("已付款", "已出貨"),
        "已完成":      ("已付款", "已出貨"),
        "已取消":      ("—",    "—"),
    }
    for idx, row in df.iterrows():
        s = str(row.get("狀態", "")).strip()
        pay, ship = status_map.get(s, ("", ""))
        df.loc[idx, "付款狀態"] = pay
        df.loc[idx, "出貨狀態"] = ship
    return df

def load_orders():          return _load_sheet("Orders",        ORDER_COLUMNS)
def save_orders(df):        _save_sheet("Orders", fill_order_substatus(fill_numerology(df)))
def load_customers():       return _load_sheet("Customers",     CUSTOMER_COLUMNS)
def save_customers(df):     _save_sheet("Customers",     fill_numerology(df))
def load_relationships():   return _load_sheet("Relationships", RELATIONSHIP_COLUMNS)
def save_relationships(df): _save_sheet("Relationships", df)

def get_customer_relations(name, rel_df):
    if rel_df.empty or not name:
        return pd.DataFrame(columns=["對象", "關係類型", "備註", "建立時間"])
    rows = []
    for _, r in rel_df.iterrows():
        if r["客戶A"] == name:
            rows.append({"對象": r["客戶B"], "關係類型": r["關係類型"],
                         "備註": r["備註"], "建立時間": r["建立時間"]})
        elif r["客戶B"] == name:
            rows.append({"對象": r["客戶A"], "關係類型": r["關係類型"],
                         "備註": r["備註"], "建立時間": r["建立時間"]})
    return pd.DataFrame(rows) if rows else pd.DataFrame(
        columns=["對象", "關係類型", "備註", "建立時間"])

def generate_order_id():
    return f"ORD-{datetime.now().strftime('%m%d%H%M%S')}"

def safe_get(row, col, default=""):
    try:
        val = row[col]
        return val if pd.notna(val) and str(val).strip() else default
    except (KeyError, TypeError):
        return default

def sync_customers_from_orders():
    orders_df    = load_orders()
    customers_df = load_customers()
    if orders_df.empty:
        return 0
    existing_names = set(customers_df["客戶名稱"].tolist())
    new_rows = []
    for name, group in orders_df.groupby("客戶名稱"):
        if not name or name in existing_names:
            continue
        latest = group.iloc[-1]
        new_rows.append({
            "客戶名稱":   name,
            "客戶電話":   safe_get(latest, "客戶電話"),
            "手圍":      safe_get(latest, "手圍"),
            "喜神":      safe_get(latest, "喜神"),
            "忌神":      safe_get(latest, "忌神"),
            "生日":      safe_get(latest, "生日"),
            "出生時間":   safe_get(latest, "出生時間"),
            "收件人姓名": "",
            "收件電話":   "",
            "收件類型":   "",
            "收件地址":   "",
            "超商名稱門市": "",
        })
    if new_rows:
        customers_df = pd.concat(
            [customers_df, pd.DataFrame(new_rows)], ignore_index=True)
        save_customers(customers_df)
    return len(new_rows)

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
        "🔗 關係鏈結",
        "🔢 數字學計算",
    ])
    if st.button("🔄 刷新資料"):
        get_gs_client.clear()
        st.rerun()

    st.divider()
    if st.button("🔃 同步訂單→客戶資料", use_container_width=True,
                help="將訂單中尚未建檔的客戶自動加入客戶資料表"):
        added = sync_customers_from_orders()
        if added:
            st.success(f"✅ 已新增 {added} 位客戶")
        else:
            st.info("客戶資料已是最新，無需同步")

    if st.button("🔁 更新所有訂單狀態欄位", use_container_width=True,
                 help="將付款狀態、出貨狀態欄位同步到 Google Sheets"):
        df = load_orders()
        save_orders(df)
        st.success("✅ 所有訂單狀態欄位已更新！")

# ==========================================
# § 5 建立訂單
# ==========================================
if page == "📝 建立訂單":
    st.header("📝 建立新訂單")

    customers_df = load_customers()
    customer_list = customers_df["客戶名稱"].tolist() if not customers_df.empty else []

    st.subheader("👤 客戶選擇")
    use_existing = st.toggle("從現有客戶帶入資料", value=bool(customer_list))

    prefill = {}
    if use_existing and customer_list:
        sel_customer = st.selectbox("選擇客戶", ["── 請選擇 ──"] + customer_list)
        if sel_customer != "── 請選擇 ──":
            prefill = customers_df[customers_df["客戶名稱"] == sel_customer].iloc[0].to_dict()
            bday_str = str(prefill.get("生日", "")).strip()
            if bday_str:
                st.markdown("#### 📊 流年 × 階段數 三年對照表")
                render_numerology_table(bday_str)
            else:
                with st.container(border=True):
                    ci1, ci2, ci3, ci4 = st.columns(4)
                    ci1.write(f"**電話：** {prefill.get('客戶電話','-')}")
                    ci2.write(f"**手圍：** {prefill.get('手圍','-')}")
                    ci3.write(f"**喜神：** {prefill.get('喜神','-')}")
                    ci4.write(f"**忌神：** {prefill.get('忌神','-')}")
                st.info("ℹ️ 此客戶尚未填寫生日，無法顯示流年計算。")

    st.divider()

    with st.form("create_order_form"):
        st.subheader("客戶資訊")
        c1, c2 = st.columns(2)
        customer_name  = c1.text_input("客戶名稱 *", value=prefill.get("客戶名稱", ""))
        customer_phone = c2.text_input("客戶電話",   value=prefill.get("客戶電話", ""))

        st.subheader("訂單資訊")
        c3, c4, c5, c5b = st.columns(4)
        product_type  = c3.selectbox("商品種類", ["客製", "公版"])
        custom_item   = c4.selectbox("客製品項", CUSTOM_ITEMS)
        order_creator = c5.selectbox("建單人",   ["Imeng", "千畇"])
        total_price   = c5b.number_input("總售價 ($)（可之後再填）", min_value=0.0, value=0.0)

        st.subheader("手鍊 & 出生資訊")
        b1, b2, b3 = st.columns(3)
        wrist_size  = b1.text_input("手圍",                 value=prefill.get("手圍", ""))
        birthday    = b2.text_input("生日（YYYY/MM/DD）",   value=prefill.get("生日", ""),
                                    placeholder="例：2000/10/10")
        birth_time  = b3.text_input("出生時間（HH:MM）",   value=prefill.get("出生時間", ""),
                                    placeholder="例：08:30")

        st.subheader("五行")
        default_xi = [x for x in str(prefill.get("喜神","")).split("、") if x in WUXING_OPTS]
        default_ji = [x for x in str(prefill.get("忌神","")).split("、") if x in WUXING_OPTS]
        c6, c7 = st.columns(2)
        xi_shen = c6.multiselect("喜神", WUXING_OPTS, default=default_xi)
        ji_shen = c7.multiselect("忌神", WUXING_OPTS, default=default_ji)

        order_note = st.text_area("備註")

        if st.form_submit_button("✅ 建立訂單", use_container_width=True):
            if not customer_name:
                st.error("❌ 請填寫客戶名稱")
            else:
                order_id  = generate_order_id()
                orders_df = load_orders()
                new_order = {
                    "訂單編號":  order_id,
                    "建立時間":  datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "客戶名稱":  customer_name,
                    "客戶電話":  customer_phone,
                    "商品種類":  product_type,
                    "客製品項":  custom_item,
                    "手圍":     wrist_size,
                    "生日":     birthday,
                    "出生時間": birth_time,
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
            bday_val = safe_get(edit_row, "生日")
            if bday_val:
                st.markdown("**📊 流年 × 階段數 三年對照表**")
                render_numerology_table(bday_val)
            else:
                st.caption("ℹ️ 此訂單無生日資料，無法顯示流年計算。")

        with st.form("list_edit_form"):
            c1, c2 = st.columns(2)
            e_name  = c1.text_input("客戶名稱", value=safe_get(edit_row, "客戶名稱"))
            e_phone = c2.text_input("客戶電話", value=safe_get(edit_row, "客戶電話"))

            b1, b2, b3 = st.columns(3)
            e_wrist = b1.text_input("手圍",               value=safe_get(edit_row, "手圍"))
            e_bday  = b2.text_input("生日（YYYY/MM/DD）", value=safe_get(edit_row, "生日"))
            e_btime = b3.text_input("出生時間（HH:MM）",  value=safe_get(edit_row, "出生時間"))

            c3, c4, c5, c5b = st.columns(4)
            cur_type = safe_get(edit_row, "商品種類")
            e_type    = c3.selectbox("商品種類", ["客製","公版"],
                index=["客製","公版"].index(cur_type) if cur_type in ["客製","公版"] else 0)
            cur_item = safe_get(edit_row, "客製品項")
            e_item    = c4.selectbox("客製品項", CUSTOM_ITEMS,
                index=CUSTOM_ITEMS.index(cur_item) if cur_item in CUSTOM_ITEMS else 0)
            cur_creator = safe_get(edit_row, "建單人")
            e_creator = c5.selectbox("建單人", ["Imeng","千畇"],
                index=["Imeng","千畇"].index(cur_creator) if cur_creator in ["Imeng","千畇"] else 0)
            price_val = safe_get(edit_row, "總售價")
            e_price   = c5b.number_input("總售價 ($)", value=float(price_val) if price_val else 0.0)

            c6, c7 = st.columns(2)
            xi_val = safe_get(edit_row, "喜神")
            ji_val = safe_get(edit_row, "忌神")
            cur_xi = [x for x in xi_val.split("、") if x in WUXING_OPTS] if xi_val else []
            cur_ji = [x for x in ji_val.split("、") if x in WUXING_OPTS] if ji_val else []
            e_xi = c6.multiselect("喜神", WUXING_OPTS, default=cur_xi)
            e_ji = c7.multiselect("忌神", WUXING_OPTS, default=cur_ji)

            cur_status = safe_get(edit_row, "狀態")
            e_status = st.selectbox("狀態", STATUS_FLOW,
                index=STATUS_FLOW.index(cur_status) if cur_status in STATUS_FLOW else 0)
            e_note = st.text_area("備註", value=safe_get(edit_row, "備註"))

            if st.form_submit_button("💾 儲存修改", use_container_width=True):
                orders_df.loc[edit_idx, "客戶名稱"] = str(e_name)
                orders_df.loc[edit_idx, "客戶電話"] = str(e_phone)
                orders_df.loc[edit_idx, "手圍"]     = str(e_wrist)
                orders_df.loc[edit_idx, "生日"]     = str(e_bday)
                orders_df.loc[edit_idx, "出生時間"] = str(e_btime)
                orders_df.loc[edit_idx, "商品種類"] = str(e_type)
                orders_df.loc[edit_idx, "客製品項"] = str(e_item)
                orders_df.loc[edit_idx, "建單人"]   = str(e_creator)
                orders_df.loc[edit_idx, "總售價"]   = str(e_price)
                orders_df.loc[edit_idx, "喜神"]     = "、".join(e_xi)
                orders_df.loc[edit_idx, "忌神"]     = "、".join(e_ji)
                orders_df.loc[edit_idx, "狀態"]     = str(e_status)
                orders_df.loc[edit_idx, "備註"]     = str(e_note)
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
                c2.metric("客戶",    safe_get(sel_order, "客戶名稱"))
                price_v = safe_get(sel_order, "總售價")
                c3.metric("總售價",  f"${float(price_v):,.2f}" if price_v else "$0")
                c4.metric("目前狀態", safe_get(sel_order, "狀態"))

                st.write(
                    f"**電話：** {safe_get(sel_order,'客戶電話') or '-'} | "
                    f"**商品種類：** {safe_get(sel_order,'商品種類') or '-'} | "
                    f"**客製品項：** {safe_get(sel_order,'客製品項') or '-'} | "
                    f"**手圍：** {safe_get(sel_order,'手圍') or '-'} | "
                    f"**出生時間：** {safe_get(sel_order,'出生時間') or '-'} | "
                    f"**建單人：** {safe_get(sel_order,'建單人') or '-'} | "
                    f"**建立時間：** {safe_get(sel_order,'建立時間') or '-'}")
                st.write(
                    f"**喜神：** {safe_get(sel_order,'喜神') or '-'} | "
                    f"**忌神：** {safe_get(sel_order,'忌神') or '-'}")
                if safe_get(sel_order, "備註"):
                    st.write(f"**備註：** {sel_order['備註']}")

                bday_val = safe_get(sel_order, "生日")
                if bday_val:
                    st.markdown("**📊 流年 × 階段數 三年對照表**")
                    render_numerology_table(bday_val)

            st.divider()
            st.subheader("✏️ 修改訂單")
            with st.form("edit_order_form"):
                # 手動修改狀態
                cur_s = safe_get(sel_order, "狀態")
                all_statuses = ["待確認", "已確認", "已付款", "已出貨", "已付款已出貨", "已完成", "已取消"]
                new_status_sel = st.selectbox(
                    "📌 手動修改狀態",
                    all_statuses,
                    index=all_statuses.index(cur_s) if cur_s in all_statuses else 0
                )
                st.divider()
                ce0a, ce0b = st.columns(2)
                cur_otype = safe_get(sel_order,"商品種類")
                edit_type = ce0a.selectbox("商品種類", ["客製","公版"],
                    index=["客製","公版"].index(cur_otype) if cur_otype in ["客製","公版"] else 0)
                cur_oitem = safe_get(sel_order,"客製品項")
                edit_item = ce0b.selectbox("客製品項", CUSTOM_ITEMS,
                    index=CUSTOM_ITEMS.index(cur_oitem) if cur_oitem in CUSTOM_ITEMS else 0)

                ce1, ce2, ce3, ce4 = st.columns(4)
                edit_price = ce1.number_input("修改總售價 ($)",
                    value=float(safe_get(sel_order,"總售價")) if safe_get(sel_order,"總售價") else 0.0)
                edit_wrist = ce2.text_input("手圍",              value=safe_get(sel_order,"手圍"))
                edit_bday  = ce3.text_input("生日（YYYY/MM/DD）", value=safe_get(sel_order,"生日"))
                edit_btime = ce4.text_input("出生時間（HH:MM）",  value=safe_get(sel_order,"出生時間"))
                edit_note  = st.text_input("備註", value=safe_get(sel_order,"備註"))

                ce5, ce6 = st.columns(2)
                cx_v = safe_get(sel_order,"喜神")
                cj_v = safe_get(sel_order,"忌神")
                cx = [x for x in cx_v.split("、") if x in WUXING_OPTS] if cx_v else []
                cj = [x for x in cj_v.split("、") if x in WUXING_OPTS] if cj_v else []
                edit_xi = ce5.multiselect("喜神", WUXING_OPTS, default=cx)
                edit_ji = ce6.multiselect("忌神", WUXING_OPTS, default=cj)

                if st.form_submit_button("💾 儲存修改"):
                    orders_df.loc[sel_idx, "狀態"]     = str(new_status_sel)
                    orders_df.loc[sel_idx, "商品種類"] = str(edit_type)
                    orders_df.loc[sel_idx, "客製品項"] = str(edit_item)
                    orders_df.loc[sel_idx, "總售價"]   = str(edit_price)
                    orders_df.loc[sel_idx, "手圍"]     = str(edit_wrist)
                    orders_df.loc[sel_idx, "生日"]     = str(edit_bday)
                    orders_df.loc[sel_idx, "出生時間"] = str(edit_btime)
                    orders_df.loc[sel_idx, "備註"]     = str(edit_note)
                    orders_df.loc[sel_idx, "喜神"]     = "、".join(edit_xi)
                    orders_df.loc[sel_idx, "忌神"]     = "、".join(edit_ji)
                    save_orders(orders_df)
                    st.success("✅ 訂單已更新！")
                    time.sleep(1); st.rerun()

            st.divider()
            st.subheader("📌 變更狀態")
            cur_status = safe_get(sel_order, "狀態")

            # 進度條顯示
            if cur_status == "已取消":
                st.error("❌ 此訂單已取消")
            elif cur_status == "已完成":
                st.success("🎉 此訂單已完成")
            else:
                paid    = cur_status in ["已付款", "已付款已出貨"]
                shipped = cur_status in ["已出貨", "已付款已出貨"]

                p1, p2 = st.columns(2)
                p1.markdown(f"### 💰 付款：{'✅ 已付款' if paid else '⏳ 未付款'}")
                p2.markdown(f"### 📦 出貨：{'✅ 已出貨' if shipped else '⏳ 未出貨'}")

                st.divider()

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

                elif cur_status in ["已確認", "已付款", "已出貨", "已付款已出貨"]:
                    c1, c2, c3 = st.columns(3)
                    if not paid:
                        if c1.button("💰 確認已付款", type="primary", use_container_width=True):
                            new_s = "已付款已出貨" if shipped else "已付款"
                            orders_df.loc[sel_idx,"狀態"] = new_s
                            save_orders(orders_df); st.success(f"✅ {order_id} 已付款！")
                            time.sleep(1.5); st.rerun()
                    if not shipped:
                        if c2.button("📦 確認已出貨", type="primary", use_container_width=True):
                            new_s = "已付款已出貨" if paid else "已出貨"
                            orders_df.loc[sel_idx,"狀態"] = new_s
                            save_orders(orders_df); st.success(f"✅ {order_id} 已出貨！")
                            time.sleep(1.5); st.rerun()
                    if paid and shipped:
                        if c1.button("🎉 標記為已完成", type="primary", use_container_width=True):
                            orders_df.loc[sel_idx,"狀態"] = "已完成"
                            save_orders(orders_df); st.success(f"🎉 {order_id} 已完成！")
                            time.sleep(1.5); st.rerun()
                    if c3.button("❌ 取消訂單", use_container_width=True):
                        orders_df.loc[sel_idx,"狀態"] = "已取消"
                        save_orders(orders_df); st.warning(f"{order_id} 已取消。")
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

    with tab1:
        with st.container(border=True):
            st.markdown("#### 🔃 從訂單資料自動匯入客戶")
            st.caption("掃描所有訂單，將尚未建檔的客戶自動加入客戶資料表（已存在的不覆蓋）")
            if st.button("立即同步", type="primary", use_container_width=True):
                added = sync_customers_from_orders()
                customers_df = load_customers()
                if added:
                    st.success(f"✅ 已從訂單匯入 {added} 位新客戶！")
                else:
                    st.info("✅ 所有訂單客戶均已建檔，無需新增。")
                time.sleep(1); st.rerun()

        st.divider()
        st.subheader("手動新增客戶基本資料")
        with st.form("add_customer_form"):
            a1, a2 = st.columns(2)
            new_name  = a1.text_input("客戶名稱 *")
            new_phone = a2.text_input("客戶電話")

            a3, a4, a5 = st.columns(3)
            new_wrist = a3.text_input("手圍")
            new_bday  = a4.text_input("生日（YYYY/MM/DD）", placeholder="例：2000/10/10")
            new_btime = a5.text_input("出生時間（HH:MM）",  placeholder="例：08:30")

            a6, a7 = st.columns(2)
            new_xi = a6.multiselect("喜神", WUXING_OPTS)
            new_ji = a7.multiselect("忌神", WUXING_OPTS)

            st.divider()
            st.markdown("#### 📦 收件資料")
            d1, d2 = st.columns(2)
            new_recv_name  = d1.text_input("收件人姓名", placeholder="例：王小明")
            new_recv_phone = d2.text_input("收件電話",   placeholder="例：0912-345-678")
            new_recv_addr  = st.text_input("收件地址",   placeholder="例：台北市信義區信義路五段7號 或 7-11 台北信義門市")
            new_delivery_type = st.selectbox("收件類型", DELIVERY_TYPES, key="add_delivery_type")
            new_store_name = st.text_input("超商名稱／門市（超商才需填）", placeholder="例：7-11 台北信義門市")

            if st.form_submit_button("✅ 新增客戶", use_container_width=True):
                if not new_name:
                    st.error("❌ 請填寫客戶名稱")
                elif new_name in customers_df["客戶名稱"].values:
                    st.error(f"❌ 客戶「{new_name}」已存在")
                else:
                    row = {
                        "客戶名稱":   new_name,
                        "客戶電話":   new_phone,
                        "手圍":      new_wrist,
                        "喜神":      "、".join(new_xi),
                        "忌神":      "、".join(new_ji),
                        "生日":      new_bday,
                        "出生時間":   new_btime,
                        "收件人姓名": new_recv_name,
                        "收件電話":   new_recv_phone,
                        "收件類型":   new_delivery_type,
                        "收件地址":   new_recv_addr,
                        "超商名稱門市": new_store_name,
                    }
                    customers_df = pd.concat([customers_df, pd.DataFrame([row])], ignore_index=True)
                    save_customers(customers_df)
                    st.success(f"✅ 客戶「{new_name}」已新增！")
                    time.sleep(1.5); st.rerun()

    with tab2:
        rel_df_mgmt = load_relationships()

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

            bday_val = safe_get(cust_row, "生日")
            if bday_val:
                st.markdown("#### 📊 流年 × 階段數 三年對照表（自動計算）")
                render_numerology_table(bday_val)
            else:
                st.info("ℹ️ 請填寫生日後，系統將自動計算三年流年與階段數。")

            recv_type  = safe_get(cust_row, "收件類型")
            recv_addr  = safe_get(cust_row, "收件地址")
            recv_name  = safe_get(cust_row, "收件人姓名")
            recv_phone = safe_get(cust_row, "收件電話")
            store_name = safe_get(cust_row, "超商名稱門市")
            if recv_type or recv_addr or recv_name:
                with st.container(border=True):
                    st.markdown("#### 📦 收件資料")
                    sc1, sc2, sc3 = st.columns(3)
                    sc1.write(f"**收件人：** {recv_name or '-'}")
                    sc2.write(f"**收件電話：** {recv_phone or '-'}")
                    sc3.write(f"**類型：** {recv_type or '-'}")
                    if store_name:
                        st.write(f"**超商門市：** {store_name}")
                    if recv_addr:
                        st.write(f"**地址：** {recv_addr}")

            my_rels = get_customer_relations(sel_cust, rel_df_mgmt)
            if not my_rels.empty:
                st.markdown("#### 🔗 關係鏈結")
                st.dataframe(my_rels[["對象","關係類型","備註"]], use_container_width=True, hide_index=True)
                st.caption("完整管理請至「🔗 關係鏈結」頁面")

            with st.form("edit_customer_form"):
                ec1, ec2 = st.columns(2)
                ec_name  = ec1.text_input("客戶名稱", value=safe_get(cust_row,"客戶名稱"))
                ec_phone = ec2.text_input("客戶電話", value=safe_get(cust_row,"客戶電話"))

                eb1, eb2, eb3 = st.columns(3)
                ec_wrist = eb1.text_input("手圍",               value=safe_get(cust_row,"手圍"))
                ec_bday  = eb2.text_input("生日（YYYY/MM/DD）", value=safe_get(cust_row,"生日"))
                ec_btime = eb3.text_input("出生時間（HH:MM）",  value=safe_get(cust_row,"出生時間"))

                ec3, ec4 = st.columns(2)
                xi_v = safe_get(cust_row,"喜神")
                ji_v = safe_get(cust_row,"忌神")
                cur_xi = [x for x in xi_v.split("、") if x in WUXING_OPTS] if xi_v else []
                cur_ji = [x for x in ji_v.split("、") if x in WUXING_OPTS] if ji_v else []
                ec_xi = ec3.multiselect("喜神", WUXING_OPTS, default=cur_xi)
                ec_ji = ec4.multiselect("忌神", WUXING_OPTS, default=cur_ji)

                st.divider()
                st.markdown("#### 📦 收件資料")
                ed1, ed2 = st.columns(2)
                ec_recv_name  = ed1.text_input("收件人姓名", value=safe_get(cust_row,"收件人姓名"))
                ec_recv_phone = ed2.text_input("收件電話",   value=safe_get(cust_row,"收件電話"))
                ec_recv_addr  = st.text_input("收件地址",    value=safe_get(cust_row,"收件地址"))

                cur_dtype = safe_get(cust_row, "收件類型")
                dtype_idx = DELIVERY_TYPES.index(cur_dtype) if cur_dtype in DELIVERY_TYPES else 0
                ec_delivery_type = st.selectbox("收件類型", DELIVERY_TYPES,
                                                index=dtype_idx, key="edit_delivery_type")
                ec_store_name = st.text_input("超商名稱／門市（超商才需填）",
                                              value=safe_get(cust_row,"超商名稱門市"))

                col_save, col_del = st.columns(2)
                save_btn = col_save.form_submit_button("💾 儲存修改",  use_container_width=True)
                del_btn  = col_del.form_submit_button( "🗑️ 刪除此客戶", use_container_width=True)

                if save_btn:
                    customers_df.loc[cust_idx,"客戶名稱"]   = str(ec_name)
                    customers_df.loc[cust_idx,"客戶電話"]   = str(ec_phone)
                    customers_df.loc[cust_idx,"手圍"]       = str(ec_wrist)
                    customers_df.loc[cust_idx,"生日"]       = str(ec_bday)
                    customers_df.loc[cust_idx,"出生時間"]   = str(ec_btime)
                    customers_df.loc[cust_idx,"喜神"]       = "、".join(ec_xi)
                    customers_df.loc[cust_idx,"忌神"]       = "、".join(ec_ji)
                    customers_df.loc[cust_idx,"收件人姓名"] = str(ec_recv_name)
                    customers_df.loc[cust_idx,"收件電話"]   = str(ec_recv_phone)
                    customers_df.loc[cust_idx,"收件類型"]   = str(ec_delivery_type)
                    customers_df.loc[cust_idx,"收件地址"]   = str(ec_recv_addr)
                    customers_df.loc[cust_idx,"超商名稱門市"] = str(ec_store_name)
                    save_customers(customers_df)
                    st.success(f"✅ 客戶「{sel_cust}」資料已更新！")
                    time.sleep(1); st.rerun()

                if del_btn:
                    customers_df = customers_df.drop(index=cust_idx).reset_index(drop=True)
                    save_customers(customers_df)
                    st.warning(f"客戶「{sel_cust}」已刪除。")
                    time.sleep(1); st.rerun()

# ==========================================
# § 10 關係鏈結
# ==========================================
elif page == "🔗 關係鏈結":
    st.header("🔗 關係鏈結（Relationship Mapping）")

    customers_df  = load_customers()
    rel_df        = load_relationships()
    cust_names    = customers_df["客戶名稱"].tolist() if not customers_df.empty else []

    tab_view, tab_add, tab_all = st.tabs(["👤 查詢客戶關係", "➕ 新增關係", "📋 所有關係清單"])

    with tab_view:
        if not cust_names:
            st.info("尚未建立任何客戶資料。")
        else:
            sel_name = st.selectbox("選擇客戶", cust_names, key="rel_view_sel")
            my_rels  = get_customer_relations(sel_name, rel_df)

            if not customers_df.empty:
                crow = customers_df[customers_df["客戶名稱"] == sel_name]
                if not crow.empty:
                    c = crow.iloc[0]
                    with st.container(border=True):
                        col1, col2, col3, col4 = st.columns(4)
                        col1.write(f"**📞** {safe_get(c,'客戶電話') or '-'}")
                        col2.write(f"**手圍：** {safe_get(c,'手圍') or '-'}")
                        col3.write(f"**喜神：** {safe_get(c,'喜神') or '-'}")
                        col4.write(f"**忌神：** {safe_get(c,'忌神') or '-'}")
                        bday = safe_get(c, "生日")
                        if bday:
                            st.caption(f"🎂 {bday}　流年今年：{safe_get(c,'流年今年') or '-'}　階段數：{safe_get(c,'階段數') or '-'}")

            st.subheader(f"🔗 {sel_name} 的所有關係")
            if my_rels.empty:
                st.info("此客戶目前沒有任何關係鏈結。")
            else:
                st.dataframe(my_rels, use_container_width=True, hide_index=True)
                st.caption(f"共 {len(my_rels)} 條關係")

                st.divider()
                st.subheader("📊 關聯客戶數字學對照")
                for _, rel_row in my_rels.iterrows():
                    target = rel_row["對象"]
                    tcrow  = customers_df[customers_df["客戶名稱"] == target]
                    with st.expander(f"{rel_row['關係類型']} ▸ **{target}**"):
                        if not tcrow.empty:
                            tc = tcrow.iloc[0]
                            col1, col2 = st.columns(2)
                            col1.write(f"**電話：** {safe_get(tc,'客戶電話') or '-'}")
                            col2.write(f"**手圍：** {safe_get(tc,'手圍') or '-'}")
                            tbday = safe_get(tc, "生日")
                            if tbday:
                                render_numerology_table(tbday)
                            else:
                                st.caption("此客戶尚無生日資料")
                        else:
                            st.caption("此關聯客戶不在客戶資料庫中")

                st.divider()
                st.subheader("🗑️ 刪除關係")
                del_opts = [
                    f"{r['對象']}（{r['關係類型']}）"
                    for _, r in my_rels.iterrows()
                ]
                del_sel = st.selectbox("選擇要刪除的關係", del_opts, key="rel_del_sel")
                if st.button("🗑️ 確認刪除", type="secondary"):
                    del_target = del_sel.split("（")[0]
                    rel_df = rel_df[~(
                        ((rel_df["客戶A"] == sel_name) & (rel_df["客戶B"] == del_target)) |
                        ((rel_df["客戶A"] == del_target) & (rel_df["客戶B"] == sel_name))
                    )].reset_index(drop=True)
                    save_relationships(rel_df)
                    st.success(f"✅ 已刪除與「{del_target}」的關係")
                    time.sleep(1); st.rerun()

    with tab_add:
        if len(cust_names) < 2:
            st.info("至少需要 2 位客戶才能建立關係。")
        else:
            st.subheader("新增客戶關係")
            with st.form("add_relation_form"):
                col1, col2 = st.columns(2)
                cust_a = col1.selectbox("客戶 A", cust_names, key="rel_a")
                cust_b = col2.selectbox("客戶 B", cust_names, key="rel_b")

                rel_type = st.selectbox("關係類型", RELATION_TYPES)
                rel_note = st.text_input("備註（選填）", placeholder="例：同年入會、朋友介紹")

                if st.form_submit_button("✅ 建立關係", use_container_width=True):
                    if cust_a == cust_b:
                        st.error("❌ 不能將同一位客戶與自己連結")
                    else:
                        dup = rel_df[
                            ((rel_df["客戶A"] == cust_a) & (rel_df["客戶B"] == cust_b)) |
                            ((rel_df["客戶A"] == cust_b) & (rel_df["客戶B"] == cust_a))
                        ]
                        if not dup.empty:
                            st.warning("⚠️ 此兩位客戶之間已有關係鏈結，請至清單修改")
                        else:
                            new_rel = {
                                "客戶A":   cust_a,
                                "關係類型": rel_type,
                                "客戶B":   cust_b,
                                "備註":    rel_note,
                                "建立時間": datetime.now().strftime("%Y-%m-%d %H:%M"),
                            }
                            rel_df = pd.concat([rel_df, pd.DataFrame([new_rel])], ignore_index=True)
                            save_relationships(rel_df)
                            st.success(f"✅ 已建立：{cust_a} ⟷ {cust_b}（{rel_type}）")
                            time.sleep(1.5); st.rerun()

    with tab_all:
        st.subheader("所有關係清單")
        if rel_df.empty:
            st.info("目前沒有任何關係鏈結。")
        else:
            search_r = st.text_input("搜尋客戶名稱", key="rel_search_all")
            view_rel = rel_df.copy()
            if search_r:
                mask = (
                    view_rel["客戶A"].str.contains(search_r, case=False, na=False) |
                    view_rel["客戶B"].str.contains(search_r, case=False, na=False)
                )
                view_rel = view_rel[mask]
            st.dataframe(view_rel, use_container_width=True, hide_index=True)
            st.caption(f"共 {len(rel_df)} 條關係鏈結")

# ==========================================
# § 11 數字學計算（獨立頁面）
# ==========================================
elif page == "🔢 數字學計算":
    st.header("🔢 數字學計算器")
    st.caption("輸入任意生日，立即查看三年流年與階段數")

    col_a, col_b = st.columns([1, 2])
    with col_a:
        with st.container(border=True):
            st.subheader("輸入生日")
            input_bday  = st.text_input("生日（YYYY/MM/DD）",
                                        value="2000/10/10",
                                        placeholder="例：2000/10/10")
            input_btime = st.text_input("出生時間（HH:MM，選填）",
                                        placeholder="例：08:30")

            customers_df = load_customers()
            if not customers_df.empty:
                st.divider()
                st.caption("或從現有客戶帶入生日：")
                quick_sel = st.selectbox("快速選擇客戶", ["── 手動輸入 ──"] + customers_df["客戶名稱"].tolist())
                if quick_sel != "── 手動輸入 ──":
                    row = customers_df[customers_df["客戶名稱"] == quick_sel].iloc[0]
                    input_bday  = safe_get(row, "生日")  or input_bday
                    input_btime = safe_get(row, "出生時間") or input_btime
                    st.info(f"已帶入：{quick_sel}（{input_bday}）")

    with col_b:
        if input_bday:
            parsed = parse_birthday(input_bday)
            if parsed:
                by, bm, bd = parsed
                years  = personal_year_range(bm, bd)
                labels = ["去年", "今年", "明年"]
                today  = datetime.now().date()

                passed = (today.month, today.day) >= (bm, bd)
                bday_desc = f"生日 {bm}/{bd} 今年{'已過 ✅' if passed else '尚未到 ⏳'}"
                st.info(f"📅 {bday_desc}｜個人年基準：{years[1]} 年")

                st.subheader("📊 三年流年 × 階段數對照表")
                render_numerology_table(input_bday)

                st.divider()
                st.subheader("📐 詳細計算過程")
                for yr, lbl in zip(years, labels):
                    ln = calc_liunian(yr, bm, bd)
                    ln_steps = " → ".join(str(x) for x in _reduce_chain(
                        sum(int(d) for d in (str(yr)+str(bm)+str(bd)))))
                    jd = calc_jieduan(by, bm)
                    jd_steps = " → ".join(str(x) for x in _reduce_chain(
                        sum(int(d) for d in (str(by)+str(bm)))))

                    with st.expander(f"{yr}（{lbl}）— 流年 {ln.split('/')[-1]}，階段 {jd.split('/')[-1]}"):
                        st.markdown(f"""
**流年計算：**
- 年份 {yr} + 月 {bm} + 日 {bd}
- 各位數字：{' + '.join(list(str(yr)+str(bm)+str(bd)))} = {sum(int(d) for d in str(yr)+str(bm)+str(bd))}
- 縮減過程：{ln_steps}
- **結果：{ln.split('/')[-1]}**

**階段數計算（個人固定數）：**
- 出生年 {by} + 月 {bm}
- 各位數字：{' + '.join(list(str(by)+str(bm)))} = {sum(int(d) for d in str(by)+str(bm))}
- 縮減過程：{jd_steps}
- **結果：{jd.split('/')[-1]}**
""")
                if input_btime:
                    st.divider()
                    st.markdown(f"**出生時間：** {input_btime}")
            else:
                st.error("⚠️ 生日格式錯誤，請輸入 YYYY/MM/DD（例：2000/10/10）")
        else:
            st.info("👈 請在左側輸入生日")
