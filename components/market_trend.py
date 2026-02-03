# components/market_trend_complete.py - 完整功能版（針對您資料結構優化）
import streamlit as st
imort pandas as pd
import numpy as np
import os
import sys
import time
from datetime import datetime
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from streamlit_echarts import st_echarts
import google.generativeai as genai

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
    st.warning(f"無法載入設定或模組: {e}")


class CompleteMarketTrendAnalyzer:
    """市場趨勢分析器 - 完整功能版（針對您的資料結構）"""
    
    def __init__(self):
        self.combined_df = None
        self.population_df = None
        self.loaded = False
        
    def render_complete_dashboard(self):
        """渲染完整市場趨勢儀表板"""
        st.title("🏠 不動產市場智慧分析系統")
        
        # 初始化狀態
        self._init_session_state()
        
        # 載入資料
        if not self.loaded:
            with st.spinner("📊 載入資料中..."):
                if self._load_data():
                    self.loaded = True
                    st.success("✅ 資料載入完成")
        
        if not self.loaded:
            st.error("無法載入資料，請檢查檔案路徑")
            return
        
        # 側邊欄導航
        st.sidebar.title("📋 分析模組")
        analysis_option = st.sidebar.selectbox(
            "選擇分析功能",
            [
                "🏠 購房決策助手",
                "📈 價格趨勢分析",
                "📊 區域比較分析",
                "👥 人口與房價關係",
                "💰 投資報酬率分析",
                "🎯 市場預測模型",
                "📋 原始資料檢視"
            ]
        )
        
        # 根據選擇顯示對應模組
        if analysis_option == "🏠 購房決策助手":
            self._render_home_buying_assistant()
        elif analysis_option == "📈 價格趨勢分析":
            self._render_price_trend_analysis()
        elif analysis_option == "📊 區域比較分析":
            self._render_region_comparison()
        elif analysis_option == "👥 人口與房價關係":
            self._render_population_housing_relationship()
        elif analysis_option == "💰 投資報酬率分析":
            self._render_investment_return_analysis()
        elif analysis_option == "🎯 市場預測模型":
            self._render_market_prediction()
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
            
            # 載入人口資料
            self.population_df = self._load_population_data()
            
            # 清理和預處理資料
            self._clean_and_preprocess_data()
            
            return not self.combined_df.empty and not self.population_df.empty
            
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
                # 嘗試其他可能的檔案名稱
                csv_files = [f for f in os.listdir(data_dir) if "不動產" in f and f.endswith(".csv")]
            
            if not csv_files:
                st.warning("找不到不動產資料檔案")
                return pd.DataFrame()
            
            dfs = []
            for file in csv_files:
                file_path = os.path.join(data_dir, file)
                try:
                    df = pd.read_csv(file_path, encoding="utf-8")
                except:
                    try:
                        df = pd.read_csv(file_path, encoding="big5")
                    except:
                        try:
                            df = pd.read_csv(file_path, encoding="cp950")
                        except Exception as e:
                            st.warning(f"無法讀取檔案 {file}: {str(e)}")
                            continue
                
                # 檢查必要欄位
                required_cols = ["縣市", "行政區", "BUILD", "平均單價元平方公尺", "交易筆數", "季度"]
                missing_cols = [col for col in required_cols if col not in df.columns]
                
                if missing_cols:
                    st.warning(f"檔案 {file} 缺少必要欄位: {missing_cols}")
                    continue
                
                dfs.append(df)
            
            if dfs:
                combined_df = pd.concat(dfs, ignore_index=True)
                st.info(f"成功載入 {len(combined_df)} 筆不動產資料")
                return combined_df
            else:
                return pd.DataFrame()
                
        except Exception as e:
            st.error(f"載入不動產資料失敗: {e}")
            return pd.DataFrame()
    
    def _load_population_data(self):
        """載入人口資料"""
        try:
            data_dir = PAGE_MODULES_FOLDER
            # 嘗試不同檔案名稱
            possible_files = ["NEWWWW.csv", "population.csv", "人口資料.csv", "人口統計.csv"]
            
            file_path = None
            for file in possible_files:
                test_path = os.path.join(data_dir, file)
                if os.path.exists(test_path):
                    file_path = test_path
                    break
            
            if not file_path:
                # 尋找包含人口相關的檔案
                all_files = os.listdir(data_dir)
                pop_files = [f for f in all_files if "人口" in f or "Population" in f.lower()]
                if pop_files:
                    file_path = os.path.join(data_dir, pop_files[0])
            
            if not file_path:
                st.warning("找不到人口資料檔案")
                return pd.DataFrame()
            
            try:
                df = pd.read_csv(file_path, encoding="utf-8")
            except:
                try:
                    df = pd.read_csv(file_path, encoding="big5")
                except:
                    df = pd.read_csv(file_path, encoding="cp950")
            
            st.info(f"成功載入人口資料，共 {len(df)} 筆記錄")
            return df
            
        except Exception as e:
            st.error(f"載入人口資料失敗: {e}")
            return pd.DataFrame()
    
    def _clean_and_preprocess_data(self):
        """清理和預處理資料"""
        # 清理不動產資料
        if "季度" in self.combined_df.columns:
            # 提取年份（假設格式為 "102年第四季"）
            self.combined_df["民國年"] = self.combined_df["季度"].str.extract(r'(\d+)年').astype(int)
            
            # 提取季度數字
            self.combined_df["季度數字"] = self.combined_df["季度"].str.extract(r'第(\d+)季').astype(int)
        
        # 轉換單價為每坪價格（1平方公尺 = 0.3025坪）
        self.combined_df["平均單價元每坪"] = self.combined_df["平均單價元平方公尺"] * 3.3058
        
        # 計算總交易金額
        self.combined_df["總交易金額萬元"] = (self.combined_df["平均單價元平方公尺"] * 
                                            self.combined_df["交易筆數"] / 10000)
        
        # 清理人口資料
        self.population_df.columns = [str(col).strip().replace("　", "").replace(" ", "") 
                                     for col in self.population_df.columns]
        
        # 確保縣市和行政區欄位
        if "縣市" not in self.population_df.columns and len(self.population_df.columns) > 0:
            self.population_df.rename(columns={self.population_df.columns[0]: "縣市"}, inplace=True)
        
        if "行政區" not in self.population_df.columns and len(self.population_df.columns) > 1:
            self.population_df.rename(columns={self.population_df.columns[1]: "行政區"}, inplace=True)
    
    def _render_home_buying_assistant(self):
        """渲染購房決策助手"""
        st.header("🏠 智慧購房決策助手")
        
        # 用戶需求調查
        with st.expander("📝 填寫您的購房需求", expanded=True):
            col1, col2, col3 = st.columns(3)
            
            with col1:
                purchase_purpose = st.selectbox(
                    "購房目的",
                    ["自住", "投資", "置產", "換屋", "首購"],
                    help="選擇您的主要購房目的"
                )
            
            with col2:
                budget = st.number_input(
                    "預算總額（萬元）",
                    min_value=100,
                    max_value=10000,
                    value=1000,
                    step=100,
                    help="您的總購房預算"
                )
            
            with col3:
                expected_size = st.number_input(
                    "期望坪數",
                    min_value=10,
                    max_value=100,
                    value=30,
                    step=5,
                    help="期望的居住坪數"
                )
            
            col4, col5, col6 = st.columns(3)
            
            with col4:
                holding_years = st.slider(
                    "預計持有年限",
                    min_value=1,
                    max_value=30,
                    value=10,
                    help="計劃持有房屋的年數"
                )
            
            with col5:
                loan_rate = st.slider(
                    "房貸利率 (%)",
                    min_value=0.0,
                    max_value=5.0,
                    value=2.0,
                    step=0.1,
                    help="預期的房貸利率"
                )
            
            with col6:
                priority = st.selectbox(
                    "優先考慮",
                    ["價格", "增值潛力", "生活機能", "學區", "交通便利"],
                    help="您最重視的因素"
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
        year_min = int(self.combined_df["民國年"].min())
        year_max = int(self.combined_df["民國年"].max())
        
        year_range = st.slider(
            "分析時間範圍",
            min_value=year_min,
            max_value=year_max,
            value=(max(year_min, year_max-5), year_max)
        )
        
        # 篩選資料
        filtered_df = self._filter_real_estate_data(
            selected_county, selected_district, year_range
        )
        
        if filtered_df.empty:
            st.warning("該條件下無符合的資料")
            return
        
        # 顯示分析結果
        self._analyze_for_home_buying(
            filtered_df, purchase_purpose, budget, 
            expected_size, holding_years, loan_rate, priority
        )
    
    def _filter_real_estate_data(self, county, district, year_range):
        """篩選不動產資料"""
        filtered_df = self.combined_df[
            (self.combined_df["民國年"] >= year_range[0]) &
            (self.combined_df["民國年"] <= year_range[1])
        ]
        
        if county != "全部縣市":
            filtered_df = filtered_df[filtered_df["縣市"] == county]
            
            if district != "全部行政區":
                filtered_df = filtered_df[filtered_df["行政區"] == district]
        
        return filtered_df
    
    def _analyze_for_home_buying(self, df, purpose, budget, size, 
                                 holding_years, loan_rate, priority):
        """分析購房需求"""
        st.subheader("📊 分析結果")
        
        # 計算關鍵指標
        metrics = self._calculate_home_buying_metrics(df, budget, size)
        
        # 顯示關鍵指標卡片
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                "🏠 平均單價",
                f"{metrics.get('avg_price_per_ping', 0):,.0f} 元/坪",
                delta=f"{metrics.get('price_change_1y', 0):+.1f}%"
            )
        
        with col2:
            affordable_ping = budget * 10000 / metrics.get('avg_price_per_ping', 1)
            st.metric(
                "💰 可負擔坪數",
                f"{affordable_ping:.1f} 坪",
                delta="您的預算"
            )
        
        with col3:
            st.metric(
                "📈 年化漲幅",
                f"{metrics.get('annual_growth', 0):.1f}%",
                delta=f"近{holding_years}年"
            )
        
        with col4:
            st.metric(
                "🏢 交易活躍度",
                f"{metrics.get('transaction_score', 0):.1f}/10",
                delta="市場熱度"
            )
        
        # 詳細分析
        tabs = st.tabs(["📈 價格趨勢", "🏘️ 產品分析", "💸 財務分析", "🎯 購買建議"])
        
        with tabs[0]:
            self._plot_price_trend_analysis(df)
        
        with tabs[1]:
            self._plot_product_analysis(df)
        
        with tabs[2]:
            self._plot_financial_analysis(df, budget, size, loan_rate, holding_years)
        
        with tabs[3]:
            self._generate_purchase_recommendations(
                metrics, purpose, budget, size, holding_years, priority
            )
    
    def _calculate_home_buying_metrics(self, df, budget, expected_size):
        """計算購房關鍵指標"""
        metrics = {}
        
        # 平均單價（每坪）
        metrics['avg_price_per_ping'] = df["平均單價元每坪"].mean()
        
        # 價格變化
        if len(df['民國年'].unique()) >= 2:
            years = sorted(df['民國年'].unique())
            recent_year = years[-1]
            prev_year = years[-2] if len(years) >= 2 else years[-1]
            
            recent_price = df[df['民國年'] == recent_year]['平均單價元每坪'].mean()
            prev_price = df[df['民國年'] == prev_year]['平均單價元每坪'].mean()
            
            if prev_price > 0:
                metrics['price_change_1y'] = ((recent_price / prev_price) - 1) * 100
        
        # 年化成長率
        if len(years) >= 2:
            first_price = df[df['民國年'] == years[0]]['平均單價元每坪'].mean()
            last_price = df[df['民國年'] == years[-1]]['平均單價元每坪'].mean()
            
            if first_price > 0 and len(years) > 1:
                period = years[-1] - years[0]
                metrics['annual_growth'] = ((last_price / first_price) ** (1/period) - 1) * 100
        
        # 交易活躍度評分
        total_transactions = df['交易筆數'].sum()
        avg_transactions = df.groupby('民國年')['交易筆數'].sum().mean()
        
        # 簡單評分系統（0-10分）
        if avg_transactions > 0:
            score = min(10, total_transactions / (avg_transactions * len(years)) * 2)
            metrics['transaction_score'] = round(score, 1)
        
        # 新成屋比例
        new_house_trans = df[df['BUILD'] == '新成屋']['交易筆數'].sum()
        total_trans = df['交易筆數'].sum()
        
        if total_trans > 0:
            metrics['new_house_ratio'] = (new_house_trans / total_trans) * 100
        
        return metrics
    
    def _plot_price_trend_analysis(self, df):
        """繪製價格趨勢分析圖"""
        # 年度平均價格趨勢
        yearly_avg = df.groupby(['民國年', 'BUILD'])['平均單價元每坪'].mean().reset_index()
        
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
        
        # 季度價格趨勢
        if '季度數字' in df.columns:
            df['季度完整'] = df['民國年'].astype(str) + 'Q' + df['季度數字'].astype(str)
            quarterly_avg = df.groupby(['季度完整', 'BUILD'])['平均單價元每坪'].mean().reset_index()
            
            fig2 = px.line(
                quarterly_avg,
                x='季度完整',
                y='平均單價元每坪',
                color='BUILD',
                title='📅 季度價格趨勢',
                markers=True
            )
            
            fig2.update_layout(
                xaxis_title="季度",
                yaxis_title="平均單價（元/坪）",
                xaxis_tickangle=45
            )
            
            st.plotly_chart(fig2, use_container_width=True)
    
    def _plot_product_analysis(self, df):
        """繪製產品分析圖"""
        # 交易量分布
        trans_by_type = df.groupby('BUILD')['交易筆數'].sum().reset_index()
        
        col1, col2 = st.columns(2)
        
        with col1:
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
            if '行政區' in df.columns:
                top_districts = df.groupby('行政區')['交易筆數'].sum().reset_index()
                top_districts = top_districts.sort_values('交易筆數', ascending=False).head(10)
                
                fig2 = px.bar(
                    top_districts,
                    y='行政區',
                    x='交易筆數',
                    title='📊 熱門行政區交易量排行',
                    orientation='h',
                    color='交易筆數'
                )
                st.plotly_chart(fig2, use_container_width=True)
    
    def _plot_financial_analysis(self, df, budget, size, loan_rate, holding_years):
        """繪製財務分析圖"""
        # 計算財務指標
        avg_price_per_ping = df['平均單價元每坪'].mean()
        total_price = avg_price_per_ping * size
        down_payment = total_price * 0.2  # 假設自備款20%
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
        annual_growth = df.groupby('民國年')['平均單價元每坪'].mean().pct_change().mean() * 100
        
        if not np.isnan(annual_growth):
            future_value = total_price * ((1 + annual_growth/100) ** holding_years)
            
            st.info(f"""
            📈 **長期投資預估**（持有 {holding_years} 年）：
            - 預估年化報酬率：{annual_growth:.1f}%
            - 未來價值預估：{future_value:,.0f} 元
            - 潛在獲利：{future_value - total_price:,.0f} 元
            """)
    
    def _generate_purchase_recommendations(self, metrics, purpose, budget, 
                                         size, holding_years, priority):
        """生成購買建議"""
        st.subheader("🎯 綜合購買建議")
        
        recommendations = []
        
        # 根據購房目的
        if purpose == "自住":
            recommendations.append("✅ **優先考慮生活機能和學區**")
            recommendations.append("✅ **選擇交通便利的地點**")
            recommendations.append("✅ **注意房屋維護狀況**")
            
        elif purpose == "投資":
            recommendations.append("✅ **關注租金收益率**")
            recommendations.append("✅ **選擇未來有發展潛力的區域**")
            recommendations.append("✅ **考慮管理成本和空置率**")
        
        # 根據預算
        affordable_ping = budget * 10000 / metrics.get('avg_price_per_ping', 1)
        
        if affordable_ping < size:
            recommendations.append("⚠️ **預算可能不足，考慮：**")
            recommendations.append("   - 縮小坪數需求")
            recommendations.append("   - 考慮周邊區域")
            recommendations.append("   - 等待更好的進場時機")
        else:
            recommendations.append("💰 **預算充足，可以：**")
            recommendations.append("   - 考慮更好的地段")
            recommendations.append("   - 選擇品質較好的建案")
            recommendations.append("   - 預留裝修預算")
        
        # 根據價格趨勢
        price_change = metrics.get('price_change_1y', 0)
        
        if price_change > 10:
            recommendations.append("📈 **市場上漲中，建議：**")
            recommendations.append("   - 盡早進場")
            recommendations.append("   - 鎖定目標物件")
        elif price_change < -5:
            recommendations.append("📉 **市場調整期，建議：**")
            recommendations.append("   - 積極看房議價")
            recommendations.append("   - 尋找被低估的物件")
        
        # 顯示建議
        for rec in recommendations:
            st.markdown(rec)
        
        # AI 建議
        gemini_key = st.session_state.get("GEMINI_KEY", "")
        if gemini_key:
            if st.button("🤖 取得 AI 專家建議", type="primary"):
                self._get_ai_recommendation(
                    metrics, purpose, budget, size, holding_years, priority
                )
    
    def _get_ai_recommendation(self, metrics, purpose, budget, size, holding_years, priority):
        """取得 AI 建議"""
        prompt = f"""
        作為不動產投資顧問，請為以下購房需求提供專業建議：
        
        購房情境：
        - 目的：{purpose}
        - 預算：{budget} 萬元
        - 期望坪數：{size} 坪
        - 持有年限：{holding_years} 年
        - 最優先考慮：{priority}
        
        市場分析：
        - 平均單價：{metrics.get('avg_price_per_ping', 0):,.0f} 元/坪
        - 近期價格變化：{metrics.get('price_change_1y', 0):+.1f}%
        - 年化成長率：{metrics.get('annual_growth', 0):.1f}%
        
        請提供：
        1. 具體的購房策略
        2. 議價技巧建議
        3. 風險控制措施
        4. 未來市場展望
        5. 行動步驟建議
        """
        
        try:
            genai.configure(api_key=st.session_state.get("GEMINI_KEY"))
            model = genai.GenerativeModel("gemini-2.0-flash")
            
            with st.spinner("🤖 AI 正在分析..."):
                response = model.generate_content(prompt)
                
                st.markdown("### 🎓 AI 專家建議")
                st.markdown("---")
                st.markdown(response.text)
                st.markdown("---")
                
        except Exception as e:
            st.error(f"AI 分析失敗: {str(e)}")
    
    def _render_price_trend_analysis(self):
        """渲染價格趨勢分析"""
        st.header("📈 價格趨勢深度分析")
        
        # 地區選擇
        col1, col2, col3 = st.columns(3)
        
        with col1:
            counties = ["全部"] + sorted(self.combined_df["縣市"].dropna().unique().tolist())
            selected_county = st.selectbox("選擇縣市", counties, key="price_county")
        
        with col2:
            if selected_county != "全部":
                districts = ["全部"] + sorted(
                    self.combined_df[self.combined_df["縣市"] == selected_county]["行政區"].dropna().unique().tolist()
                )
                selected_district = st.selectbox("選擇行政區", districts, key="price_district")
            else:
                selected_district = "全部"
        
        with col3:
            house_type = st.multiselect(
                "房屋類型",
                options=["新成屋", "中古屋"],
                default=["新成屋", "中古屋"],
                key="price_type"
            )
        
        # 時間範圍
        year_range = st.slider(
            "時間範圍",
            min_value=int(self.combined_df["民國年"].min()),
            max_value=int(self.combined_df["民國年"].max()),
            value=(int(self.combined_df["民國年"].min()), int(self.combined_df["民國年"].max())),
            key="price_year_range"
        )
        
        # 篩選資料
        filtered_df = self.combined_df[
            (self.combined_df["民國年"] >= year_range[0]) &
            (self.combined_df["民國年"] <= year_range[1])
        ]
        
        if selected_county != "全部":
            filtered_df = filtered_df[filtered_df["縣市"] == selected_county]
        
        if selected_district != "全部":
            filtered_df = filtered_df[filtered_df["行政區"] == selected_district]
        
        if house_type:
            filtered_df = filtered_df[filtered_df["BUILD"].isin(house_type)]
        
        if filtered_df.empty:
            st.warning("該條件下無資料")
            return
        
        # 分析標籤頁
        tab1, tab2, tab3, tab4 = st.tabs(["趨勢圖", "比較分析", "統計指標", "預測模型"])
        
        with tab1:
            self._plot_comprehensive_trends(filtered_df)
        
        with tab2:
            self._plot_comparative_analysis(filtered_df)
        
        with tab3:
            self._show_statistical_indicators(filtered_df)
        
        with tab3:
            self._show_market_prediction(filtered_df)
    
    def _plot_comprehensive_trends(self, df):
        """繪製綜合趨勢圖"""
        # 使用 Plotly 繪製互動圖表
        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=('價格趨勢', '交易量趨勢', '價格分布', '累計交易金額'),
            vertical_spacing=0.15,
            horizontal_spacing=0.1
        )
        
        # 1. 價格趨勢（線圖）
        price_trend = df.groupby(['民國年', 'BUILD'])['平均單價元每坪'].mean().reset_index()
        
        for build_type in price_trend['BUILD'].unique():
            build_data = price_trend[price_trend['BUILD'] == build_type]
            fig.add_trace(
                go.Scatter(
                    x=build_data['民國年'],
                    y=build_data['平均單價元每坪'],
                    name=build_type,
                    mode='lines+markers'
                ),
                row=1, col=1
            )
        
        # 2. 交易量趨勢（柱狀圖）
        volume_trend = df.groupby(['民國年', 'BUILD'])['交易筆數'].sum().reset_index()
        
        for build_type in volume_trend['BUILD'].unique():
            build_data = volume_trend[volume_trend['BUILD'] == build_type]
            fig.add_trace(
                go.Bar(
                    x=build_data['民國年'],
                    y=build_data['交易筆數'],
                    name=f"{build_type}交易量",
                    opacity=0.7
                ),
                row=1, col=2
            )
        
        # 3. 價格分布（盒鬚圖）
        for i, build_type in enumerate(df['BUILD'].unique()):
            build_data = df[df['BUILD'] == build_type]
            fig.add_trace(
                go.Box(
                    y=build_data['平均單價元每坪'],
                    name=build_type,
                    boxpoints='outliers'
                ),
                row=2, col=1
            )
        
        # 4. 累計交易金額（面積圖）
        cumulative_sales = df.groupby('民國年')['總交易金額萬元'].sum().cumsum().reset_index()
        fig.add_trace(
            go.Scatter(
                x=cumulative_sales['民國年'],
                y=cumulative_sales['總交易金額萬元'],
                fill='tozeroy',
                name='累計交易金額',
                mode='lines'
            ),
            row=2, col=2
        )
        
        fig.update_layout(height=800, showlegend=True, title_text="綜合趨勢分析")
        st.plotly_chart(fig, use_container_width=True)
    
    def _plot_comparative_analysis(self, df):
        """繪製比較分析圖"""
        # 地區比較
        if '行政區' in df.columns and len(df['行政區'].unique()) > 1:
            st.subheader("地區比較分析")
            
            # 選擇比較的行政區
            districts = st.multiselect(
                "選擇比較的行政區",
                options=sorted(df['行政區'].unique()),
                default=sorted(df['行政區'].unique())[:3]
            )
            
            if districts:
                compare_df = df[df['行政區'].isin(districts)]
                
                # 價格比較
                price_comparison = compare_df.groupby(['行政區', 'BUILD'])['平均單價元每坪'].mean().reset_index()
                
                fig = px.bar(
                    price_comparison,
                    x='行政區',
                    y='平均單價元每坪',
                    color='BUILD',
                    barmode='group',
                    title='各行政區價格比較',
                    text_auto='.0f'
                )
                
                st.plotly_chart(fig, use_container_width=True)
                
                # 交易量比較
                volume_comparison = compare_df.groupby(['行政區', 'BUILD'])['交易筆數'].sum().reset_index()
                
                fig2 = px.bar(
                    volume_comparison,
                    x='行政區',
                    y='交易筆數',
                    color='BUILD',
                    barmode='stack',
                    title='各行政區交易量比較',
                    text_auto='.0f'
                )
                
                st.plotly_chart(fig2, use_container_width=True)
    
    def _show_statistical_indicators(self, df):
        """顯示統計指標"""
        st.subheader("📊 統計分析報告")
        
        # 基本統計
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### 價格統計")
            price_stats = df['平均單價元每坪'].describe()
            
            stats_df = pd.DataFrame({
                '指標': ['平均', '中位數', '標準差', '最小值', '25%分位', '75%分位', '最大值'],
                '數值': [
                    price_stats['mean'],
                    price_stats['50%'],
                    price_stats['std'],
                    price_stats['min'],
                    price_stats['25%'],
                    price_stats['75%'],
                    price_stats['max']
                ]
            })
            
            st.dataframe(
                stats_df.style.format({'數值': '{:,.0f}'}),
                use_container_width=True
            )
        
        with col2:
            st.markdown("#### 交易量統計")
            volume_stats = df['交易筆數'].describe()
            
            vol_df = pd.DataFrame({
                '指標': ['總交易筆數', '平均每筆', '最大交易量', '最小交易量'],
                '數值': [
                    df['交易筆數'].sum(),
                    volume_stats['mean'],
                    volume_stats['max'],
                    volume_stats['min']
                ]
            })
            
            st.dataframe(
                vol_df.style.format({'數值': '{:,.0f}'}),
                use_container_width=True
            )
        
        # 年度變化率
        st.markdown("#### 📈 年度變化率")
        
        yearly_data = df.groupby('民國年').agg({
            '平均單價元每坪': 'mean',
            '交易筆數': 'sum'
        }).reset_index()
        
        yearly_data['價格年增率'] = yearly_data['平均單價元每坪'].pct_change() * 100
        yearly_data['交易量年增率'] = yearly_data['交易筆數'].pct_change() * 100
        
        st.dataframe(
            yearly_data.style.format({
                '平均單價元每坪': '{:,.0f}',
                '交易筆數': '{:,.0f}',
                '價格年增率': '{:.2f}%',
                '交易量年增率': '{:.2f}%'
            }),
            use_container_width=True
        )
    
    def _show_market_prediction(self, df):
        """顯示市場預測"""
        st.subheader("🔮 市場趨勢預測")
        
        # 簡單線性預測
        yearly_avg = df.groupby('民國年')['平均單價元每坪'].mean().reset_index()
        
        if len(yearly_avg) >= 3:
            # 使用簡單線性回歸預測未來3年
            x = yearly_avg['民國年'].values
            y = yearly_avg['平均單價元每坪'].values
            
            # 線性回歸
            z = np.polyfit(x, y, 1)
            p = np.poly1d(z)
            
            # 預測未來3年
            future_years = list(range(x[-1] + 1, x[-1] + 4))
            predictions = p(future_years)
            
            # 建立預測數據框
            prediction_df = pd.DataFrame({
                '年份': future_years,
                '預測單價': predictions,
                '年增率': np.insert(np.diff(predictions) / predictions[:-1] * 100, 0, np.nan)
            })
            
            st.info("### 📊 未來三年價格預測")
            st.dataframe(
                prediction_df.style.format({
                    '預測單價': '{:,.0f}',
                    '年增率': '{:.1f}%'
                }),
                use_container_width=True
            )
            
            # 繪製預測圖
            fig = go.Figure()
            
            # 實際數據
            fig.add_trace(go.Scatter(
                x=yearly_avg['民國年'],
                y=yearly_avg['平均單價元每坪'],
                mode='lines+markers',
                name='歷史數據',
                line=dict(color='blue', width=2)
            ))
            
            # 預測數據
            fig.add_trace(go.Scatter(
                x=future_years,
                y=predictions,
                mode='lines+markers',
                name='預測數據',
                line=dict(color='red', width=2, dash='dash')
            ))
            
            fig.update_layout(
                title='價格趨勢預測',
                xaxis_title='年份',
                yaxis_title='平均單價（元/坪）',
                hovermode='x unified'
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            # 風險提示
            st.warning("""
            ⚠️ **風險提示**：
            1. 此預測基於歷史數據的簡單線性模型
            2. 實際市場受多種因素影響（政策、經濟、供需等）
            3. 投資決策應綜合多方資訊
            4. 過去表現不代表未來結果
            """)
    
    def _render_region_comparison(self):
        """渲染區域比較分析"""
        st.header("🏙️ 區域比較分析")
        
        # 選擇比較地區
        st.subheader("選擇比較地區")
        
        col1, col2 = st.columns(2)
        
        with col1:
            counties = sorted(self.combined_df["縣市"].dropna().unique().tolist())
            selected_counties = st.multiselect(
                "選擇比較縣市",
                options=counties,
                default=counties[:3] if len(counties) >= 3 else counties
            )
        
        with col2:
            house_types = st.multiselect(
                "房屋類型",
                options=["新成屋", "中古屋"],
                default=["新成屋", "中古屋"]
            )
        
        # 時間範圍
        year_range = st.slider(
            "比較時間範圍",
            min_value=int(self.combined_df["民國年"].min()),
            max_value=int(self.combined_df["民國年"].max()),
            value=(int(self.combined_df["民國年"].max()) - 5, int(self.combined_df["民國年"].max()))
        )
        
        if not selected_counties:
            st.warning("請選擇至少一個縣市進行比較")
            return
        
        # 篩選資料
        filtered_df = self.combined_df[
            (self.combined_df["縣市"].isin(selected_counties)) &
            (self.combined_df["民國年"] >= year_range[0]) &
            (self.combined_df["民國年"] <= year_range[1])
        ]
        
        if house_types:
            filtered_df = filtered_df[filtered_df["BUILD"].isin(house_types)]
        
        if filtered_df.empty:
            st.warning("該條件下無資料")
            return
        
        # 比較分析
        tabs = st.tabs(["價格比較", "交易量比較", "成長性比較", "綜合評比"])
        
        with tabs[0]:
            self._plot_region_price_comparison(filtered_df, selected_counties)
        
        with tabs[1]:
            self._plot_region_volume_comparison(filtered_df, selected_counties)
        
        with tabs[2]:
            self._plot_region_growth_comparison(filtered_df, selected_counties)
        
        with tabs[3]:
            self._show_region_comprehensive_rating(filtered_df, selected_counties)
    
    def _plot_region_price_comparison(self, df, counties):
        """繪製區域價格比較圖"""
        # 年度平均價格比較
        yearly_price = df.groupby(['縣市', '民國年'])['平均單價元每坪'].mean().reset_index()
        
        fig = px.line(
            yearly_price,
            x='民國年',
            y='平均單價元每坪',
            color='縣市',
            title='🏙️ 各縣市價格趨勢比較',
            markers=True
        )
        
        fig.update_layout(
            xaxis_title="年份",
            yaxis_title="平均單價（元/坪）",
            hovermode="x unified"
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # 最新年度價格比較
        latest_year = df['民國年'].max()
        latest_prices = df[df['民國年'] == latest_year].groupby('縣市')['平均單價元每坪'].mean().reset_index()
        
        fig2 = px.bar(
            latest_prices.sort_values('平均單價元每坪', ascending=False),
            x='縣市',
            y='平均單價元每坪',
            title=f'📊 {latest_year}年各縣市價格比較',
            color='平均單價元每坪',
            text_auto='.0f'
        )
        
        fig2.update_layout(xaxis_tickangle=45)
        st.plotly_chart(fig2, use_container_width=True)
    
    def _plot_region_volume_comparison(self, df, counties):
        """繪製區域交易量比較圖"""
        # 年度交易量比較
        yearly_volume = df.groupby(['縣市', '民國年'])['交易筆數'].sum().reset_index()
        
        fig = px.bar(
            yearly_volume,
            x='民國年',
            y='交易筆數',
            color='縣市',
            title='📊 各縣市交易量比較',
            barmode='group'
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # 交易量占比分析
        total_volume = yearly_volume.groupby('縣市')['交易筆數'].sum().reset_index()
        
        fig2 = px.pie(
            total_volume,
            values='交易筆數',
            names='縣市',
            title='🎯 各縣市交易量占比',
            hole=0.4
        )
        
        st.plotly_chart(fig2, use_container_width=True)
    
    def _plot_region_growth_comparison(self, df, counties):
        """繪製區域成長性比較圖"""
        # 計算各縣市成長率
        growth_data = []
        
        for county in counties:
            county_data = df[df['縣市'] == county]
            
            if len(country_data['民國年'].unique()) >= 2:
                years = sorted(county_data['民國年'].unique())
                first_year = years[0]
                last_year = years[-1]
                
                first_price = county_data[county_data['民國年'] == first_year]['平均單價元每坪'].mean()
                last_price = county_data[county_data['民國年'] == last_year]['平均單價元每坪'].mean()
                
                if first_price > 0:
                    period = last_year - first_year
                    annual_growth = ((last_price / first_price) ** (1/period) - 1) * 100
                    
                    growth_data.append({
                        '縣市': county,
                        '起始年份': first_year,
                        '結束年份': last_year,
                        '起始價格': first_price,
                        '結束價格': last_price,
                        '年化成長率': annual_growth
                    })
        
        if growth_data:
            growth_df = pd.DataFrame(growth_data)
            
            fig = px.bar(
                growth_df.sort_values('年化成長率', ascending=False),
                x='縣市',
                y='年化成長率',
                title='📈 各縣市年化成長率比較',
                color='年化成長率',
                text_auto='.1f'
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            # 顯示詳細數據
            st.dataframe(
                growth_df.style.format({
                    '起始價格': '{:,.0f}',
                    '結束價格': '{:,.0f}',
                    '年化成長率': '{:.2f}%'
                }),
                use_container_width=True
            )
    
    def _show_region_comprehensive_rating(self, df, counties):
        """顯示區域綜合評比"""
        st.subheader("🏆 區域綜合評比")
        
        # 計算評分指標
        rating_data = []
        
        for county in counties:
            county_data = df[df['縣市'] == county]
            
            if not county_data.empty:
                # 價格穩定性（價格波動率）
                price_std = county_data.groupby('民國年')['平均單價元每坪'].mean().std()
                price_mean = county_data.groupby('民國年')['平均單價元每坪'].mean().mean()
                price_stability = (1 - price_std / price_mean) * 100 if price_mean > 0 else 0
                
                # 交易活躍度
                total_volume = county_data['交易筆數'].sum()
                avg_volume = county_data.groupby('民國年')['交易筆數'].sum().mean()
                
                # 成長性
                years = sorted(county_data['民國年'].unique())
                if len(years) >= 2:
                    first_price = county_data[county_data['民國年'] == years[0]]['平均單價元每坪'].mean()
                    last_price = county_data[county_data['民國年'] == years[-1]]['平均單價元每坪'].mean()
                    if first_price > 0:
                        growth_rate = ((last_price / first_price) ** (1/(years[-1]-years[0])) - 1) * 100
                    else:
                        growth_rate = 0
                else:
                    growth_rate = 0
                
                # 綜合評分（0-100）
                stability_score = min(25, max(0, price_stability))
                volume_score = min(25, total_volume / 1000)
                growth_score = min(25, max(0, growth_rate * 2))
                
                total_score = stability_score + volume_score + growth_score
                
                rating_data.append({
                    '縣市': county,
                    '價格穩定性': f"{price_stability:.1f}%",
                    '交易活躍度': f"{total_volume:,.0f}筆",
                    '年化成長率': f"{growth_rate:.2f}%",
                    '綜合評分': round(total_score, 1)
                })
        
        if rating_data:
            rating_df = pd.DataFrame(rating_data)
            rating_df = rating_df.sort_values('綜合評分', ascending=False)
            
            # 顯示評分表
            st.dataframe(
                rating_df.style.background_gradient(
                    subset=['綜合評分'], 
                    cmap='RdYlGn'
                ).format({
                    '綜合評分': '{:.1f}'
                }),
                use_container_width=True
            )
            
            # 評分說明
            st.info("""
            **評分標準說明**：
            - **價格穩定性**：價格波動越小，分數越高（最高25分）
            - **交易活躍度**：交易量越大，市場越活躍（最高25分）
            - **年化成長率**：成長率越高，分數越高（最高25分）
            - **綜合評分**：總分越高表示綜合表現越好
            """)
    
    def _render_population_housing_relationship(self):
        """渲染人口與房價關係分析"""
        st.header("👥 人口與房價關係分析")
        
        # 檢查是否有人口資料
        if self.population_df.empty:
            st.warning("無人口資料可供分析")
            return
        
        # 選擇分析地區
        col1, col2 = st.columns(2)
        
        with col1:
            counties = ["全部"] + sorted(self.combined_df["縣市"].dropna().unique().tolist())
            selected_county = st.selectbox("選擇縣市", counties, key="pop_county")
        
        with col2:
            analysis_type = st.selectbox(
                "分析類型",
                ["人口變化 vs 房價變化", "人口密度 vs 房價", "人口結構 vs 市場需求"],
                key="pop_analysis_type"
            )
        
        # 準備人口資料（長格式）
        pop_long = self._prepare_population_long_format()
        
        if pop_long.empty:
            st.warning("無法處理人口資料格式")
            return
        
        # 篩選地區
        if selected_county != "全部":
            real_estate_data = self.combined_df[self.combined_df["縣市"] == selected_county]
            pop_data = pop_long[pop_long["縣市"] == selected_county]
        else:
            real_estate_data = self.combined_df
            pop_data = pop_long[pop_long["縣市"] == pop_long["行政區"]]  # 縣市層級資料
        
        # 分析
        if analysis_type == "人口變化 vs 房價變化":
            self._analyze_population_price_relationship(real_estate_data, pop_data)
        elif analysis_type == "人口密度 vs 房價":
            self._analyze_population_density_price(real_estate_data, pop_data)
    
    def _prepare_population_long_format(self):
        """準備人口資料（長格式）"""
        try:
            # 找出包含年份的欄位
            year_columns = [col for col in self.population_df.columns 
                          if any(str(year) in col for year in range(100, 115))]
            
            if not year_columns:
                # 嘗試其他識別方式
                year_columns = [col for col in self.population_df.columns 
                              if "年" in str(col)]
            
            if not year_columns:
                st.warning("無法識別人口資料中的年份欄位")
                return pd.DataFrame()
            
            # 轉換為長格式
            id_vars = ["縣市", "行政區"] if "行政區" in self.population_df.columns else ["縣市"]
            pop_long = self.population_df.melt(
                id_vars=id_vars,
                value_vars=year_columns,
                var_name="年度",
                value_name="人口數"
            )
            
            # 清理人口數
            pop_long["人口數"] = pd.to_numeric(
                pop_long["人口數"].astype(str).str.replace(",", "").str.replace(" ", ""),
                errors='coerce'
            )
            
            # 提取年份
            pop_long["年度"] = pop_long["年度"].astype(str).str.extract(r'(\d+)').astype(int)
            
            return pop_long
            
        except Exception as e:
            st.error(f"處理人口資料失敗: {str(e)}")
            return pd.DataFrame()
    
    def _analyze_population_price_relationship(self, re_df, pop_df):
        """分析人口變化與房價關係"""
        # 按年度彙總
        yearly_price = re_df.groupby('民國年')['平均單價元每坪'].mean().reset_index()
        yearly_pop = pop_df.groupby('年度')['人口數'].mean().reset_index()
        
        # 合併資料
        merged_df = pd.merge(
            yearly_price, 
            yearly_pop, 
            left_on='民國年', 
            right_on='年度',
            how='inner'
        )
        
        if merged_df.empty:
            st.warning("無共同的年份資料")
            return
        
        # 計算變化率
        merged_df['房價變化率'] = merged_df['平均單價元每坪'].pct_change() * 100
        merged_df['人口變化率'] = merged_df['人口數'].pct_change() * 100
        
        # 繪製雙軸圖
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        
        # 房價趨勢
        fig.add_trace(
            go.Scatter(
                x=merged_df['民國年'],
                y=merged_df['平均單價元每坪'],
                name='平均單價',
                mode='lines+markers',
                line=dict(color='blue')
            ),
            secondary_y=False
        )
        
        # 人口趨勢
        fig.add_trace(
            go.Scatter(
                x=merged_df['民國年'],
                y=merged_df['人口數'],
                name='人口數',
                mode='lines+markers',
                line=dict(color='green')
            ),
            secondary_y=True
        )
        
        fig.update_layout(
            title='📈 房價與人口趨勢',
            xaxis_title='年份',
            hovermode='x unified'
        )
        
        fig.update_yaxes(title_text="平均單價（元/坪）", secondary_y=False)
        fig.update_yaxes(title_text="人口數", secondary_y=True)
        
        st.plotly_chart(fig, use_container_width=True)
        
        # 相關係數分析
        valid_data = merged_df[['房價變化率', '人口變化率']].dropna()
        
        if len(valid_data) >= 2:
            correlation = valid_data['房價變化率'].corr(valid_data['人口變化率'])
            
            st.metric(
                "🔗 相關係數",
                f"{correlation:.3f}",
                delta="正相關" if correlation > 0 else "負相關"
            )
            
            # 解釋相關係數
            if correlation > 0.7:
                st.success("✅ 強烈正相關：人口增加伴隨房價上漲")
            elif correlation > 0.3:
                st.info("📊 中度正相關：人口與房價有一定關聯")
            elif correlation > -0.3:
                st.warning("⚖️ 弱相關：人口變化與房價關係不明顯")
            elif correlation > -0.7:
                st.info("📉 中度負相關：人口減少但房價上漲")
            else:
                st.error("⚠️ 強烈負相關：需進一步分析原因")
    
    def _render_raw_data_view(self):
        """渲染原始資料檢視"""
        st.header("📋 原始資料檢視")
        
        # 資料選擇
        data_type = st.radio(
            "選擇資料類型",
            ["不動產資料", "人口資料"],
            horizontal=True
        )
        
        if data_type == "不動產資料":
            df = self.combined_df
            st.info(f"不動產資料：共 {len(df)} 筆記錄")
        else:
            df = self.population_df
            st.info(f"人口資料：共 {len(df)} 筆記錄")
        
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
        
        if selected_county != "全部":
            filtered_df = filtered_df[filtered_df['縣市'] == selected_county]
        
        if selected_district != "全部":
            filtered_df = filtered_df[filtered_df['行政區'] == selected_district]
        
        if selected_type != "全部":
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
            st.write(filtered_df.describe())
            
            st.write("**欄位資訊：**")
            col_info = pd.DataFrame({
                '欄位名稱': filtered_df.columns,
                '非空值數': filtered_df.notnull().sum().values,
                '空值數': filtered_df.isnull().sum().values,
                '資料類型': filtered_df.dtypes.values
            })
            st.dataframe(col_info, use_container_width=True)
        
        # 匯出選項
        col1, col2, col3 = st.columns(3)
        
        with col2:
            if st.button("💾 匯出篩選結果", use_container_width=True):
                csv = filtered_df.to_csv(index=False).encode('utf-8-sig')
                st.download_button(
                    label="📥 下載 CSV",
                    data=csv,
                    file_name=f"不動產資料_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv",
                    use_container_width=True
                )

# 主程式入口
def main():
    """主程式"""
    analyzer = CompleteMarketTrendAnalyzer()
    analyzer.render_complete_dashboard()

if __name__ == "__main__":
    main()
