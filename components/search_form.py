import os
import re
import json
import pandas as pd
import streamlit as st
import google.generativeai as genai
from utils import get_city_options, filter_properties 

def render_search_form():
    """ 渲染搜尋表單並處理提交邏輯 """
    with st.form("property_requirements"):
        st.subheader("📍 房產篩選條件")
        housetype = ["不限", "大樓", "華廈", "公寓", "套房", "透天", "店面", "辦公", "別墅", "倉庫", "廠房", "土地", "單售車位", "其它"]
        options = get_city_options()

        col1, col2 = st.columns([1, 1])
        with col1:
            selected_label = st.selectbox("請選擇城市：", list(options.keys()))
            housetype_change = st.selectbox("請選擇房產類別：", housetype, key="housetype")
        with col2:
            budget_max = st.number_input("💰預算上限(萬)", min_value=0, max_value=1000000, value=1000000, step=100)
            budget_min = st.number_input("💰預算下限(萬)", min_value=0, max_value=1000000, value=0, step=100)

        if budget_min > budget_max and budget_max > 0:
            st.error("⚠️ 預算下限不能大於上限！")

        st.subheader("🎯房產要求細項")
        col1, col2, col3 = st.columns([1, 1, 1])
        with col1:
            age_max = st.number_input("屋齡上限", min_value=0, max_value=100, value=100, step=1)
            age_min = st.number_input("屋齡下限", min_value=0, max_value=100, value=0, step=1)
            if age_min > age_max:
                st.error("⚠️ 屋齡下限不能大於上限！")
        with col2:
            area_max = st.number_input("建坪上限", min_value=0, max_value=1000, value=1000, step=10)
            area_min = st.number_input("建坪下限", min_value=0, max_value=1000, value=0, step=10)
            if area_min > area_max:
                st.error("⚠️ 建坪下限不能大於上限！")
        with col3:
            car_grip = st.selectbox("🅿️車位選擇", ["不限", "需要", "不要"], key="car_grip")

        st.subheader("🛠️特殊要求（如：三房二廳二衛）")
        Special_Requests = st.text_area("特殊要求", placeholder="請輸入要求(自動包含以上)")

        col1, col2, col3, col4, col5 = st.columns([1, 1, 1, 1, 1])
        with col3:
            submit = st.form_submit_button("搜尋", use_container_width=True)

        if submit:
            return handle_search_submit(
                selected_label, options, housetype_change,
                budget_min, budget_max, age_min, age_max, area_min, area_max, car_grip,
                Special_Requests
            )
    return None


def _extract_json_text(text: str):
    """嘗試從回傳文字抓出第一個 JSON 物件或陣列字串"""
    if not text:
        return None
    start = text.find('{')
    end = text.rfind('}')
    if start != -1 and end != -1 and end > start:
        return text[start:end+1]
    start = text.find('[')
    end = text.rfind(']')
    if start != -1 and end != -1 and end > start:
        return text[start:end+1]
    return None


def _normalize_value(val):
    """把單一欄位的解析結果轉成整數或區間 dict"""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return int(val)
    s = str(val).strip()
    if s == '':
        return None
    m = re.match(r'^\s*(\d+)\s*[-~–]\s*(\d+)\s*$', s)
    if m:
        return {"min": int(m.group(1)), "max": int(m.group(2))}
    m = re.search(r'(\d+)\s*(以上|\+|>=)', s)
    if m:
        return {"min": int(m.group(1))}
    m = re.search(r'(以下|<=)\s*(\d+)', s)
    if m:
        return {"max": int(m.group(2))}
    m = re.match(r'^\s*(\d+)\s*$', s)
    if m:
        return int(m.group(1))
    if '低' in s:
        return {"min": 1, "max": 5}
    if '高' in s:
        return {"min": 6}
    m = re.search(r'(\d+)', s)
    if m:
        return int(m.group(1))
    return None


def _normalize_parsed_req(parsed: dict):
    """把 Gemini 回傳的欄位（可能是中文或英文）轉成我們要的 keys"""
    if not parsed or not isinstance(parsed, dict):
        return {}

    out = {}
    keymap = {
        "房間數": "rooms", "rooms": "rooms", "房間": "rooms", "臥室": "rooms",
        "廳數": "living_rooms", "廳": "living_rooms", "living_rooms": "living_rooms",
        "衛數": "bathrooms", "衛": "bathrooms", "bathrooms": "bathrooms",
        "樓層": "floor", "floor": "floor"
    }

    for k, v in parsed.items():
        if not k:
            continue
        k_strip = k.strip()
        target = keymap.get(k_strip) or keymap.get(k_strip.lower())
        if not target:
            continue
        normalized = _normalize_value(v)
        if normalized is not None:
            out[target] = normalized
    return out


def handle_search_submit(selected_label, options, housetype_change,
                        budget_min, budget_max, age_min, age_max,
                        area_min, area_max, car_grip):
    """
    處理搜尋表單提交（使用浮點數進行篩選，避免型別錯誤）
    """
    # 驗證輸入
    valid_input = True
    if budget_min > budget_max and budget_max > 0:
        st.error("❌ 請修正預算範圍設定")
        valid_input = False
    if age_min > age_max:
        st.error("❌ 請修正屋齡範圍設定")
        valid_input = False
    if area_min > area_max:
        st.error("❌ 請修正建坪範圍設定")
        valid_input = False
    
    if valid_input:
        # 重置搜尋頁面到第一頁
        st.session_state.current_search_page = 1
        selected_file = options[selected_label]
        file_path = os.path.join("./Data", selected_file)
        
        try:
            # 讀取 CSV 檔案
            df = pd.read_csv(file_path)
            
            # 屋齡預處理：將 "預售" 視為 0，其餘轉為浮點數
            if '屋齡' in df.columns:
                df['屋齡'] = (
                    df['屋齡']
                    .astype(str)
                    .str.replace('年', '', regex=False)
                    .replace('預售', '0')
                )
                df['屋齡'] = pd.to_numeric(df['屋齡'], errors='coerce').fillna(0).astype(float)
            
            # 建坪處理：確保為浮點數
            if '建坪' in df.columns:
                df['建坪'] = pd.to_numeric(df['建坪'], errors='coerce').fillna(0).astype(float)
            
            # 總價處理：確保為浮點數
            if '總價(萬)' in df.columns:
                df['總價(萬)'] = pd.to_numeric(df['總價(萬)'], errors='coerce').fillna(0).astype(float)
            
            # 準備篩選條件
            filters = {
                'housetype': housetype_change,
                'budget_min': float(budget_min),
                'budget_max': float(budget_max),
                'age_min': float(age_min),
                'age_max': float(age_max),
                'area_min': float(area_min),
                'area_max': float(area_max),
                'car_grip': car_grip
            }
            
            # 執行篩選
            filtered_df = filter_properties(df, filters)
            
            # 儲存篩選後的資料到 session state
            st.session_state.filtered_df = filtered_df
            st.session_state.search_params = {
                'city': selected_label,
                'housetype': housetype_change,
                'budget_range': f"{budget_min}-{budget_max}萬" if budget_max < 1000000 else f"{budget_min}萬以上",
                'age_range': f"{age_min}-{age_max}年" if age_max < 100 else f"{age_min}年以上",
                'area_range': f"{area_min}-{area_max}坪" if area_max < 1000 else f"{area_min}坪以上",
                'car_grip': car_grip,
                'original_count': len(df),
                'filtered_count': len(filtered_df)
            }
            
            # 顯示篩選結果統計
            if len(filtered_df) == 0:
                st.warning("😅 沒有找到符合條件的房產，請調整篩選條件後重新搜尋")
            else:
                st.success(f"✅ 從 {len(df)} 筆資料中篩選出 {len(filtered_df)} 筆符合條件的房產")
            
            return True
                
        except FileNotFoundError:
            st.error(f"❌ 找不到檔案: {file_path}")
        except Exception as e:
            st.error(f"❌ 讀取 CSV 發生錯誤: {e}")
    
    return False
