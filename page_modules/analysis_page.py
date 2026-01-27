# page_modules/analysis_page.py

# 添加路徑設定
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 直接定義 CATEGORY_COLORS（避免 import 問題）
CATEGORY_COLORS = {
    "教育": "#1E90FF",        # 藍色
    "購物": "#FF8C00",        # 橘色
    "交通運輸": "#800080",     # 紫色
    "健康與保健": "#32CD32",   # 綠色
    "餐飲美食": "#FF4500",     # 紅色
    "生活服務": "#FF1493",     # 深粉色
}

# 繼續其他 imports...
import math
import json
import requests
import streamlit as st
import time
from string import Template
from streamlit.components.v1 import html
from components.solo_analysis import tab1_module
import google.generativeai as genai
import pandas as pd
from streamlit_echarts import st_echarts

# 嘗試從 components 匯入模組
try:
    from components.place_types import PLACE_TYPES, ENGLISH_TO_CHINESE
except ImportError:
    # 如果找不到，創建簡單版本
    PLACE_TYPES = {}
    ENGLISH_TO_CHINESE = {}

def get_favorites_data():
    """取得收藏的房屋資料（暫時放在這裡）"""
    if 'favorites' not in st.session_state or not st.session_state.favorites:
        return pd.DataFrame()
    
    all_df = None
    if 'all_properties_df' in st.session_state and not st.session_state.all_properties_df.empty:
        all_df = st.session_state.all_properties_df
    elif 'filtered_df' in st.session_state and not st.session_state.filtered_df.empty:
        all_df = st.session_state.filtered_df
    
    if all_df is None or all_df.empty:
        return pd.DataFrame()
    
    fav_ids = st.session_state.favorites
    fav_df = all_df[all_df['編號'].astype(str).isin(map(str, fav_ids))].copy()
    return fav_df

def render_analysis_page():
    """渲染分析頁面"""
    st.title("📊 分析頁面")
    
    # 初始化收藏
    if 'favorites' not in st.session_state:
        st.session_state.favorites = set()
    
    # Tab 分頁
    tab1, tab2, tab3 = st.tabs(["個別分析", "房屋比較", "市場趨勢分析"])
    
    # Tab1: 個別分析
    with tab1:
        tab1_module()
    
    # Tab2: 房屋比較
    with tab2:
        analyzer = ComparisonAnalyzer()
        analyzer.render_comparison_tab()
    
    # Tab3: 市場趨勢分析
    with tab3:
        analyzer = MarketTrendAnalyzer()
        analyzer.render_analysis_tab()

# 如果直接執行此檔案
if __name__ == "__main__":
    render_analysis_page()
