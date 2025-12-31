import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection

st.set_page_config(page_title="GemCraft 日常庫存系統", layout="wide")
st.title("💎 GemCraft 日常出入庫紀錄")

# 連結同一個 Google Sheets
conn = st.connection("gsheets", type=GSheetsConnection)
df = conn.read(ttl="1s")

tab1, tab2 = st.tabs(["🛒 售出/領用扣除", "🔍 現有庫存查詢"])

with tab1:
    st.subheader("🎨 作品設計與售出扣除")
    wh = st.selectbox("選擇扣除倉庫", ["Imeng", "千畇"])
    items = df[df['倉庫'] == wh]
    
    if not items.empty:
        item_labels = items.apply(lambda r: f"{r['編號']} - {r['名稱']} (餘:{int(r['現有庫存'])})", axis=1).tolist()
        sel_label = st.selectbox("選擇使用的材料", item_labels)
        sel_id = sel_label.split(" - ")[0]
        
        qty = st.number_input("扣除數量", min_value=1, value=1)
        note = st.text_input("備註 (設計用途)")
        
        if st.button("✅ 確認扣除數量"):
            idx = df[df['編號'] == sel_id].index[0]
            df.at[idx, '現有庫存'] -= qty
            conn.update(data=df)
            st.warning(f"已完成更新！餘額將同步至雲端。")
            st.rerun()

with tab2:
    # 只顯示不敏感的欄位
    safe_df = df[['編號', '倉庫', '分類', '名稱', '現有庫存']]
    st.dataframe(safe_df, use_container_width=True)
