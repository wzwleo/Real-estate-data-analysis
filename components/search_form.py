import streamlit as st
import os
import pandas as pd
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

        st.subheader("🛠️特殊要求（可輸入文字，如：一房二廳一衛以上，低樓層）")
        Special_Requests = st.text_area("特殊要求", placeholder="例：一房二廳一衛以上，低樓層")

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


import streamlit as st
import google.generativeai as genai
import json
import re
from utils import filter_properties, load_data

def handle_search_submit(filters, Special_Requests):
    gemini_key = st.session_state.get("GEMINI_KEY", "")
    parsed_req = {}

    # === Step 1: 如果使用者輸入了特殊要求，呼叫 Gemini ===
    if Special_Requests and gemini_key:
        try:
            genai.configure(api_key=gemini_key)
            model = genai.GenerativeModel("gemini-2.0-flash")

            prompt = f"""
            你是一位房產資料分析助理。
            使用者輸入的需求是：「{Special_Requests}」。
            請解析成純 JSON 格式，不要任何說明文字。
            若無法判斷某項，該欄位請省略。
            JSON 結構如下：
            {{
              "房間數": 整數或 {{ "min": 最小值, "max": 最大值 }},
              "廳數": 整數或 {{ "min": 最小值, "max": 最大值 }},
              "衛數": 整數或 {{ "min": 最小值, "max": 最大值 }},
              "樓層": 整數或 {{ "min": 最小值, "max": 最大值 }}
            }}
            範例：
            {{
              "房間數": 2,
              "廳數": 1,
              "衛數": 1,
              "樓層": {{"min": 1, "max": 5}}
            }}
            """

            response = model.generate_content(prompt)
            text = response.text.strip()

            # === Step 2: 嘗試抓出 JSON 部分 ===
            match = re.search(r"\{[\s\S]*\}", text)
            if match:
                json_text = match.group()
                json_text = json_text.replace("：", ":")  # 修正中文冒號
                parsed_req = json.loads(json_text)
            else:
                st.warning("⚠️ Gemini 回傳格式不含 JSON，已略過智能解析。")

        except Exception as e:
            st.error(f"❌ Gemini 解析特殊要求失敗: {e}")
            st.write("🪄 原始回傳內容：")
            st.code(locals().get("text", "(無內容)"), language="json")

    # === Step 3: 載入資料並篩選 ===
    df = load_data()
    filters.update({
        "rooms": parsed_req.get("房間數"),
        "living_rooms": parsed_req.get("廳數"),
        "bathrooms": parsed_req.get("衛數"),
        "floor": parsed_req.get("樓層"),
    })

    filtered_df = filter_properties(df, filters)
    st.session_state["filtered_df"] = filtered_df

    if not filtered_df.empty:
        st.success(f"✅ 找到 {len(filtered_df)} 筆符合條件的房產。")
    else:
        st.warning("😅 沒有找到符合條件的房產，請嘗試修改條件。")
