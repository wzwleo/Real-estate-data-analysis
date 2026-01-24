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
# 關鍵字設定 - 更新版（增加健康保健和餐飲）
# ===========================
PLACE_TYPES = {
    "教育": [
        "圖書館", "library",
        "學前教育", "preschool",
        "小學", "primary_school", "school",
        "中學", "secondary_school",
        "大學", "university",
    ],
    "購物": [
        "亞洲超市", "asian_grocery_store",
        "汽車零件", "auto_parts_store",
        "自行車店", "bicycle_store",
        "書店", "book_store",
        "肉舖", "butcher_shop",
        "手機店", "cell_phone_store",
        "服飾店", "clothing_store",
        "便利商店", "convenience_store",
        "百貨公司", "department_store",
        "折扣商店", "discount_store",
        "電子用品店", "electronics_store",
        "食品店", "food_store",
        "家具店", "furniture_store",
        "禮品店", "gift_shop",
        "雜貨店", "grocery_store",
        "五金行", "hardware_store",
        "家居用品", "home_goods_store",
        "家居裝修", "home_improvement_store",
        "珠寶店", "jewelry_store",
        "酒類商店", "liquor_store",
        "市場", "market",
        "寵物店", "pet_store",
        "鞋店", "shoe_store",
        "購物中心", "shopping_mall",
        "運動用品店", "sporting_goods_store",
        "商店", "store",
        "超市", "supermarket",
        "倉庫商店", "warehouse_store",
        "批發商", "wholesaler",
    ],
    "交通運輸": [
        "機場", "airport",
        "小型機場", "airstrip",
        "公車站", "bus_station",
        "公車站牌", "bus_stop",
        "渡輪碼頭", "ferry_terminal",
        "直升機場", "heliport",
        "國際機場", "international_airport",
        "輕軌站", "light_rail_station",
        "停車轉乘", "park_and_ride",
        "地鐵站", "subway_station",
        "計程車招呼站", "taxi_stand",
        "火車站", "train_station",
        "運輸車站", "transit_depot",
        "轉運站", "transit_station",
        "卡車休息站", "truck_stop",
    ],
    "健康與保健": [
        "脊椎治療師", "chiropractor",
        "牙醫診所", "dental_clinic",
        "牙醫", "dentist",
        "醫生", "doctor",
        "藥店", "drugstore",
        "醫院", "hospital",
        "按摩", "massage",
        "藥局", "pharmacy",
        "物理治療師", "physiotherapist",
        "桑拿", "sauna",
        "皮膚護理診所", "skin_care_clinic",
        "水療中心", "spa",
        "日光浴工作室", "tanning_studio",
        "健康中心", "wellness_center",
        "瑜珈工作室", "yoga_studio",
        "醫療實驗室", "medical_lab",
    ],
    "餐飲美食": [
        "巴西莓店", "acai_shop",
        "阿富汗餐廳", "afghani_restaurant",
        "非洲餐廳", "african_restaurant",
        "美式餐廳", "american_restaurant",
        "亞洲餐廳", "asian_restaurant",
        "貝果店", "bagel_shop",
        "麵包店", "bakery",
        "酒吧", "bar",
        "酒吧與燒烤", "bar_and_grill",
        "燒烤餐廳", "barbecue_restaurant",
        "巴西餐廳", "brazilian_restaurant",
        "早餐店", "breakfast_restaurant",
        "早午餐餐廳", "brunch_restaurant",
        "自助餐", "buffet_restaurant",
        "咖啡廳", "cafe",
        "自助餐廳", "cafeteria",
        "糖果店", "candy_store",
        "貓咪咖啡廳", "cat_cafe",
        "中餐廳", "chinese_restaurant",
        "巧克力工廠", "chocolate_factory",
        "巧克力店", "chocolate_shop",
        "咖啡店", "coffee_shop",
        "甜點店", "confectionery",
        "熟食店", "deli",
        "甜點餐廳", "dessert_restaurant",
        "甜點店", "dessert_shop",
        "小餐館", "diner",
        "狗狗咖啡廳", "dog_cafe",
        "甜甜圈店", "donut_shop",
        "速食餐廳", "fast_food_restaurant",
        "高級餐廳", "fine_dining_restaurant",
        "美食街", "food_court",
        "法式餐廳", "french_restaurant",
        "希臘餐廳", "greek_restaurant",
        "漢堡餐廳", "hamburger_restaurant",
        "冰淇淋店", "ice_cream_shop",
        "印度餐廳", "indian_restaurant",
        "印尼餐廳", "indonesian_restaurant",
        "義大利餐廳", "italian_restaurant",
        "日式餐廳", "japanese_restaurant",
        "果汁店", "juice_shop",
        "韓式餐廳", "korean_restaurant",
        "黎巴嫩餐廳", "lebanese_restaurant",
        "外送", "meal_delivery",
        "外帶", "meal_takeaway",
        "地中海餐廳", "mediterranean_restaurant",
        "墨西哥餐廳", "mexican_restaurant",
        "中東餐廳", "middle_eastern_restaurant",
        "披薩店", "pizza_restaurant",
        "酒館", "pub",
        "拉麵店", "ramen_restaurant",
        "餐廳", "restaurant",
        "三明治店", "sandwich_shop",
        "海鮮餐廳", "seafood_restaurant",
        "西班牙餐廳", "spanish_restaurant",
        "牛排館", "steak_house",
        "壽司店", "sushi_restaurant",
        "茶館", "tea_house",
        "泰式餐廳", "thai_restaurant",
        "土耳其餐廳", "turkish_restaurant",
        "純素餐廳", "vegan_restaurant",
        "素食餐廳", "vegetarian_restaurant",
        "越南餐廳", "vietnamese_restaurant",
        "葡萄酒吧", "wine_bar",
    ]
}

# 建立反向映射：英文關鍵字 -> 中文顯示名稱
ENGLISH_TO_CHINESE = {}
for category, items in PLACE_TYPES.items():
    for i in range(0, len(items), 2):
        if i+1 < len(items):
            ENGLISH_TO_CHINESE[items[i+1]] = items[i]

# 建立類別顏色
CATEGORY_COLORS = {
    "教育": "#1E90FF",        # 藍色
    "購物": "#FF8C00",        # 橘色
    "交通運輸": "#800080",     # 紫色
    "健康與保健": "#32CD32",   # 綠色
    "餐飲美食": "#FF4500",     # 紅色
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

    st.warning(f"地址解析錯誤: {status}")
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
        # 使用反向映射獲取中文類別名稱
        chinese_name = ENGLISH_TO_CHINESE.get(keyword, keyword)
        results.append((
            "關鍵字",
            chinese_name,
            p.get("name", "未命名"),
            loc["lat"],
            loc["lng"],
            dist,
            p.get("place_id", "")
        ))
    return results


def load_population_csv(folder="./page_modules"):
    path = os.path.join(folder, "NEWWWW.csv")
    if not os.path.exists(path):
        return pd.DataFrame()

    try:
        df = pd.read_csv(path, encoding="utf-8")
    except:
        df = pd.read_csv(path, encoding="big5")

    return df


def query_google_places_keyword(lat, lng, api_key, selected_categories, selected_subtypes, radius=500, extra_keyword=""):
    results, seen = [], set()
    
    # 計算總任務數
    total_tasks = sum(len([st for st in selected_subtypes.get(cat, []) if st in PLACE_TYPES[cat][1::2]]) for cat in selected_categories)
    total_tasks += (1 if extra_keyword else 0)

    if total_tasks == 0:
        st.warning("⚠️ 請至少選擇一個搜尋項目")
        return []

    progress = st.progress(0)
    progress_text = st.empty()
    completed = 0

    def update_progress(task_desc):
        nonlocal completed
        completed += 1
        progress.progress(min(completed / total_tasks, 1.0))
        progress_text.text(f"進度：{completed}/{total_tasks} - {task_desc}")

    for cat in selected_categories:
        if cat not in selected_subtypes:
            continue
            
        # 取得該類別下選中的子項目（英文關鍵字）
        selected_english = [st for st in selected_subtypes[cat] if st in PLACE_TYPES[cat][1::2]]
        
        for english_kw in selected_english:
            # 取得中文名稱用於顯示
            chinese_names = {items[i+1]: items[i] for i in range(0, len(PLACE_TYPES[cat]), 2)}
            chinese_name = chinese_names.get(english_kw, english_kw)
            
            update_progress(f"查詢 {cat}-{chinese_name}")
            
            # 使用英文關鍵字查詢
            for p in search_text_google_places(lat, lng, api_key, english_kw, radius):
                if p[5] > radius:
                    continue
                pid = p[6]
                if pid in seen:
                    continue
                seen.add(pid)
                # 存儲時使用中文類別名稱
                results.append((cat, chinese_name, p[2], p[3], p[4], p[5], pid))

            time.sleep(0.5)  # 避免API限制

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


def check_places_found(places, selected_categories, selected_subtypes, extra_keyword):
    # 建立檢查字典：類別 -> 子項目 -> 是否找到
    found_dict = {}
    for cat in selected_categories:
        if cat in selected_subtypes:
            found_dict[cat] = {subtype: False for subtype in selected_subtypes[cat]}
    
    extra_found = False

    for cat, kw, name, lat, lng, dist, pid in places:
        if cat in found_dict and kw in found_dict[cat]:
            found_dict[cat][kw] = True
        if extra_keyword and cat == "關鍵字" and kw == extra_keyword:
            extra_found = True

    messages = []
    for cat, subtypes in found_dict.items():
        for subtype, found in subtypes.items():
            if not found:
                messages.append(f"⚠️ 周圍沒有 {cat} → {subtype}")

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


# ============================
# 專業提示詞準備函數
# ============================
def prepare_market_analysis_prompt(chart_type, data, real_estate_df, population_df):
    """準備專業的市場分析提示詞"""
    
    base_context = f"""
    你是一位資深不動產分析師，擁有10年市場分析經驗。
    請針對以下數據提供專業、客觀的分析報告。
    
    分析範圍：
    - 地區：{data.get('city', '全台')} - {data.get('district', '全部')}
    - 時間：{data.get('year_range', ())} 年
    - 數據類型：{chart_type}
    """
    
    if chart_type == "不動產價格趨勢分析（含交易結構）":
        prompt = base_context + f"""
        
        具體數據：
        1. 價格趨勢：
           - 分析期間：{data.get('years', [])} 年
           - 新成屋價格趨勢：{data.get('new_price', [])}
           - 中古屋價格趨勢：{data.get('old_price', [])}
        
        2. 交易結構：
           - 新成屋交易量：{data.get('new_trans', [])}
           - 中古屋交易量：{data.get('old_trans', [])}
        
        請提供以下分析：
        1. 【價格走勢解讀】
           - 新舊房屋價格差異與趨勢
           - 價格加速度（上漲/下跌速度變化）
           - 關鍵轉折點分析
        
        2. 【交易結構分析】
           - 市場主力是新成屋還是中古屋？
           - 交易量與價格的關係（價量關係）
           - 是否存在「價漲量縮」或「價跌量增」現象？
        
        3. 【市場健康度評估】
           - 市場是否過熱或過冷？
           - 新舊房屋的市場競爭態勢
        
        4. 【投資建議】
           - 對自住買家的建議
           - 對投資客的建議
           - 風險提示
        
        5. 【未來展望】
           - 短期（1年）趨勢預測
           - 長期（3-5年）可能發展
        
        請用專業但易懂的語言，避免過度技術術語。
        """
        
    elif chart_type == "交易筆數分布（結構）":
        prompt = base_context + f"""
        
        具體數據：
        1. 交易量Top 10行政區：{data.get('top_districts', [])}
        2. 每年Top 3行政區：{data.get('yearly_top3', {})}
        
        請提供以下分析：
        1. 【區域熱度分析】
           - 哪些行政區交易最熱絡？原因可能為何？
           - 交易集中度分析（是否過度集中特定區域）
        
        2. 【時間變化趨勢】
           - 熱門行政區是否隨時間改變？
           - 是否有新興熱區或沒落區域？
        
        3. 【市場結構分析】
           - 交易是否健康分散或多樣化？
           - 是否存在區域發展不平衡？
        
        4. 【政策與發展關聯】
           - 交易熱區與都市計畫、交通建設的關聯
           - 地方政府政策影響
        
        5. 【投資策略建議】
           - 熱區的投資風險與機會
           - 潛力區域的識別指標
        
        請結合當地發展背景進行分析。
        """
        
    elif chart_type == "人口 × 成交量（市場是否被壓抑）":
        prompt = base_context + f"""
        
        具體數據：
        人口與成交量趨勢：{data.get('population_trend', [])}
        
        請提供以下分析：
        1. 【人口與成交量關係解讀】
           - 兩者走勢是同步還是脫鉤？
           - 計算人口成長率 vs 交易量成長率
        
        2. 【市場壓抑程度評估】
           - 判斷市場是否被壓抑的指標
           - 如果人口成長但成交量未成長，可能原因：
             * 購買力不足
             * 供給限制
             * 政策影響（如信用管制）
             * 價格過高
        
        3. 【需求與供給分析】
           - 潛在需求估算
           - 市場吸收率分析
        
        4. 【政策影響評估】
           - 哪些政策可能影響市場供需？
           - 現行政策的效果評估
        
        5. 【市場預測與建議】
           - 如果政策放鬆，可能釋放的購買力
           - 對不同族群（首購、換屋、投資）的影響
           - 風險管理建議
        
        6. 【長期結構性問題】
           - 少子化、高齡化對市場的長期影響
           - 住宅類型需求的結構性變化
        
        請提供具體的數據解讀與實務建議。
        """
    
    else:
        prompt = base_context + "\n請提供一般性的市場趨勢分析。"
    
    return prompt


# ===========================
# 新增：建立子項目選擇器
# ===========================
def create_subtype_selector():
    """建立細分項目選擇器，返回使用者選擇的類別和子項目"""
    
    st.subheader("🏪 選擇生活機能類別")
    
    # 初始化 session state
    if 'selected_categories' not in st.session_state:
        st.session_state.selected_categories = []
    if 'selected_subtypes' not in st.session_state:
        st.session_state.selected_subtypes = {}
    
    selected_categories = []
    selected_subtypes = {}
    
    # 建立展開器讓使用者可以逐一點開選擇
    for category, items in PLACE_TYPES.items():
        with st.expander(f"📁 {category} ({len(items)//2}種設施)", expanded=False):
            # 主類別選擇框
            select_all = st.checkbox(f"選擇所有{category}設施", key=f"select_all_{category}")
            
            if select_all:
                # 選中所有子項目
                chinese_items = items[::2]  # 中文名稱
                english_items = items[1::2]  # 英文關鍵字
                selected_subtypes[category] = english_items
                selected_categories.append(category)
                
                # 顯示已選項目
                st.info(f"已選擇 {category} 全部 {len(chinese_items)} 種設施")
            else:
                # 逐個子項目選擇
                cols = st.columns(2)
                for i in range(0, len(items), 2):
                    if i+1 < len(items):
                        chinese_name = items[i]  # 中文名稱
                        english_keyword = items[i+1]  # 英文關鍵字
                        col_idx = (i//2) % 2
                        
                        with cols[col_idx]:
                            if st.checkbox(chinese_name, key=f"{category}_{english_keyword}"):
                                if category not in selected_subtypes:
                                    selected_subtypes[category] = []
                                selected_subtypes[category].append(english_keyword)
            
            # 如果有選中任何子項目，就加入主類別
            if category in selected_subtypes and selected_subtypes[category]:
                selected_categories.append(category)
    
    # 顯示選擇摘要
    if selected_categories:
        st.markdown("---")
        st.subheader("📋 已選擇的設施")
        
        for cat in selected_categories:
            if cat in selected_subtypes:
                chinese_names = []
                # 將英文關鍵字轉回中文名稱
                for english_kw in selected_subtypes[cat]:
                    # 找到對應的中文名稱
                    for i in range(0, len(PLACE_TYPES[cat]), 2):
                        if i+1 < len(PLACE_TYPES[cat]) and PLACE_TYPES[cat][i+1] == english_kw:
                            chinese_names.append(PLACE_TYPES[cat][i])
                            break
                
                st.markdown(f"**{cat}** ({len(chinese_names)}項):")
                cols = st.columns(3)
                for idx, name in enumerate(chinese_names):
                    with cols[idx % 3]:
                        st.markdown(f"✓ {name}")
    
    return selected_categories, selected_subtypes


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
            radius = st.slider("搜尋半徑 (公尺)", 100, 2000, 500, 100, key="radius_slider")
            keyword = st.text_input("額外關鍵字搜尋 (可選)", key="extra_keyword", 
                                  placeholder="例如：公園、健身房、銀行等")

            # 新的子項目選擇器
            selected_categories, selected_subtypes = create_subtype_selector()

            if st.button("開始比較", type="primary"):
                if not _get_browser_key():
                    st.error("❌ 請在側邊欄填入 Google Maps **Browser Key**")
                    st.stop()
                if not server_key or not gemini_key:
                    st.error("❌ 請在側邊欄填入 Server Key 與 Gemini Key")
                    st.stop()
                if choice_a == choice_b:
                    st.warning("⚠️ 請選擇兩個不同房屋")
                    st.stop()
                if not selected_categories:
                    st.warning("⚠️ 請至少選擇一個生活機能類別")
                    st.stop()

                house_a = fav_df[(fav_df['標題'] + " | " + fav_df['地址']) == choice_a].iloc[0]
                house_b = fav_df[(fav_df['標題'] + " | " + fav_df['地址']) == choice_b].iloc[0]

                lat_a, lng_a = geocode_address(house_a["地址"], server_key)
                lat_b, lng_b = geocode_address(house_b["地址"], server_key)

                if lat_a is None or lat_b is None:
                    st.error("❌ 地址解析失敗，請檢查 Server Key 限制。")
                    return

                # 顯示房屋基本資訊
                st.markdown("---")
                col_a, col_b = st.columns(2)
                with col_a:
                    st.markdown(f"### 房屋 A")
                    st.markdown(f"**標題**: {house_a['標題']}")
                    st.markdown(f"**地址**: {house_a['地址']}")
                    st.markdown(f"**價格**: {house_a.get('價格', 'N/A')}")
                
                with col_b:
                    st.markdown(f"### 房屋 B")
                    st.markdown(f"**標題**: {house_b['標題']}")
                    st.markdown(f"**地址**: {house_b['地址']}")
                    st.markdown(f"**價格**: {house_b.get('價格', 'N/A')}")

                # 查詢房屋周邊
                with st.spinner("正在查詢房屋 A 周邊..."):
                    places_a = query_google_places_keyword(
                        lat_a, lng_a, server_key, selected_categories, selected_subtypes,
                        radius, extra_keyword=keyword
                    )
                    messages_a = check_places_found(places_a, selected_categories, selected_subtypes, keyword)
                    for msg in messages_a:
                        st.warning(f"房屋 A: {msg}")
                    time.sleep(1)

                with st.spinner("正在查詢房屋 B 周邊..."):
                    places_b = query_google_places_keyword(
                        lat_b, lng_b, server_key, selected_categories, selected_subtypes,
                        radius, extra_keyword=keyword
                    )
                    messages_b = check_places_found(places_b, selected_categories, selected_subtypes, keyword)
                    for msg in messages_b:
                        st.warning(f"房屋 B: {msg}")

                # 顯示設施統計
                st.markdown("---")
                st.subheader("🏪 設施統計比較")
                
                col_stat1, col_stat2 = st.columns(2)
                with col_stat1:
                    st.markdown(f"**房屋 A** 找到 {len(places_a)} 個設施")
                    if places_a:
                        cat_counts = {}
                        for cat, kw, name, lat, lng, dist, pid in places_a:
                            cat_counts[cat] = cat_counts.get(cat, 0) + 1
                        
                        for cat, count in cat_counts.items():
                            st.markdown(f"- {cat}: {count}個")
                
                with col_stat2:
                    st.markdown(f"**房屋 B** 找到 {len(places_b)} 個設施")
                    if places_b:
                        cat_counts = {}
                        for cat, kw, name, lat, lng, dist, pid in places_b:
                            cat_counts[cat] = cat_counts.get(cat, 0) + 1
                        
                        for cat, count in cat_counts.items():
                            st.markdown(f"- {cat}: {count}個")

                # 顯示地圖
                st.markdown("---")
                st.subheader("🗺️ 地圖比較")
                col1, col2 = st.columns(2)
                with col1:
                    render_map(lat_a, lng_a, places_a, radius, title="房屋 A")
                with col2:
                    render_map(lat_b, lng_b, places_b, radius, title="房屋 B")

                # ============================
                # Gemini 分析（防爆版）
                # ============================
                
                # 建立唯一 key，確保不同房屋組合才重新分析
                analysis_key = f"{choice_a}__{choice_b}__{keyword}__{','.join(selected_categories)}"
                
                if (
                    "gemini_result" not in st.session_state
                    or st.session_state.get("gemini_key") != analysis_key
                ):
                
                    now = time.time()
                    last = st.session_state.get("last_gemini_call", 0)
                
                    # 免費帳號冷卻時間（非常重要）
                    if now - last < 30:
                        st.warning("⚠️ Gemini 分析請等待 30 秒後再試")
                        st.stop()
                
                    st.session_state.last_gemini_call = now
                
                    with st.spinner("🧠 Gemini 分析中，請稍候..."):
                        try:
                            genai.configure(api_key=gemini_key)
                            model = genai.GenerativeModel("gemini-2.0-flash")
                
                            # 限制輸入長度，避免 token 爆掉
                            def format_places_safe(places, limit=15):
                                if not places:
                                    return "無周邊資料"
                                places_text = []
                                for cat, kw, name, lat, lng, dist, pid in places[:limit]:
                                    places_text.append(f"{cat}-{kw}: {name}（{dist} 公尺）")
                                return "\n".join(places_text)
                
                            places_a_text = format_places_safe(places_a)
                            places_b_text = format_places_safe(places_b)
                            
                            # 統計資訊
                            total_a = len(places_a)
                            total_b = len(places_b)
                            
                            # 計算各類
