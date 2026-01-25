import os
import math
import sys
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
# 添加 components 目錄到 Python 路徑
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'components'))

try:
    # 嘗試從 components 目錄導入
    from components.house_comparison import house_comparison_module
    from components.market_trend_analysis import market_trend_analysis_module
except ImportError as e:
    st.error(f"導入模組失敗: {e}")
    # 創建臨時的模組函數
    def house_comparison_module():
        st.error("house_comparison_module 未找到，請檢查 components/house_comparison.py 檔案")
    
    def market_trend_analysis_module():
        st.error("market_trend_analysis_module 未找到，請檢查 components/market_trend_analysis.py 檔案")

# 其他導入...
from page_modules.analysis_page_utils import (
    get_favorites_data, PLACE_TYPES, ENGLISH_TO_CHINESE, CATEGORY_COLORS,
    haversine, _get_server_key, _get_browser_key, geocode_address,
    search_text_google_places, load_population_csv, query_google_places_keyword,
    check_places_found, render_map, format_places, load_real_estate_csv,
    prepare_market_analysis_prompt
)

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
        house_comparison_module()
    # ============================
    # Tab3: 市場趨勢分析
    # ============================
    with tab3:
        market_trend_analysis_module()
