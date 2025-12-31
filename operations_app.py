import streamlit as st
import pandas as pd
import os

# 設定
MASTER_FILE = 'inventory_master.csv'
SAFE_COLUMNS = ['編號', '倉庫', '分類', '名稱', '庫存(顆)']

st.set_page_config(page_title="GemCraft 日常系統", layout="wide")
st.title("💎 GemCraft 日常庫存與設計")

if not os.path.exists(MASTER_FILE):
    st.error("請先用財務系統建立資料庫")
    st.stop()

master_df = pd.read_csv(MASTER_FILE, encoding='utf-8-sig')

tab1, tab2 = st.tabs(["🧮 作品設計扣庫存", "📋 目前庫存查詢"])

with tab1:
    wh = st.selectbox("選擇倉庫", ["Imeng", "千畇"])
    items = master_df[master_df['倉庫'] == wh]
    if not items.empty:
        # 使用名稱 + 編號 避免重複
        items['display_name'] = items['名稱'] + " (" + items['編號'] + ")"
        sel_display = st.selectbox("選擇材料", items['display_name'].tolist())
        sel_id = sel_display.split(" (")[-1].replace(")", "")
        
        qty = st.number_input("使用數量", min_value=1)
        note = st.text_input("設計備註 (如：主石)")
        if st.button("✅ 確認扣除庫存"):
            idx = master_df[master_df['編號'] == sel_id].index[0]
            master_df.at[idx, '庫存(顆)'] -= qty
            master_df.to_csv(MASTER_FILE, index=False, encoding='utf-8-sig')
            st.success("扣除成功！")
            st.rerun()

with tab2:
    st.dataframe(master_df[SAFE_COLUMNS], use_container_width=True)
