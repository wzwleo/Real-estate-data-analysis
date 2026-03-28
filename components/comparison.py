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
from datetime import datetime, timedelta
import io
import re
import zipfile
import pytz

# 修正匯入路徑
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

try:
    from config import CATEGORY_COLORS, DEFAULT_RADIUS
    from components.place_types import PLACE_TYPES, CHINESE_TO_CATEGORY, NUISANCE_TYPES, IMPACT_TYPES
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
    IMPACT_TYPES = {}

# 設定台灣時區
try:
    TZ_TAIWAN = pytz.timezone('Asia/Taipei')
except:
    TZ_TAIWAN = None

def get_taiwan_time():
    """取得台灣時間"""
    if TZ_TAIWAN:
        return datetime.now(TZ_TAIWAN).strftime('%Y-%m-%d %H:%M:%S')
    else:
        utc_now = datetime.utcnow()
        taiwan_time = utc_now + timedelta(hours=8)
        return taiwan_time.strftime('%Y-%m-%d %H:%M:%S')


class ComparisonAnalyzer:
    """房屋分析器 - 支援單一分析和多房屋比較"""
    
    def __init__(self):
        self._init_session_state()
        # 建立影響類型到嫌惡設施的映射
        self._impact_to_nuisances = self._build_impact_mapping()
    
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
            'last_selected_subtypes': {},
            'custom_impact_weights': {},  # 使用者自訂的影響類型權重
            'facility_selection_version': 0  # 版本號，用於強制刷新設施選擇
        }
        for key, value in defaults.items():
            if key not in st.session_state:
                st.session_state[key] = value
    
    def _build_impact_mapping(self):
        """建立影響類型到嫌惡設施的映射"""
        mapping = {}
        for name, info in NUISANCE_TYPES.items():
            for impact in info.get("impacts", []):
                if impact not in mapping:
                    mapping[impact] = []
                mapping[impact].append(name)
        return mapping
    
    # ==================== 深度分析輔助函式 ====================
    
    def _get_depth_analysis_by_title(self, title):
        """根據房屋標題從 ai_results_summary 取得深度分析資料"""
        if 'ai_results_summary' not in st.session_state:
            return None
        
        for item in st.session_state.ai_results_summary:
            if item['basic_info'].get('標題') == title:
                return item
        return None
    
    def _format_depth_summary(self, depth_item):
        """把深度分析數據轉成簡潔文字"""
        if not depth_item:
            return ""
        
        try:
            data = depth_item['analysis_data']
            
            price = data['price_data']['目標房屋']['總價(萬)']
            price_pct = data['price_data']['價格分布']['價格百分位']
            vs_median = data['price_data']['價格分布']['與中位數差距(萬)']
            price_direction = "低" if vs_median < 0 else "高"
            
            usage = data['space_data']['目標房屋']['空間使用率']
            usage_pct = data['space_data']['坪數分布']['使用率百分位']
            
            age = data['age_data']['目標房屋']['屋齡(年)']
            age_cat = data['age_data']['屋齡分布']['屋齡評估']
            age_pct = data['age_data']['屋齡分布']['屋齡百分位']
            
            floor = data['floor_data']['目標房屋']['樓層']
            floor_cat = data['floor_data']['樓層分布']['樓層評估']
            floor_pct = data['floor_data']['樓層分布']['樓層百分位']
            
            layout = data['layout_data']['目標房屋']['格局']
            layout_rank = data['layout_data']['格局排名'].get('格局資料量排名', '未知')
            layout_pct = data['layout_data']['格局排名'].get('相同格局占比(%)', 0)
            
            return f"""
【🏠 房屋深度分析】
💰 價格：{price}萬（低於{price_pct:.0f}%的房屋，比市場中位數{price_direction}{abs(vs_median)}萬）
📐 空間：使用率{usage:.0%}（高於{usage_pct:.0f}%的房屋）
🕰 屋齡：{age}年（{age_cat}，比{100-age_pct:.0f}%的房屋新）
🏢 樓層：{floor}樓（{floor_cat}，比{floor_pct:.0f}%的房屋{"低" if floor_pct < 50 else "高"}）
🛋 格局：{layout}（市場排名第{layout_rank}，佔{layout_pct:.1f}%）
"""
        except Exception as e:
            return ""
    
    # ==================== 買家類型定義 ====================
    
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
    
    # ==================== 嫌惡設施權重設定 ====================
    
    def _render_impact_weight_settings(self):
        """渲染影響類型權重設定介面"""
        st.markdown("#### ⚙️ 嫌惡設施影響權重設定")
        st.markdown("請選擇您最在意的影響類型，並設定權重（1-10分）")
        
        current_weights = st.session_state.get('custom_impact_weights', {})
        
        st.markdown("---")
        st.info("💡 **說明**：勾選您重視的影響類型，並設定權重（1-10分）。\n\n權重越高，相關嫌惡設施的風險分數越高。")
        
        st.markdown("#### 📋 選擇您重視的影響類型並設定權重")
        
        cols = st.columns(3)
        impact_list = list(IMPACT_TYPES.items())
        per_col = len(impact_list) // 3 + (1 if len(impact_list) % 3 > 0 else 0)
        
        new_weights = {}
        
        for col_idx in range(3):
            with cols[col_idx]:
                start_idx = col_idx * per_col
                end_idx = min((col_idx + 1) * per_col, len(impact_list))
                
                for i in range(start_idx, end_idx):
                    impact_name, impact_info = impact_list[i]
                    description = impact_info["description"]
                    color = impact_info["color"]
                    
                    is_selected = impact_name in current_weights
                    default_weight = current_weights.get(impact_name, 5)
                    
                    with st.container():
                        st.markdown(f"""
                        <div style="border-left:4px solid {color}; padding-left:12px; margin-bottom:8px;">
                            <span style="font-weight:bold; font-size:14px;">{impact_name}</span>
                            <span style="font-size:10px; color:#888;">{description[:30]}...</span>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        col_select, col_weight = st.columns([1, 2])
                        with col_select:
                            selected = st.checkbox("重視", key=f"select_{impact_name}", value=is_selected)
                        with col_weight:
                            if selected:
                                weight = st.slider(
                                    "權重",
                                    min_value=1,
                                    max_value=10,
                                    value=int(default_weight),
                                    step=1,
                                    key=f"weight_{impact_name}",
                                    label_visibility="collapsed"
                                )
                                new_weights[impact_name] = weight
                            else:
                                st.write("─")
                        
                        st.markdown("---")
        
        if new_weights:
            st.markdown("#### 📊 您設定的權重")
            sorted_weights = sorted(new_weights.items(), key=lambda x: x[1], reverse=True)
            weight_cols = st.columns(3)
            for idx, (impact, weight) in enumerate(sorted_weights):
                with weight_cols[idx % 3]:
                    st.markdown(f"**{impact}**：{weight} 分")
            
            with st.expander("🔍 查看受影響的嫌惡設施", expanded=False):
                for impact, weight in sorted_weights:
                    if impact in self._impact_to_nuisances:
                        nuisances = self._impact_to_nuisances[impact]
                        st.markdown(f"**{impact} (權重 {weight})** 影響以下設施：")
                        for n in nuisances:
                            st.markdown(f"  - {n}")
                        st.markdown("---")
        
        if st.button("✅ 套用權重設定", use_container_width=True, key="apply_weights"):
            st.session_state.custom_impact_weights = new_weights
            st.success(f"✅ 已儲存 {len(new_weights)} 項權重設定！")
            st.rerun()
        
        if st.button("🔄 重置所有權重", use_container_width=True, key="reset_weights"):
            st.session_state.custom_impact_weights = {}
            st.success("✅ 已重置所有權重")
            st.rerun()
        
        st.markdown("---")
    
    def _calculate_base_score(self, nuisance_name):
        """計算嫌惡設施的基礎分數（不考慮距離）"""
        if nuisance_name not in NUISANCE_TYPES:
            return 0
        
        nuisance_info = NUISANCE_TYPES[nuisance_name]
        impacts = nuisance_info.get("impacts", [])
        
        custom_weights = st.session_state.get('custom_impact_weights', {})
        
        if not custom_weights:
            return 0
        
        total_weight = 0
        for impact in impacts:
            weight = custom_weights.get(impact, 0)
            total_weight += weight
        
        return total_weight
    
    def _calculate_final_score(self, base_score, distance, same_type_count):
        """計算嫌惡設施的最終風險分數"""
        if distance <= 300:
            distance_factor = 1.0
        elif distance <= 600:
            distance_factor = 0.8
        elif distance <= 900:
            distance_factor = 0.5
        else:
            distance_factor = 0.3
        
        facility_score = base_score * distance_factor
        
        quantity_factor = 1 + (same_type_count - 1) * 0.1
        quantity_factor = min(quantity_factor, 1.5)
        
        return facility_score * quantity_factor
    
    def _render_nuisance_selection_with_weights(self):
        """渲染嫌惡設施選擇"""
        selected = []
        
        st.markdown("#### 選擇嫌惡設施類型（可複選）")
        
        with st.expander("⚙️ 進階設定 - 調整嫌惡設施權重", expanded=False):
            self._render_impact_weight_settings()
        
        st.markdown("---")
        st.markdown("#### 選擇要分析的嫌惡設施")
        
        facility_base_scores = {}
        for name in NUISANCE_TYPES.keys():
            base_score = self._calculate_base_score(name)
            if base_score > 0:
                facility_base_scores[name] = base_score
        
        sorted_facilities = sorted(facility_base_scores.items(), key=lambda x: x[1], reverse=True)
        
        if not sorted_facilities:
            st.info("👆 請先設定權重，才會顯示可選擇的嫌惡設施")
            return selected
        
        cols = st.columns(2)
        items = sorted_facilities
        mid = len(items) // 2 + len(items) % 2
        
        for col_idx, column in enumerate(cols):
            with column:
                start_idx = col_idx * mid
                end_idx = min((col_idx + 1) * mid, len(items))
                
                for i in range(start_idx, end_idx):
                    nuisance_name, base_score = items[i]
                    nuisance_info = NUISANCE_TYPES[nuisance_name]
                    color = nuisance_info.get("color", "#dc3545")
                    impacts = nuisance_info.get("impacts", [])
                    
                    st.markdown(f"""
                    <div style="border-left:4px solid {color}; padding-left:8px; margin-bottom:15px;">
                        <span style="font-weight:bold; font-size:16px;">{nuisance_name}</span>
                        <span style="font-size:12px; margin-left:8px;">基礎分數: {base_score}分</span>
                        <div style="font-size:11px; color:#666; margin-top:4px;">影響: {', '.join(impacts)}</div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    if st.checkbox(" ", key=f"nuisance_weight_{i}", label_visibility="collapsed"):
                        selected.append(nuisance_name)
        
        if selected:
            st.success(f"✅ 已選擇 {len(selected)} 類嫌惡設施")
        else:
            st.info("👆 請選擇要分析的嫌惡設施類型")
        
        return selected
    
    # ==================== 下載功能 ====================
    
    def _generate_single_analysis_zip(self, name, analysis):
        """生成單一分析的 Excel 和 TXT 壓縮檔"""
        zip_buffer = io.BytesIO()
        
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            df = analysis.get('facilities_table', pd.DataFrame())
            if not df.empty:
                excel_buffer = io.BytesIO()
                with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                    df_copy = df.copy()
                    df_copy['分析名稱'] = name
                    df_copy['買家類型'] = analysis.get('buyer_profile', '未知')
                    df_copy['分析時間'] = analysis.get('timestamp', '未知')
                    
                    column_order = ['分析名稱', '買家類型', '分析時間', '房屋', '設施名稱', '設施子類別', '距離(公尺)']
                    if '風險分數' in df_copy.columns:
                        column_order.append('風險分數')
                    available_cols = [col for col in column_order if col in df_copy.columns]
                    df_copy = df_copy[available_cols]
                    df_copy.to_excel(writer, sheet_name='設施清單', index=False)
                    
                    summary = pd.DataFrame([{
                        '分析名稱': name,
                        '買家類型': analysis.get('buyer_profile', '未知'),
                        '分析時間': analysis.get('timestamp', '未知'),
                        '分析模式': analysis.get('analysis_mode', ''),
                        '搜尋半徑(公尺)': analysis.get('radius', 0),
                        '總設施數': len(df),
                        '包含嫌惡設施': '是' if analysis.get('include_nuisance', False) else '否',
                        '嫌惡設施風險分數': analysis.get('nuisance_scores', {}).get(name, 0) if analysis.get('include_nuisance', False) else 0
                    }])
                    summary.to_excel(writer, sheet_name='分析摘要', index=False)
                
                excel_buffer.seek(0)
                safe_name = re.sub(r'[\\/*?:"<>|]', "", name)[:30]
                zip_file.writestr(f"{safe_name}_設施清單_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx", excel_buffer.getvalue())
            
            txt_content = self._generate_single_txt_report(name, analysis)
            safe_name = re.sub(r'[\\/*?:"<>|]', "", name)[:30]
            zip_file.writestr(f"{safe_name}_分析報告_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt", txt_content.encode('utf-8'))
        
        zip_buffer.seek(0)
        return zip_buffer.getvalue()
    
    def _generate_single_txt_report(self, name, analysis):
        """生成單一分析的 TXT 報告"""
        txt_lines = []
        
        txt_lines.append("=" * 60)
        txt_lines.append(f"房屋分析報告 - {name}")
        txt_lines.append(f"報告生成時間：{get_taiwan_time()}")
        txt_lines.append("=" * 60)
        txt_lines.append("")
        
        txt_lines.append(f"【分析】{name}")
        txt_lines.append("-" * 40)
        
        profile = analysis.get('buyer_profile', '未知')
        timestamp = analysis.get('timestamp', '未知')
        mode = analysis.get('analysis_mode', '')
        include_nuisance = analysis.get('include_nuisance', False)
        radius = analysis.get('radius', 0)
        
        txt_lines.append(f"買家類型：{profile}")
        txt_lines.append(f"分析時間：{timestamp}")
        txt_lines.append(f"分析模式：{mode}")
        txt_lines.append(f"搜尋半徑：{radius} 公尺")
        if include_nuisance:
            nuisance_scores = analysis.get('nuisance_scores', {})
            score = nuisance_scores.get(name, 0)
            txt_lines.append(f"嫌惡設施風險分數：{score} 分")
        txt_lines.append("")
        
        houses_data = analysis.get('houses_data', {})
        for h_name, h_info in houses_data.items():
            txt_lines.append(f"房屋：{h_name}")
            txt_lines.append(f"  標題：{h_info.get('title', '未知')}")
            txt_lines.append(f"  地址：{h_info.get('address', '未知')}")
        txt_lines.append("")
        
        counts = analysis.get('facility_counts', {})
        txt_lines.append("設施統計：")
        for h_name, count in counts.items():
            txt_lines.append(f"  {h_name}：{count} 個設施")
        txt_lines.append("")
        
        df = analysis.get('facilities_table', pd.DataFrame())
        if not df.empty:
            txt_lines.append("設施清單：")
            txt_lines.append("-" * 50)
            
            df_sorted = df.sort_values('距離(公尺)')
            for idx, row in df_sorted.iterrows():
                is_nuisance = " ⚠️" if row['主要類別'] == "嫌惡設施" else ""
                score_text = f" [風險:{row['風險分數']}分]" if '風險分數' in row and row['風險分數'] > 0 else ""
                txt_lines.append(f"  • {row['設施名稱']} ({row['設施子類別']}){is_nuisance}{score_text} - {row['距離(公尺)']}公尺")
            
            txt_lines.append("")
        
        if 'gemini_result' in analysis:
            txt_lines.append("AI 分析報告：")
            txt_lines.append("-" * 40)
            txt_lines.append(analysis['gemini_result'])
            txt_lines.append("")
        
        txt_lines.append("=" * 60)
        txt_lines.append("")
        
        return "\n".join(txt_lines)
    
    # ==================== 主要渲染方法 ====================
    
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
                        
                        col1, col2 = st.columns([4, 1])
                        with col1:
                            btn_label = f"{icon} {name[:20]}... {profile} | {timestamp}"
                            if include_nuisance:
                                btn_label = "⚠️ " + btn_label
                            
                            if name == st.session_state.current_analysis_name:
                                btn_label = f"👉 {btn_label}"
                            
                            if st.button(btn_label, key=f"saved_{name}", use_container_width=True):
                                st.session_state.current_analysis_name = name
                                st.rerun()
                        
                        with col2:
                            if st.button("📥", key=f"download_{name}", help="下載此分析"):
                                with st.spinner("生成報告中..."):
                                    zip_data = self._generate_single_analysis_zip(name, analysis)
                                    if zip_data:
                                        b64 = base64.b64encode(zip_data).decode()
                                        safe_name = re.sub(r'[\\/*?:"<>|]', "", name)[:30]
                                        filename = f"{safe_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
                                        href = f'<a href="data:application/zip;base64,{b64}" download="{filename}">✅ 點此下載</a>'
                                        st.markdown(href, unsafe_allow_html=True)
                    
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
        """渲染生活機能分析"""
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
                    subs = self._auto_select_subtypes(profile_name)
                    st.session_state.auto_selected_subtypes = subs
                    st.session_state.last_selected_subtypes = subs.copy()
                    st.session_state.suggested_radius = profile_info.get("radius", DEFAULT_RADIUS)
                    
                    # 增加版本號，強制刷新所有 checkbox
                    st.session_state.facility_selection_version += 1
                    
                    st.rerun()
        
        current_profile = st.session_state.get('buyer_profile')
        if not current_profile:
            st.info("👆 請先選擇買家類型")
            return
        
        profile_info = profiles[current_profile]
        st.success(f"✅ 當前選擇：**{profile_info['icon']} {current_profile}**")
        st.markdown("---")
        
        st.markdown("### 🏠 步驟2：選擇要分析的房屋")
        
        mode = st.radio("選擇分析模式", ["單一房屋分析", "多房屋比較"], horizontal=True, key="life_mode")
        st.session_state.analysis_mode = mode
        
        options = fav_df['標題'] + " | " + fav_df['地址']
        selected = []
        
        if mode == "單一房屋分析":
            choice = st.selectbox("選擇要分析的房屋", options, key="life_single_select")
            if choice:
                selected = [choice]
        else:
            default = options[:min(2, len(options))] if len(options) >= 1 else []
            selected = st.multiselect("選擇要比較的房屋", options, default=default, key="life_multi_select")
        
        if not selected:
            return
        
        st.session_state.selected_houses = selected
        st.markdown("---")
        
        st.markdown("### ⚙️ 步驟3：分析設定")
        
        suggest_r = st.session_state.get('suggested_radius', DEFAULT_RADIUS)
        radius = st.slider(f"搜尋半徑（{profile_info['icon']} 建議：{suggest_r}公尺）", 
                          100, 2000, suggest_r, 100, key="life_radius")
        
        keyword = st.text_input("額外關鍵字搜尋（選填）", key="life_keyword", placeholder="例如：公園、健身房")
        
        st.markdown("---")
        st.subheader("🔍 步驟4：選擇生活機能設施")
        
        auto_subs = st.session_state.get('auto_selected_subtypes', {})
        
        if auto_subs:
            total = sum(len(set(v)) for v in auto_subs.values())
            st.info(f"📌 **{current_profile} 推薦設施**：已自動選擇 {total} 種設施")
        
        selected_subs = self._render_all_facilities_selection(auto_subs)
        
        if not selected_subs:
            st.warning("⚠️ 請至少選擇一個生活機能設施")
            return
        
        st.session_state.last_selected_subtypes = selected_subs
        
        st.markdown("---")
        st.subheader("⚠️ 嫌惡設施分析（選填）")
        st.markdown("勾選後可自由選擇要分析的嫌惡設施類型，並可調整各類型的權重")
        
        include_nuisance = st.checkbox("加入嫌惡設施分析", value=False)
        
        selected_nuisances = []
        if include_nuisance:
            selected_nuisances = self._render_nuisance_selection_with_weights()
            st.session_state.selected_nuisances = selected_nuisances
        
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
    
    def _render_all_facilities_selection(self, preset_subtypes=None):
        """渲染所有設施選擇 - 使用版本號強制刷新"""
        selected_subs = {}
        preset_subs = preset_subtypes or {}
        
        st.markdown("#### 選擇設施類型")
        
        # 獲取當前版本號
        version = st.session_state.get('facility_selection_version', 0)
        
        all_cats = list(PLACE_TYPES.keys())
        current_profile = st.session_state.get('buyer_profile', '')
        profiles = self._get_buyer_profiles()
        
        for cat in all_cats:
            with st.expander(f"📁 {cat}", expanded=True):
                # 顯示此類別已選擇數量
                current_selected_count = len(st.session_state.last_selected_subtypes.get(cat, []))
                if current_selected_count > 0:
                    st.caption(f"✅ 此類別已選擇 {current_selected_count} 種")
                
                # 推薦提示
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
                
                # 預設選擇（來自買家類型推薦）
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
                            if name in default_list:
                                default_val = True
                            
                            # 在 key 中加入版本號，確保切換買家類型時強制刷新
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
                                    cb = st.checkbox(" ", key=f"sub_{cat}_{idx}_v{version}", label_visibility="collapsed", value=default_val)
                                else:
                                    cb = st.checkbox(name, key=f"sub_{cat}_{idx}_v{version}", value=default_val)
                                
                                if cb:
                                    if cat not in selected_subs:
                                        selected_subs[cat] = []
                                    selected_subs[cat].append(name)
                
                if cat in selected_subs:
                    st.caption(f"✅ 已選擇 {len(set(selected_subs[cat]))} 種")
        
        # 移除重複的選擇
        for cat in selected_subs:
            selected_subs[cat] = list(dict.fromkeys(selected_subs[cat]))
        
        return selected_subs
    
    def _validate_inputs(self, houses, cats):
        """驗證輸入"""
        if not self._get_server_key(): 
            return "❌ 請填寫 Server Key"
        if not self._get_gemini_key(): 
            return "❌ 請填寫 Gemini Key"
        if not cats: 
            return "⚠️ 請至少選擇一個生活機能類別"
        if not houses: 
            return "⚠️ 請選擇房屋"
        if not st.session_state.get('buyer_profile'): 
            return "⚠️ 請先選擇買家類型"
        return "OK"
    
    def _start_analysis(self, mode, houses, radius, keyword, cats, subs, fav_df, profile, include_nuisance=False, selected_nuisances=None):
        """開始分析"""
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
            if k in st.session_state: 
                del st.session_state[k]
    
    def _clear_all(self):
        """全部清除"""
        keys = ['analysis_settings', 'analysis_results', 'analysis_in_progress', 'gemini_result',
                'custom_prompt', 'used_prompt', 'selected_houses', 'buyer_profile',
                'auto_selected_subtypes', 'suggested_radius',
                'analysis_completed', 'saved_analyses', 'current_analysis_name',
                'last_selected_subtypes']
        for k in keys:
            if k in st.session_state: 
                del st.session_state[k]
    
    def _execute_analysis(self):
        """執行分析核心"""
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
                nuisance_scores = {}
                if s.get("include_nuisance", False) and s.get("selected_nuisances"):
                    st.write("🔍 步驟 2.5/4：查詢周邊嫌惡設施...")
                    
                    base_scores = {}
                    for nuisance in s["selected_nuisances"]:
                        base_scores[nuisance] = self._calculate_base_score(nuisance)
                    
                    for idx, (name, info) in enumerate(houses_data.items()):
                        st.write(f"   - 查詢 {name} 周邊嫌惡設施...")
                        
                        all_nuisances = []
                        for nuisance in s["selected_nuisances"]:
                            nuisances = self._query_nuisances_no_progress(
                                info["lat"], info["lng"], s["server"],
                                [nuisance], s["radius"]
                            )
                            all_nuisances.extend(nuisances)
                        
                        nuisance_data[name] = all_nuisances
                        
                        if name not in places_data:
                            places_data[name] = []
                        
                        st.write(f"     找到 {len(all_nuisances)} 處嫌惡設施")
                        
                        type_counts = {}
                        for n in all_nuisances:
                            n_type = n[0]
                            type_counts[n_type] = type_counts.get(n_type, 0) + 1
                        
                        total_score = 0
                        for n in all_nuisances:
                            n_type = n[0]
                            base_score = base_scores.get(n_type, 0)
                            if base_score > 0:
                                distance = n[5]
                                same_type_count = type_counts.get(n_type, 1)
                                final_score = self._calculate_final_score(base_score, distance, same_type_count)
                                total_score += final_score
                                places_data[name].append(("嫌惡設施", n[1], n[2], n[3], n[4], n[5], n[6], final_score))
                        
                        nuisance_scores[name] = round(total_score, 1)
                        st.write(f"     風險評分：{nuisance_scores[name]} 分")
                
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
                    "timestamp": get_taiwan_time(),
                    "include_nuisance": s.get("include_nuisance", False),
                    "nuisance_data": nuisance_data if s.get("include_nuisance", False) else None,
                    "nuisance_scores": nuisance_scores if s.get("include_nuisance", False) else None
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
        """查詢設施"""
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
    
    def _query_nuisances_no_progress(self, lat, lng, api_key, nuisances, radius):
        """查詢嫌惡設施"""
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
            except:
                continue
        
        results.sort(key=lambda x: x[5])
        return results
    
    def _search_google_places_chinese(self, lat, lng, api_key, keyword, radius):
        """Google Places 搜尋"""
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
                row = {
                    "房屋": h_name,
                    "房屋標題": h_info['title'][:50],
                    "房屋地址": h_info['address'],
                    "設施名稱": p[2],
                    "設施子類別": p[1],
                    "主要類別": p[0],
                    "距離(公尺)": p[5],
                    "經度": p[4],
                    "緯度": p[3],
                    "place_id": p[6]
                }
                if len(p) > 7:
                    row["風險分數"] = p[7]
                rows.append(row)
        return pd.DataFrame(rows)
    
    def _display_analysis_results(self, res):
        """顯示分析結果"""
        if not res:
            return
        
        mode = res["analysis_mode"]
        profile = res.get("buyer_profile", "未指定")
        timestamp = res.get("timestamp", "未知時間")
        include_nuisance = res.get("include_nuisance", False)
        nuisance_scores = res.get("nuisance_scores", {})
        profiles = self._get_buyer_profiles()
        pinfo = profiles.get(profile, {})
        icon = pinfo.get("icon", "👤")
        
        st.markdown(f"### 分析時間：{timestamp}")
        if include_nuisance:
            st.info("⚠️ 此分析包含嫌惡設施評估")
            if nuisance_scores:
                for name, score in nuisance_scores.items():
                    st.markdown(f"{name} 嫌惡設施風險評分：{score} 分")
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
        
        # 設施詳細資料表格
        st.subheader("📋 設施詳細資料")
        
        df = res.get("facilities_table", pd.DataFrame())
        if not df.empty:
            if include_nuisance and '主要類別' in df.columns:
                normal_df = df[df['主要類別'] != "嫌惡設施"].copy()
                nuisance_df = df[df['主要類別'] == "嫌惡設施"].copy()
            else:
                normal_df = df.copy()
                nuisance_df = pd.DataFrame()
            
            if not normal_df.empty:
                with st.expander("✅ 一般設施", expanded=True):
                    st.dataframe(
                        normal_df,
                        use_container_width=True,
                        column_config={
                            "房屋": st.column_config.TextColumn(width="small"),
                            "房屋標題": st.column_config.TextColumn(width="medium"),
                            "房屋地址": st.column_config.TextColumn(width="medium"),
                            "設施名稱": st.column_config.TextColumn(width="large"),
                            "設施子類別": st.column_config.TextColumn(width="small"),
                            "距離(公尺)": st.column_config.NumberColumn(format="%d 公尺"),
                            "place_id": st.column_config.TextColumn("Google地圖", width="small")
                        },
                        hide_index=True
                    )
            
            if not nuisance_df.empty:
                with st.expander("⚠️ 嫌惡設施", expanded=True):
                    st.dataframe(
                        nuisance_df,
                        use_container_width=True,
                        column_config={
                            "房屋": st.column_config.TextColumn(width="small"),
                            "房屋標題": st.column_config.TextColumn(width="medium"),
                            "房屋地址": st.column_config.TextColumn(width="medium"),
                            "設施名稱": st.column_config.TextColumn(width="large"),
                            "設施子類別": st.column_config.TextColumn(width="small"),
                            "距離(公尺)": st.column_config.NumberColumn(format="%d 公尺"),
                            "風險分數": st.column_config.NumberColumn(format="%.1f 分"),
                            "place_id": st.column_config.TextColumn("Google地圖", width="small")
                        },
                        hide_index=True
                    )
        else:
            st.info("📭 無設施資料")
        
        st.markdown("---")
        
        # 設施統計
        st.subheader("📈 設施統計")
        
        if res["num_houses"] == 1:
            self._show_single_stats(res, include_nuisance)
        else:
            self._show_multi_stats(res, include_nuisance)
        
        # 地圖檢視
        self._display_maps(res)
        
        # 全部設施列表
        self._display_facilities_list_with_links(res, include_nuisance)
        
        # AI 智能分析
        self._display_ai_analysis(res)
    
    def _show_single_stats(self, res, include_nuisance=False):
        """單一房屋統計"""
        name = list(res["houses_data"].keys())[0]
        
        df = res.get("facilities_table", pd.DataFrame())
        if df.empty:
            return
        
        if include_nuisance and '主要類別' in df.columns:
            normal_df = df[df['主要類別'] != "嫌惡設施"]
            nuisance_df = df[df['主要類別'] == "嫌惡設施"]
            normal_cnt = len(normal_df)
            nuisance_cnt = len(nuisance_df)
            total_cnt = len(df)
        else:
            normal_df = df
            nuisance_df = pd.DataFrame()
            normal_cnt = len(df)
            nuisance_cnt = 0
            total_cnt = len(df)
        
        cols = st.columns(4)
        with cols[0]:
            st.metric("🏠 總設施", f"{total_cnt} 個")
        with cols[1]:
            st.metric("✅ 一般設施", f"{normal_cnt} 個")
        if include_nuisance:
            with cols[2]:
                st.metric("⚠️ 嫌惡設施", f"{nuisance_cnt} 個", delta_color="inverse")
        
        if normal_cnt > 0:
            normal_dists = normal_df['距離(公尺)'].tolist()
            avg_normal = sum(normal_dists) / len(normal_dists)
            min_normal = min(normal_dists)
            with cols[3] if include_nuisance else cols[2]:
                st.metric("📏 平均距離", f"{avg_normal:.0f} 公尺")
        
        if normal_cnt > 0:
            st.markdown("#### 🏪 一般設施類型分布")
            cat_cnt = Counter(normal_df['設施子類別'].tolist())
            top10 = cat_cnt.most_common(10)
            
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
    
    def _show_multi_stats(self, res, include_nuisance=False):
        """多房屋統計"""
        df = res.get("facilities_table", pd.DataFrame())
        if df.empty:
            return
        
        houses_data = res["houses_data"]
        names = list(houses_data.keys())
        
        if include_nuisance and '主要類別' in df.columns:
            normal_df = df[df['主要類別'] != "嫌惡設施"]
            nuisance_df = df[df['主要類別'] == "嫌惡設施"]
        else:
            normal_df = df.copy()
            nuisance_df = pd.DataFrame()
        
        normal_counts = normal_df.groupby('房屋').size().to_dict()
        nuisance_counts = nuisance_df.groupby('房屋').size().to_dict() if not nuisance_df.empty else {}
        
        for name in names:
            if name not in normal_counts:
                normal_counts[name] = 0
            if name not in nuisance_counts:
                nuisance_counts[name] = 0
        
        cols = st.columns(min(4, len(names)))
        for i, name in enumerate(names):
            with cols[i % len(cols)]:
                total = normal_counts.get(name, 0) + nuisance_counts.get(name, 0)
                normal = normal_counts.get(name, 0)
                nuisance = nuisance_counts.get(name, 0)
                
                st.metric(f"🏠 {name}", f"{total} 個")
                if include_nuisance and nuisance > 0:
                    st.caption(f"✅ {normal} 一般 | ⚠️ {nuisance} 嫌惡")
        
        if len(names) > 1:
            st.markdown("#### 📊 一般設施數量排名")
            data = sorted([(name, normal_counts.get(name, 0)) for name in names], 
                         key=lambda x: x[1], reverse=True)
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
            
            if include_nuisance and any(nuisance_counts.values()):
                st.markdown("#### ⚠️ 嫌惡設施數量排名")
                nuisance_data = sorted([(name, nuisance_counts.get(name, 0)) for name in names], 
                                      key=lambda x: x[1], reverse=True)
                nuisance_chart = {
                    "xAxis": {"type": "category", "data": [x[0] for x in nuisance_data]},
                    "yAxis": {"type": "value"},
                    "series": [{
                        "type": "bar",
                        "data": [x[1] for x in nuisance_data],
                        "itemStyle": {"color": "#dc3545"}
                    }],
                    "tooltip": {"trigger": "axis"}
                }
                st_echarts(nuisance_chart, height="300px")
    
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
            if p[0] == "嫌惡設施":
                color = "#dc3545"
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
                #map {{ height: 500px; width: 100%; }}
                #legend {{
                    background: white; padding: 10px; border: 1px solid #ccc; border-radius: 5px;
                    font-size: 12px; margin: 10px; max-width: 200px; box-shadow: 0 2px 6px rgba(0,0,0,0.1);
                    position: absolute; right: 10px; top: 10px; z-index: 1000;
                }}
                .legend-item {{ display: flex; align-items: center; margin-bottom: 5px; }}
                .legend-color {{ width: 12px; height: 12px; margin-right: 5px; border-radius: 2px; }}
                .info-window {{ padding: 12px; max-width: 260px; }}
                .info-window h5 {{ margin: 0 0 8px 0; color: #333; font-size: 16px; }}
                .info-window p {{ margin: 5px 0; color: #666; }}
                .maps-link {{
                    display: inline-block; margin-top: 10px; padding: 8px 12px;
                    background-color: #1a73e8; color: white !important; text-decoration: none;
                    border-radius: 4px; font-size: 12px; font-weight: 500;
                }}
                .maps-link:hover {{ background-color: #1557b0; }}
            </style>
        </head>
        <body>
            <div id="map"></div>
            <script>
                function initMap() {{
                    var center = {{lat: {lat}, lng: {lng}}};
                    var map = new google.maps.Map(document.getElementById('map'), {{
                        zoom: 16, center: center, mapTypeControl: true, streetViewControl: true, fullscreenControl: true
                    }});
                    var mainMarker = new google.maps.Marker({{
                        position: center, map: map, title: "{title}",
                        icon: {{ url: "http://maps.google.com/mapfiles/ms/icons/red-dot.png", scaledSize: new google.maps.Size(40, 40) }},
                        zIndex: 1000
                    }});
                    var mainInfoContent = '<div class="info-window"><h5>🏠 {title}</h5><p><strong>地址：</strong>{address_str}</p><p><strong>搜尋半徑：</strong>{radius} 公尺</p><p><strong>設施數量：</strong>{len(places)} 個</p></div>';
                    var mainInfoWindow = new google.maps.InfoWindow({{ content: mainInfoContent }});
                    mainMarker.addListener("click", function() {{ mainInfoWindow.open(map, mainMarker); }});
                    var legendDiv = document.createElement('div'); legendDiv.id = 'legend';
                    legendDiv.innerHTML = '<h4 style="margin-top:0; margin-bottom:10px;">設施類別圖例</h4>' + `{legend_html}`;
                    map.controls[google.maps.ControlPosition.RIGHT_TOP].push(legendDiv);
                    var facilities = {facilities_json};
                    facilities.forEach(function(facility) {{
                        var position = {{lat: facility.lat, lng: facility.lng}};
                        var marker = new google.maps.Marker({{
                            position: position, map: map, title: facility.name + " (" + facility.distance + "m)",
                            icon: {{ path: google.maps.SymbolPath.CIRCLE, scale: 8, fillColor: facility.color,
                                    fillOpacity: 0.9, strokeColor: "#FFFFFF", strokeWeight: 2 }},
                            animation: google.maps.Animation.DROP
                        }});
                        var infoContent = '<div class="info-window"><h5>' + facility.name + '</h5><p><span style="color:' + facility.color + '; font-weight:bold;">' + facility.category + ' - ' + facility.subtype + '</span></p><p><strong>距離：</strong>' + facility.distance + ' 公尺</p><a href="' + facility.maps_url + '" target="_blank" class="maps-link">🗺️ 在 Google 地圖中查看</a></div>';
                        var infoWindow = new google.maps.InfoWindow({{ content: infoContent }});
                        marker.addListener("click", function() {{ infoWindow.open(map, marker); }});
                    }});
                    var circle = new google.maps.Circle({{
                        strokeColor: "#FF0000", strokeOpacity: 0.8, strokeWeight: 2,
                        fillColor: "#FF0000", fillOpacity: 0.1, map: map, center: center, radius: {radius}
                    }});
                    setTimeout(function() {{ mainInfoWindow.open(map, mainMarker); }}, 1000);
                }}
                function handleMapError() {{
                    document.getElementById('map').innerHTML = '<div style="padding:20px; text-align:center; color:red;"><h3>❌ 地圖載入失敗</h3><p>請檢查 Google Maps API Key 是否正確</p></div>';
                }}
            </script>
            <script src="https://maps.googleapis.com/maps/api/js?key={browser_key}&callback=initMap" async defer onerror="handleMapError()"></script>
        </body>
        </html>
        """
        
        st.markdown(f"**🗺️ {title} - 周邊設施地圖**")
        if places:
            st.markdown(f"📊 **共找到 {len(places)} 個設施** (搜尋半徑: {radius}公尺)")
        else:
            st.info(f"📭 {title} 周圍半徑 {radius} 公尺內未找到設施")
        
        html(html_content, height=550)
    
    def _display_facilities_list_with_links(self, res, include_nuisance=False):
        """顯示設施列表"""
        st.markdown("---")
        st.subheader("📍 全部設施列表")
        
        df = res.get("facilities_table", pd.DataFrame())
        if df.empty:
            st.info("📭 無設施資料")
            return
        
        if include_nuisance and '主要類別' in df.columns:
            normal_df = df[df['主要類別'] != "嫌惡設施"]
            nuisance_df = df[df['主要類別'] == "嫌惡設施"]
        else:
            normal_df = df
            nuisance_df = pd.DataFrame()
        
        if not normal_df.empty:
            with st.expander("✅ 一般設施", expanded=True):
                for house_name in normal_df['房屋'].unique():
                    house_df = normal_df[normal_df['房屋'] == house_name]
                    st.markdown(f"**🏠 {house_name}** - 共 {len(house_df)} 個設施")
                    
                    for i, row in house_df.iterrows():
                        maps_url = f"https://www.google.com/maps/search/?api=1&query={row['緯度']},{row['經度']}&query_place_id={row['place_id']}"
                        dist = row['距離(公尺)']
                        if dist <= 300:
                            dist_color = "#28a745"; dist_badge = "很近"
                        elif dist <= 600:
                            dist_color = "#ffc107"; dist_badge = "中等"
                        else:
                            dist_color = "#dc3545"; dist_badge = "較遠"
                        
                        col1, col2, col3, col4 = st.columns([5, 2, 2, 2])
                        with col1:
                            st.markdown(f"**{i+1}.** {row['設施名稱']}")
                        with col2:
                            color = CATEGORY_COLORS.get(row['主要類別'], "#666")
                            st.markdown(f'<span style="background-color:{color}20; color:{color}; padding:4px 8px; border-radius:8px; font-size:12px;">{row["設施子類別"]}</span>', unsafe_allow_html=True)
                        with col3:
                            st.markdown(f'<span style="background-color:{dist_color}20; color:{dist_color}; padding:4px 8px; border-radius:8px; font-size:12px;">{dist}公尺 ({dist_badge})</span>', unsafe_allow_html=True)
                        with col4:
                            st.link_button("🗺️ 地圖", maps_url, use_container_width=True)
                        st.divider()
        
        if not nuisance_df.empty:
            with st.expander("⚠️ 嫌惡設施", expanded=True):
                for house_name in nuisance_df['房屋'].unique():
                    house_df = nuisance_df[nuisance_df['房屋'] == house_name]
                    st.markdown(f"**🏠 {house_name}** - 共 {len(house_df)} 個嫌惡設施")
                    
                    for i, row in house_df.iterrows():
                        maps_url = f"https://www.google.com/maps/search/?api=1&query={row['緯度']},{row['經度']}&query_place_id={row['place_id']}"
                        dist = row['距離(公尺)']
                        if dist <= 300:
                            dist_color = "#dc3545"; dist_badge = "⚠️ 危險近"
                        elif dist <= 600:
                            dist_color = "#fd7e14"; dist_badge = "⚠️ 需注意"
                        else:
                            dist_color = "#ffc107"; dist_badge = "🟢 尚可"
                        
                        col1, col2, col3, col4 = st.columns([5, 2, 2, 2])
                        with col1:
                            st.markdown(f"**{i+1}.** {row['設施名稱']}")
                        with col2:
                            st.markdown(f'<span style="background-color:#dc354520; color:#dc3545; padding:4px 8px; border-radius:8px; font-size:12px; font-weight:bold;">{row["設施子類別"]}</span>', unsafe_allow_html=True)
                        with col3:
                            score_text = f" [風險:{row['風險分數']}分]" if '風險分數' in row else ""
                            st.markdown(f'<span style="background-color:{dist_color}20; color:{dist_color}; padding:4px 8px; border-radius:8px; font-size:12px; font-weight:bold;">{dist}公尺 ({dist_badge}){score_text}</span>', unsafe_allow_html=True)
                        with col4:
                            st.link_button("🗺️ 地圖", maps_url, use_container_width=True)
                        st.divider()
    
    def _display_ai_analysis(self, res):
        """AI 分析"""
        st.markdown("---")
        st.subheader("🤖 AI 智能分析")
        
        profile = res.get("buyer_profile", "未指定")
        mode = res["analysis_mode"]
        include_nuisance = res.get("include_nuisance", False)
        nuisance_scores = res.get("nuisance_scores", {})
        profiles = self._get_buyer_profiles()
        pinfo = profiles.get(profile, {})
        icon = pinfo.get("icon", "👤")
        
        facilities_text, nuisance_text = self._format_facilities_for_prompt(res, include_nuisance)
        
        depth_texts = {}
        if 'ai_results_summary' in st.session_state:
            if mode == "單一房屋分析":
                house_name = list(res["houses_data"].keys())[0]
                title = res["houses_data"][house_name]['title']
                depth_item = self._get_depth_analysis_by_title(title)
                if depth_item:
                    depth_texts[house_name] = self._format_depth_summary(depth_item)
            else:
                for house_name, info in res["houses_data"].items():
                    depth_item = self._get_depth_analysis_by_title(info['title'])
                    if depth_item:
                        depth_texts[house_name] = self._format_depth_summary(depth_item)
        
        if mode == "單一房屋分析":
            if include_nuisance:
                prompt = self._build_single_with_nuisance_prompt(res, facilities_text, nuisance_text, depth_texts, nuisance_scores, profile, icon, pinfo)
            else:
                prompt = self._build_single_without_nuisance_prompt(res, facilities_text, depth_texts, profile, icon, pinfo)
        else:
            if include_nuisance:
                prompt = self._build_multi_with_nuisance_prompt(res, facilities_text, nuisance_text, depth_texts, nuisance_scores, profile, icon, pinfo)
            else:
                prompt = self._build_multi_without_nuisance_prompt(res, facilities_text, depth_texts, profile, icon, pinfo)
        
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
                if nuisance_scores:
                    for name, score in nuisance_scores.items():
                        st.markdown(f"📊 {name} 風險評分：{score} 分")
            st.markdown("---")
            st.markdown("**提示：**您可以編輯左側的提示詞")
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
                report = f"{report_title}\n生成時間：{get_taiwan_time()}\n\nAI 分析結果：\n{st.session_state.gemini_result}"
                st.download_button(label="📥 下載分析報告", data=report, file_name=f"{report_title}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt", mime="text/plain", use_container_width=True, key="download_report")
    
    def _format_facilities_for_prompt(self, res, include_nuisance=False):
        """格式化設施資料供提示詞使用"""
        df = res.get("facilities_table", pd.DataFrame())
        if df.empty:
            return "無周邊設施資料", ""
        
        if include_nuisance and '主要類別' in df.columns:
            normal_df = df[df['主要類別'] != "嫌惡設施"]
            nuisance_df = df[df['主要類別'] == "嫌惡設施"]
        else:
            normal_df = df
            nuisance_df = pd.DataFrame()
        
        normal_text = "\n【一般設施清單】\n" + "=" * 60 + "\n"
        for house_name in normal_df['房屋'].unique():
            house_df = normal_df[normal_df['房屋'] == house_name]
            normal_text += f"\n🏠 {house_name} 周邊一般設施（共 {len(house_df)} 個）：\n" + "-" * 50 + "\n"
            house_df_sorted = house_df.sort_values('距離(公尺)')
            for i, row in house_df_sorted.iterrows():
                normal_text += f"  {i+1}. {row['設施名稱']} ({row['設施子類別']}) - {row['距離(公尺)']}公尺\n"
        
        nuisance_text = ""
        if not nuisance_df.empty:
            nuisance_text = "\n【⚠️ 嫌惡設施清單】\n" + "=" * 60 + "\n"
            for house_name in nuisance_df['房屋'].unique():
                house_df = nuisance_df[nuisance_df['房屋'] == house_name]
                nuisance_text += f"\n🏠 {house_name} 周邊嫌惡設施（共 {len(house_df)} 處）：\n" + "-" * 50 + "\n"
                house_df_sorted = house_df.sort_values('距離(公尺)')
                for i, row in house_df_sorted.iterrows():
                    score = row.get('風險分數', '')
                    score_text = f" [風險:{score}分]" if score else ""
                    nuisance_text += f"  {i+1}. ⚠️ {row['設施名稱']} ({row['設施子類別']}){score_text} - {row['距離(公尺)']}公尺\n"
        
        return normal_text, nuisance_text
    
    def _build_single_without_nuisance_prompt(self, res, facilities_text, depth_texts, profile, icon, pinfo):
        """單一房屋無嫌惡設施的提示詞"""
        name = list(res["houses_data"].keys())[0]
        h = res["houses_data"][name]
        cnt = res["facility_counts"].get(name, 0)
        focus = pinfo.get("prompt_focus", [])
        depth_text = depth_texts.get(name, "")
        
        return f"""
你是一位專業的房地產分析師，請以「{icon} {profile}」的身份，對以下房屋進行綜合分析與評分。

【買家類型】
{profile} - {pinfo.get('description', '')}
重點關注：{', '.join(focus)}
{depth_text}
【房屋資訊】
- 標題：{h['title']}
- 地址：{h['address']}

【搜尋條件】
- 半徑：{res['radius']} 公尺
- 分析類別：{', '.join(res['selected_categories'])}
- 關鍵字：{res.get('keyword', '') if res.get('keyword') else '無'}

【周邊設施統計】
- 總數量：{cnt} 個設施

{facilities_text}

請根據【房屋深度分析】和【一般設施清單】綜合評估，提供以下分析：

1. **綜合評分**（1-10分）
2. **主要優點**（3-5點）
3. **主要缺點**（3-5點）
4. **生活便利性預測**
5. **未來發展潛力**
6. **購買建議**

請用專業、客觀的角度分析，給出實用的建議。
"""

    def _build_single_with_nuisance_prompt(self, res, facilities_text, nuisance_text, depth_texts, nuisance_scores, profile, icon, pinfo):
        """單一房屋有嫌惡設施的提示詞"""
        name = list(res["houses_data"].keys())[0]
        h = res["houses_data"][name]
        cnt = res["facility_counts"].get(name, 0)
        focus = pinfo.get("prompt_focus", [])
        depth_text = depth_texts.get(name, "")
        score = nuisance_scores.get(name, 0)
        
        return f"""
你是一位專業的房地產分析師，請以「{icon} {profile}」的身份，對以下房屋進行綜合分析與評分。**此分析包含嫌惡設施評估**。

【買家類型】
{profile} - {pinfo.get('description', '')}
重點關注：{', '.join(focus)}
{depth_text}
【房屋資訊】
- 標題：{h['title']}
- 地址：{h['address']}

【搜尋條件】
- 半徑：{res['radius']} 公尺
- 分析類別：{', '.join(res['selected_categories'])}
- 關鍵字：{res.get('keyword', '') if res.get('keyword') else '無'}

【嫌惡設施風險評分】{score} 分
{facilities_text}
{nuisance_text}

請根據【房屋深度分析】、【一般設施清單】和【嫌惡設施清單】綜合評估，**特別注意嫌惡設施的影響**，提供以下分析：

1. **綜合評分**（1-10分）
   - 一般設施評分（滿分7分）
   - **嫌惡設施扣分**（最高扣3分，根據風險評分）
   
2. **主要優點**（3-5點）
3. **主要缺點**（3-5點）**必須詳細說明每個嫌惡設施的影響**
4. **生活便利性預測**（需考慮嫌惡設施）
5. **未來發展潛力**（評估嫌惡設施是否可能搬遷或改善）
6. **購買建議**（考慮嫌惡設施的影響，給出價格折讓建議）

請用專業、客觀的角度分析，給出實用的建議。
"""

    def _build_multi_without_nuisance_prompt(self, res, facilities_text, depth_texts, profile, icon, pinfo):
        """多房屋比較無嫌惡設施的提示詞"""
        houses_data = res["houses_data"]
        counts = res["facility_counts"]
        focus = pinfo.get("prompt_focus", [])
        
        house_list = "\n".join([f"- {n}：{h['title'][:30]}..." for n, h in houses_data.items()])
        comparison_rows = [f"  {name}：{cnt} 個設施" for name, cnt in counts.items()]
        comparison_text = "\n".join(comparison_rows)
        
        depth_section = "\n【各房屋深度分析】\n"
        for name in houses_data.keys():
            if name in depth_texts:
                depth_section += f"\n{name}{depth_texts[name]}"
        
        return f"""
你是一位專業的房地產分析師，請比較以下{len(houses_data)}間房屋，並以「{icon} {profile}」的身份給出建議。

【買家類型】
{profile} - {pinfo.get('description', '')}
重點關注：{', '.join(focus)}
{depth_section}
【候選房屋】
{house_list}

【各房屋設施數量】
{comparison_text}

{facilities_text}

請根據【各房屋深度分析】和【一般設施清單】綜合評估，提供以下分析：

1. **綜合排名**（1-{len(houses_data)}名）
2. **各房屋評分與計算方式**
3. **優缺點比較表**
4. **各房屋詳細分析**
5. **最終推薦**
6. **購買時機建議**

請用專業、客觀的角度分析，給出實用的比較建議。
"""

    def _build_multi_with_nuisance_prompt(self, res, facilities_text, nuisance_text, depth_texts, nuisance_scores, profile, icon, pinfo):
        """多房屋比較有嫌惡設施的提示詞"""
        houses_data = res["houses_data"]
        counts = res["facility_counts"]
        focus = pinfo.get("prompt_focus", [])
        
        house_list = "\n".join([f"- {n}：{h['title'][:30]}..." for n, h in houses_data.items()])
        comparison_rows = [f"  {name}：{cnt} 個設施" for name, cnt in counts.items()]
        comparison_text = "\n".join(comparison_rows)
        
        score_text = "\n【各房屋嫌惡設施風險評分】\n"
        for name, score in nuisance_scores.items():
            score_text += f"- {name}：{score} 分\n"
        
        depth_section = "\n【各房屋深度分析】\n"
        for name in houses_data.keys():
            if name in depth_texts:
                depth_section += f"\n{name}{depth_texts[name]}"
        
        return f"""
你是一位專業的房地產分析師，請比較以下{len(houses_data)}間房屋，並以「{icon} {profile}」的身份給出建議。**此分析包含嫌惡設施評估**。

【買家類型】
{profile} - {pinfo.get('description', '')}
重點關注：{', '.join(focus)}
{depth_section}
【候選房屋】
{house_list}

【各房屋設施數量】
{comparison_text}
{score_text}

{facilities_text}
{nuisance_text}

請根據【各房屋深度分析】、【一般設施清單】和【嫌惡設施清單】綜合評估，**特別注意嫌惡設施的影響**，提供以下分析：

1. **綜合排名**（1-{len(houses_data)}名）**優先考慮嫌惡設施較少的房屋**
2. **各房屋評分與計算方式**（一般設施評分 + 嫌惡設施扣分）
3. **優缺點比較表**（包含嫌惡設施影響欄位）
4. **各房屋詳細分析**（包含嫌惡設施影響詳細說明）
5. **最終推薦**（考慮嫌惡設施的影響）
6. **購買時機建議**（考慮嫌惡設施對房價的長期影響）

請用專業、客觀的角度分析，給出實用的比較建議。
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
    
    def _get_server_key(self):
        return st.session_state.get("GMAPS_SERVER_KEY") or st.session_state.get("GOOGLE_MAPS_KEY", "")
    
    def _get_browser_key(self):
        return st.session_state.get("GMAPS_BROWSER_KEY") or st.session_state.get("GOOGLE_MAPS_KEY", "")
    
    def _get_gemini_key(self):
        return st.session_state.get("GEMINI_KEY", "")


def get_comparison_analyzer():
    return ComparisonAnalyzer()
