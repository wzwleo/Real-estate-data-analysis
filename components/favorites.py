# components/favorites.py
import pandas as pd
import streamlit as st


class FavoritesManager:
    """管理收藏功能"""

    @staticmethod
    def normalize_property_id(value):
        """統一房屋編號格式，避免字串/數字型別不一致。"""
        if value is None:
            return ""
        text = str(value).strip()
        if text.endswith('.0') and text[:-2].isdigit():
            text = text[:-2]
        return text

    @staticmethod
    def build_property_key(row):
        """建立穩定主鍵，優先使用房屋編號。"""
        if row is None:
            return ""
        try:
            return FavoritesManager.normalize_property_id(row.get('編號', ''))
        except Exception:
            return ""

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
        
        fav_ids = {FavoritesManager.normalize_property_id(x) for x in st.session_state.favorites}
        property_ids = all_df['編號'].apply(FavoritesManager.normalize_property_id)
        fav_df = all_df[property_ids.isin(fav_ids)].copy()
        return fav_df
