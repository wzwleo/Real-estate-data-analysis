import streamlit as st
import pandas as pd
from utils import filter_properties

def render_search_form(property_df):

    with st.form("property_requirements"):
        st.subheader("📍 房產篩選條件")

        # 房型
        housetype_options = ["不限", "大樓", "透天", "公寓"]
        housetype = st.selectbox("房型", housetype_options)

        # 價格
        col1, col2 = st.columns(2)
        budget_min = col1.number_input("最低預算（萬）", min_value=0, value=0)
        budget_max = col2.number_input("最高預算（萬）", min_value=0, value=0)

        # 屋齡
        col3, col4 = st.columns(2)
        age_min = col3.number_input("屋齡下限", min_value=0, value=0)
        age_max = col4.number_input("屋齡上限 (0 表示不限)", min_value=0, value=0)

        # 建坪
        col5, col6 = st.columns(2)
        area_min = col5.number_input("建坪下限", min_value=0.0, value=0.0)
        area_max = col6.number_input("建坪上限 (0 表示不限)", min_value=0.0, value=0.0)

        # 車位
        car_grip = st.selectbox("車位需求", ["不限", "需要", "不要"])

        submitted = st.form_submit_button("搜尋房產")

        if submitted:
            filters = {
                "housetype": housetype,
                "budget_min": float(budget_min),
                "budget_max": float(budget_max) if budget_max > 0 else float('inf'),
                "age_min": float(age_min),
                "age_max": float(age_max) if age_max > 0 else float('inf'),
                "area_min": float(area_min),
                "area_max": float(area_max) if area_max > 0 else float('inf'),
                "car_grip": car_grip
            }

            result_df = filter_properties(property_df, filters)
            handle_search_submit(result_df)


def handle_search_submit(result_df):

    st.subheader("📊 搜尋結果")

    if result_df.empty:
        st.warning("😅 沒有找到符合條件的房產，請調整條件看看！")
        return

    # 顯示統計
    st.success(f"共找到 {len(result_df)} 筆房產資料")

    # 顯示結果表
    st.dataframe(result_df)
