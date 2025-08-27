import os
import pandas as pd
import math
import streamlit as st

def get_city_options(data_dir="./Data"):
    """
    獲取城市選項
    """
    # 讀取 CSV 檔
    files = [f for f in os.listdir(data_dir) if f.endswith(".csv")]
    # 中文對照表
    name_map = {
        "Taichung-city_buy_properties.csv": "台中市",
    }
    # 自動 fallback 顯示英文檔名（去掉 -city_buy_properties.csv）
    options = {name_map.get(f, f.replace("-city_buy_properties.csv", "")): f for f in files}
    return options

def filter_properties(df, filters):
    """
    根據篩選條件過濾房產資料
    """
    filtered_df = df.copy()
    
    try:
        # 房產類型篩選
        if filters['housetype'] != "不限":
            filtered_df = filtered_df[filtered_df['類型'] == filters['housetype']]
        
        # 預算篩選（總價萬元）
        if filters['budget_min'] > 0:
            filtered_df = filtered_df[filtered_df['總價(萬)'] >= filters['budget_min']]
        if filters['budget_max'] < 1000000:
            filtered_df = filtered_df[filtered_df['總價(萬)'] <= filters['budget_max']]
        
        # 屋齡篩選
        if filters['age_min'] > 0:
            filtered_df = filtered_df[filtered_df['屋齡'] >= filters['age_min']]
        if filters['age_max'] < 100:
            filtered_df = filtered_df[filtered_df['屋齡'] <= filters['age_max']]
        
        # 建坪篩選
        if filters['area_min'] > 0:
            filtered_df = filtered_df[filtered_df['建坪'] >= filters['area_min']]
        if filters['area_max'] < 1000:
            filtered_df = filtered_df[filtered_df['建坪'] <= filters['area_max']]
        
        # 車位篩選
        if filters['car_grip'] == "需要":
            # 假設有車位的資料在某個欄位中，這裡需要根據實際資料結構調整
            # 例如：如果有 '車位' 欄位，且值為 "有" 或數量大於0
            if '車位' in filtered_df.columns:
                filtered_df = filtered_df[
                    (filtered_df['車位'].notna()) & 
                    (filtered_df['車位'] != "無") & 
                    (filtered_df['車位'] != 0)
                ]
        elif filters['car_grip'] == "不要":
            if '車位' in filtered_df.columns:
                filtered_df = filtered_df[
                    (filtered_df['車位'].isna()) | 
                    (filtered_df['車位'] == "無") | 
                    (filtered_df['車位'] == 0)
                ]
        
    except Exception as e:
        st.error(f"篩選過程中發生錯誤: {e}")
        return df
    
    return filtered_df

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
