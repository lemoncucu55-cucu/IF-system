import streamlit as st
import pandas as pd
import os
import time

# 檔案設定
MASTER_FILE = 'ops_inventory.csv'
WAREHOUSES = ["Imeng", "千畇"]
CATEGORIES = ["天然石", "配件", "耗材", "其他"]

# 設定標準欄位順序
ALL_COLUMNS = [
    '編號', '倉庫', '分類', '名稱', 
    '寬度mm', '長度mm', '形狀', '五行', 
    '庫存(顆)', '單顆成本'
]

st.set_page_config(page_title="GemCraft 日常庫存系統", layout="wide")
st.title("💎 GemCraft 日常庫存 - 快速編輯版")

# 初始化資料庫
if not os.path.exists(MASTER_FILE):
    pd.DataFrame(columns=ALL_COLUMNS).to_csv(MASTER_FILE, index=False, encoding='utf-8-sig')

def load_data():
    try:
        df = pd.read_csv(MASTER_FILE, encoding='utf-8-sig')
        # 確保所有欄位都存在
        for col in ALL_COLUMNS:
            if col not in df.columns:
                df[col] = 0 if "庫存" in col or "成本" in col else ""
        # 轉型態以利編輯 (數字轉數字，文字轉文字)
        df['庫存(顆)'] = pd.to_numeric(df['庫存(顆)'], errors='coerce').fillna(0)
        df['單顆成本'] = pd.to_numeric(df['單顆成本'], errors='coerce').fillna(0)
        return df[ALL_COLUMNS]
    except Exception as e:
        st.error(f"資料讀取錯誤: {e}")
        return pd.DataFrame(columns=ALL_COLUMNS)

# 讀取資料
df = load_data()

st.info("💡 操作提示：您可以直接在下方表格修改數據，或從 Excel 複製資料後，點擊表格按 `Ctrl+V` 貼上。")

with st.form("editor_form"):
    # 顯示可編輯的表格 (num_rows="dynamic" 允許新增/刪除行)
    edited_df = st.data_editor(
        df,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "倉庫": st.column_config.SelectboxColumn(options=WAREHOUSES, required=True),
            "分類": st.column_config.SelectboxColumn(options=CATEGORIES),
            "庫存(顆)": st.column_config.NumberColumn(min_value=0, step=1),
            "單顆成本": st.column_config.NumberColumn(min_value=0.0, step=0.1, format="$%.2f"),
        },
        key="inventory_editor"
    )

    # 存檔按鈕
    save_btn = st.form_submit_button("💾 確認並儲存變更")

    if save_btn:
        try:
            # 存檔前確保欄位完整
            final_df = edited_df[ALL_COLUMNS]
            final_df.to_csv(MASTER_FILE, index=False, encoding='utf-8-sig')
            st.success(f"✅ 已成功儲存 {len(final_df)} 筆資料！")
            time.sleep(1)
            st.rerun()
        except Exception as e:
            st.error(f"存檔失敗: {e}")

st.divider()

# 下載備份功能
csv = df.to_csv(index=False).encode('utf-8-sig')
st.download_button(
    label="📥 下載目前庫存備份 (CSV)",
    data=csv,
    file_name=f'inventory_backup_{time.strftime("%Y%m%d")}.csv',
    mime='text/csv',
)
