{\rtf1\ansi\ansicpg950\cocoartf2821
\cocoatextscaling0\cocoaplatform0{\fonttbl\f0\fswiss\fcharset0 Helvetica;}
{\colortbl;\red255\green255\blue255;}
{\*\expandedcolortbl;;}
\paperw11900\paperh16840\margl1440\margr1440\vieww11520\viewh8400\viewkind0
\pard\tx720\tx1440\tx2160\tx2880\tx3600\tx4320\tx5040\tx5760\tx6480\tx7200\tx7920\tx8640\pardirnatural\partightenfactor0

\f0\fs24 \cf0 import streamlit as st\
import pandas as pd\
import os\
import time\
from datetime import date, datetime\
\
# \uc0\u35373 \u23450 \
MASTER_FILE = 'inventory_master.csv'\
HISTORY_FILE = 'inventory_history.csv'\
COLUMNS = ['\uc0\u32232 \u34399 ', '\u20489 \u24235 ', '\u20998 \u39006 ', '\u21517 \u31281 ', '\u23532 \u24230 mm', '\u38263 \u24230 mm', '\u24418 \u29376 ', '\u20116 \u34892 ', '\u36914 \u36008 \u32317 \u20729 ', '\u36914 \u36008 \u25976 \u37327 (\u38982 )', '\u36914 \u36008 \u26085 \u26399 ', '\u36914 \u36008 \u24288 \u21830 ', '\u24235 \u23384 (\u38982 )', '\u21934 \u38982 \u25104 \u26412 ']\
WAREHOUSES = ["Imeng", "\uc0\u21315 \u30023 "]\
\
st.set_page_config(page_title="GemCraft \uc0\u36001 \u21209 \u36914 \u36008 \u31995 \u32113 ", layout="wide")\
st.title("\uc0\u55357 \u56496  GemCraft \u36001 \u21209 \u33287 \u36914 \u36008 \u31649 \u29702 ")\
\
# \uc0\u21021 \u22987 \u21270 \u36039 \u26009 \u24235 \
if not os.path.exists(MASTER_FILE):\
    pd.DataFrame(columns=COLUMNS).to_csv(MASTER_FILE, index=False, encoding='utf-8-sig')\
\
df = pd.read_csv(MASTER_FILE, encoding='utf-8-sig')\
\
# \uc0\u20596 \u37002 \u27396 \
with st.sidebar:\
    pwd = st.text_input("\uc0\u20027 \u31649 \u23494 \u30908 ", type="password")\
    if pwd != "admin123":\
        st.error("\uc0\u35531 \u36664 \u20837 \u27491 \u30906 \u23494 \u30908 \u20197 \u25805 \u20316 \u36001 \u21209 \u31995 \u32113 ")\
        st.stop()\
    menu = st.radio("\uc0\u21151 \u33021 \u36984 \u21934 ", ["\u55356 \u56725  \u26032 \u21830 \u21697 \u24314 \u27284 ", "\u55357 \u56520  \u36914 \u36008 \u32000 \u37636 \u22577 \u34920 ", "\u55357 \u57056 \u65039  \u36039 \u26009 \u24235 \u32173 \u35703 "])\
\
# 1. \uc0\u26032 \u21830 \u21697 \u24314 \u27284 \
if menu == "\uc0\u55356 \u56725  \u26032 \u21830 \u21697 \u24314 \u27284 ":\
    with st.form("new_item_form"):\
        st.subheader("\uc0\u55357 \u56550  \u21830 \u21697 \u22522 \u26412 \u36039 \u35338 \u33287 \u25104 \u26412 \u36664 \u20837 ")\
        c1, c2, c3 = st.columns(3)\
        wh = c1.selectbox("\uc0\u20489 \u24235 ", WAREHOUSES)\
        cat = c2.selectbox("\uc0\u20998 \u39006 ", ["\u22825 \u28982 \u30707 ", "\u37197 \u20214 ", "\u32791 \u26448 "])\
        name = c3.text_input("\uc0\u21830 \u21697 \u21517 \u31281 ")\
        \
        s1, s2, s3 = st.columns(3)\
        w_mm = s1.number_input("\uc0\u23532 \u24230 mm", min_value=0.0)\
        l_mm = s2.number_input("\uc0\u38263 \u24230 mm", min_value=0.0)\
        shape = s3.text_input("\uc0\u24418 \u29376 ")\
        \
        f1, f2, f3 = st.columns(3)\
        qty = f1.number_input("\uc0\u36914 \u36008 \u25976 \u37327 (\u38982 )", min_value=1)\
        total_cost = f2.number_input("\uc0\u36914 \u36008 \u32317 \u20729 ", min_value=0.0)\
        vendor = f3.text_input("\uc0\u24288 \u21830 ")\
        \
        if st.form_submit_button("\uc0\u55357 \u56510  \u24314 \u31435 \u20006 \u23384 \u27284 "):\
            avg_cost = total_cost / qty if qty > 0 else 0\
            new_data = \{\
                '\uc0\u32232 \u34399 ': f"ST\{int(time.time())\}", '\u20489 \u24235 ': wh, '\u20998 \u39006 ': cat, '\u21517 \u31281 ': name,\
                '\uc0\u23532 \u24230 mm': w_mm, '\u38263 \u24230 mm': l_mm, '\u24418 \u29376 ': shape, '\u20116 \u34892 ': "",\
                '\uc0\u36914 \u36008 \u32317 \u20729 ': total_cost, '\u36914 \u36008 \u25976 \u37327 (\u38982 )': qty, '\u36914 \u36008 \u26085 \u26399 ': date.today(),\
                '\uc0\u36914 \u36008 \u24288 \u21830 ': vendor, '\u24235 \u23384 (\u38982 )': qty, '\u21934 \u38982 \u25104 \u26412 ': avg_cost\
            \}\
            df = pd.concat([df, pd.DataFrame([new_data])], ignore_index=True)\
            df.to_csv(MASTER_FILE, index=False, encoding='utf-8-sig')\
            st.success(f"\uc0\u21830 \u21697  \{name\} \u24050 \u25104 \u21151 \u24314 \u27284 \u65292 \u21934 \u38982 \u25104 \u26412 \u28858 : \{avg_cost:.2f\}")\
\
# 2. \uc0\u36914 \u36008 \u32000 \u37636 \u22577 \u34920 \
elif menu == "\uc0\u55357 \u56520  \u36914 \u36008 \u32000 \u37636 \u22577 \u34920 ":\
    st.subheader("\uc0\u20840 \u37096 \u24235 \u23384 \u33287 \u25104 \u26412 \u28165 \u21934 ")\
    st.dataframe(df)\
    \
    csv = df.to_csv(index=False).encode('utf-8-sig')\
    st.download_button("\uc0\u55357 \u56549  \u19979 \u36617 \u36001 \u21209 \u32317 \u34920 ", csv, "financial_master.csv", "text/csv")}