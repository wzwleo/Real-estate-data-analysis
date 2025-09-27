import streamlit as st
import pandas as pd
import requests
import math
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
# Google Places 關鍵字搜尋與地圖顯示
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

def geocode_address(address: str, api_key: str):
    url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {"address": address, "key": api_key, "language": "zh-TW"}
    r = requests.get(url, params=params, timeout=10).json()
    if r.get("status") == "OK" and r["results"]:
        loc = r["results"][0]["geometry"]["location"]
        return loc["lat"], loc["lng"]
    return None, None

def query_google_places_keyword(lat, lng, api_key, selected_categories, radius=500, extra_keyword=""):
    results = []
    # 類別關鍵字搜尋
    for cat in selected_categories:
        for kw in PLACE_TYPES[cat]:
            params = {
                "location": f"{lat},{lng}",
                "radius": radius,
                "keyword": kw,
                "key": api_key,
                "language": "zh-TW"
            }
            res = requests.get("https://maps.googleapis.com/maps/api/place/nearbysearch/json", params=params, timeout=10).json()
            for p in res.get("results", []):
                p_lat = p["geometry"]["location"]["lat"]
                p_lng = p["geometry"]["location"]["lng"]
                dist = int(haversine(lat, lng, p_lat, p_lng))
                if dist <= radius:
                    results.append((cat, kw, p.get("name","未命名"), p_lat, p_lng, dist, p.get("place_id","")))
    # 額外關鍵字搜尋
    if extra_keyword:
        params = {
            "location": f"{lat},{lng}",
            "radius": radius,
            "keyword": extra_keyword,
            "key": api_key,
            "language": "zh-TW"
        }
        res = requests.get("https://maps.googleapis.com/maps/api/place/nearbysearch/json", params=params, timeout=10).json()
        for p in res.get("results", []):
            p_lat = p["geometry"]["location"]["lat"]
            p_lng = p["geometry"]["location"]["lng"]
            dist = int(haversine(lat, lng, p_lat, p_lng))
            if dist <= radius:
                results.append(("關鍵字", extra_keyword, p.get("name","未命名"), p_lat, p_lng, dist, p.get("place_id","")))
    results.sort(key=lambda x: x[5])
    return results

def render_map(lat, lng, places, radius, title="房屋"):
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
            icon: {{ url: "http://maps.google.com/mapfiles/ms/icons/red-dot.png" }}
        }});
        {circle_js}
        {markers_js}
    }}
    </script>
    <script src="https://maps.googleapis.com/maps/api/js?key={st.session_state.get('GOOGLE_MAPS_KEY','')}&callback=initMap" async defer></script>
    """
    html(map_html, height=400)

# ===========================
# 分析頁面
# ===========================
def render_analysis_page():
    st.title("📊 分析頁面")

    if 'favorites' not in st.session_state:
        st.session_state.favorites = set()

    col1, col2, col3, col4 = st.columns([1,1,1,1])
    with col4:
        analysis_scope = st.selectbox(
            "選擇分析範圍",
            ["⭐收藏類別", "已售出房產"],
            key="analysis_scope"
        )

    tab1, tab2, tab3 = st.tabs(["個別分析","房屋比較","市場趨勢分析"])

    # ---------------- 個別分析 ----------------
    with tab1:
        if analysis_scope == "⭐收藏類別":
            fav_df = get_favorites_data()
            if fav_df.empty and st.session_state.favorites:
                st.warning("⚠️ 找不到收藏房產的詳細資料，請先在搜尋頁面載入房產資料")
            elif not st.session_state.favorites:
                st.info("⭐ 你尚未收藏任何房產")
            else:
                render_favorites_list(fav_df)
        else:
            st.info("🚧 已售出房產分析功能開發中...")

    # ---------------- 房屋比較 ----------------
    with tab2:
        st.subheader("🏠 房屋比較（Google Places + Gemini 分析）")
        fav_df = get_favorites_data()
        if fav_df.empty:
            st.info("⭐ 尚未有收藏房產，無法比較")
        else:
            options = fav_df['標題'] + " | " + fav_df['地址']
            col1, col2 = st.columns(2)
            with col1:
                choice_a = st.selectbox("選擇房屋 A", options, key="compare_a")
            with col2:
                choice_b = st.selectbox("選擇房屋 B", options, key="compare_b")

            google_key = st.session_state.get("GOOGLE_MAPS_KEY","")
            gemini_key = st.session_state.get("GEMINI_KEY","")

            radius = st.slider("搜尋半徑 (公尺)", 100, 500, 400, step=50)
            keyword = st.text_input("額外關鍵字搜尋 (可選)", key="extra_keyword")

            st.subheader("選擇要比較的生活機能類別")
            selected_categories = []
            cols = st.columns(len(PLACE_TYPES))
            for i, cat in enumerate(PLACE_TYPES.keys()):
                with cols[i]:
                    if st.checkbox(cat, value=True, key=f"comp_cat_{cat}"):
                        selected_categories.append(cat)

            if st.button("開始比較"):
                if not google_key or not gemini_key:
                    st.error("❌ 請先在側邊欄輸入 API Key")
                    st.stop()
                if choice_a == choice_b:
                    st.warning("⚠️ 請選擇兩個不同房屋")
                    st.stop()

                house_a = fav_df[options==choice_a].iloc[0]
                house_b = fav_df[options==choice_b].iloc[0]
                lat_a, lng_a = geocode_address(house_a["地址"], google_key)
                lat_b, lng_b = geocode_address(house_b["地址"], google_key)
                if not lat_a or not lat_b:
                    st.error("❌ 無法解析地址")
                    st.stop()

                places_a = query_google_places_keyword(lat_a, lng_a, google_key, selected_categories, radius, extra_keyword=keyword)
                places_b = query_google_places_keyword(lat_b, lng_b, google_key, selected_categories, radius, extra_keyword=keyword)

                col_map1, col_map2 = st.columns(2)
                with col_map1:
                    render_map(lat_a, lng_a, places_a, radius, title="房屋 A")
                with col_map2:
                    render_map(lat_b, lng_b, places_b, radius, title="房屋 B")

                # Gemini 分析
                genai.configure(api_key=gemini_key)
                model = genai.GenerativeModel("gemini-2.0-flash")
                prompt = f"""你是一位房地產分析專家，請比較以下兩間房屋的生活機能，
                並列出優缺點與結論：
                房屋 A：
                {places_a}
                房屋 B：
                {places_b}
                """
                response = model.generate_content(prompt)
                st.subheader("📊 Gemini 分析結果")
                st.write(response.text)

    # ---------------- 市場趨勢 ----------------
    with tab3:
        st.subheader("📈 市場趨勢分析")
        st.info("🚧 市場趨勢分析功能開發中...")

# ===========================
# 側邊欄與狀態同步
# ===========================
def ensure_data_sync():
    if ('filtered_df' in st.session_state and 
        not st.session_state.filtered_df.empty and
        'all_properties_df' not in st.session_state):
        st.session_state.all_properties_df = st.session_state.filtered_df.copy()
    if 'favorites' not in st.session_state:
        st.session_state.favorites = set()

def render_sidebar():
    st.sidebar.title("📑 導航")
    page = st.sidebar.radio(
        "選擇頁面",
        ["🏠 首頁", "🔍 搜尋頁面", "📊 分析頁面"],
        key="nav_radio"
    )

    if page == "🏠 首頁":
        st.session_state.current_page = 'home'
    elif page == "🔍 搜尋頁面":
        st.session_state.current_page = 'search'
    elif page == "📊 分析頁面":
        st.session_state.current_page = 'analysis'

    st.sidebar.title("⚙️ 設置")
    st.session_state["GEMINI_KEY"] = st.sidebar.text_input(
        "Gemini API Key",
        type="password",
        value=st.session_state.get("GEMINI_KEY", "")
    )
    st.session_state["GOOGLE_MAPS_KEY"] = st.sidebar.text_input(
        "Google Maps API Key",
        type="password",
        value=st.session_state.get("GOOGLE_MAPS_KEY", "")
    )

# ===========================
# 主程式
# ===========================
def main():
    st.set_page_config(page_title="房產分析系統", layout="wide")
    if "current_page" not in st.session_state:
        st.session_state.current_page = "home"

    render_sidebar()
    ensure_data_sync()

    if st.session_state.current_page == "home":
        st.title("🏠 首頁")
        st.write("歡迎使用房產分析系統")
    elif st.session_state.current_page == "search":
        st.title("🔍 搜尋頁面")
        st.info("🚧 搜尋功能開發中...")
    elif st.session_state.current_page == "analysis
