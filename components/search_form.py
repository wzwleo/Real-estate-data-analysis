import streamlit as st
import os
import pandas as pd
import google.generativeai as genai
import json
from utils import get_city_options, filter_properties


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
            budget_max = st.number_input("💰預算上限(萬)", min_value=0, max_value=1000000, value=1000000, step=100)
            budget_min = st.number_input("💰預算下限(萬)", min_value=0, max_value=1000000, value=0, step=100)
            if budget_min > budget_max and budget_max > 0:
                st.error("⚠️ 預算下限不能大於上限！")

        st.subheader("🎯 房產要求細項")
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
            car_grip = st.selectbox("🅿️ 車位選擇", ["不限", "需要", "不要"], key="car_grip")

        st.subheader("🛠️ 特殊要求")
        Special_Requests = st.text_area("請輸入您的需求", placeholder="例如：兩房一廳一衛、高樓層、屋齡低於10年...")

        submit = st.form_submit_button("搜尋", use_container_width=True)

        if submit:
            return handle_search_submit(
                selected_label, options, housetype_change,
                budget_min, budget_max, age_min, age_max,
                area_min, area_max, car_grip, Special_Requests
            )

    return None


def handle_search_submit(selected_label, options, housetype_change,
                         budget_min, budget_max, age_min, age_max,
                         area_min, area_max, car_grip, Special_Requests):

    gemini_key = st.session_state.get("GEMINI_KEY", "")
    if not gemini_key:
        st.error("❌ 尚未設定 Gemini API Key，請到側邊欄設定後再試。")
        return False

    # 驗證基本輸入
    if budget_min > budget_max or age_min > age_max or area_min > area_max:
        st.error("❌ 請檢查範圍設定是否正確。")
        return False

    st.session_state.current_search_page = 1
    selected_file = options[selected_label]
    file_path = os.path.join("./Data", selected_file)

    try:
        df = pd.read_csv(file_path)

        # 嘗試轉換常見數值欄位，避免 str 比較錯誤
        numeric_cols = ['總價(萬)', '屋齡', '建坪', '主+陽', '樓層']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')

        # 🔹 呼叫 Gemini 解析特殊需求
        genai.configure(api_key=gemini_key)
        model = genai.GenerativeModel("gemini-2.0-flash")

        prompt = f"""
        你是一個房地產搜尋助理，請根據使用者的特殊需求輸出 JSON 結構。
        格式範例：
        輸入「兩房一廳一衛」→ 輸出 {{"rooms": 2, "living_rooms": 1, "bathrooms": 1}}
        輸入「三房以上、一廳一衛、高樓層」→ 輸出 {{"rooms_min": 3, "living_rooms": 1, "bathrooms": 1, "floor_min": 7}}
        只回傳 JSON，不要多餘文字。

        使用者輸入：{Special_Requests}
        """

        with st.spinner("Gemini 正在解析您的需求..."):
            response = model.generate_content(prompt)

        try:
            ai_data = json.loads(response.text.strip())
            st.success("✅ 特殊需求解析完成！")
            st.write("AI 解析結果：", ai_data)
        except Exception as e:
            st.warning(f"⚠️ 無法解析 AI 回傳內容：{e}")
            st.write("原始 AI 回覆：", response.text)
            ai_data = {}

        # 整合篩選條件
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

        # 🔹 加入 AI 特殊條件
        filters.update(ai_data)

        # 執行篩選
        filtered_df = filter_properties(df, filters)

        # 儲存狀態
        st.session_state.filtered_df = filtered_df
        st.session_state.search_params = {
            'city': selected_label,
            'housetype': housetype_change,
            'budget_range': f"{budget_min}-{budget_max}萬",
            'age_range': f"{age_min}-{age_max}年",
            'area_range': f"{area_min}-{area_max}坪",
            'car_grip': car_grip,
            'special_request': Special_Requests,
            'filtered_count': len(filtered_df)
        }

        if len(filtered_df) == 0:
            st.warning("😅 沒有找到符合條件的房產，請嘗試修改條件。")
        else:
            st.success(f"✅ 從 {len(df)} 筆資料中篩選出 {len(filtered_df)} 筆符合條件的房產")

        return True

    except FileNotFoundError:
        st.error(f"❌ 找不到檔案: {file_path}")
    except Exception as e:
        st.error(f"❌ 搜尋過程發生錯誤：{e}")

    return False
