import os
import pandas as pd
import math
import streamlit as st

import os

def get_city_options(data_dir="./Data"):
    """
    獲取城市選項，只顯示對照表內有定義的檔案
    """
    if not os.path.exists(data_dir):
        return {}

    # 對照表：英文檔名 -> 中文名稱
    name_map = {
        "Taichung-city_buy_properties.csv": "台中市",
        "Taipei-city_buy_properties.csv": "台北市"
        

        # 可以繼續加其他城市
    }

    # 讀取資料夾中的檔案
    files = [f for f in os.listdir(data_dir) if f.endswith(".csv")]

    # 只挑出有對照表的檔案
    options = {name_map[f]: f for f in files if f in name_map}

    # 排序（照中文名稱）
    options = dict(sorted(options.items(), key=lambda x: x[0]))

    return options


def filter_properties(df: pd.DataFrame, filters: dict):
    """依據篩選條件過濾房產資料"""
    filtered = df.copy()

    # 🔹 通用數值欄位處理，避免比較錯誤
    numeric_cols = ['總價(萬)', '屋齡', '建坪', '主+陽', '樓層', '房數', '廳數', '衛數']
    for col in numeric_cols:
        if col in filtered.columns:
            filtered[col] = pd.to_numeric(filtered[col], errors='coerce')

    # 🔹 房產類型
    if filters.get('housetype') and filters['housetype'] != "不限":
        filtered = filtered[filtered['型態'].str.contains(filters['housetype'], na=False)]

    # 🔹 預算範圍
    if 'budget_min' in filters:
        filtered = filtered[filtered['總價(萬)'] >= filters['budget_min']]
    if 'budget_max' in filters and filters['budget_max'] > 0:
        filtered = filtered[filtered['總價(萬)'] <= filters['budget_max']]

    # 🔹 屋齡
    if 'age_min' in filters:
        filtered = filtered[filtered['屋齡'] >= filters['age_min']]
    if 'age_max' in filters and filters['age_max'] < 100:
        filtered = filtered[filtered['屋齡'] <= filters['age_max']]

    # 🔹 建坪
    if 'area_min' in filters:
        filtered = filtered[filtered['建坪'] >= filters['area_min']]
    if 'area_max' in filters and filters['area_max'] < 1000:
        filtered = filtered[filtered['建坪'] <= filters['area_max']]

    # 🔹 車位條件
    if filters.get('car_grip') == "需要":
        filtered = filtered[filtered['車位'].notna()]
    elif filters.get('car_grip') == "不要":
        filtered = filtered[filtered['車位'].isna()]

    # ------------------------------
    # 🧠 Gemini AI 擴充條件支援
    # ------------------------------
    # 房間數
    if 'rooms' in filters:
        filtered = filtered[filtered['房數'] == filters['rooms']]
    if 'rooms_min' in filters:
        filtered = filtered[filtered['房數'] >= filters['rooms_min']]
    if 'rooms_max' in filters:
        filtered = filtered[filtered['房數'] <= filters['rooms_max']]

    # 廳數
    if 'living_rooms' in filters:
        filtered = filtered[filtered['廳數'] == filters['living_rooms']]
    if 'living_rooms_min' in filters:
        filtered = filtered[filtered['廳數'] >= filters['living_rooms_min']]
    if 'living_rooms_max' in filters:
        filtered = filtered[filtered['廳數'] <= filters['living_rooms_max']]

    # 衛數
    if 'bathrooms' in filters:
        filtered = filtered[filtered['衛數'] == filters['bathrooms']]
    if 'bathrooms_min' in filters:
        filtered = filtered[filtered['衛數'] >= filters['bathrooms_min']]
    if 'bathrooms_max' in filters:
        filtered = filtered[filtered['衛數'] <= filters['bathrooms_max']]

    # 樓層條件（部分資料可能是 "7/15" 格式，需擷取樓層數字）
    if 'floor_min' in filters or 'floor_max' in filters:
        if '樓層' in filtered.columns:
            filtered['樓層數'] = (
                filtered['樓層']
                .astype(str)
                .str.extract(r'(\d+)')[0]
                .astype(float)
            )
            if 'floor_min' in filters:
                filtered = filtered[filtered['樓層數'] >= filters['floor_min']]
            if 'floor_max' in filters:
                filtered = filtered[filtered['樓層數'] <= filters['floor_max']]

    return filtered
def display_pagination(df, items_per_page=10):
    """
    處理分頁邏輯並返回當前頁面的資料
    """
    # 初始化頁面狀態
    if 'current_search_page' not in st.session_state:
        st.session_state.current_search_page = 1
    
    total_items = len(df)
    total_pages = math.ceil(total_items / items_per_page) if total_items > 0 else 1
    
    # 確保頁面數在有效範圍內
    if st.session_state.current_search_page > total_pages:
        st.session_state.current_search_page = 1
    
    # 計算當前頁面的資料範圍
    start_idx = (st.session_state.current_search_page - 1) * items_per_page
    end_idx = min(start_idx + items_per_page, total_items)
    
    current_page_data = df.iloc[start_idx:end_idx]
    
    return current_page_data, st.session_state.current_search_page, total_pages, total_items



