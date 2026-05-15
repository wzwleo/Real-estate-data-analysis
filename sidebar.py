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
    
    with st.sidebar.expander("🎚️ 客製化購屋喜好"):
            
            # 1. 定義數據中心
            system_default = {"w_price": 30, "w_space": 25, "w_age": 20, "w_floor": 15, "w_layout": 10}
            
            templates = {
                "預設": [30, 25, 20, 15, 10], # 自訂的基礎值同系統預設
                "👨‍👩‍👧‍👦 小家庭首購": [40, 15, 15, 10, 20],
                "💼 投資客導向": [35, 15, 20, 10, 20],
                "👴 退休族優先": [20, 20, 25, 25, 10]
            }
            preset_list = list(templates.keys())
    
            # 初始化 Session State
            if 'w_price' not in st.session_state:
                for k, v in system_default.items(): st.session_state[k] = v
            if 'preset_index' not in st.session_state:
                st.session_state.preset_index = 0
    
            # --- 核心邏輯：Callback 函式 ---
            
            def on_reset():
                """智慧重設邏輯"""
                # 取得當前選單選中的名稱 (利用下面 selectbox 的 key)
                current_preset = st.session_state.temp_preset_key
                
                # 取得該模板對應的分數
                target_vals = templates.get(current_preset, templates["預設"])
                
                # 更新 Slider 數值
                st.session_state.w_price = target_vals[0]
                st.session_state.w_space = target_vals[1]
                st.session_state.w_age = target_vals[2]
                st.session_state.w_floor = target_vals[3]
                st.session_state.w_layout = target_vals[4]
                # 清除成功訊息標記
                if 'apply_success' in st.session_state:
                    st.session_state.apply_success = False
    
            def on_preset_change():
                """切換模板時立即同步數值"""
                new_preset = st.session_state.temp_preset_key
                st.session_state.preset_index = preset_list.index(new_preset)
                
                vals = templates[new_preset]
                st.session_state.w_price = vals[0]
                st.session_state.w_space = vals[1]
                st.session_state.w_age = vals[2]
                st.session_state.w_floor = vals[3]
                st.session_state.w_layout = vals[4]
                # 切換模板時也重設成功訊息
                st.session_state.apply_success = False
    
            # 2. 下拉選單
            st.selectbox(
                "快速選擇模板", 
                preset_list, 
                index=st.session_state.preset_index,
                key="temp_preset_key",
                on_change=on_preset_change
            )
    
            # 3. Slider 區域
            st.slider("💰 價格競爭力", 0, 100, step=5, key="w_price")
            st.slider("📐 空間效率", 0, 100, step=5, key="w_space")
            st.slider("🕰️ 屋齡優勢", 0, 100, step=5, key="w_age")
            st.slider("🏢 樓層定位", 0, 100, step=5, key="w_floor")
            st.slider("🛋️ 格局流動性", 0, 100, step=5, key="w_layout")
            
            total_weight = (st.session_state.w_price + st.session_state.w_space + 
                            st.session_state.w_age + st.session_state.w_floor + 
                            st.session_state.w_layout)
    
            st.divider()
    
            # 4. 按鈕區域
            col1, col2 = st.columns(2)
            
            with col2:
                # 這裡的 on_click 會觸發上面寫好的智慧重設
                st.button("🔄 重設", use_container_width=True, on_click=on_reset)
    
            with col1:
                if st.button("💾 套用", use_container_width=True):
                    if total_weight == 100:
                        st.session_state.score_weights = {
                            "價格競爭力": st.session_state.w_price,
                            "空間效率": st.session_state.w_space,
                            "屋齡優勢": st.session_state.w_age,
                            "樓層定位": st.session_state.w_floor,
                            "格局流動性": st.session_state.w_layout
                        }
                        st.session_state.apply_success = True
                    else:
                        st.session_state.apply_success = False
    
            # 5. 訊息顯示 (位於按鈕下方)
            if st.session_state.get('apply_success'):
                st.success("✅ 權重已更新！")
            elif total_weight != 100:
                st.error(f"❌ 總和需為 100% (目前 {total_weight}%)")
        
    with st.sidebar.expander("💰 購屋預算規劃師"):
        
        # ── 初始化 ──
        if 'budget_monthly_income' not in st.session_state:
            st.session_state.budget_monthly_income = 10
        if 'budget_down_payment' not in st.session_state:
            st.session_state.budget_down_payment = 200
        if 'budget_years' not in st.session_state:
            st.session_state.budget_years = 30
        if 'budget_rate' not in st.session_state:
            st.session_state.budget_rate = 2.0
    
        st.caption("📌 根據您的財務狀況試算購屋能力")
        
        # ── 輸入區 ──
        monthly_income = st.number_input(
            "💵 月收入（萬元）",
            min_value=1,
            max_value=500,
            value=st.session_state.budget_monthly_income,
            step=1,
            key="budget_monthly_income",
            help="稅後實際月收入"
        )
    
        down_payment = st.number_input(
            "🏦 頭期款（萬元）",
            min_value=0,
            max_value=10000,
            value=st.session_state.budget_down_payment,
            step=10,
            key="budget_down_payment",
            help="目前可用於頭期款的資金"
        )
    
        loan_years = st.selectbox(
            "📅 貸款年限",
            options=[20, 30, 40],
            index=1,
            key="budget_years",
            help="一般建議 30 年攤還壓力較小"
        )
    
        interest_rate = st.slider(
            "📈 年利率（%）",
            min_value=1.0,
            max_value=5.0,
            value=st.session_state.budget_rate,
            step=0.1,
            format="%.1f%%",
            key="budget_rate",
            help="目前台灣房貸利率約 2.0~2.5%"
        )
    
        st.divider()
    
        # ── 計算核心 ──
        monthly_rate = interest_rate / 100 / 12
        n = loan_years * 12
    
        # 月還款不超過月收入 30% → 反推最高可貸金額
        max_monthly_payment = monthly_income * 10000 * 0.3
    
        if monthly_rate > 0:
            max_loan = max_monthly_payment * (1 - (1 + monthly_rate) ** (-n)) / monthly_rate
        else:
            max_loan = max_monthly_payment * n
    
        max_loan_wan = max_loan / 10000
        max_total_price = max_loan_wan + down_payment
    
        # 頭期款比例（以最高總價為基準）
        down_payment_ratio = (down_payment / max_total_price * 100) if max_total_price > 0 else 0
    
        # 實際月還款（以最高可貸金額計算）
        if monthly_rate > 0:
            actual_monthly = max_loan * monthly_rate / (1 - (1 + monthly_rate) ** (-n))
        else:
            actual_monthly = max_loan / n
    
        # 總利息
        total_paid = actual_monthly * n
        total_interest = total_paid - max_loan
        total_interest_wan = total_interest / 10000
    
        # ── 輸出區 ──
        st.markdown("#### 📊 試算結果")
    
        st.metric("🏠 建議總價上限", f"{max_total_price:.0f} 萬")
        st.metric("🏦 最高可貸金額", f"{max_loan_wan:.0f} 萬")
        st.metric("📅 每月還款金額", f"{actual_monthly/10000:.2f} 萬")
        st.metric("💸 總利息支出", f"{total_interest_wan:.0f} 萬")
        st.metric("📊 頭期款佔比", f"{down_payment_ratio:.1f}%")
    
        st.divider()
    
        # 頭期款比例提示
        if down_payment_ratio >= 30:
            st.success(f"✅ 頭期款佔 {down_payment_ratio:.1f}%，資金充裕，還款壓力較小")
        elif down_payment_ratio >= 20:
            st.info(f"ℹ️ 頭期款佔 {down_payment_ratio:.1f}%，符合銀行建議的兩成標準")
        elif down_payment_ratio >= 10:
            st.warning(f"⚠️ 頭期款佔 {down_payment_ratio:.1f}%，低於建議兩成，貸款成數較高")
        else:
            st.error(f"❌ 頭期款佔 {down_payment_ratio:.1f}%，頭期款不足，建議先累積資金")
    
        # 月還款壓力提示
        payment_ratio = actual_monthly / (monthly_income * 10000) * 100
        if payment_ratio <= 25:
            st.success(f"✅ 月還款佔月收入 {payment_ratio:.1f}%，還款壓力輕鬆")
        elif payment_ratio <= 30:
            st.info(f"ℹ️ 月還款佔月收入 {payment_ratio:.1f}%，在合理範圍內")
        elif payment_ratio <= 40:
            st.warning(f"⚠️ 月還款佔月收入 {payment_ratio:.1f}%，壓力稍重，建議增加頭期款")
        else:
            st.error(f"❌ 月還款佔月收入 {payment_ratio:.1f}%，還款壓力過重")
    
        st.caption("⚠️ 以上為試算參考，實際核貸金額依銀行審核為準")

