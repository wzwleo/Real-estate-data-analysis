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
    
    def _render_map(self, lat, lng, places, radius, title="房屋", show_all_places=True):
        """渲染地圖 - 修改為顯示全部設施"""
        browser_key = self._get_browser_key()
        
        # 如果沒有設施資料，顯示訊息
        if not places:
            st.info(f"📭 {title} 周圍半徑 {radius} 公尺內未找到設施")
            return
        
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
        
        # 計算總設施數量
        total_places = len(places)
        
        # 如果 show_all_places 為 True，在地圖上顯示所有設施
        tpl = Template("""
               <div id="map" style="height:500px;"></div>
               <script>
               function initMap() {
                   var center = {lat: $LAT, lng: $LNG};
                   var map = new google.maps.Map(document.getElementById('map'), {
                       zoom: 16,
                       center: center,
                       mapTypeControl: true,
                       streetViewControl: true
                   });
                   
                   // 主房屋標記（紅色）
                   var mainMarker = new google.maps.Marker({
                       position: center,
                       map: map,
                       title: "$TITLE",
                       icon: {
                           url: "http://maps.google.com/mapfiles/ms/icons/red-dot.png"
                       },
                       zIndex: 1000
                   });
                   
                   // 顯示主房屋資訊視窗
                   var mainInfoWindow = new google.maps.InfoWindow({
                       content: "<div style='padding:10px;'><strong>$TITLE</strong><br>搜尋中心點<br>半徑：$RADIUS 公尺</div>"
                   });
                   mainMarker.addListener("click", function(){
                       mainInfoWindow.open(map, mainMarker);
                   });
                   
                   var data = $DATA_JSON;
                   
                   // 建立類別圖例
                   var legendDiv = document.createElement('div');
                   legendDiv.id = 'legend';
                   legendDiv.style.cssText = 'background: white; padding: 10px; border: 1px solid #ccc; border-radius: 5px; font-size: 12px; margin: 10px;';
                   legendDiv.innerHTML = '<h4 style="margin-top:0;">設施類別圖例</h4>';
                   
                   var categories = {};
                   data.forEach(function(p){
                       if(!categories[p.cat]) {
                           categories[p.cat] = p.color;
                       }
                   });
                   
                   for(var cat in categories) {
                       legendDiv.innerHTML += '<div style="margin-bottom: 5px;"><span style="display:inline-block; width:12px; height:12px; background-color:' + categories[cat] + '; margin-right:5px;"></span>' + cat + '</div>';
                   }
                   
                   map.controls[google.maps.ControlPosition.RIGHT_TOP].push(legendDiv);
                   
                   // 為每個設施建立標記
                   data.forEach(function(p){
                       var infoContent = `
                           <div style="padding:10px; max-width:250px;">
                               <strong>${p.name}</strong><br>
                               <span style="color:${p.color}; font-weight:bold;">${p.cat} - ${p.kw}</span><br>
                               距離中心：<strong>${p.dist} 公尺</strong><br>
                               <small>緯度：${p.lat.toFixed(6)}<br>經度：${p.lng.toFixed(6)}</small>
                           </div>
                       `;
                       
                       var marker = new google.maps.Marker({
                           position: {lat: p.lat, lng: p.lng},
                           map: map,
                           icon: {
                               path: google.maps.SymbolPath.CIRCLE,
                               scale: 8,
                               fillColor: p.color,
                               fillOpacity: 0.9,
                               strokeColor: "#FFFFFF",
                               strokeWeight: 2
                           },
                           title: p.cat + " - " + p.name,
                           animation: google.maps.Animation.DROP
                       });
                       
                       var infoWindow = new google.maps.InfoWindow({
                           content: infoContent
                       });
                       
                       marker.addListener("click", function(){
                           // 關閉所有其他資訊視窗
                           infoWindow.open(map, marker);
                       });
                   });

                   // 繪製搜尋半徑圓
                   new google.maps.Circle({
                       strokeColor: "#FF0000",
                       strokeOpacity: 0.8,
                       strokeWeight: 2,
                       fillColor: "#FF0000",
                       fillOpacity: 0.1,
                       map: map,
                       center: center,
                       radius: $RADIUS
                   });
                   
                   // 自動打開主房屋資訊視窗
                   setTimeout(function() {
                       mainInfoWindow.open(map, mainMarker);
                   }, 1000);
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
        
        # 顯示地圖資訊
        st.markdown(f"**🗺️ {title} - 周邊設施地圖**")
        st.markdown(f"📊 **共找到 {total_places} 個設施** (搜尋半徑: {radius}公尺)")
        html(map_html, height=520)
        
        # 顯示全部設施列表
        st.markdown("### 📍 全部設施列表")
        
        if total_places > 0:
            # 分頁顯示所有設施
            places_per_page = 10
            total_pages = (total_places + places_per_page - 1) // places_per_page
            
            # 如果有需要分頁
            if total_pages > 1:
                page_number = st.number_input(
                    "選擇頁碼",
                    min_value=1,
                    max_value=total_pages,
                    value=1,
                    step=1,
                    key=f"page_{title}"
                )
                start_idx = (page_number - 1) * places_per_page
                end_idx = min(page_number * places_per_page, total_places)
            else:
                start_idx, end_idx = 0, total_places
            
            # 顯示當前頁的設施
            st.markdown(f"**顯示 {start_idx+1}-{end_idx} 個設施 (共 {total_places} 個)**")
            
            for i, (cat, kw, name, lat, lng, dist, pid) in enumerate(places[start_idx:end_idx], start=start_idx+1):
                color = CATEGORY_COLORS.get(cat, "#000000")
                
                # 建立資訊卡片
                col1, col2, col3 = st.columns([3, 1, 1])
                with col1:
                    st.markdown(f"""
                    <div style="padding:10px; border-left:4px solid {color}; background-color:#f8f9fa; border-radius:5px; margin-bottom:10px;">
                        <strong style="font-size:14px;">{i}. {name}</strong><br>
                        <small>🏷️ <span style="color:{color};"><strong>{cat}</strong> - {kw}</span></small><br>
                        <small>📍 距離: <strong>{dist} 公尺</strong></small>
                    </div>
                    """, unsafe_allow_html=True)
                
                with col2:
                    # 距離分類標籤
                    if dist <= 300:
                        dist_label = "🟢 很近"
                        dist_color = "#28a745"
                    elif dist <= 600:
                        dist_label = "🟡 中等"
                        dist_color = "#ffc107"
                    else:
                        dist_label = "🔴 較遠"
                        dist_color = "#dc3545"
                    
                    st.markdown(f'<div style="color:{dist_color}; font-weight:bold; text-align:center; padding-top:10px;">{dist_label}</div>', unsafe_allow_html=True)
                
                with col3:
                    # 顯示地圖連結按鈕
                    maps_url = f"https://www.google.com/maps/search/?api=1&query={lat},{lng}&query_place_id={pid}"
                    st.markdown(f'<a href="{maps_url}" target="_blank" style="text-decoration:none;"><button style="background-color:{color}; color:white; border:none; padding:5px 10px; border-radius:4px; cursor:pointer;">🗺️ 地圖</button></a>', unsafe_allow_html=True)
            
            # 如果分頁，顯示分頁資訊
            if total_pages > 1:
                st.caption(f"第 {page_number} 頁，共 {total_pages} 頁")
                
                # 分頁導航按鈕
                nav_cols = st.columns([2, 1, 2])
                with nav_cols[0]:
                    if page_number > 1:
                        if st.button("⬅️ 上一頁", key=f"prev_{title}"):
                            page_number = max(1, page_number - 1)
                            st.rerun()
                with nav_cols[2]:
                    if page_number < total_pages:
                        if st.button("下一頁 ➡️", key=f"next_{title}"):
                            page_number = min(total_pages, page_number + 1)
                            st.rerun()
            
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
                
                stat_cols = st.columns(3)
                with stat_cols[0]:
                    st.metric("很近 (≤300m)", close_places)
                with stat_cols[1]:
                    st.metric("中等 (300-600m)", medium_places)
                with stat_cols[2]:
                    st.metric("較遠 (>600m)", far_places)
                
                # 顯示類別分布
                st.markdown("**🏪 類別分布:**")
                for cat, count in sorted(category_stats.items(), key=lambda x: x[1], reverse=True):
                    color = CATEGORY_COLORS.get(cat, "#000000")
                    percentage = (count / total_places) * 100
                    
                    st.markdown(f"""
                    <div style="margin-bottom:5px;">
                        <span style="display:inline-block; width:100px; text-align:right;">{cat}:</span>
                        <div style="display:inline-block; width:200px; height:20px; background-color:#eee; margin-left:10px; border-radius:3px;">
                            <div style="width:{percentage}%; height:100%; background-color:{color}; border-radius:3px;"></div>
                        </div>
                        <span style="margin-left:10px;">{count} ({percentage:.1f}%)</span>
                    </div>
                    """, unsafe_allow_html=True)
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
            - 總
