# compare_page.py

def render_compare_page():
    import streamlit as st
    import requests
    import google.generativeai as genai

    # ===============================
    # 支援查詢的 OSM Tags
    # ===============================
    OSM_TAGS = {
        "交通": {"public_transport": "stop_position"},
        "超商": {"shop": "convenience"},
        "餐廳": {"amenity": "restaurant"},
        "學校": {"amenity": "school"},
        "醫院": {"amenity": "hospital"},
        "藥局": {"amenity": "pharmacy"}
    }

    # ===============================
    # 工具函式
    # ===============================
    def geocode_address(address: str, opencage_key: str):
        url = "https://api.opencagedata.com/geocode/v1/json"
        params = {"q": address, "key": opencage_key, "language": "zh-TW", "limit": 1}
        try:
            res = requests.get(url, params=params, timeout=10).json()
            if res["results"]:
                return res["results"][0]["geometry"]["lat"], res["results"][0]["geometry"]["lng"]
            else:
                return None, None
        except Exception:
            return None, None

    def query_osm(lat, lng, radius=200):
        query_parts = []
        for tag_dict in OSM_TAGS.values():
            for k, v in tag_dict.items():
                query_parts.append(f"""
                  node["{k}"="{v}"](around:{radius},{lat},{lng});
                  way["{k}"="{v}"](around:{radius},{lat},{lng});
                  relation["{k}"="{v}"](around:{radius},{lat},{lng});
                """)
        query = f"""
        [out:json][timeout:25];
        (
            {"".join(query_parts)}
        );
        out center;
        """
        try:
            r = requests.post("https://overpass-api.de/api/interpreter", data=query.encode("utf-8"), timeout=20)
            data = r.json()
        except:
            return {}

        results = {k: [] for k in OSM_TAGS.keys()}
        for el in data.get("elements", []):
            tags = el.get("tags", {})
            name = tags.get("name", "未命名")
            for label, tag_dict in OSM_TAGS.items():
                for k, v in tag_dict.items():
                    if tags.get(k) == v:
                        results[label].append(name)
        return results

    def format_info(address, info_dict):
        lines = [f"房屋（{address}）："]
        for k, v in info_dict.items():
            lines.append(f"- {k}: {len(v)} 個")
        return "\n".join(lines)

    # ===============================
    # UI
    # ===============================
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
        OPENCAGE_KEY = st.session_state.get("OPENCAGE_KEY")
        GEMINI_KEY = st.session_state.get("GEMINI_KEY")

        if not OPENCAGE_KEY or not GEMINI_KEY:
            st.error("❌ 請先設定 OPENCAGE 與 GEMINI API Key")
            st.stop()

        genai.configure(api_key=GEMINI_KEY)

        if not addr_a or not addr_b:
            st.warning("請輸入兩個地址")
            st.stop()

        lat_a, lng_a = geocode_address(addr_a, OPENCAGE_KEY)
        lat_b, lng_b = geocode_address(addr_b, OPENCAGE_KEY)
        if not lat_a or not lat_b:
            st.error("❌ 無法解析其中一個地址")
            st.stop()

        info_a = query_osm(lat_a, lng_a, radius=200)
        info_b = query_osm(lat_b, lng_b, radius=200)

        text_a = format_info(addr_a, info_a)
        text_b = format_info(addr_b, info_b)

        st.session_state["text_a"] = text_a
        st.session_state["text_b"] = text_b

        prompt = f"""
你是一位房地產分析專家，請比較以下兩間房屋的生活機能。
請列出優點與缺點，最後做總結：

{text_a}

{text_b}
"""
        model = genai.GenerativeModel("gemini-2.0-flash")
        response = model.generate_content(prompt)
        st.subheader("📊 Gemini 分析結果")
        st.write(response.text)
        st.session_state["comparison_done"] = True

    if st.session_state["comparison_done"]:
        st.subheader("🏠 房屋資訊對照表")
        st.markdown(f"### 房屋 A\n{st.session_state['text_a']}")
        st.markdown(f"### 房屋 B\n{st.session_state['text_b']}")

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
            response = model.generate_content(chat_prompt)
            st.session_state["chat_history"].append(("🤖", response.text))

        for role, msg in st.session_state["chat_history"]:
            st.markdown(f"**{role}**：{msg}")
