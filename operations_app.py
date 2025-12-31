import streamlit as st
import pandas as pd
import os
import time

# 檔案設定
MASTER_FILE = 'ops_inventory.csv'
WAREHOUSES = ["Imeng", "千畇"]
CATEGORIES = ["天然石", "配件", "耗材", "其他"]

st.set_page_config(page_title="GemCraft 日常庫存系統", layout="wide")
st.title("💎 GemCraft 日常出入庫與盤點系統")

# 1. 初始化資料庫 (如果檔案不存在)
if not os.path.exists(MASTER_FILE):
    pd.DataFrame(columns=['編號', '倉庫', '分類', '名稱', '現有庫存', '最後更新時間']).to_csv(MASTER_FILE, index=False, encoding='utf-8-sig')

# 讀取資料
def load_data():
    return pd.read_csv(MASTER_FILE, encoding='utf-8-sig')

df = load_data()

# --- 功能分頁 ---
tab1, tab2, tab3, tab4 = st.tabs(["🧮 作品設計扣量", "📥 入庫與盤點修正", "🔍 庫存查詢與報表", "📤 上傳更新數據"])

# --- Tab 1: 作品設計扣量 ---
with tab1:
    st.subheader("🎨 作品設計領料 (出庫)")
    wh = st.selectbox("選擇出庫倉庫", WAREHOUSES, key="out_wh")
    items = df[df['倉庫'] == wh]
    
    if not items.empty:
        item_labels = items.apply(lambda r: f"{r['名稱']} (餘:{int(r['現有庫存'])})", axis=1).tolist()
        sel_label = st.selectbox("選擇材料", item_labels)
        sel_name = sel_label.split(" (")[0]
        
        qty = st.number_input("扣除數量", min_value=1, value=1)
        note = st.text_input("設計備註 (例如：訂單編號或作品名)")
        
        if st.button("✅ 確認領料扣庫存"):
            idx = df[(df['名稱'] == sel_name) & (df['倉庫'] == wh)].index[0]
            if df.at[idx, '現有庫存'] >= qty:
                df.at[idx, '現有庫存'] -= qty
                df.at[idx, '最後更新時間'] = time.strftime("%Y-%m-%d %H:%M:%S")
                df.to_csv(MASTER_FILE, index=False, encoding='utf-8-sig')
                st.success(f"扣除成功！{sel_name} 剩餘數量：{int(df.at[idx, '現有庫存'])}")
                st.rerun()
            else:
                st.error("庫存不足，無法扣除！")
    else:
        st.info("該倉庫目前沒有商品。")

# --- Tab 2: 入庫與盤點修正 ---
with tab2:
    st.subheader("📥 盤點修正與新物料入庫")
    mode = st.radio("操作模式", ["現有商品增減 (盤點)", "新商品初次入庫"])
    
    if mode == "現有商品增減 (盤點)":
        wh_mod = st.selectbox("選擇倉庫", WAREHOUSES, key="mod_wh")
        mod_items = df[df['倉庫'] == wh_mod]
        if not mod_items.empty:
            sel_mod = st.selectbox("選擇商品", mod_items['名稱'].tolist())
            current_q = df[(df['名稱'] == sel_mod) & (df['倉庫'] == wh_mod)]['現有庫存'].values[0]
            st.write(f"目前系統庫存：**{int(current_q)}**")
            
            new_q = st.number_input("修正後的實際庫存總數", min_value=0, value=int(current_q))
            if st.button("🔧 修正庫存"):
                idx = df[(df['名稱'] == sel_mod) & (df['倉庫'] == wh_mod)].index[0]
                df.at[idx, '現有庫存'] = new_q
                df.at[idx, '最後更新時間'] = time.strftime("%Y-%m-%d %H:%M:%S")
                df.to_csv(MASTER_FILE, index=False, encoding='utf-8-sig')
                st.success("庫存修正完成！")
                st.rerun()
        else:
            st.info("該倉庫目前沒有商品。")
            
    else: # 新商品入庫
        with st.form("add_new_item"):
            c1, c2 = st.columns(2)
            new_wh = c1.selectbox("存入倉庫", WAREHOUSES)
            new_cat = c1.selectbox("分類", CATEGORIES)
            new_name = c2.text_input("商品名稱")
            new_qty = c2.number_input("初始入庫數量", min_value=1, value=1)
            if st.form_submit_button("➕ 建立新項目"):
                new_r = {
                    '編號': f"OP{int(time.time())}",
                    '倉庫': new_wh, '分類': new_cat, '名稱': new_name,
                    '現有庫存': new_qty, '最後更新時間': time.strftime("%Y-%m-%d %H:%M:%S")
                }
                df = pd.concat([df, pd.DataFrame([new_r])], ignore_index=True)
                df.to_csv(MASTER_FILE, index=False, encoding='utf-8-sig')
                st.success("新商品已成功入庫！")
                st.rerun()

# --- Tab 3: 庫存查詢與報表下載 ---
with tab3:
    st.subheader("📋 庫存總覽表")
    st.dataframe(df, use_container_width=True)
    
    # 下載功能
    csv = df.to_csv(index=False).encode('utf-8-sig')
    st.download_button(
        label="📥 下載完整庫存報表 (CSV格式)",
        data=csv,
        file_name=f'gemcraft_inventory_{time.strftime("%Y%m%d")}.csv',
        mime='text/csv',
    )

# --- Tab 4: 上傳報表更新 ---
with tab4:
    st.subheader("📤 大量數據更新")
    st.write("您可以下載報表修改後，再從這裡上傳覆蓋系統數據。")
    uploaded_file = st.file_uploader("選擇要上傳的 CSV 檔案", type="csv")
    if uploaded_file is not None:
        new_df = pd.read_csv(uploaded_file)
        # 基本欄位檢查
        if set(['倉庫', '名稱', '現有庫存']).issubset(new_df.columns):
            if st.button("⚠️ 確認覆蓋系統數據"):
                new_df.to_csv(MASTER_FILE, index=False, encoding='utf-8-sig')
                st.success("數據已成功更新！請重新整理頁面。")
                st.rerun()
        else:
            st.error("檔案格式不正確，請確保包含 倉庫、名稱、現有庫存 欄位。")
