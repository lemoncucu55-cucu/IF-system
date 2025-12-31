import streamlit as st
import pandas as pd
import os
import time

# 檔案設定
MASTER_FILE = 'ops_inventory.csv'
WAREHOUSES = ["Imeng", "千畇"]
CATEGORIES = ["天然石", "配件", "耗材", "其他"]

# 設定欄位順序 (完全依照您的要求)
ALL_COLUMNS = [
    '編號', '倉庫', '分類', '名稱', 
    '寬度mm', '長度mm', '形狀', '五行', 
    '庫存(顆)', '單顆成本'
]

st.set_page_config(page_title="GemCraft 日常庫存系統", layout="wide")
st.title("💎 GemCraft 日常出入庫與盤點系統")

# 1. 初始化資料庫
if not os.path.exists(MASTER_FILE):
    pd.DataFrame(columns=ALL_COLUMNS).to_csv(MASTER_FILE, index=False, encoding='utf-8-sig')

def load_data():
    try:
        df = pd.read_csv(MASTER_FILE, encoding='utf-8-sig')
        # 確保資料庫包含所有標準欄位，若無則補空值
        for col in ALL_COLUMNS:
            if col not in df.columns:
                df[col] = 0 if "庫存" in col or "成本" in col else ""
        # 強制依照指定順序排列
        return df[ALL_COLUMNS]
    except Exception as e:
        st.error(f"讀取資料庫失敗: {e}")
        return pd.DataFrame(columns=ALL_COLUMNS)

df = load_data()

# --- 功能分頁 ---
tab1, tab2, tab3, tab4 = st.tabs(["🧮 作品設計扣量", "📥 入庫與盤點修正", "🔍 庫存查詢與報表", "📤 上傳更新數據"])

# --- Tab 1: 作品設計扣量 ---
with tab1:
    st.subheader("🎨 作品設計領料 (出庫)")
    wh = st.selectbox("選擇出庫倉庫", WAREHOUSES, key="out_wh")
    items = df[df['倉庫'] == wh]
    
    if not items.empty:
        # 顯示格式：名稱 (餘額)
        item_labels = items.apply(lambda r: f"{r['名稱']} (餘:{int(r['庫存(顆)'])})", axis=1).tolist()
        sel_label = st.selectbox("選擇材料", item_labels)
        sel_name = sel_label.split(" (")[0]
        
        qty = st.number_input("扣除數量", min_value=1, value=1)
        note = st.text_input("設計備註 (例如：訂單編號或作品名)")
        
        if st.button("✅ 確認領料扣庫存"):
            # 找到對應的那一行
            idx = df[(df['名稱'] == sel_name) & (df['倉庫'] == wh)].index[0]
            current_stock = df.at[idx, '庫存(顆)']
            
            if current_stock >= qty:
                df.at[idx, '庫存(顆)'] -= qty
                df.to_csv(MASTER_FILE, index=False, encoding='utf-8-sig')
                st.success(f"扣除成功！{sel_name} 剩餘數量：{int(df.at[idx, '庫存(顆)'])}")
                time.sleep(1)
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
            sel_mod = st.selectbox("選擇商品", mod_items['名稱'].tolist(), key="mod_sel")
            # 取得目前庫存
            current_q = df[(df['名稱'] == sel_mod) & (df['倉庫'] == wh_mod)]['庫存(顆)'].values[0]
            st.write(f"目前系統庫存：**{int(current_q)}**")
            
            new_q = st.number_input("修正後的實際庫存總數", min_value=0, value=int(current_q))
            if st.button("🔧 修正庫存"):
                idx = df[(df['名稱'] == sel_mod) & (df['倉庫'] == wh_mod)].index[0]
                df.at[idx, '庫存(顆)'] = new_q
                df.to_csv(MASTER_FILE, index=False, encoding='utf-8-sig')
                st.success("庫存修正完成！")
                st.rerun()
        else:
            st.info("該倉庫目前沒有商品。")
            
    else: # 新商品入庫
        with st.form("add_new_item"):
            st.write("輸入新商品詳細資訊")
            c1, c2 = st.columns(2)
            new_wh = c1.selectbox("存入倉庫", WAREHOUSES)
            new_cat = c1.selectbox("分類", CATEGORIES)
            new_name = c2.text_input("商品名稱")
            new_qty = c2.number_input("初始庫存(顆)", min_value=1, value=1)
            
            c3, c4 = st.columns(2)
            new_w = c3.text_input("寬度mm")
            new_l = c4.text_input("長度mm")
            new_shape = c3.text_input("形狀")
            new_element = c4.text_input("五行")
            
            # 雖然此 App 不計算成本，但保留欄位以便資料完整
            new_cost = st.number_input("單顆成本 (可填0)", min_value=0.0, value=0.0)
            
            if st.form_submit_button("➕ 建立新項目"):
                new_row = {
                    '編號': f"OP{int(time.time())}",
                    '倉庫': new_wh, '分類': new_cat, '名稱': new_name,
                    '寬度mm': new_w, '長度mm': new_l, 
                    '形狀': new_shape, '五行': new_element,
                    '庫存(顆)': new_qty, '單顆成本': new_cost
                }
                df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
                # 存檔時確保欄位順序正確
                df = df[ALL_COLUMNS]
                df.to_csv(MASTER_FILE, index=False, encoding='utf-8-sig')
                st.success("新商品已成功入庫！")
                st.rerun()

# --- Tab 3: 庫存查詢與報表下載 ---
with tab3:
    st.subheader("📋 庫存總覽表")
    # 直接顯示所有欄位，不隱藏成本
    st.dataframe(df, use_container_width=True)
    
    csv = df.to_csv(index=False).encode('utf-8-sig')
    st.download_button(
        label="📥 下載完整庫存報表",
        data=csv,
        file_name=f'inventory_{time.strftime("%Y%m%d")}.csv',
        mime='text/csv',
    )

# --- Tab 4: 上傳報表更新 ---
with tab4:
    st.subheader("📤 大量數據更新")
    st.info("請上傳 CSV 檔案。系統將只讀取以下欄位進行更新，多餘欄位將被忽略。")
    st.code(", ".join(ALL_COLUMNS), language="text")
    
    uploaded_file = st.file_uploader("選擇 CSV 檔案", type="csv")
    if uploaded_file is not None:
        try:
            new_df = pd.read_csv(uploaded_file)
            
            # 檢查關鍵欄位是否存在
            required_cols = ['倉庫', '名稱', '庫存(顆)']
            if set(required_cols).issubset(new_df.columns):
                
                # 自動補齊缺失的標準欄位 (設為空或0)
                for col in ALL_COLUMNS:
                    if col not in new_df.columns:
                        new_df[col] = 0 if "庫存" in col or "成本" in col else ""
                
                # 只保留我們需要的欄位，並依照正確順序排列
                final_df = new_df[ALL_COLUMNS]
                
                st.write("預覽將寫入的資料 (前 5 筆):")
                st.dataframe(final_df.head())
                
                if st.button("⚠️ 確認覆蓋系統數據"):
                    final_df.to_csv(MASTER_FILE, index=False, encoding='utf-8-sig')
                    st.success("數據已成功更新！請重新整理頁面。")
                    time.sleep(2)
                    st.rerun()
            else:
                st.error(f"檔案缺少關鍵欄位！必須包含：{required_cols}")
        except Exception as e:
            st.error(f"檔案讀取錯誤: {e}")
