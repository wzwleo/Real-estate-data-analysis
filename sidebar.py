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
 
    if st.sidebar.button("🗄️ 分析結果總覽", use_container_width=True, key="analysis_records_button"):
        st.session_state.current_page = 'records'
        # 重置搜尋頁面
        if 'current_search_page' in st.session_state:
            del st.session_state.current_search_page

    
    # 設置區域
    st.sidebar.title("⚙️設置")

    # 更新：分開 Google Maps Server Key 和 Browser Key
    with st.sidebar.expander("🗺️ Google Maps API Keys"):
        st.markdown("**Server Key** (用於後端查詢)")
        gmaps_server_input = st.text_input(
            "Google Maps Server Key", 
            type="password", 
            value=st.session_state.get("GMAPS_SERVER_KEY", ""),
            key="gmaps_server_input",
            label_visibility="collapsed"
        )
        if st.button("設定 Server Key", key="gmaps_server_set"):
            st.session_state["GMAPS_SERVER_KEY"] = gmaps_server_input
            st.success("✅ Google Maps Server Key 已設定")
        
        st.divider()
        
        st.markdown("**Browser Key** (用於前端地圖顯示)")
        gmaps_browser_input = st.text_input(
            "Google Maps Browser Key", 
            type="password", 
            value=st.session_state.get("GMAPS_BROWSER_KEY", ""),
            key="gmaps_browser_input",
            label_visibility="collapsed"
        )
        if st.button("設定 Browser Key", key="gmaps_browser_set"):
            st.session_state["GMAPS_BROWSER_KEY"] = gmaps_browser_input
            st.success("✅ Google Maps Browser Key 已設定")
        
        st.divider()
        
        # 保持原有的統一金鑰設置，兼容舊代碼
        st.markdown("**統一金鑰** (兼容模式)")
        google_maps_input = st.text_input(
            "Google Maps API 金鑰 (統一)", 
            type="password", 
            value=st.session_state.get("GOOGLE_MAPS_KEY", ""),
            key="google_maps_input",
            label_visibility="collapsed"
        )
        if st.button("設定統一金鑰", key="google_maps_set"):
            st.session_state["GOOGLE_MAPS_KEY"] = google_maps_input
            st.success("✅ Google Maps API KEY 已設定")

    # 更新：改為 DeepSeek API Key
    with st.sidebar.expander("🤖 AI API KEY"):
        # DeepSeek API Key
        st.markdown("**DeepSeek API 金鑰**")
        deepseek_input = st.text_input(
            "請輸入 DeepSeek API 金鑰", 
            type="password", 
            value=st.session_state.get("DEEPSEEK_KEY", ""),
            key="deepseek_input",
            label_visibility="collapsed",
            help="在 https://platform.deepseek.com/ 註冊獲取 API 金鑰"
        )
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("設定 DeepSeek", key="deepseek_set"):
                st.session_state["DEEPSEEK_KEY"] = deepseek_input
                st.success("✅ DeepSeek API KEY 已設定")
        
        with col2:
            if st.button("測試連線", key="deepseek_test"):
                if not deepseek_input:
                    st.error("❌ 請先輸入 DeepSeek API Key")
                else:
                    try:
                        import openai
                        client = openai.OpenAI(
                            api_key=deepseek_input,
                            base_url="https://api.deepseek.com"
                        )
                        response = client.chat.completions.create(
                            model="deepseek-chat",
                            messages=[{"role": "user", "content": "測試連線，請回覆'連線成功'"}],
                            max_tokens=10
                        )
                        st.success(f"✅ DeepSeek 連線成功！")
                    except Exception as e:
                        st.error(f"❌ 連線失敗：{str(e)}")
        
        st.divider()
        
        # 保留 Gemini API Key 設置（可選，兼容舊功能）
        st.markdown("**Gemini API 金鑰** (選填)")
        gemini_input = st.text_input(
            "請輸入 Gemini API 金鑰", 
            type="password", 
            value=st.session_state.get("GEMINI_KEY", ""),
            key="gemini_input",
            label_visibility="collapsed"
        )
        if st.button("設定 Gemini", key="gemini_set"):
            st.session_state["GEMINI_KEY"] = gemini_input
            st.success("✅ Gemini API KEY 已設定")

    if st.sidebar.button("其他功能一", use_container_width=True, key="updata_button"):
        st.sidebar.write("施工中...")

    if st.sidebar.button("💬智能小幫手", use_container_width=True, key="line_button"):
        st.sidebar.write("施工中...")
