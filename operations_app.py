import streamlit as st
import pandas as pd
import os
import time

# 檔案設定
MASTER_FILE = 'ops_inventory.csv'
WAREHOUSES = ["Imeng", "千畇"]
CATEGORIES = ["天然石", "配件", "耗材", "其他"]

# 您指定的標準欄位順序
ALL_COLUMNS = [
    '編號', '倉庫', '分類', '名稱', 
    '寬度mm', '長度mm', '形狀', '五行', 
    '庫存(顆)', '單顆成本'
]

st.set_page_config(page_title="GemCraft 日常庫存系統", layout="wide")
st.title("💎 GemCraft 日常出入庫與盤點系統")

# 初始化資料庫
if not os.path.exists(MASTER_FILE):
    pd.DataFrame(columns=ALL_COLUMNS).to_csv(MASTER_FILE, index=False, encoding='utf-8-sig')

def load_data():
    try:
        df = pd.read_csv(MASTER_FILE, encoding='utf-8-sig')
        # 補齊可能缺失的欄位
        for col in ALL_COLUMNS:
            if col not in df.columns:
                df[col] = 0 if "庫存" in col or "成本" in col else ""
        return df[ALL_COLUMNS]
    except Exception as e:
        st.error(f"資料庫讀取失敗: {e}")
        return pd.DataFrame(columns=ALL_COLUMNS)

df = load_data()

# --- 維持原本的四個分頁設計 ---
tab1, tab2, tab3, tab4 = st.tabs(["🧮 作品設計扣量", "📥 入庫與盤點修正", "🔍 庫存查詢與報表", "📤 上傳 Excel 更新"])

# --- Tab 1: 作品設計扣量 (維持原樣) ---
with tab1:
    st.subheader("🎨 作品設計領料 (出庫)")
    wh = st.selectbox("選擇出庫倉庫", WAREHOUSES, key="out_wh")
    items = df[df['倉庫'] == wh]
    
    if not items.empty:
        item_labels = items.apply(lambda r: f"{r['名稱']} (餘:{int(r['庫存(顆)'])})", axis=1).tolist()
        sel_label = st.selectbox("選擇材料", item_labels)
        sel_name = sel_label.split(" (")[0]
        
        qty = st.number_input("扣除數量", min_value=1, value=1)
        note = st.text_input("設計備註")
        
        if st.button("✅ 確認領料扣庫存"):
            idx = df[(df['名稱'] == sel_name) & (df['倉庫'] == wh)].index[0]
            if df.at[idx, '庫存(顆)'] >= qty:
                df.at[idx, '庫存(顆)'] -= qty
                df.to_csv(MASTER_FILE, index=False, encoding='utf-8-sig')
                st.success(f"扣除成功！{sel_name} 剩餘數量：{int(df.at[idx, '庫存(顆)'])}")
                time.sleep(1)
                st.rerun()
            else:
                st.error("庫存不足！")
    else:
        st.info("此倉庫無資料。")

# --- Tab 2: 入庫與盤點修正 (維持原樣) ---
with tab2:
    st.subheader("📥 盤點修正與新物料入庫")
    mode = st.radio("操作模式", ["現有商品增減 (盤點)", "新商品初次入庫"])
    
    if mode == "現有商品增減 (盤點)":
        wh_mod = st.selectbox("選擇倉庫", WAREHOUSES, key="mod_wh")
        mod_items = df[df['倉庫'] == wh_mod]
        if not mod_items.empty:
            sel_mod = st.selectbox("選擇商品", mod_items['名稱'].tolist(), key="mod_sel")
            current_q = df[(df['名稱'] == sel_mod) & (df['倉庫'] == wh_mod)]['庫存(顆)'].values[0]
            st.write(f"目前系統庫存：**{int(current_q)}**")
            new_q = st.number_input("修正後實際庫存", min_value=0, value=int(current_q))
            if st.button("🔧 修正庫存"):
                idx = df[(df['名稱'] == sel_mod) & (df['倉庫'] == wh_mod)].index[0]
                df.at[idx, '庫存(顆)'] = new_q
                df.to_csv(MASTER_FILE, index=False, encoding='utf-8-sig')
                st.success("庫存已修正！")
                st.rerun()
        else:
            st.info("此倉庫無資料。")
            
    else: # 新商品入庫
        with st.form("add_new_item"):
            st.write("輸入新商品資訊")
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
            new_cost = st.number_input("單顆成本", min_value=0.0, value=0.0)
            
            if st.form_submit_button("➕ 建立新項目"):
                new_row = {
                    '編號': f"OP{int(time.time())}",
                    '倉庫': new_wh, '分類': new_cat, '名稱': new_name,
                    '寬度mm': new_w, '長度mm': new_l, '形狀': new_shape, '五行': new_element,
                    '庫存(顆)': new_qty, '單顆成本': new_cost
                }
                df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
                df = df[ALL_COLUMNS]
                df.to_csv(MASTER_FILE, index=False, encoding='utf-8-sig')
                st.success("新商品已入庫！")
                st.rerun()

# --- Tab 3: 庫存查詢 (維持原樣) ---
with tab3:
    st.subheader("📋 庫存總覽表")
    st.dataframe(df, use_container_width=True)
    st.download_button(
        label="📥 下載完整報表 (CSV)",
        data=df.to_csv(index=False).encode('utf-8-sig'),
        file_name=f'inventory_{time.strftime("%Y%m%d")}.csv',
        mime='text/csv',
    )

# --- Tab 4: 上傳 Excel 更新 (修正版) ---
with tab4:
    st.subheader("📤 上傳 Excel 更新數據")
    st.info("請直接上傳 **Excel (.xlsx)** 檔案。標題請使用：倉庫、名稱、庫存(顆)。")
    
    # 限制只能上傳 Excel (最穩定)
    uploaded_file = st.file_uploader("選擇 Excel (.xlsx) 檔案", type=['xlsx'])
    
    if uploaded_file is not None:
        try:
            # 使用 openpyxl 讀取 Excel，徹底解決編碼問題
            df_new = pd.read_excel(uploaded_file, engine='openpyxl')
            
            # 去除標題前後空白
            df_new.columns = df_new.columns.str.strip()
            
            # 自動修正欄位名稱 (防呆)
            rename_map = {
                '現有庫存': '庫存(顆)',
                '數量': '庫存(顆)',
                '成本': '單顆成本'
            }
            df_new.rename(columns=rename_map, inplace=True)
            
            # 檢查關鍵欄位
            required = ['倉庫', '名稱', '庫存(顆)']
            missing = [c for c in required if c not in df_new.columns]
            
            if not missing:
                # 補齊其他標準欄位
                for col in ALL_COLUMNS:
                    if col not in df_new.columns:
                        df_new[col] = 0 if "庫存" in col or "成本" in col else ""
                
                # 依照正確順序整理
                final_df = df_new[ALL_COLUMNS]
                
                st.write("✅ 讀取成功！預覽如下：")
                st.dataframe(final_df.head())
                
                if st.button("⚠️ 確認覆蓋系統數據"):
                    final_df.to_csv(MASTER_FILE, index=False, encoding='utf-8-sig')
                    st.success("數據更新成功！")
                    time.sleep(1)
                    st.rerun()
            else:
                st.error(f"❌ 缺少關鍵欄位，請檢查您的 Excel 標題是否包含：{required}")
                st.write("讀到的欄位：", list(df_new.columns))
                
        except Exception as e:
            st.error(f"檔案讀取錯誤：{e}")
            st.warning("請確認您的檔案是 .xlsx 格式，且已更新 requirements.txt")
