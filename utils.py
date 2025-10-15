import os
import pandas as pd
import math
import streamlit as st

def get_city_options(data_dir="./Data"):
    """ 獲取城市選項，只顯示對照表內有定義的檔案 """
    if not os.path.exists(data_dir):
        return {}
    name_map = {
        "Taichung-city_buy_properties.csv": "台中市",
        "Taipei-city_buy_properties.csv": "台北市"
    }
    files = [f for f in os.listdir(data_dir) if f.endswith(".csv")]
    options = {name_map[f]: f for f in files if f in name_map}
    return dict(sorted(options.items(), key=lambda x: x[0]))


def filter_properties(df: pd.DataFrame, filters: dict) -> pd.DataFrame:
    """
    篩選房產資料
    filters 可能包含：
    - housetype
    - budget_min, budget_max
    - age_min, age_max
    - area_min, area_max
    - car_grip ("不限"/"需要"/"不要")
    """
    # 確保欄位都是數字型態
    for col in ['屋齡', '建坪', '總價(萬)']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(float)

    filtered = df.copy()

    # 房產類型
    if filters.get('housetype') and filters['housetype'] != "不限":
        filtered = filtered[filtered['房型'] == filters['housetype']]

    # 預算
    budget_min = filters.get('budget_min', 0)
    budget_max = filters.get('budget_max', float('inf'))
    filtered = filtered[(filtered['總價(萬)'] >= budget_min) & (filtered['總價(萬)'] <= budget_max)]

    # 屋齡
    age_min = filters.get('age_min', 0)
    age_max = filters.get('age_max', float('inf'))
    filtered = filtered[(filtered['屋齡'] >= age_min) & (filtered['屋齡'] <= age_max)]

    # 建坪
    area_min = filters.get('area_min', 0)
    area_max = filters.get('area_max', float('inf'))
    filtered = filtered[(filtered['建坪'] >= area_min) & (filtered['建坪'] <= area_max)]

    # 車位
    car_grip = filters.get('car_grip', "不限")
    if car_grip == "需要":
        filtered = filtered[filtered.get('車位', 0) > 0]
    elif car_grip == "不要":
        filtered = filtered[filtered.get('車位', 0) == 0]

    return filtered



def display_pagination(df, items_per_page=10):
    """ 處理分頁邏輯 """
    if 'current_search_page' not in st.session_state:
        st.session_state.current_search_page = 1
    total_items = len(df)
    total_pages = math.ceil(total_items / items_per_page) if total_items > 0 else 1
    if st.session_state.current_search_page > total_pages:
        st.session_state.current_search_page = 1
    start_idx = (st.session_state.current_search_page - 1) * items_per_page
    end_idx = min(start_idx + items_per_page, total_items)
    current_page_data = df.iloc[start_idx:end_idx]
    return current_page_data, st.session_state.current_search_page, total_pages, total_items
