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
    
    with st.sidebar.expander("🎚️ 評分權重設定", expanded=True):
            # 1. 初始化所有狀態 (在 Widget 出現前完成)
            default_weights = {"w_price": 30, "w_space": 25, "w_age": 20, "w_floor": 15, "w_layout": 10}
            
            if 'w_price' not in st.session_state:
                for k, v in default_weights.items(): st.session_state[k] = v
            
            # 用來控制 selectbox 顯示位置的 state
            if 'preset_index' not in st.session_state:
                st.session_state.preset_index = 0 
    
            templates = {
                "自訂": None,
                "👨‍👩‍👧‍👦 小家庭首購": [40, 15, 15, 10, 20],
                "💼 投資客導向": [35, 15, 20, 10, 20],
                "👴 退休族優先": [20, 20, 25, 25, 10]
            }
            preset_list = list(templates.keys())
    
            # 2. 渲染下拉選單 (使用 index 避開 key 鎖死問題)
            selected_preset = st.selectbox(
                "快速選擇模板", 
                preset_list, 
                index=st.session_state.preset_index
            )
    
            # 如果選單被手動切換了，更新 index 並處理數值
            if preset_list.index(selected_preset) != st.session_state.preset_index:
                st.session_state.preset_index = preset_list.index(selected_preset)
                if selected_preset != "自訂":
                    vals = templates[selected_preset]
                    st.session_state.w_price, st.session_state.w_space, st.session_state.w_age, \
                    st.session_state.w_floor, st.session_state.w_layout = vals
                st.rerun()
    
            # 3. 渲染按鈕 (放在 Slider 上方或下方皆可)
            col1, col2 = st.columns(2)
            
            if col2.button("🔄 重設", use_container_width=True):
                for k, v in default_weights.items():
                    st.session_state[k] = v
                st.session_state.preset_index = 0 # 強制跳回「自訂」
                st.rerun()
    
            # 4. 渲染 Slider
            st.slider("💰 價格競爭力", 0, 100, step=5, key="w_price")
            st.slider("📐 空間效率", 0, 100, step=5, key="w_space")
            st.slider("🕰️ 屋齡優勢", 0, 100, step=5, key="w_age")
            st.slider("🏢 樓層定位", 0, 100, step=5, key="w_floor")
            st.slider("🛋️ 格局流動性", 0, 100, step=5, key="w_layout")
            
            total_weight = (st.session_state.w_price + st.session_state.w_space + 
                            st.session_state.w_age + st.session_state.w_floor + 
                            st.session_state.w_layout)
    
            # 5. 套用邏輯
            if total_weight == 100:
                st.success(f"✅ 總權重：{total_weight}%")
                if col1.button("💾 套用", use_container_width=True):
                    st.session_state.score_weights = {
                        "價格競爭力": st.session_state.w_price,
                        "空間效率": st.session_state.w_space,
                        "屋齡優勢": st.session_state.w_age,
                        "樓層定位": st.session_state.w_floor,
                        "格局流動性": st.session_state.w_layout
                    }
                    st.toast("✅ 權重已更新")
            else:
                st.error(f"❌ 總權重：{total_weight}%")
        

    if st.sidebar.button("其他功能一", use_container_width=True, key="updata_button"):
        st.sidebar.write("施工中...")

    if st.sidebar.button("💬智能小幫手", use_container_width=True, key="line_button"):
        st.sidebar.write("施工中...")
