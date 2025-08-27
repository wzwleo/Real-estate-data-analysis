import os
import pandas as pd
import streamlit as st

def get_city_options(data_dir="./Data"):
    files = [f for f in os.listdir(data_dir) if f.endswith(".csv")]
    name_map = {
        "Taichung-city_buy_properties.csv": "台中市",
    }
    options = {name_map.get(f, f.replace("-city_buy_properties.csv", "")): f for f in files}
    return options

def filter_properties(df, filters):
    filtered_df = df.copy()
    try:
        if filters['housetype'] != "不限":
            filtered_df = filtered_df[filtered_df['類型'] == filters['housetype']]
        if filters['budget_min'] > 0:
            filtered_df = filtered_df[filtered_df['總價(萬)'] >= filters['budget_min']]
        if filters['budget_max'] < 1000000:
            filtered_df = filtered_df[filtered_df['總價(萬)'] <= filters['budget_max']]
        if filters['age_min'] > 0:
            filtered_df = filtered_df[filtered_df['屋齡'] >= filters['age_min']]
        if filters['age_max'] < 100:
            filtered_df = filtered_df[filtered_df['屋齡'] <= filters['age_max']]
        if filters['area_min'] > 0:
            filtered_df = filtered_df[filtered_df['建坪'] >= filters['area_min']]
        if filters['area_max'] < 1000:
            filtered_df = filtered_df[filtered_df['建坪'] <= filters['area_max']]
        if filters['car_grip'] == "需要":
            if '車位' in filtered_df.columns:
                filtered_df = filtered_df[(filtered_df['車位'].notna()) & 
                                          (filtered_df['車位'] != "無") & 
                                          (filtered_df['車位'] != 0)]
        elif filters['car_grip'] == "不要":
            if '車位' in filtered_df.columns:
                filtered_df = filtered_df[(filtered_df['車位'].isna()) | 
                                          (filtered_df['車位'] == "無") | 
                                          (filtered_df['車位'] == 0)]
    except Exception as e:
        st.error(f"篩選過程中發生錯誤: {e}")
        return df
    return filtered_df
