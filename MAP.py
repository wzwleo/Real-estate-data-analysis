import streamlit as st
import requests
import folium
import os
from streamlit.components.v1 import html
from dotenv import load_dotenv

# 載入本地 .env（如果有的話）
load_dotenv()

# 取得 OpenCage API Key
API_KEY = os.getenv("OPENCAGE_API_KEY")
if not API_KEY:
    st.error("請先設定環境變數 OPENCAGE_API_KEY")
    st.stop()

PLACE_TAGS = {
    "交通": '["public_transport"="stop_position"]',
    "醫院": '["amenity"="hospital"]',
    "超商": '["shop"="convenience"]',
    "餐廳": '["amenity"="restaurant"]',
    "學校": '["amenity"="school"]'
}

st.title("🌍 地址周邊400公尺查詢 (OSM + OpenCage)")

address = st.text_input("輸入地址")
selected_types = st.multiselect("選擇要查詢的類別", PLACE_TAGS.keys(), default=["超商", "交通"])

if st.button("查詢"):
    # 1️⃣ 用 OpenCage Geocoder 轉經緯度
    geo_url = "https://api.opencagedata.com/geocode/v1/json"
    params = {
        "q": address,
        "key": API_KEY,
        "language": "zh-TW",
        "limit": 1
    }
    try:
        geo_res = requests.get(geo_url, params=params, timeout=10).json()
        if geo_res["results"]:
            lat = geo_res["results"][0]["geometry"]["lat"]
            lng = geo_res["results"][0]["geometry"]["lng"]
        else:
            st.error("無法解析該地址")
            st.stop()
    except requests.exceptions.RequestException as e:
        st.error(f"無法連線到 OpenCage: {e}")
        st.stop()

    # 2️⃣ 建立 Folium 地圖
    m = folium.Map(location=[lat, lng], zoom_start=16)
    folium.Marker([lat, lng], popup="查詢中心", icon=folium.Icon(color="red")).add_to(m)

    all_places = []
    for t in selected_types:
        tag = PLACE_TAGS[t]
        query = f"""
        [out:json];
        (
          node{tag}(around:200,{lat},{lng});
          way{tag}(around:200,{lat},{lng});
          relation{tag}(around:200,{lat},{lng});
        );
        out center;
        """
        try:
            res = requests.post(
                "https://overpass-api.de/api/interpreter",
                data=query.encode("utf-8"),
                headers={"User-Agent": "StreamlitApp"},
                timeout=20
            )
            data = res.json()
        except requests.exceptions.RequestException as e:
            st.warning(f"無法查詢 {t}: {e}")
            continue

        for el in data.get("elements", []):
            if "lat" in el and "lon" in el:
                name = el["tags"].get("name", "未命名")
                all_places.append((t, name))
                folium.Marker(
                    [el["lat"], el["lon"]],
                    popup=f"{t}: {name}",
                    icon=folium.Icon(color="blue" if t != "醫院" else "green")
                ).add_to(m)

    # 3️⃣ 顯示結果與地圖
    st.subheader("查詢結果")
    if all_places:
        for t, name in all_places:
            st.write(f"**{t}** - {name}")
    else:
        st.write("該範圍內無相關地點。")

    map_html = m._repr_html_()
    html(map_html, height=500)


