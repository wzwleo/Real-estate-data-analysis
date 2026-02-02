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
        
        # 初始化 session state 變數
        self._init_session_state()
        
        # 模式選擇 - 兩種模式
        analysis_mode = st.radio(
            "選擇分析模式",
            ["單一房屋分析", "多房屋比較"],
            horizontal=True,
            key="analysis_mode",
            on_change=self._clear_selections_on_mode_change
        )
        
        options = fav_df['標題'] + " | " + fav_df['地址']
        selected_houses = []
        
        if analysis_mode == "單一房屋分析":
            # 單一房屋分析模式
            default_index = 0
            if "last_single_selection" in st.session_state:
                try:
                    default_index = list(options).index(st.session_state.last_single_selection)
                except:
                    default_index = 0
            
            choice_single = st.selectbox("選擇要分析的房屋", options, key="compare_single", index=default_index)
            
            if choice_single:
                selected_houses = [choice_single]
                st.session_state.last_single_selection = choice_single
                
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
            default_selections = []
            if "last_multi_selections" in st.session_state:
                # 只保留仍然存在的選項
                for selection in st.session_state.last_multi_selections:
                    if selection in list(options):
                        default_selections.append(selection)
            
            # 確保至少有1個預設選擇
            if not default_selections and len(options) > 0:
                default_selections = options[:min(1, len(options))]
            
            selected_houses = st.multiselect(
                "選擇要比較的房屋（可選1個或多個）",
                options,
                default=default_selections,
                key="multi_compare"
            )
            
            if selected_houses:
                st.session_state.last_multi_selections = selected_houses
            
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

                # 儲存所有分析設定
                st.session_state.analysis_settings = {
                    "analysis_mode": analysis_mode,
                    "selected_houses": selected_houses,
                    "radius": radius,
                    "keyword": keyword,
                    "selected_categories": selected_categories,
                    "selected_subtypes": selected_subtypes,
                    "server_key": server_key,
                    "gemini_key": gemini_key,
                    "fav_df_json": fav_df.to_json(orient='split')
                }
                
                # 清除舊的結果
                if "analysis_results" in st.session_state:
                    del st.session_state.analysis_results
                if "gemini_result" in st.session_state:
                    del st.session_state.gemini_result
                
                # 設置分析標記
                st.session_state.analysis_in_progress = True
                
                # 重新運行
                st.rerun()
        
        with col_clear:
            if st.button("🗑️ 清除結果", type="secondary", use_container_width=True, key="clear_results"):
                # 清除所有相關的 session state
                keys_to_clear = [
                    'analysis_settings', 'analysis_results', 'analysis_in_progress',
                    'gemini_result', 'gemini_key', 'places_data', 'houses_data', 
                    'custom_prompt', 'used_prompt', 'selected_template', 'last_template',
                    'last_single_selection', 'last_multi_selections', 'current_page'
                ]
                for key in keys_to_clear:
                    if key in st.session_state:
                        del st.session_state[key]
                st.rerun()
        
        # 檢查是否需要執行分析
        if "analysis_settings" in st.session_state and st.session_state.get("analysis_in_progress", False):
            # 從 session state 恢復設定
            settings = st.session_state.analysis_settings
            
            # 恢復 DataFrame
            fav_df = pd.read_json(settings["fav_df_json"], orient='split')
            
            # 執行分析
            with st.spinner("🔍 執行分析中..."):
                try:
                    # 取得房屋資料
                    houses_data = {}
                    
                    # 地址解析
                    for idx, house_option in enumerate(settings["selected_houses"]):
                        house_info = fav_df[(fav_df['標題'] + " | " + fav_df['地址']) == house_option].iloc[0]
                        house_name = f"房屋 {chr(65+idx)}" if len(settings["selected_houses"]) > 1 else "分析房屋"
                        
                        lat, lng = geocode_address(house_info["地址"], settings["server_key"])
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
                        lat, lng = house_info["lat"], house_info["lng"]
                        
                        places = self._query_google_places_keyword(
                            lat, lng, settings["server_key"], 
                            settings["selected_categories"], settings["selected_subtypes"],
                            settings["radius"], extra_keyword=settings["keyword"]
                        )
                        
                        places_data[house_name] = places
                    
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
                    
                    # 建立設施表格資料供AI分析
                    facilities_table = self._create_facilities_table(houses_data, places_data)
                    
                    # 儲存結果到 session state
                    st.session_state.analysis_results = {
                        "analysis_mode": settings["analysis_mode"],
                        "houses_data": houses_data,
                        "places_data": places_data,
                        "facility_counts": facility_counts,
                        "category_counts": category_counts,
                        "selected_categories": settings["selected_categories"],
                        "radius": settings["radius"],
                        "keyword": settings["keyword"],
                        "num_houses": len(houses_data),
                        "facilities_table": facilities_table  # 新增設施表格
                    }
                    
                    # 標記分析完成
                    st.session_state.analysis_in_progress = False
                    
                    # 重新運行以顯示結果
                    st.rerun()
                    
                except Exception as e:
                    st.error(f"❌ 分析執行失敗: {str(e)}")
                    st.session_state.analysis_in_progress = False
                    return
        
        # 顯示分析結果
        if "analysis_results" in st.session_state:
            self._display_analysis_results(st.session_state.analysis_results)
    
    def _init_session_state(self):
        """初始化 session state 變數"""
        if "analysis_mode" not in st.session_state:
            st.session_state.analysis_mode = "單一房屋分析"
        
        if "last_single_selection" not in st.session_state:
            st.session_state.last_single_selection = None
        
        if "last_multi_selections" not in st.session_state:
            st.session_state.last_multi_selections = []
        
        if "current_page" not in st.session_state:
            st.session_state.current_page = 1
        
        # 確保 current_page 是整數
        self._ensure_page_number_is_int()
    
    def _ensure_page_number_is_int(self):
        """確保 current_page 是整數"""
        if "current_page" in st.session_state:
            if isinstance(st.session_state.current_page, str):
                try:
                    st.session_state.current_page = int(st.session_state.current_page)
                except (ValueError, TypeError):
                    st.session_state.current_page = 1
            elif not isinstance(st.session_state.current_page, int):
                st.session_state.current_page = 1
            
            # 確保頁碼是正整數
            if st.session_state.current_page < 1:
                st.session_state.current_page = 1
    
    def _get_safe_page_number(self):
        """安全地取得頁碼，確保返回整數"""
        if "current_page" not in st.session_state:
            return 1
        
        try:
            # 嘗試轉換為整數
            page_num = int(st.session_state.current_page)
            # 確保頁碼是正整數
            return max(1, page_num)
        except (ValueError, TypeError):
            # 如果轉換失敗，返回默認值
            return 1
    
    def _clear_selections_on_mode_change(self):
        """當模式變更時清除相關選擇"""
        # 當分析模式改變時，清除某些選項
        if "selected_template" in st.session_state:
            st.session_state.selected_template = "default"
        
        # 清除分頁狀態
        if "current_page" in st.session_state:
            st.session_state.current_page = 1
    
    def _create_facilities_table(self, houses_data, places_data):
        """建立設施表格資料"""
        all_facilities = []
        
        for house_name, places in places_data.items():
            house_info = houses_data[house_name]
            
            for i, (cat, kw, name, lat, lng, dist, pid) in enumerate(places):
                # 轉換英文關鍵字為中文
                chinese_kw = ENGLISH_TO_CHINESE.get(kw, kw)
                
                facility_info = {
                    "房屋": house_name,
                    "房屋標題": house_info['title'][:50],
                    "房屋地址": house_info['address'],
                    "設施編號": i + 1,
                    "設施名稱": name,
                    "設施類別": cat,
                    "設施子類別": chinese_kw,
                    "距離(公尺)": dist,
                    "經度": lng,
                    "緯度": lat,
                    "place_id": pid
                }
                all_facilities.append(facility_info)
        
        return pd.DataFrame(all_facilities)
    
    def _display_analysis_results(self, results):
        """顯示分析結果"""
        analysis_mode = results["analysis_mode"]
        houses_data = results["houses_data"]
        places_data = results["places_data"]
        facility_counts = results["facility_counts"]
        category_counts = results["category_counts"]
        selected_categories = results["selected_categories"]
        radius = results["radius"]
        keyword = results["keyword"]
        num_houses = results["num_houses"]
        
        # 顯示分析標題
        if analysis_mode == "單一房屋分析":
            st.markdown(f"## 📊 單一房屋分析結果")
        else:
            st.markdown(f"## 📊 比較結果 ({num_houses}間房屋)")
        
        # 顯示設施表格
        st.markdown("---")
        st.subheader("📋 設施詳細資料表格")
        
        facilities_table = results.get("facilities_table", pd.DataFrame())
        
        if not facilities_table.empty:
            # 顯示資料摘要
            st.info(f"📈 共找到 {len(facilities_table)} 筆設施資料")
            
            # 分頁顯示表格
            page_size = 50
            total_pages = max(1, (len(facilities_table) + page_size - 1) // page_size)
            
            # 初始化分頁狀態
            if "current_page" not in st.session_state:
                st.session_state.current_page = 1
            
            # 確保 current_page 是整數
            self._ensure_page_number_is_int()
            
            # 分頁控制
            if total_pages > 1:
                col1, col2, col3 = st.columns([1, 2, 1])
                with col1:
                    if st.button("◀️ 上一頁", key="prev_page"):
                        # 確保 current_page 是整數
                        current_page = self._get_safe_page_number()
                        if current_page > 1:
                            st.session_state.current_page = current_page - 1
                        st.rerun()
                with col2:
                    # 確保顯示的頁碼是整數
                    current_page = self._get_safe_page_number()
                    st.write(f"第 {current_page}/{total_pages} 頁")
                with col3:
                    if st.button("下一頁 ▶️", key="next_page"):
                        current_page = self._get_safe_page_number()
                        if current_page < total_pages:
                            st.session_state.current_page = current_page + 1
                        st.rerun()
            
            # 取得當前頁的資料 - 確保 current_page 是整數
            current_page = self._get_safe_page_number()
            # 確保頁碼在有效範圍內
            if current_page < 1:
                current_page = 1
                st.session_state.current_page = 1
            if current_page > total_pages:
                current_page = total_pages
                st.session_state.current_page = total_pages
            
            # 修復：確保 current_page 是整數，再進行計算
            current_page_int = int(current_page)
            page_size_int = int(page_size)
            
            # 第602行：計算 start_idx - 現在使用整數
            start_idx = (current_page_int - 1) * page_size_int
            end_idx = min(start_idx + page_size_int, len(facilities_table))
            
            # 顯示當前頁的表格
            current_df = facilities_table.iloc[start_idx:end_idx]
        
        # ... 其餘程式碼保持不變 ...
            
            # 使用 Streamlit 的 dataframe 顯示
            st.dataframe(
                current_df,
                use_container_width=True,
                column_config={
                    "房屋": st.column_config.TextColumn(width="small"),
                    "房屋標題": st.column_config.TextColumn(width="medium"),
                    "房屋地址": st.column_config.TextColumn(width="medium"),
                    "設施名稱": st.column_config.TextColumn(width="large"),
                    "設施類別": st.column_config.TextColumn(width="small"),
                    "設施子類別": st.column_config.TextColumn(width="small"),
                    "距離(公尺)": st.column_config.NumberColumn(
                        format="%d 公尺",
                        help="設施距離房屋的距離（公尺）"
                    ),
                },
                hide_index=True
            )
            
            # 提供下載按鈕
            csv_data = facilities_table.to_csv(index=False, encoding='utf-8-sig')
            st.download_button(
                label="📥 下載完整設施資料 (CSV)",
                data=csv_data,
                file_name=f"設施資料_{time.strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                key="download_facilities_csv"
            )
        
        # 統計分析
        st.markdown("---")
        st.subheader("📈 設施統計")
        
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
            max_distance = max(distances) if distances else 0
            
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
        
        # 顯示地圖
        st.markdown("---")
        st.subheader("🗺️ 地圖檢視")
        
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
                house_info=house_info
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
                        house_info=house_info
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
                        house_info=house_info
                    )
        
        # AI 分析部分
        self._display_ai_analysis_section(results)
    
    def _render_map_improved(self, lat, lng, places, radius, title="房屋", house_info=None):
        """改良版地圖渲染"""
        browser_key = self._get_browser_key()
        
        if not browser_key:
            st.error("❌ 請在側邊欄填入 Google Maps Browser Key")
            return
        
        # 如果沒有設施資料，顯示訊息
        if not places:
            st.info(f"📭 {title} 周圍半徑 {radius} 公尺內未找到設施")
            return
        
        # 準備設施資料
        facilities_data = []
        for cat, kw, name, p_lat, p_lng, dist, pid in places:
            color = CATEGORY_COLORS.get(cat, "#000000")
            facilities_data.append({
                "name": name,
                "category": cat,
                "subcategory": kw,
                "lat": p_lat,
                "lng": p_lng,
                "distance": dist,
                "color": color,
                "maps_url": f"https://www.google.com/maps/search/?api=1&query={p_lat},{p_lng}&query_place_id={pid}"
            })
        
        # 建立圖例
        categories = {}
        for facility in facilities_data:
            cat = facility["category"]
            if cat not in categories:
                categories[cat] = facility["color"]
        
        # 建立HTML地圖
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
                                         '<p><strong>設施數量：</strong>{len(places)} 個</p>' +
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
                    legendDiv.innerHTML = '<h4 style="margin-top:0; margin-bottom:10px;">設施類別圖例</h4>';
                    
                    // 圖例項目
                    {'\n'.join([f'legendDiv.innerHTML += \'<div class="legend-item"><div class="legend-color" style="background-color:{color};"></div><span>{cat}</span></div>\';' for cat, color in categories.items()])}
                    
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
                                          facility.category + ' - ' + facility.subcategory + 
                                          '</span></p>' +
                                          '<p style="margin:5px 0;"><strong>距離：</strong>' + facility.distance + ' 公尺</p>' +
                                          '<p style="margin:5px 0;"><strong>座標：</strong><br>' + 
                                          '緯度：' + facility.lat.toFixed(6) + '<br>' +
                                          '經度：' + facility.lng.toFixed(6) + '</p>' +
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
        
        # 顯示地圖
        st.markdown(f"**🗺️ {title} - 周邊設施地圖**")
        st.markdown(f"📊 **共找到 {len(places)} 個設施** (搜尋半徑: {radius}公尺)")
        
        # 使用 html 組件顯示地圖
        html(html_content, height=550)
        
        # 顯示設施列表
        self._display_facilities_list(places)
    
    def _display_facilities_list(self, places):
        """顯示設施列表"""
        st.markdown("### 📍 全部設施列表")
        
        if len(places) > 0:
            with st.expander(f"顯示所有 {len(places)} 個設施", expanded=True):
                for i, (cat, kw, name, lat, lng, dist, pid) in enumerate(places, 1):
                    color = CATEGORY_COLORS.get(cat, "#000000")
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
                            st.markdown(f'<span style="background-color:{color}20; color:{color}; padding:4px 8px; border-radius:8px; font-size:12px; font-weight:bold;">{cat}</span>', unsafe_allow_html=True)
                        
                        with col3:
                            st.markdown(f'<span style="background-color:{dist_color}20; color:{dist_color}; padding:4px 8px; border-radius:8px; font-size:12px; font-weight:bold;">{dist}公尺</span>', unsafe_allow_html=True)
                        
                        with col4:
                            st.link_button("🗺️ 地圖", maps_url)
                        
                        with st.expander("詳細資訊", expanded=False):
                            col_info1, col_info2 = st.columns(2)
                            with col_info1:
                                st.write(f"**類別:** {cat}")
                                st.write(f"**子類別:** {kw}")
                                st.write(f"**距離:** {dist} 公尺 ({dist_class})")
                            with col_info2:
                                st.write(f"**座標:** {lat:.6f}, {lng:.6f}")
                                st.write(f"**Google 地圖:** [開啟地圖]({maps_url})")
                        
                        st.divider()
        else:
            st.info("📭 未找到任何設施")
    
    def _display_ai_analysis_section(self, results):
        """顯示AI分析部分"""
        st.markdown("---")
        st.subheader("🤖 AI 智能分析")
        
        # 顯示設施表格摘要
        facilities_table = results.get("facilities_table", pd.DataFrame())
        if not facilities_table.empty:
            with st.expander("📊 查看設施表格摘要", expanded=True):
                st.dataframe(
                    facilities_table.head(10),
                    use_container_width=True,
                    hide_index=True
                )
                st.caption(f"顯示前10筆資料，共 {len(facilities_table)} 筆")
        
        # 準備AI分析資料
        analysis_text = self._prepare_analysis_prompt(
            results["houses_data"], 
            results["places_data"], 
            results["facility_counts"], 
            results["category_counts"],
            results["selected_categories"],
            results["radius"],
            results["keyword"],
            results["analysis_mode"],
            results.get("facilities_table", pd.DataFrame())
        )
        
        # 建立唯一 key
        analysis_key = f"{results['analysis_mode']}__{','.join(list(results['houses_data'].keys()))}__{results['keyword']}__{','.join(results['selected_categories'])}__{results['radius']}"
        
        # 顯示提示詞模板選擇
        st.markdown("### 📋 提示詞模板選擇")
        
        templates = self._get_prompt_templates(results["analysis_mode"])
        
        # 建立模板選項
        template_options = {k: f"{v['name']} - {v['description']}" for k, v in templates.items()}
        
        # 初始化 session state
        if "selected_template" not in st.session_state:
            st.session_state.selected_template = "default"
        
        if "custom_prompt" not in st.session_state:
            st.session_state.custom_prompt = analysis_text
        
        # 模板選擇框
        selected_template = st.selectbox(
            "選擇提示詞模板",
            options=list(template_options.keys()),
            format_func=lambda x: template_options[x],
            key="template_selector",
            index=list(template_options.keys()).index(st.session_state.selected_template) 
            if st.session_state.selected_template in template_options else 0
        )
        
        # 如果模板改變了，更新提示詞內容
        if selected_template != st.session_state.get("last_selected_template", ""):
            if selected_template == "default":
                st.session_state.custom_prompt = analysis_text
            elif "content" in templates[selected_template]:
                st.session_state.custom_prompt = templates[selected_template]["content"]
            st.session_state.selected_template = selected_template
            st.session_state.last_selected_template = selected_template
        
        # 顯示提示詞編輯區域
        st.markdown("### 📝 AI 分析提示詞設定")
        
        col_prompt, col_info = st.columns([3, 1])
        
        with col_prompt:
            # 使用一個獨立的 key 來控制提示詞編輯框的重新渲染
            prompt_key = f"prompt_editor_{analysis_key}_{selected_template}"
            
            # 顯示可編輯的文字區域
            edited_prompt = st.text_area(
                "編輯AI分析提示詞",
                value=st.session_state.custom_prompt,
                height=400,
                key=prompt_key,
                help="您可以修改提示詞來調整AI的分析方向和重點"
            )
            
            # 保存按鈕
            if st.button("💾 儲存提示詞修改", type="secondary", use_container_width=True, key="save_prompt_btn"):
                st.session_state.custom_prompt = edited_prompt
                st.session_state.last_saved_prompt = edited_prompt
                st.success("✅ 提示詞已儲存！")
                st.rerun()
        
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
            
            # 恢復預設按鈕
            if st.button("🔄 恢復預設提示詞", type="secondary", use_container_width=True, key="reset_prompt_btn"):
                st.session_state.custom_prompt = analysis_text
                st.session_state.selected_template = "default"
                st.session_state.last_selected_template = "default"
                st.rerun()
        
        # 開始AI分析按鈕
        if st.button("🚀 開始AI分析", type="primary", use_container_width=True, key="start_ai_analysis"):
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
                    
                    # 使用當前提示詞
                    final_prompt = edited_prompt
                    
                    # 呼叫 Gemini
                    resp = model.generate_content(final_prompt)
                    
                    # 儲存結果
                    st.session_state.gemini_result = resp.text
                    st.session_state.gemini_key = analysis_key
                    st.session_state.used_prompt = final_prompt
                    
                    # 重新運行以顯示結果
                    st.rerun()
                    
                except Exception as e:
                    st.error(f"❌ Gemini API 錯誤: {str(e)}")
                    st.info("請檢查：1. API 金鑰是否正確 2. 配額是否用盡 3. 網路連線是否正常")
                    return
        
        # 顯示分析結果
        if "gemini_result" in st.session_state:
            st.markdown("### 📋 AI 分析報告")
            
            # 顯示使用的提示詞摘要
            if "used_prompt" in st.session_state:
                with st.expander("ℹ️ 查看本次使用的提示詞摘要", expanded=False):
                    used_prompt = st.session_state.used_prompt
                    prompt_preview = used_prompt[:500] + ("..." if len(used_prompt) > 500 else "")
                    st.text(prompt_preview)
            
            # 美化顯示
            with st.container():
                st.markdown("---")
                st.markdown(st.session_state.gemini_result)
                st.markdown("---")
            
            # 重新分析按鈕
            if st.button("🔄 重新分析", type="secondary", use_container_width=True, key="reanalyze_btn"):
                # 清除之前的結果
                keys_to_clear = ['gemini_result', 'gemini_key', 'used_prompt']
                for key in keys_to_clear:
                    if key in st.session_state:
                        del st.session_state[key]
                st.rerun()
            
            # 提供下載選項
            if results["analysis_mode"] == "單一房屋分析":
                report_title = "房屋分析報告"
            else:
                report_title = f"{results['num_houses']}間房屋比較報告"
            
            report_text = f"""
            {report_title}
            生成時間：{time.strftime('%Y-%m-%d %H:%M:%S')}
            分析模式：{results['analysis_mode']}
            
            分析房屋 ({results['num_houses']}間):
            """
            
            for house_name, house_info in results["houses_data"].items():
                report_text += f"""
            - {house_name}: {house_info['title']}
              地址：{house_info['address']}
              """
            
            report_text += f"""
            
            搜尋條件：
            - 半徑：{results['radius']} 公尺
            - 選擇類別：{', '.join(results['selected_categories'])}
            - 額外關鍵字：{results['keyword'] if results['keyword'] else '無'}
            
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
                use_container_width=True,
                key="download_report_btn"
            )
    
    def _prepare_analysis_prompt(self, houses_data, places_data, facility_counts, 
                                category_counts, selected_categories, radius, 
                                keyword, analysis_mode, facilities_table):
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
            
            # 建立表格摘要
            table_summary = ""
            if not facilities_table.empty:
                # 只取前20筆設施作為範例
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
                - 設施類別：主要類別（如教育、購物等）
                - 設施子類別：詳細設施類型
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
            
            【各類別設施數量】
            {chr(10).join([f'- {cat}: {num} 個' for cat, num in category_stats.items()])}
            
            {table_summary}
            
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
                
                # 建立表格摘要
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
                
                【各類別設施數量】
                {chr(10).join([f'- {cat}: {num} 個' for cat, num in category_stats.items()])}
                
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
                    # 分房屋顯示前10筆設施
                    table_summary = "\n\n【各房屋設施摘要】\n"
                    for house_name in houses_data.keys():
                        house_facilities = facilities_table[facilities_table['房屋'] == house_name].head(10)
                        if not house_facilities.empty:
                            table_summary += f"\n{house_name} 的前10個設施：\n"
                            table_summary += house_facilities[['設施名稱', '設施類別', '距離(公尺)']].to_string(index=False) + "\n"
                
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


# 如果需要，可以保留單獨的函數供外部調用
def get_comparison_analyzer():
    """取得比較分析器實例"""
    return ComparisonAnalyzer()
