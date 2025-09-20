import streamlit as st
import requests
import math
import folium
from streamlit.components.v1 import html
import google.generativeai as genai

# ===============================
# 工具函式
# ===============================

def geocode_address(address: str, api_key: str):
    """將地址轉換為經緯度"""
    url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {"address": address, "key": api_key, "language": "zh-TW"}
    r = requests.get(url, params=params, timeout=10).json()
    if r.get("status") == "OK" and r["results"]:
        loc = r["results"][0]["geometry"]["location"]
        return loc["lat"], loc["lng"]
    return None, None

def query_google_places_by_type(lat, lng, api_key, selected_categories, radius=500):
    """根據 Places API 的 type 參數查詢（房屋比較用）"""
    results = {k: [] for k in selected_categories}
    for label in selected_categories:
        for t in PLACE_TYPES_COMPARE[label]:
            url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
            params = {
                "location": f"{lat},{lng}",
                "radius": radius,
                "type": t,
                "language": "zh-TW",
                "key": api_key,
            }
            r = requests.get(url, params=params, timeout=10).json()
            for place in r.get("results", []):
                name = place.get("name", "未命名")
                p_lat = place["geometry"]["location"]["lat"]
                p_lng = place["geometry"]["location"]["lng"]
                dist = int(haversine(lat, lng, p_lat, p_lng))
                results[label].append((name, p_lat, p_lng, dist))
    return results

# ===============================
# Streamlit 介面
# ===============================

st.set_page_config(layout="wide", page_title="🏠 房屋生活機能查詢與比較")

st.title("🏠 房屋生活機能查詢與比較")

# 取得 API 金鑰
google_key = st.session_state.get("GOOGLE_MAPS_KEY", "")
gemini_key = st.session_state.get("GEMINI_KEY", "")

if not google_key or not gemini_key:
    st.info("請先在側邊欄輸入 Google Maps 與 Gemini API 金鑰")
    st.stop()
else:
    # 設定 Gemini API 金鑰
    genai.configure(api_key=gemini_key)

# 功能選擇
option = st.sidebar.radio(
    "選擇功能",
    ("房屋比較與分析", "單一地址周邊查詢")
)

if option == "房屋比較與分析":
    st.header("🏠 房屋比較 + 雙地圖 + Gemini 分析")
    col1, col2 = st.columns(2)
    with col1:
        addr_a = st.text_input("房屋 A 地址")
    with col2:
        addr_b = st.text_input("房屋 B 地址")

    radius = st.slider("搜尋半徑 (公尺)", min_value=100, max_value=2000, value=500, step=50)

    st.subheader("選擇要比較的生活機能類別")
    selected_categories = []
    cols = st.columns(3)
    for idx, cat in enumerate(PLACE_TYPES_COMPARE.keys()):
        if cols[idx % 3].checkbox(cat, value=True):
            selected_categories.append(cat)

    if st.button("比較房屋", use_container_width=True):
        if not addr_a or not addr_b:
            st.warning("請輸入兩個地址")
            st.stop()
        if not selected_categories:
            st.warning("請至少選擇一個類別")
            st.stop()

        with st.spinner("正在查詢並分析..."):
            lat_a, lng_a = geocode_address(addr_a, google_key)
            lat_b, lng_b = geocode_address(addr_b, google_key)
            if not lat_a or not lat_b:
                st.error("❌ 無法解析其中一個地址，請檢查地址是否正確。")
                st.stop()

            info_a = query_google_places_by_type(lat_a, lng_a, google_key, selected_categories, radius=radius)
            info_b = query_google_places_by_type(lat_b, lng_b, google_key, selected_categories, radius=radius)

            text_a = format_info(addr_a, info_a)
            text_b = format_info(addr_b, info_b)
            
            st.subheader("📍 房屋 A 周邊地圖")
            m_a = folium.Map(location=[lat_a, lng_a], zoom_start=15)
            folium.Marker([lat_a, lng_a], popup=f"房屋 A：{addr_a}", icon=folium.Icon(color="red", icon="home")).add_to(m_a)
            add_markers(m_a, info_a, "red")
            html(m_a._repr_html_(), height=400)

            st.subheader("📍 房屋 B 周邊地圖")
            m_b = folium.Map(location=[lat_b, lng_b], zoom_start=15)
            folium.Marker([lat_b, lng_b], popup=f"房屋 B：{addr_b}", icon=folium.Icon(color="blue", icon="home")).add_to(m_b)
            add_markers(m_b, info_b, "blue")
            html(m_b._repr_html_(), height=400)

            prompt = f"""你是一位房地產分析專家，請比較以下兩間房屋的生活機能，並列出優缺點與結論：
            {text_a}
            {text_b}
            """
            model = genai.GenerativeModel("gemini-1.5-flash")
            response = model.generate_content(prompt)

            st.subheader("📊 Gemini 分析結果")
            st.markdown(response.text)
