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

PLACE_TYPES = {
    "教育": [
        "圖書館", "圖書館",
        "幼兒園", "幼兒園",
        "托兒所", "托兒所",
        "小學", "小學",
        "國中", "國中",
        "高中", "高中",
        "大學", "大學",
        "補習班", "補習班",
        "學校", "學校",
    ],
    "購物": [
        "超市", "超市",
        "便利商店", "便利商店",
        "全聯福利中心", "全聯",
        "家樂福", "家樂福",
        "大潤發", "大潤發",
        "好市多", "好市多",
        "屈臣氏", "屈臣氏",
        "康是美", "康是美",
        "寶雅", "寶雅",
        "藥妝店", "藥妝店",
        "五金行", "五金行",
        "家具行", "家具行",
        "書局", "書局",
        "文具店", "文具店",
        "手機行", "手機行",
        "電腦賣場", "電腦賣場",
        "服飾店", "服飾店",
        "鞋店", "鞋店",
        "眼鏡行", "眼鏡行",
        "百貨公司", "百貨公司",
        "購物中心", "購物中心",
        "市場", "市場",
        "傳統市場", "傳統市場",
        "夜市", "夜市",
        "批發", "批發",
    ],
    "交通運輸": [
        "公車站", "公車站",
        "捷運站", "捷運站",
        "火車站", "火車站",
        "高鐵站", "高鐵站",
        "客運站", "客運站",
        "計程車行", "計程車行",
        "停車場", "停車場",
        "加油站", "加油站",
        "YouBike", "YouBike",
        "機車行", "機車行",
        "汽車維修", "汽車維修",
    ],
    "健康與保健": [
        "醫院", "醫院",
        "診所", "診所",
        "衛生所", "衛生所",
        "藥局", "藥局",
        "牙醫診所", "牙醫",
        "中醫診所", "中醫",
        "西醫診所", "診所",
        "小兒科診所", "小兒科",
        "婦產科診所", "婦產科",
        "眼科診所", "眼科",
        "皮膚科診所", "皮膚科",
        "復健科診所", "復健科",
        "物理治療所", "物理治療",
        "按摩店", "按摩",
        "養生館", "養生館",
        "SPA", "SPA",
        "健身中心", "健身房",
        "健身房", "健身中心",
        "瑜珈教室", "瑜珈",
        "運動中心", "運動中心",
    ],
    "餐飲美食": [
        "餐廳", "餐廳",
        "小吃店", "小吃店",
        "早餐店", "早餐店",
        "咖啡廳", "咖啡廳",
        "星巴克", "星巴克",
        "路易莎咖啡", "路易莎",
        "85度C", "85度C",
        "手搖飲料店", "手搖飲",
        "飲料店", "飲料店",
        "速食店", "速食店",
        "麥當勞", "麥當勞",
        "肯德基", "肯德基",
        "摩斯漢堡", "摩斯漢堡",
        "漢堡王", "漢堡王",
        "披薩店", "披薩",
        "達美樂披薩", "達美樂",
        "拿坡里披薩", "拿坡里",
        "必勝客", "必勝客",
        "火鍋店", "火鍋",
        "燒烤店", "燒烤",
        "牛排館", "牛排館",
        "鐵板燒", "鐵板燒",
        "日本料理", "日本料理",
        "壽司店", "壽司",
        "拉麵店", "拉麵",
        "韓式料理", "韓式料理",
        "泰式料理", "泰式料理",
        "越南料理", "越南料理",
        "美式餐廳", "美式餐廳",
        "義大利麵餐廳", "義大利麵",
        "自助餐", "自助餐",
        "便當店", "便當店",
        "麵店", "麵店",
        "滷味店", "滷味",
        "鹽酥雞", "鹽酥雞",
        "雞排店", "雞排",
        "甜點店", "甜點店",
        "蛋糕店", "蛋糕店",
        "麵包店", "麵包店",
        "冰店", "冰店",
        "豆花店", "豆花",
    ],
    "生活服務": [
        "銀行", "銀行",
        "郵局", "郵局",
        "派出所", "派出所",
        "警察局", "警察局",
        "消防局", "消防局",
        "區公所", "區公所",
        "戶政事務所", "戶政事務所",
        "運動公園", "公園",
        "公園", "公園",
        "兒童公園", "兒童公園",
        "河濱公園", "河濱公園",
        "廟宇", "廟",
        "教堂", "教堂",
        "洗車場", "洗車場",
        "汽車美容", "汽車美容",
        "洗衣店", "洗衣店",
        "影印店", "影印店",
        "電信行", "電信行",
        "中華電信", "中華電信",
        "台灣大哥大", "台灣大哥大",
        "遠傳電信", "遠傳",
        "寵物店", "寵物店",
        "動物醫院", "動物醫院",
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
    """搜尋Google Places（使用中文關鍵字）"""
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
        
        # 關鍵字本身就是中文，直接使用
        results.append((
            "關鍵字",
            keyword,  # 直接使用中文關鍵字
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
    """查詢Google Places關鍵字（簡化版，使用中文關鍵字）"""
    results, seen = [], set()
    
    total_tasks = 0
    for cat in selected_categories:
        if cat in selected_subtypes:
            total_tasks += len(selected_subtypes[cat])
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
            
        for chinese_kw in selected_subtypes[cat]:  # 現在是中文關鍵字
            update_progress(f"查詢 {cat}-{chinese_kw}")
            
            try:
                places = search_text_google_places(lat, lng, api_key, chinese_kw, radius)
                
                for p in places:
                    if p[5] > radius:
                        continue
                    pid = p[6]
                    if pid in seen:
                        continue
                    seen.add(pid)
                    results.append((cat, chinese_kw, p[2], p[3], p[4], p[5], p[6]))

                time.sleep(0.5)
                
            except Exception as e:
                st.warning(f"查詢 {chinese_kw} 時發生錯誤: {str(e)[:50]}")
                continue

    if extra_keyword:
        update_progress(f"額外關鍵字: {extra_keyword}")
        try:
            places = search_text_google_places(lat, lng, api_key, extra_keyword, radius)
            for p in places:
                if p[5] > radius:
                    continue
                pid = p[6]
                if pid in seen:
                    continue
                seen.add(pid)
                results.append(("關鍵字", extra_keyword, p[2], p[3], p[4], p[5], p[6]))
                
            time.sleep(0.3)
        except Exception as e:
            st.warning(f"查詢額外關鍵字時發生錯誤: {str(e)[:50]}")

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
    for category_idx, (category, items) in enumerate(PLACE_TYPES.items()):
        with st.expander(f"📁 {category} ({len(items)//2}種設施)", expanded=False):
            # 主類別選擇框
            select_all_key = f"select_all_{category}_{category_idx}"
            select_all = st.checkbox(f"選擇所有{category}設施", key=select_all_key)
            
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
                            # 確保每個checkbox有唯一的key
                            checkbox_key = f"selector_{category}_{english_keyword}_{i}"
                            if st.checkbox(chinese_name, key=checkbox_key):
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
                # 修復這裡：將英文關鍵字轉回中文名稱
                chinese_names = []
                for english_kw in selected_subtypes[cat]:
                    # 從 ENGLISH_TO_CHINESE 字典獲取中文名稱
                    if english_kw in ENGLISH_TO_CHINESE:
                        chinese_names.append(ENGLISH_TO_CHINESE[english_kw])
                    else:
                        # 如果字典中沒有，嘗試直接查找
                        chinese_names.append(english_kw)
                
                st.markdown(f"**{cat}** ({len(chinese_names)}項):")
                
                # 使用網格顯示，每行3列
                items_per_row = 3
                chinese_items = sorted(chinese_names)
                
                for i in range(0, len(chinese_items), items_per_row):
                    cols = st.columns(items_per_row)
                    for j in range(items_per_row):
                        idx = i + j
                        if idx < len(chinese_items):
                            with cols[j]:
                                st.markdown(f"✓ {chinese_items[idx]}")
    
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
    # Tab2: 房屋比較 - 支援單獨和多個比較
    # ============================
    with tab2:
        st.subheader("🏠 房屋比較（單獨或多個比較）")
        
        # 模式選擇：單獨比較或多個比較
        comparison_mode = st.radio(
            "選擇比較模式",
            ["單獨比較（2個房屋）", "多個比較（2個以上房屋）"],
            horizontal=True,
            key="comparison_mode"
        )
        fav_df = get_favorites_data()
        if fav_df.empty:
            st.info("⭐ 尚未有收藏房產，無法比較")
            st.stop()  # 停止執行後續程式
        
        options = fav_df['標題'] + " | " + fav_df['地址']
        
        if comparison_mode == "單獨比較（2個房屋）":
            # 單獨比較模式
            c1, c2 = st.columns(2)
            with c1:
                choice_a = st.selectbox("選擇房屋 A", options, key="compare_a")
            with c2:
                choice_b = st.selectbox("選擇房屋 B", options, key="compare_b")
            
            selected_houses = [choice_a, choice_b] if choice_a and choice_b else []
            
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
        
        else:
            # 多個比較模式
            st.subheader("🏘️ 選擇多個房屋進行比較")
            
            # 使用多選下拉框
            selected_houses = st.multiselect(
                "選擇要比較的房屋（至少選擇2個）",
                options,
                default=options[:min(3, len(options))] if len(options) >= 2 else [],
                key="multi_compare"
            )
            
            # 顯示已選房屋的預覽
            if selected_houses:
                st.markdown("### 📋 已選房屋清單")
                
                # 分列顯示
                num_columns = min(3, len(selected_houses))
                cols = st.columns(num_columns)
                
                for idx, house_option in enumerate(selected_houses):
                    with cols[idx % num_columns]:
                        house_info = fav_df[(fav_df['標題'] + " | " + fav_df['地址']) == house_option].iloc[0]
                        st.markdown(f"""
                        <div style="border:1px solid #ddd; padding:10px; border-radius:5px; margin-bottom:10px;">
                        <strong>房屋 {chr(65+idx)}</strong><br>
                        📍 {house_info['地址'][:30]}...<br>
                        🏷️ {house_info['標題'][:25]}...
                        </div>
                        """, unsafe_allow_html=True)
                
                st.caption(f"已選擇 {len(selected_houses)} 間房屋進行比較")
            
            if len(selected_houses) < 2:
                st.warning("⚠️ 請至少選擇2個房屋進行比較")
                st.stop()

        # 共通設定
        st.markdown("---")
        st.subheader("⚙️ 比較設定")
        
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
                category_selection[cat] = st.checkbox(f"選擇{cat}", key=f"main_cat_{cat}_{i}")
        
        # 如果選擇了大類別，顯示細分選項
        selected_main_cats = [cat for cat, selected in category_selection.items() if selected]
        
        if selected_main_cats:
            st.markdown("### 選擇細分設施")
            
            for cat_idx, cat in enumerate(selected_main_cats):
                with st.expander(f"📁 {cat} 類別細選", expanded=True):
                    # 全選按鈕
                    select_all = st.checkbox(f"選擇所有{cat}設施", key=f"select_all_{cat}_{cat_idx}")
                    
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
                                        # 確保每個checkbox有唯一的key
                                        checkbox_key = f"tab2_{cat}_{english_keyword}_{row}_{col_idx}"
                                        if st.checkbox(chinese_name, key=checkbox_key):
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
                        
                        # 顯示前幾個項目（修復這裡）
                        chinese_names = []
                        for english_kw in selected_subtypes[cat][:5]:
                            if english_kw in ENGLISH_TO_CHINESE:
                                chinese_names.append(ENGLISH_TO_CHINESE[english_kw])
                            else:
                                chinese_names.append(english_kw)
                        
                        if count <= 5:
                            items_display = "、".join(chinese_names)
                            st.caption(f"✓ {items_display}")
                        else:
                            items_display = "、".join(chinese_names[:3])
                            st.caption(f"✓ {items_display}等{count}種設施")
        
        # 開始比較按鈕
        st.markdown("---")
        col_start, col_clear = st.columns([3, 1])
        
        with col_start:
            if st.button("🚀 開始比較", type="primary", use_container_width=True, key="start_comparison"):
                # 驗證檢查
                if not _get_browser_key():
                    st.error("❌ 請在側邊欄填入 Google Maps **Browser Key**")
                    st.stop()
                if not server_key or not gemini_key:
                    st.error("❌ 請在側邊欄填入 Server Key 與 Gemini Key")
                    st.stop()
                
                # 根據模式進行不同檢查
                if comparison_mode == "單獨比較（2個房屋）":
                    if choice_a == choice_b:
                        st.warning("⚠️ 請選擇兩個不同房屋")
                        st.stop()
                else:
                    if len(selected_houses) < 2:
                        st.warning("⚠️ 請至少選擇2個房屋")
                        st.stop()
                
                if not selected_categories:
                    st.warning("⚠️ 請至少選擇一個生活機能類別")
                    st.stop()

                # 執行比較
                run_comparison_analysis(
                    comparison_mode, 
                    selected_houses, 
                    fav_df, 
                    server_key, 
                    gemini_key, 
                    radius, 
                    keyword, 
                    selected_categories, 
                    selected_subtypes
                )
        
        with col_clear:
            if st.button("🗑️ 清除結果", type="secondary", use_container_width=True, key="clear_results"):
                # 清除比較相關的 session state
                keys_to_clear = ['gemini_result', 'gemini_key', 'places_data', 'houses_data']
                for key in keys_to_clear:
                    if key in st.session_state:
                        del st.session_state[key]
                st.rerun()

    # ============================
    # Tab3: 市場趨勢分析（整合人口資料）
    # ============================
    with tab3:
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
            city_choice = st.selectbox("選擇縣市", cities, key="city_choice")
        
            if city_choice != "全台":
                district_choice = st.selectbox(
                    "選擇行政區",
                    ["全部"] + sorted(
                        combined_df[combined_df["縣市"] == city_choice]["行政區"].unique()
                    ),
                    key="district_choice"
                )
            else:
                district_choice = "全部"
        
            year_min = int(min(combined_df["民國年"].min(), pop_long["民國年"].min()))
            year_max = int(max(combined_df["民國年"].max(), pop_long["民國年"].max()))
        
            year_range = st.slider(
                "選擇分析年份",
                min_value=year_min,
                max_value=year_max,
                value=(year_min, year_max),
                key="year_range"
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
                if st.button("🚀 啟動 AI 分析", type="primary", use_container_width=True, key="start_market_analysis"):
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
                        st.text_area("Gemini 將收到的提示詞", prompt, height=300, key="prompt_preview")
                    
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
                if st.button("🗑️ 清除分析結果", type="secondary", use_container_width=True, key="clear_analysis"):
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
                    label_visibility="collapsed",
                    key="user_question"
                )
            
            with col_btn:
                ask_disabled = not (user_question and gemini_key)
                if st.button("🔍 提問", type="secondary", use_container_width=True, disabled=ask_disabled, key="ask_question"):
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



# ============================
# 新增：執行比較分析的函數
# ============================
def run_comparison_analysis(
    comparison_mode, 
    selected_houses, 
    fav_df, 
    server_key, 
    gemini_key, 
    radius, 
    keyword, 
    selected_categories, 
    selected_subtypes
):
    """執行房屋比較分析的核心函數"""
    
    # 取得房屋資料
    houses_data = {}
    geocode_results = {}
    
    # 地址解析
    with st.spinner("📍 解析房屋地址中..."):
        for idx, house_option in enumerate(selected_houses):
            house_info = fav_df[(fav_df['標題'] + " | " + fav_df['地址']) == house_option].iloc[0]
            house_name = f"房屋 {chr(65+idx)}"
            
            lat, lng = geocode_address(house_info["地址"], server_key)
            if lat is None or lng is None:
                st.error(f"❌ {house_name} 地址解析失敗")
                return
            
            houses_data[house_name] = {
                "name": house_name,
                "title": house_info['標題'],
                "address": house_info['地址'],
                "lat": lat,
                "lng": lng,
                "original_name": house_info['標題']
            }
            geocode_results[house_name] = (lat, lng)
    
    # 查詢每個房屋的周邊設施
    places_data = {}
    
    for house_name, house_info in houses_data.items():
        with st.spinner(f"🔍 查詢 {house_name} 周邊設施 (半徑: {radius}公尺)..."):
            lat, lng = house_info["lat"], house_info["lng"]
            
            places = query_google_places_keyword(
                lat, lng, server_key, selected_categories, selected_subtypes,
                radius, extra_keyword=keyword
            )
            
            # 檢查缺失設施
            messages = check_places_found(places, selected_categories, selected_subtypes, keyword)
            if messages:
                for msg in messages:
                    st.warning(f"{house_name}: {msg}")
            
            places_data[house_name] = places
    
    # 顯示比較標題
    st.markdown("## 📊 比較結果")
    
    # 統計分析
    st.markdown("---")
    st.subheader("📈 設施統計比較")
    
    # 計算各房屋的設施數量
    facility_counts = {}
    category_counts = {}
    
    for house_name, places in places_data.items():
        total_count = len(places)
        facility_counts[house_name] = total_count
        
        # 計算各類別數量
        cat_counts = {}
        for cat, kw, name, lat, lng, dist, pid in places:
            cat_counts[cat] = cat_counts.get(cat, 0) + 1
        category_counts[house_name] = cat_counts
    
    # 顯示總體統計
    num_houses = len(houses_data)
    stat_cols = st.columns(min(num_houses, 5))
    
    max_facilities = max(facility_counts.values()) if facility_counts else 0
    
    for idx, house_name in enumerate(houses_data.keys()):
        with stat_cols[idx % len(stat_cols)]:
            count = facility_counts.get(house_name, 0)
            house_title = houses_data[house_name]["title"][:20]
            
            # 計算排名
            if max_facilities > 0:
                percentage = (count / max_facilities) * 100 if max_facilities > 0 else 0
            else:
                percentage = 0
            
            st.metric(
                f"🏠 {house_name}",
                f"{count} 個設施",
                f"排名: {sorted(facility_counts.values(), reverse=True).index(count) + 1}/{num_houses}"
            )
            
            if places_data[house_name]:
                nearest = min([p[5] for p in places_data[house_name]])
                st.caption(f"最近設施: {nearest}公尺")
            
            st.caption(f"{house_title}...")
    
    # 如果有超過2個房屋，顯示排名圖表
    if num_houses > 2:
        st.markdown("### 📊 設施數量排名")
        
        # 準備排名資料
        rank_data = sorted(
            [(name, count) for name, count in facility_counts.items()],
            key=lambda x: x[1],
            reverse=True
        )
        
        chart_data = {
            "xAxis": {
                "type": "category",
                "data": [item[0] for item in rank_data]
            },
            "yAxis": {"type": "value"},
            "series": [{
                "type": "bar",
                "data": [item[1] for item in rank_data],
                "itemStyle": {
                    "color": {
                        "type": "linear",
                        "x": 0, "y": 0, "x2": 0, "y2": 1,
                        "colorStops": [
                            {"offset": 0, "color": "#1E90FF"},
                            {"offset": 1, "color": "#87CEFA"}
                        ]
                    }
                }
            }],
            "tooltip": {"trigger": "axis"}
        }
        
        st_echarts(chart_data, height="300px")
    
    # 各類別詳細比較
    st.markdown("### 🏪 各類別設施數量比較")
    
    # 收集所有類別
    all_categories = set()
    for counts in category_counts.values():
        all_categories.update(counts.keys())
    
    if all_categories:
        # 建立比較表格
        comparison_rows = []
        for cat in sorted(all_categories):
            row = {"類別": cat}
            for house_name in houses_data.keys():
                row[house_name] = category_counts[house_name].get(cat, 0)
            comparison_rows.append(row)
        
        comp_df = pd.DataFrame(comparison_rows)
        
        # 顯示表格
        st.dataframe(
            comp_df,
            use_container_width=True,
            hide_index=True
        )
        
        # 顯示類別比較圖表
        if num_houses <= 5:  # 避免圖表太複雜
            chart_data = {
                "xAxis": {
                    "type": "category",
                    "data": comp_df['類別'].tolist()
                },
                "yAxis": {"type": "value"},
                "series": [
                    {
                        "name": house_name,
                        "type": "bar",
                        "data": comp_df[house_name].tolist(),
                        "itemStyle": {"color": f"hsl({idx * 60}, 70%, 50%)"}
                    }
                    for idx, house_name in enumerate(houses_data.keys())
                ],
                "tooltip": {"trigger": "axis"},
                "legend": {"data": list(houses_data.keys())}
            }
            
            st_echarts(chart_data, height="400px")
    
    # 顯示地圖比較
    st.markdown("---")
    st.subheader("🗺️ 地圖比較")
    
    # 根據房屋數量決定地圖顯示方式
    if num_houses <= 3:
        # 並排顯示地圖
        map_cols = st.columns(num_houses)
        for idx, (house_name, house_info) in enumerate(houses_data.items()):
            with map_cols[idx]:
                st.markdown(f"### {house_name}")
                render_map(
                    house_info["lat"], 
                    house_info["lng"], 
                    places_data[house_name], 
                    radius, 
                    title=house_name
                )
                
                # 顯示最近的幾個設施
                if places_data[house_name]:
                    st.markdown("**最近的 3 個設施:**")
                    for i, (cat, kw, name, lat, lng, dist, pid) in enumerate(places_data[house_name][:3]):
                        st.caption(f"{i+1}. {cat}-{kw}: {name} ({dist}公尺)")
    else:
        # 使用選項卡顯示地圖
        map_tabs = st.tabs([f"{house_name}" for house_name in houses_data.keys()])
        
        for idx, (house_name, house_info) in enumerate(houses_data.items()):
            with map_tabs[idx]:
                render_map(
                    house_info["lat"], 
                    house_info["lng"], 
                    places_data[house_name], 
                    radius, 
                    title=house_name
                )
                
                # 顯示最近的幾個設施
                if places_data[house_name]:
                    st.markdown("**最近的 5 個設施:**")
                    for i, (cat, kw, name, lat, lng, dist, pid) in enumerate(places_data[house_name][:5]):
                        st.caption(f"{i+1}. {cat}-{kw}: {name} ({dist}公尺)")
    
    # ============================
    # Gemini AI 分析
    # ============================
    st.markdown("---")
    st.subheader("🤖 AI 智能分析")
    
    # 建立唯一 key
    analysis_key = f"{','.join(selected_houses)}__{keyword}__{','.join(selected_categories)}__{radius}"
    
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
                analysis_text = prepare_multi_comparison_prompt(
                    houses_data, 
                    places_data, 
                    facility_counts, 
                    category_counts,
                    selected_categories,
                    radius,
                    keyword,
                    comparison_mode
                )
                
                # 顯示提示詞預覽
                with st.expander("📝 查看 AI 分析提示詞"):
                    st.text_area("送給 Gemini 的提示詞", analysis_text, height=300)
                
                # 呼叫 Gemini
                resp = model.generate_content(analysis_text)
                
                # 儲存結果
                st.session_state.gemini_result = resp.text
                st.session_state.gemini_key = analysis_key
                st.session_state.places_data = places_data
                st.session_state.houses_data = houses_data
                
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
        比較模式：{comparison_mode}
        
        比較房屋 ({len(houses_data)}間):
        """
        
        for house_name, house_info in houses_data.items():
            report_text += f"""
        - {house_name}: {house_info['title']}
          地址：{house_info['address']}
          """
        
        report_text += f"""
        
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
# 新增：準備多房屋比較的提示詞
# ============================
def prepare_multi_comparison_prompt(
    houses_data, 
    places_data, 
    facility_counts, 
    category_counts,
    selected_categories,
    radius,
    keyword,
    comparison_mode
):
    """準備多房屋比較的 AI 提示詞"""
    
    # 統計摘要
    stats_summary = "統計摘要：\n"
    for house_name, count in facility_counts.items():
        if places_data[house_name]:
            nearest = min([p[5] for p in places_data[house_name]])
            stats_summary += f"- {house_name}：共 {count} 個設施，最近設施 {nearest} 公尺\n"
        else:
            stats_summary += f"- {house_name}：共 0 個設施\n"
    
    # 排名
    ranked_houses = sorted(facility_counts.items(), key=lambda x: x[1], reverse=True)
    ranking_text = "設施數量排名：\n"
    for rank, (house_name, count) in enumerate(ranked_houses, 1):
        ranking_text += f"第{rank}名：{house_name} ({count}個設施)\n"
    
    # 各類別比較
    category_comparison = "各類別設施比較：\n"
    all_categories = set()
    for counts in category_counts.values():
        all_categories.update(counts.keys())
    
    for cat in sorted(all_categories):
        category_comparison += f"\n【{cat}】\n"
        for house_name in houses_data.keys():
            count = category_counts[house_name].get(cat, 0)
            category_comparison += f"- {house_name}: {count} 個設施\n"
    
    # 房屋詳細資訊
    houses_details = "房屋詳細資訊：\n"
    for house_name, house_info in houses_data.items():
        houses_details += f"""
        {house_name}:
        - 標題：{house_info['title']}
        - 地址：{house_info['address']}
        """
    
    # 建構提示詞
    prompt = f"""
    你是一位專業的房地產分析師，請根據以下{len(houses_data)}間房屋的生活機能進行比較分析。
    
    【分析要求】
    1. 請以中文繁體回應
    2. 從「自住」和「投資」兩個角度分析
    3. 考慮各類生活設施的完整性與距離
    4. 提供具體建議與風險提示
    5. 請進行排名比較並說明原因
    
    【搜尋條件】
    - 搜尋半徑：{radius} 公尺
    - 選擇的生活機能類別：{', '.join(selected_categories)}
    - 額外關鍵字：{keyword if keyword else '無'}
    - 比較模式：{comparison_mode}
    
    {houses_details}
    
    【設施統計】
    {stats_summary}
    
    {ranking_text}
    
    {category_comparison}
    
    【請依序分析】
    1. 總體設施豐富度比較與排名
    2. 各類別設施完整性分析（教育、購物、交通、健康、餐飲等）
    3. 生活便利性綜合評估
    4. 對「自住者」的建議（哪間最適合，排名與原因）
    5. 對「投資者」的建議（哪間最有潛力，排名與原因）
    6. 各房屋的優缺點分析
    7. 潛在缺點與風險提醒
    8. 綜合結論與推薦排名
    
    請使用專業但易懂的語言，並提供具體的判斷依據。
    對於每個房屋，請給予1-5星的評分（⭐為單位）。
    """
    
    return prompt
