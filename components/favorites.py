# components/favorites.py
import pandas as pd
import streamlit as st


def normalize_property_id(value):
    """統一房屋編號格式，避免字串/數字型別不一致。"""
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    return str(value).strip()


def build_property_key(row_or_series):
    """建立穩定的房屋識別 key。優先使用編號。"""
    if row_or_series is None:
        return ""
    property_id = normalize_property_id(row_or_series.get('編號', ''))
    if property_id:
        return property_id
    title = str(row_or_series.get('標題', '')).strip()
    address = str(row_or_series.get('地址', '')).strip()
    return f"{title}|{address}"


class FavoritesManager:
    """管理收藏功能"""
    
    @staticmethod
    def get_favorites_data():
        """取得收藏的房屋資料"""
        if 'favorites' not in st.session_state or not st.session_state.favorites:
            return pd.DataFrame()
        
        all_df = None
        if 'all_properties_df' in st.session_state and not st.session_state.all_properties_df.empty:
            all_df = st.session_state.all_properties_df
        elif 'filtered_df' in st.session_state and not st.session_state.filtered_df.empty:
            all_df = st.session_state.filtered_df
        
        if all_df is None or all_df.empty:
            return pd.DataFrame()
        
        fav_ids = {normalize_property_id(x) for x in st.session_state.favorites}
        fav_df = all_df[all_df['編號'].apply(normalize_property_id).isin(fav_ids)].copy()
        return fav_df
