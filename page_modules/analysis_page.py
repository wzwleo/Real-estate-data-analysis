# page_modules/analysis_page.py

# 方案 1A：使用相對路徑 import
import sys
import os

# 添加父目錄到 Python 路徑
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 現在可以匯入 config
from config import CATEGORY_COLORS

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
