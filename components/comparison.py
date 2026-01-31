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
    """房屋分析器 - 支援單一分析和多房屋比較"""
    
    def __init__(self):
        pass
    
    def render_comparison_tab(self):
        """渲染分析頁面"""
        st.subheader("🏠 房屋分析模式")
        
        # 檢查是否有收藏
        fav_df = self._get_favorites_data()
        if fav_df.empty:
            st.info("⭐ 尚未有收藏房產，無法分析")
            return
        
        # 模式選擇 - 兩種模式
        analysis_mode = st.radio(
            "選擇分析模式",
            ["單一房屋分析", "多房屋比較"],
            horizontal=True,
            key="analysis_mode"
        )
        
        options = fav_df['標題'] + " | " + fav_df['地址']
        selected_houses = []
        
        if analysis_mode == "單一房屋分析":
            # 單一房屋分析模式
            choice_single = st.selectbox("選擇要分析的房屋", options, key="compare_single")
            
            if choice_single:
                selected_houses = [choice_single]
                
                # 顯示選擇的房屋資訊
                house_info = fav_df[(fav_df['標題'] + " | " + fav_df['地址']) == choice_single].iloc[0]
                
                st.markdown("### 📋 選擇的房屋")
                col1, col2 = st.columns([1, 2])
                with col1:
                    st.metric("房屋", f"🏠 單一分析")
                with col2:
                    st.markdown(f"**標題**: {house_info['標題']}")
                    st.markdown(f"**地址**: {house_info['地址']}")
                
                # 顯示房屋基本資訊
                with st.expander("📊 房屋詳細資訊", expanded=True):
                    info_cols = st.columns(3)
                    with info_cols[0]:
                        if '總價元' in house_info:
                            st.metric("總價", f"{int(house_info['總價元']):,} 元")
                    with info_cols[1]:
                        if '建物面積平方公尺' in house_info:
                            st.metric("面積", f"{house_info['建物面積平方公尺']:.1f} ㎡")
                    with info_cols[2]:
                        if '平均單價元平方公尺' in house_info:
                            st.metric("單價", f"{int(house_info['平均單價元平方公尺']):,} 元/㎡")
                
        else:  # 多房屋比較
            # 多房屋比較模式
            selected_houses = st.multiselect(
                "選擇要比較的房屋（可選1個或多個）",
                options,
                default=options[:min(3, len(options))] if len(options) >= 1 else [],
                key="multi_compare"
            )
            
            if not selected_houses:
                st.warning("⚠️ 請至少選擇1個房屋")
                return
            
            # 顯示已選房屋的預覽
            if selected_houses:
                st.markdown("### 📋 已選房屋清單")
                
                # 根據房屋數量決定顯示方式
                if len(selected_houses) == 1:
                    # 只有一個房屋時，顯示更詳細
                    house_info = fav_df[(fav_df['標題'] + " | " + fav_df['地址']) == selected_houses[0]].iloc[0]
                    st.markdown(f"""
                    <div style="border:2px solid #4CAF50; padding:15px; border-radius:10px; background-color:#f9f9f9;">
                    <h4 style="color:#4CAF50;">🏠 單一房屋（比較模式）</h4>
                    <p><strong>標題：</strong>{house_info['標題']}</p>
                    <p><strong>地址：</strong>{house_info['地址']}</p>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    # 多個房屋時，分列顯示
                    num_columns = min(3, len(selected_houses))
                    cols = st.columns(num_columns)
                    
                    for idx, house_option in enumerate(selected_houses):
                        with cols[idx % num_columns]:
                            house_info = fav_df[(fav_df['標題'] + " | " + fav_df['地址']) == house_option].iloc[0]
                            price_info = ""
                            if '平均單價元平方公尺' in house_info:
                                price = int(house_info['平均單價元平方公尺'])
                                price_info = f"<br>💰 {price:,} 元/㎡"
                            
                            st.markdown(f"""
                            <div style="border:1px solid #ddd; padding:10px; border-radius:5px; margin-bottom:10px;">
                            <strong>房屋 {chr(65+idx)}</strong><br>
                            📍 {house_info['地址'][:30]}...<br>
                            🏷️ {house_info['標題'][:25]}...{price_info}
                            </div>
                            """, unsafe_allow_html=True)
                
                st.caption(f"已選擇 {len(selected_houses)} 間房屋{'進行比較' if len(selected_houses) > 1 else ''}")
                
                # 如果選擇了多個房屋，顯示快速價格比較
                if len(selected_houses) > 1:
                    price_comparison = []
                    for house_option in selected_houses:
                        house_info = fav_df[(fav_df['標題'] + " | " + fav_df['地址']) == house_option].iloc[0]
                        if '平均單價元平方公尺' in house_info:
                            price_comparison.append({
                                'option': house_option,
                                'price': house_info['平均單價元平方公尺']
                            })
                    
                    if len(price_comparison) > 1:
                        price_comparison.sort(key=lambda x: x['price'])
                        cheapest = price_comparison[0]
                        most_expensive = price_comparison[-1]
                        price_diff = ((most_expensive['price'] - cheapest['price']) / cheapest['price'] * 100) if cheapest['price'] > 0 else 0
                        
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("最便宜", f"{int(cheapest['price']):,} 元/㎡", "房屋 A")
                        with col2:
                            st.metric("最昂貴", f"{int(most_expensive['price']):,} 元/㎡", f"房屋 {chr(65 + selected_houses.index(most_expensive['option']))}")
                        with col3:
                            st.metric("價格差距", f"{price_diff:.1f}%")
        
        # 如果沒有選擇房屋，停止執行
        if not selected_houses:
            return
        
        # 分析設定
        st.markdown("---")
        st.subheader("⚙️ 分析設定")
        
        # 取得 API Keys
        server_key = self._get_server_key()
        gemini_key = self._get_gemini_key()
        browser_key = self._get_browser_key()
        
        # 搜尋設定
        radius = st.slider("搜尋半徑 (公尺)", 100, 2000, DEFAULT_RADIUS, 100, key="radius_slider")
        keyword = st.text_input("額外關鍵字搜尋 (可選)", key="extra_keyword", 
                              placeholder="例如：公園、健身房、銀行等")
        
        # 生活機能選擇
        st.markdown("---")
        st.subheader("🔍 選擇生活機能類別")
        
        selected_categories = []
        selected_subtypes = {}
        
        # 快速選擇模式
        st.markdown("### 🚀 快速選擇")
        quick_mode = st.radio(
            "選擇方式",
            ["快速選擇（常用組合）", "自訂選擇"],
            horizontal=True,
            key="quick_mode"
        )
        
        if quick_mode == "快速選擇（常用組合）":
            # 預設組合
            preset_options = {
                "基礎生活圈": ["教育", "購物", "交通運輸", "健康與保健"],
                "完整生活機能": ["教育", "購物", "交通運輸", "健康與保健", "餐飲美食", "生活服務"],
                "家庭需求": ["教育", "購物", "健康與保健", "生活服務"],
                "投資潛力": ["交通運輸", "購物", "餐飲美食"],
                "退休養老": ["健康與保健", "生活服務", "餐飲美食"],
                "上班族通勤": ["交通運輸", "餐飲美食", "購物"]
            }
            
            selected_preset = st.selectbox(
                "選擇預設組合",
                list(preset_options.keys()),
                key="preset_selection"
            )
            
            if selected_preset:
                selected_categories = preset_options[selected_preset]
                # 選中對應的大類別
                for cat in selected_categories:
                    selected_subtypes[cat] = PLACE_TYPES[cat][1::2]  # 所有子項目
                
                st.success(f"✅ 已選擇「{selected_preset}」組合")
                st.info(f"包含: {', '.join(selected_categories)}")
        
        else:  # 自訂選擇
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
            
            summary_cols = st.columns(min(len(selected_categories), 4))
            for idx, cat in enumerate(selected_categories):
                with summary_cols[idx % len(summary_cols)]:
                    if cat in selected_subtypes:
                        count = len(selected_subtypes[cat])
                        color = CATEGORY_COLORS.get(cat, "#000000")
                        st.markdown(f"""
                        <div style="background-color:{color}20; padding:10px; border-radius:5px; border-left:4px solid {color}; margin-bottom:10px;">
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
        
        # 開始分析按鈕
        st.markdown("---")
        col_start, col_clear = st.columns([3, 1])
        
        with col_start:
            analyze_text = "🚀 開始分析" if analysis_mode == "單一房屋分析" else "🚀 開始比較"
            if st.button(analyze_text, type="primary", use_container_width=True, key="start_analysis"):
                # 驗證檢查
                if not browser_key:
                    st.error("❌ 請在側邊欄填入 Google Maps **Browser Key**")
                    return
                if not server_key or not gemini_key:
                    st.error("❌ 請在側邊欄填入 Server Key 與 Gemini Key")
                    return
                
                if not selected_categories:
                    st.warning("⚠️ 請至少選擇一個生活機能類別")
                    return
                
                if not selected_houses:
                    st.warning("⚠️ 請選擇要分析的房屋")
                    return

                # 執行分析
                self._run_analysis(
                    analysis_mode, 
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
                # 清除相關的 session state
                keys_to_clear = ['gemini_result', 'gemini_key', 'places_data', 'houses_data', 'custom_prompt', 'used_prompt']
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
        """搜尋Google Places（使用文字搜尋）"""
        url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
        params = {
            "query": keyword,
            "location": f"{lat},{lng}",
            "radius": radius,
            "key": api_key,
            "language": "zh-TW"
        }

        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            r = response.json()
        except Exception as e:
            st.warning(f"❌ 關鍵字 {keyword} 查詢失敗: {e}")
            return []

        results = []
        for p in r.get("results", []):
            loc = p["geometry"]["location"]
            dist = int(haversine(lat, lng, loc["lat"], loc["lng"]))
            
            results.append((
                "關鍵字",
                keyword,
                p.get("name", "未命名"),
                loc["lat"],
                loc["lng"],
                dist,
                p.get("place_id", "")
            ))
        return results
    
    def _search_nearby_places_by_type(self, lat, lng, api_key, place_type, radius=500):
        """使用 Nearby Search 和 Type Filter 查詢地點"""
        url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
        params = {
            "location": f"{lat},{lng}",
            "radius": radius,
            "type": place_type,  # 使用類型篩選
            "key": api_key,
            "language": "zh-TW"  # 結果返回中文
        }

        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            r = response.json()
        except requests.exceptions.Timeout:
            st.warning(f"❌ 查詢 {place_type} 超時")
            return []
        except Exception as e:
            st.warning(f"❌ 查詢 {place_type} 失敗: {e}")
            return []

        results = []
        if r.get("status") != "OK":
            if r.get("status") == "ZERO_RESULTS":
                return []  # 沒有結果是正常的
            st.warning(f"⚠️ 查詢 {place_type} 返回狀態: {r.get('status')}")
            return []

        for p in r.get("results", []):
            loc = p["geometry"]["location"]
            dist = int(haversine(lat, lng, loc["lat"], loc["lng"]))
            
            # 將英文類型轉回中文顯示
            chinese_type = ENGLISH_TO_CHINESE.get(place_type, place_type)
            results.append((
                "類型搜尋",
                chinese_type,
                p.get("name", "未命名"),
                loc["lat"],
                loc["lng"],
                dist,
                p.get("place_id", "")
            ))
        return results
    
    def _query_google_places_keyword(self, lat, lng, api_key, selected_categories, selected_subtypes, radius=500, extra_keyword=""):
        """查詢Google Places關鍵字 - 使用 Nearby Search + Type"""
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
                
            for place_type in selected_subtypes[cat]:  # 現在是 Google Places 類型
                update_progress(f"查詢 {cat}-{place_type}")
                
                try:
                    # 使用新的 Nearby Search + Type 方法
                    places = self._search_nearby_places_by_type(lat, lng, api_key, place_type, radius)
                    
                    for p in places:
                        if p[5] > radius:
                            continue
                        pid = p[6]
                        if pid in seen:
                            continue
                        seen.add(pid)
                        results.append((cat, place_type, p[2], p[3], p[4], p[5], p[6]))

                    time.sleep(0.5)
                    
                except Exception as e:
                    st.warning(f"查詢 {place_type} 時發生錯誤: {str(e)[:50]}")
                    continue

        if extra_keyword:
            update_progress(f"額外關鍵字: {extra_keyword}")
            try:
                # 額外關鍵字仍使用 text search
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
    
    def _render_map(self, lat, lng, places, radius, title="房屋", show_all_places=True):
        """渲染地圖 - 修改為顯示全部設施"""
        browser_key = self._get_browser_key()
        
        # 如果沒有設施資料，顯示訊息
        if not places:
            st.info(f"📭 {title} 周圍半徑 {radius} 公尺內未找到設施")
            return
        
        data = []
        for cat, kw, name, p_lat, p_lng, dist, pid in places:
            # 確保所有字串都轉換為安全格式
            safe_name = name.replace("'", "\\'").replace('"', '\\"')
            data.append({
                "cat": cat,
                "kw": kw,
                "name": safe_name,
                "lat": p_lat,
                "lng": p_lng,
                "dist": dist,
                "pid": pid,
                "color": CATEGORY_COLORS.get(cat, "#000000")
            })
    
        # 將 data_json 轉為 JavaScript 安全格式
        import json
        data_json = json.dumps(data, ensure_ascii=False)
        
        # 計算總設施數量
        total_places = len(places)
        
        # 修正 Template，將 JavaScript 字符串直接嵌入
        # 而不是使用 Template 替換
        html_content = f"""
        <div id="map" style="height:500px;"></div>
        <script>
        function initMap() {{
            var center = {{lat: {lat}, lng: {lng}}};
            var map = new google.maps.Map(document.getElementById('map'), {{
                zoom: 16,
                center: center,
                mapTypeControl: true,
                streetViewControl: true
            }});
            
            // 主房屋標記（紅色）
            var mainMarker = new google.maps.Marker({{
                position: center,
                map: map,
                title: "{title}",
                icon: {{
                    url: "http://maps.google.com/mapfiles/ms/icons/red-dot.png"
                }},
                zIndex: 1000
            }});
            
            // 顯示主房屋資訊視窗
            var mainInfoWindow = new google.maps.InfoWindow({{
                content: "<div style='padding:10px;'><strong>{title}</strong><br>搜尋中心點<br>半徑：{radius} 公尺</div>"
            }});
            mainMarker.addListener("click", function(){{
                mainInfoWindow.open(map, mainMarker);
            }});
            
            var data = {data_json};
            
            // 建立類別圖例
            var legendDiv = document.createElement('div');
            legendDiv.id = 'legend';
            legendDiv.style.cssText = 'background: white; padding: 10px; border: 1px solid #ccc; border-radius: 5px; font-size: 12px; margin: 10px;';
            legendDiv.innerHTML = '<h4 style="margin-top:0;">設施類別圖例</h4>';
            
            var categories = {{}};
            data.forEach(function(p){{
                if(!categories[p.cat]) {{
                    categories[p.cat] = p.color;
                }}
            }});
            
            for(var cat in categories) {{
                legendDiv.innerHTML += '<div style="margin-bottom: 5px;"><span style="display:inline-block; width:12px; height:12px; background-color:' + categories[cat] + '; margin-right:5px;"></span>' + cat + '</div>';
            }}
            
            map.controls[google.maps.ControlPosition.RIGHT_TOP].push(legendDiv);
            
            // 為每個設施建立標記
            data.forEach(function(p){{
                var mapsUrl = "https://www.google.com/maps/search/?api=1&query=" + p.lat + "," + p.lng + "&query_place_id=" + p.pid;
                var infoContent = `
                    <div style="padding:10px; max-width:250px;">
                        <strong>${{p.name}}</strong><br>
                        <span style="color:${{p.color}}; font-weight:bold;">${{p.cat}} - ${{p.kw}}</span><br>
                        距離中心：<strong>${{p.dist}} 公尺</strong><br>
                        <small>緯度：${{p.lat.toFixed(6)}}<br>經度：${{p.lng.toFixed(6)}}</small><br>
                        <a href="${{mapsUrl}}" target="_blank" style="color:#1a73e8; text-decoration:none; font-size:12px;">
                            <span style="color:#1a73e8;">🗺️ 在 Google 地圖中查看</span>
                        </a>
                    </div>
                `;
                
                var marker = new google.maps.Marker({{
                    position: {{lat: p.lat, lng: p.lng}},
                    map: map,
                    icon: {{
                        path: google.maps.SymbolPath.CIRCLE,
                        scale: 8,
                        fillColor: p.color,
                        fillOpacity: 0.9,
                        strokeColor: "#FFFFFF",
                        strokeWeight: 2
                    }},
                    title: p.cat + " - " + p.name,
                    animation: google.maps.Animation.DROP
                }});
                
                var infoWindow = new google.maps.InfoWindow({{
                    content: infoContent
                }});
                
                marker.addListener("click", function(){{
                    // 關閉所有其他資訊視窗
                    infoWindow.open(map, marker);
                }});
            }});
    
            // 繪製搜尋半徑圓
            new google.maps.Circle({{
                strokeColor: "#FF0000",
                strokeOpacity: 0.8,
                strokeWeight: 2,
                fillColor: "#FF0000",
                fillOpacity: 0.1,
                map: map,
                center: center,
                radius: {radius}
            }});
            
            // 自動打開主房屋資訊視窗
            setTimeout(function() {{
                mainInfoWindow.open(map, mainMarker);
            }}, 1000);
        }}
        </script>
        <script src="https://maps.googleapis.com/maps/api/js?key={browser_key}&callback=initMap" async defer></script>
        """
        
        # 顯示地圖資訊
        st.markdown(f"**🗺️ {title} - 周邊設施地圖**")
        st.markdown(f"📊 **共找到 {total_places} 個設施** (搜尋半徑: {radius}公尺)")
        html(html_content, height=520)
        
        # 顯示全部設施列表 - 使用純 Python 方法
        st.markdown("### 📍 全部設施列表")
        
        if total_places > 0:
            # 建立一個可折疊的下拉選單來顯示所有設施
            with st.expander(f"顯示所有 {total_places} 個設施", expanded=True):
                # 設施已經按距離排序，直接顯示
                for i, (cat, kw, name, lat, lng, dist, pid) in enumerate(places, 1):
                    color = CATEGORY_COLORS.get(cat, "#000000")
                    maps_url = f"https://www.google.com/maps/search/?api=1&query={lat},{lng}&query_place_id={pid}"
                    
                    # 距離分類標籤
                    if dist <= 300:
                        dist_color = "#28a745"
                        dist_class = "很近"
                    elif dist <= 600:
                        dist_color = "#ffc107"
                        dist_class = "中等"
                    else:
                        dist_color = "#dc3545"
                        dist_class = "較遠"
                    
                    # 創建一個卡片容器
                    with st.container():
                        # 使用 columns 來佈局
                        col1, col2, col3, col4 = st.columns([6, 2, 2, 2])
                        
                        with col1:
                            # 顯示設施編號和名稱
                            st.write(f"**{i}.**")
                            st.write(f"**{name}**")
                        
                        with col2:
                            # 類別標籤
                            st.markdown(f'<span style="background-color:{color}20; color:{color}; padding:4px 8px; border-radius:8px; font-size:12px; font-weight:bold;">{cat}</span>', unsafe_allow_html=True)
                        
                        with col3:
                            # 距離標籤
                            st.markdown(f'<span style="background-color:{dist_color}20; color:{dist_color}; padding:4px 8px; border-radius:8px; font-size:12px; font-weight:bold;">{dist}公尺</span>', unsafe_allow_html=True)
                        
                        with col4:
                            # 地圖連結按鈕 - 使用 st.link_button
                            st.link_button("🗺️ 地圖", maps_url)
                        
                        # 顯示詳細資訊
                        with st.expander("詳細資訊", expanded=False):
                            col_info1, col_info2 = st.columns(2)
                            with col_info1:
                                st.write(f"**類別:** {cat}")
                                st.write(f"**子類別:** {kw}")
                                st.write(f"**距離:** {dist} 公尺 ({dist_class})")
                            with col_info2:
                                st.write(f"**座標:** {lat:.6f}, {lng:.6f}")
                                st.write(f"**Google 地圖:** [開啟地圖]({maps_url})")
                        
                        # 添加分隔線
                        st.divider()
            
            # 顯示統計摘要
            with st.expander("📊 設施統計摘要", expanded=False):
                # 按類別統計
                category_stats = {}
                for cat, kw, name, lat, lng, dist, pid in places:
                    category_stats[cat] = category_stats.get(cat, 0) + 1
                
                # 按距離分組統計
                close_places = sum(1 for p in places if p[5] <= 300)
                medium_places = sum(1 for p in places if 300 < p[5] <= 600)
                far_places = sum(1 for p in places if p[5] > 600)
                
                # 顯示統計卡片
                stat_cols = st.columns(3)
                with stat_cols[0]:
                    st.metric("🟢 很近 (≤300m)", close_places, f"{close_places/total_places*100:.1f}%" if total_places > 0 else "0%")
                with stat_cols[1]:
                    st.metric("🟡 中等 (300-600m)", medium_places, f"{medium_places/total_places*100:.1f}%" if total_places > 0 else "0%")
                with stat_cols[2]:
                    st.metric("🔴 較遠 (>600m)", far_places, f"{far_places/total_places*100:.1f}%" if total_places > 0 else "0%")
                
                # 顯示類別分布
                st.markdown("**🏪 設施類別分布:**")
                for cat, count in sorted(category_stats.items(), key=lambda x: x[1], reverse=True):
                    color = CATEGORY_COLORS.get(cat, "#000000")
                    percentage = (count / total_places) * 100 if total_places > 0 else 0
                    
                    st.markdown(f"""
                    <div style="margin-bottom:8px; display:flex; align-items:center;">
                        <div style="display:flex; align-items:center; width:150px;">
                            <span style="display:inline-block; width:12px; height:12px; background-color:{color}; border-radius:50%; margin-right:8px;"></span>
                            <span style="font-weight:500;">{cat}:</span>
                        </div>
                        <div style="flex:1; margin-left:10px;">
                            <div style="width:100%; height:20px; background-color:#e9ecef; border-radius:10px; overflow:hidden;">
                                <div style="width:{percentage}%; height:100%; background-color:{color};"></div>
                            </div>
                        </div>
                        <div style="width:80px; text-align:right; margin-left:10px;">
                            <span style="font-weight:bold;">{count} 個</span>
                            <span style="color:#666; font-size:12px;"> ({percentage:.1f}%)</span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                
                # 顯示距離統計
                if places:
                    avg_distance = sum(p[5] for p in places) / total_places
                    min_distance = min(p[5] for p in places)
                    max_distance = max(p[5] for p in places)
                    
                    st.markdown("**📏 距離統計:**")
                    dist_cols = st.columns(3)
                    with dist_cols[0]:
                        st.metric("平均距離", f"{avg_distance:.0f} 公尺")
                    with dist_cols[1]:
                        st.metric("最近設施", f"{min_distance} 公尺")
                    with dist_cols[2]:
                        st.metric("最遠設施", f"{max_distance} 公尺")
        else:
            st.info("📭 未找到任何設施")
    
    def _prepare_analysis_prompt(self, houses_data, places_data, facility_counts, 
                                category_counts, selected_categories, radius, 
                                keyword, analysis_mode):
        """準備分析提示詞（根據模式不同）"""
        
        if analysis_mode == "單一房屋分析":
            # 單一房屋分析提示詞
            house_name = list(houses_data.keys())[0]
            house_info = houses_data[house_name]
            places = places_data[house_name]
            count = facility_counts.get(house_name, 0)
            
            # 統計設施距離
            distances = [p[5] for p in places]
            avg_distance = sum(distances) / len(distances) if distances else 0
            min_distance = min(distances) if distances else 0
            
            # 各類別統計
            category_stats = {}
            for cat, kw, name, lat, lng, dist, pid in places:
                category_stats[cat] = category_stats.get(cat, 0) + 1
            
            prompt = f"""
            你是一位專業的房地產分析師，請對以下房屋的生活機能進行詳細分析。
            
            【房屋資訊】
            - 標題：{house_info['title']}
            - 地址：{house_info['address']}
            
            【搜尋條件】
            - 搜尋半徑：{radius} 公尺
            - 選擇的生活機能類別：{', '.join(selected_categories)}
            - 額外關鍵字：{keyword if keyword else '無'}
            
            【設施統計】
            - 總設施數量：{count} 個
            - 平均距離：{avg_distance:.0f} 公尺
            - 最近設施：{min_distance} 公尺
            
            【各類別設施數量】
            {chr(10).join([f'- {cat}: {num} 個' for cat, num in category_stats.items()])}
            
            【請分析以下面向】
            1. 生活便利性評估（以1-5星評分）
            2. 設施完整性分析（哪些類別充足，哪些缺乏）
            3. 適合的居住族群分析（單身、小家庭、大家庭、退休族等）
            4. 投資潛力評估（以1-5星評分）
            5. 優點總結（至少3點）
            6. 缺點提醒（至少2點）
            7. 建議改善或補充的生活機能
            8. 綜合評價與建議
            
            【特別注意】
            - 考慮設施距離與日常生活的實際便利性
            - 分析對不同族群的吸引力
            - 評估房價與生活機能的性價比
            
            請使用專業但易懂的語言，提供具體、實用的建議。
            """
        
        else:  # 多房屋比較
            # 多房屋比較提示詞
            num_houses = len(houses_data)
            
            if num_houses == 1:
                # 只有一個房屋的比較模式
                house_name = list(houses_data.keys())[0]
                house_info = houses_data[house_name]
                places = places_data[house_name]
                count = facility_counts.get(house_name, 0)
                
                # 統計設施距離
                distances = [p[5] for p in places]
                avg_distance = sum(distances) / len(distances) if distances else 0
                
                # 各類別統計
                category_stats = {}
                for cat, kw, name, lat, lng, dist, pid in places:
                    category_stats[cat] = category_stats.get(cat, 0) + 1
                
                prompt = f"""
                你是一位專業的房地產分析師，請對以下房屋的生活機能進行綜合評估。
                
                【房屋資訊】
                - 標題：{house_info['title']}
                - 地址：{house_info['address']}
                
                【搜尋條件】
                - 搜尋半徑：{radius} 公尺
                - 選擇的生活機能類別：{', '.join(selected_categories)}
                - 額外關鍵字：{keyword if keyword else '無'}
                
                【設施統計】
                - 總設施數量：{count} 個
                - 平均距離：{avg_distance:.0f} 公尺
                
                【各類別設施數量】
                {chr(10).join([f'- {cat}: {num} 個' for cat, num in category_stats.items()])}
                
                【請提供深度分析】
                1. 區域生活機能整體評價
                2. 與類似區域的比較優勢
                3. 未來發展潛力評估
                4. 投資回報率預估
                5. 風險因素分析
                6. 最佳使用建議
                
                請提供專業、客觀的分析報告。
                """
            else:
                # 多個房屋比較
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
                
                # 房屋詳細資訊
                houses_details = "房屋詳細資訊：\n"
                for house_name, house_info in houses_data.items():
                    houses_details += f"""
                    {house_name}:
                    - 標題：{house_info['title']}
                    - 地址：{house_info['address']}
                    """
                
                prompt = f"""
                你是一位專業的房地產分析師，請對以下{num_houses}間房屋進行綜合比較分析。
                
                【搜尋條件】
                - 搜尋半徑：{radius} 公尺
                - 選擇的生活機能類別：{', '.join(selected_categories)}
                - 額外關鍵字：{keyword if keyword else '無'}
                
                {houses_details}
                
                【設施統計】
                {stats_summary}
                
                {ranking_text}
                
                【請依序分析】
                1. 總體設施豐富度排名與分析
                2. 各類別設施完整性比較
                3. 生活便利性綜合評估（為每間房屋評1-5星）
                4. 對「自住者」的推薦排名與原因
                5. 對「投資者」的推薦排名與原因
                6. 各房屋的優勢特色分析
                7. 各房屋的潛在風險提醒
                8. 綜合性價比評估
                9. 最終推薦與總結
                
                【分析要求】
                - 提供清晰的排名和評分
                - 每項評估都要有具體依據
                - 考慮不同生活階段的需求
                - 給出實用的購買建議
                
                請使用專業但易懂的語言，提供全面、客觀的分析。
                """
        
        return prompt
    
    def _get_prompt_templates(self, analysis_mode):
        """取得提示詞模板"""
        templates = {
            "default": {
                "name": "預設分析模板",
                "description": "標準的全面性分析"
            },
            "detailed": {
                "name": "詳細分析模板",
                "description": "更深入的詳細分析",
                "content": """
                你是一位專業的房地產分析師，請對以下房屋進行極其詳細的分析。
                
                【要求】
                1. 提供1-5星的詳細評分，並說明每個星等的評分標準
                2. 分析每個生活機能類別的優缺點
                3. 提供具體的數據支持和比較
                4. 考慮不同時間段的需求（平日/假日、白天/晚上）
                5. 分析噪音、交通、安全等環境因素
                6. 預測未來3-5年的發展潛力
                7. 提供具體的改善建議
                
                請使用專業術語，但讓非專業人士也能理解。
                """
            },
            "investment": {
                "name": "投資分析模板",
                "description": "專注於投資回報率的分析",
                "content": """
                你是一位房地產投資專家，請從投資角度分析以下房產。
                
                【投資分析重點】
                1. 租金收益率預估
                2. 資本增值潛力評估
                3. 目標租客族群分析
                4. 空置風險評估
                5. 管理成本估算
                6. 投資回收期計算
                7. 競爭優勢分析
                8. 風險因素與對策
                
                請提供具體的數字和百分比估計。
                """
            },
            "family": {
                "name": "家庭需求模板",
                "description": "專注於家庭生活需求的分析",
                "content": """
                你是一位家庭生活規劃專家，請分析以下房屋對家庭的適合度。
                
                【家庭需求分析】
                1. 兒童教育資源評估（學校、補習班、圖書館）
                2. 育兒便利性（公園、醫療、安全）
                3. 家庭採購便利性（超市、市場）
                4. 家庭娛樂設施（公園、運動場所）
                5. 社區安全與環境
                6. 通勤便利性對家庭的影響
                7. 鄰里關係與社區活動
                
                考慮不同家庭階段的需求（新生兒、學齡兒童、青少年）。
                """
            },
            "simple": {
                "name": "簡明報告模板",
                "description": "簡潔扼要的分析報告",
                "content": """
                請提供簡潔的房屋分析報告，包含：
                
                【簡明分析】
                1. 整體評價（1-5星）
                2. 主要優點（3點）
                3. 主要缺點（3點）
                4. 最適合族群
                5. 一句話總結
                
                請使用簡短的段落和要點式說明。
                """
            }
        }
        return templates
    
    def _run_analysis(self, analysis_mode, selected_houses, fav_df, 
                     server_key, gemini_key, radius, keyword, 
                     selected_categories, selected_subtypes):
        """執行分析的核心函數"""
        
        # 取得房屋資料
        houses_data = {}
        
        # 地址解析
        with st.spinner("📍 解析房屋地址中..."):
            for idx, house_option in enumerate(selected_houses):
                house_info = fav_df[(fav_df['標題'] + " | " + fav_df['地址']) == house_option].iloc[0]
                house_name = f"房屋 {chr(65+idx)}" if len(selected_houses) > 1 else "分析房屋"
                
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
        
        # 顯示分析標題
        num_houses = len(houses_data)
        if analysis_mode == "單一房屋分析":
            st.markdown(f"## 📊 單一房屋分析結果")
        else:
            st.markdown(f"## 📊 比較結果 ({num_houses}間房屋)")
        
        # 統計分析
        st.markdown("---")
        st.subheader("📈 設施統計")
        
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
        
        # 顯示統計
        if num_houses == 1 or analysis_mode == "單一房屋分析":
            # 單一房屋統計
            house_name = list(houses_data.keys())[0]
            count = facility_counts.get(house_name, 0)
            places = places_data[house_name]
            
            # 計算距離統計
            distances = [p[5] for p in places]
            avg_distance = sum(distances) / len(distances) if distances else 0
            min_distance = min(distances) if distances else 0
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("🏠 總設施數量", f"{count} 個")
            with col2:
                st.metric("📏 平均距離", f"{avg_distance:.0f} 公尺")
            with col3:
                st.metric("📍 最近設施", f"{min_distance} 公尺")
            
            # 各類別設施數量
            if places:
                st.markdown("### 🏪 各類別設施分布")
                
                # 建立類別數據
                cat_data = {}
                for cat, kw, name, lat, lng, dist, pid in places:
                    cat_data[cat] = cat_data.get(cat, 0) + 1
                
                # 顯示餅圖
                if cat_data:
                    pie_data = {
                        "tooltip": {"trigger": "item"},
                        "legend": {"type": "scroll", "orient": "vertical", "right": 10, "top": 20, "bottom": 20},
                        "series": [{
                            "type": "pie",
                            "radius": "50%",
                            "data": [
                                {"value": count, "name": cat, "itemStyle": {"color": CATEGORY_COLORS.get(cat, "#000000")}}
                                for cat, count in cat_data.items()
                            ],
                            "emphasis": {
                                "itemStyle": {
                                    "shadowBlur": 10,
                                    "shadowOffsetX": 0,
                                    "shadowColor": "rgba(0, 0, 0, 0.5)"
                                }
                            }
                        }]
                    }
                    
                    st_echarts(pie_data, height="400px")
                    
                    # 顯示詳細表格
                    with st.expander("📋 詳細設施列表", expanded=False):
                        for i, (cat, kw, name, lat, lng, dist, pid) in enumerate(places[:20]):  # 只顯示前20個
                            col_a, col_b, col_c = st.columns([3, 2, 1])
                            with col_a:
                                st.markdown(f"**{name}**")
                                st.caption(f"{cat}-{kw}")
                            with col_b:
                                st.caption(f"距離: {dist} 公尺")
                            with col_c:
                                color = CATEGORY_COLORS.get(cat, "#000000")
                                st.markdown(f'<span style="background-color:{color}; color:white; padding:2px 8px; border-radius:10px;">{cat}</span>', unsafe_allow_html=True)
                        
                        if len(places) > 20:
                            st.caption(f"...還有 {len(places)-20} 個設施未顯示")
        
        else:
            # 多房屋統計比較
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
            
            # 如果有超過1個房屋，顯示排名圖表
            if num_houses > 1:
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
            if num_houses > 1:
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
        
        # 顯示地圖
        st.markdown("---")
        st.subheader("🗺️ 地圖檢視")
        
        if num_houses == 1 or analysis_mode == "單一房屋分析":
            # 單一房屋地圖
            house_name = list(houses_data.keys())[0]
            house_info = houses_data[house_name]
            
            # 移除原本顯示最近設施的程式碼，直接調用 _render_map 方法
            self._render_map(
                house_info["lat"], 
                house_info["lng"], 
                places_data[house_name], 
                radius, 
                title=house_name,
                show_all_places=True  # 新增參數
            )
            
        elif num_houses <= 3:
            # 並排顯示地圖
            map_cols = st.columns(num_houses)
            for idx, (house_name, house_info) in enumerate(houses_data.items()):
                with map_cols[idx]:
                    st.markdown(f"### {house_name}")
                    # 直接調用 _render_map 方法，移除顯示最近設施的程式碼
                    self._render_map(
                        house_info["lat"], 
                        house_info["lng"], 
                        places_data[house_name], 
                        radius, 
                        title=house_name,
                        show_all_places=True  # 新增參數
                    )
        else:
            # 使用選項卡顯示地圖
            map_tabs = st.tabs([f"{house_name}" for house_name in houses_data.keys()])
            
            for idx, (house_name, house_info) in enumerate(houses_data.items()):
                with map_tabs[idx]:
                    # 直接調用 _render_map 方法
                    self._render_map(
                        house_info["lat"], 
                        house_info["lng"], 
                        places_data[house_name], 
                        radius, 
                        title=house_name,
                        show_all_places=True  # 新增參數
                    )
        
        # ============================
        # AI 分析 - 可編輯提示詞版本
        # ============================
        st.markdown("---")
        st.subheader("🤖 AI 智能分析")
        
      # 準備AI分析資料
        with st.spinner("🧠 準備分析資料..."):
            analysis_text = self._prepare_analysis_prompt(
                houses_data, 
                places_data, 
                facility_counts, 
                category_counts,
                selected_categories,
                radius,
                keyword,
                analysis_mode
            )
        
        # 建立唯一 key
        analysis_key = f"{analysis_mode}__{','.join(selected_houses)}__{keyword}__{','.join(selected_categories)}__{radius}"
        
        # 顯示提示詞模板選擇 - 修正版本
        st.markdown("### 📋 提示詞模板選擇")
        
        templates = self._get_prompt_templates(analysis_mode)
        
        # 建立模板選項
        template_options = {k: f"{v['name']} - {v['description']}" for k, v in templates.items()}
        
        # 使用 session state 來儲存選擇的模板
        if "selected_template" not in st.session_state:
            st.session_state.selected_template = "default"
        
        # 使用 on_change 回調函數來處理模板選擇
        def on_template_change():
            # 當模板改變時，更新自定義提示詞
            selected_template = st.session_state.template_selector
            if selected_template != "default" and "content" in templates[selected_template]:
                st.session_state.custom_prompt = templates[selected_template]["content"]
                st.session_state.selected_template = selected_template
                # 不清除結果，只更新提示詞
                st.info(f"✅ 已套用「{templates[selected_template]['name']}」模板")
        
        # 修正選擇框 - 使用 on_change 參數
        selected_template = st.selectbox(
            "選擇提示詞模板",
            options=list(template_options.keys()),
            format_func=lambda x: template_options[x],
            key="template_selector",
            on_change=on_template_change
        )
        
        # 顯示提示詞編輯區域
        st.markdown("### 📝 AI 分析提示詞設定")
        
        col_prompt, col_info = st.columns([3, 1])
        
        with col_prompt:
            # 預設提示詞
            default_prompt = analysis_text
            
            # 如果session state中有自定義提示詞，使用它
            custom_prompt = st.session_state.get("custom_prompt", default_prompt)
            
            # 顯示可編輯的文字區域
            edited_prompt = st.text_area(
                "編輯AI分析提示詞",
                value=custom_prompt,
                height=400,
                key="prompt_editor",
                help="您可以修改提示詞來調整AI的分析方向和重點"
            )
            
            # 比較提示詞是否有變更
            prompt_changed = edited_prompt != custom_prompt
            
        with col_info:
            st.markdown("#### 💡 提示詞使用說明")
            st.markdown("""
            **預設提示詞包含：**
            - 房屋資訊
            - 搜尋條件
            - 設施統計
            - 分析要求
            
            **您可以：**
            1. 調整分析重點
            2. 添加特定問題
            3. 修改評分標準
            4. 調整語言風格
            
            **建議：**
            - 保持基本資訊完整
            - 明確指定分析方向
            - 設定具體的評分標準
            """)
        
        # 按鈕區域
        col_analyze, col_reset, col_save = st.columns([2, 1, 1])
        
        with col_analyze:
            analyze_clicked = st.button("🚀 開始AI分析", type="primary", use_container_width=True)
            
            if analyze_clicked:
                # 儲存自定義提示詞
                st.session_state.custom_prompt = edited_prompt
                
                # 防爆檢查
                now = time.time()
                last = st.session_state.get("last_gemini_call", 0)
                
                if now - last < 30:
                    st.warning("⚠️ AI 分析請等待 30 秒後再試")
                    return
                
                st.session_state.last_gemini_call = now
                
                with st.spinner("🧠 AI 分析中..."):
                    try:
                        import google.generativeai as genai
                        genai.configure(api_key=gemini_key)
                        model = genai.GenerativeModel("gemini-2.0-flash")
                        
                        # 使用編輯後的提示詞
                        final_prompt = edited_prompt
                        
                        # 顯示使用中的提示詞預覽
                        with st.expander("📋 查看本次使用的提示詞", expanded=False):
                            st.text_area("送給 Gemini 的提示詞", final_prompt, height=200, key="final_prompt_display")
                        
                        # 呼叫 Gemini
                        resp = model.generate_content(final_prompt)
                        
                        # 儲存結果
                        st.session_state.gemini_result = resp.text
                        st.session_state.gemini_key = analysis_key
                        st.session_state.places_data = places_data
                        st.session_state.houses_data = houses_data
                        st.session_state.used_prompt = final_prompt  # 儲存使用的提示詞
                        
                        st.success("✅ AI 分析完成！")
                        # 使用 st.rerun() 來更新顯示
                        st.rerun()
                        
                    except Exception as e:
                        st.error(f"❌ Gemini API 錯誤: {str(e)}")
                        st.info("請檢查：1. API 金鑰是否正確 2. 配額是否用盡 3. 網路連線是否正常")
                        return
        
        with col_reset:
            if st.button("🔄 恢復預設提示詞", type="secondary", use_container_width=True):
                # 恢復預設提示詞
                st.session_state.custom_prompt = default_prompt
                st.session_state.selected_template = "default"
                st.success("✅ 已恢復預設提示詞")
                # 使用 st.rerun() 來更新顯示
                st.rerun()
        
        with col_save:
            if st.button("💾 儲存提示詞", type="secondary", use_container_width=True):
                # 儲存當前提示詞
                st.session_state.custom_prompt = edited_prompt
                st.success("✅ 提示詞已儲存！")
                # 不需要 rerun，只是更新 session state
        
        # 提示詞變更提醒
        if prompt_changed:
            st.info("📝 提示詞已修改，請點擊「開始AI分析」重新分析")
        
        # 顯示分析結果
        if "gemini_result" in st.session_state:
            st.markdown("### 📋 AI 分析報告")
            
            # 顯示使用的提示詞摘要
            if "used_prompt" in st.session_state:
                with st.expander("ℹ️ 查看本次使用的提示詞摘要", expanded=False):
                    used_prompt = st.session_state.used_prompt
                    # 顯示前500字作為摘要
                    prompt_preview = used_prompt[:500] + ("..." if len(used_prompt) > 500 else "")
                    st.text(prompt_preview)
            
            # 美化顯示
            with st.container():
                st.markdown("---")
                st.markdown(st.session_state.gemini_result)
                st.markdown("---")
            
            # 重新分析按鈕
            if st.button("🔄 使用修改後的提示詞重新分析", type="secondary", use_container_width=True):
                # 清除之前的結果，觸發重新分析
                keys_to_clear = ['gemini_result', 'gemini_key']
                for key in keys_to_clear:
                    if key in st.session_state:
                        del st.session_state[key]
                st.rerun()
            
            # 提供下載選項
            if analysis_mode == "單一房屋分析":
                report_title = "房屋分析報告"
            else:
                report_title = f"{num_houses}間房屋比較報告"
            
            report_text = f"""
            {report_title}
            生成時間：{time.strftime('%Y-%m-%d %H:%M:%S')}
            分析模式：{analysis_mode}
            
            分析房屋 ({len(houses_data)}間):
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
            
            提示詞設定：
            {st.session_state.get('used_prompt', '預設提示詞')[:500]}...
            
            AI 分析結果：
            {st.session_state.gemini_result}
            """
            
            st.download_button(
                label="📥 下載分析報告",
                data=report_text,
                file_name=f"{report_title}_{time.strftime('%Y%m%d_%H%M%S')}.txt",
                mime="text/plain",
                use_container_width=True
            )
