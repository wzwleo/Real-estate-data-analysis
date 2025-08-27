import streamlit as st

def render_sidebar():
    """
    渲染側邊欄導航和設置
    """
    # 側邊欄按鈕 - 每個都有唯一的 key
    if st.sidebar.button("🏠 首頁", use_container_width=True, key="home_button"):
        st.session_state.current_page = 'home'
        # 重置搜尋頁面
        if 'current_search_page' in st.session_state:
            del st.session_state.current_search_page

    if st.sidebar.button("🔍 搜尋頁面", use_container_width=True, key="search_button"):
        st.session_state.current_page = 'search'

    if st.sidebar.button("📊 分析頁面", use_container_width=True, key="analysis_button"):
        st.session_state.current_page = 'analysis'
        # 重置搜尋頁面
        if 'current_search_page' in st.session_state:
            del st.session_state.current_search_page
    if st.sidebar.button("🏡 房屋比較", use_container_width=True, key="compare_button"):
        st.session_state.current_page = 'compare'     
 

    # 設置區域
    st.sidebar.title("⚙️設置")

    with st.sidebar.expander("🔑 Gemini API KEY"):
        api_key_input = st.text_input(
            "請輸入 Gemini API 金鑰", 
            type="password", 
            value=st.session_state.get("GEMINI_KEY", ""),
            key="gemini_input"
        )
        if st.button("設定 Gemini KEY", key="gemini_set"):
            st.session_state["GEMINI_KEY"] = api_key_input
            st.success("✅ Gemini API KEY 已設定")
    
    with st.sidebar.expander("🗺️ OpenCage API KEY"):
        opencage_input = st.text_input(
            "請輸入 OpenCage 金鑰", 
            type="password", 
            value=st.session_state.get("OPENCAGE_KEY", ""),
            key="opencage_input"
        )
        if st.button("設定 OpenCage KEY", key="opencage_set"):
            st.session_state["OPENCAGE_KEY"] = opencage_input
            st.success("✅ OpenCage API KEY 已設定")
    
    with st.sidebar.expander("🔄更新資料"):
        st.write("施工中...")

    if st.sidebar.button("其他功能一", use_container_width=True, key="updata_button"):
        st.sidebar.write("施工中...")

    if st.sidebar.button("💬智能小幫手", use_container_width=True, key="line_button"):
        st.sidebar.write("施工中...")
