
    '訂單編號', '建立時間', '客戶名稱', '客戶電話', '商品種類', '客製品項',
    '手圍', '生日', '農曆生日', '出生時間', '喜神', '忌神',
    '流年去年', '流年今年', '流年明年', '階段數',
    '總售價', '成本', '運費', '工本費', '總成本', '備註', '狀態', '建單人'
    '總售價', '成本', '運費', '工本費', '總成本',
    '收件人姓名', '收件電話', '收件類型', '收件地址', '超商名稱門市',
    '出貨方式', '物流單號', '出貨日期',
    '備註', '狀態', '建單人'
]

CUSTOM_ITEMS = ["手鍊", "項鍊", "鑰匙圈"]
]

DELIVERY_TYPES = ["🏠 住家", "🏪 超商"]
SHIPPING_METHODS = ["未指定", "郵寄", "宅配", "7-11 店到店", "全家店到店", "面交", "其他"]

STATUS_FLOW    = ["未付款未出貨", "已付款未出貨", "未付款已出貨", "已完成", "已取消"]
WUXING_OPTS    = ["金", "木", "水", "火", "土"]
            "喜神":     safe_get(latest, "喜神"),
            "忌神":     safe_get(latest, "忌神"),
            "生日":     safe_get(latest, "生日"),
            "農曆生日": safe_get(latest, "農曆生日"),
            "出生時間":  safe_get(latest, "出生時間"),
            "收件人姓名": "",
            "收件電話":  "",
            "收件類型":  "",
            "收件地址":  "",
            "超商名稱門市": "",
            "收件人姓名": safe_get(latest, "收件人姓名"),
            "收件電話":  safe_get(latest, "收件電話"),
            "收件類型":  safe_get(latest, "收件類型"),
            "收件地址":  safe_get(latest, "收件地址"),
            "超商名稱門市": safe_get(latest, "超商名稱門市"),
        })

    if new_rows:
        xi_shen = c6.multiselect("喜神", WUXING_OPTS, default=default_xi)
        ji_shen = c7.multiselect("忌神", WUXING_OPTS, default=default_ji)

        st.subheader("出貨資料")
        d1, d2 = st.columns(2)
        recv_name = d1.text_input("收件人姓名", value=prefill.get("收件人姓名", "") or customer_name)
        recv_phone = d2.text_input("收件電話", value=prefill.get("收件電話", "") or customer_phone)

        default_delivery_type = prefill.get("收件類型", "")
        delivery_type = st.selectbox(
            "收件類型",
            DELIVERY_TYPES,
            index=DELIVERY_TYPES.index(default_delivery_type) if default_delivery_type in DELIVERY_TYPES else 0,
            key="create_order_delivery_type",
        )
        if delivery_type == "🏪 超商":
            d3, d4 = st.columns(2)
            recv_addr = d3.text_input("超商地址（選填）", value=prefill.get("收件地址", ""))
            store_name = d4.text_input("超商名稱／門市", value=prefill.get("超商名稱門市", ""))
        else:
            recv_addr = st.text_input("收件地址", value=prefill.get("收件地址", ""))
            store_name = ""

        s1, s2, s3 = st.columns(3)
        shipping_method = s1.selectbox("出貨方式", SHIPPING_METHODS, key="create_order_shipping_method")
        tracking_no = s2.text_input("物流單號", placeholder="出貨後填寫")
        ship_date = s3.text_input("出貨日期", placeholder="例：2026-07-20")

        order_note = st.text_area("備註")

        if st.form_submit_button("✅ 建立訂單", use_container_width=True):
                    "運費":     str(shipping_fee),
                    "工本費":   str(labor_fee),
                    "總成本":   str(cost_price + shipping_fee + labor_fee),
                    "收件人姓名": recv_name or customer_name,
                    "收件電話":  recv_phone or customer_phone,
                    "收件類型":  delivery_type,
                    "收件地址":  recv_addr,
                    "超商名稱門市": store_name,
                    "出貨方式":  shipping_method,
                    "物流單號":  tracking_no,
                    "出貨日期":  ship_date,
                    "備註":     order_note,
                    "狀態":     "未付款未出貨",
                    "建單人":   order_creator,
                st.write(
                    f"**喜神：** {safe_get(sel_order,'喜神') or '-'} | "
                    f"**忌神：** {safe_get(sel_order,'忌神') or '-'}")
                st.write(
                    f"**出貨資料：** "
                    f"{safe_get(sel_order,'收件類型') or '-'} | "
                    f"收件人：{safe_get(sel_order,'收件人姓名') or '-'} | "
                    f"電話：{safe_get(sel_order,'收件電話') or '-'} | "
                    f"地址／門市：{safe_get(sel_order,'超商名稱門市') or safe_get(sel_order,'收件地址') or '-'}")
                st.write(
                    f"**物流：** "
                    f"方式：{safe_get(sel_order,'出貨方式') or '-'} | "
                    f"單號：{safe_get(sel_order,'物流單號') or '-'} | "
                    f"出貨日期：{safe_get(sel_order,'出貨日期') or '-'}")
                if safe_get(sel_order, "備註"):
