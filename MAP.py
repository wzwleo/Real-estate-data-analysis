import streamlit as st
import requests
import folium
from streamlit.components.v1 import html

# 擴充 PLACE_TAGS
PLACE_TAGS = {
    "交通": ['["public_transport"="stop_position"]', '["highway"="bus_stop"]'],
    "醫院": ['["amenity"="hospital"]'],
    "超商": ['["shop"="convenience"]', '["amenity"="convenience"]'],
    "餐廳": ['["amenity"="restaurant"]'],
    "學校": ['["amenity"="school"]', '["amenity"="college"]', '["amenity"="university"]'],
    "銀行": ['["amenity"="bank"]'],
    "加油站": ['["amenity"="fuel"]'],
    "公園": ['["leisure"="park"]']
}

st.title("🌍 地址周邊自動調整範圍查詢 (OSM)")

address = st.text_input("輸入地址", "台北101")
selected_types = st.multiselect("選擇要查詢的類別", PLACE_TAGS.keys(), default=["超商", "交通"])

if st.button("查詢"):
    geo_url = f"https://nominatim.openstreetmap.org/search?format=json&q={address}"
    geo_res = requests.get(geo_url, headers={"User-Agent": "StreamlitApp"}).json()
    
    if geo_res:
        lat, lng = float(geo_res[0]["lat"]), float(geo_res[0]["lon"])
        
        m = folium.Map(location=[lat, lng], zoom_start=16)
        folium.Marker([lat, lng], popup="查詢中心", icon=folium.Icon(color="red")).add_to(m)
        
        all_places = []
        for t in selected_types:
            tags_list = PLACE_TAGS[t]
            found = False
            radius = 400
            while not found and radius <= 1000:
                for tag in tags_list:
                    query = f"""
                    [out:json];
                    (
                      node{tag}(around:{radius},{lat},{lng});
                      way{tag}(around:{radius},{lat},{lng});
                      relation{tag}(around:{radius},{lat},{lng});
                    );
                    out center;
                    """
                    res = requests.post("https://overpass-api.de/api/interpreter",
                                        data=query.encode("utf-8"),
                                        headers={"User-Agent": "StreamlitApp"})
                    data = res.json()
                    
                    for el in data.get("elements", []):
                        if "lat" in el and "lon" in el:
                            name = el["tags"].get("name", "未命名")
                            all_places.append((t, name, el["lat"], el["lon"]))
                            folium.Marker([el["lat"], el["lon"]],
                                          popup=f"{t}: {name}",
                                          icon=folium.Icon(color="blue" if t != "醫院" else "green")
                                         ).add_to(m)
                            found = True
                radius += 200  # 半徑增加 200 公尺
        
        st.subheader("查詢結果")
        if all_places:
            for t, name, lat_, lng_ in all_places:
                st.write(f"**{t}** - {name}")
        else:
            st.write("該範圍內無相關地點。")
        
        map_html = m._repr_html_()
        html(map_html, height=500)
    else:
        st.error("無法解析地址，請確認輸入正確。")
