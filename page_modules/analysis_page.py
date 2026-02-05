# page_modules/analysis_page.py
"""
分析頁面主模組 - 修正版本
直接導入，失敗則報錯
"""

import os
import sys
import streamlit as st
import pandas as pd
import traceback

# 設定導入路徑
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
components_dir = os.path.join(parent_dir, "components")

# 添加到 Python 路徑
sys.path.insert(0, parent_dir)
sys.path.insert(0, components_dir)

# 嘗試導入所有必要模組
import_error = False
error_messages = []

try:
    # 導入個別分析模組
    from components.solo_analysis import tab1_module
except ImportError as e:
    import_error = True
    error_messages.append(f"個別分析模組導入失敗: {str(e)}")
    tab1_module = None

try:
    # 導入比較分析模組
    from components.comparison import ComparisonAnalyzer, get_comparison_analyzer
except ImportError as e:
    import_error = True
    error_messages.append(f"比較分析模組導入失敗: {str(e)}")
    ComparisonAnalyzer = None
    get_comparison_analyzer = None

try:
    # 導入市場趨勢分析模組
    from components.market_trend import MarketTrendAnalyzer
    MARKET_TREND_AVAILABLE = True
except ImportError as e:
    import_error = True
    error_messages.append(f"市場趨勢分析模組導入失敗: {str(e)}")
    MarketTrendAnalyzer = None
    MARKET_TREND_AVAILABLE = False


def render_analysis_page():
    """渲染分析頁面"""
    st.title("📊 不動產分析平台")
    
    # 顯示系統狀態
    st.sidebar.markdown("### 🔧 系統狀態")
    
    status_col1, status_col2, status_col3 = st.sidebar.columns(3)
    
    with status_col1:
        st.metric("個別分析", "✅" if tab1_module else "❌")
    with status_col2:
        st.metric("房屋比較", "✅" if ComparisonAnalyzer else "❌")
    with status_col3:
        st.metric("市場趨勢", "✅" if MARKET_TREND_AVAILABLE else "❌")
    
    # 如果導入失敗，顯示詳細錯誤
    if import_error:
        st.error("❌ 模組導入失敗")
        with st.expander("📋 錯誤詳情", expanded=True):
            for msg in error_messages:
                st.error(msg)
            
            st.markdown("### 🔧 修復建議")
            st.markdown("""
            1. **檢查檔案結構**
               ```
               project/
               ├── components/
               │   ├── comparison.py
               │   ├── solo_analysis.py
               │   └── market_trend.py
               ├── page_modules/
               │   └── analysis_page.py
               └── main.py
               ```
            
            2. **檢查 Python 路徑**
               - 確保 `components/` 目錄存在
               - 確保 `__init__.py` 檔案存在
            
            3. **檢查檔案內容**
               - 確認每個模組檔案都存在
               - 確認沒有語法錯誤
            
            4. **重新啟動 Streamlit**
               ```bash
               # 停止並重新啟動
               Ctrl+C
               streamlit run main.py
               ```
            """)
        
        st.stop()  # 停止執行，不顯示後續內容
    
    # Tab 分頁
    tab1, tab2, tab3 = st.tabs([
        "🏠 個別分析", 
        "🔄 房屋比較", 
        "📈 市場趨勢分析"
    ])
    
    # Tab1: 個別分析
    with tab1:
        if tab1_module:
            tab1_module()
        else:
            st.error("個別分析功能不可用")
    
    # Tab2: 房屋比較
    with tab2:
        if ComparisonAnalyzer:
            try:
                # 使用 get_comparison_analyzer() 或直接實例化
                if get_comparison_analyzer:
                    analyzer = get_comparison_analyzer()
                else:
                    analyzer = ComparisonAnalyzer()
                
                if hasattr(analyzer, 'render_comparison_tab'):
                    analyzer.render_comparison_tab()
                else:
                    st.error("比較分析器缺少 render_comparison_tab 方法")
                    
            except Exception as e:
                st.error(f"房屋比較執行錯誤: {str(e)}")
                with st.expander("錯誤詳情"):
                    st.code(traceback.format_exc())
        else:
            st.error("房屋比較功能不可用")
    
    # Tab3: 市場趨勢分析
    with tab3:
        if MARKET_TREND_AVAILABLE and MarketTrendAnalyzer:
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
                else:
                    st.error("市場趨勢分析器缺少標準方法")
                    
            except Exception as e:
                st.error(f"市場趨勢分析執行錯誤: {str(e)}")
                with st.expander("錯誤詳情"):
                    st.code(traceback.format_exc())
        else:
            st.error("市場趨勢分析功能不可用")
            render_emergency_market_trend()


def render_emergency_market_trend():
    """緊急修復的市場趨勢分析功能"""
    st.header("📈 市場趨勢分析（緊急模式）")
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
        
        # 顯示可能的檔案範例
        with st.expander("📋 檔案格式說明"):
            st.markdown("""
            **支援的檔案格式:**
            - CSV (.csv)
            - Excel (.xlsx, .xls)
            
            **建議的資料欄位:**
            - 價格相關: `總價`, `單價`, `價格`
            - 區域相關: `縣市`, `行政區`, `地址`
            - 時間相關: `交易日期`, `年`, `月`
            - 基本資訊: `建物面積`, `屋齡`, `樓層`
            """)


def display_simple_analysis(df):
    """顯示簡化資料分析"""
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
        st.dataframe(df.head(), use_container_width=True)
    
    # 欄位資訊
    with st.expander("📊 欄位資訊"):
        col_info = pd.DataFrame({
            '欄位名稱': df.columns,
            '資料類型': df.dtypes.astype(str),
            '非空值數': df.notnull().sum(),
            '空值率%': (df.isnull().sum() / len(df) * 100).round(2)
        })
        st.dataframe(col_info, use_container_width=True)
    
    # 基本統計分析
    st.subheader("📈 基本統計分析")
    
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
            fig = px.histogram(df, x=selected_col, title=f"{selected_col} 分布")
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("沒有找到數值型欄位進行統計分析")
    
    # 下載分析結果
    st.subheader("💾 匯出結果")
    
    if st.button("📥 下載資料摘要"):
        # 建立摘要資料
        summary_data = {
            '統計項目': ['總筆數', '欄位數', '數值欄位數', '資料大小(MB)'],
            '數值': [
                len(df),
                len(df.columns),
                len(numeric_cols),
                f"{df.memory_usage(deep=True).sum() / 1024 / 1024:.1f}"
            ]
        }
        
        summary_df = pd.DataFrame(summary_data)
        
        # 提供下載
        csv = summary_df.to_csv(index=False, encoding='utf-8-sig')
        st.download_button(
            label="下載摘要報告 (CSV)",
            data=csv,
            file_name="資料分析摘要.csv",
            mime="text/csv"
        )


# 如果直接執行此檔案
if __name__ == "__main__":
    import plotly.express as px
    import plotly.graph_objects as go
    
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
