import streamlit as st
#from (檔案名稱) import (函式名稱)

def main():
    st.set_page_config(layout="wide")

    # 初始化頁面狀態
    if 'current_page' not in st.session_state:
        st.session_state.current_page = 'home'
    
    # 側邊欄按鈕 - 每個都有唯一的 key
    if st.sidebar.button("🏠 首頁", use_container_width=True, key="home_button"):
        st.session_state.current_page = 'home'
    
    if st.sidebar.button("🔍 搜尋頁面", use_container_width=True, key="search_button"):
        st.session_state.current_page = 'search'
    
    if st.sidebar.button("📊 分析頁面", use_container_width=True, key="analysis_button"):
        st.session_state.current_page = 'analysis'
    
    # 頁面內容
    if st.session_state.current_page == 'home':
        st.title("🏠AI購屋分析憨")
        st.write("👋歡迎來到房地產分析系統")
        st.write("以下是使用說明：")
        
        col1, col2 = st.columns(2)

        with col1:
            # 左上表單
            with st.form("search"):
                st.subheader("🔍 搜尋頁面")
                st.write("第一步：阿對對對 就是這樣 嗯嗯嗯 沒錯沒錯")
                if st.sidebar.button("開始", key="search_start"):
                    st.session_state.current_page = 'search'
            
            # 左下表單
            with st.form("form2"):
                st.subheader("表單 2")
                submit2 = st.form_submit_button("提交")
                if submit2:
                    st.write(f"表單 2 提交：城市={city1}")
        
        with col2:
            # 右上表單
            with st.form("analysis"):
                st.subheader("📊 分析頁面")
                st.write("第二步：阿對對對 就是這樣 嗯嗯嗯 沒錯沒錯")
                analysis_bt = st.form_submit_button("開始", key="analysis_start")
                if analysis_bt:
                    st.session_state.current_page = 'analysis'
            
            # 右下表單
            with st.form("form4"):
                st.subheader("表單 4")
                submit4 = st.form_submit_button("提交")
                if submit4:
                    st.write(f"表單 4 提交：Email={email}")

    elif st.session_state.current_page == 'search':
        st.title("🔍 搜尋頁面")
        with st.form("property_requirements"):
            st.subheader("📍 房產篩選條件")
            submit = st.form_submit_button("開始篩選")
        
    elif st.session_state.current_page == 'analysis':
        st.title("📊 分析頁面")
        st.write("房產分析和數據")
        
    
    st.sidebar.title("⚙️設置")
        
    with st.sidebar.expander("🔑Gemini API KEY"):
        api_key_input = st.text_input("請輸入 Gemini API 金鑰", type="password")
        if st.button("確定", key="api_confirm_button"):
            st.success("✅APIKEY已設定")
    with st.sidebar.expander("其他功能一"):
        st.write("施工中...")
    with st.sidebar.expander("其他功能二"):
        st.write("施工中...")

    if st.sidebar.button("🔄更新資料", use_container_width=True, key="updata_button"):
        st.sidebar.write("施工中...")

if __name__ == "__main__":

    main()





































































