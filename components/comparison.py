# components/comparison.py
import streamlit as st
import pandas as pd
import time
import sys
import os

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
        
        # 顯示選擇的房屋
        if selected_houses:
            self._display_selected_houses(selected_houses, fav_df)
        
        # 基本設定
        st.markdown("---")
        st.subheader("⚙️ 比較設定")
        
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
                        chinese_names = items[::2]
                        english_keywords = items[1::2]
                        
                        for i, (chinese, english) in enumerate(zip(chinese_names, english_keywords)):
                            col1, col2 = st.columns([1, 4])
                            with col1:
                                checkbox_key = f"tab2_{cat}_{english}_{i}"
                                if st.checkbox("", key=checkbox_key):
                                    if cat not in selected_subtypes:
                                        selected_subtypes[cat] = []
                                    selected_subtypes[cat].append(english)
                            with col2:
                                st.text(chinese)
                    
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
        
        # 開始比較按鈕
        st.markdown("---")
        if st.button("🚀 開始比較", type="primary", use_container_width=True, key="start_comparison"):
            if not selected_categories:
                st.warning("⚠️ 請至少選擇一個生活機能類別")
            else:
                st.success("✅ 比較功能準備就緒！")
                st.info("完整比較功能將在此實作")
    
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
    
    def _display_selected_houses(self, selected_houses, fav_df):
        """顯示已選房屋資訊"""
        if len(selected_houses) == 2:
            house_a = fav_df[(fav_df['標題'] + " | " + fav_df['地址']) == selected_houses[0]].iloc[0]
            house_b = fav_df[(fav_df['標題'] + " | " + fav_df['地址']) == selected_houses[1]].iloc[0]
            
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
            st.markdown("### 📋 已選房屋清單")
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
