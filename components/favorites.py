# components/favorites.py
import pandas as pd
import streamlit as st


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
        
        fav_ids = st.session_state.favorites
        fav_df = all_df[all_df['編號'].astype(str).isin(map(str, fav_ids))].copy()
        return fav_df
