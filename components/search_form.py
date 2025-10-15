import streamlit as st
import os
import pandas as pd
import google.generativeai as genai
from utils import get_city_options, filter_properties

def interpret_special_request(request_text, gemini_key):
    """使用 Gemini 將自然語言轉為可用的篩選條件"""
    if not request_text.strip():
        return {}

    try:
        genai.configure(api_key=gemini_key)
        model = genai.GenerativeModel("gemini-2.0-flash")
        prompt = f"""
        你是一個房地產資料篩選助理。
        請根據使用者的描述（中文）輸出結構化的 JSON 篩選條件，格式如下：

        {{
          "room_min": int 或 null,
          "room_max": int 或 null,
          "living_min": int 或 null,
          "living_max": int 或 null,
          "bath_min": int 或 null,
          "bath_max": int 或 null,
          "floor_min": int 或 null,
          "floor_max": int 或 null
        }}

        若描述中沒有提到該項，值請設為 null。
        以下是使用者輸入的文字：
        「{request_text}」
        """

        response = model.generate_content(prompt)
        import json
        result = json.loads(response.text)
        return result
    except Exception as e:
        st.warning(f"⚠️ 無法解析特殊需求：{e}")
        return {}

def render_search_form():
    """渲染搜尋表單並處理提交邏輯"""
    with st.form("property_requirements"):
        st.subheader("📍 房產篩選條件")
        
        housetype = ["不限", "大樓", "華廈", "公寓", "套房", "透天", "店面", "辦公", "別墅", "倉庫", "廠房", "土地", "單售車位", "其它"]
        options = get_city_options()
        col1, col2 = st.columns([1, 1])
        with col1:
            selected_label = st.selectbox("請選擇城市：", list(options.keys()))
            housetype_change = st.selectbox("請選擇房產類別：", housetype, key="housetype")
                     
        with col2:
            budget_max = st.number_input("💰預算上限(萬)", 0, 1000000, 1000000, step=100)
            budget_min = st.number_input("💰預算下限(萬)", 0, 1000000, 0, step=100)
            if budget_min > budget_max and budget_max > 0:
                st.error("⚠️ 預算下限不能大於上限！")

        st.subheader("🎯 房產要求細項")
        col1, col2, col3 = st.columns([1, 1, 1])
        with col1:
            age_max = st.number_input("屋齡上限", 0, 100, 100, step=1)
            age_min = st.number_input("屋齡下限", 0, 100, 0, step=1)
            if age_min > age_max:
                st.error("⚠️ 屋齡下限不能大於上限！")
                
        with col2:
            area_max = st.number_input("建坪上限", 0, 1000, 1000, step=10)
            area_min = st.number_input("建坪下限", 0, 1000, 0, step=10)
            if area_min > area_max:
                st.error("⚠️ 建坪下限不能大於上限！")
                
        with col3:
            car_grip = st.selectbox("🅿️ 車位選擇", ["不限", "需要","不要"], key="car_grip")
        
        st.subheader("🛠️ 特殊要求（自然語言）")
        Special_Requests = st.text_area("請輸入需求，如：'兩房一廳一衛以上，高樓層'", placeholder="輸入文字...")
        
        submit = st.form_submit_button("搜尋", use_container_width=True)
        
        if submit:
            return handle_search_submit(
                selected_label, options, housetype_change,
                budget_min, budget_max, age_min, age_max,
                area_min, area_max, car_grip, Special_Requests
            )

def handle_search_submit(selected_label, options, housetype_change,
                        budget_min, budget_max, age_min, age_max,
                        area_min, area_max, car_grip, special_requests):
    """處理搜尋表單提交"""
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
    
    if not valid_input:
        return False

    selected_file = options[selected_label]
    file_path = os.path.join("./Data", selected_file)

    try:
        df = pd.read_csv(file_path)
        st.session_state.all_properties_df = df  # 儲存全部資料
        
        filters = {
            'housetype': housetype_change,
            'budget_min': budget_min,
            'budget_max': budget_max,
            'age_min': age_min,
            'age_max': age_max,
            'area_min': area_min,
            'area_max': area_max,
            'car_grip': car_grip
        }

        # 若有特殊需求文字，使用 Gemini 解析
        if special_requests.strip():
            gemini_key = st.session_state.get("GEMINI_KEY", "")
            if gemini_key:
                st.info("✨ Gemini 正在解析您的需求...")
                extracted = interpret_special_request(special_requests, gemini_key)
                filters.update(extracted)
                st.success(f"AI 解析結果：{extracted}")
            else:
                st.warning("⚠️ 未設定 Gemini API Key，略過智能分析。")

        filtered_df = filter_properties(df, filters)
        st.session_state.filtered_df = filtered_df
        st.session_state.search_params = {
            'city': selected_label,
            'housetype': housetype_change,
            'budget_range': f"{budget_min}-{budget_max}萬" if budget_max < 1000000 else f"{budget_min}萬以上",
            'age_range': f"{age_min}-{age_max}年" if age_max < 100 else f"{age_min}年以上",
            'area_range': f"{area_min}-{area_max}坪" if area_max < 1000 else f"{area_min}坪以上",
            'car_grip': car_grip,
            'special_requests': special_requests,
            'original_count': len(df),
            'filtered_count': len(filtered_df)
        }

        if len(filtered_df) == 0:
            st.warning("😅 沒有找到符合條件的房產，請調整篩選條件後重新搜尋")
        else:
            st.success(f"✅ 從 {len(df)} 筆資料中篩選出 {len(filtered_df)} 筆符合條件的房產")

        return True

    except Exception as e:
        st.error(f"❌ 發生錯誤：{e}")
        return False
