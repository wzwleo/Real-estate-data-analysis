import streamlit as st
from sidebar import render_sidebar
from pages.home_page import render_home_page
from pages.search_page import render_search_page
from pages.analysis_page import render_analysis_page

def main():
    """
    主應用程式入口
    """
    st.set_page_config(layout="wide")

    # 初始化頁面狀態
    if 'current_page' not in st.session_state:
        st.session_state.current_page = 'home'

    # 渲染側邊欄
    render_sidebar()



if __name__ == "__main__":
    main()
