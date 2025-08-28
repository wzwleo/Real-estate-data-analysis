def render_compare_page():
    st.title("🏡 房屋比較 + 💬 對話助手")

    # 初始化狀態
    if "comparison_done" not in st.session_state:
        st.session_state["comparison_done"] = False
    if "chat_history" not in st.session_state:
        st.session_state["chat_history"] = []
    if "text_a" not in st.session_state:
        st.session_state["text_a"] = ""
    if "text_b" not in st.session_state:
        st.session_state["text_b"] = ""

    col1, col2 = st.columns(2)
    with col1:
        addr_a = st.text_input("輸入房屋 A 地址")
    with col2:
        addr_b = st.text_input("輸入房屋 B 地址")

    if st.button("比較房屋"):
        # ✅ 按下按鈕時才檢查 API Key
        OPENCAGE_KEY = st.session_state.get("OPENCAGE_KEY")
        GEMINI_KEY = st.session_state.get("GEMINI_KEY")

        if not OPENCAGE_KEY or not GEMINI_KEY:
            st.error("❌ 請先設定 OPENCAGE 與 GEMINI API Key")
            st.stop()

        # 設定 Gemini API
        genai.configure(api_key=GEMINI_KEY)

        if not addr_a or not addr_b:
            st.warning("請輸入兩個地址")
            st.stop()

        lat_a, lng_a = geocode_address(addr_a, OPENCAGE_KEY)
        lat_b, lng_b = geocode_address(addr_b, OPENCAGE_KEY)
        if not lat_a or not lat_b:
            st.error("❌ 無法解析其中一個地址")
            st.stop()

        # 查詢 OSM
        info_a = query_osm(lat_a, lng_a, radius=200)
        info_b = query_osm(lat_b, lng_b, radius=200)

        # 格式化資訊
        text_a = format_info(addr_a, info_a)
        text_b = format_info(addr_b, info_b)

        st.session_state["text_a"] = text_a
        st.session_state["text_b"] = text_b

        # 組合 prompt
        prompt = f"""
你是一位房地產分析專家，請比較以下兩間房屋的生活機能。
請列出優點與缺點，最後做總結：

{text_a}

{text_b}
"""
        model = genai.GenerativeModel("gemini-2.0-flash")
        response = model.generate_content(prompt)  # ✅ 傳入 prompt

        st.subheader("📊 Gemini 分析結果")
        st.write(response.text)
        st.session_state["comparison_done"] = True

    # 顯示房屋資訊
    if st.session_state["comparison_done"]:
        st.subheader("🏠 房屋資訊對照表")
        st.markdown(f"### 房屋 A\n{st.session_state['text_a']}")
        st.markdown(f"### 房屋 B\n{st.session_state['text_b']}")

        # 簡單對話框
        st.header("💬 對話框")
        with st.form("chat_form", clear_on_submit=True):
            user_input = st.text_input("你想問什麼？", placeholder="請輸入問題...")
            submitted = st.form_submit_button("🚀 送出")

        if submitted and user_input:
            st.session_state["chat_history"].append(("👤", user_input))
            chat_prompt = f"""
以下是兩間房屋的周邊資訊：

{st.session_state['text_a']}

{st.session_state['text_b']}

使用者問題：{user_input}

請根據房屋周邊的生活機能與位置，提供有意義的回答。
"""
            model = genai.GenerativeModel("gemini-2.0-flash")
            response = model.generate_content(chat_prompt)  # ✅ 傳入 chat_prompt
            st.session_state["chat_history"].append(("🤖", response.text))

        for role, msg in st.session_state["chat_history"]:
            st.markdown(f"**{role}**：{msg}")
