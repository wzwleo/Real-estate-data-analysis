# page_modules/analysis_page.py
"""
分析頁面主模組
整合了三個主要功能：
1. 個別分析 (Tab1) - 使用 solo_analysis.tab1_module
2. 房屋比較 (Tab2) - 使用 ComparisonAnalyzer
3. 市場趨勢分析 (Tab3) - 使用 MarketTrendAnalyzer（如果存在）或直接實作
"""

import os
import sys
import streamlit as st

# 修正導入路徑
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# 嘗試匯入各個模組
import_success = True
missing_modules = []

try:
    from components.solo_analysis import tab1_module
except ImportError as e:
    import_success = False
    missing_modules.append(f"solo_analysis: {e}")

try:
    from components.comparison import ComparisonAnalyzer
except ImportError as e:
    import_success = False
    missing_modules.append(f"comparison: {e}")

# 嘗試匯入市場趨勢分析，如果不存在則提供替代方案
try:
    from components.market_trend import MarketTrendAnalyzer
    HAS_MARKET_TREND = True
except ImportError:
    HAS_MARKET_TREND = False
    missing_modules.append("market_trend")

def render_analysis_page():
    """渲染分析頁面"""
    st.title("📊 分析頁面")
    
    # 檢查是否成功匯入
    if not import_success:
        st.error("⚠️ 無法載入部分分析模組")
        st.warning("請檢查以下模組是否存在：")
        for module in missing_modules:
            st.write(f"- {module}")
        
        # 提供替代方案
        st.info("以下功能仍可正常使用：")
        
        # 只顯示可用的功能
        if 'tab1_module' in locals():
            st.write("✅ 個別分析")
        if 'ComparisonAnalyzer' in locals():
            st.write("✅ 房屋比較")
        if HAS_MARKET_TREND:
            st.write("✅ 市場趨勢分析")
        
        # 繼續執行可用的功能
        if not any(['tab1_module' in locals(), 'ComparisonAnalyzer' in locals(), HAS_MARKET_TREND]):
            st.error("沒有任何分析模組可用，請檢查檔案結構")
            return
    
    # 初始化 session state
    if 'favorites' not in st.session_state:
        st.session_state.favorites = set()
    
    # Tab 分頁
    tab_names = []
    if 'tab1_module' in locals():
        tab_names.append("個別分析")
    if 'ComparisonAnalyzer' in locals():
        tab_names.append("房屋比較")
    if HAS_MARKET_TREND:
        tab_names.append("市場趨勢分析")
    
    # 如果沒有可用的功能，顯示錯誤
    if not tab_names:
        st.error("沒有任何可用的分析功能")
        return
    
    # 建立分頁
    tabs = st.tabs(tab_names)
    
    # 索引追蹤
    tab_index = 0
    
    # Tab1: 個別分析
    if 'tab1_module' in locals():
        with tabs[tab_index]:
            try:
                st.subheader("🏠 個別房屋分析")
                tab1_module()
            except Exception as e:
                st.error(f"個別分析模組錯誤: {e}")
                import traceback
                with st.expander("錯誤詳情"):
                    st.code(traceback.format_exc())
        tab_index += 1
    
    # Tab2: 房屋比較
    if 'ComparisonAnalyzer' in locals():
        with tabs[tab_index]:
            try:
                analyzer = ComparisonAnalyzer()
                analyzer.render_comparison_tab()
            except Exception as e:
                st.error(f"房屋比較模組錯誤: {e}")
                import traceback
                with st.expander("錯誤詳情"):
                    st.code(traceback.format_exc())
        tab_index += 1
    
    # Tab3: 市場趨勢分析
    if HAS_MARKET_TREND:
        with tabs[tab_index]:
            try:
                analyzer = MarketTrendAnalyzer()
                analyzer.render_analysis_tab()
            except Exception as e:
                st.error(f"市場趨勢分析模組錯誤: {e}")
                import traceback
                with st.expander("錯誤詳情"):
                    st.code(traceback.format_exc())
    else:
        # 如果沒有市場趨勢分析模組，提供簡單的替代方案
        with tabs[tab_index] if tab_index < len(tabs) else st.container():
            st.subheader("📈 市場趨勢分析")
            st.info("市場趨勢分析模組尚未整合")
            
            # 提供簡單的 CSV 數據上傳和分析
            uploaded_file = st.file_uploader("上傳市場數據 CSV 檔案", type=['csv'])
            if uploaded_file is not None:
                try:
                    import pandas as pd
                    df = pd.read_csv(uploaded_file)
                    
                    st.subheader("📊 數據預覽")
                    st.dataframe(df.head(), use_container_width=True)
                    
                    st.subheader("📈 基本統計")
                    st.write(df.describe())
                    
                    # 簡單的圖表
                    if len(df) > 0:
                        col1, col2 = st.columns(2)
                        with col1:
                            if '價格' in df.columns:
                                st.line_chart(df[['價格']])
                        with col2:
                            if '交易量' in df.columns:
                                st.bar_chart(df[['交易量']])
                except Exception as e:
                    st.error(f"處理檔案時發生錯誤: {e}")

# 如果直接執行此檔案
if __name__ == "__main__":
    render_analysis_page()

# 確保函數可以被導入
__all__ = ['render_analysis_page']
