"""
分析頁面主模組
整合了三個主要功能：
1. 個別分析 (Tab1)
2. 房屋比較 (Tab2) - 使用 ComparisonAnalyzer
3. 市場趨勢分析 (Tab3) - 修復版本
"""

import os
import sys
import streamlit as st
import pandas as pd
import time
import traceback

# 修正導入路徑
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
components_dir = os.path.join(parent_dir, "components")

# 將必要的路徑添加到 Python 路徑
for path in [parent_dir, components_dir]:
    if path not in sys.path and os.path.exists(path):
        sys.path.insert(0, path)

st.sidebar.markdown("### 🔍 系統狀態")

# 診斷資訊
st.sidebar.write("**檔案結構檢查:**")
paths_to_check = [
    ("專案根目錄", parent_dir),
    ("components 目錄", components_dir),
]

for name, path in paths_to_check:
    if os.path.exists(path):
        st.sidebar.success(f"✅ {name} 存在")
    else:
        st.sidebar.error(f"❌ {name} 不存在")

# 檢查 components 目錄內容
if os.path.exists(components_dir):
    py_files = [f for f in os.listdir(components_dir) if f.endswith('.py')]
    st.sidebar.write(f"**找到 {len(py_files)} 個 Python 模組:**")
    for file in sorted(py_files):
        st.sidebar.info(f"📄 {file}")
else:
    st.sidebar.error("❌ components 目錄不存在")

# 導入模組 - 使用安全的方式
import_success = False
ComparisonAnalyzer = None
tab1_module = None

try:
    # 1. 導入個別分析模組
    try:
        from components.solo_analysis import tab1_module as solo_module
        tab1_module = solo_module
        st.sidebar.success("✅ 個別分析模組導入成功")
    except ImportError as e:
        st.sidebar.warning(f"⚠️ 個別分析模組導入失敗: {e}")
        # 創建一個臨時的替代函數
        def temp_tab1_module():
            st.header("個別分析")
            st.warning("個別分析模組暫時不可用")
            st.info("這是臨時替代功能")
        tab1_module = temp_tab1_module
    
    # 2. 導入比較模組
    try:
        from components.comparison import ComparisonAnalyzer as CA
        ComparisonAnalyzer = CA
        st.sidebar.success("✅ 比較分析模組導入成功")
    except ImportError as e:
        st.sidebar.warning(f"⚠️ 比較分析模組導入失敗: {e}")
        # 創建一個臨時的替代類別
        class TempComparisonAnalyzer:
            def render_comparison_tab(self):
                st.header("房屋比較")
                st.warning("比較分析模組暫時不可用")
                st.info("這是臨時替代功能")
        ComparisonAnalyzer = TempComparisonAnalyzer
    
    import_success = True
    st.sidebar.success("🎉 所有模組初始化完成")
    
except Exception as e:
    st.sidebar.error(f"❌ 初始化失敗: {str(e)}")
    import_success = False


def render_analysis_page():
    """渲染分析頁面"""
    st.title("📊 不動產分析平台")
    
    # 顯示系統狀態
    with st.expander("🔧 系統狀態資訊", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            st.metric("個別分析", "✅ 可用" if tab1_module else "⚠️ 受限")
        with col2:
            st.metric("房屋比較", "✅ 可用" if ComparisonAnalyzer else "⚠️ 受限")
        
        col3, col4 = st.columns(2)
        with col3:
            st.metric("整體狀態", "✅ 正常" if import_success else "⚠️ 異常")
        with col4:
            st.metric("市場趨勢", "❌ 已移除")
    
    # 如果導入失敗，顯示錯誤訊息
    if not import_success:
        st.error("⚠️ 模組導入失敗，部分功能可能受限")
        st.info("""
        請檢查：
        1. 確保 `components/` 目錄存在且包含必要檔案
        2. 檢查 Python 路徑設定
        3. 重新啟動應用程式
        """)
    
    # Tab 分頁 - 現在只有兩個分頁
    tab1, tab2 = st.tabs([
        "🏠 個別分析", 
        "🔄 房屋比較"
    ])
    
    # Tab1: 個別分析
    with tab1:
        st.header("🏠 個別房屋分析")
        
        if tab1_module:
            try:
                with st.spinner("載入個別分析模組..."):
                    tab1_module()
            except Exception as e:
                st.error(f"個別分析模組執行錯誤: {e}")
                st.code(traceback.format_exc())
        else:
            st.warning("個別分析模組暫時不可用")
            # 提供基本功能
            st.subheader("基本功能")
            st.info("請檢查 components/solo_analysis.py 檔案是否存在")
    
    # Tab2: 房屋比較
    with tab2:
        st.header("🔄 房屋比較分析")
        
        if ComparisonAnalyzer:
            try:
                with st.spinner("初始化比較分析器..."):
                    analyzer = ComparisonAnalyzer()
                    analyzer.render_comparison_tab()
            except Exception as e:
                st.error(f"房屋比較模組執行錯誤: {e}")
                st.code(traceback.format_exc())
        else:
            st.warning("房屋比較模組暫時不可用")
            # 提供基本比較功能
            st.subheader("簡化比較功能")
            st.info("請檢查 components/comparison.py 檔案是否存在")


# 如果直接執行此檔案
if __name__ == "__main__":
    st.set_page_config(
        page_title="不動產分析平台",
        page_icon="🏠",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    render_analysis_page()
    
    # 顯示系統資訊
    st.sidebar.markdown("---")
    st.sidebar.markdown("### ℹ️ 系統資訊")
    st.sidebar.info(f"Python 版本: {sys.version.split()[0]}")
    st.sidebar.info(f"Streamlit 版本: {st.__version__}")
    st.sidebar.info(f"Pandas 版本: {pd.__version__}")
    
    # 提供重新載入按鈕
    if st.sidebar.button("🔄 重新整理頁面", use_container_width=True):
        st.rerun()
