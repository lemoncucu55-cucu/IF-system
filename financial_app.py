import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
from datetime import date
import time

st.set_page_config(page_title="GemCraft 財務進貨系統", layout="wide")
st.title("💰 GemCraft 財務成本管理")

# 連結 Google Sheets
conn = st.connection("gsheets", type=GSheetsConnection)

# 讀取現有資料
df = conn.read(ttl="1s") # 設定快取為1秒，確保數據即時

menu = st.sidebar.radio("功能選單", ["🆕 新商品進貨建檔", "📊 成本歷史報表"])

if menu == "🆕 新商品進貨建檔":
    with st.form("finance_form"):
        st.subheader("📝 輸入進貨資料")
        c1, c2 = st.columns(2)
        wh = c1.selectbox("存入倉庫", ["Imeng", "千畇"])
        cat = c1.selectbox("商品分類", ["天然石", "配件", "耗材"])
        name = c2.text_input("商品名稱")
        vendor = c2.text_input("進貨廠商")
        
        c3, c4 = st.columns(2)
        qty = c3.number_input("進貨數量 (顆/個)", min_value=1)
        total_cost = c4.number_input("進貨總價 (台幣)", min_value=0.0)
        
        if st.form_submit_button("💾 計算並存檔"):
            avg_cost = total_cost / qty
            new_row = pd.DataFrame([{
                '編號': f"ST{int(time.time())}", 
                '倉庫': wh, '分類': cat, '名稱': name, 
                '進貨總價': total_cost, '進貨數量': qty, 
                '進貨日期': str(date.today()), '廠商': vendor, 
                '單顆成本': avg_cost, '現有庫存': qty  # 進貨時初始庫存等於進貨量
            }])
            updated_df = pd.concat([df, new_row], ignore_index=True)
            conn.update(data=updated_df)
            st.success(f"已同步至 Google Sheets！單價：{avg_cost:.2f}")

elif menu == "📊 成本歷史報表":
    st.dataframe(df, use_container_width=True)
