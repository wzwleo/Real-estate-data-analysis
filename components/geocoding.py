# components/geocoding.py
import math
import requests
import streamlit as st


def haversine(lat1, lon1, lat2, lon2):
    """計算兩點間的大圓距離"""
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    
    a = (
        math.sin(d_phi/2)**2 +
        math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda/2)**2
    )
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def geocode_address(address: str, api_key: str = None):
    """將地址轉換為經緯度座標"""
    if api_key is None:
        api_key = st.session_state.get("GMAPS_SERVER_KEY") or st.session_state.get("GOOGLE_MAPS_KEY", "")
    
    if not api_key:
        st.error("❌ 缺少 Google Maps API Key")
        return None, None
    
    url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {"address": address, "key": api_key, "language": "zh-TW"}
    
    try:
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
    except Exception as e:
        st.error(f"地址解析失敗: {e}")
        return None, None
    
    if data.get("status") == "OK" and data.get("results"):
        loc = data["results"][0]["geometry"]["location"]
        return loc["lat"], loc["lng"]
    
    return None, None
