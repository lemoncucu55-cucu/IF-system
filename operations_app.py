from __future__ import annotations
import uuid
from datetime import date, datetime
import pandas as pd
import gspread
import streamlit as st
from oauth2client.service_account import ServiceAccountCredentials
import time

# § 1 常數與設定
SHEET_ID = "1gf-pn034w0oZx8jWDUJvmIyHX_O7eHbiBb9diVSBX0Q"
KEY_FILE = "google_key.json"
COLUMNS = ['編號', '批號', '倉庫', '分類', '名稱', '寬度mm', '長度mm', '形狀', '五行', '進貨數量(顆)', '進貨日期', '進貨廠商', '庫存(顆)', '成本單價']
HISTORY_COLUMNS = ['紀錄時間', '單號', '動作', '倉庫', '批號', '編號', '分類', '名稱', '規格', '廠商', '數量變動', '成本備註']
MANUAL = "➕ 手動輸入"

# § 2 核心連線
@st.cache_resource
def _gs_client():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    try:
        if "gcp_service_account" in st.secrets:
            creds = ServiceAccountCredentials.from_json_keyfile_dict(dict(st.secrets["gcp_service_account"]), scope)
        else:
            creds = ServiceAccountCredentials.from_json_keyfile_name(KEY_FILE, scope)
    except:
        st.error("Google Key 授權失敗"); st.stop()
    return gspread.authorize(creds)

def load_data(tab=None):
    try:
        ws = _gs_client().open_by_key(SHEET_ID).worksheet(tab) if tab else _gs_client().open_by_key(SHEET_ID).sheet1
        df = pd.DataFrame(ws.get_all_records())
        if df.empty: return pd.DataFrame(columns=COLUMNS if not tab else HISTORY_COLUMNS)
        return df
    except: return pd.DataFrame(columns=COLUMNS if not tab else HISTORY_COLUMNS)

def save_data(df, tab=None):
    ws = _gs_client().open_by_key(SHEET_ID).worksheet(tab) if tab else _gs_client().open_by_key(SHEET_ID).sheet1
    ws.clear()
    ws.update(range_name="A1", values=[df.columns.tolist()] + df.astype(str).values.tolist())

# § 3 工具函式
def get_opts(col, defaults, inv):
    exist = {str(v).strip() for v in inv[col].unique() if str(v).strip() and str(v).lower() not in ("nan", "0")}
    return [MANUAL] + sorted(exist | set(defaults))

def fmt_sz(r):
    try:
        w, l = float(r.get('寬度mm', 0)), float(r.get('長度mm', 0))
        return f"{w}x{l}mm" if l > 0 else f"{w}mm"
    except: return str(r.get('規格', '0mm'))

def mk_label(r, admin=False):
    sz = fmt_sz(r)
    cost = f" 💰${float(r.get('成本單價', 0)):.2f}" if admin else ""
    return f"[{r.get('倉庫', '庫')}] ({r.get('五行', '無')}) {r.get('名稱', '無')} {sz} 【{r.get('批號', '批')}】 | 存:{r.get('庫存(顆)', 0)}{cost}"

# § 4 初始化
st.set_page_config(page_title="IF Crystal 系統", layout="wide")
if "inventory" not in st.session_state: st.session_state["inventory"] = load_data()
if "history" not in st.session_state: st.session_state["history"] = load_data("History")
if "current_design" not in st.session_state: st.session_state["current_design"] = []

# § 5 介面
with st.sidebar:
    st.header("🔑 管理員")
    st.session_state["admin_mode"] = (st.text_input("主管密碼", type="password") == "admin123")
    page = st.radio("前往", ["📦 庫存管理", "📜 紀錄查詢", "🧮 設計領料"])
    if st.button("🔄 重整系統"): st.session_state.clear(); st.rerun()

# --- 庫存管理 (Tab 邏輯) ---
if page == "📦 庫存管理":
    t1, t2, t3 = st.tabs(["🔄 補貨", "✨ 建檔", "🛠️ 修改"])
    inv = st.session_state["inventory"]
    with t1:
        if not inv.empty:
            df_l = inv.copy(); df_l["dp"] = df_l.apply(lambda r: mk_label(r, st.session_state["admin_mode"]), axis=1)
            sel = st.selectbox("選擇商品", df_l["dp"].tolist(), key="restock_box")
            idx = df_l[df_l["dp"] == sel].index[0]; row = inv.loc[idx]
            with st.form("r_f"):
                qty = st.number_input("進貨數量", 1); pri = st.number_input("本次總價", 0.0)
                if st.form_submit_button("確認補貨"):
                    st.session_state["inventory"].at[idx, "庫存(顆)"] += qty
                    st.session_state["inventory"].at[idx, "成本單價"] = round(pri/qty, 2) if qty > 0 else 0
                    save_data(st.session_state["inventory"]); st.rerun()
    with t2:
        with st.form("c_f"):
            c1, c2, c3 = st.columns(3)
            wh = c1.selectbox("倉庫", ["Imeng", "千畇"])
            n_sel = c2.selectbox("名稱", get_opts("名稱", ["水晶"], inv), key="create_n")
            n_man = c2.text_input("手動名稱")
            el_sel = c3.selectbox("五行", get_opts("五行", ["金", "木", "水", "火", "土"], inv))
            if st.form_submit_button("建立商品"):
                name = n_man if n_sel == MANUAL else n_sel
                new_r = {"編號": f"ST{uuid.uuid4().hex[:5].upper()}", "批號": "初始", "倉庫": wh, "名稱": name, "五行": el_sel, "庫存(顆)": 1, "成本單價": 0, "寬度mm": 0, "長度mm": 0, "分類": "天然石", "形狀": "圓珠", "進貨廠商": "自用", "進貨數量(顆)": 1, "進貨日期": str(date.today())}
                st.session_state["inventory"] = pd.concat([inv, pd.DataFrame([new_r])], ignore_index=True)
                save_data(st.session_state["inventory"]); st.rerun()
    with t3:
        if not inv.empty:
            df_l = inv.copy(); df_l["dp"] = df_l.apply(lambda r: mk_label(r, True), axis=1)
            sel = st.selectbox("修改項目", df_l["dp"].tolist(), key="edit_box")
            idx = df_l[df_l["dp"] == sel].index[0]; row = inv.loc[idx]
            with st.form("e_f"):
                new_n = st.text_input("品名", row["名稱"])
                new_q = st.number_input("庫存", value=int(row["庫存(顆)"]))
                if st.form_submit_button("儲存修改"):
                    st.session_state["inventory"].at[idx, "名稱"] = new_n
                    st.session_state["inventory"].at[idx, "庫存(顆)"] = new_q
                    save_data(st.session_state["inventory"]); st.rerun()
    st.dataframe(st.session_state["inventory"], use_container_width=True)

# --- 設計領料 (核心修正：相容性顯示) ---
elif page == "🧮 設計領料":
    st.subheader("🧮 設計單領料")
    c1, c2 = st.columns([1, 2])
    oid = c1.text_input("單號", f"DES-{date.today().strftime('%m%d')}")
    note = c2.text_input("備註")
    
    inv = st.session_state["inventory"]
    df_l = inv.copy(); df_l["dp"] = df_l.apply(lambda r: mk_label(r), axis=1)
    sel = st.selectbox("選擇材料", df_l["dp"].tolist(), key="design_box")
    idx = df_l[df_l["dp"] == sel].index[0]; row = inv.loc[idx]
    
    qty = st.number_input("加入數量", 1, max_value=max(1, int(row["庫存(顆)"])))
    if st.button("⬇️ 加入待領清單"):
        st.session_state["current_design"].append({
            "idx": idx, 
            "名稱": row["名稱"], 
            "五行": row["五行"], 
            "數量": qty, 
            "單價": float(row["成本單價"]),
            "規格": fmt_sz(row),
            "批號": row["批號"]
        })
        st.rerun()
    
    if st.session_state["current_design"]:
        st.write("---")
        st.markdown("### 🛒 待領清單明細")
        total_p = 0
        for i, item in enumerate(st.session_state["current_design"]):
            # 相容性處理：如果舊資料沒有某個 Key，給予預設值避免當機
            iname = item.get("名稱", "未知")
            ielem = item.get("五行", item.get("顏色", "無"))
            iqty = item.get("數量", 1)
            ipri = float(item.get("單價", item.get("成本單價", 0)))
            isz = item.get("規格", "0mm")
            ibatch = item.get("批號", "初始")
            
            subtotal = ipri * iqty
            total_p += subtotal
            
            col_t, col_b = st.columns([5, 1])
            admin_info = f" (💰單價:${ipri:.2f} | 小計:${subtotal:.2f})" if st.session_state["admin_mode"] else ""
            col_t.write(f"🔸 [{ielem}] **{iname}** ({isz}) x{iqty} | 批號:{ibatch}{admin_info}")
            
            if col_b.button("🗑️", key=f"del_btn_{i}"):
                st.session_state["current_design"].pop(i); st.rerun()
        
        st.write("---")
        if st.session_state["admin_mode"]: st.metric("預估總成本", f"${total_p:.2f}")
        
        if st.button("✅ 確認領出 (扣庫存)", type="primary", use_container_width=True):
            for item in st.session_state["current_design"]:
                target_idx = item["idx"]
                target_qty = item["數量"]
                st.session_state["inventory"].at[target_idx, "庫存(顆)"] -= target_qty
            save_data(st.session_state["inventory"])
            st.session_state["current_design"] = []
            st.success("領料成功！"); time.sleep(1); st.rerun()

elif page == "📜 紀錄查詢":
    st.dataframe(st.session_state["history"].iloc[::-1], use_container_width=True)
