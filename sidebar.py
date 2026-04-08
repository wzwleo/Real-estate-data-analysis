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
        if 'score_weights' not in st.session_state:
            st.session_state.score_weights = {
                "價格競爭力": 30,
                "空間效率": 25,
                "屋齡優勢": 20,
                "樓層定位": 15,
                "格局流動性": 10
            }
        
        st.write("調整各項指標的重要性")
        st.caption("💡 總和需為 100%")
        
        # 預設模板選擇
        preset = st.selectbox(
            "快速選擇模板",
            [
                "自訂",
                "👨‍👩‍👧‍👦 小家庭首購",
                "💼 投資客導向",
                "👴 退休族優先",
                "🏃 年輕族群"
            ],
            key="weight_preset"
        )
        
        # 根據模板設定權重
        if preset == "👨‍👩‍👧‍👦 小家庭首購":
            template_weights = {
                "價格競爭力": 40,
                "空間效率": 15,
                "屋齡優勢": 15,
                "樓層定位": 10,
                "格局流動性": 20
            }
        elif preset == "💼 投資客導向":
            template_weights = {
                "價格競爭力": 35,
                "空間效率": 15,
                "屋齡優勢": 20,
                "樓層定位": 10,
                "格局流動性": 20
            }
        elif preset == "👴 退休族優先":
            template_weights = {
                "價格競爭力": 20,
                "空間效率": 20,
                "屋齡優勢": 25,
                "樓層定位": 25,
                "格局流動性": 10
            }
        elif preset == "🏃 年輕族群":
            template_weights = {
                "價格競爭力": 35,
                "空間效率": 30,
                "屋齡優勢": 10,
                "樓層定位": 15,
                "格局流動性": 10
            }
        else:  # 自訂
            template_weights = st.session_state.score_weights
        
        # 使用 slider 調整權重
        weight_price = st.slider(
            "💰 價格競爭力",
            min_value=0,
            max_value=100,
            value=template_weights["價格競爭力"],
            step=5,
            help="價格越便宜，分數越高",
            key="weight_price_slider"
        )
        
        weight_space = st.slider(
            "📐 空間效率",
            min_value=0,
            max_value=100,
            value=template_weights["空間效率"],
            step=5,
            help="公設比越低，分數越高",
            key="weight_space_slider"
        )
        
        weight_age = st.slider(
            "🕰️ 屋齡優勢",
            min_value=0,
            max_value=100,
            value=template_weights["屋齡優勢"],
            step=5,
            help="屋齡越新，分數越高",
            key="weight_age_slider"
        )
        
        weight_floor = st.slider(
            "🏢 樓層定位",
            min_value=0,
            max_value=100,
            value=template_weights["樓層定位"],
            step=5,
            help="中樓層分數最高",
            key="weight_floor_slider"
        )
        
        weight_layout = st.slider(
            "🛋️ 格局流動性",
            min_value=0,
            max_value=100,
            value=template_weights["格局流動性"],
            step=5,
            help="主流格局分數越高",
            key="weight_layout_slider"
        )
        
        # 計算總和
        total_weight = weight_price + weight_space + weight_age + weight_floor + weight_layout
        
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
            if st.button("💾 套用", use_container_width=True, key="apply_weights"):
                if total_weight == 100:
                    st.session_state.score_weights = {
                        "價格競爭力": weight_price,
                        "空間效率": weight_space,
                        "屋齡優勢": weight_age,
                        "樓層定位": weight_floor,
                        "格局流動性": weight_layout
                    }
                    st.success("✅ 權重已更新！")
                    # 清除分析結果，讓使用者重新分析
                    if 'solo_analysis_result' in st.session_state:
                        del st.session_state['solo_analysis_result']
                    st.rerun()
                else:
                    st.error("❌ 總權重必須為 100%")
        
        with col2:
            if st.button("🔄 重設", use_container_width=True, key="reset_weights"):
                st.session_state.score_weights = {
                    "價格競爭力": 30,
                    "空間效率": 25,
                    "屋齡優勢": 20,
                    "樓層定位": 15,
                    "格局流動性": 10
                }
                st.success("✅ 已重設！")
                # 清除分析結果
                if 'solo_analysis_result' in st.session_state:
                    del st.session_state['solo_analysis_result']
                st.rerun()
        

    if st.sidebar.button("其他功能一", use_container_width=True, key="updata_button"):
        st.sidebar.write("施工中...")

    if st.sidebar.button("💬智能小幫手", use_container_width=True, key="line_button"):
        st.sidebar.write("施工中...")
