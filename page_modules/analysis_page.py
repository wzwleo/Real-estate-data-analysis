"""
分析頁面主模組
整合了三個主要功能：
1. 個別分析 (Tab1)
2. 房屋比較 (Tab2) - 使用 ComparisonAnalyzer
3. 市場趨勢分析 (Tab3)
"""

# 確保必要的導入
import os
import sys

# 修正導入路徑
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# 其他導入...

# 在文件末尾確保函數可以被導入
__all__ = ['render_analysis_page']

# 主函數
def render_analysis_page():
    """渲染分析頁面"""
    # ... 你的程式碼 ...


def render_analysis_page():
    """渲染分析頁面"""
    st.title("📊 分析頁面")
    
    # 檢查是否成功匯入
    if not import_success:
        st.error("無法載入分析模組，請檢查檔案結構")
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
        try:
            analyzer = MarketTrendAnalyzer()
            analyzer.render_analysis_tab()
        except Exception as e:
            st.error(f"市場趨勢分析模組錯誤: {e}")
            import traceback
            st.code(traceback.format_exc())


# 如果直接執行此檔案
if __name__ == "__main__":
    render_analysis_page()
