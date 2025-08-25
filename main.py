import streamlit as st

def main():
    st.set_page_config(layout="wide")
    
    # 初始化頁面狀態
    if 'current_page' not in st.session_state:
        st.session_state.current_page = 'home'
    
    # 側邊欄按鈕
    if st.sidebar.button("🏠 首頁", use_container_width=True, key="home_button"):
        st.session_state.current_page = 'home'
    if st.sidebar.button("🔍 搜尋頁面", use_container_width=True, key="search_button"):
        st.session_state.current_page = 'search'
    if st.sidebar.button("📊 分析頁面", use_container_width=True, key="analysis_button"):
        st.session_state.current_page = 'analysis'
    
    # 頁面內容
    if st.session_state.current_page == 'home':
        st.title("🏠AI購屋分析")
        st.write("👋歡迎來到房地產分析系統")
        st.write("以下是使用說明：")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # 搜尋表單
            with st.form("search_form", clear_on_submit=False):
                st.subheader("🔍 搜尋頁面")
                st.write("第一步：阿對對對 就是這樣 嗯嗯嗯 沒錯沒錯")
                search_submitted = st.form_submit_button("開始")
                
            if search_submitted:
                st.session_state.current_page = 'search'
                st.rerun()
            
            # 表單2
            with st.form("form2", clear_on_submit=False):
                st.subheader("表單 2")
                city1 = st.selectbox("選擇城市", ["台北", "新北", "桃園", "台中", "台南", "高雄"])
                form2_submitted = st.form_submit_button("提交")
                
            if form2_submitted:
                st.success(f"表單 2 提交：城市={city1}")
        
        with col2:
            # 分析表單
            with st.form("analysis_form", clear_on_submit=False):
                st.subheader("📊 分析頁面")
                st.write("第二步：阿對對對 就是這樣 嗯嗯嗯 沒錯沒錯")
                analysis_submitted = st.form_submit_button("開始")
                
            if analysis_submitted:
                st.session_state.current_page = 'analysis'
                st.rerun()
            
            # 表單4
            with st.form("form4", clear_on_submit=False):
                st.subheader("表單 4")
                email = st.text_input("Email")
                form4_submitted = st.form_submit_button("提交")
                
            if form4_submitted:
                st.success(f"表單 4 提交：Email={email}")
    
    elif st.session_state.current_page == 'search':
        st.title("🔍 搜尋頁面")
        
        with st.form("property_search", clear_on_submit=False):
            st.subheader("📍 房產篩選條件")
            
            col1, col2 = st.columns(2)
            with col1:
                city = st.selectbox("城市", ["台北", "新北", "桃園", "台中", "台南", "高雄"])
                district = st.text_input("區域")
            with col2:
                price_min = st.number_input("最低價格(萬)", min_value=0, value=500)
                price_max = st.number_input("最高價格(萬)", min_value=0, value=2000)
            
            search_property_submitted = st.form_submit_button("開始篩選")
            
        if search_property_submitted:
            st.success(f"搜尋條件：{city} {district}, 價格範圍：{price_min}-{price_max}萬")
            # 這裡可以添加實際的搜尋邏輯
            st.info("搜尋結果將顯示在這裡...")
    
    elif st.session_state.current_page == 'analysis':
        st.title("📊 分析頁面")
        st.write("房產分析和數據")
        
        # 模擬一些分析內容
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("📈 價格趨勢")
            import numpy as np
            chart_data = np.random.randn(20, 3)
            st.line_chart(chart_data)
        
        with col2:
            st.subheader("📊 區域分布")
            chart_data = {
                '台北': 45,
                '新北': 30,
                '桃園': 25,
                '台中': 35,
                '台南': 20,
                '高雄': 28
            }
            st.bar_chart(chart_data)
    
    # 側邊欄設置
    st.sidebar.title("⚙️設置")
    
    with st.sidebar.expander("🔑Gemini API KEY"):
        api_key_input = st.text_input("請輸入 Gemini API 金鑰", type="password", key="api_key")
        if st.button("確定", key="api_confirm_button"):
            if api_key_input:
                st.session_state.api_key = api_key_input
                st.success("✅APIKEY已設定")
            else:
                st.error("請輸入有效的API金鑰")
    
    with st.sidebar.expander("其他功能一"):
        st.write("施工中...")
    
    with st.sidebar.expander("其他功能二"):
        st.write("施工中...")
    
    if st.sidebar.button("🔄更新資料", use_container_width=True, key="update_button"):
        st.sidebar.success("資料更新中...")

if __name__ == "__main__":
    main()
