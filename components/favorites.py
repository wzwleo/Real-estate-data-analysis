import pandas as pd
import streamlit as st

def normalize_property_id(value):
    if value is None:
        return ""
    return str(value).strip()

class FavoritesManager:
    
    @staticmethod
    def add_favorite(row: pd.Series):
        """新增收藏，同時把該筆資料快取起來"""
        if 'favorites' not in st.session_state:
            st.session_state.favorites = []
        if 'favorites_cache' not in st.session_state:
            st.session_state.favorites_cache = {}

        pid = normalize_property_id(row.get('編號', ''))
        if not pid:
            return

        # 加入 ID 清單
        favs = list(st.session_state.favorites)
        if pid not in favs:
            favs.append(pid)
            st.session_state.favorites = favs

        # 快取完整資料
        st.session_state.favorites_cache[pid] = row.to_dict()

    @staticmethod
    def remove_favorite(property_id: str):
        """移除收藏"""
        pid = normalize_property_id(property_id)
        favs = list(st.session_state.get('favorites', []))
        if pid in favs:
            favs.remove(pid)
            st.session_state.favorites = favs
        cache = st.session_state.get('favorites_cache', {})
        cache.pop(pid, None)

    @staticmethod
    def get_favorites_data() -> pd.DataFrame:
        """
        取得所有收藏房屋的完整資料。
        優先從 favorites_cache 取，其次再從搜尋結果補齊。
        """
        if 'favorites' not in st.session_state or not st.session_state.favorites:
            return pd.DataFrame()

        fav_ids = [normalize_property_id(x) for x in st.session_state.favorites]
        cache: dict = st.session_state.get('favorites_cache', {})

        rows = []
        missing_ids = []

        for pid in fav_ids:
            if pid in cache:
                rows.append(cache[pid])
            else:
                missing_ids.append(pid)

        # 嘗試從搜尋結果補齊 cache 沒有的
        if missing_ids:
            for source_key in ['all_properties_df', 'filtered_df']:
                source_df = st.session_state.get(source_key)
                if source_df is not None and not source_df.empty and '編號' in source_df.columns:
                    matched = source_df[
                        source_df['編號'].map(normalize_property_id).isin(missing_ids)
                    ]
                    for _, row in matched.iterrows():
                        pid = normalize_property_id(row['編號'])
                        if pid in missing_ids:
                            rows.append(row.to_dict())
                            cache[pid] = row.to_dict()
                            missing_ids.remove(pid)
                if not missing_ids:
                    break
            # 把補齊的結果寫回 cache
            st.session_state.favorites_cache = cache

        if not rows:
            return pd.DataFrame()

        return pd.DataFrame(rows)
