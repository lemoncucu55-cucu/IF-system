import streamlit as st
import pandas as pd
import os
from datetime import datetime

# 設定
MASTER_FILE = 'inventory_master.csv'
WAREHOUSES = ["Imeng", "千畇"]
# 隱藏財務敏感資訊
SAFE_COLUMNS = ['編號', '倉庫', '分類', '名稱', '寬度mm', '長度mm', '形狀', '庫存(顆)']

st.set_page_config(page_title="GemCraft 日常操作系統", layout="wide")
st.title("💎 GemCraft 庫存操作與設計紀錄")

if not os.path.exists(MASTER_FILE):
    st.error("找不到資料庫檔案，請聯絡管理員先執行財務系統建檔。")
    st.stop()

# 讀取資料並隱藏成本
master_df = pd.read_csv(MASTER_FILE, encoding='utf-8-sig')
display_df = master_df[SAFE_COLUMNS].copy()

page = st.tabs(["📤 領用/盤點", "🧮 作品設計", "📋 庫存查詢"])

# 1. 領用/盤點
with page[0]:
    wh_sel = st.radio("目前操作倉庫", WAREHOUSES, horizontal=True)
    filtered_items = display_df[display_df['倉庫'] == wh_sel]
    
    if not filtered_items.empty:
        item_list = filtered_items.apply(lambda r: f"{r['編號']} - {r['名稱']} (餘:{int(r['庫存(顆)'])})", axis=1).tolist()
        target = st.selectbox("選擇商品", item_list)
        target_id = target.split(" - ")[0]
        
        with st.form("op_form"):
            action = st.selectbox("動作", ["日常領用", "盤點修正", "損壞報廢"])
            num = st.number_input("數量變動 (減少請輸入負數)", value=-1)
            reason = st.text_input("備註說明")
            
            if st.form_submit_button("確認更新"):
                # 更新主檔案
                idx = master_df[master_df['編號'] == target_id].index[0]
                master_df.at[idx, '庫存(顆)'] += num
                master_df.to_csv(MASTER_FILE, index=False, encoding='utf-8-sig')
                st.success("庫存已更新！")
                st.rerun()

# 2. 作品設計 (核心需求：含備註欄位)
with page[1]:
    if 'design_cart' not in st.session_state: st.session_state['design_cart'] = []
    
    st.subheader("🎨 新作品材料組合")
    c1, c2, c3 = st.columns([2, 1, 2])
    
    wh_design = c1.selectbox("材料倉庫", WAREHOUSES)
    d_items = display_df[display_df['倉庫'] == wh_design]
    sel_item = c1.selectbox("選擇材料", d_items['名稱'].unique())
    
    # 找尋該名稱下的規格 (針對同名不同規格)
    specs = d_items[d_items['名稱'] == sel_item]
    sel_spec = c2.selectbox("選擇規格/編號", specs.apply(lambda r: f"{r['編號']} ({r['寬度mm']}mm)", axis=1))
    
    qty_design = c2.number_input("使用數量", min_value=1, value=1)
    note_design = c3.text_input("這項材料的備註 (如：主石、隔珠)")
    
    if st.button("⬇️ 加入作品清單"):
        target_id = sel_spec.split(" (")[0]
        st.session_state['design_cart'].append({
            '編號': target_id, '名稱': sel_item, '數量': qty_design, '備註': note_design, '倉庫': wh_design
        })
        st.rerun()

    if st.session_state['design_cart']:
        st.table(pd.DataFrame(st.session_state['design_cart']))
        if st.button("✅ 完成設計並扣除庫存", type="primary"):
            for item in st.session_state['design_cart']:
                idx = master_df[master_df['編號'] == item['編號']].index[0]
                master_df.at[idx, '庫存(顆)'] -= item['數量']
            master_df.to_csv(MASTER_FILE, index=False, encoding='utf-8-sig')
            st.session_state['design_cart'] = []
            st.success("作品領料完成，庫存已扣除。")
            st.rerun()

# 3. 庫存查詢
with page[2]:
    st.dataframe(display_df, use_container_width=True)
