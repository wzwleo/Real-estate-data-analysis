#PLACE TYPE

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
        # 初始化狀態標記
        self._init_session_state()
    
    def _init_session_state(self):
        """初始化必要的 session state 變數"""
        defaults = {
            'analysis_in_progress': False,
            'analysis_mode': '單一房屋分析',
            'selected_houses': [],
            'current_page': 1,
            'last_gemini_call': 0,
            'template_selector_key': 'default',
            'prompt_editor_key': 'default_prompt'
            # 移除 category_coverage
        }
        
        for key, value in defaults.items():
            if key not in st.session_state:
                st.session_state[key] = value
    
    def render_comparison_tab(self):
        """渲染分析頁面 - 修正版本"""
        try:
            st.subheader("🏠 房屋分析模式")
            
            # 檢查是否有收藏
            fav_df = self._get_favorites_data()
            if fav_df.empty:
                st.info("⭐ 尚未有收藏房產，無法分析")
                return
            
            # 如果正在分析中，顯示進度並阻止其他互動
            if st.session_state.get('analysis_in_progress', False):
                self._show_analysis_in_progress()
                return
            
            # 顯示分析設定部分
            self._render_analysis_setup(fav_df)
            
            # 如果有分析結果，顯示結果
            if "analysis_results" in st.session_state:
                self._display_analysis_results(st.session_state.analysis_results)
                
        except Exception as e:
            st.error(f"❌ 渲染分析頁面時發生錯誤: {str(e)}")
            st.button("🔄 重新整理頁面", on_click=self._reset_page)
    
    def _show_analysis_in_progress(self):
        """顯示分析進行中的畫面"""
        st.warning("🔍 分析進行中，請稍候...")
        
        # 顯示進度指示器
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # 模擬進度更新
        for i in range(100):
            progress_bar.progress(i + 1)
            status_text.text(f"分析中... {i+1}%")
            time.sleep(0.01)
        
        # 完成後自動更新
        st.success("✅ 分析完成！")
        time.sleep(1)
        
        # 清除進度標記
        if 'analysis_in_progress' in st.session_state:
            st.session_state.analysis_in_progress = False
        
        st.rerun()
    
    def _reset_page(self):
        """重設頁面狀態"""
        keys_to_reset = [
            'analysis_in_progress',
            'analysis_results',
            'gemini_result',
            'current_page'
            # 移除 category_coverage
        ]
        for key in keys_to_reset:
            if key in st.session_state:
                del st.session_state[key]
    
    def _render_analysis_setup(self, fav_df):
        """渲染分析設定部分"""
        # 模式選擇
        analysis_mode = st.radio(
            "選擇分析模式",
            ["單一房屋分析", "多房屋比較"],
            horizontal=True,
            key="analysis_mode_radio",
            index=0 if st.session_state.get('analysis_mode', '單一房屋分析') == '單一房屋分析' else 1,
            on_change=self._on_analysis_mode_change
        )
        
        st.session_state.analysis_mode = analysis_mode
        
        options = fav_df['標題'] + " | " + fav_df['地址']
        selected_houses = []
        
        if analysis_mode == "單一房屋分析":
            # 單一房屋分析模式
            default_idx = 0 if len(options) > 0 else None
            choice_single = st.selectbox(
                "選擇要分析的房屋", 
                options, 
                key="compare_single_select",
                index=default_idx
            )
            
            if choice_single:
                selected_houses = [choice_single]
                house_info = fav_df[(fav_df['標題'] + " | " + fav_df['地址']) == choice_single].iloc[0]
                
                # 顯示預覽
                self._show_house_preview_single(house_info)
                
        else:  # 多房屋比較
            # 多房屋比較模式
            default_selections = options[:min(3, len(options))] if len(options) >= 1 else []
            selected_houses = st.multiselect(
                "選擇要比較的房屋（可選1個或多個）",
                options,
                default=default_selections,
                key="multi_compare_select"
            )
            
            if selected_houses:
                self._show_houses_preview_multi(fav_df, selected_houses)
        
        # 如果沒有選擇房屋，顯示提示並返回
        if not selected_houses:
            if analysis_mode == "多房屋比較" and len(options) > 0:
                st.info("ℹ️ 請至少選擇一個房屋進行比較")
            return
        
        st.session_state.selected_houses = selected_houses
        
        # 分析設定
        st.markdown("---")
        st.subheader("⚙️ 分析設定")
        
        # API Keys 檢查
        server_key = self._get_server_key()
        gemini_key = self._get_gemini_key()
        browser_key = self._get_browser_key()
        
        # 顯示 API 狀態
        col1, col2, col3 = st.columns(3)
        with col1:
            status = "✅" if server_key else "❌"
            st.metric("Server Key", status)
        with col2:
            status = "✅" if gemini_key else "❌"
            st.metric("Gemini Key", status)
        with col3:
            status = "✅" if browser_key else "❌"
            st.metric("Browser Key", status)
        
        # 搜尋設定
        radius = st.slider(
            "搜尋半徑 (公尺)", 
            100, 2000, DEFAULT_RADIUS, 100, 
            key="radius_slider_main"
        )
        
        keyword = st.text_input(
            "額外關鍵字搜尋 (可選)", 
            key="extra_keyword_main",
            placeholder="例如：公園、健身房、銀行等"
        )
        
        # 生活機能選擇 - 移除快速選擇，只保留自訂選擇
        st.markdown("---")
        st.subheader("🔍 選擇生活機能類別")
        
        selected_categories, selected_subtypes = self._render_category_selection()
        
        # 如果沒有選擇類別，顯示警告
        if not selected_categories:
            st.warning("⚠️ 請至少選擇一個生活機能類別")
        
        # 顯示選擇摘要
        if selected_categories:
            self._render_selection_summary(selected_categories, selected_subtypes)
        
        # 開始分析按鈕
        st.markdown("---")
        self._render_action_buttons(
            analysis_mode, selected_houses, selected_categories,
            radius, keyword, selected_subtypes, fav_df
        )
    
    def _on_analysis_mode_change(self):
        """當分析模式改變時的處理"""
        # 清除舊的結果和選擇
        keys_to_clear = [
            'selected_houses',
            'analysis_results',
            'gemini_result',
            'places_data',
            'custom_prompt'
            # 移除 category_coverage
        ]
        for key in keys_to_clear:
            if key in st.session_state:
                del st.session_state[key]
    
    def _show_house_preview_single(self, house_info):
        """顯示單一房屋預覽"""
        st.markdown("### 📋 選擇的房屋")
        
        # 使用卡片形式顯示
        with st.container():
            st.markdown(f"""
            <div style="border:2px solid #4CAF50; padding:15px; border-radius:10px; background-color:#f9f9f9; margin-bottom:20px;">
                <h4 style="color:#4CAF50; margin-top:0;">🏠 {house_info['標題'][:50]}</h4>
                <p><strong>地址：</strong>{house_info['地址']}</p>
            </div>
            """, unsafe_allow_html=True)
        
        # 顯示基本資訊
        col1, col2, col3 = st.columns(3)
        with col1:
            if '總價元' in house_info:
                st.metric("總價", f"{int(house_info['總價元']):,} 元")
        with col2:
            if '建物面積平方公尺' in house_info:
                st.metric("面積", f"{house_info['建物面積平方公尺']:.1f} ㎡")
        with col3:
            if '平均單價元平方公尺' in house_info:
                st.metric("單價", f"{int(house_info['平均單價元平方公尺']):,} 元/㎡")
    
    def _show_houses_preview_multi(self, fav_df, selected_houses):
        """顯示多房屋預覽"""
        st.markdown("### 📋 已選房屋清單")
        
        # 根據數量決定顯示方式
        num_houses = len(selected_houses)
        
        if num_houses == 1:
            house_info = fav_df[(fav_df['標題'] + " | " + fav_df['地址']) == selected_houses[0]].iloc[0]
            st.markdown(f"""
            <div style="border:2px solid #4CAF50; padding:15px; border-radius:10px; background-color:#f9f9f9;">
                <h4 style="color:#4CAF50; margin-top:0;">🏠 {house_info['標題'][:50]}</h4>
                <p><strong>地址：</strong>{house_info['地址']}</p>
            </div>
            """, unsafe_allow_html=True)
        else:
            # 分列顯示
            num_columns = min(3, num_houses)
            cols = st.columns(num_columns)
            
            for idx, house_option in enumerate(selected_houses):
                with cols[idx % num_columns]:
                    house_info = fav_df[(fav_df['標題'] + " | " + fav_df['地址']) == house_option].iloc[0]
                    
                    price_info = ""
                    if '平均單價元平方公尺' in house_info:
                        price = int(house_info['平均單價元平方公尺'])
                        price_info = f"<br>💰 {price:,} 元/㎡"
                    
                    house_letter = chr(65 + idx)
                    st.markdown(f"""
                    <div style="border:1px solid #ddd; padding:10px; border-radius:5px; margin-bottom:10px;">
                        <strong>房屋 {house_letter}</strong><br>
                        📍 {house_info['地址'][:20]}...<br>
                        {price_info}
                    </div>
                    """, unsafe_allow_html=True)
            
            # 顯示快速比較
            self._show_quick_comparison(fav_df, selected_houses)
    
    def _show_quick_comparison(self, fav_df, selected_houses):
        """顯示快速價格比較"""
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
            
            st.markdown("#### 💰 快速價格比較")
            col1, col2, col3 = st.columns(3)
            with col1:
                cheapest_idx = selected_houses.index(cheapest['option'])
                st.metric("最便宜", f"{int(cheapest['price']):,} 元/㎡", f"房屋 {chr(65 + cheapest_idx)}")
            with col2:
                expensive_idx = selected_houses.index(most_expensive['option'])
                st.metric("最昂貴", f"{int(most_expensive['price']):,} 元/㎡", f"房屋 {chr(65 + expensive_idx)}")
            with col3:
                st.metric("價格差距", f"{price_diff:.1f}%")
    
    def _render_category_selection(self):
        """渲染類別選擇界面 - 移除快速選擇，只保留自訂選擇"""
        selected_categories = []
        selected_subtypes = {}
        
        # 大類別選擇
        st.markdown("### 選擇大類別")
        all_categories = list(PLACE_TYPES.keys())
        
        category_selection = {}
        cols = st.columns(len(all_categories))
        
        for i, cat in enumerate(all_categories):
            with cols[i]:
                color = CATEGORY_COLORS.get(cat, "#000000")
                st.markdown(f"""
                <div style="text-align:center; margin-bottom:5px;">
                    <span style="background-color:{color}; color:white; padding:5px 10px; border-radius:5px;">
                        {cat}
                    </span>
                </div>
                """, unsafe_allow_html=True)
                
                checkbox_key = f"main_cat_{cat}"
                category_selection[cat] = st.checkbox(f"選擇{cat}", key=checkbox_key)
        
        # 細分設施選擇
        selected_main_cats = [cat for cat, selected in category_selection.items() if selected]
        
        if selected_main_cats:
            st.markdown("### 選擇細分設施")
            
            for cat_idx, cat in enumerate(selected_main_cats):
                with st.expander(f"📁 {cat} 類別細選", expanded=True):
                    select_all_key = f"select_all_{cat}"
                    select_all = st.checkbox(f"選擇所有{cat}設施", key=select_all_key)
                    
                    if select_all:
                        items = PLACE_TYPES[cat]
                        selected_subtypes[cat] = items[1::2]
                        selected_categories.append(cat)
                        st.info(f"已選擇 {cat} 全部 {len(items)//2} 種設施")
                    else:
                        items = PLACE_TYPES[cat]
                        num_columns = 3
                        num_items = len(items) // 2
                        items_per_row = (num_items + num_columns - 1) // num_columns
                        
                        for row in range(items_per_row):
                            cols = st.columns(num_columns)
                            for col_idx in range(num_columns):
                                item_idx = row + col_idx * items_per_row
                                if item_idx * 2 + 1 < len(items):
                                    chinese_name = items[item_idx * 2]
                                    english_keyword = items[item_idx * 2 + 1]
                                    
                                    with cols[col_idx]:
                                        checkbox_key = f"subcat_{cat}_{english_keyword}_{row}_{col_idx}"
                                        if st.checkbox(chinese_name, key=checkbox_key):
                                            if cat not in selected_subtypes:
                                                selected_subtypes[cat] = []
                                            selected_subtypes[cat].append(english_keyword)
                        
                        if cat in selected_subtypes and selected_subtypes[cat]:
                            selected_categories.append(cat)
        
        return selected_categories, selected_subtypes
    
    def _render_selection_summary(self, selected_categories, selected_subtypes):
        """渲染選擇摘要 - 簡化版，只顯示基本摘要"""
        st.markdown("---")
        st.subheader("📋 已選擇的設施摘要")
        
        # 使用網格布局顯示摘要
        num_cols = min(len(selected_categories), 4)
        summary_cols = st.columns(num_cols)
        
        for idx, cat in enumerate(selected_categories):
            with summary_cols[idx % num_cols]:
                if cat in selected_subtypes:
                    count = len(selected_subtypes[cat])
                    color = CATEGORY_COLORS.get(cat, "#000000")
                    
                    st.markdown(f"""
                    <div style="background-color:{color}20; padding:10px; border-radius:5px; 
                                border-left:4px solid {color}; margin-bottom:10px;">
                        <h4 style="color:{color}; margin:0;">{cat}</h4>
                        <p style="margin:5px 0 0 0;">已選擇 {count} 種設施</p>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # 顯示前幾個項目
                    if count <= 5:
                        chinese_names = []
                        for english_kw in selected_subtypes[cat]:
                            chinese_name = ENGLISH_TO_CHINESE.get(english_kw, english_kw)
                            chinese_names.append(chinese_name)
                        items_display = "、".join(chinese_names)
                        st.caption(f"✓ {items_display}")
                    else:
                        chinese_names = []
                        for english_kw in selected_subtypes[cat][:3]:
                            chinese_name = ENGLISH_TO_CHINESE.get(english_kw, english_kw)
                            chinese_names.append(chinese_name)
                        items_display = "、".join(chinese_names)
                        st.caption(f"✓ {items_display}等{count}種設施")
    
    def _render_action_buttons(self, analysis_mode, selected_houses, selected_categories, 
                              radius, keyword, selected_subtypes, fav_df):
        """渲染操作按鈕"""
        col_start, col_clear = st.columns([3, 1])
        
        with col_start:
            analyze_text = "🚀 開始分析" if analysis_mode == "單一房屋分析" else "🚀 開始比較"
            
            if st.button(analyze_text, type="primary", use_container_width=True, key="start_analysis_main"):
                # 驗證檢查
                validation_result = self._validate_analysis_inputs(
                    selected_houses, selected_categories
                )
                
                if validation_result != "OK":
                    st.error(validation_result)
                    return
                
                # 開始分析流程
                self._start_analysis_process(
                    analysis_mode, selected_houses, radius, keyword,
                    selected_categories, selected_subtypes, fav_df
                )
        
        with col_clear:
            if st.button("🗑️ 清除結果", type="secondary", use_container_width=True, key="clear_results_main"):
                self._clear_all_results()
                st.rerun()
    
    def _validate_analysis_inputs(self, selected_houses, selected_categories):
        """驗證分析輸入"""
        if not self._get_browser_key():
            return "❌ 請在側邊欄填入 Google Maps **Browser Key**"
        
        if not self._get_server_key() or not self._get_gemini_key():
            return "❌ 請在側邊欄填入 Server Key 與 Gemini Key"
        
        if not selected_categories:
            return "⚠️ 請至少選擇一個生活機能類別"
        
        if not selected_houses:
            return "⚠️ 請選擇要分析的房屋"
        
        return "OK"
    
    def _start_analysis_process(self, analysis_mode, selected_houses, radius, keyword,
                               selected_categories, selected_subtypes, fav_df):
        """開始分析流程"""
        try:
            # 儲存分析設定
            st.session_state.analysis_settings = {
                "analysis_mode": analysis_mode,
                "selected_houses": selected_houses,
                "radius": radius,
                "keyword": keyword,
                "selected_categories": selected_categories,
                "selected_subtypes": selected_subtypes,
                "server_key": self._get_server_key(),
                "gemini_key": self._get_gemini_key(),
                "fav_df_json": fav_df.to_json(orient='split')
            }
            
            # 清除舊結果
            self._clear_old_results()
            
            # 設置分析標記
            st.session_state.analysis_in_progress = True
            
            # 執行分析
            self._execute_analysis()
            
        except Exception as e:
            st.error(f"❌ 分析設定儲存失敗: {str(e)}")
            st.session_state.analysis_in_progress = False
    
    def _clear_old_results(self):
        """清除舊的分析結果"""
        keys_to_clear = [
            'analysis_results',
            'gemini_result',
            'places_data',
            'houses_data',
            'custom_prompt',
            'used_prompt'
            # 移除 category_coverage
        ]
        for key in keys_to_clear:
            if key in st.session_state:
                del st.session_state[key]
    
    def _clear_all_results(self):
        """清除所有結果"""
        keys_to_clear = [
            'analysis_settings',
            'analysis_results',
            'analysis_in_progress',
            'gemini_result',
            'gemini_key',
            'places_data',
            'houses_data',
            'custom_prompt',
            'used_prompt',
            'selected_template',
            'last_template',
            'selected_houses'
            # 移除 category_coverage
        ]
        for key in keys_to_clear:
            if key in st.session_state:
                del st.session_state[key]
    
    def _execute_analysis(self):
        """執行分析"""
        try:
            # 從 session state 恢復設定
            settings = st.session_state.analysis_settings
            fav_df = pd.read_json(settings["fav_df_json"], orient='split')
            
            # 顯示進度
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            # 步驟1: 取得房屋資料
            status_text.text("🔍 步驟 1/4: 解析房屋地址...")
            houses_data = {}
            
            for idx, house_option in enumerate(settings["selected_houses"]):
                house_info = fav_df[(fav_df['標題'] + " | " + fav_df['地址']) == house_option].iloc[0]
                house_name = f"房屋 {chr(65+idx)}" if len(settings["selected_houses"]) > 1 else "分析房屋"
                
                lat, lng = geocode_address(house_info["地址"], settings["server_key"])
                if lat is None or lng is None:
                    st.error(f"❌ {house_name} 地址解析失敗")
                    st.session_state.analysis_in_progress = False
                    return
                
                houses_data[house_name] = {
                    "name": house_name,
                    "title": house_info['標題'],
                    "address": house_info['地址'],
                    "lat": lat,
                    "lng": lng,
                    "original_name": house_info['標題']
                }
            
            progress_bar.progress(25)
            
            # 步驟2: 查詢周邊設施
            status_text.text("🔍 步驟 2/4: 查詢周邊設施...")
            places_data = {}
            
            total_houses = len(houses_data)
            for house_idx, (house_name, house_info) in enumerate(houses_data.items()):
                lat, lng = house_info["lat"], house_info["lng"]
                
                # 查詢設施（簡化版，不記錄覆蓋情況）
                places = self._query_google_places(
                    lat, lng, settings["server_key"], 
                    settings["selected_categories"], settings["selected_subtypes"],
                    settings["radius"], extra_keyword=settings["keyword"]
                )
                
                places_data[house_name] = places
                
                # 更新進度
                progress_value = 25 + int(((house_idx + 1) / total_houses) * 25)
                progress_bar.progress(progress_value)
            
            progress_bar.progress(50)
            
            # 步驟3: 計算統計
            status_text.text("📊 步驟 3/4: 計算統計資料...")
            facility_counts = {}
            
            for house_name, places in places_data.items():
                total_count = len(places)
                facility_counts[house_name] = total_count
            
            # 建立設施表格
            facilities_table = self._create_facilities_table(houses_data, places_data)
            
            progress_bar.progress(75)
            
            # 步驟4: 儲存結果
            status_text.text("💾 步驟 4/4: 儲存分析結果...")
            st.session_state.analysis_results = {
                "analysis_mode": settings["analysis_mode"],
                "houses_data": houses_data,
                "places_data": places_data,
                "facility_counts": facility_counts,
                "selected_categories": settings["selected_categories"],
                "radius": settings["radius"],
                "keyword": settings["keyword"],
                "num_houses": len(houses_data),
                "facilities_table": facilities_table
            }
            
            progress_bar.progress(100)
            status_text.text("✅ 分析完成！")
            
            # 標記分析完成
            st.session_state.analysis_in_progress = False
            
            # 重新運行以顯示結果
            time.sleep(1)
            st.rerun()
            
        except Exception as e:
            st.error(f"❌ 分析執行失敗: {str(e)}")
            st.session_state.analysis_in_progress = False
    
    def _query_google_places(self, lat, lng, api_key, selected_categories, selected_subtypes, radius=500, extra_keyword=""):
        """查詢Google Places（簡化版，不記錄覆蓋情況）"""
        results, seen = [], set()
        
        total_tasks = 0
        for cat in selected_categories:
            if cat in selected_subtypes:
                total_tasks += len(selected_subtypes[cat])
        total_tasks += (1 if extra_keyword else 0)

        if total_tasks == 0:
            return results

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
                
            for place_type in selected_subtypes[cat]:
                update_progress(f"查詢 {cat}-{place_type}")
                
                try:
                    places = self._search_nearby_places_by_type(lat, lng, api_key, place_type, radius)
                    
                    for p in places:
                        if p[5] > radius:
                            continue
                        pid = p[6]
                        if pid in seen:
                            continue
                        seen.add(pid)
                        
                        results.append((cat, place_type, p[2], p[3], p[4], p[5], p[6]))

                    time.sleep(0.3)
                    
                except Exception as e:
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
                pass

        progress.progress(1.0)
        progress_text.text("✅ 查詢完成！")
        results.sort(key=lambda x: x[5])
        
        return results
    
    def _display_analysis_results(self, results):
        """顯示分析結果"""
        try:
            # 確保有結果才顯示
            if not results:
                return
            
            analysis_mode = results["analysis_mode"]
            
            # 顯示分析標題
            st.markdown("---")
            if analysis_mode == "單一房屋分析":
                st.markdown(f"## 📊 單一房屋分析結果")
            else:
                st.markdown(f"## 📊 比較結果 ({results['num_houses']}間房屋)")
            
            # 顯示設施表格
            self._display_facilities_table(results)
            
            # 顯示統計分析
            self._display_statistics_analysis(results)
            
            # 顯示地圖
            self._display_maps(results)
            
            # AI 分析部分
            self._display_ai_analysis_section(results)
            
        except Exception as e:
            st.error(f"❌ 顯示分析結果時發生錯誤: {str(e)}")
    
    def _display_facilities_table(self, results):
        """顯示設施表格"""
        st.markdown("---")
        st.subheader("📋 設施詳細資料表格")
        
        facilities_table = results.get("facilities_table", pd.DataFrame())
        
        if not facilities_table.empty:
            st.info(f"📈 共找到 {len(facilities_table)} 筆設施資料")
            
            # 顯示前50筆資料
            st.dataframe(
                facilities_table.head(50),
                use_container_width=True,
                column_config={
                    "房屋": st.column_config.TextColumn(width="small"),
                    "房屋標題": st.column_config.TextColumn(width="medium"),
                    "房屋地址": st.column_config.TextColumn(width="medium"),
                    "設施名稱": st.column_config.TextColumn(width="large"),
                    "設施子類別": st.column_config.TextColumn(
                        width="small",
                        help="設施的具體類型"
                    ),
                    "距離(公尺)": st.column_config.NumberColumn(
                        format="%d 公尺",
                        help="設施距離房屋的距離（公尺）"
                    ),
                },
                hide_index=True
            )
            
            # 下載按鈕
            csv_data = facilities_table.to_csv(index=False, encoding='utf-8-sig')
            st.download_button(
                label="📥 下載完整設施資料 (CSV)",
                data=csv_data,
                file_name=f"設施資料_{time.strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                key="download_facilities_csv"
            )
    
    def _display_statistics_analysis(self, results):
        """顯示統計分析"""
        st.markdown("---")
        st.subheader("📈 設施統計")
        
        if results["num_houses"] == 1 or results["analysis_mode"] == "單一房屋分析":
            self._display_single_house_stats(results)
        else:
            self._display_multi_houses_stats(results)
    
    def _display_single_house_stats(self, results):
        """顯示單一房屋統計"""
        house_name = list(results["houses_data"].keys())[0]
        count = results["facility_counts"].get(house_name, 0)
        places = results["places_data"][house_name]
        
        if places:
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
            
            # 設施子類別分布
            subtype_data = {}
            for cat, subtype, name, lat, lng, dist, pid in places:
                chinese_subtype = ENGLISH_TO_CHINESE.get(subtype, subtype)
                subtype_data[chinese_subtype] = subtype_data.get(chinese_subtype, 0) + 1
            
            if subtype_data:
                st.markdown("### 🏪 各類型設施分布")
                
                # 按數量排序
                sorted_subtypes = sorted(subtype_data.items(), key=lambda x: x[1], reverse=True)
                
                # 只顯示前20個，避免圖表過於擁擠
                if len(sorted_subtypes) > 20:
                    sorted_subtypes = sorted_subtypes[:20]
                
                chart_data = {
                    "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}},
                    "grid": {"left": "3%", "right": "4%", "bottom": "15%", "top": "10%", "containLabel": True},
                    "xAxis": {
                        "type": "category",
                        "data": [item[0] for item in sorted_subtypes],
                        "axisLabel": {
                            "rotate": 45,
                            "interval": 0
                        }
                    },
                    "yAxis": {"type": "value"},
                    "series": [{
                        "type": "bar",
                        "data": [item[1] for item in sorted_subtypes],
                        "itemStyle": {
                            "color": {
                                "type": "linear",
                                "x": 0, "y": 0, "x2": 0, "y2": 1,
                                "colorStops": [
                                    {"offset": 0, "color": "#5470c6"},
                                    {"offset": 1, "color": "#91cc75"}
                                ]
                            }
                        },
                        "label": {
                            "show": True,
                            "position": "top"
                        }
                    }]
                }
                
                st_echarts(chart_data, height="500px")
                
                # 顯示子類別統計表
                with st.expander("📊 查看詳細設施類型統計"):
                    subtype_df = pd.DataFrame(sorted_subtypes, columns=["設施類型", "數量"])
                    st.dataframe(
                        subtype_df,
                        use_container_width=True,
                        hide_index=True
                    )
    
    def _display_multi_houses_stats(self, results):
        """顯示多房屋統計"""
        houses_data = results["houses_data"]
        facility_counts = results["facility_counts"]
        
        # 顯示每個房屋的統計
        num_houses = len(houses_data)
        max_facilities = max(facility_counts.values()) if facility_counts else 0
        
        stat_cols = st.columns(min(num_houses, 4))
        
        for idx, house_name in enumerate(houses_data.keys()):
            with stat_cols[idx % len(stat_cols)]:
                count = facility_counts.get(house_name, 0)
                
                st.metric(
                    f"🏠 {house_name}",
                    f"{count} 個設施",
                    f"排名: {sorted(facility_counts.values(), reverse=True).index(count) + 1}/{num_houses}"
                )
        
        # 顯示排名圖表
        if num_houses > 1:
            st.markdown("### 📊 設施數量排名")
            
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
            
            # 多房屋比較時，也顯示子類別分布
            st.markdown("### 🏪 各房屋設施類型比較")
            
            # 為每個房屋計算子類別分布
            all_subtypes = set()
            house_subtype_data = {}
            
            for house_name in houses_data.keys():
                places = results["places_data"][house_name]
                subtype_counts = {}
                
                for cat, subtype, name, lat, lng, dist, pid in places:
                    chinese_subtype = ENGLISH_TO_CHINESE.get(subtype, subtype)
                    subtype_counts[chinese_subtype] = subtype_counts.get(chinese_subtype, 0) + 1
                    all_subtypes.add(chinese_subtype)
                
                house_subtype_data[house_name] = subtype_counts
            
            # 轉換為比較圖表
            if all_subtypes and num_houses <= 5:  # 避免圖表過於複雜
                # 只取數量最多的前10個子類別
                subtype_totals = {}
                for subtype in all_subtypes:
                    total = sum(house_subtype_data.get(house_name, {}).get(subtype, 0) for house_name in houses_data.keys())
                    subtype_totals[subtype] = total
                
                top_subtypes = sorted(subtype_totals.items(), key=lambda x: x[1], reverse=True)[:10]
                top_subtype_names = [item[0] for item in top_subtypes]
                
                # 建立比較圖表
                series_data = []
                for house_name in houses_data.keys():
                    data = []
                    for subtype in top_subtype_names:
                        data.append(house_subtype_data.get(house_name, {}).get(subtype, 0))
                    
                    series_data.append({
                        "name": house_name,
                        "type": "bar",
                        "data": data
                    })
                
                comparison_chart = {
                    "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}},
                    "legend": {"data": list(houses_data.keys())},
                    "grid": {"left": "3%", "right": "4%", "bottom": "15%", "top": "15%", "containLabel": True},
                    "xAxis": {
                        "type": "category",
                        "data": top_subtype_names,
                        "axisLabel": {"rotate": 45}
                    },
                    "yAxis": {"type": "value"},
                    "series": series_data
                }
                
                st_echarts(comparison_chart, height="400px")
    
    def _display_maps(self, results):
        """顯示地圖"""
        st.markdown("---")
        st.subheader("🗺️ 地圖檢視")
        
        houses_data = results["houses_data"]
        places_data = results["places_data"]
        radius = results["radius"]
        num_houses = results["num_houses"]
        analysis_mode = results["analysis_mode"]
        
        browser_key = self._get_browser_key()
        if not browser_key:
            st.error("❌ 請在側邊欄填入 Google Maps Browser Key")
            return
        
        if num_houses == 1 or analysis_mode == "單一房屋分析":
            # 單一房屋地圖
            house_name = list(houses_data.keys())[0]
            house_info = houses_data[house_name]
            
            self._render_map_improved(
                house_info["lat"], 
                house_info["lng"], 
                places_data[house_name], 
                radius, 
                title=house_name,
                house_info=house_info,
                browser_key=browser_key
            )
            
        elif num_houses <= 3:
            # 並排顯示地圖
            map_cols = st.columns(num_houses)
            for idx, (house_name, house_info) in enumerate(houses_data.items()):
                with map_cols[idx]:
                    st.markdown(f"### {house_name}")
                    self._render_map_improved(
                        house_info["lat"], 
                        house_info["lng"], 
                        places_data[house_name], 
                        radius, 
                        title=house_name,
                        house_info=house_info,
                        browser_key=browser_key
                    )
        else:
            # 使用選項卡顯示地圖
            map_tabs = st.tabs([f"{house_name}" for house_name in houses_data.keys()])
            
            for idx, (house_name, house_info) in enumerate(houses_data.items()):
                with map_tabs[idx]:
                    self._render_map_improved(
                        house_info["lat"], 
                        house_info["lng"], 
                        places_data[house_name], 
                        radius, 
                        title=house_name,
                        house_info=house_info,
                        browser_key=browser_key
                    )
    
    def _render_map_improved(self, lat, lng, places, radius, title="房屋", house_info=None, browser_key=""):
        """改良版地圖渲染"""
        if not browser_key:
            st.error("❌ 請在側邊欄填入 Google Maps Browser Key")
            return
        
        if not places:
            st.info(f"📭 {title} 周圍半徑 {radius} 公尺內未找到設施")
            return
        
        # 準備設施資料
        facilities_data = []
        for cat, subtype, name, p_lat, p_lng, dist, pid in places:
            color = CATEGORY_COLORS.get(cat, "#000000")
            chinese_subtype = ENGLISH_TO_CHINESE.get(subtype, subtype)
            facilities_data.append({
                "name": name,
                "category": cat,
                "subtype": chinese_subtype,  # 使用中文子類別
                "lat": p_lat,
                "lng": p_lng,
                "distance": dist,
                "color": color,
                "maps_url": f"https://www.google.com/maps/search/?api=1&query={p_lat},{p_lng}&query_place_id={pid}"
            })
        
        # 建立HTML地圖
        html_content = self._generate_map_html(
            lat, lng, facilities_data, radius, title, house_info, browser_key
        )
        
        # 顯示地圖
        st.markdown(f"**🗺️ {title} - 周邊設施地圖**")
        st.markdown(f"📊 **共找到 {len(places)} 個設施** (搜尋半徑: {radius}公尺)")
        html(html_content, height=550)
        
        # 顯示設施列表
        self._display_facilities_list(places)
    
    def _generate_map_html(self, lat, lng, facilities_data, radius, title, house_info, browser_key):
        """生成地圖HTML"""
        categories = {}
        for facility in facilities_data:
            cat = facility["category"]
            if cat not in categories:
                categories[cat] = facility["color"]
        
        # 生成圖例HTML
        legend_html = ""
        for cat, color in categories.items():
            legend_html += f"""
            <div class="legend-item">
                <div class="legend-color" style="background-color:{color};"></div>
                <span>{cat}</span>
            </div>
            """
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>{title} 周邊設施地圖</title>
            <style>
                #map {{
                    height: 500px;
                    width: 100%;
                }}
                #legend {{
                    background: white;
                    padding: 10px;
                    border: 1px solid #ccc;
                    border-radius: 5px;
                    font-size: 12px;
                    margin: 10px;
                    max-width: 200px;
                }}
                .legend-item {{
                    display: flex;
                    align-items: center;
                    margin-bottom: 5px;
                }}
                .legend-color {{
                    width: 12px;
                    height: 12px;
                    margin-right: 5px;
                    border-radius: 2px;
                }}
            </style>
        </head>
        <body>
            <div id="map"></div>
            
            <script>
                function initMap() {{
                    console.log('開始初始化地圖...');
                    
                    // 中心點座標
                    var center = {{lat: {lat}, lng: {lng}}};
                    
                    // 建立地圖
                    var map = new google.maps.Map(document.getElementById('map'), {{
                        zoom: 16,
                        center: center,
                        mapTypeControl: true,
                        streetViewControl: true,
                        fullscreenControl: true
                    }});
                    
                    // 主房屋標記
                    var mainMarker = new google.maps.Marker({{
                        position: center,
                        map: map,
                        title: "{title}",
                        icon: {{
                            url: "http://maps.google.com/mapfiles/ms/icons/red-dot.png",
                            scaledSize: new google.maps.Size(40, 40)
                        }},
                        zIndex: 1000
                    }});
                    
                    // 主房屋資訊視窗
                    var mainInfoContent = '<div style="padding:15px;">' +
                                         '<h4 style="margin-top:0; color:#d32f2f;">🏠 {title}</h4>' +
                                         '<p><strong>地址：</strong>{house_info["address"] if house_info else "未知"}</p>' +
                                         '<p><strong>搜尋半徑：</strong>{radius} 公尺</p>' +
                                         '<p><strong>設施數量：</strong>{len(facilities_data)} 個</p>' +
                                         '</div>';
                    
                    var mainInfoWindow = new google.maps.InfoWindow({{
                        content: mainInfoContent
                    }});
                    
                    mainMarker.addListener("click", function() {{
                        mainInfoWindow.open(map, mainMarker);
                    }});
                    
                    // 建立圖例
                    var legendDiv = document.createElement('div');
                    legendDiv.id = 'legend';
                    legendDiv.innerHTML = '<h4 style="margin-top:0; margin-bottom:10px;">設施類別圖例</h4>' + `{legend_html}`;
                    map.controls[google.maps.ControlPosition.RIGHT_TOP].push(legendDiv);
                    
                    // 添加設施標記
                    var facilities = {json.dumps(facilities_data, ensure_ascii=False)};
                    
                    facilities.forEach(function(facility) {{
                        var position = {{lat: facility.lat, lng: facility.lng}};
                        
                        var marker = new google.maps.Marker({{
                            position: position,
                            map: map,
                            title: facility.name + " (" + facility.distance + "m)",
                            icon: {{
                                path: google.maps.SymbolPath.CIRCLE,
                                scale: 8,
                                fillColor: facility.color,
                                fillOpacity: 0.9,
                                strokeColor: "#FFFFFF",
                                strokeWeight: 2
                            }},
                            animation: google.maps.Animation.DROP
                        }});
                        
                        var infoContent = '<div style="padding:10px; max-width:250px;">' +
                                          '<h5 style="margin-top:0; margin-bottom:5px;">' + facility.name + '</h5>' +
                                          '<p style="margin:5px 0;">' +
                                          '<span style="color:' + facility.color + '; font-weight:bold;">' + 
                                          facility.category + ' - ' + facility.subtype + 
                                          '</span></p>' +
                                          '<p style="margin:5px 0;"><strong>距離：</strong>' + facility.distance + ' 公尺</p>' +
                                          '<a href="' + facility.maps_url + '" target="_blank" ' +
                                          'style="display:inline-block; margin-top:5px; padding:5px 10px; ' +
                                          'background-color:#1a73e8; color:white; text-decoration:none; ' +
                                          'border-radius:3px; font-size:12px;">' +
                                          '🗺️ 在 Google 地圖中查看</a>' +
                                          '</div>';
                        
                        var infoWindow = new google.maps.InfoWindow({{
                            content: infoContent
                        }});
                        
                        marker.addListener("click", function() {{
                            infoWindow.open(map, marker);
                        }});
                    }});
                    
                    // 繪製搜尋半徑圓
                    var circle = new google.maps.Circle({{
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
                    
                    console.log('地圖初始化完成');
                }}
                
                // 錯誤處理
                function handleMapError() {{
                    console.error('地圖載入失敗');
                    document.getElementById('map').innerHTML = 
                        '<div style="padding:20px; text-align:center; color:red;">' +
                        '<h3>❌ 地圖載入失敗</h3>' +
                        '<p>請檢查：</p>' +
                        '<ul style="text-align:left;">' +
                        '<li>Google Maps API Key 是否正確</li>' +
                        '<li>網路連線是否正常</li>' +
                        '<li>API Key 是否有足夠配額</li>' +
                        '</ul></div>';
                }}
            </script>
            
            <script src="https://maps.googleapis.com/maps/api/js?key={browser_key}&callback=initMap" 
                    async defer 
                    onerror="handleMapError()"></script>
        </body>
        </html>
        """
        return html_content
    
    def _display_facilities_list(self, places):
        """顯示設施列表"""
        st.markdown("### 📍 全部設施列表")
        
        if len(places) > 0:
            with st.expander(f"顯示所有 {len(places)} 個設施", expanded=True):
                for i, (cat, subtype, name, lat, lng, dist, pid) in enumerate(places, 1):
                    color = CATEGORY_COLORS.get(cat, "#000000")
                    chinese_subtype = ENGLISH_TO_CHINESE.get(subtype, subtype)
                    maps_url = f"https://www.google.com/maps/search/?api=1&query={lat},{lng}&query_place_id={pid}"
                    
                    # 距離分類
                    if dist <= 300:
                        dist_color = "#28a745"
                        dist_class = "很近"
                    elif dist <= 600:
                        dist_color = "#ffc107"
                        dist_class = "中等"
                    else:
                        dist_color = "#dc3545"
                        dist_class = "較遠"
                    
                    with st.container():
                        col1, col2, col3, col4 = st.columns([6, 2, 2, 2])
                        
                        with col1:
                            st.write(f"**{i}.**")
                            st.write(f"**{name}**")
                        
                        with col2:
                            st.markdown(f'<span style="background-color:{color}20; color:{color}; padding:4px 8px; border-radius:8px; font-size:12px; font-weight:bold;">{chinese_subtype}</span>', unsafe_allow_html=True)
                        
                        with col3:
                            st.markdown(f'<span style="background-color:{dist_color}20; color:{dist_color}; padding:4px 8px; border-radius:8px; font-size:12px; font-weight:bold;">{dist}公尺</span>', unsafe_allow_html=True)
                        
                        with col4:
                            st.link_button("🗺️ 地圖", maps_url)
                        
                        st.divider()
        else:
            st.info("📭 未找到任何設施")
    
    def _display_ai_analysis_section(self, results):
        """顯示AI分析部分"""
        st.markdown("---")
        st.subheader("🤖 AI 智能分析")
        
        # 準備AI分析資料
        analysis_text = self._prepare_analysis_prompt(
            results["houses_data"], 
            results["places_data"], 
            results["facility_counts"], 
            results["selected_categories"],
            results["radius"],
            results["keyword"],
            results["analysis_mode"],
            results.get("facilities_table", pd.DataFrame())
        )
        
        # 初始化自訂提示詞
        if "custom_prompt" not in st.session_state:
            st.session_state.custom_prompt = analysis_text
        
        # 模板選擇
        st.markdown("### 📋 提示詞模板選擇")
        templates = self._get_prompt_templates(results["analysis_mode"])
        
        template_options = {k: f"{v['name']} - {v['description']}" for k, v in templates.items()}
        
        selected_template = st.selectbox(
            "選擇提示詞模板",
            options=list(template_options.keys()),
            format_func=lambda x: template_options[x],
            key="template_selector_ai"
        )
        
        # 更新提示詞內容
        if selected_template == "default":
            st.session_state.custom_prompt = analysis_text
        elif "content" in templates[selected_template]:
            st.session_state.custom_prompt = templates[selected_template]["content"]
        
        # 顯示提示詞編輯區域
        st.markdown("### 📝 AI 分析提示詞設定")
        
        col_prompt, col_info = st.columns([3, 1])
        
        with col_prompt:
            edited_prompt = st.text_area(
                "編輯AI分析提示詞",
                value=st.session_state.custom_prompt,
                height=400,
                key="prompt_editor_ai"
            )
            
            if st.button("💾 儲存提示詞修改", type="secondary", use_container_width=True, key="save_prompt_btn_ai"):
                st.session_state.custom_prompt = edited_prompt
                st.success("✅ 提示詞已儲存！")
        
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
            """)
            
            if st.button("🔄 恢復預設提示詞", type="secondary", use_container_width=True, key="reset_prompt_btn_ai"):
                st.session_state.custom_prompt = analysis_text
                st.rerun()
        
        # 開始AI分析按鈕
        if st.button("🚀 開始AI分析", type="primary", use_container_width=True, key="start_ai_analysis_main"):
            self._start_gemini_analysis(edited_prompt)
        
        # 顯示AI分析結果
        if "gemini_result" in st.session_state:
            self._display_gemini_result()
    
    def _start_gemini_analysis(self, prompt):
        """開始Gemini分析"""
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
                gemini_key = st.session_state.get("GEMINI_KEY", "")
                
                if not gemini_key:
                    st.error("❌ 請在側邊欄填入 Gemini Key")
                    return
                
                genai.configure(api_key=gemini_key)
                model = genai.GenerativeModel("gemini-2.0-flash")
                
                resp = model.generate_content(prompt)
                
                # 儲存結果
                st.session_state.gemini_result = resp.text
                st.session_state.used_prompt = prompt
                
                st.rerun()
                
            except Exception as e:
                st.error(f"❌ Gemini API 錯誤: {str(e)}")
    
    def _display_gemini_result(self):
        """顯示Gemini結果"""
        st.markdown("### 📋 AI 分析報告")
        
        # 顯示使用的提示詞摘要
        if "used_prompt" in st.session_state:
            with st.expander("ℹ️ 查看本次使用的提示詞摘要", expanded=False):
                used_prompt = st.session_state.used_prompt
                prompt_preview = used_prompt[:500] + ("..." if len(used_prompt) > 500 else "")
                st.text(prompt_preview)
        
        # 顯示分析結果
        with st.container():
            st.markdown("---")
            st.markdown(st.session_state.gemini_result)
            st.markdown("---")
        
        # 重新分析按鈕
        if st.button("🔄 重新分析", type="secondary", use_container_width=True, key="reanalyze_btn_main"):
            del st.session_state.gemini_result
            del st.session_state.used_prompt
            st.rerun()
        
        # 下載報告
        if "analysis_results" in st.session_state:
            results = st.session_state.analysis_results
            report_title = "房屋分析報告" if results["analysis_mode"] == "單一房屋分析" else f"{results['num_houses']}間房屋比較報告"
            
            report_text = f"{report_title}\n生成時間：{time.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            report_text += f"AI 分析結果：\n{st.session_state.gemini_result}"
            
            st.download_button(
                label="📥 下載分析報告",
                data=report_text,
                file_name=f"{report_title}_{time.strftime('%Y%m%d_%H%M%S')}.txt",
                mime="text/plain",
                use_container_width=True,
                key="download_report_btn_main"
            )
    
    def _create_facilities_table(self, houses_data, places_data):
        """建立設施表格資料"""
        all_facilities = []
        
        for house_name, places in places_data.items():
            house_info = houses_data[house_name]
            
            for i, (cat, subtype, name, lat, lng, dist, pid) in enumerate(places):
                chinese_subtype = ENGLISH_TO_CHINESE.get(subtype, subtype)
                
                facility_info = {
                    "房屋": house_name,
                    "房屋標題": house_info['title'][:50],
                    "房屋地址": house_info['address'],
                    "設施編號": i + 1,
                    "設施名稱": name,
                    "設施子類別": chinese_subtype,
                    "距離(公尺)": dist,
                    "經度": lng,
                    "緯度": lat,
                    "place_id": pid
                }
                all_facilities.append(facility_info)
        
        return pd.DataFrame(all_facilities)
    
    def _prepare_analysis_prompt(self, houses_data, places_data, facility_counts, 
                                selected_categories, radius, keyword, analysis_mode, facilities_table):
        """準備分析提示詞"""
        if analysis_mode == "單一房屋分析":
            house_name = list(houses_data.keys())[0]
            house_info = houses_data[house_name]
            places = places_data[house_name]
            count = facility_counts.get(house_name, 0)
            
            distances = [p[5] for p in places]
            avg_distance = sum(distances) / len(distances) if distances else 0
            min_distance = min(distances) if distances else 0
            
            # 設施子類別統計
            subtype_stats = {}
            for cat, subtype, name, lat, lng, dist, pid in places:
                chinese_subtype = ENGLISH_TO_CHINESE.get(subtype, subtype)
                subtype_stats[chinese_subtype] = subtype_stats.get(chinese_subtype, 0) + 1
            
            table_summary = ""
            if not facilities_table.empty:
                sample_facilities = facilities_table.head(20).to_string(index=False)
                table_summary = f"""
                
                【設施表格摘要（前20筆）】
                以下是搜尋到的設施表格資料：
                {sample_facilities}
                
                【表格欄位說明】
                - 房屋：房屋名稱
                - 房屋標題：房屋詳細標題
                - 房屋地址：房屋地址
                - 設施名稱：設施名稱
                - 設施子類別：設施的具體類型（如超市、便利商店等）
                - 距離(公尺)：設施距離房屋的距離
                - 經度、緯度：設施的GPS座標
                """
            
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
            
            【各類型設施數量】
            {chr(10).join([f'- {subtype}: {num} 個' for subtype, num in sorted(subtype_stats.items(), key=lambda x: x[1], reverse=True)])}
            
            {table_summary}
            
            【請分析以下面向】
            1. 生活便利性評估（以1-5星評分）
            2. 設施完整性分析（哪些設施類型充足，哪些缺乏）
            3. 適合的居住族群分析（單身、小家庭、大家庭、退休族等）
            4. 投資潛力評估（以1-5星評分）
            5. 優點總結（至少3點）
            6. 缺點提醒（至少2點）
            7. 建議改善或補充的生活機能
            8. 綜合評價與建議
            
            請使用專業但易懂的語言，提供具體、實用的建議。
            """
        
        else:  # 多房屋比較
            num_houses = len(houses_data)
            
            if num_houses == 1:
                house_name = list(houses_data.keys())[0]
                house_info = houses_data[house_name]
                places = places_data[house_name]
                count = facility_counts.get(house_name, 0)
                
                distances = [p[5] for p in places]
                avg_distance = sum(distances) / len(distances) if distances else 0
                
                # 設施子類別統計
                subtype_stats = {}
                for cat, subtype, name, lat, lng, dist, pid in places:
                    chinese_subtype = ENGLISH_TO_CHINESE.get(subtype, subtype)
                    subtype_stats[chinese_subtype] = subtype_stats.get(chinese_subtype, 0) + 1
                
                table_summary = ""
                if not facilities_table.empty:
                    sample_facilities = facilities_table.head(15).to_string(index=False)
                    table_summary = f"""
                    
                    【設施表格摘要（前15筆）】
                    {sample_facilities}
                    """
                
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
                
                【各類型設施數量】
                {chr(10).join([f'- {subtype}: {num} 個' for subtype, num in sorted(subtype_stats.items(), key=lambda x: x[1], reverse=True)])}
                
                {table_summary}
                
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
                
                # 建立表格摘要
                table_summary = ""
                if not facilities_table.empty:
                    table_summary = "\n\n【各房屋設施摘要】\n"
                    for house_name in houses_data.keys():
                        house_facilities = facilities_table[facilities_table['房屋'] == house_name].head(10)
                        if not house_facilities.empty:
                            table_summary += f"\n{house_name} 的前10個設施：\n"
                            table_summary += house_facilities[['設施名稱', '設施子類別', '距離(公尺)']].to_string(index=False) + "\n"
                
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
                
                {table_summary}
                
                【請依序分析】
                1. 總體設施豐富度排名與分析
                2. 各類型設施完整性比較
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
            "type": place_type,
            "key": api_key,
            "language": "zh-TW"
        }

        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            r = response.json()
        except requests.exceptions.Timeout:
            return []
        except Exception as e:
            return []

        results = []
        if r.get("status") != "OK":
            return []

        for p in r.get("results", []):
            loc = p["geometry"]["location"]
            dist = int(haversine(lat, lng, loc["lat"], loc["lng"]))
            
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


def get_comparison_analyzer():
    """取得比較分析器實例"""
    return ComparisonAnalyzer()   
