# analysis_page.py - 簡化後的主檔案
import streamlit as st

# 從 config 匯入設定
from config import CATEGORY_COLORS

# 匯入模組
from components.solo_analysis import tab1_module
from components.favorites import FavoritesManager
from components.geocoding import geocode_address
from utils.data_loaders import load_real_estate_csv, load_population_csv

# 匯入分析模組
from components.comparison import ComparisonAnalyzer
from components.market_trend import MarketTrendAnalyzer


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
