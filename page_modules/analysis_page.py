import streamlit as st
import pandas as pd
import requests
import math
import folium
from streamlit.components.v1 import html
import google.generativeai as genai

# ===========================
# 收藏與分析功能
# ===========================
def get_favorites_data():
    """
    取得收藏房產的資料
    """
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
    """
    渲染收藏清單
    """
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
# Google Places 功能
# ===========================
PLACE_TYPES = {
    "交通": ["bus_stop", "subway_station", "train_station"],
    "超商": ["convenience_store"],
    "餐廳": ["restaurant", "cafe"],
    "學校": ["school", "university", "primary_school", "secondary_school"],
    "醫院": ["hospital"],
    "藥局": ["pharmacy"],
}

def geocode_address(address: str, api_key: str):
    url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {"address": address, "key": api_key, "language": "zh-TW"}
    r = requests.get(url, params=params, timeout=10).json()
    if r.get("status") == "OK" and r["results"]:
        loc = r["results"][0]["geometry"]["location"]
        return loc["lat"], loc["lng"]
    return None, None

def haversine(lat1, lon1, lat2, lon2):
    R = 6371000
    dlat, dlon = math.radians(lat2-lat1), math.radians(lon2-lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1))*math.cos(math.radians(lat2))*math.sin(dlon/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

def query_google_places(lat, lng, api_key, selected_categories, radius=500):
    results = {k: [] for k in selected_categories}
    for label in selected_categories:
        for t in PLACE_TYPES[label]:
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
    lines = [f"房屋（{address}）："]
    for k, v in info_dict.items():
        lines.append(f"- {k}: {len(v)} 個")
    return "\n".join(lines)

def add_markers(m, info_dict, color):
    for category, places in info_dict.items():
        for name, lat, lng, dist in places:
            folium.Marker(
                [lat, lng],
                popup=f"{category}：{name}（{dist} 公尺）",
                icon=folium.Icon(color=color, icon="info-sign"),
            ).add_to(m)


# ===========================
# 分析頁面
# ===========================
def render_analysis_page():
    st.title("📊 分析頁面")

    if 'favorites' not in st.session_state:
        st.session_state.favorites = set()

    col1, col2, col3, col4 = st.columns([1, 1, 1, 1])
    with col4:
        analysis_scope = st.selectbox(
            "選擇分析範圍",
            ["⭐收藏類別", "已售出房產"],
            key="analysis_scope"
        )

    tab1, tab2, tab3 = st.tabs(["個別分析", "房屋比較", "市場趨勢分析"])

    # ---------------- 個別分析 ----------------
    with tab1:
        if analysis_scope == "⭐收藏類別":
            fav_df = get_favorites_data()
            if fav_df.empty and st.session_state.favorites:
                st.warning("⚠️ 找不到收藏房產的詳細資料，請先在搜尋頁面載入房產資料")
                st.info("💡 請先到搜尋頁面進行搜尋，載入房產資料後再回到分析頁面")
            elif not st.session_state.favorites:
                st.info("⭐ 你尚未收藏任何房產")
            else:
                render_favorites_list(fav_df)
        elif analysis_scope == "已售出房產":
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

            google_key = st.session_state.get("GOOGLE_MAPS_KEY", "")
            gemini_key = st.session_state.get("GEMINI_KEY", "")

            if choice_a and choice_b and choice_a != choice_b:
                house_a = fav_df.iloc[options[options == choice_a].index[0]]
                house_b = fav_df.iloc[options[options == choice_b].index[0]]

                addr_a, addr_b = house_a["地址"], house_b["地址"]

                radius = st.slider("搜尋半徑 (公尺)", min_value=100, max_value=2000, value=500, step=50)

                st.subheader("選擇要比較的生活機能類別")
                selected_categories = []
                cols = st.columns(3)
                for idx, cat in enumerate(PLACE_TYPES.keys()):
                    if cols[idx % 3].checkbox(cat, value=True):
                        selected_categories.append(cat)

                if st.button("開始比較"):
                    if not google_key or not gemini_key:
                        st.error("❌ 請先在側邊欄輸入 API Key")
                        st.stop()

                    lat_a, lng_a = geocode_address(addr_a, google_key)
                    lat_b, lng_b = geocode_address(addr_b, google_key)
                    if not lat_a or not lat_b:
                        st.error("❌ 無法解析其中一個地址")
                        st.stop()

                    info_a = query_google_places(lat_a, lng_a, google_key, selected_categories, radius)
                    info_b = query_google_places(lat_b, lng_b, google_key, selected_categories, radius)

                    text_a = format_info(addr_a, info_a)
                    text_b = format_info(addr_b, info_b)

                    # 地圖
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

                    # Gemini 分析
                    genai.configure(api_key=gemini_key)
                    model = genai.GenerativeModel("gemini-2.0-flash")
                    prompt = f"""你是一位房地產分析專家，請比較以下兩間房屋的生活機能，
                    並列出優缺點與結論：
                    {text_a}
                    {text_b}
                    """
                    response = model.generate_content(prompt)

                    st.subheader("📊 Gemini 分析結果")
                    st.write(response.text)

            else:
                st.warning("⚠️ 請選擇兩個不同的房屋進行比較")

    # ---------------- 市場趨勢 ----------------
    with tab3:
        st.subheader("📈 市場趨勢分析")
        st.info("🚧 市場趨勢分析功能開發中...")


# ===========================
# 狀態同步
# ===========================
def ensure_data_sync():
    if ('filtered_df' in st.session_state and 
        not st.session_state.filtered_df.empty and
        'all_properties_df' not in st.session_state):
        st.session_state.all_properties_df = st.session_state.filtered_df.copy()
    if 'favorites' not in st.session_state:
        st.session_state.favorites = set()


# ===========================
# 側邊欄
# ===========================
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

    elif st.session_state.current_page == "analysis":
        render_analysis_page()


if __name__ == "__main__":
    main()
