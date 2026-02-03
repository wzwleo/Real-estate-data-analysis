# page_modules/analysis_page.py
"""
分析頁面主模組
整合了三個主要功能：
1. 個別分析 (Tab1)
2. 房屋比較 (Tab2) - 使用 ComparisonAnalyzer
3. 市場趨勢分析 (Tab3)
"""

import os
import sys
import streamlit as st
import pandas as pd
import time

# 修正導入路徑
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# 嘗試導入模組
import_success = False
try:
    # 嘗試導入個別分析模組
    from components.solo_analysis import tab1_module
    
    # 嘗試導入比較模組
    from components.comparison import ComparisonAnalyzer
    
    # 嘗試導入市場趨勢分析（改為嘗試不同名稱）
    MARKET_TREND_AVAILABLE = False
    MarketTrendAnalyzer = None
    
    # 嘗試不同可能的模組名稱
    try:
        from components.market_trend import CompleteMarketTrendAnalyzer
        MarketTrendAnalyzer = CompleteMarketTrendAnalyzer
        MARKET_TREND_AVAILABLE = True
        st.sidebar.success("✅ 市場趨勢模組載入成功")
    except ImportError as e1:
        try:
            # 嘗試另一個可能的類別名稱
            from components.market_trend import MarketTrendAnalyzer
            MARKET_TREND_AVAILABLE = True
            st.sidebar.success("✅ 市場趨勢模組載入成功")
        except ImportError as e2:
            try:
                # 嘗試直接導入
                import components.market_trend as market_trend_module
                # 檢查模組中是否有可用的類別
                if hasattr(market_trend_module, 'CompleteMarketTrendAnalyzer'):
                    MarketTrendAnalyzer = market_trend_module.CompleteMarketTrendAnalyzer
                    MARKET_TREND_AVAILABLE = True
                elif hasattr(market_trend_module, 'MarketTrendAnalyzer'):
                    MarketTrendAnalyzer = market_trend_module.MarketTrendAnalyzer
                    MARKET_TREND_AVAILABLE = True
                elif hasattr(market_trend_module, 'main'):
                    # 如果是函數式模組
                    MarketTrendAnalyzer = market_trend_module
                    MARKET_TREND_AVAILABLE = True
                st.sidebar.success("✅ 市場趨勢模組載入成功")
            except ImportError as e3:
                MARKET_TREND_AVAILABLE = False
                st.sidebar.warning(f"市場趨勢分析模組導入嘗試失敗：{e1} | {e2} | {e3}")
    
    import_success = True
    
except ImportError as e:
    st.error(f"導入模組失敗: {e}")
    import traceback
    st.code(traceback.format_exc())
    import_success = False


def render_analysis_page():
    """渲染分析頁面"""
    st.title("📊 分析頁面")
    
    # 檢查是否成功匯入
    if not import_success:
        st.error("無法載入分析模組，請檢查檔案結構")
        st.info("請確保以下模組存在：")
        st.info("1. components/solo_analysis.py")
        st.info("2. components/comparison.py")
        st.info("3. components/market_trend.py")
        return
    
    # 初始化 session state
    if 'favorites' not in st.session_state:
        st.session_state.favorites = set()
    
    # Tab 分頁
    tab1, tab2, tab3 = st.tabs(["個別分析", "房屋比較", "市場趨勢分析"])
    
    # Tab1: 個別分析
    with tab1:
        try:
            tab1_module()
        except Exception as e:
            st.error(f"個別分析模組錯誤: {e}")
            import traceback
            st.code(traceback.format_exc())
    
    # Tab2: 房屋比較
    with tab2:
        try:
            analyzer = ComparisonAnalyzer()
            analyzer.render_comparison_tab()
        except Exception as e:
            st.error(f"房屋比較模組錯誤: {e}")
            import traceback
            st.code(traceback.format_exc())
    
    # Tab3: 市場趨勢分析
    with tab3:
        if MARKET_TREND_AVAILABLE and MarketTrendAnalyzer:
            try:
                # 根據類別類型執行
                if callable(MarketTrendAnalyzer):
                    # 如果是類別
                    analyzer_instance = MarketTrendAnalyzer()
                    
                    # 檢查是否有 render_complete_dashboard 方法
                    if hasattr(analyzer_instance, 'render_complete_dashboard'):
                        analyzer_instance.render_complete_dashboard()
                    elif hasattr(analyzer_instance, 'render_analysis_tab'):
                        analyzer_instance.render_analysis_tab()
                    elif hasattr(analyzer_instance, 'main'):
                        analyzer_instance.main()
                    else:
                        st.error("市場趨勢分析模組沒有可用的渲染方法")
                else:
                    # 如果是函數式模組
                    MarketTrendAnalyzer.main()
                    
            except Exception as e:
                st.error(f"市場趨勢分析模組錯誤: {e}")
                import traceback
                st.code(traceback.format_exc())
        else:
            # 簡化的市場趨勢分析（替代方案）
            st.subheader("📈 市場趨勢分析")
            st.info("完整市場趨勢分析功能正在開發中")
            
            # 顯示如何解決問題
            with st.expander("🔧 如何啟用完整功能？", expanded=True):
                st.markdown("""
                ### 請確保以下設定：
                1. **檔案位置**：`components/market_trend.py` 檔案存在
                2. **檔案內容**：包含 `CompleteMarketTrendAnalyzer` 或 `MarketTrendAnalyzer` 類別
                3. **必要套件**：已安裝以下套件：
                   ```bash
                   pip install plotly streamlit-echarts google-generativeai
                   ```
                4. **類別名稱**：檢查檔案中的類別名稱
                """)
                
                # 提供快速修復選項
                if st.button("🔄 重新嘗試載入模組"):
                    st.rerun()


# 如果直接執行此檔案
if __name__ == "__main__":
    render_analysis_page()
