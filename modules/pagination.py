import math
import streamlit as st

def display_pagination(df, items_per_page=10):
    if 'current_search_page' not in st.session_state:
        st.session_state.current_search_page = 1
    
    total_items = len(df)
    total_pages = math.ceil(total_items / items_per_page) if total_items > 0 else 1
    if st.session_state.current_search_page > total_pages:
        st.session_state.current_search_page = 1
    
    start_idx = (st.session_state.current_search_page - 1) * items_per_page
    end_idx = min(start_idx + items_per_page, total_items)
    
    return df.iloc[start_idx:end_idx], st.session_state.current_search_page, total_pages, total_items
