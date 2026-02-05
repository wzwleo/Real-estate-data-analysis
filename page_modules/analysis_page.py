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
MARKET_TREND_AVAILABLE = False
MarketTrendClass = None
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
    
    # 3. 導入市場趨勢分析模組 - 使用多重嘗試
    st.sidebar.write("**市場趨勢模組狀態:**")
    
    # 方法1：嘗試直接導入
    try:
        import components.market_trend as market_trend_module
        st.sidebar.info("✅ market_trend 模組導入成功")
        
        # 檢查模組中的類別
        available_classes = []
        for attr_name in dir(market_trend_module):
            attr = getattr(market_trend_module, attr_name)
            if isinstance(attr, type):  # 檢查是否為類別
                available_classes.append((attr_name, attr))
                st.sidebar.info(f"📦 找到類別: {attr_name}")
        
        # 選擇合適的類別
        preferred_classes = [
            'CompleteMarketTrendAnalyzer',
            'MarketTrendAnalyzer', 
            'SimpleMarketTrendAnalyzer'
        ]
        
        for class_name, class_obj in available_classes:
            if class_name in preferred_classes:
                MarketTrendClass = class_obj
                MARKET_TREND_AVAILABLE = True
                st.sidebar.success(f"✅ 使用 {class_name} 類別")
                break
        
        if not MARKET_TREND_AVAILABLE and available_classes:
            # 使用第一個找到的類別
            MarketTrendClass = available_classes[0][1]
            MARKET_TREND_AVAILABLE = True
            st.sidebar.warning(f"⚠️ 使用備選類別: {available_classes[0][0]}")
            
    except ImportError as e:
        st.sidebar.error(f"❌ 方法1失敗: {e}")
        
        # 方法2：嘗試使用 importlib
        try:
            import importlib.util
            market_trend_path = os.path.join(components_dir, "market_trend.py")
            
            if os.path.exists(market_trend_path):
                spec = importlib.util.spec_from_file_location(
                    "market_trend", 
                    market_trend_path
                )
                market_trend_module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(market_trend_module)
                
                # 檢查類別
                if hasattr(market_trend_module, 'CompleteMarketTrendAnalyzer'):
                    MarketTrendClass = market_trend_module.CompleteMarketTrendAnalyzer
                    MARKET_TREND_AVAILABLE = True
                    st.sidebar.success("✅ 方法2成功: 找到 CompleteMarketTrendAnalyzer")
                elif hasattr(market_trend_module, 'MarketTrendAnalyzer'):
                    MarketTrendClass = market_trend_module.MarketTrendAnalyzer
                    MARKET_TREND_AVAILABLE = True
                    st.sidebar.success("✅ 方法2成功: 找到 MarketTrendAnalyzer")
                else:
                    st.sidebar.warning("⚠️ 方法2: 未找到標準類別名稱")
            else:
                st.sidebar.error(f"❌ market_trend.py 檔案不存在於: {market_trend_path}")
                
        except Exception as e2:
            st.sidebar.error(f"❌ 方法2失敗: {e2}")
            
            # 方法3：創建緊急修復類別
            st.sidebar.warning("⚠️ 創建緊急修復類別")
            
            class EmergencyMarketTrendAnalyzer:
                def __init__(self):
                    self.df = None
                
                def render_analysis_tab(self):
                    st.header("📈 市場趨勢分析（緊急修復版）")
                    st.warning("完整功能模組載入失敗，使用緊急修復版本")
                    
                    # 簡單功能
                    st.subheader("簡化功能")
                    
                    # 嘗試載入資料
                    try:
                        data_files = []
                        for root, dirs, files in os.walk(parent_dir):
                            for file in files:
                                if file.endswith('.csv'):
                                    data_files.append(os.path.join(root, file))
                        
                        if data_files:
                            selected_file = st.selectbox("選擇資料檔案", data_files[:5])
                            
                            if st.button("載入資料"):
                                try:
                                    self.df = pd.read_csv(selected_file, encoding='utf-8')
                                except:
                                    try:
                                        self.df = pd.read_csv(selected_file, encoding='big5')
                                    except:
                                        self.df = pd.read_csv(selected_file, encoding='latin1')
                                
                                if self.df is not None:
                                    st.success(f"✅ 載入 {len(self.df)} 筆資料")
                                    
                                    # 基本分析
                                    st.subheader("📊 基本分析")
                                    col1, col2, col3 = st.columns(3)
                                    
                                    with col1:
                                        st.metric("資料筆數", len(self.df))
                                    
                                    with col2:
                                        if '縣市' in self.df.columns:
                                            st.metric("縣市數量", self.df['縣市'].nunique())
                                    
                                    with col3:
                                        if '平均單價元平方公尺' in self.df.columns:
                                            avg_price = self.df['平均單價元平方公尺'].mean()
                                            st.metric("平均單價", f"{avg_price:,.0f}")
                                    
                                    # 資料預覽
                                    with st.expander("📋 資料預覽"):
                                        st.dataframe(self.df.head(10))
                        else:
                            st.error("找不到任何 CSV 資料檔案")
                            
                    except Exception as e:
                        st.error(f"資料載入失敗: {str(e)}")
            
            MarketTrendClass = EmergencyMarketTrendAnalyzer
            MARKET_TREND_AVAILABLE = True
            st.sidebar.info("✅ 緊急修復類別已創建")
    
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
    
    # Tab3: 市場趨勢分析
    with tab3:
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
                    else:
                        # 嘗試調用默認方法
                        analyzer_instance()
                        
            except Exception as e:
                st.error(f"市場趨勢分析執行錯誤: {str(e)}")
                st.code(traceback.format_exc())
                
                # 提供修復選項
                st.subheader("🛠️ 問題排除")
                col1, col2 = st.columns(2)
                
                with col1:
                    if st.button("🔄 重新載入模組", use_container_width=True):
                        st.rerun()
                
                with col2:
                    if st.button("📋 顯示詳細錯誤", use_container_width=True):
                        with st.expander("詳細錯誤追蹤"):
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
    
    # 提供修復指南
    with st.expander("🔧 如何修復？", expanded=True):
        st.markdown("""
        ### 修復步驟：
        
        1. **檢查檔案結構**
        ```
        您的專案/
        ├── page_modules/
        │   └── analysis_page.py  ← 這個檔案
        ├── components/
        │   ├── __init__.py
        │   ├── solo_analysis.py
        │   ├── comparison.py
        │   └── market_trend.py   ← 必須存在！
        └── 不動產資料.csv         ← 資料檔案
        ```
        
        2. **檢查錯誤訊息**
           - 查看側邊欄的系統狀態
           - 檢查是否有導入錯誤
        
        3. **重新啟動應用**
           ```bash
           streamlit run app.py
           ```
        """)
    
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
                    
                    # 匯出功能
                    st.subheader("💾 資料匯出")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("📥 下載 CSV", use_container_width=True):
                            csv = df.to_csv(index=False).encode('utf-8-sig')
                            st.download_button(
                                label="點擊下載",
                                data=csv,
                                file_name=f"不動產資料_{time.strftime('%Y%m%d_%H%M%S')}.csv",
                                mime="text/csv",
                                use_container_width=True
                            )
                    
                    with col2:
                        if st.button("📊 下載摘要", use_container_width=True):
                            summary = df.describe().to_csv()
                            st.download_button(
                                label="點擊下載",
                                data=summary.encode(),
                                file_name=f"資料摘要_{time.strftime('%Y%m%d_%H%M%S')}.csv",
                                mime="text/csv",
                                use_container_width=True
                            )
                
                except Exception as e:
                    st.error(f"載入資料時發生錯誤: {str(e)}")
                    st.code(traceback.format_exc())
        else:
            st.warning("未找到任何資料檔案")
            st.info("請將資料檔案（CSV 或 Excel）放置在專案目錄中")
    
    except Exception as e:
        st.error(f"尋找檔案時發生錯誤: {str(e)}")


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
