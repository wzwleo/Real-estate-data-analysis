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
# ===========================
# 關鍵字設定 - 優化版（針對台灣地區）
# ===========================
PLACE_TYPES = {
    "教育": [
        "圖書館", "library",
        "幼兒園", "kindergarten",
        "托兒所", "nursery",
        "小學", "elementary school",
        "國中", "junior high school",
        "高中", "high school",
        "大學", "university",
        "補習班", "cram school",
        "學校", "school",
    ],
    "購物": [
        "超市", "supermarket",
        "便利商店", "convenience store",
        "全聯福利中心", "Pxmart",
        "家樂福", "Carrefour",
        "大潤發", "RT Mart",
        "好市多", "Costco",
        "屈臣氏", "Watsons",
        "康是美", "Cosmed",
        "寶雅", "Poya",
        "藥妝店", "drugstore",
        "五金行", "hardware store",
        "家具行", "furniture store",
        "書局", "bookstore",
        "文具店", "stationery store",
        "手機行", "mobile phone store",
        "電腦賣場", "computer store",
        "服飾店", "clothing store",
        "鞋店", "shoe store",
        "眼鏡行", "eyeglasses store",
        "百貨公司", "department store",
        "購物中心", "shopping mall",
        "市場", "market",
        "傳統市場", "traditional market",
        "夜市", "night market",
        "批發", "wholesale",
    ],
    "交通運輸": [
        "公車站", "bus station",
        "捷運站", "MRT station",
        "火車站", "train station",
        "高鐵站", "HSR station",
        "客運站", "bus terminal",
        "計程車行", "taxi company",
        "停車場", "parking lot",
        "加油站", "gas station",
        "YouBike", "YouBike",
        "機車行", "motorcycle shop",
        "汽車維修", "car repair",
    ],
    "健康與保健": [
        "醫院", "hospital",
        "診所", "clinic",
        "衛生所", "health center",
        "藥局", "pharmacy",
        "牙醫診所", "dental clinic",
        "中醫診所", "Chinese medicine clinic",
        "西醫診所", "western medicine clinic",
        "小兒科診所", "pediatric clinic",
        "婦產科診所", "obstetrics and gynecology clinic",
        "眼科診所", "ophthalmology clinic",
        "皮膚科診所", "dermatology clinic",
        "復健科診所", "rehabilitation clinic",
        "物理治療所", "physical therapy clinic",
        "按摩店", "massage shop",
        "養生館", "wellness center",
        "SPA", "SPA",
        "健身中心", "fitness center",
        "健身房", "gym",
        "瑜珈教室", "yoga studio",
        "運動中心", "sports center",
    ],
    "餐飲美食": [
        "餐廳", "restaurant",
        "小吃店", "snack shop",
        "早餐店", "breakfast shop",
        "咖啡廳", "cafe",
        "星巴克", "Starbucks",
        "路易莎咖啡", "Louisa Coffee",
        "85度C", "85C Bakery Cafe",
        "手搖飲料店", "bubble tea shop",
        "飲料店", "drink shop",
        "速食店", "fast food restaurant",
        "麥當勞", "McDonald's",
        "肯德基", "KFC",
        "摩斯漢堡", "Mos Burger",
        "漢堡王", "Burger King",
        "披薩店", "pizza restaurant",
        "達美樂披薩", "Domino's Pizza",
        "拿坡里披薩", "Napoli Pizza",
        "必勝客", "Pizza Hut",
        "火鍋店", "hot pot restaurant",
        "燒烤店", "barbecue restaurant",
        "牛排館", "steakhouse",
        "鐵板燒", "teppanyaki",
        "日本料理", "Japanese restaurant",
        "壽司店", "sushi restaurant",
        "拉麵店", "ramen restaurant",
        "韓式料理", "Korean restaurant",
        "泰式料理", "Thai restaurant",
        "越南料理", "Vietnamese restaurant",
        "美式餐廳", "American restaurant",
        "義大利麵餐廳", "Italian restaurant",
        "自助餐", "buffet",
        "便當店", "lunch box shop",
        "麵店", "noodle shop",
        "滷味店", "braised food shop",
        "鹽酥雞", "fried chicken",
        "雞排店", "chicken steak shop",
        "甜點店", "dessert shop",
        "蛋糕店", "cake shop",
        "麵包店", "bakery",
        "冰店", "ice shop",
        "豆花店", "tofu pudding shop",
    ],
    "生活服務": [
        "銀行", "bank",
        "郵局", "post office",
        "派出所", "police station",
        "警察局", "police department",
        "消防局", "fire station",
        "區公所", "district office",
        "戶政事務所", "household registration office",
        "運動公園", "sports park",
        "公園", "park",
        "兒童公園", "children's park",
        "河濱公園", "riverside park",
        "廟宇", "temple",
        "教堂", "church",
        "洗車場", "car wash",
        "汽車美容", "car detailing",
        "洗衣店", "laundry",
        "影印店", "copy shop",
        "電信行", "telecom store",
        "中華電信", "Chunghwa Telecom",
        "台灣大哥大", "Taiwan Mobile",
        "遠傳電信", "FarEasTone",
        "寵物店", "pet store",
        "動物醫院", "animal hospital",
    ]
}

# 建立反向映射：英文關鍵字 -> 中文顯示名稱
ENGLISH_TO_CHINESE = {}
for category, items in PLACE_TYPES.items():
    for i in range(0, len(items), 2):
        if i+1 < len(items):
            ENGLISH_TO_CHINESE[items[i+1]] = items[i]

# 建立類別顏色（增加生活服務的顏色）
CATEGORY_COLORS = {
    "教育": "#1E90FF",        # 藍色
    "購物": "#FF8C00",        # 橘色
    "交通運輸": "#800080",     # 紫色
    "健康與保健": "#32CD32",   # 綠色
    "餐飲美食": "#FF4500",     # 紅色
    "生活服務": "#FF1493",     # 深粉色
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
            st.stop()  # 停止執行後續程式
        
        options = fav_df['標題'] + " | " + fav_df['地址']
        c1, c2 = st.columns(2)
        with c1:
            choice_a = st.selectbox("選擇房屋 A", options, key="compare_a")
        with c2:
            choice_b = st.selectbox("選擇房屋 B", options, key="compare_b")

        # 顯示選擇的房屋資訊
        if choice_a and choice_b:
            house_a = fav_df[(fav_df['標題'] + " | " + fav_df['地址']) == choice_a].iloc[0]
            house_b = fav_df[(fav_df['標題'] + " | " + fav_df['地址']) == choice_b].iloc[0]
            
            col_info1, col_info2 = st.columns(2)
            with col_info1:
                st.markdown(f"**房屋 A**")
                st.markdown(f"📍 {house_a['地址']}")
                st.markdown(f"🏷️ {house_a['標題']}")
            
            with col_info2:
                st.markdown(f"**房屋 B**")
                st.markdown(f"📍 {house_b['地址']}")
                st.markdown(f"🏷️ {house_b['標題']}")

        server_key = _get_server_key()
        gemini_key = st.session_state.get("GEMINI_KEY", "")
        radius = st.slider("搜尋半徑 (公尺)", 100, 2000, 500, 100, key="radius_slider")
        keyword = st.text_input("額外關鍵字搜尋 (可選)", key="extra_keyword", 
                              placeholder="例如：公園、健身房、銀行等")

        st.markdown("---")
        st.subheader("🔍 選擇生活機能類別")
        
        # 初始化 session state
        if 'selected_subtypes' not in st.session_state:
            st.session_state.selected_subtypes = {}
        
        selected_categories = []
        selected_subtypes = {}
        
        # 建立大類別選擇器
        st.markdown("### 選擇大類別")
        all_categories = list(PLACE_TYPES.keys())
        cols = st.columns(len(all_categories))
        
        category_selection = {}
        for i, cat in enumerate(all_categories):
            with cols[i]:
                # 使用顏色標籤
                color = CATEGORY_COLORS.get(cat, "#000000")
                st.markdown(f'<span style="background-color:{color}; color:white; padding:5px 10px; border-radius:5px;">{cat}</span>', unsafe_allow_html=True)
                category_selection[cat] = st.checkbox(f"選擇{cat}", key=f"main_cat_{cat}")
        
        # 如果選擇了大類別，顯示細分選項
        selected_main_cats = [cat for cat, selected in category_selection.items() if selected]
        
        if selected_main_cats:
            st.markdown("### 選擇細分設施")
            
            for cat in selected_main_cats:
                with st.expander(f"📁 {cat} 類別細選", expanded=True):
                    # 全選按鈕
                    select_all = st.checkbox(f"選擇所有{cat}設施", key=f"select_all_{cat}")
                    
                    if select_all:
                        # 選中所有子項目
                        items = PLACE_TYPES[cat]
                        selected_subtypes[cat] = items[1::2]  # 英文關鍵字
                        selected_categories.append(cat)
                        
                        st.info(f"已選擇 {cat} 全部 {len(items)//2} 種設施")
                    else:
                        # 逐個子項目選擇
                        items = PLACE_TYPES[cat]
                        num_columns = 3
                        num_items = len(items) // 2
                        
                        # 計算每列要顯示的項目數
                        items_per_row = (num_items + num_columns - 1) // num_columns
                        
                        for row in range(items_per_row):
                            cols = st.columns(num_columns)
                            for col_idx in range(num_columns):
                                item_idx = row + col_idx * items_per_row
                                if item_idx * 2 + 1 < len(items):
                                    chinese_name = items[item_idx * 2]  # 中文名稱
                                    english_keyword = items[item_idx * 2 + 1]  # 英文關鍵字
                                    
                                    with cols[col_idx]:
                                        if st.checkbox(chinese_name, key=f"{cat}_{english_keyword}"):
                                            if cat not in selected_subtypes:
                                                selected_subtypes[cat] = []
                                            selected_subtypes[cat].append(english_keyword)
                    
                    # 如果有選中任何子項目，就加入主類別
                    if cat in selected_subtypes and selected_subtypes[cat]:
                        selected_categories.append(cat)
        
        # 顯示選擇摘要
        if selected_categories:
            st.markdown("---")
            st.subheader("📋 已選擇的設施摘要")
            
            summary_cols = st.columns(min(len(selected_categories), 3))
            for idx, cat in enumerate(selected_categories):
                with summary_cols[idx % len(summary_cols)]:
                    if cat in selected_subtypes:
                        count = len(selected_subtypes[cat])
                        color = CATEGORY_COLORS.get(cat, "#000000")
                        st.markdown(f"""
                        <div style="background-color:{color}20; padding:10px; border-radius:5px; border-left:4px solid {color};">
                        <h4 style="color:{color}; margin:0;">{cat}</h4>
                        <p style="margin:5px 0 0 0;">已選擇 {count} 種設施</p>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        # 顯示前幾個項目
                        if count <= 5:
                            items_display = ", ".join([
                                PLACE_TYPES[cat][PLACE_TYPES[cat].index(english_kw)-1] 
                                for english_kw in selected_subtypes[cat][:5]
                            ])
                            st.caption(f"✓ {items_display}")
                        else:
                            st.caption(f"✓ 包含{selected_subtypes[cat][:3]}等{count}種設施")
        
        st.markdown("---")
        
        if st.button("🚀 開始比較", type="primary", use_container_width=True):
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

            # 地址解析
            with st.spinner("📍 解析房屋地址中..."):
                lat_a, lng_a = geocode_address(house_a["地址"], server_key)
                lat_b, lng_b = geocode_address(house_b["地址"], server_key)

            if lat_a is None or lat_b is None:
                st.error("❌ 地址解析失敗，請檢查地址格式或 Server Key 限制。")
                return

            # 顯示比較標題
            st.markdown("## 📊 比較結果")
            
            # 查詢房屋A周邊
            with st.spinner(f"🔍 查詢房屋 A 周邊設施 (半徑: {radius}公尺)..."):
                places_a = query_google_places_keyword(
                    lat_a, lng_a, server_key, selected_categories, selected_subtypes,
                    radius, extra_keyword=keyword
                )
                messages_a = check_places_found(places_a, selected_categories, selected_subtypes, keyword)
                if messages_a:
                    for msg in messages_a:
                        st.warning(f"房屋 A: {msg}")

            # 查詢房屋B周邊
            with st.spinner(f"🔍 查詢房屋 B 周邊設施 (半徑: {radius}公尺)..."):
                places_b = query_google_places_keyword(
                    lat_b, lng_b, server_key, selected_categories, selected_subtypes,
                    radius, extra_keyword=keyword
                )
                messages_b = check_places_found(places_b, selected_categories, selected_subtypes, keyword)
                if messages_b:
                    for msg in messages_b:
                        st.warning(f"房屋 B: {msg}")

            # 設施統計比較
            st.markdown("---")
            st.subheader("📈 設施統計比較")
            
            # 計算各類別數量
            def count_by_category(places):
                counts = {}
                for cat, kw, name, lat, lng, dist, pid in places:
                    counts[cat] = counts.get(cat, 0) + 1
                return counts
            
            counts_a = count_by_category(places_a)
            counts_b = count_by_category(places_b)
            
            # 顯示統計圖表
            stat_cols = st.columns(3)
            with stat_cols[0]:
                st.metric("🏠 房屋 A", f"{len(places_a)} 個設施", 
                         f"半徑 {radius}公尺")
                if places_a:
                    st.caption("最近設施: " + str(min([p[5] for p in places_a])) + "公尺")
            
            with stat_cols[1]:
                difference = len(places_a) - len(places_b)
                st.metric("🏠 房屋 B", f"{len(places_b)} 個設施", 
                         f"{difference:+d} 差異")
                if places_b:
                    st.caption("最近設施: " + str(min([p[5] for p in places_b])) + "公尺")
            
            with stat_cols[2]:
                total_found = len(places_a) + len(places_b)
                st.metric("🔍 總計找到", f"{total_found} 個設施", 
                         f"{len(set([p[6] for p in places_a + places_b]))} 個不重複地點")

            # 顯示各類別詳細比較
            st.markdown("### 各類別設施數量")
            all_cats = set(list(counts_a.keys()) + list(counts_b.keys()))
            
            comparison_data = []
            for cat in all_cats:
                a_count = counts_a.get(cat, 0)
                b_count = counts_b.get(cat, 0)
                color = CATEGORY_COLORS.get(cat, "#CCCCCC")
                comparison_data.append({
                    "類別": cat,
                    "房屋A": a_count,
                    "房屋B": b_count,
                    "顏色": color
                })
            
            # 以表格形式顯示
            if comparison_data:
                comp_df = pd.DataFrame(comparison_data)
                comp_df = comp_df.sort_values("房屋A", ascending=False)
                
                # 顯示表格
                st.dataframe(
                    comp_df[['類別', '房屋A', '房屋B']],
                    use_container_width=True,
                    hide_index=True
                )
                
                # 也顯示條形圖
                chart_data = {
                    "xAxis": {
                        "type": "category",
                        "data": comp_df['類別'].tolist()
                    },
                    "yAxis": {"type": "value"},
                    "series": [
                        {
                            "name": "房屋 A",
                            "type": "bar",
                            "data": comp_df['房屋A'].tolist(),
                            "itemStyle": {"color": "#1E90FF"}
                        },
                        {
                            "name": "房屋 B",
                            "type": "bar", 
                            "data": comp_df['房屋B'].tolist(),
                            "itemStyle": {"color": "#FF8C00"}
                        }
                    ],
                    "tooltip": {"trigger": "axis"},
                    "legend": {"data": ["房屋 A", "房屋 B"]}
                }
                
                st_echarts(chart_data, height="400px")

            # 顯示地圖
            st.markdown("---")
            st.subheader("🗺️ 地圖比較")
            map_cols = st.columns(2)
            with map_cols[0]:
                st.markdown(f"### 房屋 A")
                render_map(lat_a, lng_a, places_a, radius, title="房屋 A")
                
                # 顯示最近的幾個設施
                if places_a:
                    st.markdown("**最近的 5 個設施:**")
                    for i, (cat, kw, name, lat, lng, dist, pid) in enumerate(places_a[:5]):
                        st.caption(f"{i+1}. {cat}-{kw}: {name} ({dist}公尺)")
            
            with map_cols[1]:
                st.markdown(f"### 房屋 B")
                render_map(lat_b, lng_b, places_b, radius, title="房屋 B")
                
                # 顯示最近的幾個設施
                if places_b:
                    st.markdown("**最近的 5 個設施:**")
                    for i, (cat, kw, name, lat, lng, dist, pid) in enumerate(places_b[:5]):
                        st.caption(f"{i+1}. {cat}-{kw}: {name} ({dist}公尺)")

            # ============================
            # Gemini 分析
            # ============================
            st.markdown("---")
            st.subheader("🤖 AI 智能分析")
            
            # 建立唯一 key
            analysis_key = f"{choice_a}__{choice_b}__{keyword}__{','.join(selected_categories)}__{radius}"
            
            # 檢查是否需要重新分析
            should_analyze = (
                "gemini_result" not in st.session_state or
                st.session_state.get("gemini_key") != analysis_key
            )
            
            if should_analyze:
                # 防爆檢查
                now = time.time()
                last = st.session_state.get("last_gemini_call", 0)
                
                if now - last < 30:
                    st.warning("⚠️ Gemini 分析請等待 30 秒後再試")
                    st.stop()
                
                st.session_state.last_gemini_call = now
                
                with st.spinner("🧠 AI 分析比較結果中..."):
                    try:
                        genai.configure(api_key=gemini_key)
                        model = genai.GenerativeModel("gemini-2.0-flash")
                        
                        # 準備分析資料
                        def format_places_for_ai(places, house_name, limit=20):
                            if not places:
                                return f"{house_name}：周圍 500 公尺內未找到任何選定的生活設施。"
                            
                            text = f"{house_name} 找到 {len(places)} 個設施：\n"
                            by_category = {}
                            for cat, kw, name, lat, lng, dist, pid in places[:limit]:
                                if cat not in by_category:
                                    by_category[cat] = []
                                by_category[cat].append(f"- {kw}：{name}（距離 {dist} 公尺）")
                            
                            for cat, items in by_category.items():
                                text += f"\n【{cat}】\n"
                                text += "\n".join(items[:5])  # 每類別最多顯示5個
                                if len(items) > 5:
                                    text += f"\n...及其他 {len(items)-5} 個設施"
                            
                            return text
                        
                        places_a_text = format_places_for_ai(places_a, "房屋 A")
                        places_b_text = format_places_for_ai(places_b, "房屋 B")
                        
                        # 統計摘要
                        stats_summary = f"""
                        統計摘要：
                        - 房屋 A：共 {len(places_a)} 個設施，最近設施 {min([p[5] for p in places_a]) if places_a else 0} 公尺
                        - 房屋 B：共 {len(places_b)} 個設施，最近設施 {min([p[5] for p in places_b]) if places_b else 0} 公尺
                        - 設施差異：房屋 A 比房屋 B {'多' if len(places_a) > len(places_b) else '少'} {abs(len(places_a)-len(places_b))} 個設施
                        """
                        
                        # 建構提示詞
                        prompt = f"""
                        你是一位專業的房地產分析師，請根據以下兩間房屋的生活機能進行比較分析。
                        
                        【分析要求】
                        1. 請以中文繁體回應
                        2. 從「自住」和「投資」兩個角度分析
                        3. 考慮各類生活設施的完整性與距離
                        4. 提供具體建議與風險提示
                        
                        【搜尋條件】
                        - 搜尋半徑：{radius} 公尺
                        - 選擇的生活機能類別：{', '.join(selected_categories)}
                        - 額外關鍵字：{keyword if keyword else '無'}
                        
                        【房屋基本資訊】
                        - 房屋 A：{house_a['標題']}，地址：{house_a['地址']}
                        - 房屋 B：{house_b['標題']}，地址：{house_b['地址']}
                        
                        【設施統計】
                        {stats_summary}
                        
                        【房屋 A 周邊設施】
                        {places_a_text}
                        
                        【房屋 B 周邊設施】
                        {places_b_text}
                        
                        【請依序分析】
                        1. 總體設施豐富度比較
                        2. 各類別設施完整性分析（教育、購物、交通、健康、餐飲）
                        3. 生活便利性評估
                        4. 對「自住者」的建議（哪間更適合，為什麼）
                        5. 對「投資者」的建議（哪間更有潛力，為什麼）
                        6. 潛在缺點與風險提醒
                        7. 綜合結論與推薦
                        
                        請使用專業但易懂的語言，並提供具體的判斷依據。
                        """
                        
                        # 顯示提示詞（可選）
                        with st.expander("📝 查看 AI 分析提示詞"):
                            st.text_area("送給 Gemini 的提示詞", prompt, height=300)
                        
                        # 呼叫 Gemini
                        resp = model.generate_content(prompt)
                        
                        # 儲存結果
                        st.session_state.gemini_result = resp.text
                        st.session_state.gemini_key = analysis_key
                        
                        st.success("✅ AI 分析完成！")
                        
                    except Exception as e:
                        st.error(f"❌ Gemini API 錯誤: {str(e)}")
                        st.info("請檢查：1. API 金鑰是否正確 2. 配額是否用盡 3. 網路連線是否正常")
                        st.stop()
            
            # 顯示分析結果
            if "gemini_result" in st.session_state:
                st.markdown("### 📋 AI 分析報告")
                
                # 美化顯示
                with st.container():
                    st.markdown("---")
                    st.markdown(st.session_state.gemini_result)
                    st.markdown("---")
                
                # 提供下載選項
                report_text = f"""
                房屋比較分析報告
                生成時間：{time.strftime('%Y-%m-%d %H:%M:%S')}
                
                比較房屋：
                - 房屋 A：{house_a['標題']}，地址：{house_a['地址']}
                - 房屋 B：{house_b['標題']}，地址：{house_b['地址']}
                
                搜尋條件：
                - 半徑：{radius} 公尺
                - 選擇類別：{', '.join(selected_categories)}
                - 額外關鍵字：{keyword if keyword else '無'}
                
                AI 分析結果：
                {st.session_state.gemini_result}
                """
                
                st.download_button(
                    label="📥 下載分析報告",
                    data=report_text,
                    file_name=f"房屋比較報告_{time.strftime('%Y%m%d_%H%M%S')}.txt",
                    mime="text/plain",
                    use_container_width=True
                )

    # ============================
    # Tab3: 市場趨勢分析（整合人口資料）
    # ============================
    with tab3:
        # 這裡放置完整的Tab3內容（保持原樣）
        st.subheader("📊 市場趨勢分析")
        
        # 初始化 session state
        if 'market_analysis_result' not in st.session_state:
            st.session_state.market_analysis_result = None
        if 'market_analysis_key' not in st.session_state:
            st.session_state.market_analysis_key = None
        
        # -----------------------------
        # 載入資料
        # -----------------------------
        combined_df = load_real_estate_csv(folder="./page_modules")
        population_df = load_population_csv(folder="./page_modules")
        
        if combined_df.empty or population_df.empty:
            st.info("📂 找不到房產或人口資料")
            st.stop()
        
        # ... 後面的 Tab3 內容保持原樣 ...
        
            # -----------------------------
            # 基本清理
            # -----------------------------
            combined_df["民國年"] = combined_df["季度"].str[:3].astype(int)
        
            population_df.columns = [str(c).strip().replace("　", "") for c in population_df.columns]
            population_df["縣市"] = population_df["縣市"].astype(str).str.strip()
            population_df["行政區"] = population_df["行政區"].astype(str).str.strip()
        
            # -----------------------------
            # 人口資料轉長格式
            # -----------------------------
            year_cols = [c for c in population_df.columns if "年" in c]
            pop_long = population_df.melt(
                id_vars=["縣市", "行政區"],
                value_vars=year_cols,
                var_name="年度",
                value_name="人口數"
            )
        
            pop_long["人口數"] = (
                pop_long["人口數"].astype(str).str.replace(",", "").astype(int)
            )
            pop_long["民國年"] = pop_long["年度"].str[:3].astype(int)
        
            # -----------------------------
            # 篩選條件
            # -----------------------------
            col_main, col_filter = st.columns([3, 1])
        
            with col_filter:
                cities = ["全台"] + sorted(combined_df["縣市"].unique())
                city_choice = st.selectbox("選擇縣市", cities)
        
                if city_choice != "全台":
                    district_choice = st.selectbox(
                        "選擇行政區",
                        ["全部"] + sorted(
                            combined_df[combined_df["縣市"] == city_choice]["行政區"].unique()
                        )
                    )
                else:
                    district_choice = "全部"
        
                year_min = int(min(combined_df["民國年"].min(), pop_long["民國年"].min()))
                year_max = int(max(combined_df["民國年"].max(), pop_long["民國年"].max()))
        
                year_range = st.slider(
                    "選擇分析年份",
                    min_value=year_min,
                    max_value=year_max,
                    value=(year_min, year_max)
                )
        
            # -----------------------------
            # 不動產資料篩選
            # -----------------------------
            re_df = combined_df[
                (combined_df["民國年"] >= year_range[0]) &
                (combined_df["民國年"] <= year_range[1])
            ]
        
            if city_choice != "全台":
                re_df = re_df[re_df["縣市"] == city_choice]
                if district_choice != "全部":
                    re_df = re_df[re_df["行政區"] == district_choice]
        
            # -----------------------------
            # 人口資料篩選
            # -----------------------------
            pop_df = pop_long[
                (pop_long["民國年"] >= year_range[0]) &
                (pop_long["民國年"] <= year_range[1])
            ]
        
            if city_choice == "全台":
                pop_df = pop_df[pop_df["縣市"] == pop_df["行政區"]]
            elif district_choice == "全部":
                pop_df = pop_df[
                    (pop_df["縣市"] == city_choice) &
                    (pop_df["行政區"] == city_choice)
                ]
            else:
                pop_df = pop_df[
                    (pop_df["縣市"] == city_choice) &
                    (pop_df["行政區"] == district_choice)
                ]
        
            # -----------------------------
            # 顯示資料表（保留原有的兩個表格）
            # -----------------------------
            with col_main:
                # 表格 1：不動產資料
                with st.expander("📂 表一：不動產資料（點擊展開）", expanded=True):
                    if not re_df.empty:
                        st.dataframe(re_df, use_container_width=True)
                        st.caption(f"共 {len(re_df)} 筆不動產交易記錄")
                    else:
                        st.warning("該條件下無不動產資料")
        
                # 表格 2：人口資料（年度）
                with st.expander("👥 表二：人口資料（年度，點擊展開）", expanded=False):
                    if not pop_df.empty:
                        # 建立樞紐表顯示年度人口
                        pivot_df = pop_df.pivot_table(
                            index=["縣市", "行政區"],
                            columns="民國年",
                            values="人口數",
                            aggfunc="last"
                        ).fillna(0).astype(int)
                        
                        st.dataframe(pivot_df, use_container_width=True)
                        st.caption(f"人口資料範圍：{year_range[0]} - {year_range[1]} 年")
                    else:
                        st.warning("該條件下無人口資料")
        
            # -----------------------------
            # 選擇分析類型
            # -----------------------------
            st.markdown("---")
            st.subheader("📈 圖表分析")
            
            chart_type = st.selectbox(
                "選擇分析類型",
                [
                    "不動產價格趨勢分析（含交易結構）",
                    "交易筆數分布（結構）",
                    "人口 × 成交量（市場是否被壓抑）"
                ],
                key="market_chart_type"
            )
        
            # 預先定義 analysis_data 變數
            analysis_data = {}
            
            # =====================================================
            # ① 價格趨勢分析（＋交易結構）
            # =====================================================
            if chart_type == "不動產價格趨勢分析（含交易結構）":
        
                # ---- 價格趨勢 ----
                price_df = re_df.groupby(
                    ["民國年", "BUILD"]
                )["平均單價元平方公尺"].mean().reset_index()
        
                years = sorted(price_df["民國年"].unique())
        
                def safe_mean_price(year, build):
                    s = price_df[
                        (price_df["民國年"] == year) &
                        (price_df["BUILD"] == build)
                    ]["平均單價元平方公尺"]
                    return int(s.mean()) if not s.empty else 0
        
                new_price = [safe_mean_price(y, "新成屋") for y in years]
                old_price = [safe_mean_price(y, "中古屋") for y in years]
        
                st.markdown("### 📈 價格趨勢（新成屋 vs 中古屋）")
                st_echarts({
                    "tooltip": {"trigger": "axis"},
                    "legend": {"data": ["新成屋", "中古屋"]},
                    "xAxis": {"type": "category", "data": [str(y) for y in years]},
                    "yAxis": {"type": "value"},
                    "series": [
                        {"name": "新成屋", "type": "line", "data": new_price},
                        {"name": "中古屋", "type": "line", "data": old_price}
                    ]
                }, height="350px")
        
                # 顯示數據摘要
                col1, col2 = st.columns(2)
                with col1:
                    if new_price:
                        latest_new = new_price[-1]
                        first_new = new_price[0]
                        change = ((latest_new - first_new) / first_new * 100) if first_new > 0 else 0
                        st.metric("新成屋價格變化", f"{latest_new:,.0f} 元/㎡", 
                                 f"{change:+.1f}%")
                
                with col2:
                    if old_price:
                        latest_old = old_price[-1]
                        first_old = old_price[0]
                        change = ((latest_old - first_old) / first_old * 100) if first_old > 0 else 0
                        st.metric("中古屋價格變化", f"{latest_old:,.0f} 元/㎡", 
                                 f"{change:+.1f}%")
        
                # ---- 交易結構（堆疊） ----
                trans_df = re_df.groupby(
                    ["民國年", "BUILD"]
                )["交易筆數"].sum().reset_index()
        
                def safe_sum_trans(year, build):
                    s = trans_df[
                        (trans_df["民國年"] == year) &
                        (trans_df["BUILD"] == build)
                    ]["交易筆數"]
                    return int(s.sum()) if not s.empty else 0
        
                new_trans = [safe_sum_trans(y, "新成屋") for y in years]
                old_trans = [safe_sum_trans(y, "中古屋") for y in years]
        
                st.markdown("### 📊 交易結構（量的來源）")
                st_echarts({
                    "tooltip": {"trigger": "axis"},
                    "legend": {"data": ["新成屋", "中古屋"]},
                    "xAxis": {"type": "category", "data": [str(y) for y in years]},
                    "yAxis": {"type": "value"},
                    "series": [
                        {"name": "新成屋", "type": "bar", "stack": "total", "data": new_trans},
                        {"name": "中古屋", "type": "bar", "stack": "total", "data": old_trans}
                    ]
                }, height="350px")
        
                # 儲存資料供 Gemini 分析
                analysis_data = {
                    "years": years,
                    "new_price": new_price,
                    "old_price": old_price,
                    "new_trans": new_trans,
                    "old_trans": old_trans,
                    "city": city_choice,
                    "district": district_choice,
                    "year_range": year_range,
                    "chart_type": "價格趨勢與交易結構",
                    "total_transactions": sum(new_trans) + sum(old_trans)
                }
                
            # =====================================================
            # ② 交易筆數分布（結構）
            # =====================================================
            elif chart_type == "交易筆數分布（結構）":
        
                # 行政區交易量排行（Top 10）
                total_trans = re_df.groupby("行政區")["交易筆數"].sum().reset_index()
                total_trans = total_trans.sort_values("交易筆數", ascending=True).tail(10)
        
                st.markdown("### 📊 行政區交易量排行（Top 10）")
                st_echarts({
                    "tooltip": {"trigger": "axis"},
                    "xAxis": {"type": "value"},
                    "yAxis": {
                        "type": "category",
                        "data": total_trans["行政區"].tolist()
                    },
                    "series": [
                        {"type": "bar", "data": total_trans["交易筆數"].astype(int).tolist()}
                    ]
                }, height="400px")
        
                # 顯示統計摘要
                if not total_trans.empty:
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        total = total_trans["交易筆數"].sum()
                        st.metric("總交易筆數", f"{total:,}")
                    with col2:
                        avg = total_trans["交易筆數"].mean()
                        st.metric("平均交易筆數", f"{avg:,.0f}")
                    with col3:
                        top_area = total_trans.iloc[-1]["行政區"]
                        top_value = total_trans.iloc[-1]["交易筆數"]
                        st.metric("交易最熱區", top_area, f"{top_value:,} 筆")
        
                # 每年交易筆數 Top 3
                with st.expander("📂 查看每年交易筆數 Top 3 行政區"):
                    years = sorted(re_df["民國年"].unique())
                    yearly_top3_data = {}
                    
                    for y in years:
                        df_y = re_df[re_df["民國年"] == y]
                        top3 = df_y.groupby("行政區")["交易筆數"].sum().reset_index()
                        top3 = top3.sort_values("交易筆數", ascending=False).head(3)
                        yearly_top3_data[y] = top3
                        
                        st.markdown(f"#### {y} 年")
                        st.dataframe(top3, use_container_width=True)
        
                # 儲存資料供 Gemini 分析
                analysis_data = {
                    "top_districts": total_trans.to_dict('records'),
                    "yearly_top3": yearly_top3_data,
                    "city": city_choice,
                    "district": district_choice,
                    "year_range": year_range,
                    "chart_type": "交易筆數分布",
                    "total_years": len(years)
                }
                
            # =====================================================
            # ③ 人口 × 成交量
            # =====================================================
            elif chart_type == "人口 × 成交量（市場是否被壓抑）":
        
                pop_year = pop_df.groupby("民國年")["人口數"].last().reset_index()
                trans_year = re_df.groupby("民國年")["交易筆數"].sum().reset_index()
        
                merged = pd.merge(pop_year, trans_year, on="民國年", how="left").fillna(0)
        
                st.markdown("### 📊 人口與成交量趨勢對比")
                st_echarts({
                    "tooltip": {"trigger": "axis"},
                    "legend": {"data": ["人口數", "成交量"]},
                    "xAxis": {"type": "category", "data": merged["民國年"].astype(str).tolist()},
                    "yAxis": [{"type": "value"}, {"type": "value"}],
                    "series": [
                        {"name": "人口數", "type": "line", "data": merged["人口數"].tolist()},
                        {"name": "成交量", "type": "line", "yAxisIndex": 1, "data": merged["交易筆數"].tolist()}
                    ]
                }, height="400px")
        
                # 計算市場壓抑指數（簡單版）
                pop_change = 0
                trans_change = 0
                suppression_index = 0
                
                if len(merged) > 1:
                    pop_change = ((merged["人口數"].iloc[-1] - merged["人口數"].iloc[0]) / merged["人口數"].iloc[0]) * 100
                    trans_change = ((merged["交易筆數"].iloc[-1] - merged["交易筆數"].iloc[0]) / merged["交易筆數"].iloc[0]) * 100
                    
                    # 簡單壓抑指標：人口成長率 - 交易量成長率
                    suppression_index = pop_change - trans_change if pop_change > 0 else 0
                    
                    # 顯示指標
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("人口成長率", f"{pop_change:+.1f}%")
                    with col2:
                        st.metric("交易量成長率", f"{trans_change:+.1f}%")
                    with col3:
                        st.metric("市場壓抑指標", f"{suppression_index:.1f}%")
                    
                    # 提供解讀
                    if suppression_index > 15:
                        st.error("🚨 高度壓抑市場：人口顯著成長但交易量停滯")
                        st.info("可能原因：高房價、貸款限制、供給不足、政策打壓")
                    elif suppression_index > 5:
                        st.warning("⚠️ 中度壓抑市場：人口成長快於交易量")
                        st.info("可能原因：購買力成長不足、市場觀望氣氛濃厚")
                    elif suppression_index < -15:
                        st.success("🚀 高度活躍市場：交易量成長遠超人口成長")
                        st.info("可能原因：投資需求旺盛、預期心理、政策利多")
                    elif suppression_index < -5:
                        st.info("📈 活躍市場：交易量成長快於人口成長")
                    else:
                        st.success("✅ 平衡市場：人口與交易量同步發展")
        
                # 儲存資料供 Gemini 分析
                analysis_data = {
                    "population_trend": merged.to_dict('records'),
                    "city": city_choice,
                    "district": district_choice,
                    "year_range": year_range,
                    "chart_type": "人口與成交量關係",
                    "pop_change": pop_change,
                    "trans_change": trans_change,
                    "suppression_index": suppression_index
                }
        
            # =====================================================
            # AI 分析按鈕區塊
            # =====================================================
            st.markdown("---")
            st.subheader("🤖 AI 市場趨勢分析")
            
            # 建立唯一的分析鍵值
            analysis_params_key = f"{chart_type}_{city_choice}_{district_choice}_{year_range[0]}_{year_range[1]}"
            
            # 檢查是否需要重新分析
            should_reanalyze = (
                st.session_state.get("market_analysis_key") != analysis_params_key or
                st.session_state.market_analysis_result is None
            )
            
            # 如果有 Gemini Key，顯示分析按鈕
            gemini_key = st.session_state.get("GEMINI_KEY", "")
            
            if gemini_key:
                col1, col2, col3 = st.columns([1, 2, 2])
                
                with col1:
                    if st.button("🚀 啟動 AI 分析", type="primary", use_container_width=True):
                        # 防爆檢查
                        now = time.time()
                        last = st.session_state.get("last_market_gemini_call", 0)
                        
                        if now - last < 30:
                            st.warning("⚠️ Gemini 分析請等待 30 秒後再試")
                            st.stop()
                        
                        st.session_state.last_market_gemini_call = now
                        
                        # 準備專業提示詞
                        prompt = prepare_market_analysis_prompt(chart_type, analysis_data, re_df, pop_df)
                        
                        # 顯示提示詞預覽（可選）
                        with st.expander("📝 查看分析提示詞"):
                            st.text_area("Gemini 將收到的提示詞", prompt, height=300)
                        
                        # 呼叫 Gemini
                        with st.spinner("🧠 AI 分析市場趨勢中..."):
                            try:
                                genai.configure(api_key=gemini_key)
                                model = genai.GenerativeModel("gemini-2.0-flash")
                                
                                resp = model.generate_content(prompt)
                                
                                # 儲存結果
                                st.session_state.market_analysis_result = resp.text
                                st.session_state.market_analysis_key = analysis_params_key
                                
                                st.success("✅ AI 分析完成！")
                                
                            except Exception as e:
                                st.error(f"❌ Gemini API 錯誤: {str(e)}")
                                st.info("請檢查：\n1. API 金鑰是否正確\n2. 配額是否用盡\n3. 網路連線是否正常")
                
                with col2:
                    # 顯示分析狀態
                    if st.session_state.market_analysis_key == analysis_params_key:
                        st.success("✅ 已有分析結果")
                    elif should_reanalyze:
                        st.info("🔄 需要重新分析")
                    else:
                        st.info("👆 點擊按鈕開始分析")
                        
                with col3:
                    # 清除分析結果按鈕
                    if st.button("🗑️ 清除分析結果", type="secondary", use_container_width=True):
                        st.session_state.market_analysis_result = None
                        st.session_state.market_analysis_key = None
                        st.rerun()
            
            else:
                st.warning("請在側邊欄填入 Gemini API 金鑰以使用 AI 分析功能")
            
            # =====================================================
            # 顯示 AI 分析結果
            # =====================================================
            if st.session_state.market_analysis_result and st.session_state.market_analysis_key == analysis_params_key:
                st.markdown("### 📊 AI 分析報告")
                
                # 美化顯示結果
                with st.container():
                    st.markdown("---")
                    st.markdown(st.session_state.market_analysis_result)
                    st.markdown("---")
                
                # 額外提問功能
                st.subheader("💬 深入提問")
                
                col_quest, col_btn = st.columns([3, 1])
                
                with col_quest:
                    user_question = st.text_area(
                        "對分析結果有進一步問題嗎？",
                        placeholder="例如：根據這個趨勢，未來一年的房價會如何變化？投資建議？風險評估？",
                        label_visibility="collapsed"
                    )
                
                with col_btn:
                    ask_disabled = not (user_question and gemini_key)
                    if st.button("🔍 提問", type="secondary", use_container_width=True, disabled=ask_disabled):
                        # 防爆檢查
                        now = time.time()
                        last = st.session_state.get("last_gemini_question", 0)
                        
                        if now - last < 15:
                            st.warning("⚠️ 提問請等待 15 秒後再試")
                            st.stop()
                        
                        st.session_state.last_gemini_question = now
                        
                        with st.spinner("思考中..."):
                            try:
                                genai.configure(api_key=gemini_key)
                                model = genai.GenerativeModel("gemini-2.0-flash")
                                
                                follow_up_prompt = f"""
                                根據先前的市場分析，回答用戶的後續問題。
                                
                                【先前分析摘要】
                                {st.session_state.market_analysis_result[:1000]}...
                                
                                【用戶提問】
                                {user_question}
                                
                                【分析地區與時間】
                                - 地區：{city_choice} - {district_choice}
                                - 時間範圍：{year_range[0]} - {year_range[1]} 年
                                - 圖表類型：{chart_type}
                                
                                【請提供】
                                1. 基於數據的直接回應
                                2. 可能的影響因素（經濟、政策、供需等）
                                3. 實用建議（自住、投資、風險管理等）
                                4. 相關風險提醒
                                
                                回答請保持專業、客觀，避免過度推測。如數據不足請說明限制。
                                """
                                
                                resp = model.generate_content(follow_up_prompt)
                                
                                st.markdown("### 💡 AI 回應")
                                st.write(resp.text)
                                
                            except Exception as e:
                                st.error(f"❌ 提問失敗: {str(e)}")
            
            elif should_reanalyze and gemini_key:
                st.info("👆 點擊上方「啟動 AI 分析」按鈕，獲取專業市場分析報告")
