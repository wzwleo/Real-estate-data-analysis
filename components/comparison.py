# components/comparison.py
import streamlit as st
import pandas as pd
import time
import json
import sys
import os
import requests
import math
from string import Template
from streamlit.components.v1 import html
from streamlit_echarts import st_echarts

# 修正匯入路徑
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

try:
    from config import CATEGORY_COLORS, DEFAULT_RADIUS
    from components.place_types import PLACE_TYPES, ENGLISH_TO_CHINESE
    from components.geocoding import geocode_address, haversine
    CONFIG_LOADED = True
except ImportError as e:
    CONFIG_LOADED = False
    st.warning(f"無法載入設定: {e}")


class ComparisonAnalyzer:
    """房屋比較分析器"""
    
    def __init__(self):
        pass
    
    def render_comparison_tab(self):
        """渲染比較頁面"""
        st.subheader("🏠 房屋比較（單獨或多個比較）")
        
        # 檢查是否有收藏
        fav_df = self._get_favorites_data()
        if fav_df.empty:
            st.info("⭐ 尚未有收藏房產，無法比較")
            return
        
        # 模式選擇
        comparison_mode = st.radio(
            "選擇比較模式",
            ["單獨比較（2個房屋）", "多個比較（2個以上房屋）"],
            horizontal=True,
            key="comparison_mode"
        )
        
        options = fav_df['標題'] + " | " + fav_df['地址']
        selected_houses = []
        
        if comparison_mode == "單獨比較（2個房屋）":
            # 單獨比較模式
            c1, c2 = st.columns(2)
            with c1:
                choice_a = st.selectbox("選擇房屋 A", options, key="compare_a")
            with c2:
                choice_b = st.selectbox("選擇房屋 B", options, key="compare_b")
            
            if choice_a and choice_b:
                if choice_a == choice_b:
                    st.warning("⚠️ 請選擇兩個不同房屋")
                    return
                selected_houses = [choice_a, choice_b]
                
                # 顯示選擇的房屋資訊
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
        else:
            # 多個比較模式
            selected_houses = st.multiselect(
                "選擇要比較的房屋（至少選擇2個）",
                options,
                default=options[:min(3, len(options))] if len(options) >= 2 else [],
                key="multi_compare"
            )
            
            if len(selected_houses) < 2:
                st.warning("⚠️ 請至少選擇2個房屋進行比較")
                return
            
            # 顯示已選房屋的預覽
            if selected_houses:
                st.markdown("### 📋 已選房屋清單")
                
                # 分列顯示
                num_columns = min(3, len(selected_houses))
                cols = st.columns(num_columns)
                
                for idx, house_option in enumerate(selected_houses):
                    with cols[idx % num_columns]:
                        house_info = fav_df[(fav_df['標題'] + " | " + fav_df['地址']) == house_option].iloc[0]
                        st.markdown(f"""
                        <div style="border:1px solid #ddd; padding:10px; border-radius:5px; margin-bottom:10px;">
                        <strong>房屋 {chr(65+idx)}</strong><br>
                        📍 {house_info['地址'][:30]}...<br>
                        🏷️ {house_info['標題'][:25]}...
                        </div>
                        """, unsafe_allow_html=True)
                
                st.caption(f"已選擇 {len(selected_houses)} 間房屋進行比較")
        
        # 基本設定
        st.markdown("---")
        st.subheader("⚙️ 比較設定")
        
        # 取得 API Keys
        server_key = self._get_server_key()
        gemini_key = self._get_gemini_key()
        browser_key = self._get_browser_key()
        
        radius = st.slider("搜尋半徑 (公尺)", 100, 2000, DEFAULT_RADIUS, 100, key="radius_slider")
        keyword = st.text_input("額外關鍵字搜尋 (可選)", key="extra_keyword", 
                              placeholder="例如：公園、健身房、銀行等")
        
        # 生活機能選擇
        st.markdown("---")
        st.subheader("🔍 選擇生活機能類別")
        
        selected_categories = []
        selected_subtypes = {}
        
        # 大類別選擇
        st.markdown("### 選擇大類別")
        all_categories = list(PLACE_TYPES.keys())
        cols = st.columns(len(all_categories))
        
        category_selection = {}
        for i, cat in enumerate(all_categories):
            with cols[i]:
                color = CATEGORY_COLORS.get(cat, "#000000")
                st.markdown(f'<span style="background-color:{color}; color:white; padding:5px 10px; border-radius:5px;">{cat}</span>', unsafe_allow_html=True)
                category_selection[cat] = st.checkbox(f"選擇{cat}", key=f"main_cat_{cat}_{i}")
        
        # 細分設施選擇
        selected_main_cats = [cat for cat, selected in category_selection.items() if selected]
        
        if selected_main_cats:
            st.markdown("### 選擇細分設施")
            
            for cat_idx, cat in enumerate(selected_main_cats):
                with st.expander(f"📁 {cat} 類別細選", expanded=True):
                    select_all = st.checkbox(f"選擇所有{cat}設施", key=f"select_all_{cat}_{cat_idx}")
                    
                    if select_all:
                        # 選中所有子項目
                        items = PLACE_TYPES[cat]
                        selected_subtypes[cat] = items[1::2]  # 英文關鍵字
                        selected_categories.append(cat)
                        
                        st.info(f"已選擇 {cat} 全部 {len(items)//2} 種設施")
                    else:
                        # 逐個子項目選擇
                        items = PLACE_TYPES[cat]
                        num_columns = 3
                        num_items = len(items) // 2
                        
                        # 計算每列要顯示的項目數
                        items_per_row = (num_items + num_columns - 1) // num_columns
                        
                        for row in range(items_per_row):
                            cols = st.columns(num_columns)
                            for col_idx in range(num_columns):
                                item_idx = row + col_idx * items_per_row
                                if item_idx * 2 + 1 < len(items):
                                    chinese_name = items[item_idx * 2]  # 中文名稱
                                    english_keyword = items[item_idx * 2 + 1]  # 英文關鍵字
                                    
                                    with cols[col_idx]:
                                        # 確保每個checkbox有唯一的key
                                        checkbox_key = f"tab2_{cat}_{english_keyword}_{row}_{col_idx}"
                                        if st.checkbox(chinese_name, key=checkbox_key):
                                            if cat not in selected_subtypes:
                                                selected_subtypes[cat] = []
                                            selected_subtypes[cat].append(english_keyword)
                    
                    # 如果有選中任何子項目，就加入主類別
                    if cat in selected_subtypes and selected_subtypes[cat]:
                        selected_categories.append(cat)
        
        # 顯示選擇摘要
        if selected_categories:
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
        
        # 開始比較按鈕
        st.markdown("---")
        col_start, col_clear = st.columns([3, 1])
        
        with col_start:
            if st.button("🚀 開始比較", type="primary", use_container_width=True, key="start_comparison"):
                # 驗證檢查
                if not browser_key:
                    st.error("❌ 請在側邊欄填入 Google Maps **Browser Key**")
                    return
                if not server_key or not gemini_key:
                    st.error("❌ 請在側邊欄填入 Server Key 與 Gemini Key")
                    return
                
                # 根據模式進行不同檢查
                if comparison_mode == "單獨比較（2個房屋）":
                    if 'choice_a' in locals() and 'choice_b' in locals():
                        if choice_a == choice_b:
                            st.warning("⚠️ 請選擇兩個不同房屋")
                            return
                
                if not selected_categories:
                    st.warning("⚠️ 請至少選擇一個生活機能類別")
                    return
                
                if not selected_houses:
                    st.warning("⚠️ 請選擇要比較的房屋")
                    return

                # 執行比較
                self._run_comparison_analysis(
                    comparison_mode, 
                    selected_houses, 
                    fav_df, 
                    server_key, 
                    gemini_key, 
                    radius, 
                    keyword, 
                    selected_categories, 
                    selected_subtypes
                )
        
        with col_clear:
            if st.button("🗑️ 清除結果", type="secondary", use_container_width=True, key="clear_results"):
                # 清除比較相關的 session state
                keys_to_clear = ['gemini_result', 'gemini_key', 'places_data', 'houses_data']
                for key in keys_to_clear:
                    if key in st.session_state:
                        del st.session_state[key]
                st.rerun()
    
    def _get_favorites_data(self):
        """取得收藏的房屋資料"""
        if 'favorites' not in st.session_state or not st.session_state.favorites:
            return pd.DataFrame()
        
        all_df = None
        if 'all_properties_df' in st.session_state and not st.session_state.all_properties_df.empty:
            all_df = st.session_state.all_properties_df
        elif 'filtered_df' in st.session_state and not st.session_state.filtered_df.empty:
            all_df = st.session_state.filtered_df
        
        if all_df is None or all_df.empty:
            return pd.DataFrame()
        
        fav_ids = st.session_state.favorites
        fav_df = all_df[all_df['編號'].astype(str).isin(map(str, fav_ids))].copy()
        return fav_df
    
    def _get_server_key(self):
        """取得 Google Maps Server Key"""
        return st.session_state.get("GMAPS_SERVER_KEY") or st.session_state.get("GOOGLE_MAPS_KEY", "")
    
    def _get_browser_key(self):
        """取得 Google Maps Browser Key"""
        return st.session_state.get("GMAPS_BROWSER_KEY") or st.session_state.get("GOOGLE_MAPS_KEY", "")
    
    def _get_gemini_key(self):
        """取得 Gemini API Key"""
        return st.session_state.get("GEMINI_KEY", "")
    
    def _search_text_google_places(self, lat, lng, api_key, keyword, radius=500):
        """搜尋Google Places（使用中文關鍵字）"""
        url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
        params = {
            "query": keyword,
            "location": f"{lat},{lng}",
            "radius": radius,
            "key": api_key,
            "language": "zh-TW"
        }

        try:
            r = requests.get(url, params=params, timeout=10).json()
        except Exception as e:
            st.warning(f"❌ 關鍵字 {keyword} 查詢失敗: {e}")
            return []

        results = []
        for p in r.get("results", []):
            loc = p["geometry"]["location"]
            dist = int(haversine(lat, lng, loc["lat"], loc["lng"]))
            
            # 關鍵字本身就是中文，直接使用
            results.append((
                "關鍵字",
                keyword,  # 直接使用中文關鍵字
                p.get("name", "未命名"),
                loc["lat"],
                loc["lng"],
                dist,
                p.get("place_id", "")
            ))
        return results
    
    def _query_google_places_keyword(self, lat, lng, api_key, selected_categories, selected_subtypes, radius=500, extra_keyword=""):
        """查詢Google Places關鍵字"""
        results, seen = [], set()
        
        total_tasks = 0
        for cat in selected_categories:
            if cat in selected_subtypes:
                total_tasks += len(selected_subtypes[cat])
        total_tasks += (1 if extra_keyword else 0)

        if total_tasks == 0:
            st.warning("⚠️ 請至少選擇一個搜尋項目")
            return []

        progress = st.progress(0)
        progress_text = st.empty()
        completed = 0

        def update_progress(task_desc):
            nonlocal completed
            completed += 1
            progress.progress(min(completed / total_tasks, 1.0))
            progress_text.text(f"進度：{completed}/{total_tasks} - {task_desc}")

        for cat in selected_categories:
            if cat not in selected_subtypes:
                continue
                
            for chinese_kw in selected_subtypes[cat]:  # 現在是中文關鍵字
                update_progress(f"查詢 {cat}-{chinese_kw}")
                
                try:
                    places = self._search_text_google_places(lat, lng, api_key, chinese_kw, radius)
                    
                    for p in places:
                        if p[5] > radius:
                            continue
                        pid = p[6]
                        if pid in seen:
                            continue
                        seen.add(pid)
                        results.append((cat, chinese_kw, p[2], p[3], p[4], p[5], p[6]))

                    time.sleep(0.5)
                    
                except Exception as e:
                    st.warning(f"查詢 {chinese_kw} 時發生錯誤: {str(e)[:50]}")
                    continue

        if extra_keyword:
            update_progress(f"額外關鍵字: {extra_keyword}")
            try:
                places = self._search_text_google_places(lat, lng, api_key, extra_keyword, radius)
                for p in places:
                    if p[5] > radius:
                        continue
                    pid = p[6]
                    if pid in seen:
                        continue
                    seen.add(pid)
                    results.append(("關鍵字", extra_keyword, p[2], p[3], p[4], p[5], p[6]))
                    
                time.sleep(0.3)
            except Exception as e:
                st.warning(f"查詢額外關鍵字時發生錯誤: {str(e)[:50]}")

        progress.progress(1.0)
        progress_text.text("✅ 查詢完成！")
        results.sort(key=lambda x: x[5])
        return results
    
    def _check_places_found(self, places, selected_categories, selected_subtypes, extra_keyword):
        """檢查是否找到所有選擇的設施"""
        # 建立檢查字典：類別 -> 子項目 -> 是否找到
        found_dict = {}
        for cat in selected_categories:
            if cat in selected_subtypes:
                found_dict[cat] = {subtype: False for subtype in selected_subtypes[cat]}
        
        extra_found = False

        for cat, kw, name, lat, lng, dist, pid in places:
            if cat in found_dict and kw in found_dict[cat]:
                found_dict[cat][kw] = True
            if extra_keyword and cat == "關鍵字" and kw == extra_keyword:
                extra_found = True

        messages = []
        for cat, subtypes in found_dict.items():
            for subtype, found in subtypes.items():
                if not found:
                    messages.append(f"⚠️ 周圍沒有 {cat} → {subtype}")

        if extra_keyword and not extra_found:
            messages.append(f"⚠️ 周圍沒有關鍵字「{extra_keyword}」的設施")

        return messages
    
    def _render_map(self, lat, lng, places, radius, title="房屋"):
        """渲染地圖"""
        browser_key = self._get_browser_key()

        data = []
        for cat, kw, name, p_lat, p_lng, dist, pid in places:
            data.append({
                "cat": cat,
                "kw": kw,
                "name": name,
                "lat": p_lat,
                "lng": p_lng,
                "dist": dist,
                "pid": pid,
                "color": CATEGORY_COLORS.get(cat, "#000000")
            })

        data_json = json.dumps(data, ensure_ascii=False)

        tpl = Template("""
               <div id="map" style="height:400px;"></div>
               <script>
               function initMap() {
                   var center = {lat: $LAT, lng: $LNG};
                   var map = new google.maps.Map(document.getElementById('map'), {
                       zoom: 16,
                       center: center
                   });
                   new google.maps.Marker({position: center, map: map, title: "$TITLE"});

                   var data = $DATA_JSON;
                   data.forEach(function(p){
                       var info = p.cat + "-" + p.kw + ": " + p.name +
                                  "<br>距離中心 " + p.dist + " 公尺";

                       var marker = new google.maps.Marker({
                           position: {lat: p.lat, lng: p.lng},
                           map: map,
                           icon: {
                               path: google.maps.SymbolPath.CIRCLE,
                               scale: 6,
                               fillColor: p.color,
                               fillOpacity: 1,
                               strokeWeight: 1
                           },
                           title: p.cat + "-" + p.name
                       });

                       marker.addListener("click", function(){
                           new google.maps.InfoWindow({content: info}).open(map, marker);
                       });
                   });

                   new google.maps.Circle({
                       strokeColor:"#FF0000",
                       strokeOpacity:0.8,
                       strokeWeight:2,
                       fillColor:"#FF0000",
                       fillOpacity:0.1,
                       map: map,
                       center: center,
                       radius: $RADIUS
                   });
               }
               </script>
               <script src="https://maps.googleapis.com/maps/api/js?key=$BROWSER_KEY&callback=initMap" async defer></script>
           """)

        map_html = tpl.substitute(
            LAT=lat,
            LNG=lng,
            TITLE=title,
            DATA_JSON=data_json,
            RADIUS=radius,
            BROWSER_KEY=browser_key
        )
        html(map_html, height=400)
    
    def _prepare_multi_comparison_prompt(self, houses_data, places_data, facility_counts, 
                                       category_counts, selected_categories, radius, 
                                       keyword, comparison_mode):
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
    
    def _run_comparison_analysis(self, comparison_mode, selected_houses, fav_df, 
                                server_key, gemini_key, radius, keyword, 
                                selected_categories, selected_subtypes):
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
                
                places = self._query_google_places_keyword(
                    lat, lng, server_key, selected_categories, selected_subtypes,
                    radius, extra_keyword=keyword
                )
                
                # 檢查缺失設施
                messages = self._check_places_found(places, selected_categories, selected_subtypes, keyword)
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
                    self._render_map(
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
                    self._render_map(
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
                return
            
            st.session_state.last_gemini_call = now
            
            with st.spinner("🧠 AI 分析比較結果中..."):
                try:
                    import google.generativeai as genai
                    genai.configure(api_key=gemini_key)
                    model = genai.GenerativeModel("gemini-2.0-flash")
                    
                    # 準備分析資料
                    analysis_text = self._prepare_multi_comparison_prompt(
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
                    return
        
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


# 如果需要，可以保留單獨的函數供外部調用
def get_comparison_analyzer():
    """取得比較分析器實例"""
    return ComparisonAnalyzer()
