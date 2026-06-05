import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
# 台灣時區 (UTC+8)
TW_TZ = timezone(timedelta(hours=8))
def now_tw():
    return datetime.now(TW_TZ)
import time

# 台灣時區 (UTC+8)
TW_TZ = timezone(timedelta(hours=8))
def now_tw():
    """取得台灣時間"""
    return datetime.now(TW_TZ)

# ==========================================
# § 1 核心常數
# ==========================================
SHEET_ID = "1gf-pn034w0oZx8jWDUJvmIyHX_O7eHbiBb9diVSBX0Q"
KEY_FILE  = "google_key.json"

ORDER_COLUMNS = [
    '訂單編號', '建立時間', '客戶名稱', '客戶電話', '商品種類', '客製品項',
    '手圍', '生日', '農曆生日', '出生時間', '喜神', '忌神',
    '流年去年', '流年今年', '流年明年', '階段數',
    '總售價', '成本', '運費', '工本費', '總成本', '備註', '狀態', '建單人'
]

CUSTOM_ITEMS = ["手鍊", "項鍊", "鑰匙圈"]

CUSTOMER_COLUMNS = [
    '客戶名稱', '客戶電話', '手圍', '喜神', '忌神', '生日', '農曆生日', '出生時間',
    '流年去年', '流年今年', '流年明年', '階段數',
    '收件人姓名', '收件電話', '收件類型', '收件地址', '超商名稱門市'
]

DELIVERY_TYPES = ["🏠 住家", "🏪 超商"]

STATUS_FLOW    = ["未付款未出貨", "已付款未出貨", "未付款已出貨", "已完成", "已取消"]
WUXING_OPTS    = ["金", "木", "水", "火", "土"]

RELATIONSHIP_COLUMNS = ['客戶A', '關係類型', '客戶B', '備註', '建立時間']
RELATION_TYPES = [
    "👫 夫妻／伴侶", "👨‍👩‍👧 親子", "👫 兄弟姊妹",
    "👯 朋友", "🤝 介紹人→被介紹", "💼 同事", "🔗 其他"
]

# ── 庫存系統欄位 ──
INVENTORY_COLUMNS = [
    '編號', '批號', '倉庫', '分類', '名稱', '寬度mm', '長度mm', '形狀',
    '五行', '進貨數量(顆)', '進貨日期', '進貨廠商', '庫存(顆)', '成本單價'
]
HISTORY_COLUMNS = [
    '紀錄時間', '單號', '動作', '倉庫', '批號', '編號', '分類',
    '名稱', '規格', '廠商', '數量變動', '成本備註'
]
ORDER_ITEMS_COLUMNS = [
    '訂單編號', '庫存編號', '名稱', '五行', '形狀', '尺寸mm',
    '數量', '成本單價', '小計', '領料時間', '操作人'
]

# ==========================================
# § 2 數字學計算工具
# ==========================================
def _digit_sum(n):
    return sum(int(d) for d in str(n))

def _reduce_chain(n):
    """持續縮減到個位，回傳過程列表，例如 19 → [19, 10, 1]"""
    chain = [n]
    while n >= 10:
        n = _digit_sum(n)
        chain.append(n)
    return chain

def calc_liunian(year, birth_month, birth_day):
    """
    流年 = 年份所有數字 + 生日月數字 + 生日日數字，全部相加後縮減
    例：2025/10/10 → 2+0+2+5+1+0+1+0 = 11 → 1+1 = 2，顯示 "11/2"
    """
    digits_str = str(year) + str(birth_month) + str(birth_day)
    total = sum(int(d) for d in digits_str)
    chain = _reduce_chain(total)
    return "/".join(str(x) for x in chain)

def parse_time(time_str):
    """解析出生時間字串，回傳 (時, 分) 零補齊字串，例如 '8:30' → ('08', '30')"""
    if not time_str or not str(time_str).strip():
        return "", ""
    t = str(time_str).strip().replace("：", ":")
    if ":" in t:
        parts = t.split(":")
        h = parts[0].strip().zfill(2)
        m = parts[1].strip().zfill(2) if len(parts) > 1 and parts[1].strip() else "00"
        return h, m
    digits = ''.join(c for c in t if c.isdigit())
    if len(digits) >= 4:
        return digits[:2], digits[2:4]
    if len(digits) >= 2:
        return digits[:2], "00"
    return "", ""

STAGE_DEFS = [
    ("老年階段", "61歲以上"),
    ("中年階段", "41~60歲"),
    ("青年階段", "21~40歲"),
    ("少年階段", "11~20歲"),
    ("幼年階段", "0~10歲"),
]

def calc_five_stages(year, month, day, time_str=""):
    """
    計算五大階段數（生命藍圖數字學）
    第1階段（老年）：西元年
    第2階段（中年）：西元年 + 月
    第3階段（青年）：西元年 + 月 + 日
    第4階段（少年）：西元年 + 月 + 日 + 時
    第5階段（幼年）：西元年 + 月 + 日 + 時 + 分
    月/日/時/分 皆以兩位數計算（例：8月 → 08）
    回傳長度 5 的 list，每項為 dict: {name, age, digits_str, total, reduced, display}
    """
    hour, minute = parse_time(time_str)
    # 確保所有部位只含數字
    y = ''.join(c for c in str(year) if c.isdigit())
    m = ''.join(c for c in str(month) if c.isdigit()).zfill(2)
    d = ''.join(c for c in str(day) if c.isdigit()).zfill(2)
    hour = ''.join(c for c in hour if c.isdigit()) if hour else ""
    minute = ''.join(c for c in minute if c.isdigit()) if minute else ""

    digit_parts = [
        y,                                              # 老年：年
        y + m,                                          # 中年：年+月
        y + m + d,                                      # 青年：年+月+日
        (y + m + d + hour) if hour else None,           # 少年：年+月+日+時
        (y + m + d + hour + minute) if (hour and minute) else None,  # 幼年：全部
    ]

    results = []
    for i, (name, age) in enumerate(STAGE_DEFS):
        ds = digit_parts[i]
        if ds and all(c.isdigit() for c in ds):
            total = sum(int(c) for c in ds)
            chain = _reduce_chain(total)
            reduced = chain[-1]
            display = "/".join(str(x) for x in chain)
        else:
            ds, total, reduced, display = None, None, None, "—"
        results.append({"name": name, "age": age, "digits_str": ds,
                        "total": total, "reduced": reduced, "display": display})
    return results

def get_current_stage_index(birth_year, birth_month, birth_day):
    """根據目前年齡回傳階段 index (0=老年 1=中年 2=青年 3=少年 4=幼年)"""
    today = datetime.now().date()
    age = today.year - birth_year
    if (today.month, today.day) < (birth_month, birth_day):
        age -= 1
    if age <= 10:  return 4
    if age <= 20:  return 3
    if age <= 40:  return 2
    if age <= 60:  return 1
    return 0

def get_current_jieduan(birth_year, birth_month, birth_day, birth_time_str=""):
    """取得目前年齡對應的階段數顯示值（供儲存到 Google Sheets）"""
    stages = calc_five_stages(birth_year, birth_month, birth_day, birth_time_str)
    idx = get_current_stage_index(birth_year, birth_month, birth_day)
    return stages[idx]['display']

def personal_year_range(birth_month, birth_day, today=None):
    """
    依生日是否已過決定三個年份（去年/今年/明年，以個人年為基準）
    ・尚未過生日 → 個人年 = 本曆年 - 1
    ・已過生日   → 個人年 = 本曆年
    範例（今天 2026-04-28）：
      生日 10/10 → 尚未過 → 個人年 2025 → 顯示 [2024, 2025, 2026]
      生日  3/01 → 已過   → 個人年 2026 → 顯示 [2025, 2026, 2027]
    """
    if today is None:
        today = datetime.now().date()
    birthday_passed = (today.month, today.day) >= (birth_month, birth_day)
    personal_year = today.year if birthday_passed else today.year - 1
    return [personal_year - 1, personal_year, personal_year + 1]

def parse_birthday(bday_str):
    """解析生日字串（YYYY/MM/DD 或 YYYY-MM-DD），回傳 (year, month, day) 或 None"""
    if not bday_str or not str(bday_str).strip():
        return None
    for fmt in ("%Y/%m/%d", "%Y-%m-%d"):
        try:
            d = datetime.strptime(str(bday_str).strip(), fmt)
            return d.year, d.month, d.day
        except ValueError:
            pass
    return None

def render_numerology_table(bday_str, lunar_bday_str="", birth_time_str=""):
    """顯示五大階段數 + 三年流年對照表，成功回傳 True"""
    parsed = parse_birthday(bday_str)
    if not parsed:
        st.warning("⚠️ 生日格式錯誤，請使用 YYYY/MM/DD（例：2000/10/10）")
        return False
    by, bm, bd = parsed
    btime = str(birth_time_str).strip() if birth_time_str else ""

    # ── 五大階段數 ──
    solar_stages = calc_five_stages(by, bm, bd, btime)
    cur_idx = get_current_stage_index(by, bm, bd)
    today = datetime.now().date()
    age = today.year - by - (1 if (today.month, today.day) < (bm, bd) else 0)

    lunar_parsed = parse_birthday(lunar_bday_str) if lunar_bday_str else None
    lunar_stages = None
    if lunar_parsed:
        ly, lm, ld = lunar_parsed
        lunar_stages = calc_five_stages(ly, lm, ld, btime)

    cur_stage = solar_stages[cur_idx]
    st.markdown(f"**📊 五大階段數**　｜　目前年齡：**{age}歲**（{cur_stage['name']}）")

    # 各階段對應的生日部位
    hour, minute = parse_time(btime)
    solar_parts = [str(by), str(bm).zfill(2), str(bd).zfill(2),
                   hour or "—", minute or "—"]
    lunar_parts = None
    if lunar_parsed:
        lunar_parts = [str(ly), str(lm).zfill(2), str(ld).zfill(2),
                       hour or "—", minute or "—"]
    part_labels = ["西元年", "月", "日", "時", "分"]

    cols = st.columns(5)
    for i, col in enumerate(cols):
        s = solar_stages[i]
        with col:
            is_cur = (i == cur_idx)
            if is_cur:
                st.markdown(f"🔹 **{s['name']}**")
            else:
                st.markdown(f"**{s['name']}**")
            st.caption(s['age'])
            solar_disp = f"**{s['display']}**" if is_cur else s['display']
            st.markdown(f"🌞 {solar_parts[i]}")
            st.markdown(f"　　{solar_disp}")
            if lunar_stages and lunar_parts:
                ls = lunar_stages[i]
                lunar_disp = f"**{ls['display']}**" if is_cur else ls['display']
                st.markdown(f"🌙 {lunar_parts[i]}")
                st.markdown(f"　　{lunar_disp}")

    if not btime:
        st.caption("💡 填寫「出生時間」可計算少年與幼年階段數")

    # ── 三年流年表 ──
    years  = personal_year_range(bm, bd)
    labels = ["去年", "今年", "明年"]
    rows = []
    for yr, lbl in zip(years, labels):
        ln = calc_liunian(yr, bm, bd)
        ln_final = ln.split("/")[-1]
        rows.append({
            "年份":     f"{yr}（{lbl}）",
            "流年計算": f"{yr}年 + {bm}月 + {bd}日 → {ln}",
            "流年數":   ln_final,
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

@st.cache_data(ttl=120, show_spinner=False)
def _load_sheet_cached(tab, columns_tuple):
    """帶快取的 Google Sheets 讀取（120 秒內不重複呼叫 API）
    注意：失敗時拋出例外（不會被快取），只快取成功結果。"""
    columns = list(columns_tuple)
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

def _load_sheet(tab, columns):
    """讀取工作表，失敗時自動重連一次；仍失敗則顯示錯誤並回傳空 DataFrame"""
    try:
        return _load_sheet_cached(tab, tuple(columns))
    except Exception:
        # 第一次失敗 → 清除快取、重新授權後重試
        try:
            _load_sheet_cached.clear()
            get_gs_client.clear()
            return _load_sheet_cached(tab, tuple(columns))
        except Exception as e2:
            err_type = type(e2).__name__
            err_msg  = str(e2) or "(無錯誤訊息)"
            st.error(f"讀取 {tab} 失敗 [{err_type}]: {err_msg}")
            return pd.DataFrame(columns=columns)

def _save_sheet(tab, df):
    def _do_save():
        wb = get_gs_client().open_by_key(SHEET_ID)
        try:
            ws = wb.worksheet(tab)
        except gspread.exceptions.WorksheetNotFound:
            ws = wb.add_worksheet(title=tab, rows="1000", cols="20")
        data = df.fillna("").astype(str)
        ws.clear()
        ws.update(range_name='A1', values=[data.columns.tolist()] + data.values.tolist())
    try:
        _do_save()
        _load_sheet_cached.clear()
    except Exception:
        try:
            get_gs_client.clear()
            _load_sheet_cached.clear()
            _do_save()
        except Exception as e2:
            err_type = type(e2).__name__
            err_msg  = str(e2) or "(無錯誤訊息)"
            st.error(f"儲存 {tab} 失敗 [{err_type}]: {err_msg}")

def fill_numerology(df: pd.DataFrame) -> pd.DataFrame:
    """
    根據每列的「生日」欄位，自動填入：
      流年去年 / 流年今年 / 流年明年 / 階段數
    沒有生日或格式錯誤時留空。
    """
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
        btime_str = str(row.get("出生時間", "")).strip() if "出生時間" in row.index else ""
        try:
            years = personal_year_range(bm, bd)
            df.loc[idx, "流年去年"] = calc_liunian(years[0], bm, bd)
            df.loc[idx, "流年今年"] = calc_liunian(years[1], bm, bd)
            df.loc[idx, "流年明年"] = calc_liunian(years[2], bm, bd)
            df.loc[idx, "階段數"]   = get_current_jieduan(by, bm, bd, btime_str)
        except Exception:
            df.loc[idx, ["流年去年", "流年今年", "流年明年", "階段數"]] = ""
    return df

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
        cost     = _safe_float(row.get("成本", 0))
        shipping = _safe_float(row.get("運費", 0))
        labor    = _safe_float(row.get("工本費", 0))
        df.loc[idx, "總成本"] = str(cost + shipping + labor)
    return df

def load_orders():          return _load_sheet("Orders",        ORDER_COLUMNS)
def save_orders(df):        _save_sheet("Orders", calc_total_cost(fill_numerology(df)))
def load_customers():       return _load_sheet("Customers",     CUSTOMER_COLUMNS)
def save_customers(df):     _save_sheet("Customers",     fill_numerology(df))
def load_relationships():   return _load_sheet("Relationships", RELATIONSHIP_COLUMNS)
def save_relationships(df): _save_sheet("Relationships", df)

# ── 庫存系統讀寫 ──
def load_inventory():       return _load_sheet("Inventory",  INVENTORY_COLUMNS)
def load_history():         return _load_sheet("History",    HISTORY_COLUMNS)
def load_order_items():     return _load_sheet("OrderItems", ORDER_ITEMS_COLUMNS)
def save_inventory(df):     _save_sheet("Inventory",  df)
def save_history(df):       _save_sheet("History",    df)
def save_order_items(df):   _save_sheet("OrderItems", df)

def get_order_items(order_id, items_df):
    if items_df.empty or not order_id:
        return pd.DataFrame(columns=ORDER_ITEMS_COLUMNS)
    return items_df[items_df["訂單編號"] == order_id].copy()

def calc_order_material_cost(order_id, items_df):
    oi = get_order_items(order_id, items_df)
    if oi.empty:
        return 0.0
    return oi["小計"].apply(lambda x: _safe_float(x)).sum()

def pick_inventory_item(order_id, inv_row, qty, operator, inv_df, items_df, hist_df):
    inv_id    = inv_row["編號"]
    cur_stock = _safe_float(inv_row["庫存(顆)"])
    unit_cost = _safe_float(inv_row["成本單價"])
    if qty <= 0:
        return inv_df, items_df, hist_df, "數量必須大於 0"
    if qty > cur_stock:
        return inv_df, items_df, hist_df, f"庫存不足（剩 {cur_stock:.0f} 顆）"
    now_str  = datetime.now().strftime("%Y-%m-%d %H:%M")
    subtotal = qty * unit_cost
    inv_idx  = inv_df[inv_df["編號"] == inv_id].index[0]
    inv_df.loc[inv_idx, "庫存(顆)"] = str(cur_stock - qty)
    new_item = {"訂單編號": order_id, "庫存編號": inv_id,
                "名稱": inv_row["名稱"], "五行": inv_row["五行"],
                "形狀": inv_row["形狀"], "尺寸mm": inv_row["寬度mm"],
                "數量": str(qty), "成本單價": str(unit_cost),
                "小計": str(subtotal), "領料時間": now_str, "操作人": operator}
        # 先計算此訂單之前的累計成本，再加上本次小計
    prev_cost = calc_order_material_cost(order_id, items_df)
    items_df = pd.concat([items_df, pd.DataFrame([new_item])], ignore_index=True)
    order_total = prev_cost + subtotal
    cost_note = f"[總${order_total:.1f}] 單價${unit_cost} x{qty}=${subtotal:.1f}"
    new_hist = {"紀錄時間": now_str, "單號": order_id, "動作": "訂單領料",
                "倉庫": inv_row.get("倉庫",""), "批號": inv_row.get("批號",""),
                "編號": inv_id, "分類": inv_row.get("分類",""),
                "名稱": inv_row["名稱"],
                "規格": f"{inv_row['形狀']} {inv_row['寬度mm']}mm",
                "廠商": inv_row.get("進貨廠商",""),
                "數量變動": str(-qty),
                "成本備註": cost_note}
    hist_df = pd.concat([hist_df, pd.DataFrame([new_hist])], ignore_index=True)
    return inv_df, items_df, hist_df, None

def return_inventory_item(order_id, item_row, inv_df, items_df, hist_df):
    inv_id  = item_row["庫存編號"]
    qty     = _safe_float(item_row["數量"])
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    inv_match = inv_df[inv_df["編號"] == inv_id]
    if not inv_match.empty:
        inv_idx = inv_match.index[0]
        inv_df.loc[inv_idx, "庫存(顆)"] = str(_safe_float(inv_df.loc[inv_idx, "庫存(顆)"]) + qty)
    mask = ((items_df["訂單編號"] == order_id) & (items_df["庫存編號"] == inv_id)
            & (items_df["領料時間"] == item_row["領料時間"]))
    items_df = items_df[~mask].reset_index(drop=True)
    new_hist = {"紀錄時間": now_str, "單號": order_id, "動作": "訂單退料",
                "倉庫": "", "批號": "", "編號": inv_id, "分類": "",
                "名稱": item_row["名稱"],
                "規格": f"{item_row['形狀']} {item_row['尺寸mm']}mm",
                "廠商": "", "數量變動": str(qty),
                "成本備註": f"退回 {qty:.0f} 顆"}
    hist_df = pd.concat([hist_df, pd.DataFrame([new_hist])], ignore_index=True)
    return inv_df, items_df, hist_df

def get_customer_relations(name: str, rel_df: pd.DataFrame) -> pd.DataFrame:
    """取得某客戶所有關係（含正向與反向）"""
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
    """安全取得 Series 欄位值，避免 KeyError"""
    try:
        val = row[col]
        return val if pd.notna(val) and str(val).strip() else default
    except (KeyError, TypeError):
        return default

def get_lunar_bday(order_row, customers_df):
    """
    取得農曆生日：優先用訂單自身的值；
    若訂單農曆生日空白，則從客戶資料表查詢同名客戶的農曆生日。
    """
    val = safe_get(order_row, "農曆生日")
    if val:
        return val
    if customers_df is not None and not customers_df.empty:
        name = safe_get(order_row, "客戶名稱")
        match = customers_df[customers_df["客戶名稱"] == name]
        if not match.empty:
            return safe_get(match.iloc[0], "農曆生日")
    return ""

def sync_lunar_bday_to_customer(name, lunar_bday, customers_df):
    """
    當訂單填入農曆生日後，自動同步回客戶資料表（若客戶存在且原本為空）。
    回傳更新後的 customers_df。
    """
    if not lunar_bday or customers_df is None or customers_df.empty:
        return customers_df
    idx_list = customers_df[customers_df["客戶名稱"] == name].index
    if len(idx_list) == 0:
        return customers_df
    idx = idx_list[0]
    if not safe_get(customers_df.loc[idx], "農曆生日"):
        customers_df.loc[idx, "農曆生日"] = lunar_bday
        save_customers(customers_df)
    return customers_df

def sync_customers_from_orders():
    """
    掃描 Orders 表，將尚未存在於 Customers 表的客戶自動新增進去。
    已存在的客戶不覆蓋。回傳新增數量。
    """
    orders_df    = load_orders()
    customers_df = load_customers()

    if orders_df.empty:
        return 0

    existing_names = set(customers_df["客戶名稱"].tolist())
    new_rows = []

    # 對每個客戶名稱，取最新一筆訂單的資料
    for name, group in orders_df.groupby("客戶名稱"):
        if not name or name in existing_names:
            continue
        latest = group.iloc[-1]  # 最新訂單
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
        "🔄 訂單管理",
        "📦 訂單領料",
        "📜 訂單紀錄",
        "💰 收益表",
        "👥 客戶管理",
        "🔗 關係鏈結",
        "🔢 數字學計算",
    ])
    if st.button("🔄 刷新資料"):
        get_gs_client.clear()
        _load_sheet_cached.clear()
        st.rerun()

    # ── 未完成提醒 ──
    st.divider()
    _all_orders_sb = load_orders()
    _unshipped_sb  = _all_orders_sb[
        ~_all_orders_sb["狀態"].isin(["已完成", "已取消"])
    ] if not _all_orders_sb.empty else pd.DataFrame()
    if not _unshipped_sb.empty:
        st.error(f"🚨 未完成訂單：{len(_unshipped_sb)} 筆")
        for _, _r in _unshipped_sb.iterrows():
            st.caption(f"• {_r['訂單編號']} — {_r['客戶名稱']} [{_r['狀態']}]")
    else:
        st.success("✅ 所有訂單已完成")

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

    customers_df = load_customers()
    customer_list = customers_df["客戶名稱"].tolist() if not customers_df.empty else []

    st.subheader("👤 客戶選擇")
    use_existing = st.toggle("從現有客戶帶入資料", value=bool(customer_list))

    prefill = {}
    if use_existing and customer_list:
        sel_customer = st.selectbox("選擇客戶", ["── 請選擇 ──"] + customer_list)
        if sel_customer != "── 請選擇 ──":
            _raw = customers_df[customers_df["客戶名稱"] == sel_customer].iloc[0].to_dict()
            # 清理 NaN → 空字串，避免表單欄位帶入 NaN
            prefill = {k: ("" if pd.isna(v) else str(v).strip()) for k, v in _raw.items()}
            bday_str = prefill.get("生日", "")
            lunar_str = prefill.get("農曆生日", "")
            btime_str = prefill.get("出生時間", "")
            if bday_str:
                st.markdown("#### 📊 流年 × 階段數 三年對照表")
                render_numerology_table(bday_str, lunar_str, btime_str)
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
        product_type  = c3.selectbox("商品種類", ["客製", "公版", "修改"])
        custom_item   = c4.selectbox("客製品項", CUSTOM_ITEMS)
        order_creator = c5.selectbox("建單人",   ["Imeng", "千畇"])

        p1, p2, p3, p4 = st.columns(4)
        total_price   = p1.number_input("總售價 ($)", min_value=0.0, value=0.0)
        cost_price    = p2.number_input("成本 ($)",   min_value=0.0, value=0.0)
        shipping_fee  = p3.number_input("運費 ($)",   min_value=0.0, value=0.0)
        labor_fee     = p4.number_input("工本費 ($)", min_value=0.0, value=0.0)
        _tc = cost_price + shipping_fee + labor_fee
        if _tc > 0:
            st.caption(f"💰 總成本 = ${cost_price:,.0f} + ${shipping_fee:,.0f} + ${labor_fee:,.0f} = **${_tc:,.0f}**")

        st.subheader("手鍊 & 出生資訊")
        b1, b2, b2b, b3 = st.columns(4)
        wrist_size   = b1.text_input("手圍",                   value=prefill.get("手圍", ""))
        birthday     = b2.text_input("國曆生日（YYYY/MM/DD）", value=prefill.get("生日", ""),
                                     placeholder="例：2000/10/10")
        lunar_birthday = b2b.text_input("農曆生日（YYYY/MM/DD）", value=prefill.get("農曆生日", ""),
                                        placeholder="例：2000/09/01")
        birth_time   = b3.text_input("出生時間（HH:MM）",     value=prefill.get("出生時間", ""),
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
                    "農曆生日": lunar_birthday,
                    "出生時間": birth_time,
                    "喜神":     "、".join(xi_shen),
                    "忌神":     "、".join(ji_shen),
                    "總售價":   str(total_price),
                    "成本":     str(cost_price),
                    "運費":     str(shipping_fee),
                    "工本費":   str(labor_fee),
                    "總成本":   str(cost_price + shipping_fee + labor_fee),
                    "備註":     order_note,
                    "狀態":     "未付款未出貨",
                    "建單人":   order_creator,
                }
                orders_df = pd.concat([orders_df, pd.DataFrame([new_order])], ignore_index=True)
                save_orders(orders_df)
                st.success(f"✅ 訂單 {order_id} 已建立！")
                time.sleep(1.5)
                st.rerun()

# ==========================================
# § 6+7 訂單管理（整合列表 + 狀態變更 + 修改）
# ==========================================
elif page == "🔄 訂單管理":
    st.header("🔄 訂單管理")
    orders_df = load_orders()

    if orders_df.empty:
        st.info("目前沒有任何訂單。")
    else:
        _cust_df_7 = load_customers()

        # ── 訂單統計摘要 ──
        pending = orders_df[~orders_df["狀態"].isin(["已完成", "已取消"])].copy()
        n_pending = len(pending)
        n_done    = len(orders_df[orders_df["狀態"] == "已完成"])
        n_cancel  = len(orders_df[orders_df["狀態"] == "已取消"])

        s1, s2, s3 = st.columns(3)
        s1.metric("🚨 未完成訂單", f"{n_pending} 筆")
        s2.metric("✅ 已完成訂單", f"{n_done} 筆")
        s3.metric("❌ 已取消訂單", f"{n_cancel} 筆")

        # ── 未完成訂單明細 ──
        if not pending.empty:
            with st.container(border=True):
                st.markdown(f"### 🚨 未完成訂單 — 共 **{n_pending}** 筆")
                cols_h = st.columns([2, 2, 2, 2])
                cols_h[0].markdown("**訂單編號**")
                cols_h[1].markdown("**客戶名稱**")
                cols_h[2].markdown("**商品種類**")
                cols_h[3].markdown("**目前狀態**")
                for _, urow in pending.iterrows():
                    r1, r2, r3, r4 = st.columns([2, 2, 2, 2])
                    r1.write(urow.get("訂單編號", ""))
                    r2.write(urow.get("客戶名稱", ""))
                    r3.write(urow.get("商品種類", ""))
                    s = urow.get("狀態", "")
                    if s == "未付款未出貨":    status_icon = "🔴"
                    elif s == "已付款未出貨":  status_icon = "🟡"
                    elif s == "未付款已出貨":  status_icon = "🟠"
                    elif s in ("已確認", "已出貨"): status_icon = "🔵"
                    else:                      status_icon = "⚪"
                    r4.write(f"{status_icon} {s}")

        # ── 訂單列表（篩選 + 搜尋）──
        st.divider()
        st.subheader("📋 所有訂單列表")
        fc1, fc2 = st.columns(2)
        status_filter   = fc1.selectbox("篩選狀態", ["全部"] + STATUS_FLOW)
        search_customer = fc2.text_input("搜尋客戶名稱")

        disp = orders_df.copy()
        if status_filter != "全部":
            disp = disp[disp["狀態"] == status_filter]
        if search_customer:
            disp = disp[disp["客戶名稱"].str.contains(search_customer, case=False, na=False)]

        if disp.empty:
            st.info("篩選後沒有訂單。")
        else:
            disp_show = disp.copy()
            disp_show["利潤"] = disp_show.apply(
                lambda r: _safe_float(r.get("總售價", 0)) - _safe_float(r.get("總成本", 0)), axis=1)
            # 將利潤欄位插入總成本與備註之間
            cols = list(disp_show.columns)
            cols.remove("利潤")
            tc_pos = cols.index("總成本") + 1
            cols.insert(tc_pos, "利潤")
            disp_show = disp_show[cols]
            st.dataframe(disp_show.iloc[::-1], use_container_width=True)
            st.caption(f"共 {len(disp_show)} 筆訂單")

        # ── 選擇訂單進行管理 ──
        st.divider()
        all_display = orders_df.apply(
            lambda r: f"[{r['狀態']}] {r['訂單編號']} — {r['客戶名稱']} | {r['商品種類']} | ${r['總售價']}", axis=1)
        sel_disp  = st.selectbox("選擇要管理的訂單", all_display.tolist()[::-1])
        sel_idx   = orders_df[all_display == sel_disp].index[0]
        sel_order = orders_df.loc[sel_idx]
        order_id  = sel_order["訂單編號"]

        # ── 訂單摘要卡片 ──
        with st.container(border=True):
            c1, c2, c3, c4, c5, c6 = st.columns(6)
            c1.metric("訂單編號", order_id)
            c2.metric("客戶",    safe_get(sel_order, "客戶名稱"))
            price_v = safe_get(sel_order, "總售價")
            tc_v    = safe_get(sel_order, "總成本")
            price_f = _safe_float(price_v)
            tc_f    = _safe_float(tc_v)
            c3.metric("總售價",  f"${price_f:,.0f}")
            c4.metric("總成本",  f"${tc_f:,.0f}")
            profit = price_f - tc_f
            c5.metric("利潤",    f"${profit:,.0f}",
                      delta=f"{(profit/price_f*100):.0f}%" if price_f else None)
            c6.metric("目前狀態", safe_get(sel_order, "狀態"))

            st.write(
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

            bday_val = safe_get(sel_order, "生日")
            lunar_val = get_lunar_bday(sel_order, _cust_df_7)
            btime_val = safe_get(sel_order, "出生時間")
            if bday_val:
                st.markdown("**📊 流年 × 階段數 三年對照表**")
                render_numerology_table(bday_val, lunar_val, btime_val)

        # ── 修改訂單 ──
        st.divider()
        st.subheader("✏️ 修改訂單")
        _oid = order_id  # 綁定 key，切換訂單時自動重置欄位
        with st.form(f"edit_order_form_{_oid}"):
            ce0a, ce0b = st.columns(2)
            cur_otype = safe_get(sel_order,"商品種類")
            edit_type = ce0a.selectbox("商品種類", ["客製","公版","修改"],
                index=["客製","公版","修改"].index(cur_otype) if cur_otype in ["客製","公版","修改"] else 0,
                key=f"etype_{_oid}")
            cur_oitem = safe_get(sel_order,"客製品項")
            edit_item = ce0b.selectbox("客製品項", CUSTOM_ITEMS,
                index=CUSTOM_ITEMS.index(cur_oitem) if cur_oitem in CUSTOM_ITEMS else 0,
                key=f"eitem_{_oid}")

            # 檢查是否有領料紀錄 → 成本由領料系統自動計算
            _items_df_chk = load_order_items()
            _has_picked = not get_order_items(_oid, _items_df_chk).empty
            _picked_cost = calc_order_material_cost(_oid, _items_df_chk) if _has_picked else 0.0

            ce1, ce2, ce3, ce4 = st.columns(4)
            edit_price = ce1.number_input("總售價 ($)",
                value=_safe_float(safe_get(sel_order,"總售價")), key=f"eprice_{_oid}")
            if _has_picked:
                ce2.metric("材料成本（領料）", f"${_picked_cost:,.0f}")
                edit_cost = _picked_cost  # 鎖定為領料成本
            else:
                edit_cost = ce2.number_input("成本 ($)",
                    value=_safe_float(safe_get(sel_order,"成本")), key=f"ecost_{_oid}")
            edit_ship  = ce3.number_input("運費 ($)",
                value=_safe_float(safe_get(sel_order,"運費")), key=f"eship_{_oid}")
            edit_labor = ce4.number_input("工本費 ($)",
                value=_safe_float(safe_get(sel_order,"工本費")), key=f"elabor_{_oid}")
            _etc = edit_cost + edit_ship + edit_labor
            if _etc > 0:
                st.caption(f"💰 總成本 ${_etc:,.0f} ｜ 利潤 ${edit_price - _etc:,.0f}")
            if _has_picked:
                st.caption("ℹ️ 此訂單已有領料紀錄，材料成本由領料系統自動計算，無法手動修改。")

            cn1, cn2 = st.columns(2)
            edit_name  = cn1.text_input("客戶名稱", value=safe_get(sel_order, "客戶名稱"), key=f"ename_{_oid}")
            edit_phone = cn2.text_input("客戶電話", value=safe_get(sel_order, "客戶電話"), key=f"ephone_{_oid}")

            cw1, cw2, cw3, cw4 = st.columns(4)
            edit_wrist      = cw1.text_input("手圍",                    value=safe_get(sel_order,"手圍"), key=f"ewrist_{_oid}")
            edit_bday       = cw2.text_input("國曆生日（YYYY/MM/DD）",  value=safe_get(sel_order,"生日"), key=f"ebday_{_oid}")
            edit_lunar_bday = cw3.text_input("農曆生日（YYYY/MM/DD）", value=get_lunar_bday(sel_order, _cust_df_7), key=f"elunar_{_oid}")
            edit_btime      = cw4.text_input("出生時間（HH:MM）",       value=safe_get(sel_order,"出生時間"), key=f"ebtime_{_oid}")

            ce5, ce6 = st.columns(2)
            cx_v = safe_get(sel_order,"喜神")
            cj_v = safe_get(sel_order,"忌神")
            cx = [x for x in cx_v.split("、") if x in WUXING_OPTS] if cx_v else []
            cj = [x for x in cj_v.split("、") if x in WUXING_OPTS] if cj_v else []
            edit_xi = ce5.multiselect("喜神", WUXING_OPTS, default=cx, key=f"exi_{_oid}")
            edit_ji = ce6.multiselect("忌神", WUXING_OPTS, default=cj, key=f"eji_{_oid}")

            cur_status = safe_get(sel_order, "狀態")
            e_status = st.selectbox("狀態", STATUS_FLOW,
                index=STATUS_FLOW.index(cur_status) if cur_status in STATUS_FLOW else 0,
                key=f"estatus_{_oid}")
            edit_note = st.text_area("備註", value=safe_get(sel_order, "備註"), key=f"enote_{_oid}")

            if st.form_submit_button("💾 儲存修改", use_container_width=True):
                # 有領料紀錄時，強制使用領料成本（防止被手動覆蓋）
                final_cost = _picked_cost if _has_picked else edit_cost
                orders_df.loc[sel_idx, "客戶名稱"] = str(edit_name)
                orders_df.loc[sel_idx, "客戶電話"] = str(edit_phone)
                orders_df.loc[sel_idx, "手圍"]     = str(edit_wrist)
                orders_df.loc[sel_idx, "生日"]     = str(edit_bday)
                orders_df.loc[sel_idx, "農曆生日"] = str(edit_lunar_bday)
                orders_df.loc[sel_idx, "出生時間"] = str(edit_btime)
                orders_df.loc[sel_idx, "商品種類"] = str(edit_type)
                orders_df.loc[sel_idx, "客製品項"] = str(edit_item)
                orders_df.loc[sel_idx, "總售價"]   = str(edit_price)
                orders_df.loc[sel_idx, "成本"]     = str(final_cost)
                orders_df.loc[sel_idx, "運費"]     = str(edit_ship)
                orders_df.loc[sel_idx, "工本費"]   = str(edit_labor)
                orders_df.loc[sel_idx, "總成本"]   = str(final_cost + edit_ship + edit_labor)
                orders_df.loc[sel_idx, "喜神"]     = "、".join(edit_xi)
                orders_df.loc[sel_idx, "忌神"]     = "、".join(edit_ji)
                orders_df.loc[sel_idx, "狀態"]     = str(e_status)
                orders_df.loc[sel_idx, "備註"]     = str(edit_note)
                save_orders(orders_df)
                sync_lunar_bday_to_customer(str(edit_name), str(edit_lunar_bday), _cust_df_7)
                st.success(f"✅ 訂單 {order_id} 已更新！")
                time.sleep(1); st.rerun()

        # ── 快速變更狀態 ──
        st.divider()
        st.subheader("📌 快速變更狀態")
        cur_status = safe_get(sel_order, "狀態")

        if cur_status == "未付款未出貨":
            ca, cb, cc = st.columns(3)
            if ca.button("💰 已付款", type="primary", use_container_width=True):
                orders_df.loc[sel_idx,"狀態"] = "已付款未出貨"
                save_orders(orders_df); st.success(f"✅ {order_id} 已付款")
                time.sleep(1.5); st.rerun()
            if cb.button("📦 已出貨", type="primary", use_container_width=True):
                orders_df.loc[sel_idx,"狀態"] = "未付款已出貨"
                save_orders(orders_df); st.success(f"✅ {order_id} 已出貨")
                time.sleep(1.5); st.rerun()
            if cc.button("❌ 取消訂單", use_container_width=True):
                orders_df.loc[sel_idx,"狀態"] = "已取消"
                save_orders(orders_df); st.warning(f"{order_id} 已取消。")
                time.sleep(1.5); st.rerun()

        elif cur_status == "已付款未出貨":
            ca, cb = st.columns(2)
            if ca.button("📦 已出貨 → 完成", type="primary", use_container_width=True):
                orders_df.loc[sel_idx,"狀態"] = "已完成"
                save_orders(orders_df); st.success(f"🎉 {order_id} 已完成！")
                time.sleep(1.5); st.rerun()
            if cb.button("❌ 取消訂單", use_container_width=True):
                orders_df.loc[sel_idx,"狀態"] = "已取消"
                save_orders(orders_df); st.warning(f"{order_id} 已取消。")
                time.sleep(1.5); st.rerun()

        elif cur_status == "未付款已出貨":
            ca, cb = st.columns(2)
            if ca.button("💰 已付款 → 完成", type="primary", use_container_width=True):
                orders_df.loc[sel_idx,"狀態"] = "已完成"
                save_orders(orders_df); st.success(f"🎉 {order_id} 已完成！")
                time.sleep(1.5); st.rerun()
            if cb.button("❌ 取消訂單", use_container_width=True):
                orders_df.loc[sel_idx,"狀態"] = "已取消"
                save_orders(orders_df); st.warning(f"{order_id} 已取消。")
                time.sleep(1.5); st.rerun()

        elif cur_status in ("已完成", "已取消"):
            st.info(f"此訂單狀態為「{cur_status}」，無需進一步操作。")

# ==========================================
# § 7.5 訂單領料（庫存扣存）
# ==========================================
elif page == "📦 訂單領料":
    st.header("📦 訂單領料 — 庫存扣存")
    orders_df = load_orders()

    if orders_df.empty:
        st.info("目前沒有任何訂單。")
    else:
        # 篩選狀態
        pick_status_filter = st.selectbox(
            "篩選訂單狀態", ["進行中", "已完成", "已取消", "全部"],
            key="pick_status_filter")
        if pick_status_filter == "進行中":
            active_pick = orders_df[~orders_df["狀態"].isin(["已完成", "已取消"])].copy()
        elif pick_status_filter == "已完成":
            active_pick = orders_df[orders_df["狀態"] == "已完成"].copy()
        elif pick_status_filter == "已取消":
            active_pick = orders_df[orders_df["狀態"] == "已取消"].copy()
        else:
            active_pick = orders_df.copy()

        if active_pick.empty:
            st.info("此狀態下沒有訂單。")
        else:
            active_pick["display"] = active_pick.apply(
                lambda r: f"[{r['狀態']}] {r['訂單編號']} — {r['客戶名稱']} | {r['客製品項']}", axis=1)
            sel_pick_disp = st.selectbox("選擇訂單", active_pick["display"].tolist()[::-1])
            sel_pick_idx  = active_pick[active_pick["display"] == sel_pick_disp].index[0]
            sel_pick_order = orders_df.loc[sel_pick_idx]
            pick_order_id  = sel_pick_order["訂單編號"]

            # ── 訂單摘要卡片 ──
            with st.container(border=True):
                pc1, pc2, pc3, pc4 = st.columns(4)
                pc1.metric("訂單編號", pick_order_id)
                pc2.metric("客戶", safe_get(sel_pick_order, "客戶名稱"))
                pc3.metric("品項", safe_get(sel_pick_order, "客製品項"))
                pc4.metric("狀態", safe_get(sel_pick_order, "狀態"))

            # ── 已領料清單 ──
            st.divider()
            st.subheader("📋 已領料明細")
            items_df = load_order_items()
            cur_items = get_order_items(pick_order_id, items_df)

            if cur_items.empty:
                st.info("此訂單尚未領取任何材料。")
            else:
                # 成本匯總
                material_cost = cur_items["小計"].apply(lambda x: _safe_float(x)).sum()
                total_qty = cur_items["數量"].apply(lambda x: _safe_float(x)).sum()
                mc1, mc2, mc3 = st.columns(3)
                mc1.metric("已領料品項", f"{len(cur_items)} 種")
                mc2.metric("總數量", f"{total_qty:.0f} 顆")
                mc3.metric("材料成本合計", f"${material_cost:,.0f}")

                # 顯示表格
                show_cols = ["庫存編號", "名稱", "五行", "形狀", "尺寸mm", "數量", "成本單價", "小計", "領料時間"]
                st.dataframe(cur_items[show_cols], use_container_width=True, hide_index=True)

                # 同步成本到訂單
                st.divider()
                if st.button("💰 同步材料成本到訂單", use_container_width=True,
                             help="將已領料材料成本加總，更新訂單的「成本」欄位"):
                    orders_df.loc[sel_pick_idx, "成本"] = str(material_cost)
                    save_orders(orders_df)
                    st.success(f"✅ 已同步材料成本 ${material_cost:,.0f} 到訂單")
                    time.sleep(1); st.rerun()

            # ── 從庫存領料 ──
            st.divider()
            st.subheader("🔍 從庫存領料")
            inv_df = load_inventory()

            if inv_df.empty:
                st.warning("⚠️ 庫存表為空，請先在庫存系統中新增庫存。")
            else:
                # 搜尋篩選
                sf1, sf2, sf3 = st.columns(3)
                search_name  = sf1.text_input("搜尋名稱", key="pick_search_name")
                search_wuxing = sf2.selectbox("篩選五行", ["全部"] + WUXING_OPTS, key="pick_search_wx")
                search_shape = sf3.text_input("搜尋形狀", key="pick_search_shape")

                filtered_inv = inv_df.copy()
                # 過濾有庫存的
                filtered_inv["_stock"] = filtered_inv["庫存(顆)"].apply(lambda x: _safe_float(x))
                filtered_inv = filtered_inv[filtered_inv["_stock"] > 0]

                if search_name:
                    filtered_inv = filtered_inv[filtered_inv["名稱"].str.contains(search_name, case=False, na=False)]
                if search_wuxing != "全部":
                    filtered_inv = filtered_inv[filtered_inv["五行"] == search_wuxing]
                if search_shape:
                    filtered_inv = filtered_inv[filtered_inv["形狀"].str.contains(search_shape, case=False, na=False)]

                if filtered_inv.empty:
                    st.info("找不到符合條件的庫存品項（或庫存為 0）。")
                else:
                    st.caption(f"共 {len(filtered_inv)} 項有庫存")
                    show_inv_cols = ["編號", "名稱", "進貨廠商", "五行", "形狀", "寬度mm", "庫存(顆)", "成本單價"]
                    st.dataframe(filtered_inv[show_inv_cols], use_container_width=True, hide_index=True)

                    # 領料表單
                    st.markdown("#### ✅ 選擇領料")
                    inv_options = []
                    for _, irow in filtered_inv.iterrows():
                        vendor = irow.get('進貨廠商', '') or ''
                        inv_options.append(
                            f"{irow['編號']} — {irow['名稱']} ({irow['形狀']} {irow['寬度mm']}mm) "
                            f"{'[' + vendor + '] ' if vendor else ''}"
                            f"[庫存:{irow['庫存(顆)']}] 單價:${_safe_float(irow['成本單價']):,.2f}")
                    sel_inv_item = st.selectbox("選擇庫存品項", inv_options, key="pick_inv_sel")

                    pk1, pk2 = st.columns([1, 2])
                    pick_qty = pk1.number_input("領料數量", min_value=1, value=1, step=1, key="pick_qty")
                    pick_operator = pk2.selectbox("操作人", ["Imeng", "千畇"], key="pick_operator")

                    if st.button("📦 確認領料", type="primary", use_container_width=True):
                        sel_inv_idx = inv_options.index(sel_inv_item)
                        inv_row = filtered_inv.iloc[sel_inv_idx]
                        hist_df = load_history()
                        inv_df, items_df, hist_df, err = pick_inventory_item(
                            pick_order_id, inv_row, int(pick_qty), pick_operator,
                            inv_df, items_df, hist_df)
                        if err:
                            st.error(f"❌ {err}")
                        else:
                            save_inventory(inv_df)
                            save_order_items(items_df)
                            save_history(hist_df)
                            # 自動更新訂單成本
                            new_mat_cost = calc_order_material_cost(pick_order_id, items_df)
                            orders_df.loc[sel_pick_idx, "成本"] = str(new_mat_cost)
                            save_orders(orders_df)
                            st.success(f"✅ 已領取 {inv_row['名稱']} x{pick_qty}（小計 ${_safe_float(inv_row['成本單價']) * pick_qty:,.2f}｜訂單總成本 ${new_mat_cost:,.1f}）")
                            time.sleep(1); st.rerun()

            # ── 此訂單的歷史紀錄 ──
            st.divider()
            st.subheader("📜 此訂單的庫存異動紀錄")
            hist_df = load_history()
            order_hist = hist_df[hist_df["單號"] == pick_order_id] if not hist_df.empty else pd.DataFrame()
            if order_hist.empty:
                st.caption("尚無異動紀錄。")
            else:
                st.dataframe(order_hist.iloc[::-1], use_container_width=True, hide_index=True)

                # ── 刪除歷史紀錄 ──
                st.markdown("#### 🗑️ 刪除領料紀錄")
                st.caption("刪除後將自動回復庫存數量、移除對應領料項目並重新計算訂單成本。")
                del_hist_opts = []
                for hi, hrow in order_hist.iloc[::-1].iterrows():
                    del_hist_opts.append(
                        f"{hrow['紀錄時間']} | {hrow['動作']} | {hrow['編號']} — {hrow['名稱']} "
                        f"({hrow['規格']}) 數量:{hrow['數量變動']} | {hrow['成本備註']}")
                sel_del_hist = st.selectbox("選擇要刪除的紀錄", del_hist_opts, key="del_hist_sel")
                if st.button("🗑️ 確認刪除此紀錄", type="secondary", use_container_width=True):
                    del_row_idx = del_hist_opts.index(sel_del_hist)
                    del_row = order_hist.iloc[::-1].iloc[del_row_idx]
                    del_inv_id  = del_row["編號"]
                    del_qty_chg = _safe_float(del_row["數量變動"])  # 領料為負, 退料為正

                    # 回復庫存
                    inv_df = load_inventory()
                    inv_match = inv_df[inv_df["編號"] == del_inv_id]
                    if not inv_match.empty:
                        inv_idx = inv_match.index[0]
                        cur_stock = _safe_float(inv_df.loc[inv_idx, "庫存(顆)"])
                        inv_df.loc[inv_idx, "庫存(顆)"] = str(cur_stock - del_qty_chg)  # 領料負數→加回; 退料正數→扣回
                        save_inventory(inv_df)

                    # 移除對應的 OrderItems 紀錄（僅限領料動作）
                    if del_row["動作"] == "訂單領料" and del_qty_chg < 0:
                        pick_time = del_row["紀錄時間"]
                        mask = ((items_df["訂單編號"] == pick_order_id)
                                & (items_df["庫存編號"] == del_inv_id)
                                & (items_df["領料時間"] == pick_time))
                        items_df = items_df[~mask].reset_index(drop=True)
                        save_order_items(items_df)

                        # 重新計算訂單成本
                        new_mat_cost = calc_order_material_cost(pick_order_id, items_df)
                        orders_df.loc[sel_pick_idx, "成本"] = str(new_mat_cost)
                        save_orders(orders_df)

                    # 刪除歷史紀錄本身
                    hist_real_idx = order_hist.iloc[::-1].index[del_row_idx]
                    hist_df = hist_df.drop(hist_real_idx).reset_index(drop=True)
                    save_history(hist_df)

                    st.success(f"✅ 已刪除紀錄：{del_row['名稱']} {del_row['動作']} {del_row['數量變動']} 顆，庫存已回復。")
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
        c1, c2, c3 = st.columns(3)
        c1.metric("總訂單數", f"{len(orders_df)} 筆")
        c2.metric("已完成",   f"{len(orders_df[orders_df['狀態']=='已完成'])} 筆")
        c3.metric("進行中",   f"{len(orders_df[~orders_df['狀態'].isin(['已完成','已取消'])])} 筆")

        try:
            done_df = orders_df[orders_df["狀態"] == "已完成"]
            rev  = done_df["總售價"].apply(lambda x: _safe_float(x)).sum()
            cost = done_df["總成本"].apply(lambda x: _safe_float(x)).sum()
            profit = rev - cost
        except Exception:
            rev, cost, profit = 0, 0, 0
        m1, m2, m3 = st.columns(3)
        m1.metric("已完成總營收", f"${rev:,.0f}")
        m2.metric("已完成總成本", f"${cost:,.0f}")
        m3.metric("已完成總利潤", f"${profit:,.0f}",
                  delta=f"{(profit/rev*100):.0f}%" if rev else None)

        st.divider()
        st.dataframe(orders_df.iloc[::-1], use_container_width=True)

# ==========================================
# § 8.5 收益表
# ==========================================
elif page == "💰 收益表":
    st.header("💰 收益表")
    orders_df = load_orders()

    if orders_df.empty:
        st.info("目前沒有任何訂單。")
    else:
        # 轉換數值欄位
        for nc in ["總售價", "成本", "運費", "工本費", "總成本"]:
            orders_df[f"_{nc}"] = orders_df[nc].apply(lambda x: _safe_float(x))
        orders_df["_利潤"] = orders_df["_總售價"] - orders_df["_總成本"]

        # 解析月份
        orders_df["_月份"] = orders_df["建立時間"].apply(
            lambda x: str(x)[:7] if str(x).strip() else "")

        # ── 篩選 ──
        f1, f2 = st.columns(2)
        status_opts = ["已完成", "全部（含進行中）"]
        rev_status = f1.selectbox("訂單狀態", status_opts, key="rev_status")
        months = sorted(orders_df["_月份"].unique().tolist(), reverse=True)
        months = [m for m in months if m]
        rev_month = f2.selectbox("月份", ["全部"] + months, key="rev_month")

        if rev_status == "已完成":
            df = orders_df[orders_df["狀態"] == "已完成"].copy()
        else:
            df = orders_df[orders_df["狀態"] != "已取消"].copy()

        if rev_month != "全部":
            df = df[df["_月份"] == rev_month]

        if df.empty:
            st.info("篩選後沒有訂單資料。")
        else:
            # ── 總覽指標 ──
            total_rev    = df["_總售價"].sum()
            total_cost   = df["_成本"].sum()
            total_ship   = df["_運費"].sum()
            total_labor  = df["_工本費"].sum()
            total_tc     = df["_總成本"].sum()
            total_profit = total_rev - total_tc
            margin       = (total_profit / total_rev * 100) if total_rev else 0

            st.subheader("📊 總覽")
            k1, k2, k3, k4 = st.columns(4)
            k1.metric("總營收", f"${total_rev:,.0f}", help="所有訂單總售價加總")
            k2.metric("總成本", f"${total_tc:,.0f}", help="成本 + 運費 + 工本費")
            k3.metric("淨利潤", f"${total_profit:,.0f}",
                      delta=f"{margin:.1f}%")
            k4.metric("訂單數", f"{len(df)} 筆")

            # 成本拆解
            st.caption(
                f"成本明細：材料 ${total_cost:,.0f}　|　"
                f"運費 ${total_ship:,.0f}　|　"
                f"工本費 ${total_labor:,.0f}　|　"
                f"合計 ${total_tc:,.0f}")

            # ── 月度收益表 ──
            st.divider()
            st.subheader("📅 月度收益")
            monthly = df.groupby("_月份").agg(
                訂單數=("_總售價", "count"),
                營收=("_總售價", "sum"),
                成本=("_成本", "sum"),
                運費=("_運費", "sum"),
                工本費=("_工本費", "sum"),
                總成本=("_總成本", "sum"),
            ).reset_index()
            monthly.columns = ["月份", "訂單數", "營收", "成本", "運費", "工本費", "總成本"]
            monthly["利潤"] = monthly["營收"] - monthly["總成本"]
            monthly["利潤率"] = monthly.apply(
                lambda r: f"{(r['利潤']/r['營收']*100):.1f}%" if r["營收"] else "—", axis=1)
            monthly = monthly.sort_values("月份", ascending=False)

            # 格式化顯示
            display_monthly = monthly.copy()
            for col in ["營收", "成本", "運費", "工本費", "總成本", "利潤"]:
                display_monthly[col] = display_monthly[col].apply(lambda x: f"${x:,.0f}")
            display_monthly["訂單數"] = display_monthly["訂單數"].astype(int)
            st.dataframe(display_monthly, use_container_width=True, hide_index=True)

            # ── 月度趨勢圖 ──
            if len(monthly) > 1:
                chart_df = monthly.sort_values("月份")[["月份", "營收", "總成本", "利潤"]].copy()
                chart_df = chart_df.set_index("月份")
                st.line_chart(chart_df)

            # ── 單筆訂單明細 ──
            st.divider()
            st.subheader("📋 訂單明細")
            detail_cols = ["訂單編號", "建立時間", "客戶名稱", "商品種類", "客製品項",
                           "狀態", "_總售價", "_成本", "_運費", "_工本費", "_總成本", "_利潤"]
            detail = df[detail_cols].copy()
            detail.columns = ["訂單編號", "建立時間", "客戶", "種類", "品項",
                              "狀態", "總售價", "成本", "運費", "工本費", "總成本", "利潤"]
            detail = detail.sort_values("建立時間", ascending=False)
            st.dataframe(detail, use_container_width=True, hide_index=True)

            # ── 客戶消費排行 ──
            st.divider()
            st.subheader("👑 客戶消費排行")
            cust_rank = df.groupby("客戶名稱").agg(
                訂單數=("_總售價", "count"),
                消費總額=("_總售價", "sum"),
                貢獻利潤=("_利潤", "sum"),
            ).reset_index().sort_values("消費總額", ascending=False)
            cust_rank["消費總額"] = cust_rank["消費總額"].apply(lambda x: f"${x:,.0f}")
            cust_rank["貢獻利潤"] = cust_rank["貢獻利潤"].apply(lambda x: f"${x:,.0f}")
            st.dataframe(cust_rank, use_container_width=True, hide_index=True)

# ==========================================
# § 9 客戶管理
# ==========================================
elif page == "👥 客戶管理":
    st.header("👥 客戶資料管理")
    customers_df = load_customers()

    tab1, tab2 = st.tabs(["➕ 新增客戶", "✏️ 查看 / 編輯客戶"])

    with tab1:
        # ── 從訂單自動匯入 ──
        with st.container(border=True):
            st.markdown("#### 🔃 從訂單資料自動匯入客戶")
            st.caption("掃描所有訂單，將尚未建檔的客戶自動加入客戶資料表（已存在的不覆蓋）")
            if st.button("立即同步", type="primary", use_container_width=True):
                added = sync_customers_from_orders()
                customers_df = load_customers()   # 重新載入
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

            a3, a4, a4b, a5 = st.columns(4)
            new_wrist       = a3.text_input("手圍")
            new_bday        = a4.text_input("國曆生日（YYYY/MM/DD）",  placeholder="例：2000/10/10")
            new_lunar_bday  = a4b.text_input("農曆生日（YYYY/MM/DD）", placeholder="例：2000/09/01")
            new_btime       = a5.text_input("出生時間（HH:MM）",       placeholder="例：08:30")

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
                new_store_name = d4.text_input("超商名稱／門市", placeholder="例：7-11 台北信義門市")
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
                        "農曆生日": new_lunar_bday,
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

            bday_val = safe_get(cust_row, "生日")
            lunar_val = safe_get(cust_row, "農曆生日") if "農曆生日" in cust_row.index else ""
            btime_val = safe_get(cust_row, "出生時間") if "出生時間" in cust_row.index else ""
            if bday_val:
                st.markdown("#### 📊 流年 × 階段數 三年對照表（自動計算）")
                render_numerology_table(bday_val, lunar_val, btime_val)
            else:
                st.info("ℹ️ 請填寫生日後，系統將自動計算三年流年與階段數。")

            # 顯示收件資料摘要
            recv_type = safe_get(cust_row, "收件類型")
            recv_addr = safe_get(cust_row, "收件地址")
            recv_name = safe_get(cust_row, "收件人姓名")
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

            # 顯示關係鏈結摘要
            my_rels = get_customer_relations(sel_cust, rel_df_mgmt)
            if not my_rels.empty:
                st.markdown("#### 🔗 關係鏈結")
                st.dataframe(my_rels[["對象","關係類型","備註"]], use_container_width=True, hide_index=True)
                st.caption("完整管理請至「🔗 關係鏈結」頁面")

            with st.form("edit_customer_form"):
                ec1, ec2 = st.columns(2)
                ec_name  = ec1.text_input("客戶名稱", value=safe_get(cust_row,"客戶名稱"))
                ec_phone = ec2.text_input("客戶電話", value=safe_get(cust_row,"客戶電話"))

                eb1, eb2, eb2b, eb3 = st.columns(4)
                ec_wrist      = eb1.text_input("手圍",                   value=safe_get(cust_row,"手圍"))
                ec_bday       = eb2.text_input("國曆生日（YYYY/MM/DD）", value=safe_get(cust_row,"生日"))
                ec_lunar_bday = eb2b.text_input("農曆生日（YYYY/MM/DD）",value=safe_get(cust_row,"農曆生日"))
                ec_btime      = eb3.text_input("出生時間（HH:MM）",      value=safe_get(cust_row,"出生時間"))

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
                    ec_store_name = ed4.text_input("超商名稱／門市", value=safe_get(cust_row,"超商名稱門市"))
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
                    customers_df.loc[cust_idx,"農曆生日"]   = str(ec_lunar_bday)
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

    # ── 查詢單一客戶的所有關係 ──
    with tab_view:
        if not cust_names:
            st.info("尚未建立任何客戶資料。")
        else:
            sel_name = st.selectbox("選擇客戶", cust_names, key="rel_view_sel")
            my_rels  = get_customer_relations(sel_name, rel_df)

            # 顯示此客戶基本資訊
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
                        lunar_bday = safe_get(c, "農曆生日")
                        if bday:
                            lunar_info = f"　🌙 農曆：{lunar_bday}" if lunar_bday else ""
                            st.caption(f"🎂 國曆：{bday}{lunar_info}　流年今年：{safe_get(c,'流年今年') or '-'}　階段數：{safe_get(c,'階段數') or '-'}")

            st.subheader(f"🔗 {sel_name} 的所有關係")
            if my_rels.empty:
                st.info("此客戶目前沒有任何關係鏈結。")
            else:
                st.dataframe(my_rels, use_container_width=True, hide_index=True)
                st.caption(f"共 {len(my_rels)} 條關係")

                # 顯示每位關聯客戶的數字學資訊
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
                            tlunar = safe_get(tc, "農曆生日")
                            tbtime = safe_get(tc, "出生時間")
                            if tbday:
                                render_numerology_table(tbday, tlunar, tbtime)
                            else:
                                st.caption("此客戶尚無生日資料")
                        else:
                            st.caption("此關聯客戶不在客戶資料庫中")

                # 刪除關係
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

    # ── 新增關係 ──
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
                        # 防止重複（雙向）
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

    # ── 所有關係清單 ──
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

            # 也可從客戶名單快速選入
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

                # 判斷是否已過生日說明
                passed = (today.month, today.day) >= (bm, bd)
                bday_desc = f"生日 {bm}/{bd} 今年{'已過 ✅' if passed else '尚未到 ⏳'}"
                st.info(f"📅 {bday_desc}｜個人年基準：{years[1]} 年")

                st.subheader("📊 五大階段數 × 三年流年對照表")
                render_numerology_table(input_bday, "", input_btime)

                # 詳細計算說明
                st.divider()
                st.subheader("📐 詳細計算過程")

                # 流年計算（每年一個 expander）
                for yr, lbl in zip(years, labels):
                    ln = calc_liunian(yr, bm, bd)
                    ln_steps = " → ".join(str(x) for x in _reduce_chain(
                        sum(int(d) for d in (str(yr)+str(bm)+str(bd)))))
                    with st.expander(f"流年 {yr}（{lbl}）= {ln.split('/')[-1]}"):
                        st.markdown(
                            f"- 年份 {yr} + 月 {bm} + 日 {bd}\n"
                            f"- 各位數字：{' + '.join(list(str(yr)+str(bm)+str(bd)))} "
                            f"= {sum(int(d) for d in str(yr)+str(bm)+str(bd))}\n"
                            f"- 縮減過程：{ln_steps}\n"
                            f"- **結果：{ln.split('/')[-1]}**")

                # 五大階段數計算
                st.divider()
                five_stages = calc_five_stages(by, bm, bd, input_btime)
                part_labels = ["西元年", "月", "日", "時", "分"]
                with st.expander("📊 五大階段數計算過程"):
                    for i, stg in enumerate(five_stages):
                        if stg['digits_str']:
                            digits_list = ' + '.join(list(stg['digits_str']))
                            st.markdown(
                                f"**{stg['name']}（{stg['age']}）** — 累加到「{part_labels[i]}」\n\n"
                                f"　{digits_list} = {stg['total']}　→　**{stg['display']}**")
                        else:
                            st.markdown(
                                f"**{stg['name']}（{stg['age']}）** — 需填寫出生時間")
            else:
                st.error("⚠️ 生日格式錯誤，請輸入 YYYY/MM/DD（例：2000/10/10）")
        else:
            st.info("👈 請在左側輸入生日")
