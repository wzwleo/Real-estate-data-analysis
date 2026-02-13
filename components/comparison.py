import streamlit as st
import pandas as pd
import time
import json
import sys
import os
import requests
import math
from streamlit.components.v1 import html
from streamlit_echarts import st_echarts

# 修正匯入路徑
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

try:
    from config import CATEGORY_COLORS, DEFAULT_RADIUS
    from components.place_types import PLACE_TYPES, CHINESE_TO_CATEGORY
    from components.geocoding import geocode_address, haversine
    CONFIG_LOADED = True
except ImportError as e:
    CONFIG_LOADED = False
    st.warning(f"無法載入設定: {e}")
    # 避免後續錯誤
    PLACE_TYPES = {}
    CHINESE_TO_CATEGORY = {}
    CATEGORY_COLORS = {}
    DEFAULT_RADIUS = 500


class ComparisonAnalyzer:
    """房屋分析器 - 支援單一分析和多房屋比較"""
    
    def __init__(self):
        self._init_session_state()
    
    def _init_session_state(self):
        """初始化必要的 session state 變數"""
        defaults = {
            'analysis_in_progress': False,
            'analysis_mode': '單一房屋分析',
            'selected_houses': [],
            'current_page': 1,
            'last_gemini_call': 0,
            'buyer_profile': None,
            'auto_selected_categories': [],
            'auto_selected_subtypes': {}
        }
        for key, value in defaults.items():
            if key not in st.session_state:
                st.session_state[key] = value
    
    # ============= 買家類型定義（完全對應你的純中文 place_types）=============
    
    def _get_buyer_profiles(self):
        """定義買家類型 - 關鍵字完全對應 place_types.py 的中文"""
        return {
            "首購族": {
                "icon": "🏠",
                "description": "年輕首購，預算有限，追求高效率生活",
                "priority_categories": {
                    "交通運輸": ["捷運站", "公車站", "火車站", "輕軌站", "ubike站"],
                    "購物": ["便利商店", "超市", "市場"],
                    "餐飲美食": ["咖啡廳", "速食店", "早餐餐廳"],
                    "金融機構": ["銀行", "郵局", "ATM"]
                },
                "secondary_categories": {
                    "健康與保健": ["健身房", "診所", "藥局"],
                    "生活服務": ["公園", "電影院"]
                },
                "radius": 500,
                "prompt_focus": ["通勤便利性", "日常採買效率", "預算內最高CP值", "夜間生活便利性"]
            },
            "家庭": {
                "icon": "👨‍👩‍👧‍👦",
                "description": "有小孩的家庭，重視教育、安全與居住品質",
                "priority_categories": {
                    "教育": ["小學", "中學", "幼兒園", "圖書館"],
                    "公園綠地": ["公園", "兒童遊戲場", "狗公園"],
                    "健康與保健": ["小兒科", "診所", "藥局", "醫院"],
                    "購物": ["超市", "便利商店", "市場"]
                },
                "secondary_categories": {
                    "餐飲美食": ["親子餐廳", "咖啡廳"],
                    "交通運輸": ["公車站", "捷運站", "停車場"],
                    "生活服務": ["社區中心", "運動中心"]
                },
                "radius": 800,
                "prompt_focus": ["學區品質與距離", "親子友善環境", "社區安全性", "假日家庭活動空間"]
            },
            "長輩退休族": {
                "icon": "🧓",
                "description": "退休長輩，重視醫療、寧靜、日常採買便利",
                "priority_categories": {
                    "健康與保健": ["醫院", "診所", "藥局", "復健科", "中醫"],
                    "公園綠地": ["公園", "河濱公園", "登山步道"],
                    "購物": ["傳統市場", "超市", "便利商店"],
                    "宗教": ["廟宇", "教堂"]
                },
                "secondary_categories": {
                    "交通運輸": ["公車站", "捷運站"],
                    "金融機構": ["郵局", "銀行"],
                    "餐飲美食": ["素食餐廳", "傳統小吃"]
                },
                "radius": 600,
                "prompt_focus": ["醫療資源可及性", "散步運動空間", "傳統市場便利性", "安靜宜居環境"]
            },
            "外地工作": {
                "icon": "🚄",
                "description": "跨縣市工作，需頻繁通勤，追求交通樞紐便利性",
                "priority_categories": {
                    "交通運輸": ["捷運站", "公車站", "火車站", "高鐵站", "客運站", "輕軌站"],
                    "購物": ["便利商店", "超市"],
                    "餐飲美食": ["咖啡廳", "連鎖餐廳", "速食店"],
                    "金融機構": ["ATM", "銀行", "郵局"]
                },
                "secondary_categories": {
                    "健康與保健": ["健身房", "藥局", "診所"],
                    "生活服務": ["洗衣店", "電影院"]
                },
                "radius": 400,
                "prompt_focus": ["交通樞紐距離", "南北往來便利性", "高效率生活圈", "短暫停留採買便利性"]
            }
        }
    
    def _auto_select_categories(self, profile_name):
        """根據買家類型自動選擇設施 - 完全對應純中文 place_types"""
        profiles = self._get_buyer_profiles()
        if profile_name not in profiles:
            return [], {}
        
        profile = profiles[profile_name]
        auto_categories = []
        auto_subtypes = {}
        
        # 處理優先類別
        for cat, subtypes in profile.get("priority_categories", {}).items():
            if cat in PLACE_TYPES:
                auto_categories.append(cat)
                if cat not in auto_subtypes:
                    auto_subtypes[cat] = []
                # 只加入存在於 PLACE_TYPES[cat] 的有效子類別
                valid_subtypes = [s for s in subtypes if s in PLACE_TYPES[cat]]
                auto_subtypes[cat].extend(valid_subtypes)
        
        # 處理次要類別
        for cat, subtypes in profile.get("secondary_categories", {}).items():
            if cat in PLACE_TYPES:
                auto_categories.append(cat)
                if cat not in auto_subtypes:
                    auto_subtypes[cat] = []
                valid_subtypes = [s for s in subtypes if s in PLACE_TYPES[cat]]
                auto_subtypes[cat].extend(valid_subtypes)
        
        # 移除重複的類別
        auto_categories = list(dict.fromkeys(auto_categories))
        
        return auto_categories, auto_subtypes
    
    # ============= 主要渲染方法 =============
    
    def render_comparison_tab(self):
        """渲染分析頁面"""
        try:
            st.subheader("🏠 房屋分析模式")
            
            fav_df = self._get_favorites_data()
            if fav_df.empty:
                st.info("⭐ 尚未有收藏房產，無法分析")
                return
            
            if st.session_state.get('analysis_in_progress', False):
                self._show_analysis_in_progress()
                return
            
            self._render_analysis_setup(fav_df)
            
            if "analysis_results" in st.session_state:
                self._display_analysis_results(st.session_state.analysis_results)
                
        except Exception as e:
            st.error(f"❌ 渲染分析頁面時發生錯誤: {str(e)}")
            st.button("🔄 重新整理頁面", on_click=self._reset_page)
    
    def _show_analysis_in_progress(self):
        """顯示分析進行中"""
        st.warning("🔍 分析進行中，請稍候...")
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for i in range(100):
            progress_bar.progress(i + 1)
            status_text.text(f"分析中... {i+1}%")
            time.sleep(0.01)
        
        st.success("✅ 分析完成！")
        time.sleep(1)
        st.session_state.analysis_in_progress = False
        st.rerun()
    
    def _reset_page(self):
        """重設頁面"""
        keys = ['analysis_in_progress', 'analysis_results', 'gemini_result', 
                'buyer_profile', 'auto_selected_categories', 'auto_selected_subtypes']
        for k in keys:
            if k in st.session_state:
                del st.session_state[k]
    
    def _render_analysis_setup(self, fav_df):
        """渲染分析設定 - 買家類型在最前面"""
        
        # ============= 步驟1: 買家類型選擇 =============
        st.markdown("### 👤 步驟1：誰要住這裡？")
        st.markdown("選擇買家類型，系統將**自動推薦**最適合的生活機能")
        
        profiles = self._get_buyer_profiles()
        col_profiles = st.columns(len(profiles))
        
        for idx, (profile_name, profile_info) in enumerate(profiles.items()):
            with col_profiles[idx]:
                is_selected = st.session_state.get('buyer_profile') == profile_name
                border = "3px solid #4CAF50" if is_selected else "1px solid #ddd"
                bg = "#f1f8e9" if is_selected else "white"
                
                st.markdown(f"""
                <div style="border:{border}; border-radius:10px; padding:15px; 
                            background-color:{bg}; text-align:center; height:170px;
                            margin-bottom:10px;">
                    <div style="font-size:36px;">{profile_info['icon']}</div>
                    <div style="font-size:18px; font-weight:bold; margin:5px 0;">{profile_name}</div>
                    <div style="font-size:12px; color:#666;">{profile_info['description']}</div>
                </div>
                """, unsafe_allow_html=True)
                
                btn_type = "primary" if is_selected else "secondary"
                if st.button(f"選擇 {profile_name}", key=f"select_{profile_name}", 
                           type=btn_type, use_container_width=True):
                    st.session_state.buyer_profile = profile_name
                    cats, subs = self._auto_select_categories(profile_name)
                    st.session_state.auto_selected_categories = cats
                    st.session_state.auto_selected_subtypes = subs
                    st.session_state.suggested_radius = profile_info.get("radius", DEFAULT_RADIUS)
                    st.rerun()
        
        current_profile = st.session_state.get('buyer_profile')
        if current_profile:
            profile_info = profiles[current_profile]
            st.success(f"✅ 當前選擇：**{profile_info['icon']} {current_profile}**  |  📌 分析重點：{profile_info['prompt_focus'][0]}、{profile_info['prompt_focus'][1]}...")
        else:
            st.info("👆 請先選擇買家類型，系統將自動篩選最適合的生活機能")
            return
        
        st.markdown("---")
        
        # ============= 步驟2: 房屋選擇 =============
        st.markdown("### 🏠 步驟2：選擇要分析的房屋")
        
        mode = st.radio("選擇分析模式", ["單一房屋分析", "多房屋比較"], horizontal=True, key="mode")
        st.session_state.analysis_mode = mode
        
        options = fav_df['標題'] + " | " + fav_df['地址']
        selected = []
        
        if mode == "單一房屋分析":
            choice = st.selectbox("選擇要分析的房屋", options, key="single_select")
            if choice:
                selected = [choice]
                house = fav_df[(fav_df['標題'] + " | " + fav_df['地址']) == choice].iloc[0]
                self._show_house_preview_single(house)
        else:
            default = options[:min(2, len(options))] if len(options) >= 1 else []
            selected = st.multiselect("選擇要比較的房屋", options, default=default, key="multi_select")
            if selected:
                self._show_houses_preview_multi(fav_df, selected)
        
        if not selected:
            if mode == "多房屋比較" and len(options) > 0:
                st.info("請至少選擇一間房屋")
            return
        
        st.session_state.selected_houses = selected
        st.markdown("---")
        
        # ============= 步驟3: 分析設定 =============
        st.markdown("### ⚙️ 步驟3：進階分析設定")
        
        # API 檢查
        k1, k2, k3 = st.columns(3)
        with k1: st.metric("Server Key", "✅" if self._get_server_key() else "❌")
        with k2: st.metric("Gemini Key", "✅" if self._get_gemini_key() else "❌")
        with k3: st.metric("Browser Key", "✅" if self._get_browser_key() else "❌")
        
        suggest_r = st.session_state.get('suggested_radius', DEFAULT_RADIUS)
        radius = st.slider(f"搜尋半徑（{profiles[current_profile]['icon']} 建議：{suggest_r}公尺）", 
                          100, 2000, suggest_r, 100, key="radius")
        
        keyword = st.text_input("額外關鍵字搜尋（選填）", key="keyword", placeholder="例如：公園、健身房")
        
        st.markdown("---")
        
        # ============= 步驟4: 生活機能選擇（已自動勾選）=============
        st.subheader("🔍 步驟4：確認生活機能類別")
        
        auto_cats = st.session_state.get('auto_selected_categories', [])
        auto_subs = st.session_state.get('auto_selected_subtypes', {})
        
        if auto_cats:
            total = sum(len(v) for v in auto_subs.values())
            st.info(f"📌 **{current_profile} 推薦設施**：已自動選擇 {len(auto_cats)} 大類、{total} 種設施，可手動調整")
        
        selected_cats, selected_subs = self._render_category_selection(auto_cats, auto_subs)
        
        if not selected_cats:
            st.warning("⚠️ 請至少選擇一個生活機能類別")
            return
        
        self._render_selection_summary(selected_cats, selected_subs, current_profile)
        st.markdown("---")
        
        # ============= 開始分析 =============
        col1, col2 = st.columns([3, 1])
        with col1:
            btn_text = "🚀 開始分析" if mode == "單一房屋分析" else "🚀 開始比較"
            if st.button(btn_text, type="primary", use_container_width=True, key="start"):
                valid = self._validate_inputs(selected, selected_cats)
                if valid == "OK":
                    self._start_analysis(mode, selected, radius, keyword, 
                                        selected_cats, selected_subs, fav_df, current_profile)
                else:
                    st.error(valid)
        with col2:
            if st.button("🗑️ 清除", use_container_width=True, key="clear"):
                self._clear_all()
                st.rerun()
    
    def _render_category_selection(self, preset_categories=None, preset_subtypes=None):
        """渲染類別選擇 - 完全對應純中文 place_types"""
        selected_cats = []
        selected_subs = {}
        
        preset_cats = preset_categories or []
        preset_subs = preset_subtypes or {}
        
        # 大類別選擇
        st.markdown("#### 選擇大類別")
        all_cats = list(PLACE_TYPES.keys())
        cols = st.columns(len(all_cats))
        
        cat_selection = {}
        for i, cat in enumerate(all_cats):
            with cols[i]:
                color = CATEGORY_COLORS.get(cat, "#666")
                is_rec = cat in preset_cats
                tag = "⭐ 推薦 " if is_rec else ""
                
                st.markdown(f"""
                <div style="text-align:center; margin-bottom:5px;">
                    <span style="background-color:{color}; color:white; padding:5px 10px; border-radius:5px;">
                        {tag}{cat}
                    </span>
                </div>
                """, unsafe_allow_html=True)
                
                default = cat in preset_cats
                cat_selection[cat] = st.checkbox(f"選擇{cat}", key=f"main_{cat}", value=default)
        
        # 細項選擇
        selected_main = [c for c, s in cat_selection.items() if s]
        current_profile = st.session_state.get('buyer_profile', '')
        profiles = self._get_buyer_profiles()
        
        if selected_main:
            st.markdown("#### 選擇細分設施")
            
            for cat in selected_main:
                with st.expander(f"📁 {cat} 類別細選", expanded=True):
                    # 快速全選/清除
                    cc1, cc2, cc3 = st.columns([1, 1, 2])
                    with cc1:
                        if st.button(f"全選 {cat}", key=f"all_{cat}", use_container_width=True):
                            st.session_state[f"flag_{cat}"] = True
                            st.rerun()
                    with cc2:
                        if st.button(f"清除 {cat}", key=f"clear_{cat}", use_container_width=True):
                            st.session_state[f"flag_{cat}"] = False
                            st.rerun()
                    with cc3:
                        if current_profile:
                            st.markdown(f"💡 **{current_profile}推薦**：優先")
                    
                    # 取得此類別所有設施
                    items = PLACE_TYPES[cat]
                    force_all = st.session_state.get(f"flag_{cat}", False)
                    default_list = preset_subs.get(cat, []) if cat in preset_subs else []
                    
                    # 取得優先/次要推薦清單
                    priority_list = []
                    secondary_list = []
                    if current_profile and current_profile in profiles:
                        p = profiles[current_profile]
                        priority_list = p.get("priority_categories", {}).get(cat, [])
                        secondary_list = p.get("secondary_categories", {}).get(cat, [])
                    
                    # 3欄布局
                    per_row = (len(items) + 2) // 3
                    for row in range(per_row):
                        cols = st.columns(3)
                        for ci in range(3):
                            idx = row + ci * per_row
                            if idx < len(items):
                                name = items[idx]
                                
                                # 判斷推薦等級
                                rec_text = ""
                                rec_color = ""
                                if name in priority_list:
                                    rec_text = "⭐ 優先"
                                    rec_color = "#FFD700"
                                elif name in secondary_list:
                                    rec_text = "📌 次要"
                                    rec_color = "#87CEEB"
                                
                                # 預設值
                                default_val = False
                                if force_all:
                                    default_val = True
                                elif name in default_list:
                                    default_val = True
                                elif name in priority_list:
                                    default_val = True
                                
                                with cols[ci]:
                                    if rec_text:
                                        st.markdown(f"""
                                        <div style="border-left:4px solid {rec_color}; padding-left:6px; margin-bottom:2px;">
                                            <span style="font-weight:bold;">{name}</span>
                                            <span style="background-color:{rec_color}; color:black; padding:2px 6px; border-radius:12px; font-size:10px; margin-left:5px;">
                                                {rec_text}
                                            </span>
                                        </div>
                                        """, unsafe_allow_html=True)
                                        cb = st.checkbox(" ", key=f"sub_{cat}_{idx}", label_visibility="collapsed", value=default_val)
                                    else:
                                        cb = st.checkbox(name, key=f"sub_{cat}_{idx}", value=default_val)
                                    
                                    if cb:
                                        if cat not in selected_subs:
                                            selected_subs[cat] = []
                                        selected_subs[cat].append(name)
                    
                    # 清除全選標記
                    if f"flag_{cat}" in st.session_state:
                        del st.session_state[f"flag_{cat}"]
                    
                    if cat in selected_subs:
                        st.caption(f"✅ 已選擇 {len(selected_subs[cat])} 種")
                
                if cat in selected_subs and selected_subs[cat]:
                    selected_cats.append(cat)
        
        return selected_cats, selected_subs
    
    def _render_selection_summary(self, categories, subtypes, profile=""):
        """顯示選擇摘要"""
        st.markdown("---")
        st.subheader("📋 已選擇設施摘要")
        
        if not categories:
            return
        
        cols = st.columns(min(4, len(categories)))
        profiles = self._get_buyer_profiles()
        
        for i, cat in enumerate(categories):
            with cols[i % len(cols)]:
                if cat in subtypes:
                    cnt = len(subtypes[cat])
                    color = CATEGORY_COLORS.get(cat, "#666")
                    
                    is_rec = False
                    if profile and profile in profiles:
                        p = profiles[profile]
                        is_rec = cat in p.get("priority_categories", {}) or cat in p.get("secondary_categories", {})
                    
                    badge = "⭐ 推薦" if is_rec else ""
                    st.markdown(f"""
                    <div style="background-color:{color}20; padding:10px; border-radius:5px; border-left:4px solid {color};">
                        <h4 style="color:{color}; margin:0;">{cat} {badge}</h4>
                        <p style="margin:5px 0 0;">已選擇 {cnt} 種設施</p>
                    </div>
                    """, unsafe_allow_html=True)
    
    def _show_house_preview_single(self, house):
        """單一房屋預覽"""
        st.markdown(f"""
        <div style="border:2px solid #4CAF50; padding:15px; border-radius:10px; background:#f9f9f9;">
            <h4 style="color:#4CAF50; margin:0;">🏠 {house['標題'][:50]}</h4>
            <p><strong>地址：</strong>{house['地址']}</p>
        </div>
        """, unsafe_allow_html=True)
        
        c1, c2, c3 = st.columns(3)
        with c1:
            if '總價元' in house: st.metric("總價", f"{int(house['總價元']):,} 元")
        with c2:
            if '建物面積平方公尺' in house: st.metric("面積", f"{house['建物面積平方公尺']:.1f} ㎡")
        with c3:
            if '平均單價元平方公尺' in house: st.metric("單價", f"{int(house['平均單價元平方公尺']):,} 元/㎡")
    
    def _show_houses_preview_multi(self, fav_df, selected):
        """多房屋預覽"""
        st.markdown("#### 📋 已選房屋")
        
        if len(selected) == 1:
            h = fav_df[(fav_df['標題'] + " | " + fav_df['地址']) == selected[0]].iloc[0]
            st.markdown(f"**🏠 {h['標題'][:30]}**  |  📍 {h['地址'][:20]}...")
        else:
            cols = st.columns(min(3, len(selected)))
            for i, opt in enumerate(selected[:3]):
                h = fav_df[(fav_df['標題'] + " | " + fav_df['地址']) == opt].iloc[0]
                with cols[i]:
                    letter = chr(65 + i)
                    price = f"💰 {int(h['平均單價元平方公尺']):,} 元/㎡" if '平均單價元平方公尺' in h else ""
                    st.markdown(f"**房屋 {letter}**  \n📍 {h['地址'][:15]}...  \n{price}")
    
    def _validate_inputs(self, houses, cats):
        """驗證輸入"""
        if not self._get_browser_key(): return "❌ 請填寫 Google Maps Browser Key"
        if not self._get_server_key(): return "❌ 請填寫 Server Key"
        if not self._get_gemini_key(): return "❌ 請填寫 Gemini Key"
        if not cats: return "⚠️ 請至少選擇一個生活機能類別"
        if not houses: return "⚠️ 請選擇房屋"
        if not st.session_state.get('buyer_profile'): return "⚠️ 請先選擇買家類型"
        return "OK"
    
    def _start_analysis(self, mode, houses, radius, keyword, cats, subs, fav_df, profile):
        """開始分析"""
        try:
            st.session_state.analysis_settings = {
                "mode": mode, "houses": houses, "radius": radius, "keyword": keyword,
                "cats": cats, "subs": subs, "server": self._get_server_key(),
                "gemini": self._get_gemini_key(), "fav": fav_df.to_json(orient='split'),
                "profile": profile
            }
            self._clear_old()
            st.session_state.analysis_in_progress = True
            self._execute_analysis()
        except Exception as e:
            st.error(f"❌ 啟動失敗: {e}")
            st.session_state.analysis_in_progress = False
    
    def _clear_old(self):
        """清除舊結果"""
        for k in ['analysis_results', 'gemini_result', 'places_data', 'custom_prompt', 'used_prompt']:
            if k in st.session_state: del st.session_state[k]
    
    def _clear_all(self):
        """全部清除"""
        keys = ['analysis_settings', 'analysis_results', 'analysis_in_progress', 'gemini_result',
                'custom_prompt', 'used_prompt', 'selected_houses', 'buyer_profile',
                'auto_selected_categories', 'auto_selected_subtypes', 'suggested_radius']
        for k in keys:
            if k in st.session_state: del st.session_state[k]
    
    def _execute_analysis(self):
        """執行分析核心"""
        try:
            s = st.session_state.analysis_settings
            fav_df = pd.read_json(s["fav"], orient='split')
            
            bar = st.progress(0)
            txt = st.empty()
            
            # 步驟1: 解析地址
            txt.text("🔍 步驟 1/4: 解析地址...")
            houses_data = {}
            for i, opt in enumerate(s["houses"]):
                h = fav_df[(fav_df['標題'] + " | " + fav_df['地址']) == opt].iloc[0]
                name = f"房屋 {chr(65+i)}" if len(s["houses"]) > 1 else "分析房屋"
                lat, lng = geocode_address(h["地址"], s["server"])
                if not lat or not lng:
                    st.error(f"❌ {name} 地址解析失敗")
                    st.session_state.analysis_in_progress = False
                    return
                houses_data[name] = {
                    "name": name, "title": h['標題'], "address": h['地址'],
                    "lat": lat, "lng": lng
                }
            bar.progress(25)
            
            # 步驟2: 查詢設施（純中文關鍵字）
            txt.text("🔍 步驟 2/4: 查詢周邊設施...")
            places_data = {}
            total = len(houses_data)
            for idx, (name, info) in enumerate(houses_data.items()):
                places = self._query_places_chinese(
                    info["lat"], info["lng"], s["server"],
                    s["cats"], s["subs"], s["radius"], s["keyword"]
                )
                places_data[name] = places
                bar.progress(25 + int(((idx+1)/total)*25))
            bar.progress(50)
            
            # 步驟3: 統計
            txt.text("📊 步驟 3/4: 計算統計...")
            counts = {n: len(p) for n, p in places_data.items()}
            table = self._create_facilities_table(houses_data, places_data)
            bar.progress(75)
            
            # 步驟4: 儲存
            txt.text("💾 步驟 4/4: 儲存結果...")
            st.session_state.analysis_results = {
                "analysis_mode": s["mode"], "houses_data": houses_data,
                "places_data": places_data, "facility_counts": counts,
                "selected_categories": s["cats"], "radius": s["radius"],
                "keyword": s["keyword"], "num_houses": len(houses_data),
                "facilities_table": table, "buyer_profile": s.get("profile", "未指定")
            }
            bar.progress(100)
            txt.text("✅ 分析完成！")
            
            st.session_state.analysis_in_progress = False
            time.sleep(1)
            st.rerun()
            
        except Exception as e:
            st.error(f"❌ 分析失敗: {e}")
            st.session_state.analysis_in_progress = False
    
    def _query_places_chinese(self, lat, lng, api_key, categories, subtypes, radius=500, extra=""):
        """查詢設施 - 純中文關鍵字，完全對應你的 place_types.py"""
        results = []
        seen = set()
        
        # 計算總任務數
        tasks = []
        for cat in categories:
            if cat in subtypes:
                for keyword in subtypes[cat]:
                    tasks.append(keyword)
        if extra:
            tasks.append(extra)
        
        if not tasks:
            return results
        
        bar = st.progress(0)
        txt = st.empty()
        completed = 0
        
        for keyword in tasks:
            completed += 1
            txt.text(f"搜尋 {completed}/{len(tasks)}: {keyword}")
            bar.progress(completed / len(tasks))
            
            try:
                places = self._search_google_places_chinese(lat, lng, api_key, keyword, radius)
                for p in places:
                    if p[5] > radius:
                        continue
                    pid = p[6]
                    if pid in seen:
                        continue
                    seen.add(pid)
                    
                    # 找出此設施屬於哪個大類別
                    found_cat = "其他"
                    for c in categories:
                        if keyword in subtypes.get(c, []):
                            found_cat = c
                            break
                    
                    results.append((found_cat, keyword, p[2], p[3], p[4], p[5], p[6]))
                
                time.sleep(0.3)
            except:
                continue
        
        bar.progress(1.0)
        txt.text("✅ 查詢完成")
        results.sort(key=lambda x: x[5])
        return results
    
    def _search_google_places_chinese(self, lat, lng, api_key, keyword, radius):
        """Google Places 文字搜尋 - 直接使用中文關鍵字"""
        url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
        params = {
            "query": keyword,
            "location": f"{lat},{lng}",
            "radius": radius,
            "key": api_key,
            "language": "zh-TW"
        }
        
        try:
            resp = requests.get(url, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()
        except:
            return []
        
        results = []
        for p in data.get("results", []):
            loc = p["geometry"]["location"]
            dist = int(haversine(lat, lng, loc["lat"], loc["lng"]))
            results.append((
                "文字搜尋",
                keyword,
                p.get("name", "未命名"),
                loc["lat"],
                loc["lng"],
                dist,
                p.get("place_id", "")
            ))
        return results
    
    def _create_facilities_table(self, houses, places):
        """建立設施表格"""
        rows = []
        for h_name, h_info in houses.items():
            for p in places.get(h_name, []):
                rows.append({
                    "房屋": h_name,
                    "房屋標題": h_info['title'][:50],
                    "房屋地址": h_info['address'],
                    "設施名稱": p[2],
                    "設施子類別": p[1],
                    "距離(公尺)": p[5],
                    "經度": p[4],
                    "緯度": p[3]
                })
        return pd.DataFrame(rows)
    
    def _display_analysis_results(self, res):
        """顯示分析結果"""
        if not res:
            return
        
        mode = res["analysis_mode"]
        profile = res.get("buyer_profile", "未指定")
        profiles = self._get_buyer_profiles()
        pinfo = profiles.get(profile, {})
        icon = pinfo.get("icon", "👤")
        
        st.markdown("---")
        if mode == "單一房屋分析":
            st.markdown(f"## {icon} {profile}視角 · 單一房屋分析")
        else:
            st.markdown(f"## {icon} {profile}視角 · {res['num_houses']}間房屋比較")
        
        if pinfo:
            with st.expander(f"📌 {profile} 分析重點", expanded=False):
                for pt in pinfo.get("prompt_focus", []):
                    st.markdown(f"- {pt}")
        
        # 設施表格
        st.markdown("---")
        st.subheader("📋 設施詳細資料")
        df = res.get("facilities_table", pd.DataFrame())
        if not df.empty:
            st.info(f"📈 共 {len(df)} 筆設施")
            st.dataframe(df.head(50), use_container_width=True, hide_index=True)
            csv = df.to_csv(index=False, encoding='utf-8-sig')
            st.download_button("📥 下載 CSV", csv, f"設施_{time.strftime('%Y%m%d')}.csv", "text/csv")
        
        # 統計
        st.markdown("---")
        st.subheader("📈 設施統計")
        if res["num_houses"] == 1:
            self._show_single_stats(res)
        else:
            self._show_multi_stats(res)
        
        # 地圖
        self._display_maps(res)
        
        # AI 分析
        self._display_ai_analysis(res)
    
    def _show_single_stats(self, res):
        """單一房屋統計"""
        name = list(res["houses_data"].keys())[0]
        cnt = res["facility_counts"].get(name, 0)
        places = res["places_data"][name]
        
        if places:
            dists = [p[5] for p in places]
            avg = sum(dists) / len(dists)
            mini = min(dists)
            
            c1, c2, c3 = st.columns(3)
            c1.metric("總設施", f"{cnt} 個")
            c2.metric("平均距離", f"{avg:.0f} 公尺")
            c3.metric("最近設施", f"{mini} 公尺")
            
            # 類別統計
            from collections import Counter
            cat_cnt = Counter([p[1] for p in places])
            top10 = cat_cnt.most_common(10)
            
            if top10:
                st.markdown("#### 🏪 設施類型 TOP 10")
                chart = {
                    "xAxis": {"type": "category", "data": [x[0] for x in top10], 
                            "axisLabel": {"rotate": 45}},
                    "yAxis": {"type": "value"},
                    "series": [{"type": "bar", "data": [x[1] for x in top10]}],
                    "tooltip": {"trigger": "axis"}
                }
                st_echarts(chart, height="400px")
    
    def _show_multi_stats(self, res):
        """多房屋統計"""
        cnts = res["facility_counts"]
        names = list(cnts.keys())
        
        cols = st.columns(min(4, len(names)))
        for i, n in enumerate(names):
            with cols[i % len(cols)]:
                rank = sorted(cnts.values(), reverse=True).index(cnts[n]) + 1
                st.metric(f"🏠 {n}", f"{cnts[n]} 個", f"第{rank}名")
        
        if len(names) > 1:
            st.markdown("#### 📊 設施數量排名")
            data = sorted([(n, c) for n, c in cnts.items()], key=lambda x: x[1], reverse=True)
            chart = {
                "xAxis": {"type": "category", "data": [x[0] for x in data]},
                "yAxis": {"type": "value"},
                "series": [{"type": "bar", "data": [x[1] for x in data]}]
            }
            st_echarts(chart, height="300px")
    
    def _display_maps(self, res):
        """顯示地圖"""
        st.markdown("---")
        st.subheader("🗺️ 地圖檢視")
        
        bk = self._get_browser_key()
        if not bk:
            st.error("❌ 請填寫 Browser Key")
            return
        
        houses = res["houses_data"]
        places = res["places_data"]
        radius = res["radius"]
        
        if len(houses) == 1:
            n = list(houses.keys())[0]
            self._render_map(houses[n]["lat"], houses[n]["lng"], places[n], radius, n, houses[n], bk)
        elif len(houses) <= 3:
            cols = st.columns(len(houses))
            for i, (n, info) in enumerate(houses.items()):
                with cols[i]:
                    st.markdown(f"**{n}**")
                    self._render_map(info["lat"], info["lng"], places[n], radius, n, info, bk)
        else:
            tabs = st.tabs(list(houses.keys()))
            for i, (n, info) in enumerate(houses.items()):
                with tabs[i]:
                    self._render_map(info["lat"], info["lng"], places[n], radius, n, info, bk)
    
    def _render_map(self, lat, lng, places, radius, title, house_info, key):
        """渲染單張地圖"""
        if not places:
            st.info(f"📭 {title} 半徑 {radius} 公尺內無設施")
            return
        
        data = []
        for p in places:
            color = CATEGORY_COLORS.get(p[0], "#666")
            data.append({
                "name": p[2], "cat": p[0], "sub": p[1],
                "lat": p[3], "lng": p[4], "dist": p[5],
                "color": color,
                "url": f"https://www.google.com/maps/search/?api=1&query={p[3]},{p[4]}"
            })
        
        # 圖例
        cats = {}
        for d in data:
            cats[d["cat"]] = d["color"]
        legend = "".join([f'<div style="display:flex; align-items:center; margin-bottom:5px;"><div style="width:12px; height:12px; background:{c}; margin-right:5px;"></div><span>{cat}</span></div>' 
                         for cat, c in cats.items()])
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head><title>{title}地圖</title>
        <style>#map {{height:450px; width:100%;}} #legend {{background:white; padding:10px; border-radius:5px; margin:10px; font-size:12px;}}</style>
        </head>
        <body>
        <div id="map"></div>
        <script>
        function initMap() {{
            var center = {{lat: {lat}, lng: {lng}}};
            var map = new google.maps.Map(document.getElementById('map'), {{zoom: 16, center: center}});
            var main = new google.maps.Marker({{position: center, map: map, title: "{title}", icon: {{url: "http://maps.google.com/mapfiles/ms/icons/red-dot.png", scaledSize: new google.maps.Size(40,40)}}}});
            var win = new google.maps.InfoWindow({{content: '<div><h4>🏠 {title}</h4><p>地址: {house_info["address"] if house_info else "未知"}</p><p>半徑: {radius}公尺</p><p>設施: {len(data)}個</p></div>'}});
            main.addListener('click', function() {{ win.open(map, main); }});
            var legendDiv = document.createElement('div'); legendDiv.id = 'legend'; legendDiv.innerHTML = '<h4 style="margin:0 0 10px;">圖例</h4>' + `{legend}`;
            map.controls[google.maps.ControlPosition.RIGHT_TOP].push(legendDiv);
            var facilities = {json.dumps(data, ensure_ascii=False)};
            facilities.forEach(function(f) {{
                var pos = {{lat: f.lat, lng: f.lng}};
                var marker = new google.maps.Marker({{
                    position: pos, map: map, title: f.name + " (" + f.dist + "m)",
                    icon: {{path: google.maps.SymbolPath.CIRCLE, scale: 8, fillColor: f.color, fillOpacity: 0.9, strokeColor: "#FFF", strokeWeight: 2}}
                }});
                var info = '<div><h5 style="margin:0 0 5px;">' + f.name + '</h5><p><span style="color:' + f.color + ';font-weight:bold;">' + f.cat + ' - ' + f.sub + '</span></p><p>距離: ' + f.dist + '公尺</p><a href="' + f.url + '" target="_blank" style="display:inline-block; background:#1a73e8; color:white; padding:5px 10px; text-decoration:none; border-radius:3px;">🗺️ 查看地圖</a></div>';
                var infowindow = new google.maps.InfoWindow({{content: info}});
                marker.addListener('click', function() {{ infowindow.open(map, marker); }});
            }});
            var circle = new google.maps.Circle({{strokeColor: "#FF0000", strokeOpacity: 0.8, strokeWeight: 2, fillColor: "#FF0000", fillOpacity: 0.1, map: map, center: center, radius: {radius}}});
            setTimeout(function() {{ win.open(map, main); }}, 500);
        }}
        </script>
        <script src="https://maps.googleapis.com/maps/api/js?key={key}&callback=initMap" async defer></script>
        </body>
        </html>
        """
        st.markdown(f"**🗺️ {title} - 周邊設施**  (共 {len(places)} 個)")
        html(html_content, height=500)
    
    def _display_ai_analysis(self, res):
        """AI 分析"""
        st.markdown("---")
        st.subheader("🤖 AI 智能分析")
        
        profile = res.get("buyer_profile", "未指定")
        
        prompt = self._build_prompt(
            res["houses_data"], res["places_data"], res["facility_counts"],
            res["selected_categories"], res["radius"], res["keyword"],
            res["analysis_mode"], res.get("facilities_table", pd.DataFrame()), profile
        )
        
        if "custom_prompt" not in st.session_state:
            st.session_state.custom_prompt = prompt
        
        # 模板
        templates = self._get_prompt_templates(profile)
        opt = {k: f"{v['name']} - {v['description']}" for k, v in templates.items()}
        sel = st.selectbox("📋 提示詞模板", list(opt.keys()), format_func=lambda x: opt[x], key="tmpl")
        
        if sel == "default":
            st.session_state.custom_prompt = prompt
        elif "content" in templates[sel]:
            st.session_state.custom_prompt = templates[sel]["content"]
        
        c1, c2 = st.columns([3, 1])
        with c1:
            edited = st.text_area("📝 編輯提示詞", st.session_state.custom_prompt, height=350, key="pedit")
            if st.button("💾 儲存", use_container_width=True):
                st.session_state.custom_prompt = edited
                st.success("已儲存")
        with c2:
            pinfo = self._get_buyer_profiles().get(profile, {})
            st.markdown(f"#### 💡 {profile} 分析重點")
            for pt in pinfo.get("prompt_focus", [])[:4]:
                st.markdown(f"- {pt}")
            st.markdown("---")
            if st.button("🔄 恢復預設", use_container_width=True):
                st.session_state.custom_prompt = prompt
                st.rerun()
        
        if st.button("🚀 開始AI分析", type="primary", use_container_width=True):
            self._call_gemini(edited)
        
        if "gemini_result" in st.session_state:
            st.markdown("### 📋 AI 分析報告")
            st.markdown(st.session_state.gemini_result)
            
            c1, c2 = st.columns(2)
            with c1:
                if st.button("🔄 重新分析", use_container_width=True):
                    del st.session_state.gemini_result
                    del st.session_state.used_prompt
                    st.rerun()
            with c2:
                report = f"{profile}視角-分析報告\n{time.strftime('%Y-%m-%d %H:%M:%S')}\n\n{st.session_state.gemini_result}"
                st.download_button("📥 下載報告", report, f"{profile}_報告_{time.strftime('%Y%m%d')}.txt", use_container_width=True)
    
    def _build_prompt(self, houses, places, counts, cats, radius, keyword, mode, table, profile):
        """建立提示詞 - 完全客製化買家視角"""
        pinfo = self._get_buyer_profiles().get(profile, {})
        icon = pinfo.get("icon", "👤")
        focus = pinfo.get("prompt_focus", [])
        
        if mode == "單一房屋分析":
            name = list(houses.keys())[0]
            h = houses[name]
            cnt = counts.get(name, 0)
            
            return f"""
你是一位專業的房地產分析師，請以「{icon} {profile}」的身份與視角，對以下房屋進行**深度生活機能分析**。

【本次分析特別關注】
{chr(10).join([f'✅ {f}' for f in focus])}

【房屋資訊】
- 標題：{h['title']}
- 地址：{h['address']}

【搜尋條件】
- 半徑：{radius} 公尺
- 類別：{', '.join(cats)}
- 關鍵字：{keyword if keyword else '無'}

【設施統計】
- 總數量：{cnt} 個

【分析要求 - 完全代入{profile}角色】
1. **整體適合度評分**（1-5星）：請以{profile}的角度，給出綜合評分
2. **三大優點**：對{profile}來說，這間房子最吸引人的3點
3. **三大缺點**：對{profile}來說，這間房子最需要考慮的3點
4. **理想居住情境**：描述{profile}住在這裡的一天生活樣貌
5. **CP值評估**：以{profile}的預算與需求，這間房子划算嗎？
6. **一句話總結**：用一句話告訴{profile}要不要買

請用溫暖、貼近生活的語言，讓使用者感受到這是「為我量身打造的建議」。
"""
        else:
            # 多房屋比較
            house_list = "\n".join([f"- {n}：{h['title'][:30]}..." for n, h in houses.items()])
            rank_list = "\n".join([f"{i+1}. {n}（{counts[n]}個設施）" 
                                  for i, (n, _) in enumerate(sorted(counts.items(), key=lambda x: x[1], reverse=True))])
            
            return f"""
你是一位專業的房地產分析師，請以「{icon} {profile}」的身份，對以下{len(houses)}間房屋進行**比較分析**。

【本次分析特別關注】
{chr(10).join([f'✅ {f}' for f in focus])}

【候選房屋】
{house_list}

【設施數量排名】
{rank_list}

【分析要求 - 完全代入{profile}角色】
1. **總排名**：以{profile}的需求，將這幾間房屋由高到低排序
2. **首選推薦**：哪一間最適合{profile}？為什麼？
3. **備選推薦**：如果首選無法購買，第二選擇是哪間？
4. **各房屋優勢**：每間房屋對{profile}來說的獨特價值
5. **各房屋風險**：每間房屋對{profile}來說的潛在問題
6. **終極建議**：如果{profile}今天就要決定，你會建議選哪間？

請用「你就是{profile}」的口吻，給出真正有用的購買建議。
"""
    
    def _get_prompt_templates(self, profile=""):
        """提示詞模板"""
        return {
            "default": {"name": "🎯 預設模板", "description": f"{profile}視角標準分析"},
            "simple": {"name": "📋 簡明模板", "description": "快速掌握重點", 
                      "content": f"請以{profile}視角，用5要點分析：1.評分 2.三大優點 3.三大缺點 4.適合誰 5.一句話結論"},
            "lifestyle": {"name": "🏡 生活情境", "description": "描繪居住樣貌",
                         "content": f"請以{profile}身份，描述平日、週末、緊急狀況下的生活便利性"},
            "investment": {"name": "💰 投資價值", "description": "增值潛力分析",
                         "content": f"請以{profile}的投資需求，分析轉手性、租金投報、區域發展"}
        }
    
    def _call_gemini(self, prompt):
        """呼叫 Gemini API"""
        now = time.time()
        if now - st.session_state.get("last_gemini_call", 0) < 30:
            st.warning("⏳ 請等待30秒後再試")
            return
        
        st.session_state.last_gemini_call = now
        
        with st.spinner("🧠 AI 分析中..."):
            try:
                import google.generativeai as genai
                key = st.session_state.get("GEMINI_KEY", "")
                if not key:
                    st.error("❌ 請填寫 Gemini Key")
                    return
                
                genai.configure(api_key=key)
                model = genai.GenerativeModel("gemini-2.0-flash")
                resp = model.generate_content(prompt)
                
                st.session_state.gemini_result = resp.text
                st.session_state.used_prompt = prompt
                st.rerun()
            except Exception as e:
                st.error(f"❌ Gemini 錯誤: {e}")
    
    # ============= 輔助方法 =============
    
    def _get_favorites_data(self):
        """取得收藏"""
        if 'favorites' not in st.session_state or not st.session_state.favorites:
            return pd.DataFrame()
        
        df = None
        if 'all_properties_df' in st.session_state and not st.session_state.all_properties_df.empty:
            df = st.session_state.all_properties_df
        elif 'filtered_df' in st.session_state and not st.session_state.filtered_df.empty:
            df = st.session_state.filtered_df
        
        if df is None or df.empty:
            return pd.DataFrame()
        
        fav = st.session_state.favorites
        return df[df['編號'].astype(str).isin(map(str, fav))].copy()
    
    def _get_server_key(self):
        return st.session_state.get("GMAPS_SERVER_KEY") or st.session_state.get("GOOGLE_MAPS_KEY", "")
    
    def _get_browser_key(self):
        return st.session_state.get("GMAPS_BROWSER_KEY") or st.session_state.get("GOOGLE_MAPS_KEY", "")
    
    def _get_gemini_key(self):
        return st.session_state.get("GEMINI_KEY", "")


def get_comparison_analyzer():
    return ComparisonAnalyzer()
