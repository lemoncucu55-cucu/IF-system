import streamlit as st
import pandas as pd
import os
import time

# 檔案設定
MASTER_FILE = 'ops_inventory.csv'
WAREHOUSES = ["Imeng", "千畇"]

st.set_page_config(page_title="GemCraft 日常庫存系統", layout="wide")
st.title("💎 日常出入庫與設計紀錄")

# 初始化資料庫
if not os.path.exists(MASTER_FILE):
    pd.DataFrame(columns=['編號', '倉庫', '分類', '名稱', '現有庫存']).to_csv(MASTER_FILE, index=False, encoding='utf-8-sig')

df = pd.read_csv(MASTER_FILE, encoding='utf-8-sig')

tab1, tab2 = st.tabs(["🧮 作品設計扣量", "🔍 現有庫存查詢"])

with tab1:
    st.subheader("作品設計領料")
    wh = st.selectbox("選擇倉庫", WAREHOUSES)
    items = df[df['倉庫'] == wh]
    if not items.empty:
        # 顯示格式：名稱 (餘額)
        item_labels = items.apply(lambda r: f"{r['名稱']} (餘:{int(r['現有庫存'])})", axis=1).tolist()
        sel_label = st.selectbox("選擇材料", item_labels)
        sel_name = sel_label.split(" (")[0]
        
        qty = st.number_input("使用數量", min_value=1, value=1)
        note = st.text_input("設計備註 (例如：主石/配石)")
        
        if st.button("✅ 確認領料"):
            idx = df[(df['名稱'] == sel_name) & (df['倉庫'] == wh)].index[0]
            df.at[idx, '現有庫存'] -= qty
            df.to_csv(MASTER_FILE, index=False, encoding='utf-8-sig')
            st.success(f"扣除成功！{sel_name} 剩餘：{df.at[idx, '現有庫存']}")
            st.rerun()
    else:
        st.info("目前此倉庫無庫存資料，請先至盤點分頁新增。")

with tab2:
    st.subheader("📋 目前庫存總覽")
    st.dataframe(df[['編號', '倉庫', '分類', '名稱', '現有庫存']], use_container_width=True)
