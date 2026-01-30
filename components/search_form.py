import os
import re
import pandas as pd
import streamlit as st
from utils import get_city_options, filter_properties


def render_search_form():
    """ 渲染搜尋表單並處理提交邏輯 """
    with st.form("property_requirements"):
        st.subheader("📍 房產篩選條件1")

        housetype = [
            "不限", "大樓", "華廈", "公寓", "套房", "透天", "店面",
            "辦公", "別墅", "倉庫", "廠房", "土地", "單售車位", "其它"
        ]
        options = get_city_options()

        col1, col2 = st.columns([1, 1])
        with col1:
            selected_label = st.selectbox("請選擇城市：", list(options.keys()))
            housetype_change = st.selectbox("請選擇房產類別：", housetype, key="housetype")
        with col2:
            budget_max = st.number_input("💰預算上限(萬)", 0, 1_000_000, 1_000_000, 100)
            budget_min = st.number_input("💰預算下限(萬)", 0, 1_000_000, 0, 100)

        if budget_min > budget_max and budget_max > 0:
            st.error("⚠️ 預算下限不能大於上限！")

        st.subheader("🎯 房產條件細項")
        col1, col2, col3 = st.columns([1, 1, 1])

        with col1:
            age_max = st.number_input("屋齡上限", 0, 100, 100, 1)
            age_min = st.number_input("屋齡下限", 0, 100, 0, 1)
            if age_min > age_max:
                st.error("⚠️ 屋齡下限不能大於上限！")

        with col2:
            area_max = st.number_input("建坪上限", 0, 1000, 1000, 10)
            area_min = st.number_input("建坪下限", 0, 1000, 0, 10)
            if area_min > area_max:
                st.error("⚠️ 建坪下限不能大於上限！")

        with col3:
            car_grip = st.selectbox("🅿️ 車位需求", ["不限", "需要", "不要"])

        submit = st.form_submit_button("搜尋", use_container_width=True)

        if submit:
            return handle_search_submit(
                selected_label, options, housetype_change,
                budget_min, budget_max,
                age_min, age_max,
                area_min, area_max,
                car_grip
            )
    return None


def handle_search_submit(
    selected_label, options, housetype_change,
    budget_min, budget_max,
    age_min, age_max,
    area_min, area_max,
    car_grip
):
    """處理搜尋表單提交（只做一般條件篩選）"""

    # 基本驗證
    if budget_min > budget_max and budget_max > 0:
        st.error("❌ 請修正預算範圍")
        return False
    if age_min > age_max:
        st.error("❌ 請修正屋齡範圍")
        return False
    if area_min > area_max:
        st.error("❌ 請修正建坪範圍")
        return False

    st.session_state.current_search_page = 1
    file_path = os.path.join("./Data", options[selected_label])

    try:
        df = pd.read_csv(file_path)

        # 屋齡處理
        if '屋齡' in df.columns:
            df['屋齡'] = (
                df['屋齡']
                .astype(str)
                .str.replace('年', '', regex=False)
                .replace('預售', '0')
            )
            df['屋齡'] = pd.to_numeric(df['屋齡'], errors='coerce').fillna(0)

        # 格局解析（房 / 廳 / 衛）
        def parse_layout(layout):
            if not isinstance(layout, str):
                return pd.Series([None, None, None])
            m = re.match(r'(\d+)房(\d+)廳(\d+)衛', layout)
            if m:
                return pd.Series(map(int, m.groups()))
            nums = re.findall(r'\d+', layout)
            nums += [None] * (3 - len(nums))
            return pd.Series(nums[:3])

        if '格局' in df.columns:
            df[['房間數', '廳數', '衛數']] = df['格局'].apply(parse_layout)

        # 一般篩選條件
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

        filtered_df = filter_properties(df, filters)

        st.session_state.filtered_df = filtered_df
        st.session_state.search_params = {
            'city': selected_label,
            'housetype': housetype_change,
            'original_count': len(df),
            'filtered_count': len(filtered_df)
        }

        if filtered_df.empty:
            st.warning("😅 沒有找到符合條件的房產")
        else:
            st.success(f"✅ 從 {len(df)} 筆資料中篩選出 {len(filtered_df)} 筆")

        return True

    except FileNotFoundError:
        st.error(f"❌ 找不到檔案：{file_path}")
    except Exception as e:
        st.error(f"❌ 讀取資料發生錯誤：{e}")

    return False
