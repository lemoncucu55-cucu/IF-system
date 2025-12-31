import streamlit as st
import pandas as pd
import os
import time
import io  # 關鍵模組：用於處理複製貼上的文字

# --- 1. 基礎參數設定 ---
MASTER_FILE = 'ops_inventory.csv'
WAREHOUSES = ["Imeng", "千畇"]
CATEGORIES = ["天然石", "配件", "耗材", "其他"]

# 欄位設定
ALL_COLUMNS = [
    '編號', '倉庫', '分類', '名稱', 
    '寬度mm', '長度mm', '形狀', '五行', 
    '庫存(顆)', '單顆成本'
]

st.set_page_config(page_title="GemCraft 日常庫存系統", layout="wide")
st.title("💎 GemCraft 日常出入庫與盤點系統")

# --- 2. 初始化資料庫 ---
if not os.path.exists(MASTER_FILE):
    pd.DataFrame(columns=ALL_COLUMNS).to_csv(MASTER_FILE, index=False, encoding='utf-8-sig')

def load_data():
    try:
        df = pd.read_csv(MASTER_FILE, encoding='utf-8-sig')
        # 補齊欄位
        for col in ALL_COLUMNS:
            if col not in df.columns:
                if any(x in col for x in ["庫存", "成本", "mm", "價"]):
                    df[col] = 0
                else:
                    df[col] = ""
        return df[ALL_COLUMNS]
    except Exception as e:
        return pd.DataFrame(columns=ALL_COLUMNS)

df = load_data()

# --- 3. 建立功能分頁 ---
tab1, tab2, tab3, tab4 = st.tabs(["🧮 作品設計扣量", "📥 入庫與盤點修正", "🔍 庫存查詢與報表", "📤 複製貼上更新 (除錯版)"])

# --- Tab 1: 作品設計扣量 ---
with tab1:
    st.subheader("🎨 作品設計領料")
    wh = st.selectbox("選擇出庫倉庫", WAREHOUSES, key="out_wh")
    items = df[df['倉庫'] == wh]
    
    if not items.empty:
        item_labels = items.apply(lambda r: f"{r['名稱']} (餘:{int(r['庫存(顆)'])})", axis=1).tolist()
        sel_label = st.selectbox("選擇材料", item_labels)
        sel_name = sel_label.split(" (")[0]
        qty = st.number_input("扣除數量", min_value=1, value=1)
        note = st.text_input("設計備註")
        
        if st.button("✅ 確認領料"):
            idx = df[(df['名稱'] == sel_name) & (df['倉庫'] == wh)].index[0]
            # 檢查是否夠扣
            if df.at[idx, '庫存(顆)'] >= qty:
                df.at[idx, '庫存(顆)'] -= qty
                df.to_csv(MASTER_FILE, index=False, encoding='utf-8-sig')
                st.success(f"扣除成功！{sel_name} 剩餘數量：{int(df.at[idx, '庫存(顆)'])}")
                time.sleep(1)
                st.rerun()
            else:
                st.error("庫存不足！")
    else:
        st.info("該倉庫無商品。")

# --- Tab 2: 入庫與盤點修正 (已修復崩潰問題) ---
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
            
            # --- 關鍵修正：防止負數庫存導致崩潰 ---
            # 如果目前庫存是負的 (例如 -96)，預設值改為 0，避免低於 min_value=0
            safe_value = max(0, int(current_q))
            
            new_q = st.number_input("修正後庫存", min_value=0, value=safe_value)
            
            if st.button("🔧 修正庫存"):
                idx = df[(df['名稱'] == sel_mod) & (df['倉庫'] == wh_mod)].index[0]
                df.at[idx, '庫存(顆)'] = new_q
                df.to_csv(MASTER_FILE, index=False, encoding='utf-8-sig')
                st.success("庫存修正完成！")
                st.rerun()
        else:
            st.info("該倉庫無商品。")
    else:
        with st.form("add_new_item"):
            c1, c2 = st.columns(2)
            new_wh = c1.selectbox("存入倉庫", WAREHOUSES)
            new_cat = c1.selectbox("分類", CATEGORIES)
            new_name = c2.text_input("商品名稱")
            new_qty = c2.number_input("初始庫存", min_value=1, value=1)
            c3, c4 = st.columns(2)
            new_w = c3.text_input("寬度mm")
            new_l = c4.text_input("長度mm")
            new_shape = c3.text_input("形狀")
            new_element = c4.text_input("五行")
            new_cost = st.number_input("單顆成本", min_value=0.0, value=0.0)
            if st.form_submit_button("➕ 建立新項目"):
                new_row = {
                    '編號': f"OP{int(time.time())}", '倉庫': new_wh, '分類': new_cat, '名稱': new_name,
                    '寬度mm': new_w, '長度mm': new_l, '形狀': new_shape, '五行': new_element,
                    '庫存(顆)': new_qty, '單顆成本': new_cost
                }
                df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
                df = df[ALL_COLUMNS]
                df.to_csv(MASTER_FILE, index=False, encoding='utf-8-sig')
                st.success("入庫成功！")
                st.rerun()

# --- Tab 3: 庫存查詢 ---
with tab3:
    st.subheader("📋 庫存總覽")
    st.dataframe(df, use_container_width=True)
    st.download_button("📥 下載報表", df.to_csv(index=False).encode('utf-8-sig'), f'inv_{time.strftime("%Y%m%d")}.csv', 'text/csv')

# --- Tab 4: 複製貼上更新 (Error Killer) ---
with tab4:
    st.subheader("📤 複製貼上更新 (Error Killer)")
    st.info("💡 操作方式：從 Excel 複製表格 (含標題)，直接貼在下方。")
    
    paste_data = st.text_area("請在此貼上 Excel 資料", height=300)
    
    if paste_data:
        try:
            # 使用更寬容的讀取設定：跳過壞掉的行
            df_new = pd.read_csv(io.StringIO(paste_data), sep='\t', on_bad_lines='skip')
            
            # 清理標題
            df_new.columns = df_new.columns.str.strip()
            
            # 欄位對照
            rename_map = {'現有庫存': '庫存(顆)', '數量': '庫存(顆)', '成本': '單顆成本'}
            df_new.rename(columns=rename_map, inplace=True)
            
            # 檢查欄位
            required = ['倉庫', '名稱', '庫存(顆)']
            missing = [c for c in required if c not in df_new.columns]
            
            if not missing:
                for col in ALL_COLUMNS:
                    if col not in df_new.columns:
                        if any(x in col for x in ["庫存", "成本", "mm", "價"]):
                            df_new[col] = 0
                        else:
                            df_new[col] = ""
                
                final_df = df_new[ALL_COLUMNS]
                st.write("✅ 成功讀取！資料預覽：")
                st.dataframe(final_df.head())
                
                if st.button("⚠️ 確認覆蓋"):
                    final_df.to_csv(MASTER_FILE, index=False, encoding='utf-8-sig')
                    st.success("更新成功！")
                    time.sleep(1)
                    st.rerun()
            else:
                st.error("❌ 欄位對應失敗")
                st.warning(f"系統找不到這些關鍵欄位: {missing}")
                st.write("---")
                st.write("🔍 **系統實際讀到的欄位如下 (請檢查是否有錯字或亂碼):**")
                st.code(df_new.columns.tolist())
                
        except Exception as e:
            st.error("❌ 發生未預期的錯誤")
            st.exception(e)
