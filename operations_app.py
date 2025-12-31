{\rtf1\ansi\ansicpg950\cocoartf2821
\cocoatextscaling0\cocoaplatform0{\fonttbl\f0\fswiss\fcharset0 Helvetica;}
{\colortbl;\red255\green255\blue255;}
{\*\expandedcolortbl;;}
\paperw11900\paperh16840\margl1440\margr1440\vieww11520\viewh8400\viewkind0
\pard\tx720\tx1440\tx2160\tx2880\tx3600\tx4320\tx5040\tx5760\tx6480\tx7200\tx7920\tx8640\pardirnatural\partightenfactor0

\f0\fs24 \cf0 import streamlit as st\
import pandas as pd\
import os\
from datetime import datetime\
\
# \uc0\u35373 \u23450 \
MASTER_FILE = 'inventory_master.csv'\
WAREHOUSES = ["Imeng", "\uc0\u21315 \u30023 "]\
# \uc0\u38577 \u34255 \u36001 \u21209 \u25935 \u24863 \u36039 \u35338 \
SAFE_COLUMNS = ['\uc0\u32232 \u34399 ', '\u20489 \u24235 ', '\u20998 \u39006 ', '\u21517 \u31281 ', '\u23532 \u24230 mm', '\u38263 \u24230 mm', '\u24418 \u29376 ', '\u24235 \u23384 (\u38982 )']\
\
st.set_page_config(page_title="GemCraft \uc0\u26085 \u24120 \u25805 \u20316 \u31995 \u32113 ", layout="wide")\
st.title("\uc0\u55357 \u56462  GemCraft \u24235 \u23384 \u25805 \u20316 \u33287 \u35373 \u35336 \u32000 \u37636 ")\
\
if not os.path.exists(MASTER_FILE):\
    st.error("\uc0\u25214 \u19981 \u21040 \u36039 \u26009 \u24235 \u27284 \u26696 \u65292 \u35531 \u32879 \u32097 \u31649 \u29702 \u21729 \u20808 \u22519 \u34892 \u36001 \u21209 \u31995 \u32113 \u24314 \u27284 \u12290 ")\
    st.stop()\
\
# \uc0\u35712 \u21462 \u36039 \u26009 \u20006 \u38577 \u34255 \u25104 \u26412 \
master_df = pd.read_csv(MASTER_FILE, encoding='utf-8-sig')\
display_df = master_df[SAFE_COLUMNS].copy()\
\
page = st.tabs(["\uc0\u55357 \u56548  \u38936 \u29992 /\u30436 \u40670 ", "\u55358 \u56814  \u20316 \u21697 \u35373 \u35336 ", "\u55357 \u56523  \u24235 \u23384 \u26597 \u35426 "])\
\
# 1. \uc0\u38936 \u29992 /\u30436 \u40670 \
with page[0]:\
    wh_sel = st.radio("\uc0\u30446 \u21069 \u25805 \u20316 \u20489 \u24235 ", WAREHOUSES, horizontal=True)\
    filtered_items = display_df[display_df['\uc0\u20489 \u24235 '] == wh_sel]\
    \
    if not filtered_items.empty:\
        item_list = filtered_items.apply(lambda r: f"\{r['\uc0\u32232 \u34399 ']\} - \{r['\u21517 \u31281 ']\} (\u39192 :\{int(r['\u24235 \u23384 (\u38982 )'])\})", axis=1).tolist()\
        target = st.selectbox("\uc0\u36984 \u25799 \u21830 \u21697 ", item_list)\
        target_id = target.split(" - ")[0]\
        \
        with st.form("op_form"):\
            action = st.selectbox("\uc0\u21205 \u20316 ", ["\u26085 \u24120 \u38936 \u29992 ", "\u30436 \u40670 \u20462 \u27491 ", "\u25613 \u22750 \u22577 \u24290 "])\
            num = st.number_input("\uc0\u25976 \u37327 \u35722 \u21205  (\u28187 \u23569 \u35531 \u36664 \u20837 \u36000 \u25976 )", value=-1)\
            reason = st.text_input("\uc0\u20633 \u35387 \u35498 \u26126 ")\
            \
            if st.form_submit_button("\uc0\u30906 \u35469 \u26356 \u26032 "):\
                # \uc0\u26356 \u26032 \u20027 \u27284 \u26696 \
                idx = master_df[master_df['\uc0\u32232 \u34399 '] == target_id].index[0]\
                master_df.at[idx, '\uc0\u24235 \u23384 (\u38982 )'] += num\
                master_df.to_csv(MASTER_FILE, index=False, encoding='utf-8-sig')\
                st.success("\uc0\u24235 \u23384 \u24050 \u26356 \u26032 \u65281 ")\
                st.rerun()\
\
# 2. \uc0\u20316 \u21697 \u35373 \u35336  (\u26680 \u24515 \u38656 \u27714 \u65306 \u21547 \u20633 \u35387 \u27396 \u20301 )\
with page[1]:\
    if 'design_cart' not in st.session_state: st.session_state['design_cart'] = []\
    \
    st.subheader("\uc0\u55356 \u57256  \u26032 \u20316 \u21697 \u26448 \u26009 \u32068 \u21512 ")\
    c1, c2, c3 = st.columns([2, 1, 2])\
    \
    wh_design = c1.selectbox("\uc0\u26448 \u26009 \u20489 \u24235 ", WAREHOUSES)\
    d_items = display_df[display_df['\uc0\u20489 \u24235 '] == wh_design]\
    sel_item = c1.selectbox("\uc0\u36984 \u25799 \u26448 \u26009 ", d_items['\u21517 \u31281 '].unique())\
    \
    # \uc0\u25214 \u23563 \u35442 \u21517 \u31281 \u19979 \u30340 \u35215 \u26684  (\u37341 \u23565 \u21516 \u21517 \u19981 \u21516 \u35215 \u26684 )\
    specs = d_items[d_items['\uc0\u21517 \u31281 '] == sel_item]\
    sel_spec = c2.selectbox("\uc0\u36984 \u25799 \u35215 \u26684 /\u32232 \u34399 ", specs.apply(lambda r: f"\{r['\u32232 \u34399 ']\} (\{r['\u23532 \u24230 mm']\}mm)", axis=1))\
    \
    qty_design = c2.number_input("\uc0\u20351 \u29992 \u25976 \u37327 ", min_value=1, value=1)\
    note_design = c3.text_input("\uc0\u36889 \u38917 \u26448 \u26009 \u30340 \u20633 \u35387  (\u22914 \u65306 \u20027 \u30707 \u12289 \u38548 \u29664 )")\
    \
    if st.button("\uc0\u11015 \u65039  \u21152 \u20837 \u20316 \u21697 \u28165 \u21934 "):\
        target_id = sel_spec.split(" (")[0]\
        st.session_state['design_cart'].append(\{\
            '\uc0\u32232 \u34399 ': target_id, '\u21517 \u31281 ': sel_item, '\u25976 \u37327 ': qty_design, '\u20633 \u35387 ': note_design, '\u20489 \u24235 ': wh_design\
        \})\
        st.rerun()\
\
    if st.session_state['design_cart']:\
        st.table(pd.DataFrame(st.session_state['design_cart']))\
        if st.button("\uc0\u9989  \u23436 \u25104 \u35373 \u35336 \u20006 \u25187 \u38500 \u24235 \u23384 ", type="primary"):\
            for item in st.session_state['design_cart']:\
                idx = master_df[master_df['\uc0\u32232 \u34399 '] == item['\u32232 \u34399 ']].index[0]\
                master_df.at[idx, '\uc0\u24235 \u23384 (\u38982 )'] -= item['\u25976 \u37327 ']\
            master_df.to_csv(MASTER_FILE, index=False, encoding='utf-8-sig')\
            st.session_state['design_cart'] = []\
            st.success("\uc0\u20316 \u21697 \u38936 \u26009 \u23436 \u25104 \u65292 \u24235 \u23384 \u24050 \u25187 \u38500 \u12290 ")\
            st.rerun()\
\
# 3. \uc0\u24235 \u23384 \u26597 \u35426 \
with page[2]:\
    st.dataframe(display_df, use_container_width=True)}