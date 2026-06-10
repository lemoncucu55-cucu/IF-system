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
    '總售價', '成本', '運費', '總成本',
    '備註', '狀態', '付款狀態', '出貨狀態', '建單人',
    '出貨方式', '出貨單號'
]

CUSTOM_ITEMS = ["手鍊", "項鍊", "鑰匙圈", "車掛"]

CUSTOMER_COLUMNS = [
    '客戶名稱', '客戶電話', '手圍', '喜神', '忌神', '生日', '出生時間',
    '流年去年', '流年今年', '流年明年', '階段數',
    '收件人姓名', '收件電話', '收件類型', '收件地址', '超商名稱門市'
]

DELIVERY_TYPES = ["🏠 住家", "🏪 超商"]
STATUS_FLOW = ["待確認", "已確認", "未付款未出貨", "未付款已出貨", "已付款未出貨", "已出貨", "已完成", "已取消"]
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

def calc_age(birth_year, birth_month, birth_day, today=None):
    if today is None:
        today = datetime.now().date()
    age = today.year - birth_year
    if (today.month, today.day) < (birth_month, birth_day):
        age -= 1
    return age

def get_life_stage(age):
    if age <= 10:
        return "幼年"
    elif age <= 20:
        return "少年"
    elif age <= 40:
        return "青年"
    elif age <= 60:
        return "中年"
    else:
        return "老年"

def parse_birth_time(btime_str):
    if not btime_str or not str(btime_str).strip():
        return None, None
    try:
        parts = str(btime_str).strip().split(":")
        hour   = int(parts[0]) if len(parts) > 0 else None
        minute = int(parts[1]) if len(parts) > 1 else None
        return hour, minute
    except Exception:
        return None, None

def calc_jieduan(birth_year, birth_month, birth_day=None,
                 birth_hour=None, birth_minute=None, age=None):
    if age is None:
        if birth_day:
            age = calc_age(birth_year, birth_month, birth_day)
        else:
            age = 30

    stage = get_life_stage(age)
    digits_str  = str(birth_year)
    label_parts = [f"年({birth_year})"]

    if stage in ["幼年", "少年", "青年", "中年"]:
        digits_str += str(birth_month)
        label_parts.append(f"月({birth_month})")

    if stage in ["幼年", "少年", "青年"] and birth_day is not None:
        digits_str += str(birth_day)
        label_parts.append(f"日({birth_day})")

    if stage in ["幼年", "少年"] and birth_hour is not None:
        digits_str += str(birth_hour)
        label_parts.append(f"時({birth_hour})")

    if stage == "幼年" and birth_minute is not None:
        digits_str += str(birth_minute)
        label_parts.append(f"分({birth_minute})")

    total  = sum(int(d) for d in digits_str)
    chain  = _reduce_chain(total)
    result = "/".join(str(x) for x in chain)
    label  = " + ".join(label_parts) + f" → {result}"
    return result, stage, label

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

def render_numerology_table(bday_str, btime_str=""):
    parsed = parse_birthday(bday_str)
    if not parsed:
        st.warning("⚠️ 生日格式錯誤，請使用 YYYY/MM/DD（例：2000/10/10）")
        return False

    by, bm, bd    = parsed
    birth_hour, birth_minute = parse_birth_time(btime_str)
    age           = calc_age(by, bm, bd)
    cur_stage     = get_life_stage(age)

    jd_cur, _, jd_label = calc_jieduan(by, bm, bd, birth_hour, birth_minute, age)
    st.info(
        f"{'🍼' if cur_stage=='幼年' else '🌱' if cur_stage=='少年' else '🔥' if cur_stage=='青年' else '🌳' if cur_stage=='中年' else '🌙'} "
        f"目前階段：**{cur_stage}**（{age} 歲）｜階段數公式：{jd_label}｜**階段數 = {jd_cur.split('/')[-1]}**"
    )

    stage_configs = [
        ("老年", "61 歲以上",  70, False, False),
        ("中年", "41 – 60 歲", 50, False, False),
        ("青年", "21 – 40 歲", 30, False, False),
        ("少年", "11 – 20 歲", 15, True,  False),
        ("幼年", "0 – 10 歲",   5, True,  True),
    ]

    cols = st.columns(5)
    for col, (sname, age_label, mid_age, need_hour, need_min) in zip(cols, stage_configs):
        has_data = True
        if need_hour and birth_hour is None:
            has_data = False
        if need_min and birth_minute is None:
            has_data = False

        if has_data:
            res, _, _ = calc_jieduan(by, bm, bd, birth_hour, birth_minute, mid_age)
            display = res
        else:
            display = "—"

        is_cur = (sname == cur_stage)
        bg           = "#1a3a8f" if is_cur else "#e8eef7"
        color        = "#ffffff" if is_cur else "#1a3a8f"
        border       = "2px solid #1a3a8f" if is_cur else "2px solid transparent"
        title_color  = "#1a3a8f" if is_cur else "#333333"
        cur_label    = " ◀ 目前" if is_cur else ""

        with col:
            st.markdown(
                f"<div style='text-align:center; font-weight:bold; color:{title_color}; margin-bottom:8px;'>"
                f"{sname}階段{cur_label}</div>",
                unsafe_allow_html=True
            )
            st.markdown(
                f"<div style='background:{bg}; border:{border}; border-radius:12px; "
                f"padding:18px 8px; text-align:center; margin-bottom:8px;'>"
                f"<span style='font-size:24px; font-weight:bold; color:{color};'>{display}</span>"
                f"</div>",
                unsafe_allow_html=True
            )
            st.markdown(
                f"<div style='text-align:center; color:#888; font-size:13px;'>{age_label}</div>",
                unsafe_allow_html=True
            )

    st.divider()

    st.caption("📅 流年三年對照")
    years  = personal_year_range(bm, bd)
    labels = ["去年", "今年", "明年"]
    rows   = []
    for yr, lbl in zip(years, labels):
        ln = calc_liunian(yr, bm, bd)
        rows.append({
            "年份":      f"{yr}（{lbl}）",
            "流年計算":  f"{yr}年 + {bm}月 + {bd}日 → {ln}",
            "流年數":    ln.split("/")[-1],
            "當前階段數": jd_cur.split("/")[-1],
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

def _safe_float(val):
    try:
        return float(val)
    except (ValueError, TypeError):
        return 0.0

def calc_total_cost(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    if "總成本" not in df.columns:
        df["總成本"] = ""
    for idx, row in df.iterrows():
        cost = _safe_float(row.get("成本", 0))
        shipping = _safe_float(row.get("運費", 0))
        df.loc[idx, "總成本"] = str(cost + shipping)
    return df

def fill_numerology(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for col in ["流年去年", "流年今年", "流年明年", "階段數"]:
        if col not in df.columns:
            df[col] = ""
    for idx, row in df.iterrows():
        bday_str  = str(row.get("生日", "")).strip()
        btime_str = str(row.get("出生時間", "")).strip()
        parsed = parse_birthday(bday_str)
        if not parsed:
            df.loc[idx, ["流年去年", "流年今年", "流年明年", "階段數"]] = ""
            continue
        by, bm, bd = parsed
        birth_hour, birth_minute = parse_birth_time(btime_str)
        age   = calc_age(by, bm, bd)
        years = personal_year_range(bm, bd)
        df.loc[idx, "流年去年"] = calc_liunian(years[0], bm, bd)
        df.loc[idx, "流年今年"] = calc_liunian(years[1], bm, bd)
        df.loc[idx, "流年明年"] = calc_liunian(years[2], bm, bd)
        jd_result, _, _ = calc_jieduan(by, bm, bd, birth_hour, birth_minute, age)
        df.loc[idx, "階段數"] = jd_result
    return df

@st.cache_data(ttl=60)
def load_orders():
    return _load_sheet("Orders", ORDER_COLUMNS)

@st.cache_data(ttl=60)
def load_customers():
    return _load_sheet("Customers", CUSTOMER_COLUMNS)

@st.cache_data(ttl=60)
def load_relationships():
    return _load_sheet("Relationships", RELATIONSHIP_COLUMNS)

def save_orders(df):
    df = fill_numerology(df)
    df = calc_total_cost(df)
    _save_sheet("Orders", df)
    load_orders.clear()

def save_customers(df):
    _save_sheet("Customers", fill_numerology(df))
    load_customers.clear()

def save_relationships(df):
    _save_sheet("Relationships", df)
    load_relationships.clear()

def get_customer_relations(name: str, rel_df: pd.DataFrame) -> pd.DataFrame:
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
            "客戶名稱":  name,
            "客戶電話":  safe_get(latest, "客戶電話"),
            "手圍":     safe_get(latest, "手圍"),
            "喜神":     safe_get(latest, "喜神"),
            "忌神":     safe_get(latest, "忌神"),
            "生日":     safe_get(latest, "生日"),
            "出生時間":  safe_get(latest, "出生時間"),
            "收件人姓名": "",
            "收件電話":  "",
            "收件類型":  "",
            "收件地址":  "",
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
        "📋 訂單管理",
        "📜 訂單紀錄",
        "👥 客戶管理",
        "🔗 關係鏈結",
        "🔢 數字學計算",
    ])
    if st.button("🔄 刷新資料"):
        get_gs_client.clear()
        st.rerun()

    st.divider()
    try:
        _all_orders_sb = load_orders()
        _unshipped_sb  = _all_orders_sb[
            _all_orders_sb["狀態"].isin(["待確認", "已確認", "未付款未出貨", "已付款未出貨"])
        ] if not _all_orders_sb.empty else pd.DataFrame()
    except Exception:
        _unshipped_sb = pd.DataFrame()
    if not _unshipped_sb.empty:
        st.error(f"🚨 未出貨訂單：{len(_unshipped_sb)} 筆")
        for _, _r in _unshipped_sb.iterrows():
            st.caption(f"• {_r['訂單編號']} — {_r['客戶名稱']} [{_r['狀態']}]")
    else:
        st.success("✅ 所有訂單已出貨")

    st.divider()
    if st.button("🔃 同步訂單→客戶資料", use_container_width=True,
                 help="將訂單中尚未建檔的客戶自動加入客戶資料表"):
        added = sync_customers_from_orders()
        if added:
            st.success(f"✅ 已新增 {added} 位客戶")
        else:
            st.info("客戶資料已是最新，無需同步")

# ==========================================
# § 5 建立訂單
# ==========================================
if page == "📝 建立訂單":
    st.header("📝 建立新訂單")

    customers_df  = load_customers()
    customer_list = customers_df["客戶名稱"].tolist() if not customers_df.empty else []

    st.subheader("👤 客戶選擇")
    use_existing = st.toggle("從現有客戶帶入資料", value=bool(customer_list))

    prefill = {}
    if use_existing and customer_list:
        sel_customer = st.selectbox("選擇客戶", ["── 請選擇 ──"] + customer_list)
        if sel_customer != "── 請選擇 ──":
            prefill   = customers_df[customers_df["客戶名稱"] == sel_customer].iloc[0].to_dict()
            bday_str  = str(prefill.get("生日", "")).strip()
            btime_str = str(prefill.get("出生時間", "")).strip()
            if bday_str:
                st.markdown("#### 📊 流年 × 階段數 三年對照表")
                render_numerology_table(bday_str, btime_str)
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
        c3, c4, c5 = st.columns(3)
        product_type  = c3.selectbox("商品種類", ["客製", "公版"])
        custom_item   = c4.selectbox("客製品項", CUSTOM_ITEMS)
        order_creator = c5.selectbox("建單人",   ["Imeng", "千畇"])

        p1, p2, p3 = st.columns(3)
        total_price   = p1.number_input("總售價 ($)", min_value=0.0, value=0.0)
        cost_price    = p2.number_input("成本 ($)",   min_value=0.0, value=0.0)
        shipping_fee  = p3.number_input("運費 ($)",   min_value=0.0, value=0.0)

        computed_total_cost = cost_price + shipping_fee
        st.info(f"💰 總成本 = 成本 ${cost_price:,.0f} + 運費 ${shipping_fee:,.0f} = **${computed_total_cost:,.0f}**")

        st.subheader("手鍊 & 出生資訊")
        b1, b2, b3 = st.columns(3)
        wrist_size = b1.text_input("手圍",               value=prefill.get("手圍", ""))
        birthday   = b2.text_input("生日（YYYY/MM/DD）", value=prefill.get("生日", ""),
                                   placeholder="例：2000/10/10")
        birth_time = b3.text_input("出生時間（HH:MM）",  value=prefill.get("出生時間", ""),
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
                    "成本":     str(cost_price),
                    "運費":     str(shipping_fee),
                    "總成本":   str(cost_price + shipping_fee),
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
# § 6 訂單管理（整合列表 + 狀態變更）
# ==========================================
elif page == "📋 訂單管理":
    st.header("📋 訂單管理")
    orders_df = load_orders()

    if not orders_df.empty:
        _auto_updated = False
        for _ai, _ar in orders_df.iterrows():
            _pay = str(_ar.get("付款狀態", "")).strip()
            _ship = str(_ar.get("出貨狀態", "")).strip()
            _st = str(_ar.get("狀態", "")).strip()
            if (_pay in ["已付款", "已完成"] and _ship in ["已出貨", "已完成"]
                    and _st not in ["已完成", "已取消"]):
                orders_df.loc[_ai, "狀態"] = "已完成"
                _auto_updated = True
        if _auto_updated:
            save_orders(orders_df)
            st.rerun()

    if not orders_df.empty:
        unshipped = orders_df[orders_df["狀態"].isin(["待確認", "已確認", "未付款未出貨", "已付款未出貨"])].copy()
        if not unshipped.empty:
            with st.container(border=True):
                st.markdown(f"### 🚨 未出貨訂單提醒 — 共 **{len(unshipped)}** 筆")
                cols_h = st.columns([2, 2, 2, 2])
                cols_h[0].markdown("**訂單編號**")
                cols_h[1].markdown("**客戶名稱**")
                cols_h[2].markdown("**商品種類**")
                cols_h[3].markdown("**目前狀態**")
                for _, urow in unshipped.iterrows():
                    r1, r2, r3, r4 = st.columns([2, 2, 2, 2])
                    r1.write(urow.get("訂單編號", ""))
                    r2.write(urow.get("客戶名稱", ""))
                    r3.write(urow.get("商品種類", ""))
                    status_icon = "🔴" if urow.get("狀態") == "待確認" else "🟡"
                    r4.write(f"{status_icon} {urow.get('狀態', '')}")
            st.divider()

    if orders_df.empty:
        st.info("目前沒有任何訂單。")
    else:
        search_customer = st.text_input("🔍 搜尋客戶名稱", key="mgmt_search")

        DONE_STATUS = ["已完成", "已取消"]
        active_df = orders_df[~orders_df["狀態"].isin(DONE_STATUS)].copy()
        done_df   = orders_df[ orders_df["狀態"].isin(DONE_STATUS)].copy()

        if search_customer:
            active_df = active_df[active_df["客戶名稱"].str.contains(search_customer, case=False, na=False)]
            done_df   = done_df[done_df["客戶名稱"].str.contains(search_customer, case=False, na=False)]

        tab_active, tab_done = st.tabs([
            f"🔄 未完成（{len(active_df)} 筆）",
            f"✅ 已完成（{len(done_df)} 筆）",
        ])

        with tab_active:
            if active_df.empty:
                st.success("🎉 所有訂單都已處理完成！")
            else:
                st.dataframe(
                    active_df[["訂單編號","客戶名稱","商品種類","客製品項","總售價","狀態","付款狀態","出貨狀態","建立時間"]].iloc[::-1],
                    use_container_width=True, hide_index=True)
                st.caption(f"共 {len(active_df)} 筆未完成訂單")

                st.divider()
                active_df["display"] = active_df.apply(
                    lambda r: f"[{r['狀態']}] {r['訂單編號']} — {r['客戶名稱']} | {r['商品種類']} | ${r['總售價']}", axis=1)
                sel_disp  = st.selectbox("選擇要管理的訂單", active_df["display"].tolist()[::-1])
                sel_idx   = active_df[active_df["display"] == sel_disp].index[0]
                sel_order = orders_df.loc[sel_idx]
                order_id  = sel_order["訂單編號"]

                with st.container(border=True):
                    c1, c2, c3, c4, c5, c6, c7 = st.columns(7)
                    c1.metric("訂單編號", order_id)
                    c2.metric("客戶",    safe_get(sel_order, "客戶名稱"))
                    price_v = safe_get(sel_order, "總售價")
                    cost_v  = safe_get(sel_order, "成本")
                    ship_v  = safe_get(sel_order, "運費")
                    tc_v    = safe_get(sel_order, "總成本")
                    price_f = _safe_float(price_v)
                    cost_f  = _safe_float(cost_v)
                    ship_f  = _safe_float(ship_v)
                    tc_f    = _safe_float(tc_v) if tc_v else cost_f + ship_f
                    profit  = price_f - tc_f
                    c3.metric("總售價", f"${price_f:,.0f}")
                    c4.metric("成本",   f"${cost_f:,.0f}")
                    c5.metric("運費",   f"${ship_f:,.0f}")
                    c6.metric("總成本", f"${tc_f:,.0f}")
                    c7.metric("利潤",   f"${profit:,.0f}",
                              delta=f"{(profit/price_f*100):.0f}%" if price_f else None)

                    st.write(
                        f"**目前狀態：** {safe_get(sel_order, '狀態')} | "
                        f"**電話：** {safe_get(sel_order,'客戶電話') or '-'} | "
                        f"**商品種類：** {safe_get(sel_order,'商品種類') or '-'} | "
                        f"**客製品項：** {safe_get(sel_order,'客製品項') or '-'} | "
                        f"**手圍：** {safe_get(sel_order,'手圍') or '-'} | "
                        f"**生日：** {safe_get(sel_order,'生日') or '-'} | "
                        f"**出生時間：** {safe_get(sel_order,'出生時間') or '-'} | "
                        f"**建單人：** {safe_get(sel_order,'建單人') or '-'} | "
                        f"**建立時間：** {safe_get(sel_order,'建立時間') or '-'}")
                    st.write(
                        f"**喜神：** {safe_get(sel_order,'喜神') or '-'} | "
                        f"**忌神：** {safe_get(sel_order,'忌神') or '-'}")
                    if safe_get(sel_order, "備註"):
                        st.write(f"**備註：** {sel_order['備註']}")

                    bday_val  = safe_get(sel_order, "生日")
                    btime_val = safe_get(sel_order, "出生時間")
                    if bday_val:
                        st.markdown("**📊 流年 × 階段數**")
                        render_numerology_table(bday_val, btime_val)

                st.divider()
                st.subheader("✏️ 修改訂單")
                with st.form("edit_order_form"):
                    ce0a, ce0b, ce0c = st.columns(3)
                    e_name = ce0a.text_input("客戶名稱", value=safe_get(sel_order, "客戶名稱"))
                    e_phone = ce0b.text_input("客戶電話", value=safe_get(sel_order, "客戶電話"))
                    cur_creator = safe_get(sel_order, "建單人")
                    e_creator = ce0c.selectbox("建單人", ["Imeng","千畇"],
                        index=["Imeng","千畇"].index(cur_creator) if cur_creator in ["Imeng","千畇"] else 0)

                    ce0d, ce0e = st.columns(2)
                    cur_otype = safe_get(sel_order,"商品種類")
                    edit_type = ce0d.selectbox("商品種類", ["客製","公版"],
                        index=["客製","公版"].index(cur_otype) if cur_otype in ["客製","公版"] else 0)
                    cur_oitem = safe_get(sel_order,"客製品項")
                    edit_item = ce0e.selectbox("客製品項", CUSTOM_ITEMS,
                        index=CUSTOM_ITEMS.index(cur_oitem) if cur_oitem in CUSTOM_ITEMS else 0)

                    ce1, ce2, ce3 = st.columns(3)
                    edit_price = ce1.number_input("總售價 ($)",
                        value=_safe_float(safe_get(sel_order,"總售價")))
                    edit_cost  = ce2.number_input("成本 ($)",
                        value=_safe_float(safe_get(sel_order,"成本")),
                        key="mgmt_cost")
                    edit_ship_fee = ce3.number_input("運費 ($)",
                        value=_safe_float(safe_get(sel_order,"運費")),
                        key="mgmt_ship_fee")

                    computed_tc = edit_cost + edit_ship_fee
                    st.info(f"💰 總成本 = 成本 ${edit_cost:,.0f} + 運費 ${edit_ship_fee:,.0f} = **${computed_tc:,.0f}**　｜　利潤 = ${edit_price - computed_tc:,.0f}")

                    ce3a, ce3b, ce3c = st.columns(3)
                    edit_wrist = ce3a.text_input("手圍",               value=safe_get(sel_order,"手圍"))
                    edit_bday  = ce3b.text_input("生日（YYYY/MM/DD）", value=safe_get(sel_order,"生日"))
                    edit_btime = ce3c.text_input("出生時間（HH:MM）",  value=safe_get(sel_order,"出生時間"))

                    ce6, ce7 = st.columns(2)
                    cx_v = safe_get(sel_order,"喜神")
                    cj_v = safe_get(sel_order,"忌神")
                    cx = [x for x in cx_v.split("、") if x in WUXING_OPTS] if cx_v else []
                    cj = [x for x in cj_v.split("、") if x in WUXING_OPTS] if cj_v else []
                    edit_xi = ce6.multiselect("喜神", WUXING_OPTS, default=cx)
                    edit_ji = ce7.multiselect("忌神", WUXING_OPTS, default=cj)

                    st.divider()
                    sf1, sf2 = st.columns(2)
                    SHIP_METHOD = ["—", "郵局", "7-11", "全家"]
                    cur_smethod = safe_get(sel_order, "出貨方式")
                    edit_ship_method = sf1.selectbox("出貨方式", SHIP_METHOD,
                        index=SHIP_METHOD.index(cur_smethod) if cur_smethod in SHIP_METHOD else 0,
                        key="mgmt_ship_method")
                    edit_ship_number = sf2.text_input("出貨單號", value=safe_get(sel_order, "出貨單號"), key="mgmt_ship_num")

                    edit_note = st.text_area("備註", value=safe_get(sel_order,"備註"))

                    if st.form_submit_button("💾 儲存修改", use_container_width=True):
                        orders_df.loc[sel_idx, "客戶名稱"] = str(e_name)
                        orders_df.loc[sel_idx, "客戶電話"] = str(e_phone)
                        orders_df.loc[sel_idx, "建單人"]   = str(e_creator)
                        orders_df.loc[sel_idx, "商品種類"] = str(edit_type)
                        orders_df.loc[sel_idx, "客製品項"] = str(edit_item)
                        orders_df.loc[sel_idx, "總售價"]   = str(edit_price)
                        orders_df.loc[sel_idx, "成本"]     = str(edit_cost)
                        orders_df.loc[sel_idx, "運費"]     = str(edit_ship_fee)
                        orders_df.loc[sel_idx, "總成本"]   = str(edit_cost + edit_ship_fee)
                        orders_df.loc[sel_idx, "手圍"]     = str(edit_wrist)
                        orders_df.loc[sel_idx, "生日"]     = str(edit_bday)
                        orders_df.loc[sel_idx, "出生時間"] = str(edit_btime)
                        orders_df.loc[sel_idx, "喜神"]     = "、".join(edit_xi)
                        orders_df.loc[sel_idx, "忌神"]     = "、".join(edit_ji)
                        orders_df.loc[sel_idx, "出貨方式"] = str(edit_ship_method)
                        orders_df.loc[sel_idx, "出貨單號"] = str(edit_ship_number)
                        orders_df.loc[sel_idx, "備註"]     = str(edit_note)
                        save_orders(orders_df)
                        st.success("✅ 訂單已更新！")
                        time.sleep(1); st.rerun()

                st.divider()
                st.subheader("📌 變更狀態")
                cur_status = safe_get(sel_order, "狀態")
                cur_pay    = safe_get(sel_order, "付款狀態") or "未付款"
                cur_ship   = safe_get(sel_order, "出貨狀態") or "未出貨"

                PAY_OPTS  = ["未付款", "已付款", "已完成"]
                SHIP_OPTS = ["未出貨", "已出貨", "已完成"]

                col_pay, col_ship, col_cancel = st.columns(3)
                new_pay  = col_pay.selectbox(
                    "💰 付款狀態", PAY_OPTS,
                    index=PAY_OPTS.index(cur_pay) if cur_pay in PAY_OPTS else 0)
                new_ship = col_ship.selectbox(
                    "📦 出貨狀態", SHIP_OPTS,
                    index=SHIP_OPTS.index(cur_ship) if cur_ship in SHIP_OPTS else 0)

                def derive_combined_status(pay, ship, existing):
                    if pay == "已完成" and ship == "已完成":
                        return "已完成"
                    elif pay in ["已付款", "已完成"] and ship in ["已出貨", "已完成"]:
                        return "已完成"
                    elif pay in ["已付款", "已完成"]:
                        return "已付款未出貨"
                    elif ship in ["已出貨", "已完成"]:
                        return "未付款已出貨"
                    else:
                        return existing if existing in STATUS_FLOW else "已確認"

                if col_pay.button("💾 更新狀態", type="primary", use_container_width=True):
                    new_combined = derive_combined_status(new_pay, new_ship, cur_status)
                    orders_df.loc[sel_idx, "付款狀態"] = new_pay
                    orders_df.loc[sel_idx, "出貨狀態"] = new_ship
                    orders_df.loc[sel_idx, "狀態"]     = new_combined
                    save_orders(orders_df)
                    st.success(f"✅ 已更新｜付款：{new_pay}｜出貨：{new_ship}｜狀態：{new_combined}")
                    time.sleep(1.5); st.rerun()

                if col_cancel.button("❌ 取消訂單", use_container_width=True):
                    orders_df.loc[sel_idx, "狀態"]     = "已取消"
                    orders_df.loc[sel_idx, "付款狀態"] = "—"
                    orders_df.loc[sel_idx, "出貨狀態"] = "—"
                    save_orders(orders_df)
                    st.warning(f"{order_id} 已取消。")
                    time.sleep(1.5); st.rerun()

        with tab_done:
            if done_df.empty:
                st.info("尚無已完成或已取消的訂單。")
            else:
                st.dataframe(
                    done_df[["訂單編號","客戶名稱","商品種類","客製品項","總售價","狀態","付款狀態","出貨狀態","建立時間"]].iloc[::-1],
                    use_container_width=True, hide_index=True)
                st.caption(f"共 {len(done_df)} 筆已完成／已取消訂單")

                st.divider()
                done_df["display"] = done_df.apply(
                    lambda r: f"[{r['狀態']}] {r['訂單編號']} — {r['客戶名稱']} | {r['商品種類']} | ${r['總售價']}", axis=1)
                sel_done_disp = st.selectbox("選擇訂單查看", done_df["display"].tolist()[::-1], key="done_sel")
                done_idx   = done_df[done_df["display"] == sel_done_disp].index[0]
                done_order = orders_df.loc[done_idx]

                with st.container(border=True):
                    d1, d2, d3, d4, d5, d6, d7 = st.columns(7)
                    d1.metric("訂單編號", done_order["訂單編號"])
                    d2.metric("客戶",    safe_get(done_order, "客戶名稱"))
                    price_v = safe_get(done_order, "總售價")
                    cost_v  = safe_get(done_order, "成本")
                    ship_v  = safe_get(done_order, "運費")
                    tc_v    = safe_get(done_order, "總成本")
                    price_f = _safe_float(price_v)
                    cost_f  = _safe_float(cost_v)
                    ship_f  = _safe_float(ship_v)
                    tc_f    = _safe_float(tc_v) if tc_v else cost_f + ship_f
                    d3.metric("總售價", f"${price_f:,.0f}")
                    d4.metric("成本",   f"${cost_f:,.0f}")
                    d5.metric("運費",   f"${ship_f:,.0f}")
                    d6.metric("總成本", f"${tc_f:,.0f}")
                    d7.metric("利潤",   f"${price_f - tc_f:,.0f}")

                    st.write(
                        f"**狀態：** {safe_get(done_order, '狀態')} ｜ "
                        f"**付款狀態：** {safe_get(done_order,'付款狀態') or '-'} ｜ "
                        f"**出貨狀態：** {safe_get(done_order,'出貨狀態') or '-'} ｜ "
                        f"**商品種類：** {safe_get(done_order,'商品種類') or '-'} ｜ "
                        f"**客製品項：** {safe_get(done_order,'客製品項') or '-'} ｜ "
                        f"**建立時間：** {safe_get(done_order,'建立時間') or '-'}")
                    if safe_get(done_order, "備註"):
                        st.write(f"**備註：** {done_order['備註']}")

                    bday_val  = safe_get(done_order, "生日")
                    btime_val = safe_get(done_order, "出生時間")
                    if bday_val:
                        st.markdown("**📊 流年 × 階段數**")
                        render_numerology_table(bday_val, btime_val)

                st.divider()
                if safe_get(done_order, "狀態") == "已取消":
                    if st.button("↩️ 重新開啟此訂單", use_container_width=True):
                        orders_df.loc[done_idx, "狀態"] = "已確認"
                        save_orders(orders_df)
                        st.success("✅ 訂單已重新開啟！")
                        time.sleep(1); st.rerun()

# ==========================================
# § 8 訂單紀錄
# ==========================================
elif page == "📜 訂單紀錄":
    st.header("📜 訂單紀錄總覽")
    orders_df = load_orders()

    if orders_df.empty:
        st.info("目前沒有任何訂單。")
    else:
        done = orders_df[orders_df["狀態"]=="已完成"]
        try:
            rev       = done["總售價"].apply(lambda x: _safe_float(x)).sum()
            total_c   = done["成本"].apply(lambda x: _safe_float(x)).sum()
            total_s   = done["運費"].apply(lambda x: _safe_float(x)).sum()
            total_tc  = done["總成本"].apply(lambda x: _safe_float(x)).sum()
            if total_tc == 0:
                total_tc = total_c + total_s
        except Exception:
            rev = total_c = total_s = total_tc = 0

        c1, c2, c3, c4, c5, c6 = st.columns(6)
        c1.metric("總訂單數", f"{len(orders_df)} 筆")
        c2.metric("已完成",   f"{len(done)} 筆")
        c3.metric("進行中",   f"{len(orders_df[~orders_df['狀態'].isin(['已完成','已取消'])])} 筆")
        c4.metric("已完成總營收", f"${rev:,.0f}")
        c5.metric("已完成總成本", f"${total_tc:,.0f}")
        c6.metric("已完成總利潤", f"${rev - total_tc:,.0f}")

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

            new_delivery_type = st.selectbox("收件類型", DELIVERY_TYPES, key="add_delivery_type")
            if new_delivery_type == "🏪 超商":
                d3, d4 = st.columns(2)
                new_recv_addr  = d3.text_input("超商地址（選填）", placeholder="例：台北市信義區")
                new_store_name = d4.text_input("超商名稱／門市",  placeholder="例：7-11 台北信義門市")
            else:
                new_recv_addr  = st.text_input("收件地址", placeholder="例：台北市信義區信義路五段7號")
                new_store_name = ""

            if st.form_submit_button("✅ 新增客戶", use_container_width=True):
                if not new_name:
                    st.error("❌ 請填寫客戶名稱")
                elif new_name in customers_df["客戶名稱"].values:
                    st.error(f"❌ 客戶「{new_name}」已存在")
                else:
                    row = {
                        "客戶名稱":  new_name,
                        "客戶電話":  new_phone,
                        "手圍":     new_wrist,
                        "喜神":     "、".join(new_xi),
                        "忌神":     "、".join(new_ji),
                        "生日":     new_bday,
                        "出生時間":  new_btime,
                        "收件人姓名": new_recv_name,
                        "收件電話":  new_recv_phone,
                        "收件類型":  new_delivery_type,
                        "收件地址":  new_recv_addr,
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

            bday_val  = safe_get(cust_row, "生日")
            btime_val = safe_get(cust_row, "出生時間")
            if bday_val:
                st.markdown("#### 📊 流年 × 階段數（自動計算）")
                render_numerology_table(bday_val, btime_val)
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
                    if recv_type == "🏪 超商" and store_name:
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

                cur_dtype = safe_get(cust_row, "收件類型")
                dtype_idx = DELIVERY_TYPES.index(cur_dtype) if cur_dtype in DELIVERY_TYPES else 0
                ec_delivery_type = st.selectbox("收件類型", DELIVERY_TYPES,
                                                index=dtype_idx, key="edit_delivery_type")
                if ec_delivery_type == "🏪 超商":
                    ed3, ed4 = st.columns(2)
                    ec_recv_addr  = ed3.text_input("超商地址（選填）", value=safe_get(cust_row,"收件地址"))
                    ec_store_name = ed4.text_input("超商名稱／門市",   value=safe_get(cust_row,"超商名稱門市"))
                else:
                    ec_recv_addr  = st.text_input("收件地址", value=safe_get(cust_row,"收件地址"))
                    ec_store_name = ""

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
                            tbday  = safe_get(tc, "生日")
                            tbtime = safe_get(tc, "出生時間")
                            if tbday:
                                render_numerology_table(tbday, tbtime)
                            else:
                                st.caption("此客戶尚無生日資料")
                        else:
                            st.caption("此關聯客戶不在客戶資料庫中")

                st.divider()
                st.subheader("🗑️ 刪除關係")
                del_opts = [f"{r['對象']}（{r['關係類型']}）" for _, r in my_rels.iterrows()]
                del_sel  = st.selectbox("選擇要刪除的關係", del_opts, key="rel_del_sel")
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
                quick_sel = st.selectbox("快速選擇客戶",
                    ["── 手動輸入 ──"] + customers_df["客戶名稱"].tolist())
                if quick_sel != "── 手動輸入 ──":
                    row = customers_df[customers_df["客戶名稱"] == quick_sel].iloc[0]
                    input_bday  = safe_get(row, "生日")     or input_bday
                    input_btime = safe_get(row, "出生時間") or input_btime
                    st.info(f"已帶入：{quick_sel}（{input_bday}）")

    with col_b:
        if input_bday:
            parsed = parse_birthday(input_bday)
            if parsed:
                by, bm, bd = parsed
                birth_hour, birth_minute = parse_birth_time(input_btime)
                age   = calc_age(by, bm, bd)
                years = personal_year_range(bm, bd)
                today = datetime.now().date()

                passed    = (today.month, today.day) >= (bm, bd)
                bday_desc = f"生日 {bm}/{bd} 今年{'已過 ✅' if passed else '尚未到 ⏳'}"
                st.info(f"📅 {bday_desc}｜個人年基準：{years[1]} 年")

                st.subheader("📊 五階段數 × 流年對照")
                render_numerology_table(input_bday, input_btime)

                st.divider()
                st.subheader("📐 流年詳細計算過程")
                for yr, lbl in zip(years, ["去年","今年","明年"]):
                    ln = calc_liunian(yr, bm, bd)
                    ln_steps = " → ".join(str(x) for x in _reduce_chain(
                        sum(int(d) for d in (str(yr)+str(bm)+str(bd)))))
                    with st.expander(f"{yr}（{lbl}）— 流年 {ln.split('/')[-1]}"):
                        st.markdown(f"""
**流年計算：**
- 年份 {yr} + 月 {bm} + 日 {bd}
- 各位數字：{' + '.join(list(str(yr)+str(bm)+str(bd)))} = {sum(int(d) for d in str(yr)+str(bm)+str(bd))}
- 縮減過程：{ln_steps}
- **結果：{ln.split('/')[-1]}**
""")
            else:
                st.error("⚠️ 生日格式錯誤，請輸入 YYYY/MM/DD（例：2000/10/10）")
        else:
            st.info("👈 請在左側輸入生日")
