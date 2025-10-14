import streamlit as st
from sidebar import render_sidebar
from page_modules.home_page import render_home_page
from page_modules.search_page import render_search_page
from page_modules.analysis_page import render_analysis_page
from page_modules.compare_page import render_compare_page  # 若 compare 頁面存在，建議補上這行


def main():
    """主應用程式入口"""
    st.set_page_config(layout="wide")

    # 初始化頁面狀態
    if 'current_page' not in st.session_state:
        st.session_state.current_page = 'home'

    # 渲染側邊欄
    render_sidebar()

    # 頁面路由
    current = st.session_state.current_page
    if current == 'home':
        render_home_page()
    elif current == 'search':
        render_search_page()
    elif current == 'analysis':
        render_analysis_page()
    elif current == 'compare':
        render_compare_page()


if __name__ == "__main__":
    main()
