import streamlit as st
from modules.ui_home import render_home
from modules.ui_search import render_search
from modules.ui_analysis import render_analysis

def main():
    st.set_page_config(layout="wide")
    if 'current_page' not in st.session_state:
        st.session_state.current_page = 'home'

    # 側邊欄按鈕
    if st.sidebar.button("🏠 首頁", key="home_button"):
        st.session_state.current_page = 'home'
        if 'current_search_page' in st.session_state:
            del st.session_state.current_search_page
    if st.sidebar.button("🔍 搜尋頁面", key="search_button"):
        st.session_state.current_page = 'search'
    if st.sidebar.button("📊 分析頁面", key="analysis_button"):
        st.session_state.current_page = 'analysis'
        if 'current_search_page' in st.session_state:
            del st.session_state.current_search_page

    # 頁面切換
    if st.session_state.current_page == 'home':
        render_home()
    elif st.session_state.current_page == 'search':
        render_search()
    elif st.session_state.current_page == 'analysis':
        render_analysis()

    # 側邊欄設定
    st.sidebar.title("⚙️設置")
    with st.sidebar.expander("🔑Gemini API KEY"):
        api_key_input = st.text_input("請輸入 Gemini API 金鑰", type="password")
        if st.button("確定", key="api_confirm_button"):
            st.success("✅API KEY已設定")
    with st.sidebar.expander("🗺️MAP API KEY"):
        st.write("施工中...")
    with st.sidebar.expander("🔄更新資料"):
        st.write("施工中...")
    if st.sidebar.button("其他功能一", key="updata_button"):
        st.sidebar.write("施工中...")
    if st.sidebar.button("💬智能小幫手", key="line_button"):
        st.sidebar.write("施工中...")

if __name__ == "__main__":
    main()
