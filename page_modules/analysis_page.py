# page_modules/analysis_page.py - 修正版
"""
分析頁面主模組
整合了三個主要功能：
1. 個別分析 (Tab1)
2. 房屋比較 (Tab2) - 使用 ComparisonAnalyzer
3. 市場趨勢分析 (Tab3) - 修正導入問題
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

# 設定模組搜索路徑
components_dir = os.path.join(parent_dir, "components")
if components_dir not in sys.path:
    sys.path.insert(0, components_dir)

print(f"當前目錄: {current_dir}")
print(f"父目錄: {parent_dir}")
print(f"components目錄: {components_dir}")
print(f"Python路徑: {sys.path}")

# 嘗試導入模組
import_success = False
market_trend_available = False

try:
    # 檢查檔案是否存在
    market_trend_path = os.path.join(components_dir, "market_trend.py")
    print(f"檢查市場趨勢模組路徑: {market_trend_path}")
    print(f"檔案是否存在: {os.path.exists(market_trend_path)}")
    
    if os.path.exists(market_trend_path):
        # 嘗試動態導入
        try:
            # 方法1: 使用 importlib
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                "market_trend", 
                market_trend_path
            )
            market_trend_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(market_trend_module)
            MarketTrendAnalyzer = market_trend_module.MarketTrendAnalyzer
            market_trend_available = True
            print("✅ 使用 importlib 成功載入市場趨勢模組")
            
        except Exception as e:
            print(f"importlib 載入失敗: {e}")
            
            # 方法2: 直接執行檔案
            try:
                # 讀取檔案內容
                with open(market_trend_path, 'r', encoding='utf-8') as f:
                    code = f.read()
                
                # 執行並取得類別
                exec_globals = {}
                exec(code, exec_globals)
                MarketTrendAnalyzer = exec_globals.get('MarketTrendAnalyzer')
                
                if MarketTrendAnalyzer:
                    market_trend_available = True
                    print("✅ 使用 exec 成功載入市場趨勢模組")
                else:
                    print("❌ 在檔案中找不到 MarketTrendAnalyzer 類別")
                    
            except Exception as e2:
                print(f"exec 載入失敗: {e2}")
    
    # 嘗試導入個別分析模組
    try:
        from components.solo_analysis import tab1_module
        print("✅ 成功載入個別分析模組")
    except Exception as e:
        st.warning(f"個別分析模組載入失敗: {e}")
        # 創建一個備用函數
        def tab1_module():
            st.subheader("個別分析")
            st.info("個別分析模組暫時不可用")
    
    # 嘗試導入比較模組
    try:
        from components.comparison import ComparisonAnalyzer
        print("✅ 成功載入比較模組")
    except Exception as e:
        st.warning(f"比較模組載入失敗: {e}")
        # 創建一個備用類別
        class ComparisonAnalyzer:
            def render_comparison_tab(self):
                st.subheader("房屋比較")
                st.info("房屋比較模組暫時不可用")
    
    import_success = True
    
except ImportError as e:
    st.error(f"導入模組失敗: {e}")
    import traceback
    traceback.print_exc()
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
        
        # 顯示檔案結構
        with st.expander("📁 查看檔案結構"):
            st.code(f"""
            當前目錄: {current_dir}
            父目錄: {parent_dir}
            components目錄: {components_dir}
            
            components目錄內容:
            """)
            
            if os.path.exists(components_dir):
                files = os.listdir(components_dir)
                for file in files:
                    st.write(f"- {file}")
            else:
                st.write("components目錄不存在")
        
        return
    
    # 初始化 session state
    if 'favorites' not in st.session_state:
        st.session_state.favorites = set()
    
    # Tab 分頁
    tab_names = ["個別分析", "房屋比較"]
    if market_trend_available:
        tab_names.append("市場趨勢分析")
    
    tabs = st.tabs(tab_names)
    
    # Tab1: 個別分析
    with tabs[0]:
        try:
            tab1_module()
        except Exception as e:
            st.error(f"個別分析模組錯誤: {e}")
            import traceback
            st.code(traceback.format_exc())
    
    # Tab2: 房屋比較
    with tabs[1]:
        try:
            analyzer = ComparisonAnalyzer()
            analyzer.render_comparison_tab()
        except Exception as e:
            st.error(f"房屋比較模組錯誤: {e}")
            import traceback
            st.code(traceback.format_exc())
    
    # Tab3: 市場趨勢分析（如果有）
    if market_trend_available and len(tabs) > 2:
        with tabs[2]:
            try:
                analyzer = MarketTrendAnalyzer()
                analyzer.render_analysis_tab()
            except Exception as e:
                st.error(f"市場趨勢分析模組錯誤: {e}")
                import traceback
                st.code(traceback.format_exc())
                st.info("嘗試使用簡化版市場趨勢分析...")
                render_simple_market_analysis()


def render_simple_market_analysis():
    """簡化的市場趨勢分析（替代方案）"""
    st.subheader("📈 市場趨勢分析（簡化版）")
    
    # 嘗試載入資料
    try:
        # 檢查是否有載入的資料
        if 'all_properties_df' in st.session_state:
            combined_df = st.session_state.all_properties_df
        else:
            # 嘗試從檔案載入
            data_dir = parent_dir
            csv_files = [
                f for f in os.listdir(data_dir) 
                if f.startswith("合併後不動產統計_") and f.endswith(".csv")
            ]
            
            if not csv_files:
                st.warning("找不到不動產資料檔案")
                return
            
            df_list = []
            for file in csv_files[:3]:
                file_path = os.path.join(data_dir, file)
                try:
                    df = pd.read_csv(file_path, encoding='utf-8')
                    df_list.append(df)
                except:
                    try:
                        df = pd.read_csv(file_path, encoding='big5')
                        df_list.append(df)
                    except Exception as e:
                        st.warning(f"無法讀取 {file}")
            
            if df_list:
                combined_df = pd.concat(df_list, ignore_index=True)
                st.session_state.all_properties_df = combined_df
            else:
                st.warning("無法載入任何資料")
                return
        
        # 基本清理
        if "季度" in combined_df.columns:
            combined_df["民國年"] = combined_df["季度"].str[:3].astype(int)
        
        # 價格趨勢分析
        st.markdown("### 🏠 價格趨勢分析")
        
        # 選擇縣市
        counties = ["全台"] + sorted(combined_df["縣市"].dropna().unique().tolist())
        selected_county = st.selectbox("選擇縣市", counties, key="market_county")
        
        # 篩選資料
        if selected_county != "全台":
            filtered_df = combined_df[combined_df["縣市"] == selected_county]
        else:
            filtered_df = combined_df
        
        if filtered_df.empty:
            st.warning("該縣市無資料")
            return
        
        # 計算年度平均價格
        yearly_price = filtered_df.groupby(['民國年', 'BUILD'])['平均單價元平方公尺'].mean().reset_index()
        
        # 顯示圖表
        import plotly.express as px
        
        fig = px.line(
            yearly_price,
            x='民國年',
            y='平均單價元平方公尺',
            color='BUILD',
            title=f'{selected_county} - 不動產價格趨勢',
            markers=True
        )
        
        fig.update_layout(
            xaxis_title="年份",
            yaxis_title="平均單價（元/平方公尺）",
            hovermode="x unified"
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # 顯示統計數據
        col1, col2, col3 = st.columns(3)
        
        with col1:
            latest_year = yearly_price['民國年'].max()
            latest_price = yearly_price[yearly_price['民國年'] == latest_year]['平均單價元平方公尺'].mean()
            st.metric("最新年度平均單價", f"{latest_price:,.0f} 元/m²")
        
        with col2:
            if len(yearly_price['民國年'].unique()) >= 2:
                first_year = yearly_price['民國年'].min()
                last_year = yearly_price['民國年'].max()
                first_price = yearly_price[yearly_price['民國年'] == first_year]['平均單價元平方公尺'].mean()
                last_price = yearly_price[yearly_price['民國年'] == last_year]['平均單價元平方公尺'].mean()
                
                if first_price > 0:
                    growth_rate = ((last_price / first_price) ** (1/(last_year-first_year)) - 1) * 100
                    st.metric("年均成長率", f"{growth_rate:.1f}%")
        
        with col3:
            total_transactions = filtered_df['交易筆數'].sum()
            st.metric("總交易筆數", f"{total_transactions:,} 筆")
        
        # 區域熱度分析
        st.markdown("### 🔥 區域交易熱度")
        
        if selected_county != "全台" and '行政區' in filtered_df.columns:
            # 各行政區交易量排行
            district_transactions = filtered_df.groupby('行政區')['交易筆數'].sum().reset_index()
            district_transactions = district_transactions.sort_values('交易筆數', ascending=False).head(10)
            
            fig2 = px.bar(
                district_transactions,
                x='行政區',
                y='交易筆數',
                title='熱門行政區交易量排行',
                color='交易筆數'
            )
            
            st.plotly_chart(fig2, use_container_width=True)
        
        # 新成屋 vs 中古屋分析
        st.markdown("### 🏘️ 新成屋 vs 中古屋")
        
        house_type_stats = filtered_df.groupby('BUILD').agg({
            '平均單價元平方公尺': 'mean',
            '交易筆數': 'sum'
        }).reset_index()
        
        col1, col2 = st.columns(2)
        
        with col1:
            fig3 = px.pie(
                house_type_stats,
                values='交易筆數',
                names='BUILD',
                title='交易類型分布',
                hole=0.4
            )
            st.plotly_chart(fig3, use_container_width=True)
        
        with col2:
            fig4 = px.bar(
                house_type_stats,
                x='BUILD',
                y='平均單價元平方公尺',
                title='平均單價比較',
                color='BUILD',
                text_auto='.0f'
            )
            st.plotly_chart(fig4, use_container_width=True)
        
        # 資料下載
        st.markdown("### 💾 資料下載")
        
        csv = filtered_df.to_csv(index=False).encode('utf-8-sig')
        st.download_button(
            label="📥 下載篩選資料",
            data=csv,
            file_name=f"市場趨勢分析_{selected_county}.csv",
            mime="text/csv"
        )
        
    except Exception as e:
        st.error(f"市場趨勢分析錯誤: {e}")
        import traceback
        st.code(traceback.format_exc())


# 如果直接執行此檔案
if __name__ == "__main__":
    render_analysis_page()
