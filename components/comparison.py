# components/comparison.py
# VERSION: EXACT_USER_TABLE_NO_EXTRA_IMPACTS
# VERSION: FINAL_IMPACT_FILTER_NO_SCORE_EXACT_TABLE_20260512
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

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    REPORTLAB_AVAILABLE = True
except Exception:
    REPORTLAB_AVAILABLE = False


try:
    from components.favorites import normalize_property_id
except Exception:
    try:
        from favorites import normalize_property_id
    except Exception:
        def normalize_property_id(value):
            return "" if value is None else str(value).strip()


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

try:
    from components.real_price import (
        update_real_price_cache_if_needed,
        filter_nearby_transactions,
        calculate_price_metrics,
        render_real_price_analysis,
        format_real_price_metrics_for_prompt,
        infer_city_from_address,
    )
    REAL_PRICE_AVAILABLE = True
    REAL_PRICE_IMPORT_ERROR = ""
except Exception as real_price_import_error:
    try:
        import importlib.util
        current_file_dir = os.path.dirname(os.path.abspath(__file__))
        real_price_candidates = [
            os.path.join(current_file_dir, "real_price.py"),
            os.path.join(current_file_dir, "components", "real_price.py"),
            os.path.join(os.path.dirname(current_file_dir), "components", "real_price.py"),
        ]
        real_price_path = next((path for path in real_price_candidates if os.path.exists(path)), None)
        if not real_price_path:
            raise FileNotFoundError("找不到 real_price.py，已嘗試：" + " | ".join(real_price_candidates))
        spec = importlib.util.spec_from_file_location("real_price", real_price_path)
        real_price_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(real_price_module)
        update_real_price_cache_if_needed = real_price_module.update_real_price_cache_if_needed
        filter_nearby_transactions = real_price_module.filter_nearby_transactions
        calculate_price_metrics = real_price_module.calculate_price_metrics
        render_real_price_analysis = real_price_module.render_real_price_analysis
        format_real_price_metrics_for_prompt = real_price_module.format_real_price_metrics_for_prompt
        infer_city_from_address = real_price_module.infer_city_from_address
        REAL_PRICE_AVAILABLE = True
        REAL_PRICE_IMPORT_ERROR = ""
    except Exception as fallback_error:
        REAL_PRICE_AVAILABLE = False
        REAL_PRICE_IMPORT_ERROR = f"{real_price_import_error}；fallback: {fallback_error}"

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
    
    def _ensure_analysis_store(self):
        """Ensure analysis_store exists and backfill solo_analysis summaries."""
        if 'analysis_store' not in st.session_state:
            st.session_state.analysis_store = {}

        if 'ai_results_summary' in st.session_state:
            for item in st.session_state.ai_results_summary:
                try:
                    basic = item.get('basic_info', {})
                    property_id = normalize_property_id(basic.get('\u7de8\u865f', item.get('property_id', '')))
                    if property_id and property_id not in st.session_state.analysis_store:
                        st.session_state.analysis_store[property_id] = {
                            'property_id': property_id,
                            'basic_info': basic,
                            'analysis_text': item.get('analysis_text', {}),
                            'analysis_data': item.get('analysis_data', {}),
                            'scores': item.get('scores', {}),
                            'total_score': item.get('total_score'),
                        }
                except Exception:
                    continue

    def _get_depth_analysis_by_id(self, property_id):
        """Get solo_analysis depth data by property id first."""
        self._ensure_analysis_store()
        pid = normalize_property_id(property_id)
        if not pid:
            return None
        return st.session_state.get('analysis_store', {}).get(pid)

    def _get_depth_analysis_by_title(self, title):
        """Fallback lookup for legacy data by house title."""
        self._ensure_analysis_store()
        for item in st.session_state.get('analysis_store', {}).values():
            if item.get('basic_info', {}).get('\u6a19\u984c') == title:
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
        """舊版權重設定已停用。嫌惡設施目前不使用分數、不使用權重。"""
        st.info("目前嫌惡設施採資訊揭露制：只顯示影響分類、最近距離與周圍數量，不計算分數或權重。")

    def _get_nuisance_notice(self, nuisance_type, distance, count, ai_relevance=None):
        """依距離與數量產生嫌惡設施提醒文字，不使用風險分數"""
        try:
            distance = float(distance)
        except Exception:
            distance = 999999

        nuisance_info = NUISANCE_TYPES.get(nuisance_type, {})
        impacts = nuisance_info.get("impacts", [])
        impact_text = "、".join(impacts) if impacts else "周邊環境"

        if distance <= 300:
            level_text = "距離較近"
            advice = "建議實地查看不同時段的噪音、交通、人潮、氣味或心理感受。"
        elif distance <= 600:
            level_text = "距離中等"
            advice = "建議留意尖峰時段或特定活動時段是否造成影響。"
        else:
            level_text = "距離較遠"
            advice = "通常影響較低，但仍可依個人接受度評估。"

        if count >= 3:
            count_text = f"周邊同類設施共 {count} 處，數量偏多。"
        elif count == 2:
            count_text = "周邊同類設施有 2 處，可稍微留意。"
        else:
            count_text = "周邊同類設施有 1 處。"

        relevance_advice = {
            "\u9ad8\u5ea6\u76f8\u95dc": "AI\u5224\u8b80\u70ba\u9ad8\u5ea6\u76f8\u95dc\uff0c\u5efa\u8b70\u73fe\u5834\u78ba\u8a8d\u3002",
            "\u90e8\u5206\u76f8\u95dc": "AI\u5224\u8b80\u70ba\u90e8\u5206\u76f8\u95dc\uff0c\u5efa\u8b70\u78ba\u8a8d\u5be6\u969b\u7528\u9014\u3002",
            "\u4f4e\u5ea6\u76f8\u95dc": "AI\u5224\u8b80\u70ba\u4f4e\u5ea6\u76f8\u95dc\uff0c\u8cc7\u6599\u53ef\u80fd\u4e0d\u660e\u78ba\u3002",
            "\u7121\u95dc": "AI\u5224\u8b80\u70ba\u7121\u95dc\uff0c\u8a72\u7d50\u679c\u53ef\u80fd\u662f Google \u641c\u5c0b\u8aa4\u5224\u3002",
        }.get(ai_relevance, "")
        if relevance_advice:
            relevance_advice = relevance_advice + " "

        return f"{level_text}，可能影響：{impact_text}。{count_text}{relevance_advice}{advice}"

    def _render_nuisance_selection_with_weights(self):
        """先用影響類型篩選，再選擇受影響的嫌惡設施；不使用權重與分數"""
        selected = []

        st.markdown("#### ① 選擇您在意的影響類型")
        st.info("系統會依照影響類型篩出相關嫌惡設施；此版本只揭露影響分類、最近距離與周圍數量，不計算分數。")

        if not NUISANCE_TYPES:
            st.warning("⚠️ 尚未載入嫌惡設施類型資料")
            return selected

        if not IMPACT_TYPES:
            st.warning("⚠️ 尚未載入影響類型資料")
            return selected

        selected_impacts = []
        impact_items = list(IMPACT_TYPES.items())
        impact_cols = st.columns(3)

        for i, (impact_name, impact_info) in enumerate(impact_items):
            with impact_cols[i % 3]:
                checked = st.checkbox(
                    impact_name,
                    key=f"nuisance_impact_filter_{impact_name}",
                    help=impact_info.get("description", "")
                )
                if checked:
                    selected_impacts.append(impact_name)

        if not selected_impacts:
            st.warning("請先選擇至少一個影響類型。")
            return selected

        st.markdown("---")
        st.markdown("#### ② 選擇要查詢的嫌惡設施")

        matched = {}
        for nuisance_name, nuisance_info in NUISANCE_TYPES.items():
            impacts = nuisance_info.get("impacts", [])
            if any(impact in impacts for impact in selected_impacts):
                matched[nuisance_name] = nuisance_info

        if not matched:
            st.info("目前沒有符合所選影響類型的嫌惡設施。")
            return selected

        st.caption(
            f"已依照「{'、'.join(selected_impacts)}」篩出 {len(matched)} 類嫌惡設施，"
            "預設全選；您可以取消不想查詢的項目。"
        )

        items = list(matched.items())
        cols = st.columns(3)

        for i, (nuisance_name, nuisance_info) in enumerate(items):
            impacts = nuisance_info.get("impacts", [])
            impact_text = "、".join(impacts) if impacts else "未分類"
            help_text = f"影響分類：{impact_text}"

            with cols[i % 3]:
                checked = st.checkbox(
                    nuisance_name,
                    key=f"nuisance_by_impact_{nuisance_name}",
                    value=True,
                    help=help_text
                )
                st.caption(f"分類：{impact_text}")
                if checked:
                    selected.append(nuisance_name)

        if selected:
            st.success(f"✅ 目前選擇 {len(selected)} 類嫌惡設施")
        else:
            st.warning("⚠️ 您已取消所有嫌惡設施，將不會查詢嫌惡設施。")

        return selected

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
                        '嫌惡設施數量': len(df[df['主要類別'] == '嫌惡設施']) if analysis.get('include_nuisance', False) and '主要類別' in df.columns else 0
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
            nuisance_summary = analysis.get('nuisance_summary', {}) or {}
            txt_lines.append(f"嫌惡設施數量：{nuisance_summary.get(name, 0)} 處")
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
                txt_lines.append(f"  • {row['設施名稱']} ({row['設施子類別']}){is_nuisance} - {row['距離(公尺)']}公尺")
            
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
        st.markdown("勾選後先選擇在意的影響類型，再篩出相關嫌惡設施；系統會顯示分類、最近設施、距離與周圍數量")
        
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
            fav_df = pd.read_json(io.StringIO(s["fav"]), orient='split')
            
            with st.status("🔍 分析進行中...", expanded=True) as status:
                # 步驟1：解析地址
                st.write("📌 步驟 1/4：解析地址...")
                houses_data = {}
                for i, opt in enumerate(s["houses"]):
                    h = fav_df[(fav_df['標題'] + " | " + fav_df['地址']) == opt].iloc[0]
                    raw_title = str(h.get('\u6a19\u984c', '')).strip()
                    name = raw_title[:30] if raw_title else f'\u672a\u547d\u540d\u623f\u5c4b{i+1}'
                    if name in houses_data:
                        name = f'{name}-{i+1}'
                    lat, lng = geocode_address(h["地址"], s["server"])
                    if not lat or not lng:
                        st.error(f"❌ {name} 地址解析失敗")
                        st.session_state.analysis_in_progress = False
                        return
                    houses_data[name] = {
                        "name": name, "title": h['標題'], "address": h['地址'],
                        "property_id": normalize_property_id(h.get('\u7de8\u865f', '')),
                        "lat": lat, "lng": lng,
                        "property_summary": self._extract_house_summary(h)
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
                
                # 步驟2.5：如果需要，查詢嫌惡設施（不計分，只揭露最近距離與數量）
                nuisance_data = {}
                nuisance_summary = {}
                if s.get("include_nuisance", False) and s.get("selected_nuisances"):
                    st.write("🔍 步驟 2.5/4：查詢周邊嫌惡設施...")
                    
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
                        nuisance_summary[name] = len(all_nuisances)
                        
                        if name not in places_data:
                            places_data[name] = []
                        
                        for n in all_nuisances:
                            # 格式：主要類別、設施子類別、設施名稱、緯度、經度、距離、place_id、AI相關性、設施用途、AI說明
                            places_data[name].append(("嫌惡設施", n[0], n[2], n[3], n[4], n[5], n[6], n[7] if len(n) > 7 else "", n[8] if len(n) > 8 else "", n[9] if len(n) > 9 else ""))
                        
                        st.write(f"     找到 {len(all_nuisances)} 處嫌惡設施")
                
                # 步驟3：實價登錄價格分析
                st.write("💰 步驟 3/5：更新實價登錄快取並分析價格...")
                real_price_results = self._run_real_price_analysis(houses_data)
                
                # 步驟4：計算統計
                st.write("📊 步驟 4/5：計算統計...")
                counts = {n: len(p) for n, p in places_data.items()}
                table = self._create_facilities_table(houses_data, places_data)
                
                # 步驟5：儲存結果
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
                    "nuisance_summary": nuisance_summary if s.get("include_nuisance", False) else None,
                    "real_price_results": real_price_results
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
    
    def _analyze_nuisance_relevance_with_ai(self, nuisance_type, candidates):
        """Use Gemini to label nuisance candidate relevance without removing results."""
        allowed = {"\u9ad8\u5ea6\u76f8\u95dc", "\u90e8\u5206\u76f8\u95dc", "\u4f4e\u5ea6\u76f8\u95dc", "\u7121\u95dc"}
        if not candidates:
            return {}

        print("\u958b\u59cb AI \u5acc\u60e1\u8a2d\u65bd\u5206\u6790")
        print(f"AI\u5acc\u60e1\u8a2d\u65bd\u985e\u578b: {nuisance_type}")
        print(f"AI\u5acc\u60e1\u8a2d\u65bd\u5019\u9078\u7b46\u6578: {len(candidates)}")

        fallback = {}
        for c in candidates:
            pid = str(c.get("place_id", ""))
            fallback[pid] = {
                "ai_relevance": "\u672a\u7d93AI\u5224\u65b7",
                "place_purpose": "AI\u5224\u65b7\u5931\u6557",
                "ai_explanation": "Gemini \u7121\u6cd5\u5b8c\u6210\u5224\u65b7\uff0c\u4fdd\u7559\u539f\u59cb Google Places \u641c\u5c0b\u7d50\u679c\u3002",
            }

        try:
            import traceback
            import google.generativeai as genai
            key = self._get_gemini_key()
            if not key:
                msg = "AI\u5acc\u60e1\u8a2d\u65bd\u5206\u6790\u5931\u6557: \u672a\u53d6\u5f97 Gemini API Key"
                print(msg)
                st.error(msg)
                return fallback
            genai.configure(api_key=key)
            model = genai.GenerativeModel("gemini-flash-latest")
            analyzed = {}
            for start in range(0, len(candidates), 20):
                batch = candidates[start:start + 20]
                print(f"AI\u5acc\u60e1\u8a2d\u65bd\u6279\u6b21: {start // 20 + 1}, \u7b46\u6578: {len(batch)}")
                payload = [
                    {
                        "place_id": c.get("place_id", ""),
                        "name": c.get("name", ""),
                        "query_keyword": c.get("keyword", ""),
                        "address_or_vicinity": c.get("address", ""),
                        "google_types": c.get("types", []),
                        "distance_meters": c.get("distance", ""),
                    }
                    for c in batch
                ]
                prompt = f"""
\u4f60\u662f\u53f0\u7063\u623f\u5730\u7522\u5468\u908a\u5acc\u60e1\u8a2d\u65bd\u8cc7\u6599\u5be9\u6838\u54e1\u3002\u8acb\u5224\u65b7\u4e0b\u5217 Google Places \u5730\u9ede\u8207\u4f7f\u7528\u8005\u641c\u5c0b\u7684\u5acc\u60e1\u8a2d\u65bd\u985e\u578b\u300c{nuisance_type}\u300d\u7684\u76f8\u95dc\u6027\u3002

\u8acb\u6839\u64da\uff1a
- \u4f7f\u7528\u8005\u641c\u5c0b\u7684\u5acc\u60e1\u8a2d\u65bd\u985e\u578b
- Google Places \u56de\u50b3\u7684\u8a2d\u65bd\u540d\u7a31
- \u67e5\u8a62\u95dc\u9375\u5b57
- \u5730\u5740\u6216 vicinity
- Google types

\u5224\u65b7\u6a19\u6e96\uff1a
1. \u9ad8\u5ea6\u76f8\u95dc\uff1a\u8a72\u5730\u9ede\u660e\u78ba\u5c31\u662f\u76ee\u6a19\u5acc\u60e1\u8a2d\u65bd\uff0c\u6216\u4e3b\u8981\u696d\u52d9\u660e\u78ba\u7b26\u5408\u3002
2. \u90e8\u5206\u76f8\u95dc\uff1a\u8207\u76ee\u6a19\u8a2d\u65bd\u6709\u95dc\uff0c\u4f46\u4e0d\u4e00\u5b9a\u662f\u4e3b\u8981\u5acc\u60e1\u4f86\u6e90\u3002
3. \u4f4e\u5ea6\u76f8\u95dc\uff1a\u540d\u7a31\u6216\u696d\u52d9\u6709\u4e00\u9ede\u95dc\u806f\uff0c\u4f46\u662f\u5426\u5c6c\u65bc\u76ee\u6a19\u5acc\u60e1\u8a2d\u65bd\u4e0d\u660e\u78ba\u3002
4. \u7121\u95dc\uff1a\u8207\u76ee\u6a19\u5acc\u60e1\u8a2d\u65bd\u6c92\u6709\u5408\u7406\u95dc\u4fc2\u3002

\u91cd\u8981\u898f\u5247\uff1a
- \u53ea\u80fd\u7528\uff1a\u9ad8\u5ea6\u76f8\u95dc\u3001\u90e8\u5206\u76f8\u95dc\u3001\u4f4e\u5ea6\u76f8\u95dc\u3001\u7121\u95dc\u3002
- \u4e0d\u8981\u8f38\u51fa AI \u4fe1\u5fc3\u5ea6\u3001\u767e\u5206\u6bd4\u6216\u5206\u6578\u3002
- \u5982\u679c\u7121\u6cd5\u5224\u65b7\uff0cai_relevance \u8acb\u586b\u300c\u4f4e\u5ea6\u76f8\u95dc\u300d\uff0cplace_purpose \u586b\u300c\u7121\u6cd5\u5f9e\u540d\u7a31\u5224\u65b7\u4e3b\u8981\u7528\u9014\u300d\uff0cai_explanation \u586b\u300c\u8cc7\u6599\u4e0d\u8db3\uff0c\u5efa\u8b70\u4f7f\u7528\u8005\u81ea\u884c\u78ba\u8a8d\u3002\u300d
- \u53ea\u8f38\u51fa JSON array\uff0c\u4e0d\u8981 markdown\uff0c\u4e0d\u8981 code block\uff0c\u4e0d\u8981\u52a0\u4efb\u4f55\u8aaa\u660e\u6587\u5b57\u3002

\u56de\u50b3\u683c\u5f0f\uff1a
[
  {{
    "place_id": "\u539f\u59cb place_id",
    "ai_relevance": "\u9ad8\u5ea6\u76f8\u95dc",
    "place_purpose": "\u6876\u88dd\u74e6\u65af\u4f9b\u61c9\u696d\u8005\u3002",
    "ai_explanation": "\u540d\u7a31\u8207\u696d\u52d9\u660e\u78ba\u6307\u5411\u74e6\u65af\u4f9b\u61c9\uff0c\u7b26\u5408\u74e6\u65af\u884c\u985e\u578b\u3002"
  }}
]

\u5019\u9078\u8cc7\u6599 JSON\uff1a
{json.dumps(payload, ensure_ascii=False)}
"""
                print("AI\u5acc\u60e1\u8a2d\u65bd prompt \u524d1000\u5b57:")
                print(prompt[:1000])
                resp = model.generate_content(prompt)

                raw = ""
                raw_source = "response.text"
                try:
                    raw = (getattr(resp, "text", "") or "").strip()
                except Exception as text_error:
                    print(f"\u8b80\u53d6 response.text \u5931\u6557: {text_error}")
                    raw = ""
                if not raw:
                    raw_source = "response.candidates[0].content.parts[0].text"
                    try:
                        raw = (resp.candidates[0].content.parts[0].text or "").strip()
                    except Exception as candidate_error:
                        print(f"\u8b80\u53d6 response.candidates[0].content.parts[0].text \u5931\u6557: {candidate_error}")
                        raw = ""

                print(f"Gemini response text source: {raw_source}")
                print("Gemini raw response text:")
                print(raw)

                raw = raw.replace("```json", "").replace("```", "").strip()
                raw = re.sub(r"^```(?:json)?\s*", "", raw)
                raw = re.sub(r"\s*```$", "", raw)
                print("Gemini JSON text:", raw[:2000])

                verdicts = json.loads(raw)
                verdict_by_id = {str(v.get("place_id", "")): v for v in verdicts if isinstance(v, dict)}
                for c in batch:
                    pid = str(c.get("place_id", ""))
                    verdict = verdict_by_id.get(pid, {})
                    relevance = verdict.get("ai_relevance")
                    if relevance not in allowed:
                        relevance = "\u4f4e\u5ea6\u76f8\u95dc"
                    analyzed[pid] = {
                        "ai_relevance": relevance,
                        "place_purpose": verdict.get("place_purpose") or "\u7121\u6cd5\u5f9e\u540d\u7a31\u5224\u65b7\u4e3b\u8981\u7528\u9014\u3002",
                        "ai_explanation": verdict.get("ai_explanation") or "\u8cc7\u6599\u4e0d\u8db3\uff0c\u5efa\u8b70\u4f7f\u7528\u8005\u81ea\u884c\u78ba\u8a8d\u3002",
                    }
            for pid, item in fallback.items():
                analyzed.setdefault(pid, item)
            return analyzed
        except Exception as e:
            import traceback
            msg = f"AI\u5acc\u60e1\u8a2d\u65bd\u5206\u6790\u5931\u6557: {e}"
            print(msg)
            print(traceback.format_exc())
            st.error(msg)
            return fallback
    
    def _query_nuisances_no_progress(self, lat, lng, api_key, nuisances, radius):
        """Query nuisance candidates and annotate AI relevance without removing results."""
        candidates = []
        seen = set()
        for selected_nuisance in nuisances:
            keywords = NUISANCE_TYPES.get(selected_nuisance, {}).get("keywords", [])
            for keyword in keywords:
                try:
                    places = self._search_google_places_chinese(lat, lng, api_key, keyword, radius)
                    for place in places:
                        if place[5] > radius:
                            continue
                        pid = place[6]
                        dedupe_key = pid or f"{place[2]}|{place[3]}|{place[4]}"
                        if dedupe_key in seen:
                            continue
                        seen.add(dedupe_key)
                        candidates.append({
                            "nuisance_type": selected_nuisance,
                            "keyword": keyword,
                            "name": place[2],
                            "lat": place[3],
                            "lng": place[4],
                            "distance": place[5],
                            "place_id": pid,
                            "address": place[7] if len(place) > 7 else "",
                            "types": place[8] if len(place) > 8 else [],
                        })
                    time.sleep(0.3)
                except Exception:
                    continue
        if not candidates:
            return []

        relevance_by_type = {}
        for nuisance_type in sorted({c["nuisance_type"] for c in candidates}):
            batch_candidates = [c for c in candidates if c["nuisance_type"] == nuisance_type]
            relevance_by_type[nuisance_type] = self._analyze_nuisance_relevance_with_ai(nuisance_type, batch_candidates)

        results = []
        for c in candidates:
            pid = str(c.get("place_id", ""))
            ai = relevance_by_type.get(c.get("nuisance_type", ""), {}).get(pid, {})
            results.append((
                c.get("nuisance_type", ""),
                c.get("keyword", ""),
                c.get("name", ""),
                c.get("lat"),
                c.get("lng"),
                c.get("distance", 0),
                c.get("place_id", ""),
                ai.get("ai_relevance", "\u672a\u7d93AI\u5224\u65b7"),
                ai.get("place_purpose", "AI\u5224\u65b7\u5931\u6557"),
                ai.get("ai_explanation", "Gemini \u7121\u6cd5\u5b8c\u6210\u5224\u65b7\uff0c\u4fdd\u7559\u539f\u59cb Google Places \u641c\u5c0b\u7d50\u679c\u3002"),
            ))
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
                p.get("place_id", ""),
                p.get("formatted_address") or p.get("vicinity", ""),
                p.get("types", [])
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
                    "主要類別": p[0],
                    "距離(公尺)": p[5],
                    "經度": p[4],
                    "緯度": p[3],
                    "place_id": p[6],
                    "AI\u76f8\u95dc\u6027": p[7] if len(p) > 7 else "",
                    "\u8a2d\u65bd\u7528\u9014": p[8] if len(p) > 8 else "",
                    "AI\u8aaa\u660e": p[9] if len(p) > 9 else ""
                })
        return pd.DataFrame(rows)
    
    def _summarize_nuisance_by_type(self, df):
        """依房屋與嫌惡設施類型彙整：影響分類、最近設施、最近距離、周圍數量、提醒"""
        if df is None or df.empty or "主要類別" not in df.columns:
            return pd.DataFrame()

        nuisance_df = df[df["主要類別"] == "嫌惡設施"].copy()
        if nuisance_df.empty:
            return pd.DataFrame()

        nuisance_df["距離(公尺)"] = pd.to_numeric(nuisance_df["距離(公尺)"], errors="coerce")
        nuisance_df = nuisance_df.dropna(subset=["距離(公尺)"])

        rows = []
        for (house, subtype), group in nuisance_df.groupby(["房屋", "設施子類別"]):
            group = group.sort_values("距離(公尺)")
            nearest = group.iloc[0]
            distance = float(nearest["距離(公尺)"])
            count = int(len(group))

            info = NUISANCE_TYPES.get(subtype, {})
            impacts = info.get("impacts", [])

            rows.append({
                "房屋": house,
                "嫌惡設施類型": subtype,
                "影響分類": "、".join(impacts) if impacts else "未分類",
                "最近設施名稱": nearest.get("設施名稱", ""),
                "AI\u76f8\u95dc\u6027": nearest.get("AI\u76f8\u95dc\u6027", ""),
                "\u8a2d\u65bd\u7528\u9014": nearest.get("\u8a2d\u65bd\u7528\u9014", ""),
                "AI\u8aaa\u660e": nearest.get("AI\u8aaa\u660e", ""),
                "最近距離(公尺)": int(round(distance)),
                "周圍數量": count,
                "提醒": self._get_nuisance_notice(subtype, distance, count, nearest.get("AI\u76f8\u95dc\u6027", "")),
                "\u7def\u5ea6": nearest.get("\u7def\u5ea6", ""),
                "\u7d93\u5ea6": nearest.get("\u7d93\u5ea6", ""),
                "place_id": nearest.get("place_id", "")
            })

        out = pd.DataFrame(rows)
        if out.empty:
            return out
        return out.sort_values(["房屋", "最近距離(公尺)"]).reset_index(drop=True)

    def _render_depth_analysis_summary(self, res):
        """Render solo_analysis depth summaries on the comparison result page."""
        self._ensure_analysis_store()
        if not res or 'houses_data' not in res:
            return

        st.subheader("🏠 房屋本體深度分析摘要")
        shown = 0
        for house_name, info in res['houses_data'].items():
            property_id = normalize_property_id(info.get('property_id', ''))
            depth_item = self._get_depth_analysis_by_id(property_id) if property_id else self._get_depth_analysis_by_title(info.get('title', ''))
            if not depth_item:
                with st.expander(f"{house_name}｜{info.get('title', '未命名')}", expanded=False):
                    st.info("尚未建立個別深度分析資料，請先在 solo_analysis.py 對此房屋完成分析並儲存。")
                continue

            shown += 1
            basic_info = depth_item.get('basic_info', {}) or {}
            scores = depth_item.get('scores', {}) or {}
            total_score = depth_item.get('total_score', None)
            analysis_text = depth_item.get('analysis_text', {}) or {}
            summary_text = analysis_text.get('summary', '') if isinstance(analysis_text, dict) else ''

            title = basic_info.get('標題') or info.get('title', '未命名')
            with st.expander(f"{house_name}｜{title}", expanded=(len(res['houses_data']) == 1)):
                if total_score is not None:
                    try:
                        st.metric("本體總分", f"{float(total_score):.1f} / 100")
                    except Exception:
                        st.metric("本體總分", f"{total_score} / 100")

                if scores:
                    cols = st.columns(min(len(scores), 5))
                    for idx, (label, value) in enumerate(scores.items()):
                        with cols[idx % len(cols)]:
                            st.metric(label, value)

                st.markdown("**綜合摘要**")
                if summary_text:
                    st.write(summary_text)
                else:
                    formatted = self._format_depth_summary(depth_item)
                    if formatted:
                        st.markdown(formatted)
                    else:
                        st.caption("尚未儲存綜合摘要")

        if shown == 0:
            st.caption("目前 comparison 尚未讀到任何 solo_analysis 個別分析結果。")
    
    def _extract_house_summary(self, house_row):
        """擷取分析當下選取的收藏房屋本體資料。"""
        fields = ["標題", "地址", "屋齡", "類型", "建坪", "主+陽", "格局", "樓層", "車位", "總價(萬)", "行政區"]
        summary = {}
        for field in fields:
            value = house_row.get(field, "")
            if pd.isna(value):
                value = ""
            summary[field] = value
        return summary
    
    def _display_house_body_summary(self, res):
        """在設施詳細資料前顯示房屋本體分析摘要。"""
        fields = ["標題", "地址", "屋齡", "類型", "建坪", "主+陽", "格局", "樓層", "車位", "總價(萬)", "行政區"]
        rows = []
        for house_name, info in res.get("houses_data", {}).items():
            summary = dict(info.get("property_summary") or {})
            summary.setdefault("標題", info.get("title", ""))
            summary.setdefault("地址", info.get("address", ""))
            row = {"房屋": house_name}
            for field in fields:
                row[field] = summary.get(field, "")
            rows.append(row)
        
        st.subheader("🏠 房屋本體分析摘要")
        if not rows:
            st.info("尚無房屋本體資料")
            return
        
        st.dataframe(
            pd.DataFrame(rows),
            use_container_width=True,
            hide_index=True,
            column_config={
                "房屋": st.column_config.TextColumn(width="small"),
                "標題": st.column_config.TextColumn(width="large"),
                "地址": st.column_config.TextColumn(width="large"),
                "屋齡": st.column_config.TextColumn(width="small"),
                "類型": st.column_config.TextColumn(width="small"),
                "建坪": st.column_config.TextColumn(width="small"),
                "主+陽": st.column_config.TextColumn(width="small"),
                "格局": st.column_config.TextColumn(width="small"),
                "樓層": st.column_config.TextColumn(width="small"),
                "車位": st.column_config.TextColumn(width="small"),
                "總價(萬)": st.column_config.TextColumn(width="small"),
                "行政區": st.column_config.TextColumn(width="small"),
            },
        )
    
    def _build_real_price_target_house(self, house_name, info):
        """Build target house payload for real price comparison."""
        summary = dict(info.get("property_summary") or {})
        summary.setdefault("標題", info.get("title", house_name))
        summary.setdefault("地址", info.get("address", ""))
        summary["房屋名稱"] = house_name
        summary["城市"] = infer_city_from_address(summary.get("地址", "")) if REAL_PRICE_AVAILABLE else ""
        return summary

    def _run_real_price_analysis(self, houses_data):
        """Update/load real price data and calculate metrics for selected houses."""
        results = {}
        if not REAL_PRICE_AVAILABLE:
            for house_name in houses_data.keys():
                results[house_name] = {"error": f"實價登錄模組無法載入：{REAL_PRICE_IMPORT_ERROR}"}
            return results

        for house_name, info in houses_data.items():
            target = self._build_real_price_target_house(house_name, info)
            city = target.get("城市", "")
            if not city:
                results[house_name] = {"error": "無法由地址判斷縣市，資料不足，建議放寬條件"}
                continue
            try:
                df = update_real_price_cache_if_needed(city, max_age_days=10)
                transactions = filter_nearby_transactions(df, target)
                metrics = calculate_price_metrics(transactions, target)
                results[house_name] = {
                    "city": city,
                    "target": target,
                    "metrics": metrics,
                }
            except Exception as e:
                msg = f"實價登錄資料更新或分析失敗：{e}"
                st.warning(f"{house_name}：{msg}")
                results[house_name] = {"city": city, "target": target, "error": msg}
        return results

    def _display_real_price_analysis(self, res):
        """Display real price analysis below house body summary."""
        st.subheader("💰 實價登錄價格分析")
        results = res.get("real_price_results", {}) or {}
        if not results:
            st.info("資料不足，建議放寬條件")
            return

        for house_name, result in results.items():
            with st.expander(f"{house_name}", expanded=(len(results) == 1)):
                if not isinstance(result, dict) or result.get("error"):
                    st.warning(result.get("error", "資料不足，建議放寬條件") if isinstance(result, dict) else "資料不足，建議放寬條件")
                    continue
                city = result.get("city", "")
                if city:
                    st.caption(f"資料縣市：{city}，快取超過 10 天才自動更新。")
                render_real_price_analysis(result.get("metrics", {}))

    def _format_real_price_for_prompt(self, res):
        """Format real price metrics for Gemini prompt."""
        if not REAL_PRICE_AVAILABLE:
            return f"\n【實價登錄價格分析】\n實價登錄模組無法載入：{REAL_PRICE_IMPORT_ERROR}\n"
        return format_real_price_metrics_for_prompt(res.get("real_price_results", {}) or {})

    def _display_analysis_results(self, res):
        """顯示分析結果"""
        if not res:
            return
        
        mode = res["analysis_mode"]
        profile = res.get("buyer_profile", "未指定")
        timestamp = res.get("timestamp", "未知時間")
        include_nuisance = res.get("include_nuisance", False)
        nuisance_summary = res.get("nuisance_summary", {}) or {}
        profiles = self._get_buyer_profiles()
        pinfo = profiles.get(profile, {})
        icon = pinfo.get("icon", "👤")
        
        st.markdown(f"### 分析時間：{timestamp}")
        if include_nuisance:
            st.info("⚠️ 此分析包含嫌惡設施資訊揭露：顯示最近設施、距離與周圍數量，不再使用風險分數。")
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
        self._render_depth_analysis_summary(res)
        
        st.markdown("---")
        
        # House favorite data summary
        self._display_house_body_summary(res)
        
        st.markdown("---")
        
        # Real price registration analysis
        self._display_real_price_analysis(res)
        
        st.markdown("---")
        
        # 設施統計
        st.subheader("📈 設施統計")
        
        if res["num_houses"] == 1:
            self._show_single_stats(res, include_nuisance)
        else:
            self._show_multi_stats(res, include_nuisance)
        
        # 地圖檢視
        self._display_maps(res)
        
        # 設施總表
        self._display_facility_summary_tables(res, include_nuisance)
        
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
    
    def _build_maps_url(self, row):
        """Build a Google Maps place URL for a facility row."""
        return f"https://www.google.com/maps/search/?api=1&query={row['\u7def\u5ea6']},{row['\u7d93\u5ea6']}&query_place_id={row['place_id']}"
    
    def _distance_badge(self, distance, nuisance=False):
        """Return badge color and text for a facility distance."""
        try:
            dist = float(distance)
        except Exception:
            dist = 0
        if nuisance:
            if dist <= 300:
                return "#dc3545", "\u26a0\ufe0f \u5371\u96aa\u8fd1"
            if dist <= 600:
                return "#fd7e14", "\u26a0\ufe0f \u9700\u6ce8\u610f"
            return "#ffc107", "\U0001f7e2 \u5c1a\u53ef"
        if dist <= 300:
            return "#28a745", "\u5f88\u8fd1"
        if dist <= 600:
            return "#ffc107", "\u4e2d\u7b49"
        return "#dc3545", "\u8f03\u9060"
    
    def _render_facility_cards(self, df, nuisance=False):
        """Render facility rows with distance badges and Google Maps links."""
        for house_name in df['\u623f\u5c4b'].unique():
            house_df = df[df['\u623f\u5c4b'] == house_name].sort_values('\u8ddd\u96e2(\u516c\u5c3a)')
            label = "\u5acc\u60e1\u8a2d\u65bd" if nuisance else "\u4e00\u822c\u8a2d\u65bd"
            st.markdown(f"**\U0001f3e0 {house_name}** - \u5171 {len(house_df)} \u500b{label}")
            
            for idx, (_, row) in enumerate(house_df.iterrows(), start=1):
                maps_url = self._build_maps_url(row)
                dist = row['\u8ddd\u96e2(\u516c\u5c3a)']
                dist_color, dist_badge = self._distance_badge(dist, nuisance=nuisance)
                type_color = "#dc3545" if nuisance else CATEGORY_COLORS.get(row.get('\u4e3b\u8981\u985e\u5225', ''), "#666")
                
                col1, col2, col3, col4, col5 = st.columns([3, 2, 2, 2, 1.5])
                with col1:
                    st.markdown(f"**{idx}. {row['\u8a2d\u65bd\u540d\u7a31']}**")
                with col2:
                    st.markdown(f"\u623f\u5c4b\u540d\u7a31\uff1a{house_name}")
                with col3:
                    st.markdown(
                        f'<span style="background-color:{type_color}20; color:{type_color}; padding:4px 8px; border-radius:8px; font-size:12px; font-weight:bold;">{row["\u8a2d\u65bd\u5b50\u985e\u5225"]}</span>',
                        unsafe_allow_html=True,
                    )
                with col4:
                    st.markdown(
                        f'<span style="background-color:{dist_color}20; color:{dist_color}; padding:4px 8px; border-radius:8px; font-size:12px; font-weight:bold;">{dist}\u516c\u5c3a ({dist_badge})</span>',
                        unsafe_allow_html=True,
                    )
                with col5:
                    st.link_button("Google\u5730\u5716", maps_url, use_container_width=True)
                if nuisance:
                    relevance = row.get("AI\u76f8\u95dc\u6027", "")
                    purpose = row.get("\u8a2d\u65bd\u7528\u9014", "")
                    explanation = row.get("AI\u8aaa\u660e", "")
                    if relevance:
                        st.caption(f"AI\u76f8\u95dc\u6027\uff1a{relevance}")
                    if purpose:
                        st.caption(f"\u8a2d\u65bd\u7528\u9014\uff1a{purpose}")
                    if explanation:
                        st.caption(f"AI\u8aaa\u660e\uff1a{explanation}")
                st.divider()
    
    def _display_facility_summary_tables(self, res, include_nuisance=False):
        """Display unified facility sections below the map."""
        st.markdown("---")
        df = res.get("facilities_table", pd.DataFrame())
        if df.empty:
            st.info("\U0001f4ed \u7121\u8a2d\u65bd\u8cc7\u6599")
            return
        
        if include_nuisance and '\u4e3b\u8981\u985e\u5225' in df.columns:
            normal_df = df[df['\u4e3b\u8981\u985e\u5225'] != "\u5acc\u60e1\u8a2d\u65bd"].copy()
            nuisance_df = df[df['\u4e3b\u8981\u985e\u5225'] == "\u5acc\u60e1\u8a2d\u65bd"].copy()
        else:
            normal_df = df.copy()
            nuisance_df = pd.DataFrame()
        
        with st.expander("\u2705 \u4e00\u822c\u8a2d\u65bd\u7e3d\u8868", expanded=False):
            if normal_df.empty:
                st.info("\U0001f4ed \u7121\u4e00\u822c\u8a2d\u65bd\u8cc7\u6599")
            else:
                normal_types = sorted(normal_df["\u4e3b\u8981\u985e\u5225"].dropna().unique().tolist()) if "\u4e3b\u8981\u985e\u5225" in normal_df.columns else []
                selected_normal_types = st.multiselect(
                    "\u7be9\u9078\u4e00\u822c\u8a2d\u65bd\u985e\u578b",
                    options=normal_types,
                    default=normal_types,
                    key="normal_facility_type_filter",
                )
                normal_display_df = normal_df[normal_df["\u4e3b\u8981\u985e\u5225"].isin(selected_normal_types)].copy() if normal_types else normal_df.copy()
                st.caption(f"\u76ee\u524d\u986f\u793a {len(normal_display_df)} / \u539f\u59cb {len(normal_df)} \u7b46\u8cc7\u6599")
                if normal_display_df.empty:
                    st.info("\u76ee\u524d\u7be9\u9078\u689d\u4ef6\u4e0b\u6c92\u6709\u8cc7\u6599")
                else:
                    self._render_facility_cards(normal_display_df, nuisance=False)
        
        if include_nuisance:
            st.markdown("---")
            with st.expander("\u26a0\ufe0f \u5acc\u60e1\u8a2d\u65bd\u660e\u7d30\u7e3d\u8868", expanded=True):
                if nuisance_df.empty:
                    st.info("\U0001f4ed \u7121\u5acc\u60e1\u8a2d\u65bd\u8cc7\u6599")
                else:
                    type_col = "\u5acc\u60e1\u8a2d\u65bd\u985e\u578b" if "\u5acc\u60e1\u8a2d\u65bd\u985e\u578b" in nuisance_df.columns else "\u8a2d\u65bd\u5b50\u985e\u5225"
                    nuisance_types = sorted(nuisance_df[type_col].dropna().unique().tolist()) if type_col in nuisance_df.columns else []
                    selected_nuisance_types = st.multiselect(
                        "\u7be9\u9078\u5acc\u60e1\u8a2d\u65bd\u985e\u578b",
                        options=nuisance_types,
                        default=nuisance_types,
                        key="nuisance_facility_type_filter",
                    )
                    nuisance_display_df = nuisance_df[nuisance_df[type_col].isin(selected_nuisance_types)].copy() if nuisance_types else nuisance_df.copy()
                    st.caption(f"\u76ee\u524d\u986f\u793a {len(nuisance_display_df)} / \u539f\u59cb {len(nuisance_df)} \u7b46\u8cc7\u6599")
                    if nuisance_display_df.empty:
                        st.info("\u76ee\u524d\u7be9\u9078\u689d\u4ef6\u4e0b\u6c92\u6709\u8cc7\u6599")
                    else:
                        self._render_facility_cards(nuisance_display_df, nuisance=True)
    
    def _pdf_clean_text(self, value):
        """Normalize text for reportlab paragraphs."""
        if value is None:
            return ""
        text = str(value)
        text = re.sub(r"<[^>]+>", "", text)
        text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        return text.replace("\n", "<br/>")
    
    def _pdf_table_from_df(self, df, columns, styles, max_rows=40):
        """Create a compact reportlab table from selected DataFrame columns."""
        if df is None or df.empty:
            return [Paragraph("無資料", styles["Body"])]
        available = [c for c in columns if c in df.columns]
        if not available:
            return [Paragraph("無資料", styles["Body"])]
        table_df = df[available].head(max_rows).copy()
        data = [[Paragraph(self._pdf_clean_text(c), styles["TableHeader"]) for c in available]]
        for _, row in table_df.iterrows():
            data.append([Paragraph(self._pdf_clean_text(row.get(c, "")), styles["TableCell"]) for c in available])
        table = Table(data, repeatRows=1)
        table.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), "STSong-Light"),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f0f2f6")),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#cccccc")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        items = [table]
        if len(df) > max_rows:
            items.extend([Spacer(1, 0.15 * cm), Paragraph(f"僅列出前 {max_rows} 筆，共 {len(df)} 筆資料。", styles["Small"])])
        return items
    
    def _add_pdf_section(self, story, title, body, styles):
        story.append(Paragraph(title, styles["Heading"]))
        story.extend(body)
        story.append(Spacer(1, 0.25 * cm))
    
    def _generate_pdf_report(self, res, ai_text):
        """Generate a PDF report directly from analysis data."""
        if not REPORTLAB_AVAILABLE:
            return None
        pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=1.2 * cm,
            leftMargin=1.2 * cm,
            topMargin=1.2 * cm,
            bottomMargin=1.2 * cm,
            title="房屋分析報告",
        )
        base_styles = getSampleStyleSheet()
        styles = {
            "Title": ParagraphStyle("Title", parent=base_styles["Title"], fontName="STSong-Light", fontSize=22, leading=28, alignment=1),
            "Heading": ParagraphStyle("Heading", parent=base_styles["Heading2"], fontName="STSong-Light", fontSize=14, leading=18, spaceBefore=10, spaceAfter=8),
            "Body": ParagraphStyle("Body", parent=base_styles["BodyText"], fontName="STSong-Light", fontSize=10, leading=14),
            "Small": ParagraphStyle("Small", parent=base_styles["BodyText"], fontName="STSong-Light", fontSize=8, leading=11, textColor=colors.HexColor("#666666")),
            "TableHeader": ParagraphStyle("TableHeader", parent=base_styles["BodyText"], fontName="STSong-Light", fontSize=8, leading=10),
            "TableCell": ParagraphStyle("TableCell", parent=base_styles["BodyText"], fontName="STSong-Light", fontSize=7, leading=9),
        }
        story = []
        profile = res.get("buyer_profile", "未指定")
        generated_at = get_taiwan_time()
        include_nuisance = res.get("include_nuisance", False)
        df = res.get("facilities_table", pd.DataFrame())
        story.append(Paragraph("房屋分析報告", styles["Title"]))
        story.append(Spacer(1, 0.4 * cm))
        story.append(Paragraph(f"生成時間：{self._pdf_clean_text(generated_at)}", styles["Body"]))
        story.append(Paragraph(f"買家類型：{self._pdf_clean_text(profile)}", styles["Body"]))
        story.append(Spacer(1, 0.5 * cm))
        
        house_rows = []
        fields = ["標題", "地址", "屋齡", "類型", "建坪", "主+陽", "格局", "樓層", "車位", "總價(萬)", "行政區"]
        for house_name, info in res.get("houses_data", {}).items():
            summary = dict(info.get("property_summary") or {})
            summary.setdefault("標題", info.get("title", house_name))
            summary.setdefault("地址", info.get("address", ""))
            row = {"房屋名稱": house_name}
            for field in fields:
                row[field] = summary.get(field, "")
            house_rows.append(row)
        self._add_pdf_section(story, "1. 房屋本體分析摘要", self._pdf_table_from_df(pd.DataFrame(house_rows), ["房屋名稱"] + fields, styles, 20), styles)
        
        stat_rows = []
        if not df.empty:
            for house_name, group in df.groupby("房屋"):
                if "主要類別" in group.columns:
                    normal_count = len(group[group["主要類別"] != "嫌惡設施"])
                    nuisance_count = len(group[group["主要類別"] == "嫌惡設施"])
                else:
                    normal_count = len(group)
                    nuisance_count = 0
                stat_rows.append({"房屋名稱": house_name, "一般設施數": normal_count, "嫌惡設施數": nuisance_count, "總數": len(group)})
        self._add_pdf_section(story, "2. 設施統計", self._pdf_table_from_df(pd.DataFrame(stat_rows), ["房屋名稱", "一般設施數", "嫌惡設施數", "總數"], styles, 30), styles)
        
        if not df.empty and include_nuisance and "主要類別" in df.columns:
            normal_df = df[df["主要類別"] != "嫌惡設施"].copy()
            nuisance_df = df[df["主要類別"] == "嫌惡設施"].copy()
        else:
            normal_df = df.copy()
            nuisance_df = pd.DataFrame()
        if not normal_df.empty:
            normal_df = normal_df.rename(columns={"房屋": "房屋名稱"}).copy()
            normal_df["Google地圖"] = normal_df.apply(self._build_maps_url, axis=1)
        self._add_pdf_section(story, "3. 一般設施總表", self._pdf_table_from_df(normal_df, ["房屋名稱", "主要類別", "設施子類別", "設施名稱", "距離(公尺)", "Google地圖"], styles, 40), styles)
        
        nuisance_summary_df = self._summarize_nuisance_by_type(df) if include_nuisance else pd.DataFrame()
        if not nuisance_summary_df.empty:
            nuisance_summary_df = nuisance_summary_df.rename(columns={"房屋": "房屋名稱"}).copy()
            nuisance_summary_df["Google地圖"] = nuisance_summary_df.apply(self._build_maps_url, axis=1)
        self._add_pdf_section(story, "4. 嫌惡設施摘要", self._pdf_table_from_df(nuisance_summary_df, ["房屋名稱", "嫌惡設施類型", "影響分類", "最近設施名稱", "AI\u76f8\u95dc\u6027", "\u8a2d\u65bd\u7528\u9014", "AI\u8aaa\u660e", "最近距離(公尺)", "周圍數量", "提醒", "Google地圖"], styles, 40), styles)
        
        if not nuisance_df.empty:
            nuisance_df = nuisance_df.rename(columns={"房屋": "房屋名稱"}).copy()
            nuisance_df["Google地圖"] = nuisance_df.apply(self._build_maps_url, axis=1)
        self._add_pdf_section(story, "5. 嫌惡設施明細總表", self._pdf_table_from_df(nuisance_df, ["房屋名稱", "主要類別", "設施子類別", "設施名稱", "AI\u76f8\u95dc\u6027", "\u8a2d\u65bd\u7528\u9014", "AI\u8aaa\u660e", "距離(公尺)", "Google地圖"], styles, 60), styles)
        
        story.append(Paragraph("6. AI 智能分析", styles["Heading"]))
        story.append(Paragraph(self._pdf_clean_text(ai_text), styles["Body"]))
        doc.build(story)
        buffer.seek(0)
        return buffer.getvalue()
    
    def _html_escape(self, value):
        """Escape text for HTML report output."""
        if value is None:
            return ""
        return str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    
    def _html_table_from_df(self, df, columns, max_rows=80):
        """Create an HTML table from selected DataFrame columns."""
        if df is None or df.empty:
            return '<p class="empty">\u7121\u8cc7\u6599</p>'
        available = [c for c in columns if c in df.columns]
        if not available:
            return '<p class="empty">\u7121\u8cc7\u6599</p>'
        table_df = df[available].head(max_rows).copy()
        thead = "".join(f"<th>{self._html_escape(c)}</th>" for c in available)
        rows = []
        for _, row in table_df.iterrows():
            cells = []
            for col in available:
                value = row.get(col, "")
                if col == "\u0047\u006f\u006f\u0067\u006c\u0065\u5730\u5716" and value:
                    cells.append(f'<td><a class="map-link" href="{self._html_escape(value)}" target="_blank">\u958b\u555f\u5730\u5716</a></td>')
                elif col in ["\u4e3b\u8981\u985e\u5225", "\u8a2d\u65bd\u5b50\u985e\u5225", "\u5acc\u60e1\u8a2d\u65bd\u985e\u578b", "\u5f71\u97ff\u5206\u985e"] and value:
                    cells.append(f'<td><span class="badge">{self._html_escape(value)}</span></td>')
                else:
                    cells.append(f"<td>{self._html_escape(value)}</td>")
            rows.append("<tr>" + "".join(cells) + "</tr>")
        note = ""
        if len(df) > max_rows:
            note = f'<p class="note">\u50c5\u5217\u51fa\u524d {max_rows} \u7b46\uff0c\u5171 {len(df)} \u7b46\u8cc7\u6599\u3002</p>'
        return f'<div class="table-wrap"><table><thead><tr>{thead}</tr></thead><tbody>{"".join(rows)}</tbody></table></div>{note}'
    
    def _generate_html_report(self, res, ai_text):
        """Generate a standalone HTML report directly from analysis data."""
        profile = res.get("buyer_profile", "\u672a\u6307\u5b9a")
        generated_at = get_taiwan_time()
        include_nuisance = res.get("include_nuisance", False)
        df = res.get("facilities_table", pd.DataFrame())
        house_rows = []
        fields = ["\u6a19\u984c", "\u5730\u5740", "\u5c4b\u9f61", "\u985e\u578b", "\u5efa\u576a", "\u4e3b+\u967d", "\u683c\u5c40", "\u6a13\u5c64", "\u8eca\u4f4d", "\u7e3d\u50f9(\u842c)", "\u884c\u653f\u5340"]
        for house_name, info in res.get("houses_data", {}).items():
            summary = dict(info.get("property_summary") or {})
            summary.setdefault("\u6a19\u984c", info.get("title", house_name))
            summary.setdefault("\u5730\u5740", info.get("address", ""))
            row = {"\u623f\u5c4b\u540d\u7a31": house_name}
            for field in fields:
                row[field] = summary.get(field, "")
            house_rows.append(row)
        house_df = pd.DataFrame(house_rows)
        stat_rows = []
        if not df.empty:
            for house_name, group in df.groupby("\u623f\u5c4b"):
                if "\u4e3b\u8981\u985e\u5225" in group.columns:
                    normal_count = len(group[group["\u4e3b\u8981\u985e\u5225"] != "\u5acc\u60e1\u8a2d\u65bd"])
                    nuisance_count = len(group[group["\u4e3b\u8981\u985e\u5225"] == "\u5acc\u60e1\u8a2d\u65bd"])
                else:
                    normal_count = len(group)
                    nuisance_count = 0
                stat_rows.append({"\u623f\u5c4b\u540d\u7a31": house_name, "\u4e00\u822c\u8a2d\u65bd\u6578": normal_count, "\u5acc\u60e1\u8a2d\u65bd\u6578": nuisance_count, "\u7e3d\u6578": len(group)})
        stat_df = pd.DataFrame(stat_rows)
        if not df.empty and include_nuisance and "\u4e3b\u8981\u985e\u5225" in df.columns:
            normal_df = df[df["\u4e3b\u8981\u985e\u5225"] != "\u5acc\u60e1\u8a2d\u65bd"].copy()
            nuisance_df = df[df["\u4e3b\u8981\u985e\u5225"] == "\u5acc\u60e1\u8a2d\u65bd"].copy()
        else:
            normal_df = df.copy()
            nuisance_df = pd.DataFrame()
        if not normal_df.empty:
            normal_df = normal_df.rename(columns={"\u623f\u5c4b": "\u623f\u5c4b\u540d\u7a31"}).copy()
            normal_df["Google\u5730\u5716"] = normal_df.apply(self._build_maps_url, axis=1)
        if not nuisance_df.empty:
            nuisance_detail_df = nuisance_df.rename(columns={"\u623f\u5c4b": "\u623f\u5c4b\u540d\u7a31"}).copy()
            nuisance_detail_df["Google\u5730\u5716"] = nuisance_detail_df.apply(self._build_maps_url, axis=1)
        else:
            nuisance_detail_df = pd.DataFrame()
        nuisance_summary_df = self._summarize_nuisance_by_type(df) if include_nuisance else pd.DataFrame()
        if not nuisance_summary_df.empty:
            nuisance_summary_df = nuisance_summary_df.rename(columns={"\u623f\u5c4b": "\u623f\u5c4b\u540d\u7a31"}).copy()
            nuisance_summary_df["Google\u5730\u5716"] = nuisance_summary_df.apply(self._build_maps_url, axis=1)
        sections = [
            ("1. \u623f\u5c4b\u672c\u9ad4\u5206\u6790\u6458\u8981", self._html_table_from_df(house_df, ["\u623f\u5c4b\u540d\u7a31"] + fields, 30)),
            ("2. \u8a2d\u65bd\u7d71\u8a08", self._html_table_from_df(stat_df, ["\u623f\u5c4b\u540d\u7a31", "\u4e00\u822c\u8a2d\u65bd\u6578", "\u5acc\u60e1\u8a2d\u65bd\u6578", "\u7e3d\u6578"], 50)),
            ("3. \u4e00\u822c\u8a2d\u65bd\u7e3d\u8868", self._html_table_from_df(normal_df, ["\u623f\u5c4b\u540d\u7a31", "\u4e3b\u8981\u985e\u5225", "\u8a2d\u65bd\u5b50\u985e\u5225", "\u8a2d\u65bd\u540d\u7a31", "\u8ddd\u96e2(\u516c\u5c3a)", "Google\u5730\u5716"], 120)),
            ("4. \u5acc\u60e1\u8a2d\u65bd\u6458\u8981", self._html_table_from_df(nuisance_summary_df, ["\u623f\u5c4b\u540d\u7a31", "\u5acc\u60e1\u8a2d\u65bd\u985e\u578b", "\u5f71\u97ff\u5206\u985e", "\u6700\u8fd1\u8a2d\u65bd\u540d\u7a31", "AI\u76f8\u95dc\u6027", "\u8a2d\u65bd\u7528\u9014", "AI\u8aaa\u660e", "\u6700\u8fd1\u8ddd\u96e2(\u516c\u5c3a)", "\u5468\u570d\u6578\u91cf", "\u63d0\u9192", "Google\u5730\u5716"], 80)),
            ("5. \u5acc\u60e1\u8a2d\u65bd\u660e\u7d30\u7e3d\u8868", self._html_table_from_df(nuisance_detail_df, ["\u623f\u5c4b\u540d\u7a31", "\u4e3b\u8981\u985e\u5225", "\u8a2d\u65bd\u5b50\u985e\u5225", "\u8a2d\u65bd\u540d\u7a31", "AI\u76f8\u95dc\u6027", "\u8a2d\u65bd\u7528\u9014", "AI\u8aaa\u660e", "\u8ddd\u96e2(\u516c\u5c3a)", "Google\u5730\u5716"], 120)),
            ("6. AI \u667a\u80fd\u5206\u6790", f'<div class="ai-text">{self._html_escape(ai_text).replace(chr(10), "<br>")}</div>'),
        ]
        section_html = "".join(f'<section class="card"><h2>{self._html_escape(title)}</h2>{body}</section>' for title, body in sections)
        return f"""<!DOCTYPE html>
<html lang="zh-Hant">
<head><meta charset="utf-8"><title>\u623f\u5c4b\u5206\u6790\u5831\u544a</title>
<style>
body {{ margin: 0; background: #ffffff; color: #1f2937; font-family: "Noto Sans TC", "Microsoft JhengHei", "PingFang TC", Arial, sans-serif; line-height: 1.6; }}
.container {{ max-width: 1180px; margin: 0 auto; padding: 32px 24px; }}
.cover {{ border-bottom: 3px solid #2563eb; margin-bottom: 24px; padding-bottom: 18px; }}
h1 {{ margin: 0 0 12px; font-size: 32px; color: #111827; }} h2 {{ margin: 0 0 16px; font-size: 22px; color: #111827; }}
.meta {{ color: #4b5563; margin: 4px 0; }}
.card {{ background: #ffffff; border: 1px solid #e5e7eb; border-radius: 10px; box-shadow: 0 2px 10px rgba(15, 23, 42, 0.06); padding: 22px; margin: 20px 0; }}
.table-wrap {{ overflow-x: auto; }} table {{ border-collapse: collapse; width: 100%; font-size: 14px; }}
th, td {{ border: 1px solid #d1d5db; padding: 8px 10px; vertical-align: top; }} th {{ background: #f3f4f6; font-weight: 700; text-align: left; }}
.badge {{ display: inline-block; border-radius: 999px; padding: 3px 9px; background: #e0f2fe; color: #075985; font-size: 12px; font-weight: 700; }}
.map-link {{ color: #2563eb; font-weight: 700; text-decoration: none; }} .map-link:hover {{ text-decoration: underline; }}
.note, .empty {{ color: #6b7280; font-size: 13px; }} .ai-text {{ white-space: normal; font-size: 15px; }}
</style></head>
<body><div class="container"><header class="cover"><h1>\u623f\u5c4b\u5206\u6790\u5831\u544a</h1><p class="meta">\u751f\u6210\u6642\u9593\uff1a{self._html_escape(generated_at)}</p><p class="meta">\u8cb7\u5bb6\u985e\u578b\uff1a{self._html_escape(profile)}</p></header>{section_html}</div></body></html>"""
    
    def _display_ai_analysis(self, res):
        """AI 分析"""
        st.markdown("---")
        st.subheader("🤖 AI 智能分析")
        
        profile = res.get("buyer_profile", "未指定")
        mode = res["analysis_mode"]
        include_nuisance = res.get("include_nuisance", False)
        nuisance_summary = res.get("nuisance_summary", {}) or {}
        profiles = self._get_buyer_profiles()
        pinfo = profiles.get(profile, {})
        icon = pinfo.get("icon", "👤")
        
        facilities_text, nuisance_text = self._format_facilities_for_prompt(res, include_nuisance)
        facilities_text = facilities_text + "\n" + self._format_real_price_for_prompt(res)
        
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
                prompt = self._build_single_with_nuisance_prompt(res, facilities_text, nuisance_text, depth_texts, nuisance_summary, profile, icon, pinfo)
            else:
                prompt = self._build_single_without_nuisance_prompt(res, facilities_text, depth_texts, profile, icon, pinfo)
        else:
            if include_nuisance:
                prompt = self._build_multi_with_nuisance_prompt(res, facilities_text, nuisance_text, depth_texts, nuisance_summary, profile, icon, pinfo)
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
                st.markdown("⚠️ **此分析包含嫌惡設施資訊揭露**")
                if nuisance_summary:
                    for name, count in nuisance_summary.items():
                        st.markdown(f"{name}：找到 {count} 處嫌惡設施")
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
            
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                if st.button("🔄 重新分析", use_container_width=True, key="reanalyze"):
                    del st.session_state.gemini_result
                    del st.session_state.used_prompt
                    st.rerun()
            report_title = f"{profile}視角-{'含嫌惡設施' if include_nuisance else '生活機能'}報告"
            if mode != "單一房屋分析":
                report_title = f"{profile}視角-{res['num_houses']}間房屋{'含嫌惡設施' if include_nuisance else '生活機能'}比較報告"
            report_time = datetime.now().strftime('%Y%m%d_%H%M%S')
            report = f"{report_title}\n生成時間：{get_taiwan_time()}\n\nAI 分析結果：\n{st.session_state.gemini_result}"
            with c2:
                st.download_button(label="📥 下載 TXT 報告", data=report, file_name=f"{report_title}_{report_time}.txt", mime="text/plain", use_container_width=True, key="download_report")
            with c3:
                pdf_bytes = self._generate_pdf_report(res, st.session_state.gemini_result)
                if pdf_bytes:
                    st.download_button(
                        label="📄 下載 PDF 報告",
                        data=pdf_bytes,
                        file_name=f"房屋分析報告_{report_time}.pdf",
                        mime="application/pdf",
                        use_container_width=True,
                        key="download_pdf_report",
                    )
                else:
                    st.caption("PDF 匯出需要安裝 reportlab")
            with c4:
                html_report = self._generate_html_report(res, st.session_state.gemini_result)
                st.download_button(
                    label="🌐 下載 HTML 報告",
                    data=html_report,
                    file_name=f"房屋分析報告_{report_time}.html",
                    mime="text/html",
                    use_container_width=True,
                    key="download_html_report",
                )
    
    def _format_facilities_for_prompt(self, res, include_nuisance=False):
        """格式化設施資料供提示詞使用；嫌惡設施提供分類摘要，不提供分數"""
        df = res.get("facilities_table", pd.DataFrame())
        if df.empty:
            return "無周邊設施資料", ""

        if include_nuisance and '主要類別' in df.columns:
            normal_df = df[df['主要類別'] != "嫌惡設施"].copy()
            nuisance_df = df[df['主要類別'] == "嫌惡設施"].copy()
        else:
            normal_df = df.copy()
            nuisance_df = pd.DataFrame()

        normal_text = "\n【一般設施清單】\n" + "=" * 60 + "\n"
        if normal_df.empty:
            normal_text += "無一般設施資料\n"
        else:
            for house_name in normal_df['房屋'].unique():
                house_df = normal_df[normal_df['房屋'] == house_name]
                normal_text += f"\n🏠 {house_name} 周邊一般設施（共 {len(house_df)} 個）：\n" + "-" * 50 + "\n"
                house_df_sorted = house_df.sort_values('距離(公尺)')
                for i, row in house_df_sorted.iterrows():
                    normal_text += f"  {i+1}. {row['設施名稱']} ({row['設施子類別']}) - {row['距離(公尺)']}公尺\n"

        nuisance_text = ""
        if not nuisance_df.empty:
            summary_df = self._summarize_nuisance_by_type(df)
            nuisance_text = "\n【⚠️ 嫌惡設施摘要（不使用分數）】\n" + "=" * 60 + "\n"
            for house_name in summary_df['房屋'].unique():
                house_df = summary_df[summary_df['房屋'] == house_name]
                nuisance_text += f"\n🏠 {house_name} 周邊嫌惡設施摘要（共 {len(house_df)} 類）：\n" + "-" * 50 + "\n"
                for i, row in house_df.iterrows():
                    nuisance_text += (
                        f"  {i+1}. {row['嫌惡設施類型']}｜"
                        f"影響分類：{row['影響分類']}｜"
                        f"最近：{row['最近設施名稱']}｜"
                        f"距離：{row['最近距離(公尺)']}公尺｜"
                        f"周圍數量：{row['周圍數量']}處｜"
                    )

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

    def _build_single_with_nuisance_prompt(self, res, facilities_text, nuisance_text, depth_texts, nuisance_summary, profile, icon, pinfo):
        """單一房屋有嫌惡設施的提示詞：不使用分數，只根據距離、數量與類型分析"""
        name = list(res["houses_data"].keys())[0]
        h = res["houses_data"][name]
        focus = pinfo.get("prompt_focus", [])
        depth_text = depth_texts.get(name, "")
        nuisance_count = nuisance_summary.get(name, 0)
        
        return f"""
你是一位專業的房地產分析師，請以「{icon} {profile}」的身份，對以下房屋進行綜合分析。此分析包含嫌惡設施資訊揭露，但不要使用風險分數。

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

【嫌惡設施概況】
- 周邊共找到 {nuisance_count} 處嫌惡設施
- 本系統不使用嫌惡設施分數，請勿自行產生任何嫌惡設施分數、百分比或等級分數。
- 請只根據「嫌惡設施類型、影響分類、最近距離、周圍數量、買家類型接受度」做保守文字判斷。
- 判斷用語請使用：「影響較低 / 需留意 / 建議現場確認 / 需謹慎評估」。

{facilities_text}
{nuisance_text}

請根據【房屋深度分析】、【一般設施清單】和【嫌惡設施清單】綜合評估，提供以下分析：

1. **整體居住適合度**：不用分數，改用「適合 / 可考慮 / 需謹慎」描述。
2. **主要優點**（3-5點）
3. **主要缺點**（3-5點）：必須說明最近嫌惡設施、距離與可能影響。
4. **生活便利性判斷**
5. **嫌惡設施提醒**：列出最需要現場確認的項目。
6. **購買建議**：給出是否值得看屋、是否需要議價或避開的建議。

請用專業、客觀、保守的角度分析。
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

    def _build_multi_with_nuisance_prompt(self, res, facilities_text, nuisance_text, depth_texts, nuisance_summary, profile, icon, pinfo):
        """多房屋比較有嫌惡設施的提示詞：不使用分數，只根據距離、數量與類型比較"""
        houses_data = res["houses_data"]
        counts = res["facility_counts"]
        focus = pinfo.get("prompt_focus", [])
        
        house_list = "\n".join([f"- {n}：{h['title'][:30]}..." for n, h in houses_data.items()])
        comparison_rows = [f"  {name}：{cnt} 個設施" for name, cnt in counts.items()]
        comparison_text = "\n".join(comparison_rows)
        
        nuisance_count_text = "\n【各房屋嫌惡設施數量】\n"
        for name in houses_data.keys():
            nuisance_count_text += f"- {name}：{nuisance_summary.get(name, 0)} 處\n"
        
        depth_section = "\n【各房屋深度分析】\n"
        for name in houses_data.keys():
            if name in depth_texts:
                depth_section += f"\n{name}{depth_texts[name]}"
        
        return f"""
你是一位專業的房地產分析師，請比較以下{len(houses_data)}間房屋，並以「{icon} {profile}」的身份給出建議。此分析包含嫌惡設施資訊揭露，但不要使用風險分數。

【買家類型】
{profile} - {pinfo.get('description', '')}
重點關注：{', '.join(focus)}
{depth_section}
【候選房屋】
{house_list}

【各房屋設施數量】
{comparison_text}

{nuisance_count_text}

{facilities_text}
{nuisance_text}

請根據【各房屋深度分析】、【一般設施清單】和【嫌惡設施摘要】綜合比較，提供以下分析：

重要規則：本系統不使用嫌惡設施分數，請勿自行產生任何嫌惡設施分數、百分比或等級分數。請只根據「嫌惡設施類型、影響分類、最近距離、周圍數量、買家類型接受度」做保守文字判斷。

1. **綜合排名**：不用嫌惡設施分數，改用距離、數量、類型、影響分類與買家需求判斷。
2. **各房屋優缺點比較表**
3. **嫌惡設施比較**：列出每間房屋最近的嫌惡設施、距離與數量。
4. **生活便利性比較**
5. **最終推薦**
6. **看屋提醒與議價建議**

請用專業、客觀、保守的角度分析。
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
                model = genai.GenerativeModel("gemini-flash-latest")
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
