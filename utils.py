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
    }
    files = [f for f in os.listdir(data_dir) if f.endswith(".csv")]
    options = {name_map[f]: f for f in files if f in name_map}
    return dict(sorted(options.items(), key=lambda x: x[0]))


def filter_properties(df, filters):
    """ 根據篩選條件過濾房產資料 """
    filtered_df = df.copy()
    try:
        # 類型
        if filters.get('housetype') and filters['housetype'] != "不限":
            if '類型' in filtered_df.columns:
                filtered_df = filtered_df[
                    filtered_df['類型'].astype(str).str.contains(filters['housetype'], case=False, na=False)
                ]
        # 預算
        if filters.get('budget_min', 0) > 0 and '總價(萬)' in filtered_df.columns:
            filtered_df = filtered_df[filtered_df['總價(萬)'] >= filters['budget_min']]
        if filters.get('budget_max', 1000000) < 1000000 and '總價(萬)' in filtered_df.columns:
            filtered_df = filtered_df[filtered_df['總價(萬)'] <= filters['budget_max']]
        # 屋齡
        if filters.get('age_min', 0) > 0 and '屋齡' in filtered_df.columns:
            filtered_df = filtered_df[filtered_df['屋齡'] >= filters['age_min']]
        if filters.get('age_max', 100) < 100 and '屋齡' in filtered_df.columns:
            filtered_df = filtered_df[filtered_df['屋齡'] <= filters['age_max']]
        # 建坪
        if filters.get('area_min', 0) > 0 and '建坪' in filtered_df.columns:
            filtered_df = filtered_df[filtered_df['建坪'] >= filters['area_min']]
        if filters.get('area_max', 1000) < 1000 and '建坪' in filtered_df.columns:
            filtered_df = filtered_df[filtered_df['建坪'] <= filters['area_max']]
        # 車位
        if 'car_grip' in filters and '車位' in filtered_df.columns:
            if filters['car_grip'] == "需要":
                filtered_df = filtered_df[
                    (filtered_df['車位'].notna()) & 
                    (filtered_df['車位'] != "無車位") & 
                    (filtered_df['車位'] != 0)
                ]
            elif filters['car_grip'] == "不要":
                filtered_df = filtered_df[
                    (filtered_df['車位'].isna()) | 
                    (filtered_df['車位'] == "無車位") | 
                    (filtered_df['車位'] == 0)
                ]
        # Gemini AI 特殊要求
        if "rooms" in filters:
            rooms = filters["rooms"]
            if isinstance(rooms, dict):
                filtered_df = filtered_df[(filtered_df['房間數'] >= rooms.get("min", 0)) &
                                          (filtered_df['房間數'] <= rooms.get("max", 100))]
            else:
                filtered_df = filtered_df[filtered_df['房間數'] >= rooms]
        if "living_rooms" in filters:
            filtered_df = filtered_df[filtered_df['廳數'] >= filters["living_rooms"]]
        if "bathrooms" in filters:
            filtered_df = filtered_df[filtered_df['衛數'] >= filters["bathrooms"]]
        if "floor" in filters and '樓層' in filtered_df.columns:
            floor = filters["floor"]
            if isinstance(floor, dict):
                if "min" in floor:
                    filtered_df = filtered_df[filtered_df['樓層'] >= floor["min"]]
                if "max" in floor:
                    filtered_df = filtered_df[filtered_df['樓層'] <= floor["max"]]
            else:
                filtered_df = filtered_df[filtered_df['樓層'] == floor]
    except Exception as e:
        st.error(f"篩選過程中發生錯誤: {e}")
        return df
    return filtered_df


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
