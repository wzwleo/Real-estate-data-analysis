import streamlit as st
import pandas as pd
import requests
import math
import time
from streamlit.components.v1 import html
from components.solo_analysis import tab1_module
import google.generativeai as genai

# ===========================
# 收藏與分析功能
# ===========================
def get_favorites_data():
    """取得收藏房產的資料"""
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
    fav_df = all_df[all_df['編號'].isin(fav_ids)].copy()
    return fav_df


def render_favorites_list(fav_df):
    """渲染收藏清單"""
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

                property_url = f"https://www.sinyi.com.tw/buy/house/{row['編號']}?breadcrumb=list"
                st.markdown(f'[🔗 物件連結]({property_url})')
            st.markdown("---")

# ===========================
# Google Places Keyword 搜尋與地圖顯示
# ===========================
PLACE_TYPES = {
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

def haversine(lat1, lon1, lat2, lon2):
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(d_lambda/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

@st.cache_data(show_spinner=False)
def safe_google_request(url, params):
    time.sleep(0.12)  # 節流
    try:
        res = requests.get(url, params=params, timeout=10)
        return res.json()
    except Exception:
        return {}

def geocode_address(address: str, api_key: str):
    if not api_key:
        return None, None
    url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {"address": address, "key": api_key, "language": "zh-TW"}
    r = safe_google_request(url, params)
    if r.get("status") == "OK" and r.get("results"):
        loc = r["results"][0]["geometry"]["location"]
        return loc["lat"], loc["lng"]
    return None, None

def query_google_places(lat, lng, api_key, selected_categories, radius=500, extra_keyword=""):
    """僅使用 Keyword 搜尋"""
    results = []
    if not api_key:
        return results

    for cat in selected_categories:
        for kw in PLACE_TYPES.get(cat, []):
            params = {
                "location": f"{lat},{lng}",
                "radius": radius,
                "keyword": kw,
                "key": api_key,
                "language": "zh-TW"
            }
            res = safe_google_request("https://maps.googleapis.com/maps/api/place/nearbysearch/json", params)
            for p in res.get("results", []):
                p_lat = p["geometry"]["location"]["lat"]
                p_lng = p["geometry"]["location"]["lng"]
                dist = int(haversine(lat, lng, p_lat, p_lng))
                if dist <= radius:
                    results.append((cat, kw, p.get("name","未命名"), p_lat, p_lng, dist, p.get("place_id","")))

    # 額外關鍵字
    if extra_keyword:
        params = {
            "location": f"{lat},{lng}",
            "radius": radius,
            "keyword": extra_keyword,
            "key": api_key,
            "language": "zh-TW"
        }
        res = safe_google_request("https://maps.googleapis.com/maps/api/place/nearbysearch/json", params)
        for p in res.get("results", []):
            p_lat = p["geometry"]["location"]["lat"]
            p_lng = p["geometry"]["location"]["lng"]
            dist = int(haversine(lat, lng, p_lat, p_lng))
            if dist <= radius:
                results.append(("關鍵字", extra_keyword, p.get("name","未命名"), p_lat, p_lng, dist, p.get("place_id","")))

    # 移除重複 place_id 並排序
    seen = set()
    uniq = []
    for item in sorted(results, key=lambda x: x[5]):
        pid = item[6] or (item[2]+str(item[3])+str(item[4]))
        if pid in seen:
            continue
        seen.add(pid)
        uniq.append(item)
    return uniq

def render_map(lat, lng, places, radius, title="房屋"):
    if not st.session_state.get('GOOGLE_MAPS_KEY'):
        st.warning("⚠️ 尚未設定 Google Maps API Key，無法顯示地圖")
        return

    markers_js = ""
    for cat, kw, name, p_lat, p_lng, dist, pid in places:
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
    <div id="map" style="height:400px;"></div>
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
            title: "{title}",
            icon: {{ url: "
