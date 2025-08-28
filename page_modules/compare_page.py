# compare_page.py
def render_compare_page():
    import streamlit as st
    import requests
    import google.generativeai as genai
    import os
    from dotenv import load_dotenv

    # ===============================
    # 載入環境變數
    # ===============================
    load_dotenv()
    OPENCAGE_KEY = os.getenv("OPENCAGE_API_KEY")
    GEMINI_KEY = os.getenv("GEMINI_API_KEY")

    if not OPENCAGE_KEY or not GEMINI_KEY:
        st.error("請先設定 OPENCAGE_API_KEY 與 GEMINI_API_KEY")
        st.stop()

    genai.configure(api_key=GEMINI_KEY)

    # ===============================
    # OSM Tags
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
    def geocode_address(address: str):
        url = "https://api.opencagedata.com/geocode/v1/json"
        params = {"q": address, "key": OPENCAGE_KEY, "language": "zh-TW", "limit": 1}
        try:
            res = requests.get(url, params=params, timeout=10).json()
            if res["results"]:
                return res["results"][0]["geometry"]["lat"], res["results"][0]["geometry"]["lng"]
            else:
                return None, None
        except:
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

    def format_info(info_dict):
        return ", ".join([f"{k}:{len(v)}" for k, v in info_dict.items()])

    # ===============================
    # UI
    # ===============================
    st.title("房屋比較 + 對話助手")

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
        if not addr_a or not addr_b:
            st.warning("請輸入兩個地址")
            st.stop()

        lat_a, lng_a = geocode_address(addr_a)
        lat_b, lng_b = geocode_address(addr_b)
        if lat_a is None or lat_b is None:
            st.error("無法解析其中一個地址")
            st.stop()

        info_a = query_osm(lat_a, lng_a)
        info_b = query_osm(lat_b, lng_b)

        text_a_line = format_info(info_a)
        text_b_line = format_info(info_b)
        st.session_state["text_a"] = text_a_line
        st.session_state["text_b"] = text_b_line

        # 新版 Gemini 呼叫
        prompt = f"請比較兩間房屋的生活機能，列出優缺點並做總結：\n房屋A: {text_a_line}\n房屋B: {text_b_line}"
        model = genai.GenerativeModel("gemini-2.0-flash")
        response = model.generate_content(input=[{"role": "user", "content": prompt}])
        st.subheader("分析結果")
        st.write(response.text)
        st.session_state["comparison_done"] = True

    # 對話框（保留上下文）
    if st.session_state["comparison_done"]:
        st.header("💬 對話框")
        with st.form("chat_form", clear_on_submit=True):
            user_input = st.text_input("你想問什麼？", placeholder="請輸入問題...")
            submitted = st.form_submit_button("送出")

        if submitted and user_input:
            # 把歷史對話也帶進 prompt
            chat_history_prompt = ""
            for role, msg in st.session_state["chat_history"]:
                chat_history_prompt += f"{role}: {msg}\n"

            chat_prompt = f"{chat_history_prompt}使用者: {user_input}\n請根據房屋周邊生活機能回答。"

            model = genai.GenerativeModel("gemini-2.0-flash")
            response = model.generate_content(input=[{"role": "user", "content": chat_prompt}])
            st.session_state["chat_history"].append(("使用者", user_input))
            st.session_state["chat_history"].append(("AI", response.text))

        for role, msg in st.session_state["chat_history"]:
            st.markdown(f"**{role}**：{msg}")
