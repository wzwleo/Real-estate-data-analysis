# components/market_trend_analysis.py
import streamlit as st
import pandas as pd
import time
import google.generativeai as genai
from streamlit_echarts import st_echarts
from page_modules.analysis_page import (
    load_real_estate_csv, load_population_csv,
    prepare_market_analysis_prompt
)

def market_trend_analysis_module():
    """市場趨勢分析模組 - 對應 Tab3"""
    st.subheader("📊 市場趨勢分析")
    
    # 初始化 session state
    if 'market_analysis_result' not in st.session_state:
        st.session_state.market_analysis_result = None
    if 'market_analysis_key' not in st.session_state:
        st.session_state.market_analysis_key = None
    
    # 載入資料
    combined_df = load_real_estate_csv(folder="./page_modules")
    population_df = load_population_csv(folder="./page_modules")
    
    if combined_df.empty or population_df.empty:
        st.info("📂 找不到房產或人口資料")
        return
    
    # 資料清理和處理
    processed_data = process_data(combined_df, population_df)
    if not processed_data:
        return
    
    re_df, pop_long = processed_data
    
    # 篩選條件
    city_choice, district_choice, year_range = render_filters(combined_df, pop_long)
    
    # 資料篩選
    filtered_data = filter_data(re_df, pop_long, city_choice, district_choice, year_range)
    if not filtered_data:
        return
    
    filtered_re_df, filtered_pop_df = filtered_data
    
    # 顯示資料表格
    display_data_tables(filtered_re_df, filtered_pop_df, year_range)
    
    # 圖表分析
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
    analysis_data = perform_analysis(chart_type, filtered_re_df, filtered_pop_df, 
                                    city_choice, district_choice, year_range)
    
    # AI 分析
    render_ai_analysis(chart_type, analysis_data, filtered_re_df, filtered_pop_df,
                      city_choice, district_choice, year_range)

def process_data(combined_df, population_df):
    """處理原始資料"""
    try:
        combined_df["民國年"] = combined_df["季度"].str[:3].astype(int)
        
        population_df.columns = [str(c).strip().replace("　", "") for c in population_df.columns]
        population_df["縣市"] = population_df["縣市"].astype(str).str.strip()
        population_df["行政區"] = population_df["行政區"].astype(str).str.strip()
        
        # 人口資料轉長格式
        year_cols = [c for c in population_df.columns if "年" in c]
        pop_long = population_df.melt(
            id_vars=["縣市", "行政區"],
            value_vars=year_cols,
            var_name="年度",
            value_name="人口數"
        )
        
        pop_long["人口數"] = (
            pop_long["人口數"].astype(str).str.replace(",", "").astype(int)
        )
        pop_long["民國年"] = pop_long["年度"].str[:3].astype(int)
        
        return combined_df, pop_long
    except Exception as e:
        st.error(f"資料處理失敗: {e}")
        return None

def render_filters(combined_df, pop_long):
    """渲染篩選器"""
    col_main, col_filter = st.columns([3, 1])
    
    with col_filter:
        cities = ["全台"] + sorted(combined_df["縣市"].unique())
        city_choice = st.selectbox("選擇縣市", cities, key="city_choice")
    
        if city_choice != "全台":
            district_choice = st.selectbox(
                "選擇行政區",
                ["全部"] + sorted(
                    combined_df[combined_df["縣市"] == city_choice]["行政區"].unique()
                ),
                key="district_choice"
            )
        else:
            district_choice = "全部"
    
        year_min = int(min(combined_df["民國年"].min(), pop_long["民國年"].min()))
        year_max = int(max(combined_df["民國年"].max(), pop_long["民國年"].max()))
    
        year_range = st.slider(
            "選擇分析年份",
            min_value=year_min,
            max_value=year_max,
            value=(year_min, year_max),
            key="year_range"
        )
    
    return city_choice, district_choice, year_range

def filter_data(re_df, pop_long, city_choice, district_choice, year_range):
    """篩選資料"""
    # 不動產資料篩選
    filtered_re_df = re_df[
        (re_df["民國年"] >= year_range[0]) &
        (re_df["民國年"] <= year_range[1])
    ]
    
    if city_choice != "全台":
        filtered_re_df = filtered_re_df[filtered_re_df["縣市"] == city_choice]
        if district_choice != "全部":
            filtered_re_df = filtered_re_df[filtered_re_df["行政區"] == district_choice]
    
    # 人口資料篩選
    filtered_pop_df = pop_long[
        (pop_long["民國年"] >= year_range[0]) &
        (pop_long["民國年"] <= year_range[1])
    ]
    
    if city_choice == "全台":
        filtered_pop_df = filtered_pop_df[filtered_pop_df["縣市"] == filtered_pop_df["行政區"]]
    elif district_choice == "全部":
        filtered_pop_df = filtered_pop_df[
            (filtered_pop_df["縣市"] == city_choice) &
            (filtered_pop_df["行政區"] == city_choice)
        ]
    else:
        filtered_pop_df = filtered_pop_df[
            (filtered_pop_df["縣市"] == city_choice) &
            (filtered_pop_df["行政區"] == district_choice)
        ]
    
    return filtered_re_df, filtered_pop_df

def display_data_tables(re_df, pop_df, year_range):
    """顯示資料表格"""
    col_main, col_filter = st.columns([3, 1])
    
    with col_main:
        # 表格 1：不動產資料
        with st.expander("📂 表一：不動產資料（點擊展開）", expanded=True):
            if not re_df.empty:
                st.dataframe(re_df, use_container_width=True)
                st.caption(f"共 {len(re_df)} 筆不動產交易記錄")
            else:
                st.warning("該條件下無不動產資料")
    
        # 表格 2：人口資料（年度）
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

def perform_analysis(chart_type, re_df, pop_df, city_choice, district_choice, year_range):
    """執行圖表分析"""
    analysis_data = {}
    
    if chart_type == "不動產價格趨勢分析（含交易結構）":
        analysis_data = analyze_price_trend(re_df, city_choice, district_choice, year_range)
    elif chart_type == "交易筆數分布（結構）":
        analysis_data = analyze_transaction_distribution(re_df, city_choice, district_choice, year_range)
    elif chart_type == "人口 × 成交量（市場是否被壓抑）":
        analysis_data = analyze_population_transaction(re_df, pop_df, city_choice, district_choice, year_range)
    
    return analysis_data

def analyze_price_trend(re_df, city_choice, district_choice, year_range):
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

def analyze_transaction_distribution(re_df, city_choice, district_choice, year_range):
    """分析交易筆數分布"""
    # 行政區交易量排行（Top 10）
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
    
    with st.expander("📂 查看每年交易筆數 Top 3 行政區"):
        for y in years:
            df_y = re_df[re_df["民國年"] == y]
            top3 = df_y.groupby("行政區")["交易筆數"].sum().reset_index()
            top3 = top3.sort_values("交易筆數", ascending=False).head(3)
            yearly_top3_data[y] = top3
            
            st.markdown(f"#### {y} 年")
            st.dataframe(top3, use_container_width=True)
    
    return {
        "top_districts": total_trans.to_dict('records'),
        "yearly_top3": yearly_top3_data,
        "city": city_choice,
        "district": district_choice,
        "year_range": year_range,
        "chart_type": "交易筆數分布",
        "total_years": len(years)
    }

def analyze_population_transaction(re_df, pop_df, city_choice, district_choice, year_range):
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
    pop_change, trans_change, suppression_index = 0, 0, 0
    
    if len(merged) > 1:
        pop_change = ((merged["人口數"].iloc[-1] - merged["人口數"].iloc[0]) / merged["人口數"].iloc[0]) * 100
        trans_change = ((merged["交易筆數"].iloc[-1] - merged["交易筆數"].iloc[0]) / merged["交易筆數"].iloc[0]) * 100
        suppression_index = pop_change - trans_change if pop_change > 0 else 0
    
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

def render_ai_analysis(chart_type, analysis_data, re_df, pop_df,
                      city_choice, district_choice, year_range):
    """渲染 AI 分析"""
    st.markdown("---")
    st.subheader("🤖 AI 市場趨勢分析")
    
    # 建立唯一的分析鍵值
    analysis_params_key = f"{chart_type}_{city_choice}_{district_choice}_{year_range[0]}_{year_range[1]}"
    
    # 檢查是否需要重新分析
    should_reanalyze = (
        st.session_state.get("market_analysis_key") != analysis_params_key or
        st.session_state.market_analysis_result is None
    )
    
    # 如果有 Gemini Key，顯示分析按鈕
    gemini_key = st.session_state.get("GEMINI_KEY", "")
    
    if gemini_key:
        col1, col2, col3 = st.columns([1, 2, 2])
        
        with col1:
            if st.button("🚀 啟動 AI 分析", type="primary", use_container_width=True, key="start_market_analysis"):
                execute_ai_analysis(chart_type, analysis_data, re_df, pop_df, analysis_params_key, gemini_key)
        
        with col2:
            if st.session_state.market_analysis_key == analysis_params_key:
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
    
    # 顯示 AI 分析結果
    display_ai_results(analysis_params_key, city_choice, district_choice, year_range, chart_type, gemini_key)

def execute_ai_analysis(chart_type, analysis_data, re_df, pop_df, analysis_params_key, gemini_key):
    """執行 AI 分析"""
    # 防爆檢查
    now = time.time()
    last = st.session_state.get("last_market_gemini_call", 0)
    
    if now - last < 30:
        st.warning("⚠️ Gemini 分析請等待 30 秒後再試")
        return
    
    st.session_state.last_market_gemini_call = now
    
    # 準備專業提示詞
    prompt = prepare_market_analysis_prompt(chart_type, analysis_data, re_df, pop_df)
    
    # 顯示提示詞預覽（可選）
    with st.expander("📝 查看分析提示詞"):
        st.text_area("Gemini 將收到的提示詞", prompt, height=300, key="prompt_preview")
    
    # 呼叫 Gemini
    with st.spinner("🧠 AI 分析市場趨勢中..."):
        try:
            genai.configure(api_key=gemini_key)
            model = genai.GenerativeModel("gemini-2.0-flash")
            
            resp = model.generate_content(prompt)
            
            # 儲存結果
            st.session_state.market_analysis_result = resp.text
            st.session_state.market_analysis_key = analysis_params_key
            
            st.success("✅ AI 分析完成！")
            
        except Exception as e:
            st.error(f"❌ Gemini API 錯誤: {str(e)}")

def display_ai_results(analysis_params_key, city_choice, district_choice, year_range, chart_type, gemini_key):
    """顯示 AI 分析結果"""
    if st.session_state.market_analysis_result and st.session_state.market_analysis_key == analysis_params_key:
        st.markdown("### 📊 AI 分析報告")
        
        # 美化顯示結果
        with st.container():
            st.markdown("---")
            st.markdown(st.session_state.market_analysis_result)
            st.markdown("---")
        
        # 額外提問功能
        render_follow_up_questions(city_choice, district_choice, year_range, chart_type, gemini_key)
    
    elif gemini_key:
        st.info("👆 點擊上方「啟動 AI 分析」按鈕，獲取專業市場分析報告")

def render_follow_up_questions(city_choice, district_choice, year_range, chart_type, gemini_key):
    """渲染後續提問功能"""
    st.subheader("💬 深入提問")
    
    col_quest, col_btn = st.columns([3, 1])
    
    with col_quest:
        user_question = st.text_area(
            "對分析結果有進一步問題嗎？",
            placeholder="例如：根據這個趨勢，未來一年的房價會如何變化？投資建議？風險評估？",
            label_visibility="collapsed",
            key="user_question"
        )
    
    with col_btn:
        ask_disabled = not (user_question and gemini_key)
        if st.button("🔍 提問", type="secondary", use_container_width=True, disabled=ask_disabled, key="ask_question"):
            handle_follow_up_question(user_question, city_choice, district_choice, year_range, chart_type, gemini_key)

def handle_follow_up_question(user_question, city_choice, district_choice, year_range, chart_type, gemini_key):
    """處理後續提問"""
    # 防爆檢查
    now = time.time()
    last = st.session_state.get("last_gemini_question", 0)
    
    if now - last < 15:
        st.warning("⚠️ 提問請等待 15 秒後再試")
        return
    
    st.session_state.last_gemini_question = now
    
    with st.spinner("思考中..."):
        try:
            genai.configure(api_key=gemini_key)
            model = genai.GenerativeModel("gemini-2.0-flash")
            
            follow_up_prompt = f"""
            根據先前的市場分析，回答用戶的後續問題。
            
            【先前分析摘要】
            {st.session_state.market_analysis_result[:1000]}...
            
            【用戶提問】
            {user_question}
            
            【分析地區與時間】
            - 地區：{city_choice} - {district_choice}
            - 時間範圍：{year_range[0]} - {year_range[1]} 年
            - 圖表類型：{chart_type}
            
            【請提供】
            1. 基於數據的直接回應
            2. 可能的影響因素（經濟、政策、供需等）
            3. 實用建議（自住、投資、風險管理等）
            4. 相關風險提醒
            
            回答請保持專業、客觀，避免過度推測。如數據不足請說明限制。
            """
            
            resp = model.generate_content(follow_up_prompt)
            
            st.markdown("### 💡 AI 回應")
            st.write(resp.text)
            
        except Exception as e:
            st.error(f"❌ 提問失敗: {str(e)}")
