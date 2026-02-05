# page_modules/analysis_page.py
"""
分析頁面主模組 - 修正版本
修復了 ComparisonAnalyzer 導入錯誤
"""

import os
import sys
import streamlit as st
import pandas as pd
import time
import traceback
import plotly.express as px
import numpy as np

# 修正導入路徑
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
components_dir = os.path.join(parent_dir, "components")

# 將必要的路徑添加到 Python 路徑
for path in [parent_dir, components_dir]:
    if path not in sys.path and os.path.exists(path):
        sys.path.insert(0, path)

st.sidebar.markdown("### 🔍 系統狀態")

# 初始化全局變量
import_success = False
MARKET_TREND_AVAILABLE = False
MarketTrendClass = None
ComparisonAnalyzerClass = None
tab1_module = None
get_comparison_analyzer_func = None

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
    
    # 2. 導入比較模組 - 使用兩種方式
    try:
        # 嘗試導入整個模組
        from components import comparison as comparison_module
        st.sidebar.success("✅ 比較分析模組導入成功")
        
        # 嘗試獲取 ComparisonAnalyzer 類別
        if hasattr(comparison_module, 'ComparisonAnalyzer'):
            ComparisonAnalyzerClass = comparison_module.ComparisonAnalyzer
            st.sidebar.info("✅ 找到 ComparisonAnalyzer 類別")
        
        # 嘗試獲取 get_comparison_analyzer 函數
        if hasattr(comparison_module, 'get_comparison_analyzer'):
            get_comparison_analyzer_func = comparison_module.get_comparison_analyzer
            st.sidebar.info("✅ 找到 get_comparison_analyzer 函數")
        
        # 如果都沒有找到，嘗試直接導入
        if not ComparisonAnalyzerClass and not get_comparison_analyzer_func:
            try:
                from components.comparison import ComparisonAnalyzer
                ComparisonAnalyzerClass = ComparisonAnalyzer
                st.sidebar.info("✅ 直接導入 ComparisonAnalyzer 成功")
            except ImportError:
                try:
                    from components.comparison import get_comparison_analyzer
                    get_comparison_analyzer_func = get_comparison_analyzer
                    st.sidebar.info("✅ 直接導入 get_comparison_analyzer 成功")
                except ImportError:
                    raise ImportError("無法導入比較分析模組的類別或函數")
        
    except Exception as e:
        st.sidebar.warning(f"⚠️ 比較分析模組導入失敗: {e}")
        
        # 創建一個臨時的替代函數
        def get_temp_comparison_analyzer():
            class TempComparisonAnalyzer:
                def render_comparison_tab(self):
                    st.header("房屋比較")
                    st.warning("比較分析模組暫時不可用")
                    st.info("這是臨時替代功能")
            return TempComparisonAnalyzer()
        
        get_comparison_analyzer_func = get_temp_comparison_analyzer
    
    # 3. 導入市場趨勢分析模組
    try:
        # 嘗試導入 market_trend
        from components.market_trend import MarketTrendAnalyzer
        MarketTrendClass = MarketTrendAnalyzer
        MARKET_TREND_AVAILABLE = True
        st.sidebar.success("✅ 市場趨勢分析模組導入成功")
    except ImportError as e:
        st.sidebar.warning(f"⚠️ 市場趨勢分析模組導入失敗: {e}")
        MARKET_TREND_AVAILABLE = False
    
    import_success = True
    st.sidebar.success("🎉 所有模組初始化完成")
    
except Exception as e:
    st.sidebar.error(f"❌ 初始化失敗: {str(e)}")
    import_success = False


def get_comparison_instance():
    """獲取比較分析器實例的統一函數"""
    if get_comparison_analyzer_func:
        # 使用 get_comparison_analyzer() 函數
        return get_comparison_analyzer_func()
    elif ComparisonAnalyzerClass:
        # 直接實例化 ComparisonAnalyzer 類別
        return ComparisonAnalyzerClass()
    else:
        # 創建臨時替代
        class TempComparisonAnalyzer:
            def render_comparison_tab(self):
                st.header("房屋比較")
                st.warning("比較分析模組暫時不可用")
                st.info("這是臨時替代功能")
        return TempComparisonAnalyzer()


def render_analysis_page():
    """渲染分析頁面"""
    st.title("📊 不動產分析平台")
    
    # 顯示系統狀態
    with st.expander("🔧 系統狀態資訊", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            st.metric("個別分析", "✅ 可用" if tab1_module else "⚠️ 受限")
        with col2:
            comparison_available = ComparisonAnalyzerClass is not None or get_comparison_analyzer_func is not None
            st.metric("房屋比較", "✅ 可用" if comparison_available else "⚠️ 受限")
        
        col3, col4 = st.columns(2)
        with col3:
            st.metric("市場趨勢", "✅ 可用" if MARKET_TREND_AVAILABLE else "❌ 不可用")
        with col4:
            st.metric("整體狀態", "✅ 正常" if import_success else "⚠️ 異常")
    
    # 如果導入失敗，顯示錯誤訊息
    if not import_success:
        st.error("⚠️ 模組導入失敗，部分功能可能受限")
        st.info("""
        請檢查：
        1. 確保 `components/` 目錄存在且包含必要檔案
        2. 檢查 Python 路徑設定
        3. 重新啟動應用程式
        """)
    
    # Tab 分頁
    tab1, tab2, tab3 = st.tabs([
        "🏠 個別分析", 
        "🔄 房屋比較", 
        "📈 市場趨勢分析"
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
    
    # Tab2: 房屋比較 - 這是修正的核心
    with tab2:
        st.header("🔄 房屋比較分析")
        
        try:
            with st.spinner("初始化比較分析器..."):
                # 獲取分析器實例
                analyzer_instance = get_comparison_instance()
                
                # 檢查是否有正確的方法
                if hasattr(analyzer_instance, 'render_comparison_tab'):
                    analyzer_instance.render_comparison_tab()
                else:
                    st.error("比較分析器缺少 render_comparison_tab 方法")
                    st.info(f"分析器可用方法: {[m for m in dir(analyzer_instance) if not m.startswith('_')]}")
                    
        except Exception as e:
            st.error(f"房屋比較模組執行錯誤: {e}")
            st.code(traceback.format_exc())
            st.warning("房屋比較模組暫時不可用")
    
    # Tab3: 市場趨勢分析
    with tab3:
        st.header("📈 市場趨勢分析")
        
        if MARKET_TREND_AVAILABLE and MarketTrendClass:
            try:
                with st.spinner("初始化市場趨勢分析..."):
                    # 創建分析器實例
                    analyzer_instance = MarketTrendClass()
                    
                    # 根據類別類型執行不同方法
                    if hasattr(analyzer_instance, 'render_complete_dashboard'):
                        analyzer_instance.render_complete_dashboard()
                    elif hasattr(analyzer_instance, 'render_analysis_tab'):
                        analyzer_instance.render_analysis_tab()
                    elif hasattr(analyzer_instance, 'main'):
                        analyzer_instance.main()
                    elif hasattr(analyzer_instance, 'render'):
                        analyzer_instance.render()
                    else:
                        st.error("⚠️ 市場趨勢分析器缺少標準方法")
                        
            except Exception as e:
                st.error(f"市場趨勢分析執行錯誤: {str(e)}")
                st.code(traceback.format_exc())
                
                # 顯示緊急修復功能
                st.warning("正在啟動緊急修復功能...")
                render_emergency_market_trend()
        else:
            st.error("❌ 市場趨勢分析功能不可用")
            render_emergency_market_trend()


def render_emergency_market_trend():
    """緊急修復的市場趨勢分析功能"""
    st.header("📈 市場趨勢分析（緊急模式）")
    
    st.warning("完整功能暫時不可用，正在使用緊急模式")
    
    # 簡化資料分析功能
    st.subheader("📊 簡化資料分析")
    
    # 檔案選擇
    try:
        # 尋找資料檔案
        data_files = []
        for root, dirs, files in os.walk(parent_dir):
            for file in files:
                if file.endswith(('.csv', '.xlsx', '.xls')):
                    full_path = os.path.join(root, file)
                    data_files.append((file, full_path))
        
        if data_files:
            file_names = [f[0] for f in data_files]
            selected_file_name = st.selectbox(
                "選擇資料檔案",
                file_names,
                help="選擇要分析的資料檔案"
            )
            
            # 找到對應的完整路徑
            selected_path = None
            for name, path in data_files:
                if name == selected_file_name:
                    selected_path = path
                    break
            
            if selected_path and st.button("📥 載入資料", type="primary"):
                try:
                    # 根據檔案類型載入
                    if selected_path.endswith('.csv'):
                        # 嘗試不同編碼
                        for encoding in ['utf-8', 'big5', 'cp950', 'latin1']:
                            try:
                                df = pd.read_csv(selected_path, encoding=encoding, low_memory=False)
                                st.success(f"✅ 使用 {encoding} 編碼成功載入")
                                break
                            except:
                                continue
                        else:
                            st.error("無法讀取 CSV 檔案")
                            return
                    elif selected_path.endswith(('.xlsx', '.xls')):
                        df = pd.read_excel(selected_path)
                        st.success("✅ 成功載入 Excel 檔案")
                    else:
                        st.error("不支援的檔案格式")
                        return
                    
                    # 顯示資料資訊
                    display_data_analysis(df)
                
                except Exception as e:
                    st.error(f"載入資料時發生錯誤: {str(e)}")
                    st.code(traceback.format_exc())
        else:
            st.warning("未找到任何資料檔案")
    
    except Exception as e:
        st.error(f"尋找檔案時發生錯誤: {str(e)}")


def display_data_analysis(df):
    """顯示資料分析結果"""
    st.subheader("📋 資料概覽")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("總筆數", len(df))
    
    with col2:
        st.metric("欄位數", len(df.columns))
    
    with col3:
        st.metric("記憶體使用", f"{df.memory_usage(deep=True).sum() / 1024 / 1024:.1f} MB")
    
    # 顯示欄位資訊
    with st.expander("📊 欄位資訊", expanded=True):
        col_info = pd.DataFrame({
            '欄位名稱': df.columns,
            '資料類型': df.dtypes,
            '非空值數': df.notnull().sum(),
            '空值數': df.isnull().sum(),
            '唯一值數': [df[col].nunique() for col in df.columns]
        })
        st.dataframe(col_info, use_container_width=True)
    
    # 資料預覽
    with st.expander("👀 資料預覽", expanded=False):
        preview_rows = st.slider("預覽行數", 5, 50, 10)
        st.dataframe(df.head(preview_rows), use_container_width=True)
    
    # 基本分析選項
    st.subheader("🔍 快速分析")
    
    analysis_type = st.selectbox(
        "選擇分析類型",
        ["基本統計", "價格分析", "地區分析", "時間趨勢"]
    )
    
    if analysis_type == "基本統計":
        st.write("數值欄位統計:")
        st.dataframe(df.describe(), use_container_width=True)
    
    elif analysis_type == "價格分析":
        # 尋找價格相關欄位
        price_columns = [col for col in df.columns 
                       if any(word in col.lower() for word in ['價格', '價', 'price', 'cost'])]
        
        if price_columns:
            selected_price_col = st.selectbox("選擇價格欄位", price_columns)
            
            if pd.api.types.is_numeric_dtype(df[selected_price_col]):
                col1, col2 = st.columns(2)
                with col1:
                    avg_price = df[selected_price_col].mean()
                    st.metric("平均價格", f"{avg_price:,.0f}")
                
                with col2:
                    median_price = df[selected_price_col].median()
                    st.metric("中位數價格", f"{median_price:,.0f}")
                
                # 價格分布圖
                fig = px.histogram(
                    df, 
                    x=selected_price_col,
                    title=f"{selected_price_col} 分布",
                    nbins=50
                )
                st.plotly_chart(fig, use_container_width=True)
    
    elif analysis_type == "地區分析":
        # 尋找地區相關欄位
        area_columns = [col for col in df.columns 
                      if any(word in col for word in ['縣市', '行政區', '地區', '區', 'city', 'district'])]
        
        if area_columns:
            selected_area_col = st.selectbox("選擇地區欄位", area_columns)
            
            # 地區統計
            area_stats = df[selected_area_col].value_counts().reset_index()
            area_stats.columns = ['地區', '數量']
            
            fig = px.bar(
                area_stats.head(20),
                x='地區',
                y='數量',
                title="地區分布（前20名）",
                color='數量'
            )
            fig.update_layout(xaxis_tickangle=45)
            st.plotly_chart(fig, use_container_width=True)
    
    elif analysis_type == "時間趨勢":
        # 尋找時間相關欄位
        time_columns = [col for col in df.columns 
                      if any(word in col for word in ['年', '月', '日', '日期', 'time', 'date', 'year'])]
        
        if time_columns:
            selected_time_col = st.selectbox("選擇時間欄位", time_columns)
            
            # 嘗試找出數值欄位來分析趨勢
            numeric_cols = df.select_dtypes(include=[np.number]).columns
            if len(numeric_cols) > 0:
                selected_numeric_col = st.selectbox("選擇分析數值", numeric_cols)
                
                # 簡單的時間趨勢
                time_trend = df.groupby(selected_time_col)[selected_numeric_col].mean().reset_index()
                
                fig = px.line(
                    time_trend,
                    x=selected_time_col,
                    y=selected_numeric_col,
                    title=f"{selected_numeric_col} 時間趨勢",
                    markers=True
                )
                st.plotly_chart(fig, use_container_width=True)


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
