# 小幫手專用：單物件嫌惡設施查詢與地圖（不做 AI 相關性批改，以加快對話速度）
import json
import time
import html as html_lib
import requests
import streamlit as st
from streamlit.components.v1 import html as st_html

from components.geocoding import haversine
from components.place_types import NUISANCE_TYPES, is_relevant_nuisance_place

ASSISTANT_NUISANCE_TYPES = [
    "加油站、瓦斯行、瓦斯槽",
    "基地台、電塔、變電所",
    "垃圾場、回收場",
    "市場(傳統市場、夜市)",
    "特種行業、KTV、遊樂場",
    "醫院",
    "工業區、工廠",
    "宮廟、神壇",
    "公墓、靈骨塔、殯儀館",
]

DEFAULT_RADIUS = 500


def _maps_key():
    return st.session_state.get("GMAPS_SERVER_KEY") or st.session_state.get("GOOGLE_MAPS_KEY", "")


def _browser_key():
    return st.session_state.get("GMAPS_BROWSER_KEY") or st.session_state.get("GOOGLE_MAPS_KEY", "")


def _geocode(address, api_key):
    url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {"address": address, "key": api_key, "language": "zh-TW"}
    response = requests.get(url, params=params, timeout=10)
    data = response.json()
    if data.get("status") == "OK" and data.get("results"):
        loc = data["results"][0]["geometry"]["location"]
        return loc["lat"], loc["lng"]
    return None, None


def _search_places(lat, lng, api_key, keyword, radius, place_type=""):
    url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
    params = {
        "query": keyword,
        "location": f"{lat},{lng}",
        "radius": radius,
        "key": api_key,
        "language": "zh-TW",
    }
    if place_type:
        params["type"] = place_type
    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        return []

    results = []
    for place in data.get("results", []):
        loc = place["geometry"]["location"]
        dist = int(haversine(lat, lng, loc["lat"], loc["lng"]))
        if dist > radius:
            continue
        results.append({
            "name": place.get("name", "未命名"),
            "lat": loc["lat"],
            "lng": loc["lng"],
            "distance": dist,
            "place_id": place.get("place_id", ""),
            "types": place.get("types", []),
        })
    return results


def lookup_nearby_nuisances(address, title="", radius=DEFAULT_RADIUS):
    api_key = _maps_key()
    if not api_key:
        return {"error": "請先在側邊欄設定 Google Maps API Key"}
    if not address:
        return {"error": "這間房屋沒有地址，無法查周邊"}

    try:
        lat, lng = _geocode(address, api_key)
    except Exception as exc:
        return {"error": f"地址解析失敗：{exc}"}
    if not lat or not lng:
        return {"error": f"無法解析地址：{address}"}

    seen = set()
    places = []
    for nuisance_type in ASSISTANT_NUISANCE_TYPES:
        keywords = NUISANCE_TYPES.get(nuisance_type, {}).get("keywords", [])[:2]
        impacts = NUISANCE_TYPES.get(nuisance_type, {}).get("impacts", [])
        place_type = "hospital" if nuisance_type == "醫院" else ""
        for keyword in keywords:
            if nuisance_type == "醫院" and "中心" in keyword:
                continue
            for place in _search_places(lat, lng, api_key, keyword, radius, place_type):
                if not is_relevant_nuisance_place(nuisance_type, place["name"], place.get("types")):
                    continue
                pid = place["place_id"] or f"{place['name']}|{place['lat']}|{place['lng']}"
                if pid in seen:
                    continue
                seen.add(pid)
                places.append({
                    **place,
                    "type": nuisance_type,
                    "impacts": impacts,
                    "keyword": keyword,
                })
            time.sleep(0.12)

    places.sort(key=lambda x: x["distance"])
    by_type = {}
    for place in places:
        bucket = by_type.setdefault(place["type"], {
            "type": place["type"],
            "impacts": place["impacts"],
            "count": 0,
            "nearest": "",
            "nearest_m": None,
        })
        bucket["count"] += 1
        if bucket["nearest_m"] is None or place["distance"] < bucket["nearest_m"]:
            bucket["nearest"] = place["name"]
            bucket["nearest_m"] = place["distance"]

    summary_rows = sorted(by_type.values(), key=lambda x: x["nearest_m"] or 10**9)
    nearest = places[0] if places else None
    return {
        "title": title,
        "address": address,
        "lat": lat,
        "lng": lng,
        "radius": radius,
        "total": len(places),
        "by_type": summary_rows,
        "nearest": {
            "name": nearest["name"],
            "type": nearest["type"],
            "distance_m": nearest["distance"],
        } if nearest else None,
        "places": places,
    }


def gemini_nuisance_payload(result):
    if result.get("error"):
        return result
    return {
        "title": result.get("title"),
        "address": result.get("address"),
        "radius": result.get("radius"),
        "total": result.get("total"),
        "by_type": result.get("by_type"),
        "nearest": result.get("nearest"),
        "note": "地圖會顯示在對話卡片下方，請用摘要說明最近的設施與距離，不要列出座標。",
    }


def render_nuisance_result(result):
    if not result:
        return
    if result.get("error"):
        st.warning(result["error"])
        return

    title = result.get("title") or "這間房屋"
    st.markdown(f"#### ⚠️ {title} 周邊嫌惡設施")
    st.caption(f"搜尋半徑 {result.get('radius', DEFAULT_RADIUS)} 公尺｜找到 {result.get('total', 0)} 處")

    rows = result.get("by_type") or []
    if not rows:
        st.info("這個半徑內沒有查到常見嫌惡設施，仍建議到現場確認。")
    else:
        for row in rows:
            impacts = "、".join(row.get("impacts") or [])
            st.markdown(
                f"- **{row['type']}**：{row['count']} 處，最近是「{row['nearest']}」"
                f"（{row['nearest_m']} 公尺）"
                + (f"｜影響：{impacts}" if impacts else "")
            )

    _render_nuisance_map(result)


def _render_nuisance_map(result):
    browser_key = _browser_key()
    if not browser_key:
        st.caption("地圖需要 Google Maps API Key，請在側邊欄設定後再查看。")
        return

    lat, lng = result.get("lat"), result.get("lng")
    if not lat or not lng:
        return

    facilities = []
    for place in result.get("places") or []:
        facilities.append({
            "name": place["name"],
            "category": place["type"],
            "lat": place["lat"],
            "lng": place["lng"],
            "distance": place["distance"],
            "maps_url": (
                f"https://www.google.com/maps/search/?api=1"
                f"&query={place['lat']},{place['lng']}&query_place_id={place.get('place_id','')}"
            ),
        })

    title = html_lib.escape(str(result.get("title") or "房屋"), quote=True)
    address = html_lib.escape(str(result.get("address") or ""), quote=True)
    radius = int(result.get("radius") or DEFAULT_RADIUS)
    facilities_json = json.dumps(facilities, ensure_ascii=False)
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
      <style>
        #map {{ height: 420px; width: 100%; border-radius: 8px; }}
        .info-window {{ padding: 8px; max-width: 240px; }}
      </style>
    </head>
    <body>
      <div id="map"></div>
      <script>
        function initMap() {{
          var center = {{lat: {lat}, lng: {lng}}};
          var map = new google.maps.Map(document.getElementById('map'), {{
            zoom: 16, center: center
          }});
          var home = new google.maps.Marker({{
            position: center, map: map, title: "{title}",
            icon: {{ url: "http://maps.google.com/mapfiles/ms/icons/red-dot.png" }}
          }});
          home.addListener("click", function() {{
            new google.maps.InfoWindow({{
              content: '<div class="info-window"><b>{title}</b><br>{address}</div>'
            }}).open(map, home);
          }});
          var facilities = {facilities_json};
          facilities.forEach(function(f) {{
            var marker = new google.maps.Marker({{
              position: {{lat: f.lat, lng: f.lng}},
              map: map,
              title: f.name,
              icon: {{
                path: google.maps.SymbolPath.CIRCLE,
                scale: 8,
                fillColor: "#dc3545",
                fillOpacity: 0.9,
                strokeColor: "#FFFFFF",
                strokeWeight: 2
              }}
            }});
            marker.addListener("click", function() {{
              new google.maps.InfoWindow({{
                content: '<div class="info-window"><b>' + f.name + '</b><br>' +
                         f.category + '<br>距離 ' + f.distance + ' 公尺<br>' +
                         '<a href="' + f.maps_url + '" target="_blank">在 Google 地圖開啟</a></div>'
              }}).open(map, marker);
            }});
          }});
          new google.maps.Circle({{
            strokeColor: "#FF0000", strokeOpacity: 0.7, strokeWeight: 2,
            fillColor: "#FF0000", fillOpacity: 0.08,
            map: map, center: center, radius: {radius}
          }});
        }}
      </script>
      <script src="https://maps.googleapis.com/maps/api/js?key={browser_key}&callback=initMap" async defer></script>
    </body>
    </html>
    """
    st_html(html_content, height=440, scrolling=False)
