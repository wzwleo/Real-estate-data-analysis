# components/comparison.py
import streamlit as st
from components.favorites import FavoritesManager
from components.place_types import PLACE_TYPES, ENGLISH_TO_CHINESE
from config import CATEGORY_COLORS, DEFAULT_RADIUS


class ComparisonAnalyzer:
    """房屋比較分析器"""
    
    def __init__(self):
        self.fav_manager = FavoritesManager()
    
    def render_comparison_tab(self):
        """渲染比較頁面"""
        st.subheader("🏠 房屋比較")
        
        # 檢查是否有收藏
        fav_df = self.fav_manager.get_favorites_data()
        if fav_df.empty:
            st.info("⭐ 尚未有收藏房產，無法比較")
            return
        
    with tab2:
        st.subheader("🏠 房屋比較（單獨或多個比較）")
        
        # 模式選擇：單獨比較或多個比較
        comparison_mode = st.radio(
            "選擇比較模式",
            ["單獨比較（2個房屋）", "多個比較（2個以上房屋）"],
            horizontal=True,
            key="comparison_mode"
        )
        fav_df = get_favorites_data()
        if fav_df.empty:
            st.info("⭐ 尚未有收藏房產，無法比較")
            st.stop()  # 停止執行後續程式
        
        options = fav_df['標題'] + " | " + fav_df['地址']
        
        if comparison_mode == "單獨比較（2個房屋）":
            # 單獨比較模式
            c1, c2 = st.columns(2)
            with c1:
                choice_a = st.selectbox("選擇房屋 A", options, key="compare_a")
            with c2:
                choice_b = st.selectbox("選擇房屋 B", options, key="compare_b")
            
            selected_houses = [choice_a, choice_b] if choice_a and choice_b else []
            
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
        
        else:
            # 多個比較模式
            st.subheader("🏘️ 選擇多個房屋進行比較")
            
            # 使用多選下拉框
            selected_houses = st.multiselect(
                "選擇要比較的房屋（至少選擇2個）",
                options,
                default=options[:min(3, len(options))] if len(options) >= 2 else [],
                key="multi_compare"
            )
            
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
            
            if len(selected_houses) < 2:
                st.warning("⚠️ 請至少選擇2個房屋進行比較")
                st.stop()

        # 共通設定
        st.markdown("---")
        st.subheader("⚙️ 比較設定")
        
        server_key = _get_server_key()
        gemini_key = st.session_state.get("GEMINI_KEY", "")
        radius = st.slider("搜尋半徑 (公尺)", 100, 2000, 500, 100, key="radius_slider")
        keyword = st.text_input("額外關鍵字搜尋 (可選)", key="extra_keyword", 
                              placeholder="例如：公園、健身房、銀行等")

        st.markdown("---")
        st.subheader("🔍 選擇生活機能類別")
        
        # 初始化 session state
        if 'selected_subtypes' not in st.session_state:
            st.session_state.selected_subtypes = {}
        
        selected_categories = []
        selected_subtypes = {}
        
        # 建立大類別選擇器
        st.markdown("### 選擇大類別")
        all_categories = list(PLACE_TYPES.keys())
        cols = st.columns(len(all_categories))
        
        category_selection = {}
        for i, cat in enumerate(all_categories):
            with cols[i]:
                # 使用顏色標籤
                color = CATEGORY_COLORS.get(cat, "#000000")
                st.markdown(f'<span style="background-color:{color}; color:white; padding:5px 10px; border-radius:5px;">{cat}</span>', unsafe_allow_html=True)
                category_selection[cat] = st.checkbox(f"選擇{cat}", key=f"main_cat_{cat}_{i}")
        
        # 如果選擇了大類別，顯示細分選項
        selected_main_cats = [cat for cat, selected in category_selection.items() if selected]
        
        if selected_main_cats:
            st.markdown("### 選擇細分設施")
            
            for cat_idx, cat in enumerate(selected_main_cats):
                with st.expander(f"📁 {cat} 類別細選", expanded=True):
                    # 全選按鈕
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
                        
                        # 顯示前幾個項目（修復這裡）
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
                if not _get_browser_key():
                    st.error("❌ 請在側邊欄填入 Google Maps **Browser Key**")
                    st.stop()
                if not server_key or not gemini_key:
                    st.error("❌ 請在側邊欄填入 Server Key 與 Gemini Key")
                    st.stop()
                
                # 根據模式進行不同檢查
                if comparison_mode == "單獨比較（2個房屋）":
                    if choice_a == choice_b:
                        st.warning("⚠️ 請選擇兩個不同房屋")
                        st.stop()
                else:
                    if len(selected_houses) < 2:
                        st.warning("⚠️ 請至少選擇2個房屋")
                        st.stop()
                
                if not selected_categories:
                    st.warning("⚠️ 請至少選擇一個生活機能類別")
                    st.stop()

                # 執行比較
                run_comparison_analysis(
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
        
        # 範例：顯示可比較的房屋
        options = fav_df['標題'] + " | " + fav_df['地址']
        selected = st.multiselect("選擇要比較的房屋", options)
        
        if len(selected) >= 2:
            st.success(f"已選擇 {len(selected)} 間房屋進行比較")
            # 這裡可以呼叫其他比較功能
