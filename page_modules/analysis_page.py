import os
import math
import json
import requests
import streamlit as st
import time
from string import Template
from streamlit.components.v1 import html
from components.solo_analysis import tab1_module
import google.generativeai as genai
import pandas as pd
from streamlit_echarts import st_echarts

# ===========================
# 收藏與分析功能
# ===========================
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
    fav_df = all_df[all_df['編號'].astype(str).isin(map(str, fav_ids))].copy()
    return fav_df


# ===========================
# 關鍵字設定
# ===========================
PLACE_KEYWORDS = {
    "教育": ["學校", "圖書館", "大學"],
    "健康與保健": ["藥局", "醫院", "牙醫診所", "診所"],
    "購物": ["超市", "購物中心", "便利商店"],
    "交通運輸": ["公車站", "捷運站", "火車站"],
    "餐飲": ["餐廳", "咖啡廳"]
}

CATEGORY_COLORS = {
    "教育": "#1E90FF",
    "健康與保健": "#32CD32",
    "購物": "#FF8C00",
    "交通運輸": "#800080",
    "餐飲": "#FF0000",
    "關鍵字": "#000000"
}


# ===========================
# 工具函式
# ===========================
def haversine(lat1, lon1, lat2, lon2):
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(d_phi/2)**2 +
        math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda/2)**2
    )
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _get_server_key():
    return st.session_state.get("GMAPS_SERVER_KEY") or st.session_state.get("GOOGLE_MAPS_KEY", "")


def _get_browser_key():
    return st.session_state.get("GMAPS_BROWSER_KEY") or st.session_state.get("GOOGLE_MAPS_KEY", "")


def geocode_address(address: str, api_key: str):
    url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {"address": address, "key": api_key, "language": "zh-TW"}

    try:
        r = requests.get(url, params=params, timeout=10).json()
    except Exception as e:
        st.error(f"地址解析失敗: {e}")
        return None, None

    status = r.get("status")
    if status == "OK" and r.get("results"):
        loc = r["results"][0]["geometry"]["location"]
        return loc["lat"], loc["lng"]

    st.warning(f"Geocoding error: {status}")
    return None, None


# ===========================
# Google Text Search
# ===========================
def search_text_google_places(lat, lng, api_key, keyword, radius=500):
    url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
    params = {
        "query": keyword,
        "location": f"{lat},{lng}",
        "radius": radius,
        "key": api_key,
        "language": "zh-TW"
    }

    try:
        r = requests.get(url, params=params, timeout=10).json()
    except Exception as e:
        st.warning(f"❌ 關鍵字 {keyword} 查詢失敗: {e}")
        return []

    results = []
    for p in r.get("results", []):
        loc = p["geometry"]["location"]
        dist = int(haversine(lat, lng, loc["lat"], loc["lng"]))
        results.append((
            "關鍵字",
            keyword,
            p.get("name", "未命名"),
            loc["lat"],
            loc["lng"],
            dist,
            p.get("place_id", "")
        ))
    return results
def load_population_csv(folder="./page_modules"):
    path = os.path.join(folder, "PEOPLE.csv")
    if not os.path.exists(path):
        return pd.DataFrame()

    try:
        df = pd.read_csv(path, encoding="utf-8")
    except:
        df = pd.read_csv(path, encoding="big5")

    return df



def query_google_places_keyword(lat, lng, api_key, selected_categories, radius=500, extra_keyword=""):
    results, seen = [], set()
    total_tasks = sum(len(PLACE_KEYWORDS[cat]) for cat in selected_categories) + (1 if extra_keyword else 0)

    progress = st.progress(0)
    progress_text = st.empty()
    completed = 0

    def update_progress(task_desc):
        nonlocal completed
        completed += 1
        progress.progress(min(completed / total_tasks, 1.0))
        progress_text.text(f"進度：{completed}/{total_tasks} - {task_desc}")

    for cat in selected_categories:
        for kw in PLACE_KEYWORDS[cat]:
            update_progress(f"查詢 {cat}-{kw}")
            for p in search_text_google_places(lat, lng, api_key, kw, radius):
                if p[5] > radius:
                    continue
                pid = p[6]
                if pid in seen:
                    continue
                seen.add(pid)
                results.append((cat, kw, p[2], p[3], p[4], p[5], pid))

            time.sleep(1)

    if extra_keyword:
        update_progress(f"額外關鍵字: {extra_keyword}")
        for p in search_text_google_places(lat, lng, api_key, extra_keyword, radius):
            if p[5] > radius:
                continue
            pid = p[6]
            if pid in seen:
                continue
            seen.add(pid)
            results.append(("關鍵字", extra_keyword, p[2], p[3], p[4], p[5], pid))

        time.sleep(0.3)

    progress.progress(1.0)
    progress_text.text("✅ 查詢完成！")

    results.sort(key=lambda x: x[5])
    return results


def check_places_found(places, selected_categories, extra_keyword):
    found_dict = {
        cat: {kw: False for kw in PLACE_KEYWORDS[cat]}
        for cat in selected_categories
    }
    extra_found = False

    for cat, kw, name, lat, lng, dist, pid in places:
        if cat in found_dict and kw in found_dict[cat]:
            found_dict[cat][kw] = True
        if extra_keyword and cat == "關鍵字" and kw == extra_keyword:
            extra_found = True

    messages = []
    for cat, kws in found_dict.items():
        for kw, found in kws.items():
            if not found:
                messages.append(f"⚠️ 周圍沒有 {cat} → {kw}")

    if extra_keyword and not extra_found:
        messages.append(f"⚠️ 周圍沒有關鍵字「{extra_keyword}」的設施")

    return messages


def render_map(lat, lng, places, radius, title="房屋"):
    browser_key = _get_browser_key()

    data = []
    for cat, kw, name, p_lat, p_lng, dist, pid in places:
        data.append({
            "cat": cat,
            "kw": kw,
            "name": name,
            "lat": p_lat,
            "lng": p_lng,
            "dist": dist,
            "pid": pid,
            "color": CATEGORY_COLORS.get(cat, "#000000")
        })

    data_json = json.dumps(data, ensure_ascii=False)

    tpl = Template("""
        <div id="map" style="height:400px;"></div>
        <script>
        function initMap() {
            var center = {lat: $LAT, lng: $LNG};
            var map = new google.maps.Map(document.getElementById('map'), {
                zoom: 16,
                center: center
            });
            new google.maps.Marker({position: center, map: map, title: "$TITLE"});

            var data = $DATA_JSON;
            data.forEach(function(p){
                var info = p.cat + "-" + p.kw + ": " + p.name +
                           "<br>距離中心 " + p.dist + " 公尺";

                var marker = new google.maps.Marker({
                    position: {lat: p.lat, lng: p.lng},
                    map: map,
                    icon: {
                        path: google.maps.SymbolPath.CIRCLE,
                        scale: 6,
                        fillColor: p.color,
                        fillOpacity: 1,
                        strokeWeight: 1
                    },
                    title: p.cat + "-" + p.name
                });

                marker.addListener("click", function(){
                    new google.maps.InfoWindow({content: info}).open(map, marker);
                });
            });

            new google.maps.Circle({
                strokeColor:"#FF0000",
                strokeOpacity:0.8,
                strokeWeight:2,
                fillColor:"#FF0000",
                fillOpacity:0.1,
                map: map,
                center: center,
                radius: $RADIUS
            });
        }
        </script>
        <script src="https://maps.googleapis.com/maps/api/js?key=$BROWSER_KEY&callback=initMap" async defer></script>
    """)

    map_html = tpl.substitute(
        LAT=lat,
        LNG=lng,
        TITLE=title,
        DATA_JSON=data_json,
        RADIUS=radius,
        BROWSER_KEY=browser_key
    )
    html(map_html, height=400)


def format_places(places):
    return "\n".join([
        f"{cat}-{kw}: {name} ({dist} m)"
        for cat, kw, name, lat, lng, dist, pid in places
    ])


# ===========================
# CSV 載入函式
# ===========================
def load_real_estate_csv(folder="./page_modules"):
    file_names = [
        f for f in os.listdir(folder)
        if f.startswith("合併後不動產統計_") and f.endswith(".csv")
    ]

    dfs = []
    for file in file_names:
        path = os.path.join(folder, file)
        try:
            df = pd.read_csv(path, encoding="utf-8")
        except:
            try:
                df = pd.read_csv(path, encoding="big5")
            except Exception as e:
                st.warning(f"讀取失敗：{file} - {e}")
                continue

        dfs.append(df)

    if dfs:
        return pd.concat(dfs, ignore_index=True)

    return pd.DataFrame()


# ===========================
# 分析頁面主程式
# ===========================
def render_analysis_page():
    st.title("📊 分析頁面")

    # 初始化收藏清單
    if 'favorites' not in st.session_state:
        st.session_state.favorites = set()

    # 初始化篩選條件
    if 'selected_city' not in st.session_state:
        st.session_state.selected_city = None
    if 'selected_district' not in st.session_state:
        st.session_state.selected_district = None
    if 'show_filtered_data' not in st.session_state:
        st.session_state.show_filtered_data = False

    # Tab 分頁
    tab1, tab2, tab3 = st.tabs(["個別分析", "房屋比較", "市場趨勢分析"])

    # ============================
    # Tab1: 個別分析
    # ============================
    with tab1:
        _ = get_favorites_data()
        tab1_module()  # 你的個別分析模組

    # ============================
    # Tab2: 房屋比較
    # ============================
    with tab2:
        st.subheader("🏠 房屋比較（Google Places + Gemini 分析）")

        fav_df = get_favorites_data()
        if fav_df.empty:
            st.info("⭐ 尚未有收藏房產，無法比較")
        else:
            options = fav_df['標題'] + " | " + fav_df['地址']
            c1, c2 = st.columns(2)
            with c1:
                choice_a = st.selectbox("選擇房屋 A", options, key="compare_a")
            with c2:
                choice_b = st.selectbox("選擇房屋 B", options, key="compare_b")

            server_key = _get_server_key()
            gemini_key = st.session_state.get("GEMINI_KEY", "")
            radius = 500
            keyword = st.text_input("額外關鍵字搜尋 (可選)", key="extra_keyword")

            st.subheader("選擇要比較的生活機能類別")
            selected_categories = []
            cols = st.columns(len(PLACE_KEYWORDS))
            for i, cat in enumerate(PLACE_KEYWORDS.keys()):
                with cols[i]:
                    if st.checkbox(cat, value=True, key=f"comp_cat_{cat}"):
                        selected_categories.append(cat)

            if st.button("開始比較"):
                if not _get_browser_key():
                    st.error("❌ 請在側邊欄填入 Google Maps **Browser Key**")
                    st.stop()
                if not server_key or not gemini_key:
                    st.error("❌ 請在側邊欄填入 Server Key 與 Gemini Key")
                    st.stop()
                if choice_a == choice_b:
                    st.warning("⚠️ 請選擇兩個不同房屋")
                    st.stop()

                house_a = fav_df[(fav_df['標題'] + " | " + fav_df['地址']) == choice_a].iloc[0]
                house_b = fav_df[(fav_df['標題'] + " | " + fav_df['地址']) == choice_b].iloc[0]

                lat_a, lng_a = geocode_address(house_a["地址"], server_key)
                lat_b, lng_b = geocode_address(house_b["地址"], server_key)

                if lat_a is None or lat_b is None:
                    st.error("❌ 地址解析失敗，請檢查 Server Key 限制。")
                    return

                # 查詢房屋周邊
                with st.spinner("正在查詢房屋 A 周邊..."):
                    places_a = query_google_places_keyword(
                        lat_a, lng_a, server_key, selected_categories,
                        radius, extra_keyword=keyword
                    )
                    messages_a = check_places_found(places_a, selected_categories, keyword)
                    for msg in messages_a:
                        st.warning(f"房屋 A: {msg}")
                    time.sleep(1)

                with st.spinner("正在查詢房屋 B 周邊..."):
                    places_b = query_google_places_keyword(
                        lat_b, lng_b, server_key, selected_categories,
                        radius, extra_keyword=keyword
                    )
                    messages_b = check_places_found(places_b, selected_categories, keyword)
                    for msg in messages_b:
                        st.warning(f"房屋 B: {msg}")

                # 顯示地圖
                col1, col2 = st.columns(2)
                with col1:
                    render_map(lat_a, lng_a, places_a, radius, title="房屋 A")
                with col2:
                    render_map(lat_b, lng_b, places_b, radius, title="房屋 B")

                # Gemini 分析
                genai.configure(api_key=gemini_key)
                model = genai.GenerativeModel("gemini-2.0-flash")

                places_a_text = format_places(places_a) if places_a else "無周邊資料"
                places_b_text = format_places(places_b) if places_b else "無周邊資料"

                prompt = f"""你是一位房地產分析專家，請比較以下兩間房屋的生活機能：

房屋 A:
{places_a_text}

房屋 B:
{places_b_text}

請列出每間房屋的優缺點，並給出綜合結論。
"""

                st.text_area("Gemini Prompt", prompt, height=300)
                resp = model.generate_content(prompt)
                st.subheader("📊 Gemini 分析結果")
                st.write(resp.text)

    
        # ============================
        # Tab3: 市場趨勢分析（分房市與人口篩選器）
        # ============================
        with tab3:
            st.subheader("📊 市場趨勢分析")
        
            # 載入房產資料
            combined_df = load_real_estate_csv(folder="./page_modules")
            if combined_df.empty:
                st.info("📂 無可用不動產資料")
        
            # 載入人口資料
            population_df = load_population_csv(folder="./page_modules")
            if population_df.empty:
                st.info("📂 找不到 PEOPLE.csv 或檔案為空")
            else:
                st.caption("資料來源：內政部歷年人口統計（年底人口數）")
                population_df.columns = [str(c).strip().replace("　", "") for c in population_df.columns]
                population_df["縣市"] = population_df["縣市"].astype(str).str.strip()
                population_df["行政區"] = population_df["行政區"].astype(str).str.strip()
                pop_cols = [c for c in population_df.columns if c not in ["縣市", "行政區"]]
                pop_long = population_df.melt(
                    id_vars=["縣市", "行政區"],
                    value_vars=pop_cols,
                    var_name="年度季度",
                    value_name="人口數"
                )
                pop_long["人口數"] = pd.to_numeric(
                    pop_long["人口數"].astype(str).str.replace(",", "").str.strip(),
                    errors="coerce"
                ).fillna(0).astype(int)
        
            # ============================
            # 1️⃣ 房市資料篩選器（影響四個圖表和房產表）
            # ============================
            st.markdown("### 🏠 房市篩選器")
            col1, col2 = st.columns([3, 1])
            with col2:
                cities_real = ["全台"] + sorted(combined_df["縣市"].dropna().unique())
                city_choice_real = st.selectbox("選擇縣市（房市分析）", cities_real, key="tab3_city_real")
                if city_choice_real != "全台":
                    district_names_real = ["全部"] + sorted(
                        combined_df[combined_df["縣市"] == city_choice_real]["行政區"].dropna().unique()
                    )
                    district_choice_real = st.selectbox("選擇行政區（房市分析）", district_names_real, key="tab3_district_real")
                else:
                    district_choice_real = "全部"
        
            filtered_real_estate = combined_df.copy()
            if city_choice_real != "全台":
                filtered_real_estate = filtered_real_estate[filtered_real_estate["縣市"] == city_choice_real]
            if district_choice_real != "全部":
                filtered_real_estate = filtered_real_estate[filtered_real_estate["行政區"] == district_choice_real]
        
            with col1:
                st.markdown("## 📂 房市篩選結果資料")
                st.write(f"共 {len(filtered_real_estate)} 筆房產資料")
                st.dataframe(filtered_real_estate, use_container_width=True)
        
            # ============================
            # 2️⃣ 人口資料篩選器（只影響人口統計表）
            # ============================
            st.markdown("### 👥 人口篩選器")
            col3, col4 = st.columns([3, 1])
            with col4:
                cities_pop = ["全台"] + sorted(pop_long["縣市"].dropna().unique())
                city_choice_pop = st.selectbox("選擇縣市（人口統計）", cities_pop, key="tab3_city_pop")
                if city_choice_pop != "全台":
                    district_names_pop = ["全部"] + sorted(
                        pop_long[pop_long["縣市"] == city_choice_pop]["行政區"].dropna().unique()
                    )
                    district_choice_pop = st.selectbox("選擇行政區（人口統計）", district_names_pop, key="tab3_district_pop")
                else:
                    district_choice_pop = "全部"
        
            filtered_population = pop_long.copy()
            if city_choice_pop != "全台":
                filtered_population = filtered_population[filtered_population["縣市"] == city_choice_pop]
            if district_choice_pop != "全部":
                filtered_population = filtered_population[filtered_population["行政區"] == district_choice_pop]
        
            st.markdown("## 👥 人口統計表")
            if not filtered_population.empty:
                pop_table = filtered_population.pivot_table(
                    index=["縣市", "行政區"],
                    columns="年度季度",
                    values="人口數"
                ).fillna(0).astype(int)
                st.dataframe(pop_table, use_container_width=True)
            else:
                st.info("⚠️ 無人口資料可顯示")
        
            # ============================
            # 選擇圖表類型（房市分析用）
            # ============================
            chart_type = st.selectbox(
                "選擇圖表類型",
                [
                    "不動產價格趨勢分析",
                    "交易筆數分布",
                    "人口 × 成交量（市場是否被壓抑）",
                    "人口 × 房價（潛力 / 風險）"
                ],
                key="tab3_chart_type"
            )
        
            # 安全函數避免 int(nan) 報錯
            def safe_mean(series):
                if series.empty: return 0
                val = series.mean()
                return int(val) if not pd.isna(val) else 0
        
            # -----------------------------
            # 1️⃣ 不動產價格趨勢分析
            # -----------------------------
            if chart_type == "不動產價格趨勢分析" and not filtered_real_estate.empty:
                filtered_real_estate["年份"] = filtered_real_estate["季度"].str[:3].astype(int) + 1911
                yearly_avg = filtered_real_estate.groupby(["年份", "BUILD"])["平均單價元平方公尺"].mean().reset_index()
                years = sorted(yearly_avg["年份"].unique())
                year_labels = [str(y) for y in years]
        
                new_data = [
                    safe_mean(yearly_avg[(yearly_avg["年份"] == y) & (yearly_avg["BUILD"] == "新成屋")]["平均單價元平方公尺"])
                    for y in years
                ]
                old_data = [
                    safe_mean(yearly_avg[(yearly_avg["年份"] == y) & (yearly_avg["BUILD"] == "中古屋")]["平均單價元平方公尺"])
                    for y in years
                ]
        
                option = {
                    "tooltip": {"trigger": "axis"},
                    "legend": {"data": ["新成屋", "中古屋"]},
                    "xAxis": {"type": "category", "data": year_labels},
                    "yAxis": {"type": "value"},
                    "series": [
                        {"name": "新成屋", "type": "line", "data": new_data},
                        {"name": "中古屋", "type": "line", "data": old_data},
                    ],
                }
                st_echarts(option, height="400px")
        
            # -----------------------------
            # 2️⃣ 交易筆數分布
            # -----------------------------
            elif chart_type == "交易筆數分布":
                if city_choice_real == "全台":
                    trans_counts = filtered_real_estate.groupby("縣市")["交易筆數"].sum().reset_index()
                    pie_data = [{"value": int(row["交易筆數"]), "name": row["縣市"]} for _, row in trans_counts.iterrows()]
                else:
                    df_city = filtered_real_estate
                    trans_counts = df_city.groupby("行政區")["交易筆數"].sum().reset_index()
                    pie_data = [{"value": int(row["交易筆數"]), "name": row["行政區"]} for _, row in trans_counts.iterrows()]
        
                if pie_data:
                    option = {
                        "tooltip": {"trigger": "item", "formatter": "{b}: {c} ({d}%)"},
                        "legend": {"orient": "vertical", "left": "left", "data": [d["name"] for d in pie_data]},
                        "series": [
                            {
                                "name": "交易筆數",
                                "type": "pie",
                                "radius": "50%",
                                "data": pie_data,
                                "emphasis": {
                                    "itemStyle": {
                                        "shadowBlur": 10,
                                        "shadowOffsetX": 0,
                                        "shadowColor": "rgba(0, 0, 0, 0.5)"
                                    }
                                }
                            }
                        ]
                    }
                    st_echarts(option, height="400px")
                else:
                    st.info("⚠️ 無交易資料，無法顯示圓餅圖")
        
            # -----------------------------
            # 3️⃣ 人口 × 成交量
            # -----------------------------
            elif chart_type == "人口 × 成交量（市場是否被壓抑）":
                if filtered_population.empty or filtered_real_estate.empty:
                    st.info("人口或交易資料不足，無法分析")
                else:
                    filtered_real_estate["年份"] = filtered_real_estate["季度"].str[:3].astype(int) + 1911
                    trans_grouped = filtered_real_estate.groupby(["縣市", "行政區", "年份"])["交易筆數"].sum().reset_index()
                    pop_grouped = filtered_population.copy()
                    pop_grouped["年份"] = pop_grouped["年度季度"].str[:3].astype(int) + 1911
                    pop_grouped = pop_grouped.groupby(["縣市", "行政區", "年份"])["人口數"].sum().reset_index()
        
                    merged = pd.merge(
                        pop_grouped,
                        trans_grouped,
                        on=["縣市", "行政區", "年份"],
                        how="left"
                    ).fillna(0).sort_values("年份")
        
                    option = {
                        "tooltip": {"trigger": "axis"},
                        "legend": {"data": ["人口數", "成交量"]},
                        "xAxis": {"type": "category", "data": merged["年份"].astype(int).astype(str).tolist()},
                        "yAxis": [
                            {"type": "value", "name": "人口數"},
                            {"type": "value", "name": "成交量"}
                        ],
                        "series": [
                            {"name": "人口數", "type": "line", "data": merged["人口數"].astype(int).tolist(), "smooth": True},
                            {"name": "成交量", "type": "line", "yAxisIndex": 1, "data": merged["交易筆數"].astype(int).tolist()}
                        ]
                    }
                    st_echarts(option, height="400px")
        
            # -----------------------------
            # 4️⃣ 人口 × 房價
            # -----------------------------
            elif chart_type == "人口 × 房價（潛力 / 風險）":
                if filtered_population.empty or filtered_real_estate.empty:
                    st.info("人口或房價資料不足，無法分析")
                else:
                    pop_latest = filtered_population.groupby(["縣市", "行政區"])["人口數"].sum().reset_index()
                    price_df = filtered_real_estate.groupby(["縣市", "行政區"])["平均單價元平方公尺"].mean().reset_index()
                    merged = pd.merge(pop_latest, price_df, on=["縣市", "行政區"], how="inner")
        
                    option = {
                        "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}},
                        "xAxis": {"type": "value", "name": "人口數"},
                        "yAxis": {"type": "value", "name": "平均房價"},
                        "series": [
                            {"name": "人口 × 房價", "type": "scatter", "data": merged[["人口數", "平均單價元平方公尺"]].values.tolist()}
                        ]
                    }
                    st_echarts(option, height="400px")
















            




