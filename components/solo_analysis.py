import streamlit as st
import pandas as pd
from main_test import get_favorites_data  # 或實際存放 get_favorites_data 的模組


def tab1_module():
    st.header("個別分析")
    fav_df = get_favorites_data()
    if fav_df.empty:
            st.info("⭐ 尚未有收藏房產，無法比較")
    else:
        options = fav_df['標題'] + " | " + fav_df['地址']
        col1, col2 = st.columns(2)
        with col1:
            choice_a = st.selectbox("選擇房屋 A", options, key="compare_a")
        with col2:
            choice_b = st.selectbox("選擇房屋 B", options, key="compare_b")
    

