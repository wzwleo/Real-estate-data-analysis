import streamlit as st
import pandas as pd
import time
import google.generativeai as genai
from streamlit_echarts import st_echarts
from page_modules.analysis_page import (
    get_favorites_data, _get_server_key, _get_browser_key,
    geocode_address, query_google_places_keyword, 
    check_places_found, render_map, PLACE_TYPES,
    CATEGORY_COLORS, ENGLISH_TO_CHINESE
)

def house_comparison_module():
    """房屋比較模組 - 對應 Tab2"""
    st.subheader("🏠 房屋比較（Google Places + Gemini 分析）")

    fav_df = get_favorites_data()
    if fav_df.empty:
        st.info("⭐ 尚未有收藏房產，無法比較")
        return
    
    # 房屋選擇部分
    options = fav_df['標題'] + " | " + fav_df['地址']
    c1, c2 = st.columns(2)
    with c1:
        choice_a = st.selectbox("選擇房屋 A", options, key="compare_a")
    with c2:
        choice_b = st.selectbox("選擇房屋 B", options, key="compare_b")

    # 顯示選擇的房屋資訊
    if choice_a and choice_b:
        house_a = fav_df[(fav_df['標題'] + " | " + fav_df['地址']) == choice_a].iloc[0]
        house_b = fav_df[(fav_df['標題'] + " | " + fav_df['地址']) == choice_b].iloc[0]
        
        col_info1, col_info2 = st.columns(2)
        with col_info1:
            st.markdown(f"**房屋 A**")
            st.markdown(f"📍 {house_a['地址']}")
            st.markdown(f"🏷️ {house_a['標題']}")
        
        with col_info2:
            st.markdown(f"**房屋 B**")
            st.markdown(f"📍 {house_b['地址']}")
            st.markdown(f"🏷️ {house_b['標題']}")

    # 設定部分
    server_key = _get_server_key()
    gemini_key = st.session_state.get("GEMINI_KEY", "")
    radius = st.slider("搜尋半徑 (公尺)", 100, 2000, 500, 100, key="radius_slider")
    keyword = st.text_input("額外關鍵字搜尋 (可選)", key="extra_keyword", 
                          placeholder="例如：公園、健身房、銀行等")

    # 生活機能選擇器
    selected_categories, selected_subtypes = render_facility_selector()
    
    # 開始比較按鈕
    st.markdown("---")
    if st.button("🚀 開始比較", type="primary", use_container_width=True, key="start_comparison"):
        perform_comparison(
            choice_a, choice_b, house_a, house_b,
            server_key, gemini_key, radius, keyword,
            selected_categories, selected_subtypes
        )

def render_facility_selector():
    """渲染生活機能選擇器"""
    st.markdown("---")
    st.subheader("🔍 選擇生活機能類別")
    
    selected_categories = []
    selected_subtypes = {}
    
    # 建立大類別選擇器
    st.markdown("### 選擇大類別")
    all_categories = list(PLACE_TYPES.keys())
    cols = st.columns(len(all_categories))
    
    category_selection = {}
    for i, cat in enumerate(all_categories):
        with cols[i]:
            color = CATEGORY_COLORS.get(cat, "#000000")
            st.markdown(f'<span style="background-color:{color}; color:white; padding:5px 10px; border-radius:5px;">{cat}</span>', unsafe_allow_html=True)
            category_selection[cat] = st.checkbox(f"選擇{cat}", key=f"main_cat_{cat}_{i}")
    
    # 細分選項
    selected_main_cats = [cat for cat, selected in category_selection.items() if selected]
    
    if selected_main_cats:
        st.markdown("### 選擇細分設施")
        
        for cat_idx, cat in enumerate(selected_main_cats):
            with st.expander(f"📁 {cat} 類別細選", expanded=True):
                select_all = st.checkbox(f"選擇所有{cat}設施", key=f"select_all_{cat}_{cat_idx}")
                
                if select_all:
                    items = PLACE_TYPES[cat]
                    selected_subtypes[cat] = items[1::2]
                    selected_categories.append(cat)
                    st.info(f"已選擇 {cat} 全部 {len(items)//2} 種設施")
                else:
                    items = PLACE_TYPES[cat]
                    for i in range(0, len(items), 2):
                        if i+1 < len(items):
                            chinese_name = items[i]
                            english_keyword = items[i+1]
                            
                            checkbox_key = f"facility_{cat}_{english_keyword}_{i}"
                            if st.checkbox(chinese_name, key=checkbox_key):
                                if cat not in selected_subtypes:
                                    selected_subtypes[cat] = []
                                selected_subtypes[cat].append(english_keyword)
                
                if cat in selected_subtypes and selected_subtypes[cat]:
                    selected_categories.append(cat)
    
    # 顯示選擇摘要
    if selected_categories:
        render_selection_summary(selected_categories, selected_subtypes)
    
    return selected_categories, selected_subtypes

def render_selection_summary(selected_categories, selected_subtypes):
    """顯示選擇摘要"""
    st.markdown("---")
    st.subheader("📋 已選擇的設施摘要")
    
    summary_cols = st.columns(min(len(selected_categories), 3))
    for idx, cat in enumerate(selected_categories):
        with summary_cols[idx % len(summary_cols)]:
            if cat in selected_subtypes:
                count = len(selected_subtypes[cat])
                color = CATEGORY_COLORS.get(cat, "#000000")
                st.markdown(f"""
                <div style="background-color:{color}20; padding:10px; border-radius:5px; border-left:4px solid {color};">
                <h4 style="color:{color}; margin:0;">{cat}</h4>
                <p style="margin:5px 0 0 0;">已選擇 {count} 種設施</p>
                </div>
                """, unsafe_allow_html=True)
                
                # 顯示前幾個項目
                chinese_names = []
                for english_kw in selected_subtypes[cat][:5]:
                    if english_kw in ENGLISH_TO_CHINESE:
                        chinese_names.append(ENGLISH_TO_CHINESE[english_kw])
                    else:
                        chinese_names.append(english_kw)
                
                if count <= 5:
                    items_display = "、".join(chinese_names)
                    st.caption(f"✓ {items_display}")
                else:
                    items_display = "、".join(chinese_names[:3])
                    st.caption(f"✓ {items_display}等{count}種設施")

def perform_comparison(choice_a, choice_b, house_a, house_b, server_key, gemini_key, 
                      radius, keyword, selected_categories, selected_subtypes):
    """執行房屋比較"""
    # 驗證檢查
    if not _get_browser_key():
        st.error("❌ 請在側邊欄填入 Google Maps **Browser Key**")
        return
    if not server_key or not gemini_key:
        st.error("❌ 請在側邊欄填入 Server Key 與 Gemini Key")
        return
    if choice_a == choice_b:
        st.warning("⚠️ 請選擇兩個不同房屋")
        return
    if not selected_categories:
        st.warning("⚠️ 請至少選擇一個生活機能類別")
        return

    # 地址解析
    with st.spinner("📍 解析房屋地址中..."):
        lat_a, lng_a = geocode_address(house_a["地址"], server_key)
        lat_b, lng_b = geocode_address(house_b["地址"], server_key)

    if lat_a is None or lat_b is None:
        st.error("❌ 地址解析失敗，請檢查地址格式或 Server Key 限制。")
        return

    # 查詢設施
    places_a, places_b = query_facilities(
        lat_a, lng_a, lat_b, lng_b, server_key,
        selected_categories, selected_subtypes, radius, keyword
    )
    
    # 顯示比較結果
    render_comparison_results(
        house_a, house_b, places_a, places_b, radius,
        lat_a, lng_a, lat_b, lng_b,
        selected_categories, keyword, gemini_key
    )

def query_facilities(lat_a, lng_a, lat_b, lng_b, server_key,
                    selected_categories, selected_subtypes, radius, keyword):
    """查詢兩個房屋的周邊設施"""
    places_a, places_b = [], []
    
    # 查詢房屋A周邊
    with st.spinner(f"🔍 查詢房屋 A 周邊設施 (半徑: {radius}公尺)..."):
        places_a = query_google_places_keyword(
            lat_a, lng_a, server_key, selected_categories, selected_subtypes,
            radius, extra_keyword=keyword
        )
        messages_a = check_places_found(places_a, selected_categories, selected_subtypes, keyword)
        if messages_a:
            for msg in messages_a:
                st.warning(f"房屋 A: {msg}")

    # 查詢房屋B周邊
    with st.spinner(f"🔍 查詢房屋 B 周邊設施 (半徑: {radius}公尺)..."):
        places_b = query_google_places_keyword(
            lat_b, lng_b, server_key, selected_categories, selected_subtypes,
            radius, extra_keyword=keyword
        )
        messages_b = check_places_found(places_b, selected_categories, selected_subtypes, keyword)
        if messages_b:
            for msg in messages_b:
                st.warning(f"房屋 B: {msg}")
    
    return places_a, places_b

def render_comparison_results(house_a, house_b, places_a, places_b, radius,
                             lat_a, lng_a, lat_b, lng_b,
                             selected_categories, keyword, gemini_key):
    """渲染比較結果"""
    # 顯示比較標題
    st.markdown("## 📊 比較結果")
    
    # 設施統計比較
    render_facility_statistics(places_a, places_b, radius)
    
    # 類別詳細比較
    render_category_comparison(places_a, places_b)
    
    # 地圖比較
    render_map_comparison(lat_a, lng_a, lat_b, lng_b, places_a, places_b, radius)
    
    # AI 分析
    if gemini_key:
        render_gemini_analysis(
            house_a, house_b, places_a, places_b,
            radius, selected_categories, keyword, gemini_key
        )

def render_facility_statistics(places_a, places_b, radius):
    """渲染設施統計"""
    st.markdown("---")
    st.subheader("📈 設施統計比較")
    
    def count_by_category(places):
        counts = {}
        for cat, kw, name, lat, lng, dist, pid in places:
            counts[cat] = counts.get(cat, 0) + 1
        return counts
    
    counts_a = count_by_category(places_a)
    counts_b = count_by_category(places_b)
    
    # 顯示統計圖表
    stat_cols = st.columns(3)
    with stat_cols[0]:
        st.metric("🏠 房屋 A", f"{len(places_a)} 個設施", f"半徑 {radius}公尺")
        if places_a:
            st.caption("最近設施: " + str(min([p[5] for p in places_a])) + "公尺")
    
    with stat_cols[1]:
        difference = len(places_a) - len(places_b)
        st.metric("🏠 房屋 B", f"{len(places_b)} 個設施", f"{difference:+d} 差異")
        if places_b:
            st.caption("最近設施: " + str(min([p[5] for p in places_b])) + "公尺")
    
    with stat_cols[2]:
        total_found = len(places_a) + len(places_b)
        st.metric("🔍 總計找到", f"{total_found} 個設施", 
                 f"{len(set([p[6] for p in places_a + places_b]))} 個不重複地點")

def render_category_comparison(places_a, places_b):
    """渲染類別詳細比較"""
    st.markdown("### 各類別設施數量")
    
    def count_by_category(places):
        counts = {}
        for cat, kw, name, lat, lng, dist, pid in places:
            counts[cat] = counts.get(cat, 0) + 1
        return counts
    
    counts_a = count_by_category(places_a)
    counts_b = count_by_category(places_b)
    
    all_cats = set(list(counts_a.keys()) + list(counts_b.keys()))
    
    comparison_data = []
    for cat in all_cats:
        a_count = counts_a.get(cat, 0)
        b_count = counts_b.get(cat, 0)
        color = CATEGORY_COLORS.get(cat, "#CCCCCC")
        comparison_data.append({
            "類別": cat,
            "房屋A": a_count,
            "房屋B": b_count,
            "顏色": color
        })
    
    if comparison_data:
        comp_df = pd.DataFrame(comparison_data)
        comp_df = comp_df.sort_values("房屋A", ascending=False)
        
        # 顯示表格
        st.dataframe(comp_df[['類別', '房屋A', '房屋B']], use_container_width=True, hide_index=True)
        
        # 顯示條形圖
        chart_data = {
            "xAxis": {"type": "category", "data": comp_df['類別'].tolist()},
            "yAxis": {"type": "value"},
            "series": [
                {"name": "房屋 A", "type": "bar", "data": comp_df['房屋A'].tolist(), "itemStyle": {"color": "#1E90FF"}},
                {"name": "房屋 B", "type": "bar", "data": comp_df['房屋B'].tolist(), "itemStyle": {"color": "#FF8C00"}}
            ],
            "tooltip": {"trigger": "axis"},
            "legend": {"data": ["房屋 A", "房屋 B"]}
        }
        
        st_echarts(chart_data, height="400px")

def render_map_comparison(lat_a, lng_a, lat_b, lng_b, places_a, places_b, radius):
    """渲染地圖比較"""
    st.markdown("---")
    st.subheader("🗺️ 地圖比較")
    map_cols = st.columns(2)
    with map_cols[0]:
        st.markdown(f"### 房屋 A")
        render_map(lat_a, lng_a, places_a, radius, title="房屋 A")
        
        if places_a:
            st.markdown("**最近的 5 個設施:**")
            for i, (cat, kw, name, lat, lng, dist, pid) in enumerate(places_a[:5]):
                st.caption(f"{i+1}. {cat}-{kw}: {name} ({dist}公尺)")
    
    with map_cols[1]:
        st.markdown(f"### 房屋 B")
        render_map(lat_b, lng_b, places_b, radius, title="房屋 B")
        
        if places_b:
            st.markdown("**最近的 5 個設施:**")
            for i, (cat, kw, name, lat, lng, dist, pid) in enumerate(places_b[:5]):
                st.caption(f"{i+1}. {cat}-{kw}: {name} ({dist}公尺)")

def render_gemini_analysis(house_a, house_b, places_a, places_b, 
                          radius, selected_categories, keyword, gemini_key):
    """渲染 Gemini AI 分析"""
    st.markdown("---")
    st.subheader("🤖 AI 智能分析")
    
    # 建立唯一 key
    analysis_key = f"{house_a['標題']}__{house_b['標題']}__{keyword}__{','.join(selected_categories)}__{radius}"
    
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
            return
        
        st.session_state.last_gemini_call = now
        
        with st.spinner("🧠 AI 分析比較結果中..."):
            try:
                genai.configure(api_key=gemini_key)
                model = genai.GenerativeModel("gemini-2.0-flash")
                
                # 準備分析資料
                analysis_text = prepare_analysis_text(
                    house_a, house_b, places_a, places_b,
                    radius, selected_categories, keyword
                )
                
                # 呼叫 Gemini
                resp = model.generate_content(analysis_text)
                
                # 儲存結果
                st.session_state.gemini_result = resp.text
                st.session_state.gemini_key = analysis_key
                
                st.success("✅ AI 分析完成！")
                
            except Exception as e:
                st.error(f"❌ Gemini API 錯誤: {str(e)}")
                return
    
    # 顯示分析結果
    if "gemini_result" in st.session_state:
        render_analysis_report(house_a, house_b, radius, selected_categories, keyword)

def prepare_analysis_text(house_a, house_b, places_a, places_b, radius, selected_categories, keyword):
    """準備 AI 分析文本"""
    def format_places_for_ai(places, house_name, limit=20):
        if not places:
            return f"{house_name}：周圍 500 公尺內未找到任何選定的生活設施。"
        
        text = f"{house_name} 找到 {len(places)} 個設施：\n"
        by_category = {}
        for cat, kw, name, lat, lng, dist, pid in places[:limit]:
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(f"- {kw}：{name}（距離 {dist} 公尺）")
        
        for cat, items in by_category.items():
            text += f"\n【{cat}】\n"
            text += "\n".join(items[:5])
            if len(items) > 5:
                text += f"\n...及其他 {len(items)-5} 個設施"
        
        return text
    
    places_a_text = format_places_for_ai(places_a, "房屋 A")
    places_b_text = format_places_for_ai(places_b, "房屋 B")
    
    stats_summary = f"""
    統計摘要：
    - 房屋 A：共 {len(places_a)} 個設施，最近設施 {min([p[5] for p in places_a]) if places_a else 0} 公尺
    - 房屋 B：共 {len(places_b)} 個設施，最近設施 {min([p[5] for p in places_b]) if places_b else 0} 公尺
    - 設施差異：房屋 A 比房屋 B {'多' if len(places_a) > len(places_b) else '少'} {abs(len(places_a)-len(places_b))} 個設施
    """
    
    prompt = f"""
    你是一位專業的房地產分析師，請根據以下兩間房屋的生活機能進行比較分析。
    
    【分析要求】
    1. 請以中文繁體回應
    2. 從「自住」和「投資」兩個角度分析
    3. 考慮各類生活設施的完整性與距離
    4. 提供具體建議與風險提示
    
    【搜尋條件】
    - 搜尋半徑：{radius} 公尺
    - 選擇的生活機能類別：{', '.join(selected_categories)}
    - 額外關鍵字：{keyword if keyword else '無'}
    
    【房屋基本資訊】
    - 房屋 A：{house_a['標題']}，地址：{house_a['地址']}
    - 房屋 B：{house_b['標題']}，地址：{house_b['地址']}
    
    【設施統計】
    {stats_summary}
    
    【房屋 A 周邊設施】
    {places_a_text}
    
    【房屋 B 周邊設施】
    {places_b_text}
    
    【請依序分析】
    1. 總體設施豐富度比較
    2. 各類別設施完整性分析（教育、購物、交通、健康、餐飲）
    3. 生活便利性評估
    4. 對「自住者」的建議（哪間更適合，為什麼）
    5. 對「投資者」的建議（哪間更有潛力，為什麼）
    6. 潛在缺點與風險提醒
    7. 綜合結論與推薦
    
    請使用專業但易懂的語言，並提供具體的判斷依據。
    """
    
    return prompt

def render_analysis_report(house_a, house_b, radius, selected_categories, keyword):
    """渲染分析報告"""
    st.markdown("### 📋 AI 分析報告")
    
    with st.container():
        st.markdown("---")
        st.markdown(st.session_state.gemini_result)
        st.markdown("---")
    
    # 提供下載選項
    report_text = f"""
    房屋比較分析報告
    生成時間：{time.strftime('%Y-%m-%d %H:%M:%S')}
    
    比較房屋：
    - 房屋 A：{house_a['標題']}，地址：{house_a['地址']}
    - 房屋 B：{house_b['標題']}，地址：{house_b['地址']}
    
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
