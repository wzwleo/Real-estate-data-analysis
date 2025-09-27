import streamlit as st
import pandas as pd
import requests
import math
from streamlit.components.v1 import html
import google.generativeai as genai

# ===============================
# 類別與顏色設定
# ===============================
PLACE_TYPES_MAP = {
    "教育": ["圖書館", "幼兒園", "小學", "學校", "中學", "大學"],
    "健康與保健": ["牙醫", "醫師", "藥局", "醫院"],
    "購物": ["便利商店", "超市", "百貨公司"],
    "交通運輸": ["公車站", "地鐵站", "火車站"],
    "餐飲": ["餐廳"]
}
CATEGORY_COLORS = {
    "教育": "#1E90FF",
    "健康與保健": "#32CD32",
    "購物": "#FF8C00",
    "交通運輸": "#800080",
    "餐飲": "#FF0000",
    "關鍵字": "#000000"
}

# ===============================
# 通用距離計算
# ===============================
def haversine(lat1, lon1, lat2, lon2):
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(d_lambda/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

# ===============================
# 地址周邊查詢
# ===============================
def render_address_search():
    st.title("🏙️ 地址周邊查詢（多類別按鈕 + 彩色標記 + 關鍵字顏色）")

    google_api_key = st.session_state.get("GOOGLE_MAPS_KEY", "")
    address = st.text_input("輸入地址")
    radius = 500  # 🔒 固定半徑 500 公尺
    keyword = st.text_input("輸入關鍵字")

    st.subheader("選擇大類別（可多選）")
    selected_categories = []
    cols = st.columns(len(PLACE_TYPES_MAP))
    for i, cat in enumerate(PLACE_TYPES_MAP):
        color = CATEGORY_COLORS[cat]
        with cols[i]:
            st.markdown(
                f'<span style="display:inline-block;width:12px;height:12px;border-radius:50%;background:{color};margin-right:4px"></span>',
                unsafe_allow_html=True,
            )
            if st.toggle(cat, key=f"cat_{cat}"):
                selected_categories.append(cat)

    if keyword:
        st.markdown(
            f'<span style="display:inline-block;width:12px;height:12px;border-radius:50%;background:{CATEGORY_COLORS["關鍵字"]};margin-right:4px"></span>'
            f'**關鍵字搜尋結果顏色**',
            unsafe_allow_html=True,
        )

    def search_places():
        if not google_api_key:
            st.error("請在側邊欄輸入 Google Maps API Key")
            return
        if not address:
            st.error("請輸入地址")
            return
        if not selected_categories and not keyword:
            st.error("請至少選擇一個大類別或輸入關鍵字")
            return

        geo_url = "https://maps.googleapis.com/maps/api/geocode/json"
        geo_res = requests.get(geo_url,
            params={"address": address, "key": google_api_key, "language": "zh-TW"}).json()
        if geo_res.get("status") != "OK":
            st.error("無法解析該地址")
            return

        lat, lng = geo_res["results"][0]["geometry"]["location"].values()
        all_places = []

        # 大類別搜尋
        for cat in selected_categories:
            for kw in PLACE_TYPES_MAP[cat]:
                params = {
                    "location": f"{lat},{lng}",
                    "radius": radius,
                    "keyword": kw,
                    "key": google_api_key,
                    "language": "zh-TW"
                }
                res = requests.get("https://maps.googleapis.com/maps/api/place/nearbysearch/json", params=params).json()
                for p in res.get("results", []):
                    p_lat = p["geometry"]["location"]["lat"]
                    p_lng = p["geometry"]["location"]["lng"]
                    dist = int(haversine(lat, lng, p_lat, p_lng))
                    if dist <= radius:
                        all_places.append((cat, kw, p.get("name", "未命名"), p_lat, p_lng, dist, p.get("place_id", "")))

        # 關鍵字搜尋
        if keyword:
            params = {
                "location": f"{lat},{lng}",
                "radius": radius,
                "keyword": keyword,
                "key": google_api_key,
                "language": "zh-TW"
            }
            res = requests.get("https://maps.googleapis.com/maps/api/place/nearbysearch/json", params=params).json()
            for p in res.get("results", []):
                p_lat = p["geometry"]["location"]["lat"]
                p_lng = p["geometry"]["location"]["lng"]
                dist = int(haversine(lat, lng, p_lat, p_lng))
                if dist <= radius:
                    all_places.append(("關鍵字", keyword, p.get("name", "未命名"), p_lat, p_lng, dist, p.get("place_id", "")))

        all_places.sort(key=lambda x: x[5])
        st.write("搜尋半徑固定：500 公尺")
        st.subheader("查詢結果")
        if not all_places:
            st.write("範圍內無符合地點。")
            return

        for cat, kw, name, _, _, dist, _ in all_places:
            st.write(f"**[{cat}]** {kw} - {name} ({dist} 公尺)")

        st.sidebar.subheader("Google 地圖連結")
        for cat, kw, name, _, _, dist, pid in all_places:
            if pid:
                st.sidebar.markdown(f"- [{name} ({dist}m)](https://www.google.com/maps/place/?q=place_id:{pid})")

        # Google Maps 標記與圓形範圍
        markers_js = ""
        for cat, kw, name, p_lat, p_lng, dist, pid in all_places:
            color = CATEGORY_COLORS.get(cat, "#000000")
            gmap_url = f"https://www.google.com/maps/place/?q=place_id:{pid}" if pid else ""
            info = f'{cat}-{kw}: <a href="{gmap_url}" target="_blank">{name}</a><br>距離中心 {dist} 公尺'
            markers_js += f"""
            new google.maps.Marker({{
                position: {{lat: {p_lat}, lng: {p_lng}}},
                map: map,
                title: "{cat}-{name}",
                icon: {{
                    path: google.maps.SymbolPath.CIRCLE,
                    scale: 7,
                    fillColor: "{color}",
                    fillOpacity: 1,
                    strokeColor: "white",
                    strokeWeight: 1
                }}
            }}).addListener("click", function() {{
                new google.maps.InfoWindow({{content: `{info}`}}).open(map, this);
            }});
            """

        circle_js = f"""
            new google.maps.Circle({{
                strokeColor: "#FF0000",
                strokeOpacity: 0.8,
                strokeWeight: 2,
                fillColor: "#FF0000",
                fillOpacity: 0.1,
                map: map,
                center: center,
                radius: {radius}
            }});
        """

        map_html = f"""
        <div id="map" style="height:500px;"></div>
        <script>
        function initMap() {{
            var center = {{lat: {lat}, lng: {lng}}};
            var map = new google.maps.Map(document.getElementById('map'), {{
                zoom: 16,
                center: center
            }});
            new google.maps.Marker({{
                position: center,
                map: map,
                title: "查詢中心",
                icon: {{ url: "http://maps.google.com/mapfiles/ms/icons/red-dot.png" }}
            }});
            {circle_js}
            {markers_js}
        }}
        </script>
        <script src="https://maps.googleapis.com/maps/api/js?key={google_api_key}&callback=initMap" async defer></script>
        """
        html(map_html, height=500)

    if st.button("開始查詢", use_container_width=True):
        search_places()

# ===============================
# 房產收藏與分析（保留原有提示文字）
# ===============================
def get_favorites_data():
    if 'favorites' not in st.session_state or not st.session_state.favorites:
        return pd.DataFrame()
    all_df = None
    if 'all_properties_df' in st.session_state and not st.session_state.all_properties_df.empty:
        all_df = st.session_state.all_properties_df
    elif 'filtered_df' in st.session_state and not st.session_state.filtered_df.empty:
        all_df = st.session_state.filtered_df
    if all_df is None or all_df.empty:
        return pd.DataFrame()
    fav_ids = st.session_state.favorites
    return all_df[all_df['編號'].isin(fav_ids)].copy()

def render_favorites_list(fav_df):
    st.subheader("⭐ 我的收藏清單")
    for idx, (_, row) in enumerate(fav_df.iterrows()):
        with st.container():
            col1, col2 = st.columns([8, 2])
            with col1:
                st.markdown(f"**#{idx+1} 🏠 {row['標題']}**")
                st.write(f"**地址：** {row['地址']} | **屋齡：** {row['屋齡']} | **類型：** {row['類型']}")
                st.write(f"**建坪：** {row['建坪']} | **格局：** {row['格局']} | **樓層：** {row['樓層']}")
                if '車位' in row and pd.notna(row['車位']):
                    st.write(f"**車位：** {row['車位']}")
            with col2:
                st.metric("總價", f"{row['總價(萬)']} 萬")
                if pd.notna(row['建坪']) and row['建坪'] > 0:
                    unit_price = (row['總價(萬)'] * 10000) / row['建坪']
                    st.caption(f"單價: ${unit_price:,.0f}/坪")
                property_id = row['編號']
                if st.button("❌ 移除", key=f"remove_fav_{property_id}"):
                    st.session_state.favorites.remove(property_id)
                    st.rerun()
                st.markdown(f'[🔗 物件連結](https://www.sinyi.com.tw/buy/house/{row["編號"]}?breadcrumb=list)')
            st.markdown("---")


# ===============================
# 側邊欄與主程式
# ===============================
def render_sidebar():
    st.sidebar.title("📑 導航")
    page = st.sidebar.radio(
        "選擇頁面",
        ["🏠 首頁", "🔍 房產搜尋頁面", "📊 分析頁面", "🌐 地址周邊查詢"],
        key="nav_radio"
    )
    if page == "🏠 首頁": st.session_state.current_page = 'home'
    elif page == "🔍 房產搜尋頁面": st.session_state.current_page = 'search'
    elif page == "📊 分析頁面": st.session_state.current_page = 'analysis'
    elif page == "🌐 地址周邊查詢": st.session_state.current_page = 'address'

    st.sidebar.title("⚙️ 設置")
    st.session_state["GEMINI_KEY"] = st.sidebar.text_input(
        "Gemini API Key", type="password",
        value=st.session_state.get("GEMINI_KEY", "")
    )
    st.session_state["GOOGLE_MAPS_KEY"] = st.sidebar.text_input(
        "Google Maps API Key", type="password",
        value=st.session_state.get("GOOGLE_MAPS_KEY", "")
    )

def main():
    st.set_page_config(page_title="房產分析系統 (整合版)", layout="wide")
    if "current_page" not in st.session_state:
        st.session_state.current_page = "home"

    render_sidebar()

    if st.session_state.current_page == "home":
        st.title("🏠 首頁")
        st.write("歡迎使用整合版房產分析與地址查詢系統")

    elif st.session_state.current_page == "search":
        st.title("🔍 房產搜尋頁面")
        st.info("🚧 原搜尋功能開發中...")

    elif st.session_state.current_page == "analysis":
        render_analysis_page()

    elif st.session_state.current_page == "address":
        render_address_search()

if __name__ == "__main__":
    main()
