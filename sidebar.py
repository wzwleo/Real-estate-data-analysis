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

    with st.sidebar.expander("🔑 Gemini API KEY"):
        api_key_input = st.text_input(
            "請輸入 Gemini API 金鑰", 
            type="password", 
            value=st.session_state.get("GEMINI_KEY", ""),
            key="gemini_input"
        )
        if st.button("設定", key="gemini_set"):
            st.session_state["GEMINI_KEY"] = api_key_input
            st.success("✅ Gemini API KEY 已設定")
    
    with st.sidebar.expander("🗺️ Google Maps API KEY"):
        google_maps_input = st.text_input(
            "請輸入 Google Maps API 金鑰", 
            type="password", 
            value=st.session_state.get("GOOGLE_MAPS_KEY", ""),
            key="google_maps_input"
        )
        if st.button("設定", key="google_maps_set"):
            st.session_state["GOOGLE_MAPS_KEY"] = google_maps_input
            st.success("✅ Google Maps API KEY 已設定")
    
    with st.sidebar.expander("🎚️ 評分權重設定", expanded=False):
        # 初始化預設權重
        default_weights = {
                "w_price": 30, "w_space": 25, "w_age": 20, "w_floor": 15, "w_layout": 10
            }
            
        for key, val in default_weights.items():
            if key not in st.session_state:
                st.session_state[key] = val
        
        with st.sidebar.expander("🎚️ 評分權重設定", expanded=True):
            st.caption("💡 總和需為 100%")
                
            # 2. 模板選擇邏輯
            preset = st.selectbox(
                "快速選擇模板",
                ["自訂", "👨‍👩‍👧‍👦 小家庭首購", "💼 投資客導向", "👴 退休族優先"],
                key="weight_preset"
            )
                
            # 定義模板數據
            templates = {
                "👨‍👩‍👧‍👦 小家庭首購": [40, 15, 15, 10, 20],
                "💼 投資客導向": [35, 15, 20, 10, 20],
                "👴 退休族優先": [20, 20, 25, 25, 10]
            }
        
            # 如果選了模板，直接更新 session_state 裡的 slider key
            if preset in templates:
                vals = templates[preset]
                st.session_state.w_price = vals[0]
                st.session_state.w_space = vals[1]
                st.session_state.w_age = vals[2]
                st.session_state.w_floor = vals[3]
                st.session_state.w_layout = vals[4]
        
            # 3. Slider 直接綁定 key
            # 注意：這裡不再傳入 value 參數，因為 key 會自動接管
            st.slider("💰 價格競爭力", 0, 100, step=5, key="w_price")
            st.slider("📐 空間效率", 0, 100, step=5, key="w_space")
            st.slider("🕰️ 屋齡優勢", 0, 100, step=5, key="w_age")
            st.slider("🏢 樓層定位", 0, 100, step=5, key="w_floor")
            st.slider("🛋️ 格局流動性", 0, 100, step=5, key="w_layout")
            
            total_weight = (st.session_state.w_price + st.session_state.w_space + 
                            st.session_state.w_age + st.session_state.w_floor + 
                            st.session_state.w_layout)
        
        # 顯示總和與狀態
        if total_weight == 100:
            st.success(f"✅ 總權重：{total_weight}%")
        elif total_weight < 100:
            st.warning(f"⚠️ 總權重：{total_weight}%（還差 {100 - total_weight}%）")
        else:
            st.error(f"❌ 總權重：{total_weight}%（超過 {total_weight - 100}%）")
        
        # 操作按鈕
        col1, col2 = st.columns(2)
        with col1:
            if st.button("💾 套用", use_container_width=True):
                if total_weight == 100:
                    # 這裡存入最終要給分析邏輯使用的 score_weights
                    st.session_state.score_weights = {
                        "價格競爭力": st.session_state.w_price,
                        "空間效率": st.session_state.w_space,
                        "屋齡優勢": st.session_state.w_age,
                        "樓層定位": st.session_state.w_floor,
                        "格局流動性": st.session_state.w_layout
                    }
                    st.success("✅ 已套用")
                    st.rerun()
                else:
                    st.error("❌ 總重需為 100%")
                
        with col2:
            if st.button("🔄 重設", use_container_width=True):
                # 重設所有 Slider key 到初始值
                for key, val in default_weights.items():
                    st.session_state[key] = val
                st.rerun()
        

    if st.sidebar.button("其他功能一", use_container_width=True, key="updata_button"):
        st.sidebar.write("施工中...")

    if st.sidebar.button("💬智能小幫手", use_container_width=True, key="line_button"):
        st.sidebar.write("施工中...")
