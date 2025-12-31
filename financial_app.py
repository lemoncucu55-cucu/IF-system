import streamlit as st
import pandas as pd
import os
import time
from datetime import date, datetime

# 設定
MASTER_FILE = 'inventory_master.csv'
HISTORY_FILE = 'inventory_history.csv'
COLUMNS = ['編號', '倉庫', '分類', '名稱', '寬度mm', '長度mm', '形狀', '五行', '進貨總價', '進貨數量(顆)', '進貨日期', '進貨廠商', '庫存(顆)', '單顆成本']
WAREHOUSES = ["Imeng", "千畇"]

st.set_page_config(page_title="GemCraft 財務進貨系統", layout="wide")
st.title("💰 GemCraft 財務與進貨管理")

# 初始化資料庫
if not os.path.exists(MASTER_FILE):
    pd.DataFrame(columns=COLUMNS).to_csv(MASTER_FILE, index=False, encoding='utf-8-sig')

df = pd.read_csv(MASTER_FILE, encoding='utf-8-sig')

# 側邊欄
with st.sidebar:
    pwd = st.text_input("主管密碼", type="password")
    if pwd != "admin123":
        st.error("請輸入正確密碼以操作財務系統")
        st.stop()
    menu = st.radio("功能選單", ["🆕 新商品建檔", "📈 進貨紀錄報表", "🛠️ 資料庫維護"])

# 1. 新商品建檔
if menu == "🆕 新商品建檔":
    with st.form("new_item_form"):
        st.subheader("📦 商品基本資訊與成本輸入")
        c1, c2, c3 = st.columns(3)
        wh = c1.selectbox("倉庫", WAREHOUSES)
        cat = c2.selectbox("分類", ["天然石", "配件", "耗材"])
        name = c3.text_input("商品名稱")
        
        s1, s2, s3 = st.columns(3)
        w_mm = s1.number_input("寬度mm", min_value=0.0)
        l_mm = s2.number_input("長度mm", min_value=0.0)
        shape = s3.text_input("形狀")
        
        f1, f2, f3 = st.columns(3)
        qty = f1.number_input("進貨數量(顆)", min_value=1)
        total_cost = f2.number_input("進貨總價", min_value=0.0)
        vendor = f3.text_input("廠商")
        
        if st.form_submit_button("💾 建立並存檔"):
            avg_cost = total_cost / qty if qty > 0 else 0
            new_data = {
                '編號': f"ST{int(time.time())}", '倉庫': wh, '分類': cat, '名稱': name,
                '寬度mm': w_mm, '長度mm': l_mm, '形狀': shape, '五行': "",
                '進貨總價': total_cost, '進貨數量(顆)': qty, '進貨日期': date.today(),
                '進貨廠商': vendor, '庫存(顆)': qty, '單顆成本': avg_cost
            }
            df = pd.concat([df, pd.DataFrame([new_data])], ignore_index=True)
            df.to_csv(MASTER_FILE, index=False, encoding='utf-8-sig')
            st.success(f"商品 {name} 已成功建檔，單顆成本為: {avg_cost:.2f}")

# 2. 進貨紀錄報表
elif menu == "📈 進貨紀錄報表":
    st.subheader("全部庫存與成本清單")
    st.dataframe(df)
    
    csv = df.to_csv(index=False).encode('utf-8-sig')
    st.download_button("📥 下載財務總表", csv, "financial_master.csv", "text/csv")
