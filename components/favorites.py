# components/favorites.py
import pandas as pd
import streamlit as st


def normalize_property_id(value):
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() == 'nan':
        return ""
    return text


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

        if all_df is None or all_df.empty or '編號' not in all_df.columns:
            return pd.DataFrame()

        fav_ids = {normalize_property_id(x) for x in st.session_state.favorites if normalize_property_id(x)}
        if not fav_ids:
            return pd.DataFrame()

        df = all_df.copy()
        df['__property_id__'] = df['編號'].apply(normalize_property_id)
        fav_df = df[df['__property_id__'].isin(fav_ids)].copy()
        return fav_df.drop(columns=['__property_id__'], errors='ignore')
