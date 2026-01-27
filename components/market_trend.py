# components/market_trend.py
import pandas as pd
import streamlit as st
from utils.data_loaders import load_real_estate_csv, load_population_csv


class MarketTrendAnalyzer:
    """市場趨勢分析器"""
    
    def __init__(self):
        self.combined_df = None
        self.population_df = None
    
    def render_analysis_tab(self):
        """渲染市場趨勢分析頁面"""
        st.subheader("📊 市場趨勢分析")
        
        # 載入資料
        self.combined_df = load_real_estate_csv()
        self.population_df = load_population_csv()
        
        if self.combined_df.empty or self.population_df.empty:
            st.warning("無法載入資料")
            return
        
    # ============================
    # Tab3: 市場趨勢分析（整合人口資料）
    # ============================
    with tab3:
        st.subheader("📊 市場趨勢分析")
        
        # 初始化 session state
        if 'market_analysis_result' not in st.session_state:
            st.session_state.market_analysis_result = None
        if 'market_analysis_key' not in st.session_state:
            st.session_state.market_analysis_key = None
        
        # -----------------------------
        # 載入資料
        # -----------------------------
        combined_df = load_real_estate_csv(folder="./page_modules")
        population_df = load_population_csv(folder="./page_modules")
        
        if combined_df.empty or population_df.empty:
            st.info("📂 找不到房產或人口資料")
            st.stop()
        
        # -----------------------------
        # 基本清理
        # -----------------------------
        combined_df["民國年"] = combined_df["季度"].str[:3].astype(int)
        
        population_df.columns = [str(c).strip().replace("　", "") for c in population_df.columns]
        population_df["縣市"] = population_df["縣市"].astype(str).str.strip()
        population_df["行政區"] = population_df["行政區"].astype(str).str.strip()
        
        # -----------------------------
        # 人口資料轉長格式
        # -----------------------------
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
        
        # -----------------------------
        # 篩選條件
        # -----------------------------
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
        
        # -----------------------------
        # 不動產資料篩選
        # -----------------------------
        re_df = combined_df[
            (combined_df["民國年"] >= year_range[0]) &
            (combined_df["民國年"] <= year_range[1])
        ]
        
        if city_choice != "全台":
            re_df = re_df[re_df["縣市"] == city_choice]
            if district_choice != "全部":
                re_df = re_df[re_df["行政區"] == district_choice]
        
        # -----------------------------
        # 人口資料篩選
        # -----------------------------
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
        
        # -----------------------------
        # 顯示資料表（保留原有的兩個表格）
        # -----------------------------
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
                    # 建立樞紐表顯示年度人口
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
        
        # -----------------------------
        # 選擇分析類型
        # -----------------------------
        st.markdown("---")
        st.subheader("📈 圖表分析")
        
        chart_type = st.selectbox(
            "選擇分析類型",
            [
                "不動產價格趨勢分析（含交易結構）",
                "交易筆數分布（結構）",
                "人口 × 成交量（市場是否被壓抑）"
            ],
            key="market_chart_type"
        )
    
        # 預先定義 analysis_data 變數
        analysis_data = {}
        
        # =====================================================
        # ① 價格趨勢分析（＋交易結構）
        # =====================================================
        if chart_type == "不動產價格趨勢分析（含交易結構）":
    
            # ---- 價格趨勢 ----
            price_df = re_df.groupby(
                ["民國年", "BUILD"]
            )["平均單價元平方公尺"].mean().reset_index()
    
            years = sorted(price_df["民國年"].unique())
    
            def safe_mean_price(year, build):
                s = price_df[
                    (price_df["民國年"] == year) &
                    (price_df["BUILD"] == build)
                ]["平均單價元平方公尺"]
                return int(s.mean()) if not s.empty else 0
    
            new_price = [safe_mean_price(y, "新成屋") for y in years]
            old_price = [safe_mean_price(y, "中古屋") for y in years]
    
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
    
            # 顯示數據摘要
            col1, col2 = st.columns(2)
            with col1:
                if new_price:
                    latest_new = new_price[-1]
                    first_new = new_price[0]
                    change = ((latest_new - first_new) / first_new * 100) if first_new > 0 else 0
                    st.metric("新成屋價格變化", f"{latest_new:,.0f} 元/㎡", 
                             f"{change:+.1f}%")
            
            with col2:
                if old_price:
                    latest_old = old_price[-1]
                    first_old = old_price[0]
                    change = ((latest_old - first_old) / first_old * 100) if first_old > 0 else 0
                    st.metric("中古屋價格變化", f"{latest_old:,.0f} 元/㎡", 
                             f"{change:+.1f}%")
    
            # ---- 交易結構（堆疊） ----
            trans_df = re_df.groupby(
                ["民國年", "BUILD"]
            )["交易筆數"].sum().reset_index()
    
            def safe_sum_trans(year, build):
                s = trans_df[
                    (trans_df["民國年"] == year) &
                    (trans_df["BUILD"] == build)
                ]["交易筆數"]
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
    
            # 儲存資料供 Gemini 分析
            analysis_data = {
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
            
        # =====================================================
        # ② 交易筆數分布（結構）
        # =====================================================
        elif chart_type == "交易筆數分布（結構）":
    
            # 行政區交易量排行（Top 10）
            total_trans = re_df.groupby("行政區")["交易筆數"].sum().reset_index()
            total_trans = total_trans.sort_values("交易筆數", ascending=True).tail(10)
    
            st.markdown("### 📊 行政區交易量排行（Top 10）")
            st_echarts({
                "tooltip": {"trigger": "axis"},
                "xAxis": {"type": "value"},
                "yAxis": {
                    "type": "category",
                    "data": total_trans["行政區"].tolist()
                },
                "series": [
                    {"type": "bar", "data": total_trans["交易筆數"].astype(int).tolist()}
                ]
            }, height="400px")
    
            # 顯示統計摘要
            if not total_trans.empty:
                col1, col2, col3 = st.columns(3)
                with col1:
                    total = total_trans["交易筆數"].sum()
                    st.metric("總交易筆數", f"{total:,}")
                with col2:
                    avg = total_trans["交易筆數"].mean()
                    st.metric("平均交易筆數", f"{avg:,.0f}")
                with col3:
                    top_area = total_trans.iloc[-1]["行政區"]
                    top_value = total_trans.iloc[-1]["交易筆數"]
                    st.metric("交易最熱區", top_area, f"{top_value:,} 筆")
    
            # 每年交易筆數 Top 3
            with st.expander("📂 查看每年交易筆數 Top 3 行政區"):
                years = sorted(re_df["民國年"].unique())
                yearly_top3_data = {}
                
                for y in years:
                    df_y = re_df[re_df["民國年"] == y]
                    top3 = df_y.groupby("行政區")["交易筆數"].sum().reset_index()
                    top3 = top3.sort_values("交易筆數", ascending=False).head(3)
                    yearly_top3_data[y] = top3
                    
                    st.markdown(f"#### {y} 年")
                    st.dataframe(top3, use_container_width=True)
    
            # 儲存資料供 Gemini 分析
            analysis_data = {
                "top_districts": total_trans.to_dict('records'),
                "yearly_top3": yearly_top3_data,
                "city": city_choice,
                "district": district_choice,
                "year_range": year_range,
                "chart_type": "交易筆數分布",
                "total_years": len(years)
            }
            
        # =====================================================
        # ③ 人口 × 成交量
        # =====================================================
        elif chart_type == "人口 × 成交量（市場是否被壓抑）":
    
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
    
            # 計算市場壓抑指數（簡單版）
            pop_change = 0
            trans_change = 0
            suppression_index = 0
            
            if len(merged) > 1:
                pop_change = ((merged["人口數"].iloc[-1] - merged["人口數"].iloc[0]) / merged["人口數"].iloc[0]) * 100
                trans_change = ((merged["交易筆數"].iloc[-1] - merged["交易筆數"].iloc[0]) / merged["交易筆數"].iloc[0]) * 100
                
                # 簡單壓抑指標：人口成長率 - 交易量成長率
                suppression_index = pop_change - trans_change if pop_change > 0 else 0
                
                # 顯示指標
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("人口成長率", f"{pop_change:+.1f}%")
                with col2:
                    st.metric("交易量成長率", f"{trans_change:+.1f}%")
                with col3:
                    st.metric("市場壓抑指標", f"{suppression_index:.1f}%")
                
                # 提供解讀
                if suppression_index > 15:
                    st.error("🚨 高度壓抑市場：人口顯著成長但交易量停滯")
                    st.info("可能原因：高房價、貸款限制、供給不足、政策打壓")
                elif suppression_index > 5:
                    st.warning("⚠️ 中度壓抑市場：人口成長快於交易量")
                    st.info("可能原因：購買力成長不足、市場觀望氣氛濃厚")
                elif suppression_index < -15:
                    st.success("🚀 高度活躍市場：交易量成長遠超人口成長")
                    st.info("可能原因：投資需求旺盛、預期心理、政策利多")
                elif suppression_index < -5:
                    st.info("📈 活躍市場：交易量成長快於人口成長")
                else:
                    st.success("✅ 平衡市場：人口與交易量同步發展")
    
            # 儲存資料供 Gemini 分析
            analysis_data = {
                "population_trend": merged.to_dict('records'),
                "city": city_choice,
                "district": district_choice,
                "year_range": year_range,
                "chart_type": "人口與成交量關係",
                "pop_change": pop_change,
                "trans_change": trans_change,
                "suppression_index": suppression_index
            }
    
        # =====================================================
        # AI 分析按鈕區塊
        # =====================================================
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
                    # 防爆檢查
                    now = time.time()
                    last = st.session_state.get("last_market_gemini_call", 0)
                    
                    if now - last < 30:
                        st.warning("⚠️ Gemini 分析請等待 30 秒後再試")
                        st.stop()
                    
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
                            st.info("請檢查：\n1. API 金鑰是否正確\n2. 配額是否用盡\n3. 網路連線是否正常")
            
            with col2:
                # 顯示分析狀態
                if st.session_state.market_analysis_key == analysis_params_key:
                    st.success("✅ 已有分析結果")
                elif should_reanalyze:
                    st.info("🔄 需要重新分析")
                else:
                    st.info("👆 點擊按鈕開始分析")
                    
            with col3:
                # 清除分析結果按鈕
                if st.button("🗑️ 清除分析結果", type="secondary", use_container_width=True, key="clear_analysis"):
                    st.session_state.market_analysis_result = None
                    st.session_state.market_analysis_key = None
                    st.rerun()
        
        else:
            st.warning("請在側邊欄填入 Gemini API 金鑰以使用 AI 分析功能")
        
        # =====================================================
        # 顯示 AI 分析結果
        # =====================================================
        if st.session_state.market_analysis_result and st.session_state.market_analysis_key == analysis_params_key:
            st.markdown("### 📊 AI 分析報告")
            
            # 美化顯示結果
            with st.container():
                st.markdown("---")
                st.markdown(st.session_state.market_analysis_result)
                st.markdown("---")
            
            # 額外提問功能
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
                    # 防爆檢查
                    now = time.time()
                    last = st.session_state.get("last_gemini_question", 0)
                    
                    if now - last < 15:
                        st.warning("⚠️ 提問請等待 15 秒後再試")
                        st.stop()
                    
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
        
        elif should_reanalyze and gemini_key:
            st.info("👆 點擊上方「啟動 AI 分析」按鈕，獲取專業市場分析報告")



# ============================
# 新增：執行比較分析的函數
# ============================
def run_comparison_analysis(
    comparison_mode, 
    selected_houses, 
    fav_df, 
    server_key, 
    gemini_key, 
    radius, 
    keyword, 
    selected_categories, 
    selected_subtypes
):
    """執行房屋比較分析的核心函數"""
    
    # 取得房屋資料
    houses_data = {}
    geocode_results = {}
    
    # 地址解析
    with st.spinner("📍 解析房屋地址中..."):
        for idx, house_option in enumerate(selected_houses):
            house_info = fav_df[(fav_df['標題'] + " | " + fav_df['地址']) == house_option].iloc[0]
            house_name = f"房屋 {chr(65+idx)}"
            
            lat, lng = geocode_address(house_info["地址"], server_key)
            if lat is None or lng is None:
                st.error(f"❌ {house_name} 地址解析失敗")
                return
            
            houses_data[house_name] = {
                "name": house_name,
                "title": house_info['標題'],
                "address": house_info['地址'],
                "lat": lat,
                "lng": lng,
                "original_name": house_info['標題']
            }
            geocode_results[house_name] = (lat, lng)
    
    # 查詢每個房屋的周邊設施
    places_data = {}
    
    for house_name, house_info in houses_data.items():
        with st.spinner(f"🔍 查詢 {house_name} 周邊設施 (半徑: {radius}公尺)..."):
            lat, lng = house_info["lat"], house_info["lng"]
            
            places = query_google_places_keyword(
                lat, lng, server_key, selected_categories, selected_subtypes,
                radius, extra_keyword=keyword
            )
            
            # 檢查缺失設施
            messages = check_places_found(places, selected_categories, selected_subtypes, keyword)
            if messages:
                for msg in messages:
                    st.warning(f"{house_name}: {msg}")
            
            places_data[house_name] = places
    
    # 顯示比較標題
    st.markdown("## 📊 比較結果")
    
    # 統計分析
    st.markdown("---")
    st.subheader("📈 設施統計比較")
    
    # 計算各房屋的設施數量
    facility_counts = {}
    category_counts = {}
    
    for house_name, places in places_data.items():
        total_count = len(places)
        facility_counts[house_name] = total_count
        
        # 計算各類別數量
        cat_counts = {}
        for cat, kw, name, lat, lng, dist, pid in places:
            cat_counts[cat] = cat_counts.get(cat, 0) + 1
        category_counts[house_name] = cat_counts
    
    # 顯示總體統計
    num_houses = len(houses_data)
    stat_cols = st.columns(min(num_houses, 5))
    
    max_facilities = max(facility_counts.values()) if facility_counts else 0
    
    for idx, house_name in enumerate(houses_data.keys()):
        with stat_cols[idx % len(stat_cols)]:
            count = facility_counts.get(house_name, 0)
            house_title = houses_data[house_name]["title"][:20]
            
            # 計算排名
            if max_facilities > 0:
                percentage = (count / max_facilities) * 100 if max_facilities > 0 else 0
            else:
                percentage = 0
            
            st.metric(
                f"🏠 {house_name}",
                f"{count} 個設施",
                f"排名: {sorted(facility_counts.values(), reverse=True).index(count) + 1}/{num_houses}"
            )
            
            if places_data[house_name]:
                nearest = min([p[5] for p in places_data[house_name]])
                st.caption(f"最近設施: {nearest}公尺")
            
            st.caption(f"{house_title}...")
    
    # 如果有超過2個房屋，顯示排名圖表
    if num_houses > 2:
        st.markdown("### 📊 設施數量排名")
        
        # 準備排名資料
        rank_data = sorted(
            [(name, count) for name, count in facility_counts.items()],
            key=lambda x: x[1],
            reverse=True
        )
        
        chart_data = {
            "xAxis": {
                "type": "category",
                "data": [item[0] for item in rank_data]
            },
            "yAxis": {"type": "value"},
            "series": [{
                "type": "bar",
                "data": [item[1] for item in rank_data],
                "itemStyle": {
                    "color": {
                        "type": "linear",
                        "x": 0, "y": 0, "x2": 0, "y2": 1,
                        "colorStops": [
                            {"offset": 0, "color": "#1E90FF"},
                            {"offset": 1, "color": "#87CEFA"}
                        ]
                    }
                }
            }],
            "tooltip": {"trigger": "axis"}
        }
        
        st_echarts(chart_data, height="300px")
    
    # 各類別詳細比較
    st.markdown("### 🏪 各類別設施數量比較")
    
    # 收集所有類別
    all_categories = set()
    for counts in category_counts.values():
        all_categories.update(counts.keys())
    
    if all_categories:
        # 建立比較表格
        comparison_rows = []
        for cat in sorted(all_categories):
            row = {"類別": cat}
            for house_name in houses_data.keys():
                row[house_name] = category_counts[house_name].get(cat, 0)
            comparison_rows.append(row)
        
        comp_df = pd.DataFrame(comparison_rows)
        
        # 顯示表格
        st.dataframe(
            comp_df,
            use_container_width=True,
            hide_index=True
        )
        
        # 顯示類別比較圖表
        if num_houses <= 5:  # 避免圖表太複雜
            chart_data = {
                "xAxis": {
                    "type": "category",
                    "data": comp_df['類別'].tolist()
                },
                "yAxis": {"type": "value"},
                "series": [
                    {
                        "name": house_name,
                        "type": "bar",
                        "data": comp_df[house_name].tolist(),
                        "itemStyle": {"color": f"hsl({idx * 60}, 70%, 50%)"}
                    }
                    for idx, house_name in enumerate(houses_data.keys())
                ],
                "tooltip": {"trigger": "axis"},
                "legend": {"data": list(houses_data.keys())}
            }
            
            st_echarts(chart_data, height="400px")
    
    # 顯示地圖比較
    st.markdown("---")
    st.subheader("🗺️ 地圖比較")
    
    # 根據房屋數量決定地圖顯示方式
    if num_houses <= 3:
        # 並排顯示地圖
        map_cols = st.columns(num_houses)
        for idx, (house_name, house_info) in enumerate(houses_data.items()):
            with map_cols[idx]:
                st.markdown(f"### {house_name}")
                render_map(
                    house_info["lat"], 
                    house_info["lng"], 
                    places_data[house_name], 
                    radius, 
                    title=house_name
                )
                
                # 顯示最近的幾個設施
                if places_data[house_name]:
                    st.markdown("**最近的 3 個設施:**")
                    for i, (cat, kw, name, lat, lng, dist, pid) in enumerate(places_data[house_name][:3]):
                        st.caption(f"{i+1}. {cat}-{kw}: {name} ({dist}公尺)")
    else:
        # 使用選項卡顯示地圖
        map_tabs = st.tabs([f"{house_name}" for house_name in houses_data.keys()])
        
        for idx, (house_name, house_info) in enumerate(houses_data.items()):
            with map_tabs[idx]:
                render_map(
                    house_info["lat"], 
                    house_info["lng"], 
                    places_data[house_name], 
                    radius, 
                    title=house_name
                )
                
                # 顯示最近的幾個設施
                if places_data[house_name]:
                    st.markdown("**最近的 5 個設施:**")
                    for i, (cat, kw, name, lat, lng, dist, pid) in enumerate(places_data[house_name][:5]):
                        st.caption(f"{i+1}. {cat}-{kw}: {name} ({dist}公尺)")
    
    # ============================
    # Gemini AI 分析
    # ============================
    st.markdown("---")
    st.subheader("🤖 AI 智能分析")
    
    # 建立唯一 key
    analysis_key = f"{','.join(selected_houses)}__{keyword}__{','.join(selected_categories)}__{radius}"
    
    # 檢查是否需要重新分析
    should_analyze = (
        "gemini_result" not in st.session_state or
        st.session_state.get("gemini_key") != analysis_key
    )
    
    if should_analyze:
        # 防爆檢查
        now = time.time()
        last = st.session_state.get("last_gemini_call", 0)
        
        if now - last < 30:
            st.warning("⚠️ Gemini 分析請等待 30 秒後再試")
            st.stop()
        
        st.session_state.last_gemini_call = now
        
        with st.spinner("🧠 AI 分析比較結果中..."):
            try:
                genai.configure(api_key=gemini_key)
                model = genai.GenerativeModel("gemini-2.0-flash")
                
                # 準備分析資料
                analysis_text = prepare_multi_comparison_prompt(
                    houses_data, 
                    places_data, 
                    facility_counts, 
                    category_counts,
                    selected_categories,
                    radius,
                    keyword,
                    comparison_mode
                )
                
                # 顯示提示詞預覽
                with st.expander("📝 查看 AI 分析提示詞"):
                    st.text_area("送給 Gemini 的提示詞", analysis_text, height=300)
                
                # 呼叫 Gemini
                resp = model.generate_content(analysis_text)
                
                # 儲存結果
                st.session_state.gemini_result = resp.text
                st.session_state.gemini_key = analysis_key
                st.session_state.places_data = places_data
                st.session_state.houses_data = houses_data
                
                st.success("✅ AI 分析完成！")
                
            except Exception as e:
                st.error(f"❌ Gemini API 錯誤: {str(e)}")
                st.info("請檢查：1. API 金鑰是否正確 2. 配額是否用盡 3. 網路連線是否正常")
                st.stop()
    
    # 顯示分析結果
    if "gemini_result" in st.session_state:
        st.markdown("### 📋 AI 分析報告")
        
        # 美化顯示
        with st.container():
            st.markdown("---")
            st.markdown(st.session_state.gemini_result)
            st.markdown("---")
        
        # 提供下載選項
        report_text = f"""
        房屋比較分析報告
        生成時間：{time.strftime('%Y-%m-%d %H:%M:%S')}
        比較模式：{comparison_mode}
        
        比較房屋 ({len(houses_data)}間):
        """
        
        for house_name, house_info in houses_data.items():
            report_text += f"""
        - {house_name}: {house_info['title']}
          地址：{house_info['address']}
          """
        
        report_text += f"""
        
        搜尋條件：
        - 半徑：{radius} 公尺
        - 選擇類別：{', '.join(selected_categories)}
        - 額外關鍵字：{keyword if keyword else '無'}
        
        AI 分析結果：
        {st.session_state.gemini_result}
        """
        
        st.download_button(
            label="📥 下載分析報告",
            data=report_text,
            file_name=f"房屋比較報告_{time.strftime('%Y%m%d_%H%M%S')}.txt",
            mime="text/plain",
            use_container_width=True
        )


# ============================
# 新增：準備多房屋比較的提示詞
# ============================
def prepare_multi_comparison_prompt(
    houses_data, 
    places_data, 
    facility_counts, 
    category_counts,
    selected_categories,
    radius,
    keyword,
    comparison_mode
):
    """準備多房屋比較的 AI 提示詞"""
    
    # 統計摘要
    stats_summary = "統計摘要：\n"
    for house_name, count in facility_counts.items():
        if places_data[house_name]:
            nearest = min([p[5] for p in places_data[house_name]])
            stats_summary += f"- {house_name}：共 {count} 個設施，最近設施 {nearest} 公尺\n"
        else:
            stats_summary += f"- {house_name}：共 0 個設施\n"
    
    # 排名
    ranked_houses = sorted(facility_counts.items(), key=lambda x: x[1], reverse=True)
    ranking_text = "設施數量排名：\n"
    for rank, (house_name, count) in enumerate(ranked_houses, 1):
        ranking_text += f"第{rank}名：{house_name} ({count}個設施)\n"
    
    # 各類別比較
    category_comparison = "各類別設施比較：\n"
    all_categories = set()
    for counts in category_counts.values():
        all_categories.update(counts.keys())
    
    for cat in sorted(all_categories):
        category_comparison += f"\n【{cat}】\n"
        for house_name in houses_data.keys():
            count = category_counts[house_name].get(cat, 0)
            category_comparison += f"- {house_name}: {count} 個設施\n"
    
    # 房屋詳細資訊
    houses_details = "房屋詳細資訊：\n"
    for house_name, house_info in houses_data.items():
        houses_details += f"""
        {house_name}:
        - 標題：{house_info['title']}
        - 地址：{house_info['address']}
        """
    
    # 建構提示詞
    prompt = f"""
    你是一位專業的房地產分析師，請根據以下{len(houses_data)}間房屋的生活機能進行比較分析。
    
    【分析要求】
    1. 請以中文繁體回應
    2. 從「自住」和「投資」兩個角度分析
    3. 考慮各類生活設施的完整性與距離
    4. 提供具體建議與風險提示
    5. 請進行排名比較並說明原因
    
    【搜尋條件】
    - 搜尋半徑：{radius} 公尺
    - 選擇的生活機能類別：{', '.join(selected_categories)}
    - 額外關鍵字：{keyword if keyword else '無'}
    - 比較模式：{comparison_mode}
    
    {houses_details}
    
    【設施統計】
    {stats_summary}
    
    {ranking_text}
    
    {category_comparison}
    
    【請依序分析】
    1. 總體設施豐富度比較與排名
    2. 各類別設施完整性分析（教育、購物、交通、健康、餐飲等）
    3. 生活便利性綜合評估
    4. 對「自住者」的建議（哪間最適合，排名與原因）
    5. 對「投資者」的建議（哪間最有潛力，排名與原因）
    6. 各房屋的優缺點分析
    7. 潛在缺點與風險提醒
    8. 綜合結論與推薦排名
    
    請使用專業但易懂的語言，並提供具體的判斷依據。
    對於每個房屋，請給予1-5星的評分（⭐為單位）。
    """
    
    return prompt
        
        # 範例：顯示基本統計
        st.write(f"不動產資料筆數: {len(self.combined_df)}")
        st.write(f"人口資料筆數: {len(self.population_df)}")
