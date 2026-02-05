# components/market_trend.py - 移除購房目的、購買建議、市場預測模型和統計指標
import streamlit as st
import pandas as pd
import numpy as np
import os
import sys
import time
from datetime import datetime
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from scipy import stats
import warnings
warnings.filterwarnings('ignore')

try:
    from streamlit_echarts import st_echarts
    ECHARTS_AVAILABLE = True
except ImportError:
    ECHARTS_AVAILABLE = False

try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

# 修正匯入路徑
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

try:
    from config import PAGE_MODULES_FOLDER
    CONFIG_LOADED = True
except ImportError as e:
    CONFIG_LOADED = False
    PAGE_MODULES_FOLDER = parent_dir


class CompleteMarketTrendAnalyzer:
    """市場趨勢分析器 - 簡化功能版"""
    
    def __init__(self):
        self.combined_df = None
        self.loaded = False
        
    def render_complete_dashboard(self):
        """渲染完整市場趨勢儀表板"""
        st.title("🏠 不動產市場交易資料(101-114)")
        
        # 初始化狀態
        self._init_session_state()
        
        # 載入資料
        if not self.loaded:
            with st.spinner("📊 載入資料中..."):
                if self._load_data():
                    self.loaded = True
                    if self.combined_df is not None:
                        st.success(f"✅ 資料載入完成 ({len(self.combined_df):,} 筆不動產資料)")
        
        if not self.loaded:
            st.error("無法載入資料，請檢查檔案路徑")
            return
        
        # 簡潔的資料統計
        with st.expander("📊 資料統計概覽", expanded=False):
            if self.combined_df is not None:
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("不動產資料", f"{len(self.combined_df):,} 筆")
                with col2:
                    if '縣市' in self.combined_df.columns:
                        st.metric("縣市數量", self.combined_df['縣市'].nunique())
                with col3:
                    if '平均單價元每坪' in self.combined_df.columns:
                        avg_price = self.combined_df['平均單價元每坪'].mean()
                        st.metric("平均單價", f"{avg_price:,.0f} 元/坪")
                with col4:
                    if '民國年' in self.combined_df.columns:
                        years = self.combined_df['民國年'].unique()
                        st.metric("年份範圍", f"{min(years)}-{max(years)}")
        
        # 側邊欄導航
        st.sidebar.title("📋 分析模組")
        analysis_option = st.sidebar.selectbox(
            "選擇分析功能",
            [
                "🏠 購房決策助手",
                "📈 價格趨勢分析",
                "📊 區域比較分析",
                "📋 原始資料檢視"
            ]  # 移除「🎯 市場預測模型」
        )
        
        # 根據選擇顯示對應模組
        if analysis_option == "🏠 購房決策助手":
            self._render_home_buying_assistant()
        elif analysis_option == "📈 價格趨勢分析":
            self._render_price_trend_analysis()
        elif analysis_option == "📊 區域比較分析":
            self._render_region_comparison()
        elif analysis_option == "📋 原始資料檢視":
            self._render_raw_data_view()
    
    def _init_session_state(self):
        """初始化 session state"""
        if 'market_analysis_result' not in st.session_state:
            st.session_state.market_analysis_result = None
        if 'market_analysis_key' not in st.session_state:
            st.session_state.market_analysis_key = None
        if 'selected_regions' not in st.session_state:
            st.session_state.selected_regions = []
        if 'user_profile' not in st.session_state:
            st.session_state.user_profile = {}
    
    def _load_data(self):
        """載入所有資料"""
        try:
            # 載入不動產資料
            self.combined_df = self._load_real_estate_data()
            
            if self.combined_df is None or self.combined_df.empty:
                st.error("無法載入不動產資料")
                return False
            
            # 清理和預處理資料
            self._clean_and_preprocess_data()
            
            return True
            
        except Exception as e:
            st.error(f"載入資料失敗: {str(e)}")
            return False
    
    def _load_real_estate_data(self):
        """載入不動產資料"""
        try:
            data_dir = PAGE_MODULES_FOLDER
            csv_files = [f for f in os.listdir(data_dir) 
                        if f.startswith("合併後不動產統計_") and f.endswith(".csv")]
            
            if not csv_files:
                csv_files = [f for f in os.listdir(data_dir) if "不動產" in f and f.endswith(".csv")]
            
            if not csv_files:
                return pd.DataFrame()
            
            dfs = []
            
            for file in csv_files:
                file_path = os.path.join(data_dir, file)
                try:
                    # 嘗試不同編碼
                    df = None
                    for encoding in ["utf-8", "big5", "cp950", "latin1"]:
                        try:
                            df = pd.read_csv(file_path, encoding=encoding, low_memory=False)
                            break
                        except:
                            continue
                    
                    if df is None:
                        continue
                    
                    # 檢查必要欄位
                    required_cols = ["縣市", "行政區", "BUILD", "平均單價元平方公尺", "交易筆數"]
                    
                    # 尋找可能的不同名稱
                    col_mapping = {}
                    for required in required_cols:
                        if required not in df.columns:
                            possible_names = [
                                col for col in df.columns 
                                if required in col or col in required
                            ]
                            if possible_names:
                                col_mapping[required] = possible_names[0]
                    
                    if col_mapping:
                        df = df.rename(columns=col_mapping)
                    
                    missing_cols = [col for col in required_cols if col not in df.columns]
                    
                    if missing_cols:
                        continue
                    
                    dfs.append(df)
                    
                except Exception:
                    continue
            
            if dfs:
                return pd.concat(dfs, ignore_index=True)
            else:
                return pd.DataFrame()
                
        except Exception as e:
            return pd.DataFrame()
    
    def _clean_and_preprocess_data(self):
        """清理和預處理資料"""
        try:
            # ========== 清理不動產資料 ==========
            if self.combined_df is not None and not self.combined_df.empty:
                # 處理季度資料
                if "季度" in self.combined_df.columns:
                    self.combined_df["季度"] = self.combined_df["季度"].fillna("未知季度")
                    
                    def extract_year(quarter_str):
                        if isinstance(quarter_str, str):
                            import re
                            match = re.search(r'(\d{3})年', quarter_str)
                            if match:
                                try:
                                    return int(match.group(1))
                                except:
                                    return np.nan
                        return np.nan
                    
                    self.combined_df["民國年"] = self.combined_df["季度"].apply(extract_year)
                    
                    if self.combined_df["民國年"].isna().any():
                        if not self.combined_df["民國年"].isna().all():
                            median_year = self.combined_df["民國年"].median()
                            self.combined_df["民國年"] = self.combined_df["民國年"].fillna(median_year)
                        else:
                            self.combined_df["民國年"] = 108
                    
                    self.combined_df["民國年"] = self.combined_df["民國年"].astype(int)
                    
                    def extract_quarter(quarter_str):
                        if isinstance(quarter_str, str):
                            import re
                            match = re.search(r'第(\d)季', quarter_str)
                            if match:
                                try:
                                    return int(match.group(1))
                                except:
                                    return 1
                        return 1
                    
                    self.combined_df["季度數字"] = self.combined_df["季度"].apply(extract_quarter)
                else:
                    self.combined_df["民國年"] = 108
                    self.combined_df["季度數字"] = 1
                
                # 處理單價資料
                if "平均單價元平方公尺" in self.combined_df.columns:
                    self.combined_df["平均單價元平方公尺"] = pd.to_numeric(
                        self.combined_df["平均單價元平方公尺"], 
                        errors='coerce'
                    )
                    
                    median_price = self.combined_df["平均單價元平方公尺"].median()
                    if pd.notna(median_price):
                        self.combined_df["平均單價元平方公尺"] = self.combined_df["平均單價元平方公尺"].fillna(median_price)
                    
                    self.combined_df["平均單價元每坪"] = self.combined_df["平均單價元平方公尺"] * 3.3058
                else:
                    self.combined_df["平均單價元每坪"] = 0
                
                # 處理交易筆數
                if "交易筆數" in self.combined_df.columns:
                    self.combined_df["交易筆數"] = pd.to_numeric(
                        self.combined_df["交易筆數"], 
                        errors='coerce'
                    ).fillna(0).astype(int)
                    
                    self.combined_df["總交易金額萬元"] = (
                        self.combined_df["平均單價元平方公尺"] * 
                        self.combined_df["交易筆數"] / 10000
                    ).round(2)
                else:
                    self.combined_df["交易筆數"] = 0
                    self.combined_df["總交易金額萬元"] = 0
                
                # 處理其他欄位
                for col in ["縣市", "行政區", "BUILD"]:
                    if col in self.combined_df.columns:
                        self.combined_df[col] = self.combined_df[col].fillna("未知")
                    else:
                        self.combined_df[col] = "未知"
        
        except Exception as e:
            pass
    
    def _render_home_buying_assistant(self):
        """渲染購房決策助手 - 移除購房目的選項，加上房屋類型選擇"""
        st.header("🏠 智慧購房決策助手")
        
        if self.combined_df is None or self.combined_df.empty:
            st.warning("無法載入資料，請先載入不動產資料")
            return
        
        # 用戶需求調查 - 移除購房目的欄位，加上房屋類型選擇
        with st.expander("📝 填寫您的購房需求", expanded=True):
            col1, col2 = st.columns(2)
            
            with col1:
                budget = st.number_input(
                    "預算總額（萬元）",
                    min_value=100,
                    max_value=10000,
                    value=1000,
                    step=100
                )
            
            with col2:
                expected_size = st.number_input(
                    "期望坪數",
                    min_value=10,
                    max_value=100,
                    value=30,
                    step=5
                )
            
            col3, col4 = st.columns(2)
            
            with col3:
                # 房屋類型選擇
                house_types = st.multiselect(
                    "房屋類型",
                    options=["新成屋", "中古屋"],
                    default=["新成屋", "中古屋"]
                )
            
            with col4:
                loan_rate = st.slider(
                    "房貸利率 (%)",
                    min_value=0.0,
                    max_value=5.0,
                    value=2.0,
                    step=0.1
                )
            
            col5, col6 = st.columns(2)
            
            with col5:
                holding_years = st.slider(
                    "預計持有年限",
                    min_value=1,
                    max_value=30,
                    value=10
                )
        
        # 地區選擇
        st.subheader("📍 選擇目標地區")
        
        col1, col2 = st.columns(2)
        
        with col1:
            counties = ["全部縣市"] + sorted(self.combined_df["縣市"].dropna().unique().tolist())
            selected_county = st.selectbox("選擇縣市", counties)
        
        with col2:
            if selected_county != "全部縣市":
                districts = ["全部行政區"] + sorted(
                    self.combined_df[self.combined_df["縣市"] == selected_county]["行政區"].dropna().unique().tolist()
                )
                selected_district = st.selectbox("選擇行政區", districts)
            else:
                selected_district = "全部行政區"
        
        # 時間範圍選擇
        if '民國年' in self.combined_df.columns:
            year_min = int(self.combined_df["民國年"].min())
            year_max = int(self.combined_df["民國年"].max())
            
            year_range = st.slider(
                "分析時間範圍",
                min_value=year_min,
                max_value=year_max,
                value=(max(year_min, year_max-5), year_max)
            )
        else:
            year_range = (108, 112)
        
        # 篩選資料
        filtered_df = self._filter_real_estate_data(
            selected_county, selected_district, year_range
        )
        
        # 根據房屋類型進一步篩選
        if house_types:
            filtered_df = filtered_df[filtered_df["BUILD"].isin(house_types)]
        
        if filtered_df.empty:
            st.warning("該條件下無符合的資料")
            return
        
        # 顯示分析結果
        self._analyze_for_home_buying(
            filtered_df, budget, expected_size, holding_years, loan_rate
        )
    
    def _filter_real_estate_data(self, county, district, year_range):
        """篩選不動產資料"""
        try:
            filtered_df = self.combined_df.copy()
            
            if '民國年' in filtered_df.columns:
                filtered_df = filtered_df[
                    (filtered_df["民國年"] >= year_range[0]) &
                    (filtered_df["民國年"] <= year_range[1])
                ]
            
            if county != "全部縣市":
                filtered_df = filtered_df[filtered_df["縣市"] == county]
                
                if district != "全部行政區":
                    filtered_df = filtered_df[filtered_df["行政區"] == district]
            
            return filtered_df
            
        except Exception as e:
            return pd.DataFrame()
    
    def _analyze_for_home_buying(self, df, budget, size, holding_years, loan_rate):
        """分析購房需求 - 移除購房目的參數"""
        st.subheader("📊 分析結果")
        
        # 計算關鍵指標
        metrics = self._calculate_home_buying_metrics(df, budget, size)
        
        # 顯示關鍵指標卡片 - 移除交易活躍度，加上房屋類型比例
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            if 'avg_price_per_ping' in metrics:
                price_change = metrics.get('price_change_1y', 0)
                delta = f"{price_change:+.1f}%" if price_change != 0 else None
                st.metric(
                    "🏠 平均單價",
                    f"{metrics['avg_price_per_ping']:,.0f} 元/坪",
                    delta=delta
                )
        
        with col2:
            if 'avg_price_per_ping' in metrics and metrics['avg_price_per_ping'] > 0:
                affordable_ping = budget * 10000 / metrics['avg_price_per_ping']
                st.metric(
                    "💰 可負擔坪數",
                    f"{affordable_ping:.1f} 坪",
                    delta="您的預算"
                )
        
        with col3:
            if 'annual_growth' in metrics:
                st.metric(
                    "📈 年化漲幅",
                    f"{metrics['annual_growth']:.1f}%",
                    delta=f"近{holding_years}年"
                )
        
        with col4:
            # 顯示房屋類型比例
            if 'BUILD' in df.columns:
                # 計算新成屋比例
                if '新成屋' in df['BUILD'].unique():
                    new_count = len(df[df['BUILD'] == '新成屋'])
                    total_count = len(df)
                    new_ratio = (new_count / total_count * 100) if total_count > 0 else 0
                    
                    # 根據比例顯示不同訊息
                    if new_ratio >= 70:
                        house_type_info = "以新成屋為主"
                    elif new_ratio <= 30:
                        house_type_info = "以中古屋為主"
                    else:
                        house_type_info = "混合市場"
                    
                    st.metric(
                        "🏘️ 房屋類型",
                        f"{new_ratio:.0f}% 新成屋",
                        delta=house_type_info
                    )
        
        # 詳細分析 - 移除「購買建議」標籤頁
        tabs = st.tabs(["📈 價格趨勢", "🏘️ 交易分布", "💸 價格分析"])  # 移除「🎯 購買建議」
        
        with tabs[0]:
            self._plot_price_trend_analysis(df)
        
        with tabs[1]:
            self._plot_product_analysis(df)
        
        with tabs[2]:
            self._plot_financial_analysis(df, budget, size, loan_rate, holding_years)
    
    # ========== 價格趨勢分析功能 ==========
    def _render_price_trend_analysis(self):
        """渲染價格趨勢分析"""
        st.header("📈 價格趨勢深度分析")
        
        if self.combined_df is None or self.combined_df.empty:
            st.warning("無資料可用")
            return
        
        # 分析選項
        col1, col2, col3 = st.columns(3)
        
        with col1:
            counties = ["全部"] + sorted(self.combined_df["縣市"].dropna().unique().tolist())
            selected_county = st.selectbox("選擇縣市", counties, key="trend_county")
        
        with col2:
            house_types = st.multiselect(
                "房屋類型",
                options=["新成屋", "中古屋"],
                default=["新成屋", "中古屋"],
                key="trend_type"
            )
        
        with col3:
            if '民國年' in self.combined_df.columns:
                year_min = int(self.combined_df["民國年"].min())
                year_max = int(self.combined_df["民國年"].max())
                year_range = st.slider(
                    "時間範圍",
                    min_value=year_min,
                    max_value=year_max,
                    value=(year_min, year_max),
                    key="trend_year"
                )
        
        # 篩選資料
        filtered_df = self.combined_df.copy()
        
        if selected_county != "全部":
            filtered_df = filtered_df[filtered_df["縣市"] == selected_county]
        
        if house_types:
            filtered_df = filtered_df[filtered_df["BUILD"].isin(house_types)]
        
        if '民國年' in filtered_df.columns:
            filtered_df = filtered_df[
                (filtered_df["民國年"] >= year_range[0]) &
                (filtered_df["民國年"] <= year_range[1])
            ]
        
        if filtered_df.empty:
            st.warning("該條件下無資料")
            return
        
        # 分析標籤頁 - 移除「統計指標」標籤
        tab1, tab2 = st.tabs(["趨勢圖表", "比較分析"])  # 移除「統計指標」
        
        with tab1:
            self._plot_trend_charts(filtered_df)
        
        with tab2:
            self._plot_comparative_analysis(filtered_df)
    
    def _plot_trend_charts(self, df):
        """繪製趨勢圖表"""
        st.subheader("📊 價格趨勢圖")
        
        # 1. 年度平均價格趨勢
        if '民國年' in df.columns and '平均單價元每坪' in df.columns:
            yearly_avg = df.groupby(['民國年', 'BUILD'])['平均單價元每坪'].mean().reset_index()
            
            if not yearly_avg.empty:
                fig = px.line(
                    yearly_avg,
                    x='民國年',
                    y='平均單價元每坪',
                    color='BUILD',
                    title='年度平均單價趨勢',
                    markers=True,
                    line_shape='spline'
                )
                
                fig.update_layout(
                    xaxis_title="年份",
                    yaxis_title="平均單價（元/坪）",
                    hovermode="x unified",
                    height=500
                )
                
                st.plotly_chart(fig, use_container_width=True)
        
        # 2. 移動平均趨勢
        if '民國年' in df.columns and '平均單價元每坪' in df.columns:
            yearly_price = df.groupby('民國年')['平均單價元每坪'].mean().reset_index()
            
            # 計算移動平均
            yearly_price['3年移動平均'] = yearly_price['平均單價元每坪'].rolling(window=3, min_periods=1).mean()
            yearly_price['5年移動平均'] = yearly_price['平均單價元每坪'].rolling(window=5, min_periods=1).mean()
            
            fig2 = go.Figure()
            
            fig2.add_trace(go.Scatter(
                x=yearly_price['民國年'],
                y=yearly_price['平均單價元每坪'],
                mode='markers',
                name='實際價格',
                marker=dict(size=8, color='blue')
            ))
            
            fig2.add_trace(go.Scatter(
                x=yearly_price['民國年'],
                y=yearly_price['3年移動平均'],
                mode='lines',
                name='3年移動平均',
                line=dict(color='red', width=2)
            ))
            
            fig2.add_trace(go.Scatter(
                x=yearly_price['民國年'],
                y=yearly_price['5年移動平均'],
                mode='lines',
                name='5年移動平均',
                line=dict(color='green', width=2, dash='dash')
            ))
            
            fig2.update_layout(
                title='移動平均趨勢分析',
                xaxis_title="年份",
                yaxis_title="平均單價（元/坪）",
                hovermode="x unified",
                height=500
            )
            
            st.plotly_chart(fig2, use_container_width=True)
    
    def _plot_comparative_analysis(self, df):
        """繪製比較分析"""
        st.subheader("🔄 比較分析")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # 地區比較
            if '縣市' in df.columns and len(df['縣市'].unique()) > 1:
                counties = st.multiselect(
                    "選擇比較縣市",
                    options=sorted(df['縣市'].unique()),
                    default=sorted(df['縣市'].unique())[:3]
                )
                
                if counties:
                    compare_df = df[df['縣市'].isin(counties)]
                    county_avg = compare_df.groupby(['縣市', 'BUILD'])['平均單價元每坪'].mean().reset_index()
                    
                    fig = px.bar(
                        county_avg,
                        x='縣市',
                        y='平均單價元每坪',
                        color='BUILD',
                        barmode='group',
                        title='各縣市價格比較',
                        text_auto='.0f'
                    )
                    
                    st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            # 房屋類型比較
            if 'BUILD' in df.columns:
                build_avg = df.groupby('BUILD')['平均單價元每坪'].mean().reset_index()
                
                fig2 = px.pie(
                    build_avg,
                    values='平均單價元每坪',
                    names='BUILD',
                    title='房屋類型價格占比',
                    hole=0.4
                )
                
                st.plotly_chart(fig2, use_container_width=True)
    
    # ========== 區域比較分析功能 ==========
    def _render_region_comparison(self):
        """渲染區域比較分析 - 加上年份選擇"""
        st.header("🏙️ 區域比較分析")
        
        if self.combined_df is None or self.combined_df.empty:
            st.warning("無資料可用")
            return
        
        # 選擇年份範圍
        st.subheader("📅 選擇年份範圍")
        
        if '民國年' in self.combined_df.columns:
            year_min = int(self.combined_df["民國年"].min())
            year_max = int(self.combined_df["民國年"].max())
            
            year_range = st.slider(
                "分析年份範圍",
                min_value=year_min,
                max_value=year_max,
                value=(max(year_min, year_max-5), year_max),
                key="region_year_range"
            )
        
        # 選擇比較區域
        st.subheader("📍 選擇比較區域")
        
        counties = st.multiselect(
            "選擇比較縣市",
            options=sorted(self.combined_df["縣市"].dropna().unique().tolist()),
            default=sorted(self.combined_df["縣市"].dropna().unique().tolist())[:3]
        )
        
        if not counties:
            st.warning("請選擇至少一個縣市進行比較")
            return
        
        # 篩選資料 - 加入年份篩選
        filtered_df = self.combined_df.copy()
        
        # 篩選年份
        if '民國年' in filtered_df.columns:
            filtered_df = filtered_df[
                (filtered_df["民國年"] >= year_range[0]) &
                (filtered_df["民國年"] <= year_range[1])
            ]
        
        # 篩選縣市
        filtered_df = filtered_df[filtered_df["縣市"].isin(counties)]
        
        if filtered_df.empty:
            st.warning("該條件下無資料")
            return
        
        # 顯示選擇的年份範圍
        st.info(f"分析年份：{year_range[0]} 年 - {year_range[1]} 年")
        
        # 分析標籤頁
        tab1, tab2 = st.tabs(["價格比較", "交易量分析"])
        
        with tab1:
            self._plot_region_price_comparison(filtered_df, counties, year_range)
        
        with tab2:
            self._plot_region_volume_comparison(filtered_df, counties, year_range)
    
    def _plot_region_price_comparison(self, df, counties, year_range):
        """繪製區域價格比較"""
        st.subheader("💰 價格比較分析")
        
        # 顯示年份範圍
        st.caption(f"年份範圍：{year_range[0]} 年 - {year_range[1]} 年")
        
        # 1. 趨勢比較
        if '民國年' in df.columns and '平均單價元每坪' in df.columns:
            yearly_price = df.groupby(['縣市', '民國年'])['平均單價元每坪'].mean().reset_index()
            
            fig = px.line(
                yearly_price,
                x='民國年',
                y='平均單價元每坪',
                color='縣市',
                title=f'各縣市價格趨勢比較 ({year_range[0]}-{year_range[1]}年)',
                markers=True
            )
            
            fig.update_layout(
                xaxis_title="年份",
                yaxis_title="平均單價（元/坪）",
                hovermode="x unified",
                height=500
            )
            
            st.plotly_chart(fig, use_container_width=True)
        
        # 2. 最新年度價格排行
        if '民國年' in df.columns:
            latest_year = df['民國年'].max()
            latest_prices = df[df['民國年'] == latest_year].groupby('縣市')['平均單價元每坪'].mean().reset_index()
            latest_prices = latest_prices.sort_values('平均單價元每坪', ascending=False)
            
            fig2 = px.bar(
                latest_prices,
                x='縣市',
                y='平均單價元每坪',
                title=f'{latest_year}年各縣市價格排行',
                color='平均單價元每坪',
                text_auto='.0f'
            )
            
            fig2.update_layout(
                xaxis_title="縣市",
                yaxis_title="平均單價（元/坪）",
                height=500
            )
            
            st.plotly_chart(fig2, use_container_width=True)
        
        # 3. 價格分布比較
        fig3 = px.box(
            df,
            x='縣市',
            y='平均單價元每坪',
            title=f'各縣市價格分布比較 ({year_range[0]}-{year_range[1]}年)',
            points="all"
        )
        
        fig3.update_layout(
            xaxis_title="縣市",
            yaxis_title="單價（元/坪）",
            height=500
        )
        
        st.plotly_chart(fig3, use_container_width=True)
    
    def _plot_region_volume_comparison(self, df, counties, year_range):
        """繪製區域交易量比較"""
        st.subheader("📊 交易量分析")
        
        # 顯示年份範圍
        st.caption(f"年份範圍：{year_range[0]} 年 - {year_range[1]} 年")
        
        if '交易筆數' in df.columns:
            # 1. 交易量趨勢
            if '民國年' in df.columns:
                yearly_volume = df.groupby(['縣市', '民國年'])['交易筆數'].sum().reset_index()
                
                fig = px.line(
                    yearly_volume,
                    x='民國年',
                    y='交易筆數',
                    color='縣市',
                    title=f'各縣市交易量趨勢 ({year_range[0]}-{year_range[1]}年)',
                    markers=True
                )
                
                fig.update_layout(
                    xaxis_title="年份",
                    yaxis_title="交易筆數",
                    hovermode="x unified",
                    height=500
                )
                
                st.plotly_chart(fig, use_container_width=True)
            
            # 2. 累計交易量
            total_volume = df.groupby('縣市')['交易筆數'].sum().reset_index()
            total_volume = total_volume.sort_values('交易筆數', ascending=False)
            
            fig2 = px.bar(
                total_volume,
                x='縣市',
                y='交易筆數',
                title=f'各縣市累計交易量 ({year_range[0]}-{year_range[1]}年)',
                color='交易筆數',
                text_auto='.0f'
            )
            
            fig2.update_layout(
                xaxis_title="縣市",
                yaxis_title="交易筆數",
                height=500
            )
            
            st.plotly_chart(fig2, use_container_width=True)
            
            # 3. 交易量占比
            fig3 = px.pie(
                total_volume,
                values='交易筆數',
                names='縣市',
                title=f'各縣市交易量占比 ({year_range[0]}-{year_range[1]}年)',
                hole=0.4
            )
            
            st.plotly_chart(fig3, use_container_width=True)
    
    # ========== 原始資料檢視功能 ==========
    def _render_raw_data_view(self):
        """渲染原始資料檢視"""
        st.header("📋 原始資料檢視")
        
        df = self.combined_df
        if df is None or df.empty:
            st.warning("無不動產資料可用")
            return
        st.info(f"不動產資料：共 {len(df)} 筆記錄")
        
        # 篩選選項
        with st.expander("🔍 篩選選項", expanded=False):
            col1, col2, col3 = st.columns(3)
            
            with col1:
                if '縣市' in df.columns:
                    counties = ["全部"] + sorted(df['縣市'].dropna().unique().tolist())
                    selected_county = st.selectbox("縣市", counties, key="raw_county")
                else:
                    selected_county = "全部"
            
            with col2:
                if selected_county != "全部" and '行政區' in df.columns:
                    districts = ["全部"] + sorted(
                        df[df['縣市'] == selected_county]['行政區'].dropna().unique().tolist()
                    )
                    selected_district = st.selectbox("行政區", districts, key="raw_district")
                else:
                    selected_district = "全部"
            
            with col3:
                if 'BUILD' in df.columns:
                    house_types = ["全部"] + sorted(df['BUILD'].dropna().unique().tolist())
                    selected_type = st.selectbox("房屋類型", house_types, key="raw_type")
                else:
                    selected_type = "全部"
        
        # 篩選資料
        filtered_df = df.copy()
        
        if selected_county != "全部" and '縣市' in filtered_df.columns:
            filtered_df = filtered_df[filtered_df['縣市'] == selected_county]
        
        if selected_district != "全部" and '行政區' in filtered_df.columns:
            filtered_df = filtered_df[filtered_df['行政區'] == selected_district]
        
        if selected_type != "全部" and 'BUILD' in filtered_df.columns:
            filtered_df = filtered_df[filtered_df['BUILD'] == selected_type]
        
        # 顯示資料
        st.subheader(f"📊 資料預覽（{len(filtered_df)} 筆）")
        
        # 分頁顯示
        page_size = st.slider("每頁顯示筆數", 10, 100, 20)
        
        total_pages = max(1, len(filtered_df) // page_size)
        page_number = st.number_input("頁碼", 1, total_pages, 1)
        
        start_idx = (page_number - 1) * page_size
        end_idx = min(page_number * page_size, len(filtered_df))
        
        st.dataframe(
            filtered_df.iloc[start_idx:end_idx],
            use_container_width=True
        )
        
        st.caption(f"顯示第 {start_idx+1} 到 {end_idx} 筆，共 {len(filtered_df)} 筆資料")
        
        # 資料統計
        with st.expander("📈 資料統計資訊", expanded=False):
            st.write("**基本統計：**")
            numeric_cols = filtered_df.select_dtypes(include=[np.number]).columns
            if len(numeric_cols) > 0:
                st.write(filtered_df[numeric_cols].describe())
            else:
                st.write("無數值資料可供統計")
            
            st.write("**欄位資訊：**")
            col_info = pd.DataFrame({
                '欄位名稱': filtered_df.columns,
                '非空值數': filtered_df.notnull().sum().values,
                '空值數': filtered_df.isnull().sum().values,
                '資料類型': filtered_df.dtypes.values
            })
            st.dataframe(col_info, use_container_width=True)
        
        # 匯出選項
        if st.button("💾 匯出資料"):
            csv = filtered_df.to_csv(index=False).encode('utf-8-sig')
            st.download_button(
                label="📥 下載 CSV",
                data=csv,
                file_name=f"資料匯出_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                use_container_width=True
            )
    
    # ========== 其他輔助方法 ==========
    def _calculate_home_buying_metrics(self, df, budget, size):
        """計算購房關鍵指標"""
        metrics = {}
        
        try:
            # 平均單價（每坪）
            if '平均單價元每坪' in df.columns:
                avg_price = df["平均單價元每坪"].mean()
                if not np.isnan(avg_price):
                    metrics['avg_price_per_ping'] = avg_price
            
            # 價格變化
            if '民國年' in df.columns and '平均單價元每坪' in df.columns:
                years = sorted(df['民國年'].unique())
                if len(years) >= 2:
                    recent_year = years[-1]
                    prev_year = years[-2]
                    
                    recent_df = df[df['民國年'] == recent_year]
                    prev_df = df[df['民國年'] == prev_year]
                    
                    if not recent_df.empty and not prev_df.empty:
                        recent_price = recent_df['平均單價元每坪'].mean()
                        prev_price = prev_df['平均單價元每坪'].mean()
                        
                        if prev_price > 0 and not np.isnan(recent_price) and not np.isnan(prev_price):
                            price_change = ((recent_price / prev_price) - 1) * 100
                            metrics['price_change_1y'] = price_change
            
            # 年化成長率
            if '民國年' in df.columns and '平均單價元每坪' in df.columns:
                years = sorted(df['民國年'].unique())
                if len(years) >= 2:
                    first_year = years[0]
                    last_year = years[-1]
                    
                    first_df = df[df['民國年'] == first_year]
                    last_df = df[df['民國年'] == last_year]
                    
                    if not first_df.empty and not last_df.empty:
                        first_price = first_df['平均單價元每坪'].mean()
                        last_price = last_df['平均單價元每坪'].mean()
                        
                        if first_price > 0 and not np.isnan(first_price) and not np.isnan(last_price):
                            period = last_year - first_year
                            if period > 0:
                                annual_growth = ((last_price / first_price) ** (1/period) - 1) * 100
                                metrics['annual_growth'] = annual_growth
            
            # 新成屋比例（取代交易活躍度）
            if 'BUILD' in df.columns:
                if '新成屋' in df['BUILD'].unique():
                    new_count = len(df[df['BUILD'] == '新成屋'])
                    total_count = len(df)
                    
                    if total_count > 0:
                        metrics['new_house_ratio'] = (new_count / total_count) * 100
        
        except Exception as e:
            pass
        
        return metrics
    
    def _plot_price_trend_analysis(self, df):
        """繪製價格趨勢分析圖"""
        try:
            # 年度平均價格趨勢
            if '民國年' in df.columns and '平均單價元每坪' in df.columns and 'BUILD' in df.columns:
                yearly_avg = df.groupby(['民國年', 'BUILD'])['平均單價元每坪'].mean().reset_index()
                
                if not yearly_avg.empty:
                    fig = px.line(
                        yearly_avg,
                        x='民國年',
                        y='平均單價元每坪',
                        color='BUILD',
                        title='🏠 年度平均單價趨勢',
                        markers=True
                    )
                    
                    fig.update_layout(
                        xaxis_title="年份",
                        yaxis_title="平均單價（元/坪）",
                        hovermode="x unified"
                    )
                    
                    st.plotly_chart(fig, use_container_width=True)
        except Exception as e:
            pass
    
    def _plot_product_analysis(self, df):
        """繪製產品分析圖"""
        try:
            col1, col2 = st.columns(2)
            
            with col1:
                # 交易量分布
                if 'BUILD' in df.columns and '交易筆數' in df.columns:
                    trans_by_type = df.groupby('BUILD')['交易筆數'].sum().reset_index()
                    
                    if not trans_by_type.empty:
                        fig1 = px.pie(
                            trans_by_type,
                            values='交易筆數',
                            names='BUILD',
                            title='🏘️ 交易類型分布',
                            hole=0.4
                        )
                        st.plotly_chart(fig1, use_container_width=True)
            
            with col2:
                # 各行政區交易量排行
                if '行政區' in df.columns and '交易筆數' in df.columns:
                    top_districts = df.groupby('行政區')['交易筆數'].sum().reset_index()
                    top_districts = top_districts.sort_values('交易筆數', ascending=False).head(10)
                    
                    if not top_districts.empty:
                        fig2 = px.bar(
                            top_districts,
                            y='行政區',
                            x='交易筆數',
                            title='📊 熱門行政區交易量排行',
                            orientation='h',
                            color='交易筆數'
                        )
                        st.plotly_chart(fig2, use_container_width=True)
        
        except Exception as e:
            pass
    
    def _plot_financial_analysis(self, df, budget, size, loan_rate, holding_years):
        """繪製財務分析圖"""
        try:
            # 計算財務指標
            if '平均單價元每坪' in df.columns:
                avg_price_per_ping = df['平均單價元每坪'].mean()
                
                if not np.isnan(avg_price_per_ping) and avg_price_per_ping > 0:
                    total_price = avg_price_per_ping * size
                    down_payment = total_price * 0.2
                    loan_amount = total_price - down_payment
                    
                    # 每月房貸
                    monthly_rate = loan_rate / 100 / 12
                    num_payments = holding_years * 12
                    
                    if monthly_rate > 0:
                        monthly_payment = loan_amount * monthly_rate * (1 + monthly_rate) ** num_payments / \
                                        ((1 + monthly_rate) ** num_payments - 1)
                    else:
                        monthly_payment = loan_amount / num_payments
                    
                    # 顯示財務分析
                    st.subheader("💸 財務規劃分析")
                    
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        st.metric("總房價", f"{total_price:,.0f} 元")
                    
                    with col2:
                        st.metric("自備款", f"{down_payment:,.0f} 元")
                    
                    with col3:
                        st.metric("每月房貸", f"{monthly_payment:,.0f} 元/月")
                    
                    # 預估未來價值
                    if '民國年' in df.columns and '平均單價元每坪' in df.columns:
                        yearly_prices = df.groupby('民國年')['平均單價元每坪'].mean()
                        if len(yearly_prices) >= 2:
                            annual_growth = yearly_prices.pct_change().mean() * 100
                            
                            if not np.isnan(annual_growth):
                                future_value = total_price * ((1 + annual_growth/100) ** holding_years)
                                
                                st.info(f"""
                                📈 **長期投資預估**（持有 {holding_years} 年）：
                                - 預估年化報酬率：{annual_growth:.1f}%
                                - 未來價值預估：{future_value:,.0f} 元
                                - 潛在獲利：{future_value - total_price:,.0f} 元
                                """)
        
        except Exception as e:
            pass


# 主程式入口
def main():
    """主程式"""
    try:
        analyzer = CompleteMarketTrendAnalyzer()
        analyzer.render_complete_dashboard()
    except Exception as e:
        st.error(f"執行時發生錯誤: {str(e)}")


if __name__ == "__main__":
    main()
