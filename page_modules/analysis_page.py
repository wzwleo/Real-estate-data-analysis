# page_modules/analysis_page.py
"""
分析頁面主模組 - 修正版本
直接導入，檢查實際類別名稱
"""

import os
import sys
import streamlit as st
import pandas as pd
import traceback
import importlib

# 設定導入路徑
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
components_dir = os.path.join(parent_dir, "components")

# 添加到 Python 路徑
sys.path.insert(0, parent_dir)
sys.path.insert(0, components_dir)

# 檢查目錄結構
st.sidebar.markdown("### 📁 目錄檢查")
st.sidebar.write(f"當前目錄: {current_dir}")
st.sidebar.write(f"組件目錄: {components_dir}")

# 檢查檔案是否存在
market_trend_path = os.path.join(components_dir, "market_trend.py")
market_trend_exists = os.path.exists(market_trend_path)
st.sidebar.write(f"market_trend.py 存在: {'✅' if market_trend_exists else '❌'}")

if market_trend_exists:
    st.sidebar.write(f"檔案路徑: {market_trend_path}")
    
    # 檢查檔案大小
    file_size = os.path.getsize(market_trend_path)
    st.sidebar.write(f"檔案大小: {file_size} 位元組")

# 動態導入模組
import_error = False
error_messages = []

# 1. 導入個別分析模組
try:
    # 先檢查檔案是否存在
    solo_analysis_path = os.path.join(components_dir, "solo_analysis.py")
    if not os.path.exists(solo_analysis_path):
        raise FileNotFoundError(f"找不到檔案: {solo_analysis_path}")
    
    # 動態導入
    spec = importlib.util.spec_from_file_location("solo_analysis", solo_analysis_path)
    solo_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(solo_module)
    
    # 檢查是否有 tab1_module
    if hasattr(solo_module, 'tab1_module'):
        tab1_module = solo_module.tab1_module
    else:
        # 檢查是否有其他可能的函數
        for attr_name in dir(solo_module):
            if 'module' in attr_name.lower() or 'tab' in attr_name.lower():
                tab1_module = getattr(solo_module, attr_name)
                st.success(f"使用替代函數: {attr_name}")
                break
        else:
            raise ImportError("solo_analysis.py 中找不到 tab1_module")
            
except Exception as e:
    import_error = True
    error_messages.append(f"個別分析模組導入失敗: {str(e)}")
    tab1_module = None

# 2. 導入比較分析模組
try:
    # 先檢查檔案是否存在
    comparison_path = os.path.join(components_dir, "comparison.py")
    if not os.path.exists(comparison_path):
        raise FileNotFoundError(f"找不到檔案: {comparison_path}")
    
    # 動態導入
    spec = importlib.util.spec_from_file_location("comparison", comparison_path)
    comparison_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(comparison_module)
    
    # 尋找可能的類別
    ComparisonAnalyzer = None
    get_comparison_analyzer = None
    
    # 首先查找類別
    for attr_name in dir(comparison_module):
        attr = getattr(comparison_module, attr_name)
        if isinstance(attr, type):  # 如果是類別
            if 'comparison' in attr_name.lower() or 'analyzer' in attr_name.lower():
                ComparisonAnalyzer = attr
                st.success(f"找到比較分析類別: {attr_name}")
                break
    
    # 如果沒找到類別，尋找函數
    if ComparisonAnalyzer is None:
        for attr_name in dir(comparison_module):
            attr = getattr(comparison_module, attr_name)
            if callable(attr) and not attr_name.startswith('_'):
                if 'comparison' in attr_name.lower() or 'get' in attr_name.lower():
                    get_comparison_analyzer = attr
                    st.success(f"找到比較分析函數: {attr_name}")
                    break
    
    if ComparisonAnalyzer is None and get_comparison_analyzer is None:
        raise ImportError("comparison.py 中找不到 ComparisonAnalyzer 或 get_comparison_analyzer")
        
except Exception as e:
    import_error = True
    error_messages.append(f"比較分析模組導入失敗: {str(e)}")
    ComparisonAnalyzer = None
    get_comparison_analyzer = None

# 3. 導入市場趨勢分析模組
try:
    if not os.path.exists(market_trend_path):
        raise FileNotFoundError(f"找不到檔案: {market_trend_path}")
    
    # 動態導入
    spec = importlib.util.spec_from_file_location("market_trend", market_trend_path)
    market_trend_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(market_trend_module)
    
    # 首先查看檔案中的內容
    with open(market_trend_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    st.sidebar.markdown("### 📝 market_trend.py 內容檢查")
    
    # 檢查是否有類別定義
    if 'class ' in content:
        # 找出所有類別名稱
        lines = content.split('\n')
        classes = []
        for line in lines:
            if line.strip().startswith('class '):
                class_name = line.strip()[6:].split('(')[0].strip()
                classes.append(class_name)
        
        st.sidebar.write(f"找到的類別: {', '.join(classes) if classes else '無'}")
        
        # 尋找合適的類別
        MarketTrendAnalyzer = None
        for class_name in classes:
            if hasattr(market_trend_module, class_name):
                MarketTrendAnalyzer = getattr(market_trend_module, class_name)
                st.sidebar.success(f"使用類別: {class_name}")
                MARKET_TREND_AVAILABLE = True
                break
        
        if MarketTrendAnalyzer is None:
            # 如果沒有找到 MarketTrendAnalyzer，使用第一個類別
            if classes and hasattr(market_trend_module, classes[0]):
                MarketTrendAnalyzer = getattr(market_trend_module, classes[0])
                st.sidebar.warning(f"使用替代類別: {classes[0]}")
                MARKET_TREND_AVAILABLE = True
            else:
                raise ImportError("market_trend.py 中找不到任何可用的類別")
    else:
        # 檢查是否有函數
        functions = [attr for attr in dir(market_trend_module) 
                    if callable(getattr(market_trend_module, attr)) and not attr.startswith('_')]
        st.sidebar.write(f"找到的函數: {', '.join(functions) if functions else '無'}")
        
        if functions:
            # 創建一個簡單的包裝類別
            class DynamicMarketTrendAnalyzer:
                def __init__(self):
                    self.module = market_trend_module
                
                def render_complete_dashboard(self):
                    # 嘗試調用主要函數
                    for func_name in ['main', 'render', 'show_dashboard', 'dashboard']:
                        if hasattr(self.module, func_name):
                            func = getattr(self.module, func_name)
                            if callable(func):
                                return func()
                    raise AttributeError("沒有找到可調用的函數")
            
            MarketTrendAnalyzer = DynamicMarketTrendAnalyzer
            MARKET_TREND_AVAILABLE = True
            st.sidebar.success("創建動態包裝類別")
        else:
            raise ImportError("market_trend.py 中沒有任何類別或函數")
            
except Exception as e:
    import_error = True
    error_messages.append(f"市場趨勢分析模組導入失敗: {str(e)}")
    MarketTrendAnalyzer = None
    MARKET_TREND_AVAILABLE = False

# 顯示導入結果
st.sidebar.markdown("### 📊 導入結果")
st.sidebar.metric("個別分析", "✅" if tab1_module else "❌")
st.sidebar.metric("房屋比較", "✅" if ComparisonAnalyzer or get_comparison_analyzer else "❌")
st.sidebar.metric("市場趨勢", "✅" if MARKET_TREND_AVAILABLE else "❌")


def render_analysis_page():
    """渲染分析頁面"""
    st.title("📊 不動產分析平台")
    
    # 如果導入失敗，顯示錯誤
    if import_error and not (tab1_module or ComparisonAnalyzer or get_comparison_analyzer or MARKET_TREND_AVAILABLE):
        st.error("❌ 模組導入失敗")
        with st.expander("📋 詳細錯誤資訊", expanded=True):
            for msg in error_messages:
                st.error(msg)
            
            # 顯示檔案內容
            if market_trend_exists:
                st.subheader("market_trend.py 檔案內容")
                try:
                    with open(market_trend_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    st.code(content[:2000] + ("..." if len(content) > 2000 else ""), language='python')
                except Exception as e:
                    st.error(f"無法讀取檔案: {e}")
        
        # 緊急模式
        render_emergency_mode()
        return
    
    # Tab 分頁
    tab_names = []
    if tab1_module:
        tab_names.append("🏠 個別分析")
    if ComparisonAnalyzer or get_comparison_analyzer:
        tab_names.append("🔄 房屋比較")
    if MARKET_TREND_AVAILABLE:
        tab_names.append("📈 市場趨勢分析")
    
    if not tab_names:
        render_emergency_mode()
        return
    
    tabs = st.tabs(tab_names)
    tab_index = 0
    
    # 個別分析
    if tab1_module and tab_names[0] == "🏠 個別分析":
        with tabs[tab_index]:
            try:
                tab1_module()
            except Exception as e:
                st.error(f"個別分析執行錯誤: {str(e)}")
                with st.expander("錯誤詳情"):
                    st.code(traceback.format_exc())
        tab_index += 1
    
    # 房屋比較
    if (ComparisonAnalyzer or get_comparison_analyzer) and "🔄 房屋比較" in tab_names:
        with tabs[tab_index]:
            try:
                # 使用 get_comparison_analyzer() 或直接實例化
                if get_comparison_analyzer:
                    analyzer = get_comparison_analyzer()
                elif ComparisonAnalyzer:
                    analyzer = ComparisonAnalyzer()
                else:
                    st.error("無法創建比較分析器")
                    return
                
                if hasattr(analyzer, 'render_comparison_tab'):
                    analyzer.render_comparison_tab()
                elif hasattr(analyzer, 'main'):
                    analyzer.main()
                elif hasattr(analyzer, 'render'):
                    analyzer.render()
                else:
                    st.error("比較分析器缺少標準方法")
                    
            except Exception as e:
                st.error(f"房屋比較執行錯誤: {str(e)}")
                with st.expander("錯誤詳情"):
                    st.code(traceback.format_exc())
        tab_index += 1
    
    # 市場趨勢分析
    if MARKET_TREND_AVAILABLE and MarketTrendAnalyzer and "📈 市場趨勢分析" in tab_names:
        with tabs[tab_index]:
            try:
                analyzer = MarketTrendAnalyzer()
                
                # 嘗試調用不同方法
                if hasattr(analyzer, 'render_complete_dashboard'):
                    analyzer.render_complete_dashboard()
                elif hasattr(analyzer, 'render_analysis_tab'):
                    analyzer.render_analysis_tab()
                elif hasattr(analyzer, 'main'):
                    analyzer.main()
                elif hasattr(analyzer, 'render'):
                    analyzer.render()
                elif hasattr(analyzer, 'show'):
                    analyzer.show()
                else:
                    # 嘗試找到任何可調用的方法
                    methods = [m for m in dir(analyzer) 
                              if callable(getattr(analyzer, m)) and not m.startswith('_')]
                    st.warning(f"分析器方法: {methods}")
                    if methods:
                        getattr(analyzer, methods[0])()
                    else:
                        st.error("市場趨勢分析器缺少標準方法")
                        
            except Exception as e:
                st.error(f"市場趨勢分析執行錯誤: {str(e)}")
                with st.expander("錯誤詳情"):
                    st.code(traceback.format_exc())


def render_emergency_mode():
    """緊急模式 - 當所有模組都無法導入時顯示"""
    st.header("🚨 緊急模式")
    st.warning("完整功能暫時不可用，正在使用緊急模式")
    
    # 簡化資料分析功能
    st.subheader("📊 簡化資料分析")
    
    # 手動檔案上傳
    uploaded_file = st.file_uploader(
        "選擇資料檔案 (CSV/Excel)",
        type=['csv', 'xlsx', 'xls'],
        help="上傳 CSV 或 Excel 檔案進行分析"
    )
    
    if uploaded_file is not None:
        try:
            # 根據檔案類型載入
            if uploaded_file.name.endswith('.csv'):
                # 嘗試不同編碼
                for encoding in ['utf-8', 'big5', 'cp950', 'latin1']:
                    try:
                        uploaded_file.seek(0)
                        df = pd.read_csv(uploaded_file, encoding=encoding, low_memory=False)
                        st.success(f"✅ 使用 {encoding} 編碼成功載入")
                        break
                    except:
                        continue
                else:
                    st.error("無法讀取 CSV 檔案，請嘗試另存為 Excel 格式")
                    return
            elif uploaded_file.name.endswith(('.xlsx', '.xls')):
                df = pd.read_excel(uploaded_file)
                st.success("✅ 成功載入 Excel 檔案")
            else:
                st.error("不支援的檔案格式")
                return
            
            # 顯示資料分析
            display_simple_analysis(df)
            
        except Exception as e:
            st.error(f"載入資料時發生錯誤: {str(e)}")
            st.code(traceback.format_exc())
    else:
        st.info("請上傳 CSV 或 Excel 檔案進行分析")


def display_simple_analysis(df):
    """顯示簡化資料分析"""
    import plotly.express as px
    
    st.subheader("📋 資料概覽")
    
    # 基本統計
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("總筆數", f"{len(df):,}")
    with col2:
        st.metric("欄位數", len(df.columns))
    with col3:
        st.metric("資料大小", f"{df.memory_usage(deep=True).sum() / 1024 / 1024:.1f} MB")
    
    # 資料預覽
    with st.expander("👀 資料預覽", expanded=True):
        preview_rows = st.slider("顯示行數", 5, 100, 10)
        st.dataframe(df.head(preview_rows), use_container_width=True)
    
    # 欄位資訊
    with st.expander("📊 欄位資訊"):
        col_info = pd.DataFrame({
            '欄位名稱': df.columns,
            '資料類型': df.dtypes.astype(str),
            '非空值數': df.notnull().sum(),
            '空值率%': (df.isnull().sum() / len(df) * 100).round(2)
        })
        st.dataframe(col_info, use_container_width=True)
    
    # 數值分析
    st.subheader("📈 數值分析")
    
    numeric_cols = df.select_dtypes(include=['int64', 'float64']).columns.tolist()
    
    if numeric_cols:
        selected_col = st.selectbox("選擇分析欄位", numeric_cols)
        
        if pd.api.types.is_numeric_dtype(df[selected_col]):
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("平均值", f"{df[selected_col].mean():.2f}")
            with col2:
                st.metric("中位數", f"{df[selected_col].median():.2f}")
            with col3:
                st.metric("標準差", f"{df[selected_col].std():.2f}")
            with col4:
                st.metric("範圍", f"{df[selected_col].min():.2f} - {df[selected_col].max():.2f}")
            
            # 分布圖
            fig = px.histogram(df, x=selected_col, title=f"{selected_col} 分布", nbins=30)
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("沒有找到數值型欄位進行統計分析")


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
