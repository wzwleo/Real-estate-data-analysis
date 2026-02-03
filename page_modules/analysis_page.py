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
    # 嘗試導入市場趨勢分析（如果存在）
    try:
        from components.market_trend import MarketTrendAnalyzer
        MARKET_TREND_AVAILABLE = True
    except ImportError:
        MARKET_TREND_AVAILABLE = False
        st.warning("市場趨勢分析模組不可用")
    
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
        if MARKET_TREND_AVAILABLE:
            try:
                analyzer = MarketTrendAnalyzer()
                analyzer.render_analysis_tab()
            except Exception as e:
                st.error(f"市場趨勢分析模組錯誤: {e}")
                import traceback
                st.code(traceback.format_exc())
        else:
            # 簡化的市場趨勢分析（替代方案）
            st.subheader("📈 市場趨勢分析")
            st.info("完整市場趨勢分析功能正在開發中")
            
            # 載入不動產資料
            data_load_state = st.info("正在載入資料...")
            
            # 嘗試載入資料
            try:
                # 修正路徑：從當前目錄的上一層開始
                data_dir = os.path.join(current_dir, "..")
                csv_files = [
                    f for f in os.listdir(data_dir) 
                    if f.startswith("合併後不動產統計_") and f.endswith(".csv")
                ]
                
                if csv_files:
                    df_list = []
                    for file in csv_files[:3]:  # 最多載入3個檔案
                        file_path = os.path.join(data_dir, file)
                        try:
                            df = pd.read_csv(file_path, encoding='utf-8')
                            df_list.append(df)
                        except:
                            try:
                                df = pd.read_csv(file_path, encoding='big5')
                                df_list.append(df)
                            except Exception as e:
                                st.warning(f"無法讀取 {file}: {e}")
                    
                    if df_list:
                        combined_df = pd.concat(df_list, ignore_index=True)
                        st.session_state.all_properties_df = combined_df
                        
                        data_load_state.success(f"✅ 已載入 {len(combined_df)} 筆資料")
                        
                        # 顯示基本統計
                        st.subheader("📊 資料總覽")
                        col1, col2, col3, col4 = st.columns(4)
                        with col1:
                            st.metric("總資料筆數", len(combined_df))
                        with col2:
                            if '縣市' in combined_df.columns:
                                st.metric("縣市數量", combined_df['縣市'].nunique())
                        with col3:
                            if '行政區' in combined_df.columns:
                                st.metric("行政區數量", combined_df['行政區'].nunique())
                        with col4:
                            if '民國年' in combined_df.columns:
                                years = combined_df['民國年'].unique()
                                st.metric("資料年份", f"{len(years)} 年")
                        
                        # 顯示資料預覽
                        with st.expander("📂 查看資料預覽"):
                            st.dataframe(combined_df.head(10))
                    else:
                        st.warning("無法載入任何CSV檔案")
                else:
                    st.warning("找不到不動產統計CSV檔案")
                    
            except Exception as e:
                st.error(f"載入資料時發生錯誤: {e}")


# 如果直接執行此檔案
if __name__ == "__main__":
    render_analysis_page()  
