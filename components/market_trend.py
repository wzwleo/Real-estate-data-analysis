# components/market_trend_enhanced.py - 購房決策強化版
import streamlit as st
import pandas as pd
import numpy as np
import os
import sys
import time
from datetime import datetime
from streamlit_echarts import st_echarts
import google.generativeai as genai

# 修正匯入路徑
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

try:
    from config import PAGE_MODULES_FOLDER
    from analysis.gemini_analysis import prepare_market_analysis_prompt
    CONFIG_LOADED = True
except ImportError as e:
    CONFIG_LOADED = False
    st.warning(f"無法載入設定或模組: {e}")


class EnhancedMarketTrendAnalyzer:
    """市場趨勢分析器 - 購房決策強化版"""
    
    def __init__(self):
        self.combined_df = None
        self.population_df = None
        
    def render_analysis_tab(self):
        """渲染市場趨勢分析頁面 - 購房決策強化"""
        st.title("🏠 購房市場分析儀表板")
        
        # 初始化 session state
        if 'market_analysis_result' not in st.session_state:
            st.session_state.market_analysis_result = None
        if 'market_analysis_key' not in st.session_state:
            st.session_state.market_analysis_key = None
        
        # 購房情境選擇
        st.subheader("🔍 您的購房情境")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            purchase_purpose = st.selectbox(
                "購房目的",
                ["自住", "投資", "置產", "換屋"],
                key="purchase_purpose",
                help="選擇主要購房目的"
            )
        
        with col2:
            budget_range = st.selectbox(
                "預算範圍(坪)",
                ["< 500萬", "500-1000萬", "1000-2000萬", "2000-5000萬", "> 5000萬"],
                key="budget_range"
            )
        
        with col3:
            holding_period = st.selectbox(
                "持有年限",
                ["< 3年", "3-5年", "5-10年", "> 10年"],
                key="holding_period"
            )
        
        # 載入資料
        self.combined_df = self._load_real_estate_data()
        self.population_df = self._load_population_data()
        
        if self.combined_df.empty or self.population_df.empty:
            st.info("📂 找不到房產或人口資料")
            return
        
        # 基本清理
        self._clean_data()
        
        # 人口資料轉長格式
        pop_long = self._prepare_population_data()
        
        # 地區選擇
        st.subheader("📍 選擇分析地區")
        selected_area = self._render_area_selection(pop_long)
        
        if not selected_area:
            return
        
        city_choice, district_choice, year_range = selected_area
        
        # 篩選資料
        re_df, pop_df = self._filter_data(city_choice, district_choice, year_range, pop_long)
        
        # 顯示關鍵指標儀表板
        self._display_key_metrics(re_df, pop_df, purchase_purpose)
        
        # 分析模組選擇
        analysis_modules = self._get_analysis_modules(purchase_purpose)
        
        selected_module = st.selectbox(
            "選擇分析模組",
            analysis_modules,
            key="selected_module"
        )
        
        # 執行對應的分析
        if selected_module:
            self._execute_analysis_module(
                selected_module, 
                re_df, 
                pop_df, 
                city_choice, 
                district_choice, 
                year_range,
                purchase_purpose,
                budget_range,
                holding_period
            )
    
    def _get_analysis_modules(self, purchase_purpose):
        """根據購房目的返回分析模組"""
        modules = {
            "自住": [
                "📊 可負擔性分析",
                "🏘️ 居住品質評估",
                "📈 房價趨勢與增值潛力",
                "🚇 交通便利性分析",
                "🎓 學區與生活機能"
            ],
            "投資": [
                "💰 投資報酬率分析",
                "📉 市場風險評估",
                "🏢 租金收益率分析",
                "📊 供需關係分析",
                "⏳ 最佳進場時機"
            ],
            "置產": [
                "📈 長期增值潛力",
                "🏛️ 區域發展潛力",
                "🛡️ 資產保值性",
                "🌳 環境與生活品質",
                "📋 稅務與持有成本"
            ],
            "換屋": [
                "🔄 換屋成本效益",
                "📈 舊屋增值評估",
                "🏠 新舊屋價差分析",
                "📍 升級區域選擇",
                "⏰ 換屋時機建議"
            ]
        }
        return modules.get(purchase_purpose, modules["自住"])
    
    def _display_key_metrics(self, re_df, pop_df, purchase_purpose):
        """顯示關鍵指標儀表板"""
        st.subheader("📊 市場關鍵指標")
        
        if re_df.empty:
            st.warning("無有效資料")
            return
        
        # 計算關鍵指標
        metrics = self._calculate_key_metrics(re_df, pop_df)
        
        # 顯示指標卡片
        cols = st.columns(4)
        
        with cols[0]:
            st.metric(
                label="📈 年均房價漲幅",
                value=f"{metrics.get('avg_price_growth', 0):.1f}%",
                delta=f"{metrics.get('recent_growth', 0):.1f}% (最近一年)"
            )
        
        with cols[1]:
            st.metric(
                label="🏘️ 新成屋佔比",
                value=f"{metrics.get('new_house_ratio', 0):.1f}%",
                delta="較高表示供給充足" if metrics.get('new_house_ratio', 0) > 30 else "較低表示市場成熟"
            )
        
        with cols[2]:
            st.metric(
                label="📊 成交量能",
                value=f"{metrics.get('transaction_volume', 0):,.0f}筆",
                delta=f"{metrics.get('volume_change', 0):.1f}% (變化)"
            )
        
        with cols[3]:
            st.metric(
                label="👥 人口變化",
                value=f"{metrics.get('population_change', 0):.1f}%",
                delta="正成長利於房市" if metrics.get('population_change', 0) > 0 else "需注意"
            )
        
        # 購房建議摘要
        self._display_purchase_advice(metrics, purchase_purpose)
    
    def _calculate_key_metrics(self, re_df, pop_df):
        """計算關鍵市場指標"""
        metrics = {}
        
        # 房價漲幅計算
        if not re_df.empty:
            # 年均漲幅
            yearly_avg = re_df.groupby('民國年')['平均單價元平方公尺'].mean().reset_index()
            if len(yearly_avg) > 1:
                metrics['avg_price_growth'] = ((yearly_avg['平均單價元平方公尺'].iloc[-1] / 
                                            yearly_avg['平均單價元平方公尺'].iloc[0]) ** 
                                           (1/len(yearly_avg)) - 1) * 100
            
            # 最近一年漲幅
            if len(yearly_avg) >= 2:
                metrics['recent_growth'] = ((yearly_avg['平均單價元平方公尺'].iloc[-1] / 
                                         yearly_avg['平均單價元平方公尺'].iloc[-2]) - 1) * 100
            
            # 新成屋比例
            total_trans = re_df['交易筆數'].sum()
            new_house_trans = re_df[re_df['BUILD'] == '新成屋']['交易筆數'].sum()
            metrics['new_house_ratio'] = (new_house_trans / total_trans * 100) if total_trans > 0 else 0
            
            # 交易量能
            metrics['transaction_volume'] = total_trans
            if len(yearly_avg) >= 2:
                volume_yearly = re_df.groupby('民國年')['交易筆數'].sum()
                metrics['volume_change'] = ((volume_yearly.iloc[-1] / volume_yearly.iloc[0]) - 1) * 100
        
        # 人口變化
        if not pop_df.empty and '人口數' in pop_df.columns:
            pop_by_year = pop_df.groupby('民國年')['人口數'].mean().reset_index()
            if len(pop_by_year) > 1:
                metrics['population_change'] = ((pop_by_year['人口數'].iloc[-1] / 
                                              pop_by_year['人口數'].iloc[0]) - 1) * 100
        
        return metrics
    
    def _display_purchase_advice(self, metrics, purchase_purpose):
        """顯示購房建議摘要"""
        st.subheader("💡 購房建議摘要")
        
        advice = ""
        
        # 根據指標提供建議
        growth = metrics.get('avg_price_growth', 0)
        volume_change = metrics.get('volume_change', 0)
        new_ratio = metrics.get('new_house_ratio', 0)
        
        if purchase_purpose == "自住":
            if growth > 10:
                advice = "⚠️ 市場過熱，建議謹慎觀望或考慮周邊區域"
            elif growth < 0:
                advice = "💰 市場調整期，可積極看房議價"
            else:
                advice = "✅ 市場穩定，適合進場"
                
        elif purchase_purpose == "投資":
            if volume_change > 20 and growth > 8:
                advice = "📈 熱門投資區域，但需注意風險"
            elif volume_change < 0 and growth < 3:
                advice = "💤 市場冷清，建議觀望"
            else:
                advice = "⚖️ 市場平衡，可選擇性投資"
        
        # 顯示建議卡片
        if advice:
            with st.container():
                st.info(advice)
                
                # 評分系統
                score = self._calculate_market_score(metrics, purchase_purpose)
                col1, col2, col3 = st.columns([1, 2, 1])
                with col2:
                    st.progress(score/100, text=f"市場適宜度評分: {score}/100")
    
    def _calculate_market_score(self, metrics, purpose):
        """計算市場適宜度評分"""
        score = 50  # 基礎分
        
        # 根據不同目的調整評分
        if purpose == "自住":
            # 自住重視穩定性和可負擔性
            growth = metrics.get('avg_price_growth', 0)
            if 3 <= growth <= 8:
                score += 20
            elif growth > 15:
                score -= 15
            
            volume_change = metrics.get('volume_change', 0)
            if volume_change > 0:
                score += 10
        
        elif purpose == "投資":
            # 投資重視成長性和交易活躍度
            growth = metrics.get('avg_price_growth', 0)
            if growth > 8:
                score += 25
            elif growth < 0:
                score -= 15
            
            volume_change = metrics.get('volume_change', 0)
            if volume_change > 15:
                score += 15
        
        return max(0, min(100, score))
    
    def _execute_analysis_module(self, module, re_df, pop_df, city_choice, district_choice, 
                               year_range, purchase_purpose, budget_range, holding_period):
        """執行分析模組"""
        
        if module == "📊 可負擔性分析":
            self._analyze_affordability(re_df, pop_df, budget_range)
        
        elif module == "📈 房價趨勢與增值潛力":
            self._analyze_price_trend_enhanced(re_df, pop_df, holding_period)
        
        elif module == "💰 投資報酬率分析":
            self._analyze_investment_return(re_df, pop_df)
        
        elif module == "📉 市場風險評估":
            self._analyze_market_risk(re_df, pop_df)
        
        elif module == "🔄 換屋成本效益":
            self._analyze_move_house_cost(re_df, pop_df)
        
        # 其他模組的實現...
        
        # AI 綜合分析
        self._render_ai_comprehensive_analysis(
            module, re_df, pop_df, city_choice, district_choice,
            purchase_purpose, budget_range, holding_period
        )
    
    def _analyze_affordability(self, re_df, pop_df, budget_range):
        """分析可負擔性"""
        st.subheader("💰 可負擔性分析")
        
        # 轉換預算範圍
        budget_map = {
            "< 500萬": 5000000,
            "500-1000萬": 7500000,
            "1000-2000萬": 15000000,
            "2000-5000萬": 35000000,
            "> 5000萬": 50000000
        }
        budget = budget_map.get(budget_range, 15000000)
        
        # 計算可負擔的坪數
        if not re_df.empty:
            avg_price_per_ping = re_df['平均單價元平方公尺'].mean() * 3.3058  # 轉換為每坪
            
            affordable_ping = budget / avg_price_per_ping
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric(
                    "🏠 預算",
                    f"{budget/10000:,.0f} 萬元"
                )
            
            with col2:
                st.metric(
                    "📏 平均單價",
                    f"{avg_price_per_ping:,.0f} 元/坪"
                )
            
            with col3:
                st.metric(
                    "📐 可負擔坪數",
                    f"{affordable_ping:.1f} 坪"
                )
            
            # 與歷史比較
            st.markdown("### 📈 負擔能力歷史變化")
            
            # 計算各年可負擔坪數
            yearly_price = re_df.groupby('民國年')['平均單價元平方公尺'].mean().reset_index()
            yearly_price['每坪價格'] = yearly_price['平均單價元平方公尺'] * 3.3058
            yearly_price['可負擔坪數'] = budget / yearly_price['每坪價格']
            
            # 顯示圖表
            st_echarts({
                "tooltip": {"trigger": "axis"},
                "xAxis": {"type": "category", "data": yearly_price['民國年'].astype(str).tolist()},
                "yAxis": [{"type": "value", "name": "可負擔坪數"}],
                "series": [{"name": "可負擔坪數", "type": "line", "data": yearly_price['可負擔坪數'].round(1).tolist()}]
            }, height="300px")
            
            # 提供建議
            recent_ping = yearly_price['可負擔坪數'].iloc[-1] if len(yearly_price) > 0 else 0
            if recent_ping < 20:
                st.warning("⚠️ 當前可負擔坪數較小，建議：")
                st.markdown("""
                - 考慮周邊價格較低區域
                - 選擇坪數較小的物件
                - 等待市場調整時機
                """)
            elif recent_ping > 40:
                st.success("✅ 負擔能力充足，可考慮：")
                st.markdown("""
                - 選擇核心區域物件
                - 挑選品質較好的建案
                - 預留裝修預算
                """)
    
    def _analyze_price_trend_enhanced(self, re_df, pop_df, holding_period):
        """強化版房價趨勢分析"""
        st.subheader("📈 房價趨勢與增值潛力分析")
        
        if re_df.empty:
            return
        
        # 價格趨勢分析
        price_df = re_df.groupby(['民國年', 'BUILD'])['平均單價元平方公尺'].mean().reset_index()
        
        # 預測未來趨勢（簡單線性回歸）
        years = sorted(price_df['民國年'].unique())
        recent_years = years[-5:] if len(years) >= 5 else years
        
        # 計算不同持有年限的預期報酬
        holding_years_map = {
            "< 3年": 2,
            "3-5年": 4,
            "5-10年": 7,
            "> 10年": 12
        }
        holding_years = holding_years_map.get(holding_period, 5)
        
        # 計算歷史年化報酬率
        if len(years) >= 2:
            first_price = price_df[price_df['民國年'] == years[0]]['平均單價元平方公尺'].mean()
            last_price = price_df[price_df['民國年'] == years[-1]]['平均單價元平方公尺'].mean()
            
            total_period = years[-1] - years[0]
            if total_period > 0:
                cagr = ((last_price / first_price) ** (1/total_period) - 1) * 100
                
                st.metric(
                    "📊 歷史年化報酬率",
                    f"{cagr:.1f}%",
                    delta=f"{holding_period}持有預期"
                )
                
                # 預估未來價值
                current_price = last_price
                future_price = current_price * ((1 + cagr/100) ** holding_years)
                
                col1, col2 = st.columns(2)
                with col1:
                    st.metric(
                        "💰 當前平均單價",
                        f"{current_price:,.0f} 元/m²"
                    )
                
                with col2:
                    st.metric(
                        f"📈 {holding_years}年後預估",
                        f"{future_price:,.0f} 元/m²",
                        delta=f"{(future_price/current_price - 1)*100:.1f}%"
                    )
        
        # 新成屋 vs 中古屋分析
        st.markdown("### 🏘️ 新成屋 vs 中古屋表現")
        
        # 比較增值潛力
        new_house_df = price_df[price_df['BUILD'] == '新成屋']
        old_house_df = price_df[price_df['BUILD'] == '中古屋']
        
        if not new_house_df.empty and not old_house_df.empty:
            # 計算溢價率
            new_price = new_house_df['平均單價元平方公尺'].iloc[-1] if len(new_house_df) > 0 else 0
            old_price = old_house_df['平均單價元平方公尺'].iloc[-1] if len(old_house_df) > 0 else 0
            
            if old_price > 0:
                premium_rate = ((new_price - old_price) / old_price) * 100
                
                st.info(f"新成屋溢價率: {premium_rate:.1f}%")
                
                if premium_rate > 25:
                    st.warning("⚠️ 新成屋溢價較高，中古屋CP值可能更好")
                elif premium_rate < 15:
                    st.success("✅ 新成屋溢價合理，品質較有保障")
    
    def _analyze_investment_return(self, re_df, pop_df):
        """投資報酬率分析"""
        st.subheader("💰 投資報酬率分析")
        
        # 假設租金收益率（可從資料或市場平均估算）
        avg_rent_yield = 2.5  # 預設2.5%
        
        # 計算總投資報酬率
        price_df = re_df.groupby('民國年')['平均單價元平方公尺'].mean().reset_index()
        
        if len(price_df) >= 2:
            price_growth = ((price_df['平均單價元平方公尺'].iloc[-1] / 
                          price_df['平均單價元平方公尺'].iloc[0]) ** 
                         (1/(price_df['民國年'].iloc[-1] - price_df['民國年'].iloc[0])) - 1) * 100
            
            total_return = price_growth + avg_rent_yield
            
            # 顯示報酬率儀表板
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("📈 資本利得率", f"{price_growth:.1f}%")
            
            with col2:
                st.metric("🏠 租金收益率", f"{avg_rent_yield:.1f}%")
            
            with col3:
                st.metric("💰 總報酬率", f"{total_return:.1f}%")
            
            # 與其他投資比較
            st.markdown("### ⚖️ 與其他投資工具比較")
            
            comparison_data = {
                "不動產": total_return,
                "股票": 7.5,
                "債券": 3.5,
                "定存": 1.5,
                "黃金": 4.0
            }
            
            st_echarts({
                "tooltip": {"trigger": "axis"},
                "xAxis": {"type": "category", "data": list(comparison_data.keys())},
                "yAxis": {"type": "value", "name": "年化報酬率(%)"},
                "series": [{"type": "bar", "data": list(comparison_data.values())}]
            }, height="300px")
    
    def _render_ai_comprehensive_analysis(self, module, re_df, pop_df, city_choice, 
                                        district_choice, purchase_purpose, 
                                        budget_range, holding_period):
        """AI 綜合分析"""
        st.markdown("---")
        st.subheader("🤖 AI 購房策略分析")
        
        # 準備分析數據
        analysis_data = {
            "模組": module,
            "地區": f"{city_choice} - {district_choice}",
            "購房目的": purchase_purpose,
            "預算範圍": budget_range,
            "持有年限": holding_period,
            "資料筆數": len(re_df),
            "最新年度": re_df['民國年'].max() if not re_df.empty else None
        }
        
        gemini_key = st.session_state.get("GEMINI_KEY", "")
        
        if gemini_key:
            col1, col2 = st.columns([1, 3])
            
            with col1:
                if st.button("🚀 取得AI建議", type="primary", use_container_width=True):
                    self._call_gemini_for_advice(
                        analysis_data, re_df, gemini_key,
                        purchase_purpose, budget_range, holding_period
                    )
            
            with col2:
                if st.session_state.get("market_analysis_key"):
                    st.success("✅ 已有分析結果")
                else:
                    st.info("點擊按鈕獲取AI購房建議")
        
        # 顯示分析結果
        if st.session_state.market_analysis_result:
            st.markdown("### 📋 AI 購房策略報告")
            with st.container():
                st.markdown("---")
                st.markdown(st.session_state.market_analysis_result)
                st.markdown("---")
                
                # 建議行動步驟
                st.markdown("### 🎯 建議行動步驟")
                st.markdown("""
                1. **立即行動** - 高優先級建議
                2. **短期規劃** - 3個月內可執行
                3. **長期策略** - 年度規劃
                4. **風險控制** - 注意事項
                """)
    
    def _call_gemini_for_advice(self, analysis_data, re_df, gemini_key, 
                              purchase_purpose, budget_range, holding_period):
        """呼叫Gemini獲取購房建議"""
        prompt = f"""
        你是一位有20年經驗的不動產投資顧問，請為以下購房情境提供專業建議：
        
        購房情境：
        - 目的：{purchase_purpose}
        - 預算：{budget_range}
        - 預計持有：{holding_period}
        - 分析地區：{analysis_data['地區']}
        
        市場數據摘要：
        - 分析期間：共 {analysis_data['資料筆數']} 筆交易數據
        - 最新年度：{analysis_data['最新年度']}
        
        請提供：
        1. 當前市場機會與風險評估
        2. 具體的購房策略建議
        3. 議價技巧與時機建議
        4. 風險控制措施
        5. 適合的產品類型建議
        
        請以專業但易懂的方式呈現，避免過度技術術語。
        """
        
        try:
            genai.configure(api_key=gemini_key)
            model = genai.GenerativeModel("gemini-2.0-flash")
            
            with st.spinner("🧠 AI正在分析購房策略..."):
                resp = model.generate_content(prompt)
                
                st.session_state.market_analysis_result = resp.text
                st.session_state.market_analysis_key = f"advice_{analysis_data['地區']}_{purchase_purpose}"
                
                st.success("✅ AI分析完成！")
                
        except Exception as e:
            st.error(f"❌ AI分析失敗: {str(e)}")
    
    # 其他原有方法的增強版本...
    # _render_area_selection, _filter_data 等方法的實現保持類似但可優化
    
    def _render_area_selection(self, pop_long):
        """地區選擇介面"""
        tab1, tab2, tab3 = st.tabs(["📍 快速選擇", "🗺️ 地圖選擇", "🎯 目標搜尋"])
        
        with tab1:
            col1, col2, col3 = st.columns(3)
            
            with col1:
                cities = ["全台"] + sorted(self.combined_df["縣市"].unique())
                city_choice = st.selectbox("選擇縣市", cities, key="city_choice")
            
            with col2:
                if city_choice != "全台":
                    districts = ["全部"] + sorted(
                        self.combined_df[self.combined_df["縣市"] == city_choice]["行政區"].unique()
                    )
                    district_choice = st.selectbox("選擇行政區", districts, key="district_choice")
                else:
                    district_choice = "全部"
            
            with col3:
                year_min = int(min(self.combined_df["民國年"].min(), pop_long["民國年"].min()))
                year_max = int(max(self.combined_df["民國年"].max(), pop_long["民國年"].max()))
                
                year_range = st.slider(
                    "分析期間",
                    min_value=year_min,
                    max_value=year_max,
                    value=(max(year_min, year_max-5), year_max),  # 預設最近5年
                    key="year_range"
                )
        
        return city_choice, district_choice, year_range

# 原有方法的增強實現...
