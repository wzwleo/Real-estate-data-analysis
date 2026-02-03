# page_modules/analysis_page.py
"""
分析頁面主模組 - 包含診斷功能
"""

import os
import sys
import streamlit as st
import pandas as pd
import time

# 修正導入路徑
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
components_dir = os.path.join(parent_dir, "components")

st.sidebar.markdown("### 🔍 系統診斷")

# 診斷：檢查目錄結構
st.sidebar.write("**檔案結構檢查:**")
for dir_path in [parent_dir, components_dir]:
    if os.path.exists(dir_path):
        st.sidebar.success(f"✅ {os.path.basename(dir_path)}/ 存在")
    else:
        st.sidebar.error(f"❌ {os.path.basename(dir_path)}/ 不存在")

# 診斷：檢查 components 目錄內容
if os.path.exists(components_dir):
    files = os.listdir(components_dir)
    st.sidebar.write(f"**components/ 目錄內容:**")
    for file in files:
        if file.endswith('.py'):
            st.sidebar.info(f"📄 {file}")
else:
    st.sidebar.error("components/ 目錄不存在")

# 將 components 目錄添加到 Python 路徑
if components_dir not in sys.path:
    sys.path.insert(0, components_dir)

# 嘗試導入模組 - 簡單直接的方式
import_success = False
MARKET_TREND_AVAILABLE = False
MarketTrendClass = None

try:
    # 1. 先導入個別分析和比較模組
    from solo_analysis import tab1_module
    from comparison import ComparisonAnalyzer
    st.sidebar.success("✅ 基本模組導入成功")
    
    # 2. 嘗試導入市場趨勢模組
    try:
        # 首先檢查檔案是否存在
        market_trend_path = os.path.join(components_dir, "market_trend.py")
        if os.path.exists(market_trend_path):
            st.sidebar.success("✅ market_trend.py 檔案存在")
            
            # 直接導入
            import importlib.util
            
            spec = importlib.util.spec_from_file_location(
                "market_trend", 
                market_trend_path
            )
            market_trend_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(market_trend_module)
            
            # 檢查模組中的類別
            if hasattr(market_trend_module, 'CompleteMarketTrendAnalyzer'):
                MarketTrendClass = market_trend_module.CompleteMarketTrendAnalyzer
                MARKET_TREND_AVAILABLE = True
                st.sidebar.success("✅ 找到 CompleteMarketTrendAnalyzer 類別")
            elif hasattr(market_trend_module, 'MarketTrendAnalyzer'):
                MarketTrendClass = market_trend_module.MarketTrendAnalyzer
                MARKET_TREND_AVAILABLE = True
                st.sidebar.success("✅ 找到 MarketTrendAnalyzer 類別")
            elif hasattr(market_trend_module, 'main'):
                MarketTrendClass = market_trend_module
                MARKET_TREND_AVAILABLE = True
                st.sidebar.success("✅ 找到 main 函數")
            else:
                st.sidebar.warning("⚠️ 未找到標準類別名稱")
                
                # 列出所有可能的類別
                st.sidebar.write("模組中的類別:")
                for attr_name in dir(market_trend_module):
                    attr = getattr(market_trend_module, attr_name)
                    if isinstance(attr, type):
                        st.sidebar.info(f"📦 {attr_name}")
                        MarketTrendClass = attr
                        MARKET_TREND_AVAILABLE = True
        else:
            st.sidebar.error("❌ market_trend.py 檔案不存在")
            
    except Exception as e:
        st.sidebar.error(f"❌ 導入市場趨勢模組失敗: {str(e)}")
    
    import_success = True
    
except Exception as e:
    st.sidebar.error(f"❌ 導入失敗: {str(e)}")
    import traceback
    st.sidebar.code(traceback.format_exc()[:500])


def render_analysis_page():
    """渲染分析頁面"""
    st.title("📊 分析頁面")
    
    # Tab 分頁
    tab1, tab2, tab3 = st.tabs(["個別分析", "房屋比較", "市場趨勢分析"])
    
    # Tab1: 個別分析
    with tab1:
        try:
            tab1_module()
        except Exception as e:
            st.error(f"個別分析模組錯誤: {e}")
    
    # Tab2: 房屋比較
    with tab2:
        try:
            analyzer = ComparisonAnalyzer()
            analyzer.render_comparison_tab()
        except Exception as e:
            st.error(f"房屋比較模組錯誤: {e}")
    
    # Tab3: 市場趨勢分析
    with tab3:
        if MARKET_TREND_AVAILABLE and MarketTrendClass:
            try:
                # 創建實例並執行
                if isinstance(MarketTrendClass, type):  # 如果是類別
                    analyzer = MarketTrendClass()
                    
                    # 嘗試不同的渲染方法
                    if hasattr(analyzer, 'render_complete_dashboard'):
                        analyzer.render_complete_dashboard()
                    elif hasattr(analyzer, 'render_analysis_tab'):
                        analyzer.render_analysis_tab()
                    elif hasattr(analyzer, 'main'):
                        analyzer.main()
                    else:
                        st.error("類別沒有可用的渲染方法")
                        
                elif callable(MarketTrendClass):  # 如果是函數
                    MarketTrendClass()
                    
            except Exception as e:
                st.error(f"執行市場趨勢分析時出錯: {str(e)}")
                import traceback
                st.code(traceback.format_exc())
                
                # 提供緊急修復按鈕
                if st.button("🆘 使用緊急修復版本"):
                    render_emergency_market_trend()
        else:
            # 顯示緊急修復版本
            render_emergency_market_trend()


def render_emergency_market_trend():
    """緊急修復的市場趨勢分析"""
    st.header("📈 市場趨勢分析（緊急修復版）")
    
    st.warning("完整功能模組載入失敗，使用緊急修復版本")
    
    # 提供修復選項
    with st.expander("🛠️ 修復選項", expanded=True):
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("🔄 重新載入所有模組"):
                st.rerun()
        
        with col2:
            if st.button("📁 檢查檔案結構"):
                st.code("""
您的檔案結構應該是：
專案目錄/
├── page_modules/
│   └── analysis_page.py
├── components/
│   ├── solo_analysis.py
│   ├── comparison.py
│   └── market_trend.py  ← 必須存在！
└── requirements.txt
                """)
    
    # 簡化功能
    st.subheader("簡化功能")
    
    # 嘗試載入資料
    try:
        # 尋找資料檔案
        data_files = []
        for root, dirs, files in os.walk(parent_dir):
            for file in files:
                if file.endswith('.csv') and '不動產' in file:
                    data_files.append(os.path.join(root, file))
        
        if data_files:
            selected_file = st.selectbox("選擇資料檔案", data_files)
            
            if st.button("載入資料"):
                try:
                    df = pd.read_csv(selected_file, encoding='utf-8')
                except:
                    df = pd.read_csv(selected_file, encoding='big5')
                
                st.success(f"✅ 載入 {len(df)} 筆資料")
                
                # 基本分析
                st.subheader("📊 基本分析")
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.metric("資料筆數", len(df))
                
                with col2:
                    if '縣市' in df.columns:
                        st.metric("縣市數量", df['縣市'].nunique())
                
                with col3:
                    if '平均單價元平方公尺' in df.columns:
                        avg_price = df['平均單價元平方公尺'].mean()
                        st.metric("平均單價", f"{avg_price:,.0f}")
                
                # 資料預覽
                with st.expander("📋 資料預覽"):
                    st.dataframe(df.head(10))
        else:
            st.error("找不到任何不動產資料檔案")
            
    except Exception as e:
        st.error(f"資料載入失敗: {str(e)}")


if __name__ == "__main__":
    render_analysis_page()
