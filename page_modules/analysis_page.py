import streamlit as st
import requests
import math
from streamlit.components.v1 import html


def render_analysis_page():
    """
    渲染分析頁面：Google Maps API 周邊地點查詢
    """
    st.title("📊 分析頁面")
    st.header("地址周邊 400 公尺查詢（Google Maps 版）")

    # 使用者輸入 Google API Key 與地址
    google_api_key = st.text_input("輸入 Google Maps API Key", type="password")
    address = st.text_input("輸入地址")
    radius = 600  # 搜尋半徑（公尺）

    # 分類 + 子類別
    PLACE_TYPES = {
        "教育": {
            "圖書館": "library",
            "幼兒園": "preschool",
            "小學": "primary_school",
            "學校": "school",
            "中學": "secondary_school",
            "大學": "university",
        },
        "健康與保健": {
            "整脊診所": "chiropractor",
            "牙科診所": "dental_clinic",
            "牙醫": "dentist",
            "醫師": "doctor",
            "藥局": "pharmacy",
            "醫院": "hospital",
            "藥妝店": "drugstore",
            "醫學檢驗所": "medical_lab",
            "物理治療所": "physiotherapist",
            "按摩": "massage",
            "三溫暖": "sauna",
            "皮膚科診所": "skin_care_clinic",
            "SPA": "spa",
            "日曬工作室": "tanning_studio",
            "健康中心": "wellness_center",
            "瑜伽教室": "yoga_studio",
        },
        "購物": {
            "亞洲超市": "asian_grocery_store",
            "汽車零件行": "auto_parts_store",
            "腳踏車行": "bicycle_store",
            "書店": "book_store",
            "肉舖": "butcher_shop",
            "手機行": "cell_phone_store",
            "服飾店": "clothing_store",
            "便利商店": "convenience_store",
            "百貨公司": "department_store",
            "折扣商店": "discount_store",
            "電子產品店": "electronics_store",
            "食品雜貨店": "food_store",
            "家具行": "furniture_store",
            "禮品店": "gift_shop",
            "五金行": "hardware_store",
            "家居用品": "home_goods_store",
            "居家裝修": "home_improvement_store",
            "珠寶店": "jewelry_store",
            "酒類專賣": "liquor_store",
            "傳統市場": "market",
            "寵物店": "pet_store",
            "鞋店": "shoe_store",
            "購物中心": "shopping_mall",
            "體育用品店": "sporting_goods_store",
            "商店(其他)": "store",
            "超市": "supermarket",
            "倉儲商店": "warehouse_store",
            "批發商": "wholesaler",
        },
        "交通運輸": {
            "機場": "airport",
            "簡易飛機場": "airstrip",
            "公車站": "bus_station",
            "公車候車亭": "bus_stop",
            "渡輪碼頭": "ferry_terminal",
            "直升機場": "heliport",
            "國際機場": "international_airport",
            "輕軌站": "light_rail_station",
            "停車轉乘": "park_and_ride",
            "地鐵站": "subway_station",
            "計程車招呼站": "taxi_stand",
            "火車站": "train_station",
            "轉運站": "transit_depot",
            "交通站點": "transit_station",
            "卡車停靠站": "truck_stop",
        },
        "餐飲": {
            "餐廳": "restaurant"
        }
    }

    # 使用者選擇類別與地點類型
    main_category = st.selectbox("選擇分類", PLACE_TYPES.keys())
    sub_types = st.multiselect("選擇要查詢的地點類型", list(PLACE_TYPES[main_category].keys()))

    # ------------------------------
    # 工具函式：計算兩點距離（Haversine公式）
    # ------------------------------
    def haversine(lat1, lon1, lat2, lon2):
        R = 6371000
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        d_phi = math.radians(lat2 - lat1)
        d_lambda = math.radians(lon2 - lon1)
        a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return R * c

    # ------------------------------
    # 查詢流程
    # ------------------------------
    if st.button("🔍 查詢"):
        if not google_api_key:
            st.error("請先輸入 Google Maps API Key")
            st.stop()

        if not address:
            st.error("請輸入地址")
            st.stop()

        # 1️⃣ 地址轉經緯度
        geo_url = "https://maps.googleapis.com/maps/api/geocode/json"
        geo_params = {"address": address, "key": google_api_key, "language": "zh-TW"}
        geo_res = requests.get(geo_url, params=geo_params).json()

        if geo_res.get("status") != "OK":
            st.error("無法解析該地址")
            st.stop()

        location = geo_res["results"][0]["geometry"]["location"]
        lat, lng = location["lat"], location["lng"]

        all_places = []

        # 2️⃣ 搜尋周邊地點
        for sub_type in sub_types:
            place_type = PLACE_TYPES[main_category][sub_type]
            places_url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
            places_params = {
                "location": f"{lat},{lng}",
                "radius": radius,
                "type": place_type,
                "key": google_api_key,
                "language": "zh-TW"
            }
            places_res = requests.get(places_url, params=places_params).json()

            for place in places_res.get("results", []):
                name = place.get("name", "未命名")
                p_lat = place["geometry"]["location"]["lat"]
                p_lng = place["geometry"]["location"]["lng"]
                dist = int(haversine(lat, lng, p_lat, p_lng))
                all_places.append((sub_type, name, p_lat, p_lng, dist))

        # 依距離排序
        all_places = sorted(all_places, key=lambda x: x[4])

        # 3️⃣ 顯示結果
        st.subheader("查詢結果（由近到遠）")
        if all_places:
            for t, name, _, _, dist in all_places:
                st.write(f"**{t}** - {name}（{dist} 公尺）")
        else:
            st.warning("⚠️ 該範圍內無相關地點。")

        # 4️⃣ 標記顏色
        icon_map = {
            "餐廳": "http://maps.google.com/mapfiles/ms/icons/orange-dot.png",
            "醫院": "http://maps.google.com/mapfiles/ms/icons/green-dot.png",
            "便利商店": "http://maps.google.com/mapfiles/ms/icons/blue-dot.png",
            "交通站點": "http://maps.google.com/mapfiles/ms/icons/yellow-dot.png"
        }

        markers_js = ""
        for t, name, p_lat, p_lng, dist in all_places:
            icon_url = icon_map.get(t, "http://maps.google.com/mapfiles/ms/icons/blue-dot.png")
            markers_js += f"""
            var marker = new google.maps.Marker({{
                position: {{lat: {p_lat}, lng: {p_lng}}},
                map: map,
                title: "{t}: {name}",
                icon: {{
                    url: "{icon_url}"
                }}
            }});
            var infowindow = new google.maps.InfoWindow({{
                content: "{t}: {name}<br>距離中心 {dist} 公尺"
            }});
            marker.addListener("click", function() {{
                infowindow.open(map, marker);
            }});
            """

        # 5️⃣ 顯示地圖
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
                icon: {{
                    url: "http://maps.google.com/mapfiles/ms/icons/red-dot.png"
                }}
            }});

            {markers_js}
        }}
        </script>
        <script src="https://maps.googleapis.com/maps/api/js?key={google_api_key}&callback=initMap" async defer></script>
        """

        html(map_html, height=500)
