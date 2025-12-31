# --- Tab 4: 上傳報表更新 (強力解碼版) ---
with tab4:
    st.subheader("📤 大量數據更新")
    st.info("支援 Excel 轉出的 CSV (Mac/Windows 皆可)。")
    st.code(", ".join(ALL_COLUMNS), language="text")
    
    uploaded_file = st.file_uploader("選擇 CSV 檔案", type="csv")
    if uploaded_file is not None:
        try:
            df_new = None
            # 嘗試 3 種常見編碼
            encodings_to_try = ['utf-8-sig', 'big5', 'cp950']
            
            for enc in encodings_to_try:
                try:
                    uploaded_file.seek(0) # 每次重試前，把讀取指針歸零
                    df_new = pd.read_csv(uploaded_file, encoding=enc)
                    # 測試：如果讀得懂中文標題 '名稱'，代表編碼對了
                    if "名稱" in df_new.columns:
                        break
                except:
                    continue
            
            if df_new is None:
                st.error("無法辨識檔案編碼，請嘗試在 Excel 中另存為 'CSV UTF-8 (逗號分隔)'。")
                st.stop()

            # 去除欄位名稱前後可能多餘的空白
            df_new.columns = df_new.columns.str.strip()

            # 檢查關鍵欄位 (允許 '庫存(顆)' 或 '現有庫存' 兩種寫法)
            # 這裡做一個對照轉換，避免您 Excel 標題打錯
            df_new.rename(columns={'現有庫存': '庫存(顆)'}, inplace=True)

            required_cols = ['倉庫', '名稱', '庫存(顆)']
            
            # 檢查是否有缺漏關鍵欄位
            missing = [c for c in required_cols if c not in df_new.columns]
            
            if not missing:
                # 1. 自動補齊缺失的標準欄位 (設為 0 或 空白)
                for col in ALL_COLUMNS:
                    if col not in df_new.columns:
                        # 如果是數字類型的欄位，補 0
                        if "庫存" in col or "成本" in col or "mm" in col or "價" in col:
                            df_new[col] = 0
                        else:
                            df_new[col] = ""
                
                # 2. 強制依照系統的順序排列 (這步很重要，讓顯示正確)
                final_df = df_new[ALL_COLUMNS]
                
                st.write("✅ 成功讀取！預覽資料 (前 5 筆)：")
                st.dataframe(final_df.head())
                
                if st.button("⚠️ 確認覆蓋系統數據"):
                    final_df.to_csv(MASTER_FILE, index=False, encoding='utf-8-sig')
                    st.success("數據已成功更新！正在重新整理...")
                    time.sleep(2)
                    st.rerun()
            else:
                st.error(f"欄位辨識失敗！您的檔案缺少以下欄位 (或標題亂碼)：{missing}")
                st.write("程式目前讀到的欄位名稱：", list(df_new.columns))
                st.warning("若上方顯示的是亂碼，請在 Excel 另存新檔時選擇 **「CSV UTF-8 (逗號分隔)」**。")
                
        except Exception as e:
            st.error(f"檔案處理發生錯誤: {e}")
