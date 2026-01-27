# components/market_trend.py - 完整功能版
import streamlit as st
import pandas as pd
import os
import sys
import time
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


class MarketTrendAnalyzer:
    """市場趨勢分析器 - 完整功能版"""
    
    def __init__(self):
        self.combined_df = None
        self.population_df = None
        
    def render_analysis_tab(self):
        """渲染市場趨勢分析頁面 - 完整功能"""
        st.subheader("📊 市場趨勢分析")
        
        # 初始化 session state
        if 'market_analysis_result' not in st.session_state:
            st.session_state.market_analysis_result = None
        if 'market_analysis_key' not in st.session_state:
            st.session_state.market_analysis_key = None
        
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
        
        # 篩選條件
        city_choice, district_choice, year_range = self._render_filters(pop_long)
        
        # 篩選資料
        re_df, pop_df = self._filter_data(city_choice, district_choice, year_range, pop_long)
        
        # 顯示資料表
        self._display_data_tables(re_df, pop_df, year_range)
        
        # 選擇分析類型
        chart_type = st.selectbox(
            "選擇分析類型",
            [
                "不動產價格趨勢分析（含交易結構）",
                "交易筆數分布（結構）",
                "人口 × 成交量（市場是否被壓抑）"
            ],
            key="market_chart_type"
        )
        
        # 執行分析
        if chart_type:
            analysis_data = self._perform_chart_analysis(
                chart_type, re_df, pop_df, city_choice, district_choice, year_range
            )
            
            # AI 分析
            if analysis_data:
                self._render_ai_analysis(
                    chart_type,
                    analysis_data,
                    re_df,
                    pop_df,
                    city_choice,
                    district_choice,
                    year_range
                )
    
    def _load_real_estate_data(self):
        """載入不動產資料"""
        try:
            data_dir = PAGE_MODULES_FOLDER
            csv_files = [f for f in os.listdir(data_dir) 
                        if f.startswith("合併後不動產統計_") and f.endswith(".csv")]
            
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
                        continue
                dfs.append(df)
            
            if dfs:
                return pd.concat(dfs, ignore_index=True)
            else:
                return pd.DataFrame()
                
        except Exception as e:
            st.error(f"載入不動產資料失敗: {e}")
            return pd.DataFrame()
    
    def _load_population_data(self):
        """載入人口資料"""
        try:
            data_dir = PAGE_MODULES_FOLDER
            file_path = os.path.join(data_dir, "NEWWWW.csv")
            
            if not os.path.exists(file_path):
                st.warning(f"找不到人口資料檔案: {file_path}")
                return pd.DataFrame()
            
            try:
                df = pd.read_csv(file_path, encoding="utf-8")
            except:
                df = pd.read_csv(file_path, encoding="big5")
            
            return df
            
        except Exception as e:
            st.error(f"載入人口資料失敗: {e}")
            return pd.DataFrame()
    
    def _clean_data(self):
        """清理資料"""
        if "季度" in self.combined_df.columns:
            self.combined_df["民國年"] = self.combined_df["季度"].str[:3].astype(int)
        
        # 清理人口資料欄位名稱
        self.population_df.columns = [str(c).strip().replace("　", "") for c in self.population_df.columns]
        self.population_df["縣市"] = self.population_df["縣市"].astype(str).str.strip()
        self.population_df["行政區"] = self.population_df["行政區"].astype(str).str.strip()
    
    def _prepare_population_data(self):
        """準備人口資料（轉長格式）"""
        year_cols = [c for c in self.population_df.columns if "年" in c]
        pop_long = self.population_df.melt(
            id_vars=["縣市", "行政區"],
            value_vars=year_cols,
            var_name="年度",
            value_name="人口數"
        )
        
        pop_long["人口數"] = (
            pop_long["人口數"].astype(str).str.replace(",", "").astype(int)
        )
        pop_long["民國年"] = pop_long["年度"].str[:3].astype(int)
        
        return pop_long
    
    def _render_filters(self, pop_long):
        """渲染篩選條件"""
        col_main, col_filter = st.columns([3, 1])
        
        with col_filter:
            cities = ["全台"] + sorted(self.combined_df["縣市"].unique())
            city_choice = st.selectbox("選擇縣市", cities, key="city_choice")
            
            if city_choice != "全台":
                district_choice = st.selectbox(
                    "選擇行政區",
                    ["全部"] + sorted(
                        self.combined_df[self.combined_df["縣市"] == city_choice]["行政區"].unique()
                    ),
                    key="district_choice"
                )
            else:
                district_choice = "全部"
            
            year_min = int(min(self.combined_df["民國年"].min(), pop_long["民國年"].min()))
            year_max = int(max(self.combined_df["民國年"].max(), pop_long["民國年"].max()))
            
            year_range = st.slider(
                "選擇分析年份",
                min_value=year_min,
                max_value=year_max,
                value=(year_min, year_max),
                key="year_range"
            )
        
        return city_choice, district_choice, year_range
    
    def _filter_data(self, city_choice, district_choice, year_range, pop_long):
        """篩選資料"""
        # 不動產資料篩選
        re_df = self.combined_df[
            (self.combined_df["民國年"] >= year_range[0]) &
            (self.combined_df["民國年"] <= year_range[1])
        ]
        
        if city_choice != "全台":
            re_df = re_df[re_df["縣市"] == city_choice]
            if district_choice != "全部":
                re_df = re_df[re_df["行政區"] == district_choice]
        
        # 人口資料篩選
        pop_df = pop_long[
            (pop_long["民國年"] >= year_range[0]) &
            (pop_long["民國年"] <= year_range[1])
        ]
        
        if city_choice == "全台":
            pop_df = pop_df[pop_df["縣市"] == pop_df["行政區"]]
        elif district_choice == "全部":
            pop_df = pop_df[
                (pop_df["縣市"] == city_choice) &
                (pop_df["行政區"] == city_choice)
            ]
        else:
            pop_df = pop_df[
                (pop_df["縣市"] == city_choice) &
                (pop_df["行政區"] == district_choice)
            ]
        
        return re_df, pop_df
    
    def _display_data_tables(self, re_df, pop_df, year_range):
        """顯示資料表"""
        col_main, _ = st.columns([3, 1])
        
        with col_main:
            # 表格 1：不動產資料
            with st.expander("📂 表一：不動產資料（點擊展開）", expanded=True):
                if not re_df.empty:
                    st.dataframe(re_df, use_container_width=True)
                    st.caption(f"共 {len(re_df)} 筆不動產交易記錄")
                else:
                    st.warning("該條件下無不動產資料")
            
            # 表格 2：人口資料
            with st.expander("👥 表二：人口資料（年度，點擊展開）", expanded=False):
                if not pop_df.empty:
                    pivot_df = pop_df.pivot_table(
                        index=["縣市", "行政區"],
                        columns="民國年",
                        values="人口數",
                        aggfunc="last"
                    ).fillna(0).astype(int)
                    
                    st.dataframe(pivot_df, use_container_width=True)
                    st.caption(f"人口資料範圍：{year_range[0]} - {year_range[1]} 年")
                else:
                    st.warning("該條件下無人口資料")
    
    def _perform_chart_analysis(self, chart_type, re_df, pop_df, city_choice, district_choice, year_range):
        """執行圖表分析"""
        analysis_data = {}
        
        if chart_type == "不動產價格趨勢分析（含交易結構）":
            analysis_data = self._analyze_price_trend(re_df, city_choice, district_choice, year_range)
        
        elif chart_type == "交易筆數分布（結構）":
            analysis_data = self._analyze_transaction_distribution(re_df, city_choice, district_choice, year_range)
        
        elif chart_type == "人口 × 成交量（市場是否被壓抑）":
            analysis_data = self._analyze_population_vs_transactions(re_df, pop_df, city_choice, district_choice, year_range)
        
        return analysis_data
    
    def _analyze_price_trend(self, re_df, city_choice, district_choice, year_range):
        """分析價格趨勢"""
        # 價格趨勢
        price_df = re_df.groupby(["民國年", "BUILD"])["平均單價元平方公尺"].mean().reset_index()
        years = sorted(price_df["民國年"].unique())
        
        def safe_mean_price(year, build):
            s = price_df[(price_df["民國年"] == year) & (price_df["BUILD"] == build)]["平均單價元平方公尺"]
            return int(s.mean()) if not s.empty else 0
        
        new_price = [safe_mean_price(y, "新成屋") for y in years]
        old_price = [safe_mean_price(y, "中古屋") for y in years]
        
        # 顯示圖表
        st.markdown("### 📈 價格趨勢（新成屋 vs 中古屋）")
        st_echarts({
            "tooltip": {"trigger": "axis"},
            "legend": {"data": ["新成屋", "中古屋"]},
            "xAxis": {"type": "category", "data": [str(y) for y in years]},
            "yAxis": {"type": "value"},
            "series": [
                {"name": "新成屋", "type": "line", "data": new_price},
                {"name": "中古屋", "type": "line", "data": old_price}
            ]
        }, height="350px")
        
        # 交易結構
        trans_df = re_df.groupby(["民國年", "BUILD"])["交易筆數"].sum().reset_index()
        
        def safe_sum_trans(year, build):
            s = trans_df[(trans_df["民國年"] == year) & (trans_df["BUILD"] == build)]["交易筆數"]
            return int(s.sum()) if not s.empty else 0
        
        new_trans = [safe_sum_trans(y, "新成屋") for y in years]
        old_trans = [safe_sum_trans(y, "中古屋") for y in years]
        
        st.markdown("### 📊 交易結構（量的來源）")
        st_echarts({
            "tooltip": {"trigger": "axis"},
            "legend": {"data": ["新成屋", "中古屋"]},
            "xAxis": {"type": "category", "data": [str(y) for y in years]},
            "yAxis": {"type": "value"},
            "series": [
                {"name": "新成屋", "type": "bar", "stack": "total", "data": new_trans},
                {"name": "中古屋", "type": "bar", "stack": "total", "data": old_trans}
            ]
        }, height="350px")
        
        return {
            "years": years,
            "new_price": new_price,
            "old_price": old_price,
            "new_trans": new_trans,
            "old_trans": old_trans,
            "city": city_choice,
            "district": district_choice,
            "year_range": year_range,
            "chart_type": "價格趨勢與交易結構",
            "total_transactions": sum(new_trans) + sum(old_trans)
        }
    
    def _analyze_transaction_distribution(self, re_df, city_choice, district_choice, year_range):
        """分析交易筆數分布"""
        # 行政區交易量排行
        total_trans = re_df.groupby("行政區")["交易筆數"].sum().reset_index()
        total_trans = total_trans.sort_values("交易筆數", ascending=True).tail(10)
        
        st.markdown("### 📊 行政區交易量排行（Top 10）")
        st_echarts({
            "tooltip": {"trigger": "axis"},
            "xAxis": {"type": "value"},
            "yAxis": {"type": "category", "data": total_trans["行政區"].tolist()},
            "series": [{"type": "bar", "data": total_trans["交易筆數"].astype(int).tolist()}]
        }, height="400px")
        
        # 每年交易筆數 Top 3
        yearly_top3_data = {}
        years = sorted(re_df["民國年"].unique())
        
        for y in years:
            df_y = re_df[re_df["民國年"] == y]
            top3 = df_y.groupby("行政區")["交易筆數"].sum().reset_index()
            top3 = top3.sort_values("交易筆數", ascending=False).head(3)
            yearly_top3_data[y] = top3
        
        return {
            "top_districts": total_trans.to_dict('records'),
            "yearly_top3": yearly_top3_data,
            "city": city_choice,
            "district": district_choice,
            "year_range": year_range,
            "chart_type": "交易筆數分布",
            "total_years": len(years)
        }
    
    def _analyze_population_vs_transactions(self, re_df, pop_df, city_choice, district_choice, year_range):
        """分析人口與成交量關係"""
        pop_year = pop_df.groupby("民國年")["人口數"].last().reset_index()
        trans_year = re_df.groupby("民國年")["交易筆數"].sum().reset_index()
        
        merged = pd.merge(pop_year, trans_year, on="民國年", how="left").fillna(0)
        
        st.markdown("### 📊 人口與成交量趨勢對比")
        st_echarts({
            "tooltip": {"trigger": "axis"},
            "legend": {"data": ["人口數", "成交量"]},
            "xAxis": {"type": "category", "data": merged["民國年"].astype(str).tolist()},
            "yAxis": [{"type": "value"}, {"type": "value"}],
            "series": [
                {"name": "人口數", "type": "line", "data": merged["人口數"].tolist()},
                {"name": "成交量", "type": "line", "yAxisIndex": 1, "data": merged["交易筆數"].tolist()}
            ]
        }, height="400px")
        
        # 計算市場壓抑指數
        pop_change, trans_change, suppression_index = self._calculate_suppression_index(merged)
        
        return {
            "population_trend": merged.to_dict('records'),
            "city": city_choice,
            "district": district_choice,
            "year_range": year_range,
            "chart_type": "人口與成交量關係",
            "pop_change": pop_change,
            "trans_change": trans_change,
            "suppression_index": suppression_index
        }
    
    def _calculate_suppression_index(self, merged_df):
        """計算市場壓抑指數"""
        if len(merged_df) <= 1:
            return 0, 0, 0
        
        pop_change = ((merged_df["人口數"].iloc[-1] - merged_df["人口數"].iloc[0]) / merged_df["人口數"].iloc[0]) * 100
        trans_change = ((merged_df["交易筆數"].iloc[-1] - merged_df["交易筆數"].iloc[0]) / merged_df["交易筆數"].iloc[0]) * 100
        
        suppression_index = pop_change - trans_change if pop_change > 0 else 0
        
        return pop_change, trans_change, suppression_index
    
    def _render_ai_analysis(self, chart_type, analysis_data, re_df, pop_df, city_choice, district_choice, year_range):
        """渲染 AI 分析"""
        st.markdown("---")
        st.subheader("🤖 AI 市場趨勢分析")
        
        # 建立分析鍵值
        analysis_params_key = f"{chart_type}_{city_choice}_{district_choice}_{year_range[0]}_{year_range[1]}"
        
        # 檢查是否需要重新分析
        should_reanalyze = (
            st.session_state.get("market_analysis_key") != analysis_params_key or
            st.session_state.market_analysis_result is None
        )
        
        gemini_key = st.session_state.get("GEMINI_KEY", "")
        
        if gemini_key:
            col1, col2, col3 = st.columns([1, 2, 2])
            
            with col1:
                if st.button("🚀 啟動 AI 分析", type="primary", use_container_width=True, key="start_market_analysis"):
                    self._call_gemini_analysis(chart_type, analysis_data, re_df, pop_df, analysis_params_key, gemini_key)
            
            with col2:
                if st.session_state.get("market_analysis_key") == analysis_params_key:
                    st.success("✅ 已有分析結果")
                elif should_reanalyze:
                    st.info("🔄 需要重新分析")
                else:
                    st.info("👆 點擊按鈕開始分析")
                    
            with col3:
                if st.button("🗑️ 清除分析結果", type="secondary", use_container_width=True, key="clear_analysis"):
                    st.session_state.market_analysis_result = None
                    st.session_state.market_analysis_key = None
                    st.rerun()
        else:
            st.warning("請在側邊欄填入 Gemini API 金鑰以使用 AI 分析功能")
        
        # 顯示分析結果
        if st.session_state.market_analysis_result and st.session_state.market_analysis_key == analysis_params_key:
            st.markdown("### 📊 AI 分析報告")
            with st.container():
                st.markdown("---")
                st.markdown(st.session_state.market_analysis_result)
                st.markdown("---")
    
    def _call_gemini_analysis(self, chart_type, analysis_data, re_df, pop_df, analysis_key, gemini_key):
        """呼叫 Gemini 分析"""
        # 防爆檢查
        now = time.time()
        last = st.session_state.get("last_market_gemini_call", 0)
        
        if now - last < 30:
            st.warning("⚠️ Gemini 分析請等待 30 秒後再試")
            return
        
        st.session_state.last_market_gemini_call = now
        
        # 準備提示詞
        prompt = self._prepare_market_analysis_prompt(chart_type, analysis_data, re_df, pop_df)
        
        # 呼叫 Gemini
        with st.spinner("🧠 AI 分析市場趨勢中..."):
            try:
                genai.configure(api_key=gemini_key)
                model = genai.GenerativeModel("gemini-2.0-flash")
                
                resp = model.generate_content(prompt)
                
                # 儲存結果
                st.session_state.market_analysis_result = resp.text
                st.session_state.market_analysis_key = analysis_key
                
                st.success("✅ AI 分析完成！")
                
            except Exception as e:
                st.error(f"❌ Gemini API 錯誤: {str(e)}")
    
    def _prepare_market_analysis_prompt(self, chart_type, analysis_data, re_df, pop_df):
        """準備市場分析提示詞"""
        base_context = f"""
        你是一位資深不動產分析師，擁有10年市場分析經驗。
        請針對以下數據提供專業、客觀的分析報告。
        
        分析範圍：
        - 地區：{analysis_data.get('city', '全台')} - {analysis_data.get('district', '全部')}
        - 時間：{analysis_data.get('year_range', ())} 年
        - 數據類型：{chart_type}
        """
        
        if chart_type == "不動產價格趨勢分析（含交易結構）":
            return base_context + f"""
            
            具體數據：
            1. 價格趨勢：
               - 分析期間：{analysis_data.get('years', [])} 年
               - 新成屋價格趨勢：{analysis_data.get('new_price', [])}
               - 中古屋價格趨勢：{analysis_data.get('old_price', [])}
            
            2. 交易結構：
               - 新成屋交易量：{analysis_data.get('new_trans', [])}
               - 中古屋交易量：{analysis_data.get('old_trans', [])}
            
            請提供專業的市場分析報告。
            """
        
        elif chart_type == "交易筆數分布（結構）":
            return base_context + f"""
            
            具體數據：
            1. 交易量Top 10行政區：{analysis_data.get('top_districts', [])}
            
            請提供專業的區域熱度分析報告。
            """
        
        elif chart_type == "人口 × 成交量（市場是否被壓抑）":
            return base_context + f"""
            
            具體數據：
            人口與成交量趨勢：{analysis_data.get('population_trend', [])}
            
            請提供專業的人口與市場關係分析報告。
            """
        
        return base_context
