# components/favorites.py
import pandas as pd
import streamlit as st


def normalize_property_id(value):
    """統一房屋編號格式，避免字串 / 數字比對失敗"""
    if value is None:
        return ""
    return str(value).strip()


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
        if '編號' not in all_df.columns:
            return pd.DataFrame()
        
        fav_df = all_df[all_df['編號'].map(normalize_property_id).isin(fav_ids)].copy()
        return fav_df
