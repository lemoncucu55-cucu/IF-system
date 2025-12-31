# --- Tab 4: 上傳報表更新 (強力讀取版) ---
with tab4:
    st.subheader("📤 大量數據更新")
    st.info("支援 Excel 轉出的 CSV (Big5 或 UTF-8 皆可)。")
    st.code(", ".join(ALL_COLUMNS), language="text")
    
    uploaded_file = st.file_uploader("選擇 CSV 檔案", type="csv")
    if uploaded_file is not None:
        try:
            # 嘗試 1: 使用 UTF-8 (標準格式)
            try:
                new_df = pd.read_csv(uploaded_file, encoding='utf-8-sig')
            except UnicodeDecodeError:
                # 嘗試 2: 如果失敗，嘗試 Big5 (Excel 預設格式)
                uploaded_file.seek(0) # 重置讀取指標
                new_df = pd.read_csv(uploaded_file, encoding='big5')

            # 去除欄位名稱前後的空白 (Excel 常見問題)
            new_df.columns = new_df.columns.str.strip()

            # 檢查關鍵欄位是否存在
            required_cols = ['倉庫', '名稱', '庫存(顆)']
            
            # 檢查是否有缺漏
            missing = [c for c in required_cols if c not in new_df.columns]
            
            if not missing:
                # 自動補齊缺失的標準欄位
                for col in ALL_COLUMNS:
                    if col not in new_df.columns:
                        new_df[col] = 0 if "庫存" in col or "成本" in col else ""
                
                # 只保留需要的欄位並排序
                final_df = new_df[ALL_COLUMNS]
                
                st.write("預覽讀取結果 (前 5 筆):")
                st.dataframe(final_df.head())
                
                if st.button("⚠️ 確認覆蓋系統數據"):
                    final_df.to_csv(MASTER_FILE, index=False, encoding='utf-8-sig')
                    st.success("數據已成功更新！請重新整理頁面。")
                    time.sleep(2)
                    st.rerun()
            else:
                st.error(f"欄位辨識失敗！缺少以下欄位：{missing}")
                st.warning("請檢查您的 CSV 標題列是否包含上述名稱。如果是亂碼，請嘗試另存為 'CSV UTF-8' 格式。")
                st.write("程式讀到的欄位名稱：", list(new_df.columns))
                
        except Exception as e:
            st.error(f"檔案讀取發生未預期的錯誤: {e}")
