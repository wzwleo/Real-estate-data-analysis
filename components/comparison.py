# components/comparison.py
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
from collections import Counter
import base64
from datetime import datetime
import io
import re

# 嘗試導入PDF相關庫
try:
    from fpdf import FPDF
    import matplotlib.pyplot as plt
    import matplotlib
    matplotlib.use('Agg')
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False
    pass

# 修正匯入路徑
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

try:
    from config import CATEGORY_COLORS, DEFAULT_RADIUS
    from components.place_types import PLACE_TYPES, CHINESE_TO_CATEGORY, NUISANCE_TYPES
    from components.geocoding import geocode_address, haversine
    CONFIG_LOADED = True
except ImportError as e:
    CONFIG_LOADED = False
    st.warning(f"無法載入設定: {e}")
    PLACE_TYPES = {}
    NUISANCE_TYPES = {}
    CHINESE_TO_CATEGORY = {}
    CATEGORY_COLORS = {}
    DEFAULT_RADIUS = 500


class ChinesePDF(FPDF):
    """支援中文的PDF類 - 使用系統內建字型"""
    
    def __init__(self):
        super().__init__()
        self.set_auto_page_break(auto=True, margin=15)
        self.font_loaded = False
        
        # 根據作業系統選擇中文字型
        try:
            if os.name == 'nt':  # Windows
                # 嘗試常見的Windows中文字型
                font_paths = [
                    'C:\\Windows\\Fonts\\msjh.ttc',  # 微軟正黑體
                    'C:\\Windows\\Fonts\\msjhbd.ttc',  # 微軟正黑體粗體
                    'C:\\Windows\\Fonts\\kaiu.ttf',  # 標楷體
                    'C:\\Windows\\Fonts\\mingliu.ttc',  # 細明體
                ]
                for font_path in font_paths:
                    if os.path.exists(font_path):
                        self.add_font('chinese', '', font_path, uni=True)
                        self.add_font('chinese', 'B', font_path, uni=True)
                        self.font_loaded = True
                        break
                        
            elif os.name == 'posix':  # macOS/Linux
                # macOS 字型路徑
                mac_fonts = [
                    '/System/Library/Fonts/PingFang.ttc',
                    '/System/Library/Fonts/STHeiti Light.ttc',
                    '/System/Library/Fonts/AppleGothic.ttf',
                ]
                # Linux 字型路徑
                linux_fonts = [
                    '/usr/share/fonts/truetype/wqy/wqy-microhei.ttc',
                    '/usr/share/fonts/truetype/arphic/uming.ttc',
                ]
                
                all_fonts = mac_fonts + linux_fonts
                for font_path in all_fonts:
                    if os.path.exists(font_path):
                        self.add_font('chinese', '', font_path, uni=True)
                        self.add_font('chinese', 'B', font_path, uni=True)
                        self.font_loaded = True
                        break
        except:
            self.font_loaded = False
    
    def header(self):
        if self.font_loaded:
            self.set_font('chinese', 'B', 16)
            self.cell(0, 10, '房屋分析報告', 0, 1, 'C')
        else:
            self.set_font('helvetica', 'B', 16)
            self.cell(0, 10, 'House Analysis Report', 0, 1, 'C')
        self.ln(5)
    
    def footer(self):
        self.set_y(-15)
        if self.font_loaded:
            self.set_font('chinese', '', 8)
            self.cell(0, 10, f'第 {self.page_no()} 頁', 0, 0, 'C')
        else:
            self.set_font('helvetica', '', 8)
            self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')
    
    def chapter_title(self, title):
        if self.font_loaded:
            self.set_font('chinese', 'B', 14)
        else:
            self.set_font('helvetica', 'B', 14)
        self.set_fill_color(200, 220, 255)
        self.cell(0, 10, title, 0, 1, 'L', 1)
        self.ln(5)
    
    def chapter_body(self, body):
        if self.font_loaded:
            self.set_font('chinese', '', 11)
        else:
            self.set_font('helvetica', '', 11)
        
        for line in body.split('\n'):
            if line.strip():
                # 如果沒有中文字型，過濾掉非ASCII字符
                if not self.font_loaded:
                    line = ''.join(c for c in line if ord(c) < 128)
                self.multi_cell(0, 8, line)
        self.ln(2)
    
    def add_table(self, df, title, max_rows=10):
        """添加表格到PDF"""
        self.chapter_title(title)
        
        # 計算列寬
        col_width = self.w / (min(len(df.columns), 5) + 1) - 2
        
        # 表頭
        if self.font_loaded:
            self.set_font('chinese', 'B', 10)
        else:
            self.set_font('helvetica', 'B', 10)
        self.set_fill_color(200, 200, 200)
        
        # 只顯示前5個欄位
        display_cols = list(df.columns)[:5]
        for col in display_cols:
            self.cell(col_width, 8, str(col)[:10], 1, 0, 'C', 1)
        self.ln()
        
        # 表格內容
        if self.font_loaded:
            self.set_font('chinese', '', 9)
        else:
            self.set_font('helvetica', '', 9)
        self.set_fill_color(255, 255, 255)
        
        for i, row in df.head(max_rows).iterrows():
            for col in display_cols:
                value = str(row[col])[:15]
                if not self.font_loaded:
                    value = ''.join(c for c in value if ord(c) < 128)
                self.cell(col_width, 8, value, 1, 0, 'C')
            self.ln()
        
        if len(df) > max_rows:
            if self.font_loaded:
                self.set_font('chinese', 'I', 9)
                self.cell(0, 8, f'... 還有 {len(df) - max_rows} 筆資料', 0, 1, 'L')
            else:
                self.set_font('helvetica', 'I', 9)
                self.cell(0, 8, f'... and {len(df) - max_rows} more items', 0, 1, 'L')
        self.ln(5)


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
            'auto_selected_subtypes': {},
            'analysis_completed': False,
            'saved_analyses': {},
            'current_analysis_name': None,
            'include_nuisance': False,
            'selected_nuisances': [],
            'last_selected_subtypes': {}
        }
        for key, value in defaults.items():
            if key not in st.session_state:
                st.session_state[key] = value
    
    def _get_buyer_profiles(self):
        """定義買家類型"""
        return {
            "首購族": {
                "icon": "🏠",
                "description": "年輕首購，預算有限，追求高效率生活",
                "priority_categories": {
                    "交通運輸": ["捷運站", "公車站", "火車站", "輕軌站"],
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
                    "生活服務": ["公園", "兒童遊戲場", "狗公園"],
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
                    "生活服務": ["公園", "河濱公園", "登山步道"],
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
                    "餐飲美食": ["咖啡廳", "速食店"],
                    "金融機構": ["ATM", "銀行", "郵局"]
                },
                "secondary_categories": {
                    "健康與保健": ["健身房", "藥局", "診所"],
                    "生活服務": ["洗衣店", "電影院"]
                },
                "radius": 400,
                "prompt_focus": ["交通樞紐距離", "南北往來便利性", "高效率生活圈", "短暫停留採買便利性"]
            },
            "投資客": {
                "icon": "💰",
                "description": "房產投資，重視增值潛力與租金報酬",
                "priority_categories": {
                    "交通運輸": ["捷運站", "火車站", "公車站"],
                    "購物": ["超市", "便利商店", "百貨公司"],
                    "餐飲美食": ["餐廳", "咖啡廳"],
                    "生活服務": ["公園"]
                },
                "secondary_categories": {
                    "教育": ["大學", "中學"],
                    "健康與保健": ["醫院", "診所"]
                },
                "radius": 700,
                "prompt_focus": ["區域發展潛力", "未來轉手性", "租金投報率", "增值空間"]
            }
        }
    
    def _auto_select_subtypes(self, profile_name):
        """根據買家類型自動選擇設施"""
        profiles = self._get_buyer_profiles()
        if profile_name not in profiles:
            return {}
        
        profile = profiles[profile_name]
        auto_subtypes = {}
        
        # 處理優先類別
        for cat, subtypes in profile.get("priority_categories", {}).items():
            if cat in PLACE_TYPES:
                if cat not in auto_subtypes:
                    auto_subtypes[cat] = []
                valid_subtypes = []
                seen = set()
                for s in subtypes:
                    if s in PLACE_TYPES[cat] and s not in seen:
                        valid_subtypes.append(s)
                        seen.add(s)
                auto_subtypes[cat].extend(valid_subtypes)
        
        # 處理次要類別
        for cat, subtypes in profile.get("secondary_categories", {}).items():
            if cat in PLACE_TYPES:
                if cat not in auto_subtypes:
                    auto_subtypes[cat] = []
                valid_subtypes = []
                seen = set(auto_subtypes.get(cat, []))
                for s in subtypes:
                    if s in PLACE_TYPES[cat] and s not in seen:
                        valid_subtypes.append(s)
                        seen.add(s)
                auto_subtypes[cat].extend(valid_subtypes)
        
        return auto_subtypes
    
    def _generate_pdf_report(self):
        """生成包含所有分析結果的PDF報告 - 使用系統字型"""
        if not PDF_AVAILABLE:
            return None
        
        if not st.session_state.saved_analyses:
            return None
        
        try:
            pdf = ChinesePDF()
            pdf.add_page()
            
            # 生成時間
            if pdf.font_loaded:
                pdf.set_font('chinese', '', 11)
                pdf.cell(0, 8, f'生成時間：{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}', 0, 1, 'C')
            else:
                pdf.set_font('helvetica', '', 11)
                pdf.cell(0, 8, f'Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}', 0, 1, 'C')
            pdf.ln(5)
            
            # 目錄
            pdf.chapter_title('目錄' if pdf.font_loaded else 'Table of Contents')
            for i, (name, analysis) in enumerate(st.session_state.saved_analyses.items()):
                profile = analysis.get('buyer_profile', '未知')
                display_name = name[:30] + '...' if len(name) > 30 else name
                if not pdf.font_loaded:
                    display_name = ''.join(c for c in display_name if ord(c) < 128)
                    profile = ''.join(c for c in profile if ord(c) < 128)
                pdf.cell(0, 8, f'{i+1}. {display_name} - {profile}視角', 0, 1)
            pdf.ln(5)
            
            # 逐個分析結果
            for i, (name, analysis) in enumerate(st.session_state.saved_analyses.items()):
                pdf.add_page()
                pdf.chapter_title(f'分析 {i+1}：{name[:30]}')
                
                # 基本資訊
                profile = analysis.get('buyer_profile', '未知')
                timestamp = analysis.get('timestamp', '未知時間')
                mode = analysis.get('analysis_mode', '')
                include_nuisance = analysis.get('include_nuisance', False)
                
                info = f"""
基本資訊：
- 買家類型：{profile}
- 分析時間：{timestamp}
- 分析模式：{mode}
{' - 包含嫌惡設施分析' if include_nuisance else ''}
                """
                pdf.chapter_body(info)
                
                # 房屋資訊
                houses_data = analysis.get('houses_data', {})
                pdf.set_font('chinese' if pdf.font_loaded else 'helvetica', 'B', 12)
                pdf.cell(0, 8, '房屋資訊：', 0, 1)
                pdf.set_font('chinese' if pdf.font_loaded else 'helvetica', '', 11)
                for h_name, h_info in houses_data.items():
                    pdf.multi_cell(0, 8, f"{h_name}：")
                    pdf.multi_cell(0, 8, f"  標題：{h_info.get('title', '未知')}")
                    pdf.multi_cell(0, 8, f"  地址：{h_info.get('address', '未知')}")
                pdf.ln(5)
                
                # 設施統計
                counts = analysis.get('facility_counts', {})
                pdf.set_font('chinese' if pdf.font_loaded else 'helvetica', 'B', 12)
                pdf.cell(0, 8, '設施統計：', 0, 1)
                pdf.set_font('chinese' if pdf.font_loaded else 'helvetica', '', 11)
                for h_name, count in counts.items():
                    pdf.cell(0, 8, f"{h_name}：{count} 個設施", 0, 1)
                pdf.ln(5)
                
                # 設施表格
                df = analysis.get('facilities_table', pd.DataFrame())
                if not df.empty:
                    pdf.add_table(df, '設施清單（前20筆）', max_rows=20)
                
                # AI 分析結果
                if 'gemini_result' in analysis:
                    pdf.set_font('chinese' if pdf.font_loaded else 'helvetica', 'B', 12)
                    pdf.cell(0, 8, 'AI 分析報告：', 0, 1)
                    pdf.set_font('chinese' if pdf.font_loaded else 'helvetica', '', 10)
                    
                    result_text = analysis['gemini_result']
                    for line in result_text.split('\n'):
                        if line.strip():
                            if not pdf.font_loaded:
                                line = ''.join(c for c in line if ord(c) < 128)
                            pdf.multi_cell(0, 6, line)
                    pdf.ln(5)
            
            return pdf.output(dest='S').encode('latin1')
            
        except Exception as e:
            st.error(f"PDF生成錯誤：{str(e)}")
            return None
    
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
            
            with st.sidebar:
                st.markdown("### 📊 已儲存分析")
                
                if st.session_state.saved_analyses:
                    for name, analysis in st.session_state.saved_analyses.items():
                        profile = analysis.get('buyer_profile', '未知')
                        icon = self._get_buyer_profiles().get(profile, {}).get('icon', '🏠')
                        timestamp = analysis.get('timestamp', '未知時間')
                        include_nuisance = analysis.get('include_nuisance', False)
                        
                        btn_label = f"{icon} {name[:20]}...\n{profile} | {timestamp}"
                        if include_nuisance:
                            btn_label = "⚠️ " + btn_label
                        
                        if name == st.session_state.current_analysis_name:
                            btn_label = f"👉 {btn_label}"
                        
                        if st.button(btn_label, key=f"saved_{name}", use_container_width=True):
                            st.session_state.current_analysis_name = name
                            st.rerun()
                    
                    if PDF_AVAILABLE:
                        if st.button("📥 下載所有分析為PDF", use_container_width=True):
                            with st.spinner("生成PDF中..."):
                                pdf_data = self._generate_pdf_report()
                                if pdf_data:
                                    b64 = base64.b64encode(pdf_data).decode()
                                    filename = f"房屋分析報告_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
                                    href = f'<a href="data:application/octet-stream;base64,{b64}" download="{filename}">點此下載PDF</a>'
                                    st.markdown(href, unsafe_allow_html=True)
                                else:
                                    st.error("PDF生成失敗")
                    else:
                        st.caption("📌 PDF下載功能需要安裝：`pip install fpdf`")
                    
                    if st.button("🗑️ 清除所有分析", use_container_width=True):
                        st.session_state.saved_analyses = {}
                        st.session_state.current_analysis_name = None
                        st.rerun()
                else:
                    st.info("尚無儲存的分析")
            
            if st.session_state.current_analysis_name and st.session_state.current_analysis_name in st.session_state.saved_analyses:
                current_analysis = st.session_state.saved_analyses[st.session_state.current_analysis_name]
                self._display_analysis_results(current_analysis)
                
                col1, col2, col3 = st.columns([1, 1, 2])
                with col1:
                    if st.button("🆕 新分析", use_container_width=True):
                        st.session_state.current_analysis_name = None
                        st.rerun()
                with col2:
                    if st.button("🗑️ 刪除此分析", use_container_width=True):
                        del st.session_state.saved_analyses[st.session_state.current_analysis_name]
                        st.session_state.current_analysis_name = None
                        st.rerun()
            else:
                self._render_life_function_analysis(fav_df)
            
        except Exception as e:
            st.error(f"❌ 渲染分析頁面時發生錯誤：{str(e)}")
            st.button("🔄 重新整理頁面", on_click=self._reset_page)
    
    def _render_life_function_analysis(self, fav_df):
        """渲染生活機能分析 - 包含嫌惡設施選項"""
        
        # 步驟1：買家類型選擇
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
                    
                    # 更新買家類型
                    st.session_state.buyer_profile = profile_name
                    
                    # 根據新買家類型取得推薦設施
                    subs = self._auto_select_subtypes(profile_name)
                    st.session_state.auto_selected_subtypes = subs
                    
                    # 立即更新 UI 顯示的選擇狀態
                    st.session_state.last_selected_subtypes = subs.copy()
                    
                    # 更新建議半徑
                    st.session_state.suggested_radius = profile_info.get("radius", DEFAULT_RADIUS)
                    
                    # 清除所有類別的臨時標記
                    for cat in PLACE_TYPES.keys():
                        if f"all_{cat}" in st.session_state:
                            del st.session_state[f"all_{cat}"]
                        if f"clear_{cat}" in st.session_state:
                            del st.session_state[f"clear_{cat}"]
                    
                    st.rerun()
        
        current_profile = st.session_state.get('buyer_profile')
        if current_profile:
            profile_info = profiles[current_profile]
            st.success(f"✅ 當前選擇：**{profile_info['icon']} {current_profile}**  |  📌 分析重點：{profile_info['prompt_focus'][0]}、{profile_info['prompt_focus'][1]}...")
        else:
            st.info("👆 請先選擇買家類型，系統將自動篩選最適合的生活機能")
            return
        
        st.markdown("---")
        
        # 步驟2：房屋選擇
        st.markdown("### 🏠 步驟2：選擇要分析的房屋")
        
        mode = st.radio("選擇分析模式", ["單一房屋分析", "多房屋比較"], horizontal=True, key="life_mode")
        st.session_state.analysis_mode = mode
        
        options = fav_df['標題'] + " | " + fav_df['地址']
        selected = []
        
        if mode == "單一房屋分析":
            choice = st.selectbox("選擇要分析的房屋", options, key="life_single_select")
            if choice:
                selected = [choice]
                house = fav_df[(fav_df['標題'] + " | " + fav_df['地址']) == choice].iloc[0]
                self._show_house_preview_single(house)
        else:
            default = options[:min(2, len(options))] if len(options) >= 1 else []
            selected = st.multiselect("選擇要比較的房屋", options, default=default, key="life_multi_select")
            if selected:
                self._show_houses_preview_multi(fav_df, selected)
        
        if not selected:
            if mode == "多房屋比較" and len(options) > 0:
                st.info("請至少選擇一間房屋")
            return
        
        st.session_state.selected_houses = selected
        st.markdown("---")
        
        # 步驟3：分析設定
        st.markdown("### ⚙️ 步驟3：分析設定")
        
        suggest_r = st.session_state.get('suggested_radius', DEFAULT_RADIUS)
        radius = st.slider(f"搜尋半徑（{profiles[current_profile]['icon']} 建議：{suggest_r}公尺）", 
                          100, 2000, suggest_r, 100, key="life_radius")
        
        keyword = st.text_input("額外關鍵字搜尋（選填）", key="life_keyword", placeholder="例如：公園、健身房")
        
        st.markdown("---")
        
        # 步驟4：生活機能選擇
        st.subheader("🔍 步驟4：選擇生活機能設施")
        
        auto_subs = st.session_state.get('auto_selected_subtypes', {})
        
        if auto_subs:
            total = sum(len(set(v)) for v in auto_subs.values())
            st.info(f"📌 **{current_profile} 推薦設施**：已自動選擇 {total} 種設施，可手動調整")
        
        # 顯示當前選擇摘要
        if st.session_state.last_selected_subtypes:
            total_selected = sum(len(v) for v in st.session_state.last_selected_subtypes.values())
            if total_selected > 0:
                st.markdown("### 📋 當前選擇摘要")
                st.info(f"📌 當前已選擇 **{total_selected}** 種設施")
                
                cols = st.columns(3)
                col_idx = 0
                for cat, items in st.session_state.last_selected_subtypes.items():
                    if items:
                        with cols[col_idx % 3]:
                            color = CATEGORY_COLORS.get(cat, "#666")
                            st.markdown(f"""
                            <div style="background-color:{color}20; padding:10px; border-radius:5px; border-left:4px solid {color}; margin-bottom:10px;">
                                <h5 style="color:{color}; margin:0;">{cat}</h5>
                                <p style="margin:5px 0 0; font-size:12px;">{', '.join(items[:3])}{'...' if len(items) > 3 else ''}</p>
                                <p style="margin:2px 0 0; font-size:11px; color:#666;">共 {len(items)} 種</p>
                            </div>
                            """, unsafe_allow_html=True)
                        col_idx += 1
        
        selected_subs = self._render_all_facilities_selection(auto_subs)
        
        if not selected_subs:
            st.warning("⚠️ 請至少選擇一個生活機能設施")
            return
        
        # 更新最後選擇
        st.session_state.last_selected_subtypes = selected_subs
        
        # 步驟5：嫌惡設施選擇（進階選項）
        st.markdown("---")
        st.subheader("⚠️ 嫌惡設施分析（選填）")
        st.markdown("勾選後將分析周邊的嫌惡設施，可自由選擇要分析的類型")
        
        include_nuisance = st.checkbox("加入嫌惡設施分析", value=False, 
                                      help="勾選後可選擇要分析的嫌惡設施類型")
        
        selected_nuisances = []
        if include_nuisance:
            selected_nuisances = self._render_nuisance_selection_full()
            st.session_state.selected_nuisances = selected_nuisances
        
        # 開始分析
        col1, col2 = st.columns([3, 1])
        with col1:
            btn_text = "🚀 開始分析" if mode == "單一房屋分析" else "🚀 開始比較"
            if st.button(btn_text, type="primary", use_container_width=True, key="life_start"):
                selected_cats = list(selected_subs.keys())
                valid = self._validate_inputs(selected, selected_cats)
                if valid == "OK":
                    self._start_analysis(
                        mode, selected, radius, keyword, 
                        selected_cats, selected_subs, fav_df, current_profile,
                        include_nuisance, selected_nuisances
                    )
                else:
                    st.error(valid)
        with col2:
            if st.button("🗑️ 清除", use_container_width=True, key="life_clear"):
                self._clear_all()
                st.rerun()
    
    def _render_nuisance_selection_full(self):
        """渲染完整的嫌惡設施選擇介面 - 包含等級標示"""
        selected = []
        
        st.markdown("#### 選擇嫌惡設施類型（可複選）")
        
        # 建立兩欄布局
        cols = st.columns(2)
        
        # 將嫌惡設施分成兩欄
        items = list(NUISANCE_TYPES.items())
        mid = len(items) // 2 + len(items) % 2
        
        for col_idx, column in enumerate(cols):
            with column:
                start_idx = col_idx * mid
                end_idx = min((col_idx + 1) * mid, len(items))
                
                for i in range(start_idx, end_idx):
                    nuisance_name, nuisance_info = items[i]
                    color = nuisance_info.get("color", "#dc3545")
                    level = nuisance_info.get("level", "中")
                    
                    # 根據等級顯示不同標記
                    if level == "高":
                        level_badge = "🔴 高度注意"
                    elif level == "中":
                        level_badge = "🟡 中度注意"
                    else:
                        level_badge = "🟢 低度注意"
                    
                    st.markdown(f"""
                    <div style="border-left:4px solid {color}; padding-left:8px; margin-bottom:10px;">
                        <span style="font-weight:bold;">{nuisance_name}</span>
                        <span style="color:{color}; font-size:12px; margin-left:5px;">{level_badge}</span>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    if st.checkbox(" ", key=f"nuisance_full_{i}", label_visibility="collapsed"):
                        selected.append(nuisance_name)
        
        if selected:
            st.success(f"✅ 已選擇 {len(selected)} 類嫌惡設施")
        else:
            st.info("👆 請選擇要分析的嫌惡設施類型（可複選）")
        
        return selected
    
    def _render_all_facilities_selection(self, preset_subtypes=None):
        """渲染所有設施選擇 - 即時顯示選擇內容"""
        selected_subs = {}
        preset_subs = preset_subtypes or {}
        
        st.markdown("#### 選擇設施類型")
        
        all_cats = list(PLACE_TYPES.keys())
        current_profile = st.session_state.get('buyer_profile', '')
        profiles = self._get_buyer_profiles()
        
        for cat in all_cats:
            with st.expander(f"📁 {cat}", expanded=True):
                # 顯示此類別已選擇數量
                current_selected_count = len(st.session_state.last_selected_subtypes.get(cat, []))
                if current_selected_count > 0:
                    st.caption(f"✅ 此類別已選擇 {current_selected_count} 種")
                
                cc1, cc2, cc3 = st.columns([1, 1, 2])
                with cc1:
                    if st.button(f"全選 {cat}", key=f"all_{cat}", use_container_width=True):
                        st.session_state[f"all_{cat}"] = True
                        st.rerun()
                with cc2:
                    if st.button(f"清除 {cat}", key=f"clear_{cat}", use_container_width=True):
                        st.session_state[f"clear_{cat}"] = True
                        st.rerun()
                with cc3:
                    if current_profile:
                        st.markdown(f"💡 **{current_profile}推薦**")
                
                # 取得此類別所有設施（去除重複）
                items = []
                seen = set()
                for item in PLACE_TYPES[cat]:
                    if item not in seen:
                        items.append(item)
                        seen.add(item)
                
                # 取得優先/次要推薦清單
                priority_list = []
                secondary_list = []
                if current_profile and current_profile in profiles:
                    p = profiles[current_profile]
                    priority_list = p.get("priority_categories", {}).get(cat, [])
                    secondary_list = p.get("secondary_categories", {}).get(cat, [])
                
                # 處理全選/清除
                force_all = st.session_state.get(f"all_{cat}", False)
                force_clear = st.session_state.get(f"clear_{cat}", False)
                
                if force_clear:
                    default_list = []
                else:
                    # 優先使用上次選擇
                    if cat in st.session_state.last_selected_subtypes:
                        default_list = st.session_state.last_selected_subtypes.get(cat, [])
                    else:
                        default_list = preset_subs.get(cat, []) if cat in preset_subs else []
                
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
                            elif name in priority_list and not force_clear:
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
                
                # 清除標記
                if f"all_{cat}" in st.session_state:
                    del st.session_state[f"all_{cat}"]
                if f"clear_{cat}" in st.session_state:
                    del st.session_state[f"clear_{cat}"]
                
                if cat in selected_subs:
                    st.caption(f"✅ 已選擇 {len(set(selected_subs[cat]))} 種")
        
        # 移除重複的選擇
        for cat in selected_subs:
            selected_subs[cat] = list(dict.fromkeys(selected_subs[cat]))
        
        return selected_subs
    
    def _validate_nuisance_inputs(self, houses, nuisances):
        """驗證嫌惡設施輸入"""
        if not self._get_server_key(): return "❌ 請填寫 Server Key"
        if not self._get_gemini_key(): return "❌ 請填寫 Gemini Key"
        if not nuisances: return "⚠️ 請至少選擇一個嫌惡設施類別"
        if not houses: return "⚠️ 請選擇房屋"
        if not st.session_state.get('buyer_profile'): return "⚠️ 請先選擇買家類型"
        return "OK"
    
    def _start_nuisance_analysis(self, mode, houses, radius, nuisances, fav_df, profile):
        """開始嫌惡設施分析"""
        try:
            st.session_state.analysis_settings = {
                "mode": mode, 
                "houses": houses, 
                "radius": radius, 
                "nuisances": nuisances,
                "server": self._get_server_key(),
                "gemini": self._get_gemini_key(), 
                "fav": fav_df.to_json(orient='split'),
                "profile": profile,
                "analysis_type": "嫌惡設施"
            }
            self._clear_old()
            st.session_state.analysis_in_progress = True
            st.session_state.analysis_completed = False
            self._execute_nuisance_analysis()
        except Exception as e:
            st.error(f"❌ 啟動失敗：{e}")
            st.session_state.analysis_in_progress = False
    
    def _execute_nuisance_analysis(self):
        """執行嫌惡設施分析核心"""
        try:
            s = st.session_state.analysis_settings
            fav_df = pd.read_json(s["fav"], orient='split')
            
            with st.status("🔍 分析進行中...", expanded=True) as status:
                st.write("📌 步驟 1/4：解析地址...")
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
                
                st.write("🔍 步驟 2/4：查詢周邊嫌惡設施...")
                nuisances_data = {}
                for idx, (name, info) in enumerate(houses_data.items()):
                    st.write(f"   - 查詢 {name} 周邊設施...")
                    nuisances = self._query_nuisances_no_progress(
                        info["lat"], info["lng"], s["server"],
                        s["nuisances"], s["radius"]
                    )
                    nuisances_data[name] = nuisances
                
                st.write("📊 步驟 3/4：計算風險評分...")
                counts = {n: len(p) for n, p in nuisances_data.items()}
                
                risk_scores = {}
                for name, nuisances in nuisances_data.items():
                    score = 0
                    for n in nuisances:
                        nuisance_type = n[0]
                        distance = n[5]
                        weight = self._get_nuisance_weight(nuisance_type)
                        if distance <= 300:
                            distance_factor = 1.0
                        elif distance <= 600:
                            distance_factor = 0.7
                        elif distance <= 900:
                            distance_factor = 0.4
                        else:
                            distance_factor = 0.2
                        score += weight * distance_factor
                    risk_scores[name] = round(score, 1)
                
                table = self._create_nuisance_table(houses_data, nuisances_data)
                
                st.write("💾 步驟 4/4：儲存結果...")
                
                analysis_result = {
                    "analysis_mode": s["mode"],
                    "analysis_type": "嫌惡設施",
                    "houses_data": houses_data,
                    "places_data": nuisances_data,
                    "facility_counts": counts,
                    "risk_scores": risk_scores,
                    "selected_nuisances": s["nuisances"],
                    "radius": s["radius"],
                    "num_houses": len(houses_data),
                    "facilities_table": table,
                    "buyer_profile": s.get("profile", "未指定"),
                    "timestamp": time.strftime('%Y-%m-%d %H:%M:%S')
                }
                
                if s["mode"] == "單一房屋分析":
                    name = list(houses_data.keys())[0]
                    analysis_name = f"{s.get('profile', '未知')}_{name}"
                else:
                    analysis_name = f"{s.get('profile', '未知')}_{s['mode']}_{len(houses_data)}間"
                
                st.session_state.saved_analyses[analysis_name] = analysis_result
                st.session_state.current_analysis_name = analysis_name
                
                status.update(label="✅ 分析完成！", state="complete", expanded=False)
            
            st.session_state.analysis_in_progress = False
            st.session_state.analysis_completed = True
            st.rerun()
            
        except Exception as e:
            st.error(f"❌ 分析失敗：{e}")
            st.session_state.analysis_in_progress = False
    
    def _query_nuisances_no_progress(self, lat, lng, api_key, nuisances, radius):
        """查詢嫌惡設施（無進度條版本）"""
        results = []
        seen = set()
        
        keywords = []
        for nuisance in nuisances:
            if nuisance in NUISANCE_TYPES:
                keywords.extend(NUISANCE_TYPES[nuisance].get("keywords", []))
        
        if not keywords:
            return results
        
        for keyword in keywords:
            try:
                places = self._search_google_places_chinese(lat, lng, api_key, keyword, radius)
                for p in places:
                    if p[5] > radius:
                        continue
                    pid = p[6]
                    if pid in seen:
                        continue
                    seen.add(pid)
                    
                    found_nuisance = "其他"
                    for nuisance_name, nuisance_info in NUISANCE_TYPES.items():
                        if keyword in nuisance_info.get("keywords", []):
                            found_nuisance = nuisance_name
                            break
                    
                    results.append((found_nuisance, keyword, p[2], p[3], p[4], p[5], p[6]))
                
                time.sleep(0.3)
            except Exception as e:
                st.warning(f"查詢 {keyword} 時發生錯誤：{e}")
                continue
        
        results.sort(key=lambda x: x[5])
        return results
    
    def _get_nuisance_weight(self, nuisance_type):
        """取得嫌惡設施的權重分數"""
        weights = {
            "加油站/瓦斯行": 9,
            "基地台/電塔/變電所": 8,
            "警察局/消防局": 4,
            "垃圾場/回收場": 8,
            "市場(傳統市場/夜市)": 6,
            "高架道路/地下道/捷運": 6,
            "特種行業/KTV/遊樂場": 7,
            "醫院": 5,
            "大型賣場/停車場": 5,
            "交流道": 8,
            "工業區/工廠": 9,
            "禮儀社/葬儀社": 10,
            "宮廟/神壇": 7,
            "焚化爐": 9,
            "發電廠": 8,
            "監獄": 8,
            "汙水處理廠": 8,
            "飛機場": 8,
            "公墓/靈骨塔/殯儀館": 10,
            "畜牧業": 7
        }
        return weights.get(nuisance_type, 5)
    
    def _create_nuisance_table(self, houses, places):
        """建立嫌惡設施表格"""
        rows = []
        for h_name, h_info in houses.items():
            for p in places.get(h_name, []):
                rows.append({
                    "房屋": h_name,
                    "房屋標題": h_info['title'][:50],
                    "房屋地址": h_info['address'],
                    "嫌惡設施名稱": p[2],
                    "嫌惡設施類型": p[1],
                    "主要類別": p[0],
                    "距離(公尺)": p[5],
                    "經度": p[4],
                    "緯度": p[3],
                    "place_id": p[6]
                })
        return pd.DataFrame(rows)
    
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
                'buyer_profile', 'auto_selected_subtypes',
                'analysis_completed', 'saved_analyses', 'current_analysis_name',
                'last_selected_subtypes']
        for k in keys:
            if k in st.session_state:
                del st.session_state[k]
    
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
        if not self._get_server_key(): return "❌ 請填寫 Server Key"
        if not self._get_gemini_key(): return "❌ 請填寫 Gemini Key"
        if not cats: return "⚠️ 請至少選擇一個生活機能類別"
        if not houses: return "⚠️ 請選擇房屋"
        if not st.session_state.get('buyer_profile'): return "⚠️ 請先選擇買家類型"
        return "OK"
    
    def _start_analysis(self, mode, houses, radius, keyword, cats, subs, fav_df, profile, include_nuisance=False, selected_nuisances=None):
        """開始分析 - 四種情境"""
        try:
            st.session_state.analysis_settings = {
                "mode": mode, 
                "houses": houses, 
                "radius": radius, 
                "keyword": keyword,
                "cats": cats, 
                "subs": subs, 
                "server": self._get_server_key(),
                "gemini": self._get_gemini_key(), 
                "fav": fav_df.to_json(orient='split'),
                "profile": profile, 
                "include_nuisance": include_nuisance,
                "selected_nuisances": selected_nuisances or []
            }
            self._clear_old()
            st.session_state.analysis_in_progress = True
            st.session_state.analysis_completed = False
            self._execute_analysis()
        except Exception as e:
            st.error(f"❌ 啟動失敗：{e}")
            st.session_state.analysis_in_progress = False
    
    def _clear_old(self):
        """清除舊結果"""
        for k in ['analysis_results', 'gemini_result', 'places_data', 'custom_prompt', 'used_prompt']:
            if k in st.session_state: del st.session_state[k]
    
    def _clear_all(self):
        """全部清除"""
        keys = ['analysis_settings', 'analysis_results', 'analysis_in_progress', 'gemini_result',
                'custom_prompt', 'used_prompt', 'selected_houses', 'buyer_profile',
                'auto_selected_subtypes', 'suggested_radius',
                'analysis_completed', 'saved_analyses', 'current_analysis_name',
                'last_selected_subtypes']
        for k in keys:
            if k in st.session_state: del st.session_state[k]
    
    def _execute_analysis(self):
        """執行分析核心 - 修正嫌惡設施查詢"""
        try:
            s = st.session_state.analysis_settings
            fav_df = pd.read_json(s["fav"], orient='split')
            
            with st.status("🔍 分析進行中...", expanded=True) as status:
                # 步驟1：解析地址
                st.write("📌 步驟 1/4：解析地址...")
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
                
                # 步驟2：查詢生活機能設施
                st.write("🔍 步驟 2/4：查詢周邊生活機能設施...")
                places_data = {}
                for idx, (name, info) in enumerate(houses_data.items()):
                    st.write(f"   - 查詢 {name} 周邊設施...")
                    places = self._query_places_chinese_no_progress(
                        info["lat"], info["lng"], s["server"],
                        s["cats"], s["subs"], s["radius"], s["keyword"]
                    )
                    places_data[name] = places
                
                # 步驟2.5：如果需要，查詢嫌惡設施
                nuisance_data = {}
                if s.get("include_nuisance", False) and s.get("selected_nuisances"):
                    st.write("🔍 步驟 2.5/4：查詢周邊嫌惡設施...")
                    for idx, (name, info) in enumerate(houses_data.items()):
                        st.write(f"   - 查詢 {name} 周邊嫌惡設施...")
                        nuisances = self._query_nuisances_no_progress(
                            info["lat"], info["lng"], s["server"],
                            s["selected_nuisances"], s["radius"]
                        )
                        nuisance_data[name] = nuisances
                        
                        # 確保 places_data[name] 存在
                        if name not in places_data:
                            places_data[name] = []
                        
                        # 將嫌惡設施加入 places_data（用不同的類別標示）
                        st.write(f"     找到 {len(nuisances)} 處嫌惡設施")
                        for n in nuisances:
                            # n 的格式：(found_nuisance, keyword, name, lat, lng, dist, pid)
                            places_data[name].append(("嫌惡設施", n[1], n[2], n[3], n[4], n[5], n[6]))
                
                # 步驟3：計算統計
                st.write("📊 步驟 3/4：計算統計...")
                counts = {n: len(p) for n, p in places_data.items()}
                table = self._create_facilities_table(houses_data, places_data)
                
                # 步驟4：儲存結果
                st.write("💾 步驟 4/4：儲存結果...")
                
                analysis_result = {
                    "analysis_mode": s["mode"],
                    "houses_data": houses_data,
                    "places_data": places_data,
                    "facility_counts": counts,
                    "selected_categories": s["cats"],
                    "radius": s["radius"],
                    "keyword": s["keyword"],
                    "num_houses": len(houses_data),
                    "facilities_table": table,
                    "buyer_profile": s.get("profile", "未指定"),
                    "timestamp": time.strftime('%Y-%m-%d %H:%M:%S'),
                    "include_nuisance": s.get("include_nuisance", False),
                    "nuisance_data": nuisance_data if s.get("include_nuisance", False) else None
                }
                
                if s["mode"] == "單一房屋分析":
                    name = list(houses_data.keys())[0]
                    analysis_name = f"{s.get('profile', '未知')}_{name}"
                else:
                    analysis_name = f"{s.get('profile', '未知')}_{s['mode']}_{len(houses_data)}間"
                
                st.session_state.saved_analyses[analysis_name] = analysis_result
                st.session_state.current_analysis_name = analysis_name
                
                status.update(label="✅ 分析完成！", state="complete", expanded=False)
            
            st.session_state.analysis_in_progress = False
            st.session_state.analysis_completed = True
            st.rerun()
            
        except Exception as e:
            st.error(f"❌ 分析失敗：{e}")
            st.session_state.analysis_in_progress = False
    
    def _query_places_chinese_no_progress(self, lat, lng, api_key, categories, subtypes, radius=500, extra=""):
        """查詢設施（無進度條版本）"""
        results = []
        seen = set()
        
        keywords = set()
        for cat in categories:
            if cat in subtypes:
                for keyword in subtypes[cat]:
                    keywords.add(keyword)
        if extra:
            keywords.add(extra)
        
        keywords = list(keywords)
        
        if not keywords:
            return results
        
        for keyword in keywords:
            try:
                places = self._search_google_places_chinese(lat, lng, api_key, keyword, radius)
                for p in places:
                    if p[5] > radius:
                        continue
                    pid = p[6]
                    if pid in seen:
                        continue
                    seen.add(pid)
                    
                    found_cat = "其他"
                    for c in categories:
                        if keyword in subtypes.get(c, []):
                            found_cat = c
                            break
                    
                    results.append((found_cat, keyword, p[2], p[3], p[4], p[5], p[6]))
                
                time.sleep(0.3)
            except:
                continue
        
        results.sort(key=lambda x: x[5])
        return results
    
    def _search_google_places_chinese(self, lat, lng, api_key, keyword, radius):
        """Google Places 文字搜尋"""
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
                    "緯度": p[3],
                    "place_id": p[6]
                })
        return pd.DataFrame(rows)
    
    def _display_analysis_results(self, res):
        """顯示分析結果"""
        if not res:
            return
        
        mode = res["analysis_mode"]
        profile = res.get("buyer_profile", "未指定")
        timestamp = res.get("timestamp", "未知時間")
        include_nuisance = res.get("include_nuisance", False)
        profiles = self._get_buyer_profiles()
        pinfo = profiles.get(profile, {})
        icon = pinfo.get("icon", "👤")
        
        st.markdown(f"### 分析時間：{timestamp}")
        if include_nuisance:
            st.info("⚠️ 此分析包含嫌惡設施評估")
        st.markdown("---")
        
        if mode == "單一房屋分析":
            st.markdown(f"## {icon} {profile}視角 · 單一房屋分析" + (" (含嫌惡設施)" if include_nuisance else ""))
        else:
            st.markdown(f"## {icon} {profile}視角 · {res['num_houses']}間房屋比較" + (" (含嫌惡設施)" if include_nuisance else ""))
        
        if pinfo:
            with st.expander(f"📌 {profile} 分析重點", expanded=False):
                for pt in pinfo.get("prompt_focus", []):
                    st.markdown(f"- {pt}")
        
        st.markdown("---")
        st.subheader("📋 設施詳細資料表格" + (" (包含嫌惡設施)" if include_nuisance else ""))
        
        df = res.get("facilities_table", pd.DataFrame())
        if not df.empty:
            nuisance_count = 0
            if include_nuisance and res.get('nuisance_data'):
                for house_name in res['houses_data'].keys():
                    nuisance_count = len(res['nuisance_data'].get(house_name, []))
                    if nuisance_count > 0:
                        break
            
            st.info(f"📈 共找到 {len(df)} 筆資料" + (f"（包含 {nuisance_count} 處嫌惡設施）" if nuisance_count > 0 else ""))
            
            st.dataframe(
                df,
                use_container_width=True,
                column_config={
                    "房屋": st.column_config.TextColumn(width="small"),
                    "房屋標題": st.column_config.TextColumn(width="medium"),
                    "房屋地址": st.column_config.TextColumn(width="medium"),
                    "設施名稱": st.column_config.TextColumn(width="large"),
                    "設施子類別": st.column_config.TextColumn(width="small"),
                    "距離(公尺)": st.column_config.NumberColumn(format="%d 公尺"),
                    "place_id": st.column_config.TextColumn("Google地圖", 
                        help="點擊連結在Google地圖中查看",
                        width="small"
                    )
                },
                column_order=["房屋", "房屋標題", "房屋地址", "設施名稱", "設施子類別", "距離(公尺)", "place_id"],
                hide_index=True
            )
            
            csv = df.to_csv(index=False, encoding='utf-8-sig')
            st.download_button(
                label="📥 下載完整設施資料 (CSV)",
                data=csv,
                file_name=f"設施資料_{time.strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                key="download_facilities_csv"
            )
        
        st.markdown("---")
        st.subheader("📈 設施統計")
        if res["num_houses"] == 1:
            self._show_single_stats(res)
        else:
            self._show_multi_stats(res)
        
        self._display_maps(res)
        self._display_facilities_list_with_links(res)
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
            c1.metric("🏠 總設施數量", f"{cnt} 個")
            c2.metric("📏 平均距離", f"{avg:.0f} 公尺")
            c3.metric("📍 最近設施", f"{mini} 公尺")
            
            cat_cnt = Counter([p[1] for p in places])
            top10 = cat_cnt.most_common(10)
            
            if top10:
                st.markdown("#### 🏪 各類型設施分布")
                chart_data = {
                    "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}},
                    "grid": {"left": "3%", "right": "4%", "bottom": "15%", "top": "10%", "containLabel": True},
                    "xAxis": {
                        "type": "category",
                        "data": [x[0] for x in top10],
                        "axisLabel": {"rotate": 45, "interval": 0}
                    },
                    "yAxis": {"type": "value"},
                    "series": [{
                        "type": "bar",
                        "data": [x[1] for x in top10],
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
                        "label": {"show": True, "position": "top"}
                    }]
                }
                st_echarts(chart_data, height="500px")
                
                with st.expander("📊 查看詳細設施類型統計"):
                    subtype_df = pd.DataFrame(top10, columns=["設施類型", "數量"])
                    st.dataframe(subtype_df, use_container_width=True, hide_index=True)
    
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
            chart_data = {
                "xAxis": {"type": "category", "data": [x[0] for x in data]},
                "yAxis": {"type": "value"},
                "series": [{
                    "type": "bar",
                    "data": [x[1] for x in data],
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
    
    def _display_maps(self, res):
        """顯示地圖"""
        st.markdown("---")
        st.subheader("🗺️ 地圖檢視")
        
        bk = self._get_browser_key()
        if not bk:
            st.error("❌ 請在側邊欄填入 Google Maps Browser Key")
            return
        
        houses = res["houses_data"]
        places = res["places_data"]
        radius = res["radius"]
        
        if len(houses) == 1:
            n = list(houses.keys())[0]
            self._render_map_with_links(
                houses[n]["lat"], houses[n]["lng"], places[n], radius, n, houses[n], bk
            )
        elif len(houses) <= 3:
            cols = st.columns(len(houses))
            for i, (n, info) in enumerate(houses.items()):
                with cols[i]:
                    st.markdown(f"### {n}")
                    self._render_map_with_links(
                        info["lat"], info["lng"], places[n], radius, n, info, bk
                    )
        else:
            tabs = st.tabs(list(houses.keys()))
            for i, (n, info) in enumerate(houses.items()):
                with tabs[i]:
                    self._render_map_with_links(
                        info["lat"], info["lng"], places[n], radius, n, info, bk
                    )
    
    def _render_map_with_links(self, lat, lng, places, radius, title, house_info, browser_key):
        """渲染地圖"""
        if not browser_key:
            st.error("❌ 請在側邊欄填入 Google Maps Browser Key")
            return
        
        facilities_data = []
        for p in places:
            # 判斷是否為嫌惡設施
            if p[0] == "嫌惡設施":
                color = "#dc3545"  # 紅色
            else:
                color = CATEGORY_COLORS.get(p[0], "#666")
            
            facilities_data.append({
                "name": p[2],
                "category": p[0],
                "subtype": p[1],
                "lat": p[3],
                "lng": p[4],
                "distance": p[5],
                "color": color,
                "place_id": p[6],
                "maps_url": f"https://www.google.com/maps/search/?api=1&query={p[3]},{p[4]}&query_place_id={p[6]}"
            })
        
        categories = {}
        for f in facilities_data:
            categories[f["category"]] = f["color"]
        
        legend_html = ""
        for cat, color in categories.items():
            legend_html += f"""
            <div class="legend-item">
                <div class="legend-color" style="background-color:{color};"></div>
                <span>{cat}</span>
            </div>
            """
        
        facilities_json = json.dumps(facilities_data, ensure_ascii=False)
        
        address_str = house_info.get('address', '未知地址') if house_info else '未知地址'
        address_str = address_str.replace('"', '&quot;').replace("'", "\\'")
        
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
                    box-shadow: 0 2px 6px rgba(0,0,0,0.1);
                    position: absolute;
                    right: 10px;
                    top: 10px;
                    z-index: 1000;
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
                .info-window {{
                    padding: 12px;
                    max-width: 260px;
                }}
                .info-window h5 {{
                    margin: 0 0 8px 0;
                    color: #333;
                    font-size: 16px;
                }}
                .info-window p {{
                    margin: 5px 0;
                    color: #666;
                }}
                .maps-link {{
                    display: inline-block;
                    margin-top: 10px;
                    padding: 8px 12px;
                    background-color: #1a73e8;
                    color: white !important;
                    text-decoration: none;
                    border-radius: 4px;
                    font-size: 12px;
                    font-weight: 500;
                }}
                .maps-link:hover {{
                    background-color: #1557b0;
                }}
            </style>
        </head>
        <body>
            <div id="map"></div>
            
            <script>
                function initMap() {{
                    var center = {{lat: {lat}, lng: {lng}}};
                    
                    var map = new google.maps.Map(document.getElementById('map'), {{
                        zoom: 16,
                        center: center,
                        mapTypeControl: true,
                        streetViewControl: true,
                        fullscreenControl: true
                    }});
                    
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
                    
                    var mainInfoContent = '<div class="info-window">' +
                                         '<h5>🏠 {title}</h5>' +
                                         '<p><strong>地址：</strong>{address_str}</p>' +
                                         '<p><strong>搜尋半徑：</strong>{radius} 公尺</p>' +
                                         '<p><strong>設施數量：</strong>{len(places)} 個</p>' +
                                         '</div>';
                    
                    var mainInfoWindow = new google.maps.InfoWindow({{
                        content: mainInfoContent
                    }});
                    
                    mainMarker.addListener("click", function() {{
                        mainInfoWindow.open(map, mainMarker);
                    }});
                    
                    var legendDiv = document.createElement('div');
                    legendDiv.id = 'legend';
                    legendDiv.innerHTML = '<h4 style="margin-top:0; margin-bottom:10px;">設施類別圖例</h4>' + `{legend_html}`;
                    map.controls[google.maps.ControlPosition.RIGHT_TOP].push(legendDiv);
                    
                    var facilities = {facilities_json};
                    
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
                        
                        var infoContent = '<div class="info-window">' +
                                          '<h5>' + facility.name + '</h5>' +
                                          '<p>' +
                                          '<span style="color:' + facility.color + '; font-weight:bold;">' + 
                                          facility.category + ' - ' + facility.subtype + 
                                          '</span></p>' +
                                          '<p><strong>距離：</strong>' + facility.distance + ' 公尺</p>' +
                                          '<a href="' + facility.maps_url + '" target="_blank" class="maps-link">' +
                                          '🗺️ 在 Google 地圖中查看</a>' +
                                          '</div>';
                        
                        var infoWindow = new google.maps.InfoWindow({{
                            content: infoContent
                        }});
                        
                        marker.addListener("click", function() {{
                            infoWindow.open(map, marker);
                        }});
                    }});
                    
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
                    
                    setTimeout(function() {{
                        mainInfoWindow.open(map, mainMarker);
                    }}, 1000);
                }}
                
                function handleMapError() {{
                    document.getElementById('map').innerHTML = 
                        '<div style="padding:20px; text-align:center; color:red;">' +
                        '<h3>❌ 地圖載入失敗</h3>' +
                        '<p>請檢查 Google Maps API Key 是否正確</p>' +
                        '</div>';
                }}
            </script>
            
            <script src="https://maps.googleapis.com/maps/api/js?key={browser_key}&callback=initMap" 
                    async defer 
                    onerror="handleMapError()"></script>
        </body>
        </html>
        """
        
        st.markdown(f"**🗺️ {title} - 周邊設施地圖**")
        if places:
            st.markdown(f"📊 **共找到 {len(places)} 個設施** (搜尋半徑: {radius}公尺)")
        else:
            st.info(f"📭 {title} 周圍半徑 {radius} 公尺內未找到設施")
        
        html(html_content, height=550)
    
    def _display_facilities_list_with_links(self, res):
        """顯示設施列表"""
        st.markdown("---")
        include_nuisance = res.get("include_nuisance", False)
        
        st.subheader("📍 全部設施列表" + (" (包含嫌惡設施)" if include_nuisance else ""))
        
        for house_name, places in res["places_data"].items():
            if places:
                with st.expander(f"🏠 {house_name} - 共 {len(places)} 個設施", expanded=False):
                    for i, p in enumerate(places, 1):
                        cat, subtype, name, lat, lng, dist, pid = p
                        
                        # 判斷是否為嫌惡設施
                        if cat == "嫌惡設施":
                            color = "#dc3545"
                            is_nuisance = True
                        else:
                            color = CATEGORY_COLORS.get(cat, "#666")
                            is_nuisance = False
                        
                        maps_url = f"https://www.google.com/maps/search/?api=1&query={lat},{lng}&query_place_id={pid}"
                        
                        if dist <= 300:
                            dist_color = "#dc3545" if is_nuisance else "#28a745"
                            dist_badge = "很近" if not is_nuisance else "⚠️ 危險近"
                        elif dist <= 600:
                            dist_color = "#fd7e14" if is_nuisance else "#ffc107"
                            dist_badge = "中等" if not is_nuisance else "⚠️ 需注意"
                        else:
                            dist_color = "#ffc107" if is_nuisance else "#dc3545"
                            dist_badge = "較遠" if not is_nuisance else "🟢 尚可"
                        
                        col1, col2, col3, col4 = st.columns([5, 2, 2, 2])
                        
                        with col1:
                            st.markdown(f"**{i}.** {name}")
                        
                        with col2:
                            st.markdown(f'<span style="background-color:{color}20; color:{color}; padding:4px 8px; border-radius:8px; font-size:12px; font-weight:bold;">{subtype}</span>', 
                                      unsafe_allow_html=True)
                        
                        with col3:
                            st.markdown(f'<span style="background-color:{dist_color}20; color:{dist_color}; padding:4px 8px; border-radius:8px; font-size:12px; font-weight:bold;">{dist}公尺 ({dist_badge})</span>', 
                                      unsafe_allow_html=True)
                        
                        with col4:
                            st.link_button("🗺️ 地圖", maps_url, use_container_width=True)
                        
                        st.divider()
            else:
                st.info(f"📭 {house_name} 周圍未找到設施")
    
    def _display_ai_analysis(self, res):
        """AI 分析 - 四種情境"""
        st.markdown("---")
        st.subheader("🤖 AI 智能分析")
        
        profile = res.get("buyer_profile", "未指定")
        mode = res["analysis_mode"]
        include_nuisance = res.get("include_nuisance", False)
        profiles = self._get_buyer_profiles()
        pinfo = profiles.get(profile, {})
        icon = pinfo.get("icon", "👤")
        
        # 產生詳細的設施清單（全部列出）
        facilities_text = self._format_all_facilities_for_prompt(res)
        
        # 根據四種情境選擇不同的提示詞
        if mode == "單一房屋分析":
            if include_nuisance:
                prompt = self._build_single_with_nuisance_prompt(res, facilities_text, profile, icon, pinfo)
            else:
                prompt = self._build_single_without_nuisance_prompt(res, facilities_text, profile, icon, pinfo)
        else:  # 多房屋比較
            if include_nuisance:
                prompt = self._build_multi_with_nuisance_prompt(res, facilities_text, profile, icon, pinfo)
            else:
                prompt = self._build_multi_without_nuisance_prompt(res, facilities_text, profile, icon, pinfo)
        
        if "custom_prompt" not in st.session_state:
            st.session_state.custom_prompt = prompt
        
        c1, c2 = st.columns([3, 1])
        with c1:
            edited = st.text_area("📝 AI 分析提示詞設定（可編輯）", st.session_state.custom_prompt, height=350, key="pedit")
            if st.button("💾 儲存提示詞修改", use_container_width=True, key="save_prompt"):
                st.session_state.custom_prompt = edited
                st.success("✅ 提示詞已儲存！")
        with c2:
            st.markdown(f"#### 💡 {profile} 分析重點")
            for pt in pinfo.get("prompt_focus", [])[:4]:
                st.markdown(f"- {pt}")
            if include_nuisance:
                st.markdown("---")
                st.markdown("⚠️ **此分析包含嫌惡設施評估**")
            st.markdown("---")
            st.markdown("**提示：**")
            st.markdown("您可以編輯左側的提示詞，讓AI更符合您的需求")
            if st.button("🔄 恢復預設提示詞", use_container_width=True, key="reset_prompt"):
                st.session_state.custom_prompt = prompt
                st.rerun()
        
        if st.button("🚀 開始AI分析", type="primary", use_container_width=True, key="start_ai"):
            self._call_gemini(edited)
        
        if "gemini_result" in st.session_state:
            st.markdown("### 📋 AI 分析報告")
            
            with st.expander("ℹ️ 查看本次使用的提示詞摘要", expanded=False):
                used = st.session_state.used_prompt
                st.text(used[:500] + ("..." if len(used) > 500 else ""))
            
            st.markdown("---")
            st.markdown(st.session_state.gemini_result)
            st.markdown("---")
            
            if st.session_state.current_analysis_name and st.session_state.current_analysis_name in st.session_state.saved_analyses:
                st.session_state.saved_analyses[st.session_state.current_analysis_name]['gemini_result'] = st.session_state.gemini_result
            
            c1, c2 = st.columns(2)
            with c1:
                if st.button("🔄 重新分析", use_container_width=True, key="reanalyze"):
                    del st.session_state.gemini_result
                    del st.session_state.used_prompt
                    st.rerun()
            with c2:
                report_title = f"{profile}視角-{'含嫌惡設施' if include_nuisance else '生活機能'}報告"
                if mode != "單一房屋分析":
                    report_title = f"{profile}視角-{res['num_houses']}間房屋{'含嫌惡設施' if include_nuisance else '生活機能'}比較報告"
                
                report = f"{report_title}\n生成時間：{time.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                report += f"AI 分析結果：\n{st.session_state.gemini_result}"
                st.download_button(
                    label="📥 下載分析報告",
                    data=report,
                    file_name=f"{report_title}_{time.strftime('%Y%m%d_%H%M%S')}.txt",
                    mime="text/plain",
                    use_container_width=True,
                    key="download_report"
                )
    
    def _build_single_without_nuisance_prompt(self, res, facilities_text, profile, icon, pinfo):
        """單一房屋無嫌惡設施的提示詞"""
        name = list(res["houses_data"].keys())[0]
        h = res["houses_data"][name]
        cnt = res["facility_counts"].get(name, 0)
        focus = pinfo.get("prompt_focus", [])
        
        return f"""
你是一位專業的房地產分析師，請以「{icon} {profile}」的身份，對以下房屋進行生活機能分析與評分。

【買家類型】
{profile} - {pinfo.get('description', '')}
重點關注：{', '.join(focus)}

【房屋資訊】
- 標題：{h['title']}
- 地址：{h['address']}

【搜尋條件】
- 半徑：{res['radius']} 公尺
- 分析類別：{', '.join(res['selected_categories'])}
- 關鍵字：{res.get('keyword', '') if res.get('keyword') else '無'}

【周邊設施統計】
- 總數量：{cnt} 個設施

【完整設施清單】
{facilities_text}

請提供以下分析：

1. **綜合評分**（1-10分）
   請根據{profile}的需求給出具體分數，並詳細說明評分依據：
   - 交通便利性（滿分3分）：根據周邊交通設施數量和距離評分
   - 日常採買（滿分3分）：根據超市、便利商店等設施評分
   - 生活品質（滿分2分）：根據公園、餐廳等設施評分
   - 特殊需求（滿分2分）：根據{profile}的關注重點評分
   請列出每項得分和計算方式。

2. **主要優點**（3-5點）
   對{profile}來說最實用的設施和生活機能，請具體說明每個優點如何提升生活品質，並引用具體的設施名稱和距離。

3. **主要缺點**（3-5點）
   對{profile}來說的不足之處或潛在問題，請具體說明每個缺點的影響程度，並指出缺少哪些重要設施。

4. **生活便利性預測**
   - 平日通勤/上班日：預測平日的生活便利性
   - 假日生活：預測週末的生活樣貌
   - 緊急情況（醫療、採買）：評估緊急情況下的應變能力

5. **未來發展潛力**
   根據周邊設施和區域特性，預測這個地點未來3-5年的發展潛力。

6. **購買建議**
   - 是否適合{profile}購買？
   - 合理的價格區間建議
   - 什麼時候是最佳購買時機？

請用專業、客觀的角度分析，給出實用的建議，並盡量引用具體的設施名稱和距離來支持你的觀點。
"""

    def _build_single_with_nuisance_prompt(self, res, facilities_text, profile, icon, pinfo):
        """單一房屋有嫌惡設施的提示詞"""
        name = list(res["houses_data"].keys())[0]
        h = res["houses_data"][name]
        cnt = res["facility_counts"].get(name, 0)
        focus = pinfo.get("prompt_focus", [])
        
        # 計算嫌惡設施數量
        nuisance_count = 0
        if res.get('nuisance_data'):
            nuisance_count = len(res['nuisance_data'].get(name, []))
        
        return f"""
你是一位專業的房地產分析師，請以「{icon} {profile}」的身份，對以下房屋進行生活機能分析與評分。**此分析包含嫌惡設施評估**。

【買家類型】
{profile} - {pinfo.get('description', '')}
重點關注：{', '.join(focus)}

【房屋資訊】
- 標題：{h['title']}
- 地址：{h['address']}

【搜尋條件】
- 半徑：{res['radius']} 公尺
- 分析類別：{', '.join(res['selected_categories'])}
- 關鍵字：{res.get('keyword', '') if res.get('keyword') else '無'}

【周邊設施統計】
- 總數量：{cnt} 個設施（包含 {nuisance_count} 處嫌惡設施）

【完整設施清單】（⚠️ 標記為嫌惡設施）
{facilities_text}

請提供以下分析，**特別注意嫌惡設施的影響**：

1. **綜合評分**（1-10分）
   請根據{profile}的需求給出具體分數，並詳細說明評分依據：
   - 交通便利性（滿分3分）：根據周邊交通設施數量和距離評分
   - 日常採買（滿分3分）：根據超市、便利商店等設施評分
   - 生活品質（滿分2分）：根據公園、餐廳等設施評分，**會因嫌惡設施而扣分**
   - 特殊需求（滿分2分）：根據{profile}的關注重點評分
   - **嫌惡設施扣分**：根據數量、距離和類型，從總分中扣除（最高扣3分）
   
   請列出每項得分、扣分項目和最終計算方式。

2. **主要優點**（3-5點）
   對{profile}來說最實用的設施和生活機能，請具體說明每個優點如何提升生活品質，並引用具體的設施名稱和距離。

3. **主要缺點**（3-5點）
   對{profile}來說的不足之處或潛在問題，**必須包含嫌惡設施的影響**，請具體說明：
   - 每個嫌惡設施的類型、距離和潛在影響
   - 對日常生活、居住品質的具體影響
   - 對房價的可能影響

4. **生活便利性預測**（需考慮嫌惡設施）
   - 平日通勤/上班日：預測平日的生活便利性
   - 假日生活：預測週末的生活樣貌（考慮嫌惡設施的影響）
   - 緊急情況（醫療、採買）：評估緊急情況下的應變能力

5. **未來發展潛力**
   根據周邊設施和區域特性，預測這個地點未來3-5年的發展潛力，**並評估嫌惡設施是否可能搬遷或改善**。

6. **購買建議**
   - 是否適合{profile}購買？**考慮嫌惡設施的影響**
   - 合理的價格區間建議（**因嫌惡設施應有適當折價**）
   - 什麼時候是最佳購買時機？

請用專業、客觀的角度分析，給出實用的建議，並盡量引用具體的設施名稱和距離來支持你的觀點。
"""

    def _build_multi_without_nuisance_prompt(self, res, facilities_text, profile, icon, pinfo):
        """多房屋比較無嫌惡設施的提示詞"""
        houses_data = res["houses_data"]
        counts = res["facility_counts"]
        focus = pinfo.get("prompt_focus", [])
        
        house_list = "\n".join([f"- {n}：{h['title'][:30]}..." for n, h in houses_data.items()])
        comparison_rows = [f"  {name}：{cnt} 個設施" for name, cnt in counts.items()]
        comparison_text = "\n".join(comparison_rows)
        
        return f"""
你是一位專業的房地產分析師，請比較以下{len(houses_data)}間房屋，並以「{icon} {profile}」的身份給出建議。

【買家類型】
{profile} - {pinfo.get('description', '')}
重點關注：{', '.join(focus)}

【候選房屋】
{house_list}

【各房屋設施數量】
{comparison_text}

【完整設施清單】
{facilities_text}

請提供以下分析：

1. **綜合排名**（1-{len(houses_data)}名）
   請將這{len(houses_data)}間房屋從最適合到最不適合排序，並詳細說明排名依據。

2. **各房屋評分與計算方式**（1-10分）
   {chr(10).join([f'   - {name}：___分\n     交通便利性(3):___ 日常採買(3):___ 生活品質(2):___ 特殊需求(2):___' for name in houses_data.keys()])}

3. **優缺點比較表**
   | 項目 | {' | '.join(houses_data.keys())} |
   |------|{'|'.join(['---' for _ in houses_data])}|
   | 交通便利性 | |{' |'.join([' ' for _ in houses_data])}|
   | 日常採買 | |{' |'.join([' ' for _ in houses_data])}|
   | 生活品質 | |{' |'.join([' ' for _ in houses_data])}|
   | 價格效益 | |{' |'.join([' ' for _ in houses_data])}|
   | 未來潛力 | |{' |'.join([' ' for _ in houses_data])}|

4. **各房屋詳細分析**
   {chr(10).join([f'   **{name}**：\n   - 優勢（引用具體設施）：\n   - 劣勢（缺少的設施）：\n   - 適合{profile}的程度：' for name in houses_data.keys()])}

5. **最終推薦**
   - **首選**：房屋___，因為...
   - **備選**：房屋___，當首選有問題時
   - **不建議**：房屋___，因為...

6. **購買時機建議**
   現在是否適合購買？應該等待還是立即行動？預期的價格趨勢如何？

請用專業、客觀的角度分析，給出實用的比較建議，並盡量引用具體的設施名稱和距離來支持你的觀點。
"""

    def _build_multi_with_nuisance_prompt(self, res, facilities_text, profile, icon, pinfo):
        """多房屋比較有嫌惡設施的提示詞"""
        houses_data = res["houses_data"]
        counts = res["facility_counts"]
        focus = pinfo.get("prompt_focus", [])
        
        house_list = "\n".join([f"- {n}：{h['title'][:30]}..." for n, h in houses_data.items()])
        comparison_rows = [f"  {name}：{cnt} 個設施" for name, cnt in counts.items()]
        comparison_text = "\n".join(comparison_rows)
        
        # 建立各房屋嫌惡設施比較
        nuisance_comparison = "\n【各房屋嫌惡設施數量】\n"
        nuisance_counts = {}
        if res.get('nuisance_data'):
            for name in houses_data.keys():
                nuisance_counts[name] = len(res['nuisance_data'].get(name, []))
                nuisance_comparison += f"- {name}：{nuisance_counts[name]} 處嫌惡設施\n"
        
        return f"""
你是一位專業的房地產分析師，請比較以下{len(houses_data)}間房屋，並以「{icon} {profile}」的身份給出建議。**此分析包含嫌惡設施評估**。

【買家類型】
{profile} - {pinfo.get('description', '')}
重點關注：{', '.join(focus)}

【候選房屋】
{house_list}

【各房屋設施數量】
{comparison_text}
{nuisance_comparison}

【完整設施清單】（⚠️ 標記為嫌惡設施）
{facilities_text}

請提供以下分析，**特別注意嫌惡設施的影響**：

1. **綜合排名**（1-{len(houses_data)}名）
   請將這{len(houses_data)}間房屋從最適合到最不適合排序，**優先考慮嫌惡設施較少的房屋**，並詳細說明排名依據。

2. **各房屋評分與計算方式**（1-10分）
   {chr(10).join([f'   - {name}：___分\n     交通便利性(3):___ 日常採買(3):___ 生活品質(2):___ 特殊需求(2):___ 嫌惡設施扣分(最高-3):___' for name in houses_data.keys()])}

3. **優缺點比較表**
   | 項目 | {' | '.join(houses_data.keys())} |
   |------|{'|'.join(['---' for _ in houses_data])}|
   | 交通便利性 | |{' |'.join([' ' for _ in houses_data])}|
   | 日常採買 | |{' |'.join([' ' for _ in houses_data])}|
   | 生活品質 | |{' |'.join([' ' for _ in houses_data])}|
   | 價格效益 | |{' |'.join([' ' for _ in houses_data])}|
   | 未來潛力 | |{' |'.join([' ' for _ in houses_data])}|
   | 嫌惡設施影響 | |{' |'.join([str(nuisance_counts.get(name, 0)) + '處' for name in houses_data.keys()])}|

4. **各房屋詳細分析**
   {chr(10).join([f'   **{name}**：\n   - 優勢（引用具體設施）：\n   - 劣勢（包含嫌惡設施）：\n   - 嫌惡設施影響：{nuisance_counts.get(name, 0)}處\n   - 適合{profile}的程度：' for name in houses_data.keys()])}

5. **最終推薦**
   - **首選**：房屋___，因為...（考慮嫌惡設施的影響）
   - **備選**：房屋___，當首選有問題時
   - **不建議**：房屋___，因為...（可能因嫌惡設施過多）

6. **購買時機建議**
   現在是否適合購買？應該等待還是立即行動？預期的價格趨勢如何？**請考慮嫌惡設施對房價的長期影響**。

請用專業、客觀的角度分析，給出實用的比較建議，並盡量引用具體的設施名稱和距離來支持你的觀點。
"""
    
    def _call_gemini(self, prompt):
        """呼叫 Gemini API"""
        now = time.time()
        if now - st.session_state.get("last_gemini_call", 0) < 30:
            st.warning("⏳ AI 分析請等待30秒後再試")
            return
        
        st.session_state.last_gemini_call = now
        
        with st.spinner("🧠 AI 分析中..."):
            try:
                import google.generativeai as genai
                key = st.session_state.get("GEMINI_KEY", "")
                if not key:
                    st.error("❌ 請在側邊欄填入 Gemini Key")
                    return
                
                genai.configure(api_key=key)
                model = genai.GenerativeModel("gemini-2.0-flash")
                resp = model.generate_content(prompt)
                
                st.session_state.gemini_result = resp.text
                st.session_state.used_prompt = prompt
                st.rerun()
            except Exception as e:
                st.error(f"❌ Gemini API 錯誤：{e}")
    
    def _format_all_facilities_for_prompt(self, res):
        """格式化所有設施資料供提示詞使用（全部列出，無省略）"""
        df = res.get("facilities_table", pd.DataFrame())
        if df.empty:
            return "無周邊設施資料"
        
        result = "\n【完整周邊設施清單】\n"
        result += "=" * 60 + "\n"
        
        # 按房屋分組
        for house_name in df['房屋'].unique():
            house_df = df[df['房屋'] == house_name]
            result += f"\n🏠 {house_name} 周邊設施（共 {len(house_df)} 個）：\n"
            result += "-" * 50 + "\n"
            
            # 按距離排序
            house_df_sorted = house_df.sort_values('距離(公尺)')
            
            # 列出所有設施
            for i, row in house_df_sorted.iterrows():
                # 標記嫌惡設施
                is_nuisance = " ⚠️" if row['設施子類別'] in [n for n in NUISANCE_TYPES.keys()] else ""
                result += f"  {i+1}. {row['設施名稱']} ({row['設施子類別']}){is_nuisance} - {row['距離(公尺)']}公尺\n"
            
            # 統計摘要
            result += f"\n  📊 統計摘要：\n"
            cat_summary = house_df.groupby('設施子類別').size().sort_values(ascending=False)
            for cat, count in cat_summary.items():
                is_nuisance_cat = " ⚠️" if cat in [n for n in NUISANCE_TYPES.keys()] else ""
                result += f"     - {cat}{is_nuisance_cat}: {count}個\n"
            
            result += "\n"
        
        return result
    
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
