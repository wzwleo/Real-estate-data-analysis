import streamlit as st
import requests
import math
import folium
from streamlit.components.v1 import html
import google.generativeai as genai

# ===============================
# Google Places 類別
# ===============================
# 房屋比較用
PLACE_TYPES_COMPARE = {
    "交通": ["bus_stop", "subway_station", "train_station"],
    "超商": ["convenience_store"],
    "餐廳": ["restaurant", "cafe"],
    "學校": ["school", "university", "primary_school", "secondary_school"],
    "醫院": ["hospital"],
    "藥局": ["pharmacy"],
}

# 周邊查詢用
PLACE_TYPES_SEARCH = {
    "教育": ["圖書館", "幼兒園", "小學", "學校", "中學", "大學"],
    "健康與保健": ["牙醫", "醫師", "藥局", "醫院"],
    "購物": ["便利商店", "超市", "百貨公司"],
    "交通運輸": ["公車站", "地鐵站", "火車站"],
    "餐飲": ["餐廳"]
}

# 標記顏色
CATEGORY_COLORS = {
    "教育": "#1E90FF",
    "健康與保健": "#32CD32",
    "購物": "#FF8C00",
    "交通運輸": "#800080",
    "餐飲": "#FF0000",
    "關鍵字": "#000000"
}

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

def haversine(lat1, lon1, lat2, lon2):
    """計算兩點間的球面距離（公尺）"""
    R = 6371000
    dlat, dlon = math.radians(lat2-lat1), math.radians(lon2-lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1))*math.cos(math.radians(lat2))*math.sin(dlon/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

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

def format_info(address, info_dict):
    """將查詢結果格式化為文字"""
    lines = [f"房屋（{address}）："]
    for k, v in info_dict.items():
        lines.append(f"- {k}: {len(v)} 個")
    return "\n".join(lines)

def add_markers(m, info_dict, color):
    """在 Folium 地圖上添加標記"""
    for category, places in info_dict.items():
        for name, lat, lng, dist in places:
            folium.Marker(
                [lat, lng],
                popup=f"{category}：{name}（{dist} 公尺）",
                icon=folium.Icon(color=color, icon="info-sign"),
            ).add_to(m)

def query_google_places_by_keyword(lat, lng, api_key, selected_categories, keyword, radius):
    """根據 Places API 的 keyword 參數查詢（周邊查詢用）"""
    all_places = []

    for cat in selected_categories:
        for kw in PLACE_TYPES_SEARCH[cat]:
            params = {
                "location": f"{lat},{lng}",
                "radius": radius,
                "keyword": kw + (f" {keyword}" if keyword else ""),
                "key": api_key,
                "language": "zh-TW"
            }
            res = requests.get("https://maps.googleapis.com/maps/api/place/nearbysearch/json", params=params).json()
            for p in res.get("results", []):
                p_lat = p["geometry"]["location"]["lat"]
                p_lng = p["geometry"]["location"]["lng"]
                dist = int(haversine(lat, lng, p_lat, p_lng))
                if dist <= radius:
                    all_places.append((cat, kw, p.get("name", "未命名"), p_lat, p_lng, dist, p.get("place_id", "")))

    if keyword and not selected_categories:
        params = {
            "location": f"{lat},{lng}",
            "radius": radius,
            "keyword": keyword,
            "key": api_key,
            "language": "zh-TW"
        }
        res = requests.get("https://maps.googleapis.com/maps/api/place/nearbysearch/json", params=params).json()
        for p in res.get("results", []):
            p_lat = p["geometry"]["location"]["lat"]
            p_lng = p["geometry"]["location"]["lng"]
            dist = int(haversine(lat, lng, p_lat, p_lng))
            if dist <= radius:
                all_places.append(("關鍵字", keyword, p.get("name", "未命名"), p_lat, p_lng, dist, p.get("place_id", "")))
    
    return all_places


def render_map_with_markers(lat, lng, api_key, all_places, radius):
    """渲染帶有標記的 Google Maps"""
    markers_js = ""
    for cat, kw, name, p_lat, p_lng, dist, pid in all_places:
        color = CATEGORY_COLORS.get(cat, "#000000")
        gmap_url = f"https://www.google.com/maps/place/?q=place_id:{pid}" if pid else ""
        info = f'[{cat}-{kw}]: <a href="{gmap_url}" target="_blank">{name}</a><br>距離中心 {dist} 公尺'
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
    <script async defer src="https://maps.googleapis.com/maps/api/js?key={api_key}&callback=initMap"></script>
    """
    html(map_html, height=500)

# ===============================
# Streamlit 介面
# ===============================
st.set_page_config(layout="wide", page_title="🏠 房屋生活機能查詢與比較")

st.title("🏠 房屋生活機能查詢與比較")

#
