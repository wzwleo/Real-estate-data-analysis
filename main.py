import streamlit as st
from Analysis import User_Analysis
#from (檔案名稱) import (函式名稱)

def main():
    st.set_page_config(layout="wide")

    # 初始化 session state
    if 'current_page' not in st.session_state:
        st.session_state.current_page = 'home'
    
    # 側邊欄按鈕
    if st.sidebar.button("首頁", use_container_width=True):
        st.session_state.current_page = 'home'
    
    if st.sidebar.button("搜尋頁面", use_container_width=True):
        st.session_state.current_page = 'search'
    
    if st.sidebar.button("分析頁面", use_container_width=True):
        st.session_state.current_page = 'analysis'
    
    # 根據當前頁面顯示不同內容
    if st.session_state.current_page == 'home':
        st.title("🏠 首頁")
        st.write("歡迎來到房地產分析系統")
        
    elif st.session_state.current_page == 'search':
        st.title("🔍 搜尋頁面")
        st.write("在這裡搜尋房產")
        
    elif st.session_state.current_page == 'analysis':
        st.title("📊 分析頁面")
        st.write("房產分析和數據")# 初始化 session state
    if 'current_page' not in st.session_state:
        st.session_state.current_page = 'home'
    
    # 側邊欄按鈕
    if st.sidebar.button("首頁", use_container_width=True):
        st.session_state.current_page = 'home'
    
    if st.sidebar.button("搜尋頁面", use_container_width=True):
        st.session_state.current_page = 'search'
    
    if st.sidebar.button("分析頁面", use_container_width=True):
        st.session_state.current_page = 'analysis'
    
    # 根據當前頁面顯示不同內容
    if st.session_state.current_page == 'home':
        st.title("🏠 首頁")
        st.write("歡迎來到房地產分析系統")
        
    elif st.session_state.current_page == 'search':
        st.title("🔍 搜尋頁面")
        st.write("在這裡搜尋房產")
        
    elif st.session_state.current_page == 'analysis':
        st.title("📊 分析頁面")
        st.write("房產分析和數據")
    '''
    st.title("🏠AI購屋分析")
    st.sidebar.title("⚙️設置")

    st.sidebar.button("首頁", use_container_width=True)
        
    with st.sidebar.expander("🔑Gemini API KEY"):
        api_key_input = st.text_input("請輸入 Gemini API 金鑰", type="password")
    with st.sidebar.expander("其他功能一"):
        st.write("施工中...")
    with st.sidebar.expander("其他功能二"):
        st.write("施工中...")

    with st.form("property_requirements"):
        st.subheader("📍 Location & Budget")
        submit = st.form_submit_button("Update Search")
    
    '''

if __name__ == "__main__":

    main()

































