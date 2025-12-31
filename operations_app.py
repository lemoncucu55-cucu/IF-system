# --- Tab 4: 複製貼上更新 (終極解法) ---
import io # 記得在檔案最上方加入 import io

with tab4:
    st.subheader("📤 複製貼上更新數據")
    st.info("這是最穩定的方法。請直接從 Excel 複製資料，然後貼在下方。")
    
    with st.expander("👉 點此查看操作教學", expanded=True):
        st.markdown("""
        1. 在您的電腦打開 Excel 檔案。
        2. 選取您要更新的範圍（**務必包含標題列**：倉庫、名稱、庫存...）。
        3. 按下複製 (**Ctrl+C** 或 **Cmd+C**)。
        4. 在下方文字框按貼上 (**Ctrl+V** 或 **Cmd+V**)。
        5. 確認預覽無誤後，點擊按鈕更新。
        """)

    # 1. 提供一個超大文字框讓您貼上
    paste_data = st.text_area("請在此貼上 Excel 資料", height=300, help="點擊這裡，然後按下貼上")
    
    if paste_data:
        try:
            # 2. 告訴 Pandas 這是 Tab 分隔的文字 (Excel 複製出來的預設格式)
            df_new = pd.read_csv(io.StringIO(paste_data), sep='\t')
            
            # 3. 清理欄位名稱
            df_new.columns = df_new.columns.str.strip()
            
            # 4. 欄位名稱容錯對照
            rename_map = {
                '現有庫存': '庫存(顆)',
                '數量': '庫存(顆)',
                '成本': '單顆成本',
                'Width': '寬度mm',
                'Length': '長度mm'
            }
            df_new.rename(columns=rename_map, inplace=True)
            
            # 5. 檢查關鍵欄位
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
                st.error(f"❌ 缺少關鍵欄位，請檢查您複製的標題是否包含：{required}")
                st.write("讀到的欄位：", list(df_new.columns))
                
        except Exception as e:
            st.error(f"資料解析錯誤：{e}")
            st.warning("請確保您是直接從 Excel 表格中複製資料。")
