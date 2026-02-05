import streamlit as st
import google.generativeai as genai
import json
import pandas as pd
import re

def render_ai_chat_search():
    st.header("🤖 AI 房市顧問")
    st.write("你可以輸入自然語言查詢條件，AI 會幫你搜尋適合的物件。")
    
    # ====== GEMINI_KEY 驗證 ======
    gemini_key = st.session_state.get("GEMINI_KEY", "")
    if not gemini_key:
        st.error("❌ 右側 gemini API Key 未設定或有誤")
        st.stop()
    
    # ====== 初始化 Gemini API ======
    try:
        genai.configure(api_key=gemini_key)
        model = genai.GenerativeModel('gemini-3-flash-preview')
    except Exception as e:
        st.error(f"❌ Gemini 初始化錯誤：{e}")
        st.stop()
    
    # ====== 初始化 session_state ======
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
    
    if "ai_search_count" not in st.session_state:
        st.session_state.ai_search_count = 0
    
    if 'favorites' not in st.session_state:
        st.session_state.favorites = set()
    
    # ====== 顯示現有的聊天記錄 ======
    for chat in st.session_state.chat_history:
        with st.chat_message(chat["role"]):
            st.markdown(chat["content"])
    
    # ====== 顯示最新的 AI 解析結果（如果有的話）======
    if 'ai_latest_filters' in st.session_state and 'ai_latest_reply' in st.session_state:
        with st.chat_message("assistant"):
            st.success("✅ 已解析您的需求：")
            st.json(st.session_state.ai_latest_filters)
            
            # 除錯：顯示原始 AI 回應
            with st.expander("🔍 查看 AI 原始回應（除錯用）"):
                st.code(st.session_state.ai_latest_reply, language="json")
            
            # 顯示結果統計
            if 'ai_search_result_text' in st.session_state:
                st.markdown(st.session_state.ai_search_result_text)
            
            # 除錯資訊
            if 'ai_debug_info' in st.session_state:
                debug_info = st.session_state.ai_debug_info
                with st.expander("📊 除錯資訊 - 點擊查看詳細篩選過程"):
                    st.write(f"**使用的 CSV 檔案：** `{debug_info['csv_file']}`")
                    st.write(f"**原始資料筆數：** {debug_info['original_count']}")
                    st.write(f"**篩選後筆數：** {debug_info['filtered_count']}")
                    
                    st.write("---")
                    st.write("**篩選步驟（每一步的資料變化）：**")
                    if debug_info['filter_steps']:
                        for step in debug_info['filter_steps']:
                            st.write(f"- {step}")
                    else:
                        st.write("未套用任何篩選條件")
                    
                    st.write("---")
                    st.write("**解析出的篩選條件：**")
                    st.json(debug_info['filters'])
                    
                    st.write("---")
                    st.write("**資料欄位：**")
                    st.code(", ".join(debug_info['columns']))
                    
                    st.write("---")
                    st.write("**前 5 筆原始資料範例：**")
                    st.dataframe(debug_info['sample_data'])
                    
                    if debug_info['filtered_count'] > 0 and 'filtered_sample' in debug_info:
                        st.write("---")
                        st.write("**前 5 筆篩選結果：**")
                        st.dataframe(debug_info['filtered_sample'])
    
    # ====== 使用者輸入 ======
    if prompt := st.chat_input("請輸入查詢條件，例如：『台中市西屯區 2000 萬內 3房2廳2衛 5樓以上』"):
        # 清除之前的解析結果
        if 'ai_latest_filters' in st.session_state:
            del st.session_state.ai_latest_filters
        if 'ai_latest_reply' in st.session_state:
            del st.session_state.ai_latest_reply
        if 'ai_debug_info' in st.session_state:
            del st.session_state.ai_debug_info
        if 'ai_search_result_text' in st.session_state:
            del st.session_state.ai_search_result_text
        
        # 立即顯示使用者訊息
        with st.chat_message("user"):
            st.markdown(prompt)
        st.session_state.chat_history.append({"role": "user", "content": prompt})
        
        with st.spinner("AI 正在分析您的查詢，並篩選資料中..."):
            # 呼叫 AI 解析查詢
            result_text = ""
            try:
                system_prompt = """
你是一個房產搜尋助手。請根據使用者的自然語言查詢，提取出搜尋條件。

請以 JSON 格式回傳，格式如下：
{
    "city": "台北市 或 台中市",
    "district": "行政區名稱(例如: 西屯區、大安區)",
    "budget_min": 最低預算(萬),
    "budget_max": 最高預算(萬),
    "age_min": 最小屋齡,
    "age_max": 最大屋齡,
    "area_min": 最小建坪,
    "area_max": 最大建坪,
    "floor_min": 最低樓層,
    "floor_max": 最高樓層,
    "rooms": 房間數,
    "living_rooms": 廳數,
    "bathrooms": 衛數,
    "study_rooms": 室數(書房/儲藏室),
    "housetype": "華廈/公寓/大樓/套房/透天/店面/辦公/別墅/倉庫/廠房/土地/單售車位/其他",
    "car_grip": "需要/不要/不限",
}

注意：
- 只回傳 JSON，不要有其他文字
- "district" 欄位：請精確提取使用者提到的行政區。如果使用者說「西屯」請回傳「西屯區」。
- 如果使用者沒提到某個條件，該欄位則可以省略
- 預算單位是「萬」
- 如果使用者提到「上下」、「左右」、「大約」，請自動計算一個合理的範圍。
- 預算範例：若說「1800萬左右」，請回傳 "budget_min": 1750, "budget_max": 1850。
- 如果使用者只說「1800萬以內」或「低於1800萬」，則 "budget_min" 可省略，只設 "budget_max": 1800。
- 坪數與屋齡同理，若有「左右」字眼，請給出範圍。
- **格局解析：**
  - 如果使用者說「3房2廳2衛1室」，請提取：
    - "rooms": 3
    - "living_rooms": 2
    - "bathrooms": 2
    - "study_rooms": 1
  - 如果使用者說「3房」或「3房以上」，只設定 "rooms": 3
  - 如果使用者說「2房2廳」，請設定 "rooms": 2, "living_rooms": 2
  - 「室」通常指書房或儲藏室，但不是必要條件
- **樓層處理：**
  - 如果使用者說「5樓以上」或「高樓層」，請設定 "floor_min": 5
  - 如果使用者說「10樓以下」或「低樓層」，請設定 "floor_max": 10
  - 如果使用者說「3-8樓」，請設定 "floor_min": 3, "floor_max": 8
  - 如果使用者說「不要1樓」或「避開1樓」，請設定 "floor_min": 2
  - 高樓層通常指5樓以上，低樓層通常指3樓以下
- 城市只能是「台中市」
"""
                
                full_prompt = f"{system_prompt}\n\n使用者查詢：{prompt}"
                response = model.generate_content(full_prompt)
                ai_reply = response.text.strip()
                
                # 清理回應
                if ai_reply.startswith("```json"):
                    ai_reply = ai_reply.replace("```json", "").replace("```", "").strip()
                
                # 解析 JSON
                filters = json.loads(ai_reply)
                
                # 儲存 AI 回應到 session_state
                st.session_state.ai_latest_filters = filters
                st.session_state.ai_latest_reply = ai_reply
                
                # 執行搜尋
                city = filters.get("city", "台中市")
                city_file_map = {
                    "台中市": "Taichung-city_buy_properties.csv"
                }
                
                csv_file = city_file_map.get(city)
                if not csv_file:
                    result_text = "❌ 不支援的城市"
                else:
                    # 載入資料
                    df = pd.read_csv(f"./Data/{csv_file}")
                    
                    # ====== 新增：格局欄位解析 ======
                    def parse_layout(layout_str):
                        """
                        解析格局字串，例如：
                        - '3房2廳2衛' -> (3, 2, 2, 0)
                        - '3房2廳2衛1室' -> (3, 2, 2, 1)
                        - '2房2廳1衛' -> (2, 2, 1, 0)
                        """
                        if pd.isna(layout_str) or not isinstance(layout_str, str):
                            return None, None, None, None
                        
                        rooms = re.search(r'(\d+)房', layout_str)
                        living = re.search(r'(\d+)廳', layout_str)
                        bath = re.search(r'(\d+)衛', layout_str)
                        study = re.search(r'(\d+)室', layout_str)
                        
                        return (
                            int(rooms.group(1)) if rooms else None,
                            int(living.group(1)) if living else None,
                            int(bath.group(1)) if bath else None,
                            int(study.group(1)) if study else None
                        )
                    
                    if '格局' in df.columns:
                        df[['房間數', '廳數', '衛數', '室數']] = df['格局'].apply(
                            lambda x: pd.Series(parse_layout(x))
                        )
                    # ================================
                    
                    # 行政區預處理
                    def quick_parse_district(addr):
                        if pd.isna(addr) or not isinstance(addr, str): return ""
                        # 簡單邏輯：找「市」或「縣」之後的三個字（例如：台中市西屯區 -> 西屯區）
                        import re
                        match = re.search(r'[市縣](.+?[區鄉鎮市])', addr)
                        return match.group(1) if match else ""
                        
                    if '地址' in df.columns:
                        df['行政區'] = df['地址'].apply(quick_parse_district)
                    
                    # ====== 樓層預處理 ======
                    def parse_floor(floor_str):
                        """
                        從樓層字串中提取實際樓層數字
                        例如：'2樓/12樓' -> 2, '10樓/20樓' -> 10
                        """
                        if pd.isna(floor_str) or not isinstance(floor_str, str):
                            return None
                        
                        # 使用正規表達式提取第一個數字（所在樓層）
                        match = re.search(r'^(\d+)樓', floor_str)
                        if match:
                            return int(match.group(1))
                        return None
                    
                    if '樓層' in df.columns:
                        df['實際樓層'] = df['樓層'].apply(parse_floor)
                    # ================================
                    
                    original_count = len(df)
                    
                    # 過濾資料（內嵌函式）
                    filtered_df = df.copy()
                    
                    # ====== 強制轉型：確保數字欄位真的是數字 ======
                    num_cols = {
                        '總價(萬)': 'budget',
                        '屋齡': 'age',
                        '建坪': 'area',
                        '房間數': 'rooms',
                        '廳數': 'living_rooms',
                        '衛數': 'bathrooms',
                        '室數': 'study_rooms',
                        '實際樓層': 'floor'
                    }
                    
                    for col in num_cols.keys():
                        if col in filtered_df.columns:
                            # 1. 轉成字串 2. 移除逗號 3. 轉成數字 (無法轉換的會變成 NaN)
                            filtered_df[col] = pd.to_numeric(
                                filtered_df[col].astype(str).str.replace(',', ''), 
                                errors='coerce'
                            )
                    
                    # 順手補一個：把 NaN 的地方填入 0，避免比大小時又噴錯（樓層和室數除外）
                    fill_dict = {k: 0 for k in num_cols.keys() if k not in ['實際樓層', '室數']}
                    filtered_df = filtered_df.fillna(fill_dict)
                    # ============================================
                    
                    filter_steps = []  # 記錄每個篩選步驟
                    
                    try:
                        # 行政區篩選邏輯 (修正版：支援複選)
                        if filters.get('district') and filters['district'] != "不限":
                            if '行政區' in filtered_df.columns:
                                before_count = len(filtered_df)
                                
                                # 1. 統一分隔符號，把 頓號、全型逗號 都換成 半型逗號
                                raw_districts = filters['district'].replace('、', ',').replace('，', ',')
                                
                                # 2. 拆分成清單，例如 ["西屯區", "北屯區"]
                                dist_list = [d.strip() for d in raw_districts.split(',') if d.strip()]
                                
                                # 3. 建立正規表達式的「或」型式，例如 "西屯區|北屯區"
                                search_pattern = '|'.join(dist_list)
                                
                                # 4. 執行篩選
                                filtered_df = filtered_df[
                                    filtered_df['行政區'].astype(str).str.contains(search_pattern, na=False)
                                ]
                                
                                after_count = len(filtered_df)
                                filter_steps.append(f"行政區({raw_districts}): {before_count} → {after_count}")
                        
                        # 房屋類型篩選
                        if filters.get('housetype') and filters['housetype'] != "不限":
                            if '類型' in filtered_df.columns:
                                before_count = len(filtered_df)
                                filtered_df = filtered_df[
                                    filtered_df['類型'].astype(str).str.contains(filters['housetype'], case=False, na=False)
                                ]
                                after_count = len(filtered_df)
                                filter_steps.append(f"類型={filters['housetype']}: {before_count} → {after_count}")
                        
                        # 預算下限
                        if filters.get('budget_min', 0) > 0 and '總價(萬)' in filtered_df.columns:
                            before_count = len(filtered_df)
                            filtered_df = filtered_df[filtered_df['總價(萬)'] >= filters['budget_min']]
                            after_count = len(filtered_df)
                            filter_steps.append(f"預算>={filters['budget_min']}萬: {before_count} → {after_count}")
                        
                        # 預算上限
                        if filters.get('budget_max', 1000000) < 1000000 and '總價(萬)' in filtered_df.columns:
                            before_count = len(filtered_df)
                            filtered_df = filtered_df[filtered_df['總價(萬)'] <= filters['budget_max']]
                            after_count = len(filtered_df)
                            filter_steps.append(f"預算<={filters['budget_max']}萬: {before_count} → {after_count}")
                        
                        # 屋齡下限
                        if filters.get('age_min', 0) > 0 and '屋齡' in filtered_df.columns:
                            before_count = len(filtered_df)
                            filtered_df = filtered_df[filtered_df['屋齡'] >= filters['age_min']]
                            after_count = len(filtered_df)
                            filter_steps.append(f"屋齡>={filters['age_min']}年: {before_count} → {after_count}")
                        
                        # 屋齡上限
                        if filters.get('age_max', 100) < 100 and '屋齡' in filtered_df.columns:
                            before_count = len(filtered_df)
                            filtered_df = filtered_df[filtered_df['屋齡'] <= filters['age_max']]
                            after_count = len(filtered_df)
                            filter_steps.append(f"屋齡<={filters['age_max']}年: {before_count} → {after_count}")
                        
                        # 建坪下限
                        if filters.get('area_min', 0) > 0 and '建坪' in filtered_df.columns:
                            before_count = len(filtered_df)
                            filtered_df = filtered_df[filtered_df['建坪'] >= filters['area_min']]
                            after_count = len(filtered_df)
                            filter_steps.append(f"建坪>={filters['area_min']}: {before_count} → {after_count}")
                        
                        # 建坪上限
                        if filters.get('area_max', 1000) < 1000 and '建坪' in filtered_df.columns:
                            before_count = len(filtered_df)
                            filtered_df = filtered_df[filtered_df['建坪'] <= filters['area_max']]
                            after_count = len(filtered_df)
                            filter_steps.append(f"建坪<={filters['area_max']}: {before_count} → {after_count}")
                        
                        # ====== 樓層篩選 ======
                        # 樓層下限
                        if filters.get('floor_min', 0) > 0 and '實際樓層' in filtered_df.columns:
                            before_count = len(filtered_df)
                            # 只篩選有效樓層資料
                            filtered_df = filtered_df[
                                (filtered_df['實際樓層'].notna()) & 
                                (filtered_df['實際樓層'] >= filters['floor_min'])
                            ]
                            after_count = len(filtered_df)
                            filter_steps.append(f"樓層>={filters['floor_min']}樓: {before_count} → {after_count}")
                        
                        # 樓層上限
                        if filters.get('floor_max', 0) > 0 and '實際樓層' in filtered_df.columns:
                            before_count = len(filtered_df)
                            # 只篩選有效樓層資料
                            filtered_df = filtered_df[
                                (filtered_df['實際樓層'].notna()) & 
                                (filtered_df['實際樓層'] <= filters['floor_max'])
                            ]
                            after_count = len(filtered_df)
                            filter_steps.append(f"樓層<={filters['floor_max']}樓: {before_count} → {after_count}")
                        # ============================
                        
                        # ====== 格局篩選（使用解析後的欄位）======
                        # 房間數篩選
                        if filters.get('rooms', 0) > 0 and '房間數' in filtered_df.columns:
                            before_count = len(filtered_df)
                            filtered_df = filtered_df[
                                (filtered_df['房間數'].notna()) & 
                                (filtered_df['房間數'] >= filters['rooms'])
                            ]
                            after_count = len(filtered_df)
                            filter_steps.append(f"房間數>={filters['rooms']}: {before_count} → {after_count}")
                        
                        # 廳數篩選
                        if filters.get('living_rooms', 0) > 0 and '廳數' in filtered_df.columns:
                            before_count = len(filtered_df)
                            filtered_df = filtered_df[
                                (filtered_df['廳數'].notna()) & 
                                (filtered_df['廳數'] >= filters['living_rooms'])
                            ]
                            after_count = len(filtered_df)
                            filter_steps.append(f"廳數>={filters['living_rooms']}: {before_count} → {after_count}")
                        
                        # 衛數篩選
                        if filters.get('bathrooms', 0) > 0 and '衛數' in filtered_df.columns:
                            before_count = len(filtered_df)
                            filtered_df = filtered_df[
                                (filtered_df['衛數'].notna()) & 
                                (filtered_df['衛數'] >= filters['bathrooms'])
                            ]
                            after_count = len(filtered_df)
                            filter_steps.append(f"衛數>={filters['bathrooms']}: {before_count} → {after_count}")
                        
                        # 室數篩選（書房/儲藏室 - 選用）
                        if filters.get('study_rooms', 0) > 0 and '室數' in filtered_df.columns:
                            before_count = len(filtered_df)
                            filtered_df = filtered_df[
                                (filtered_df['室數'].notna()) & 
                                (filtered_df['室數'] >= filters['study_rooms'])
                            ]
                            after_count = len(filtered_df)
                            filter_steps.append(f"室數>={filters['study_rooms']}: {before_count} → {after_count}")
                        # =========================================
                        
                        # 車位篩選
                        if 'car_grip' in filters and '車位' in filtered_df.columns:
                            before_count = len(filtered_df)
                            if filters['car_grip'] == "需要":
                                filtered_df = filtered_df[
                                    (filtered_df['車位'].notna()) & 
                                    (filtered_df['車位'] != "無車位") & 
                                    (filtered_df['車位'] != 0)
                                ]
                            elif filters['car_grip'] == "不要":
                                filtered_df = filtered_df[
                                    (filtered_df['車位'].isna()) | 
                                    (filtered_df['車位'] == "無車位") | 
                                    (filtered_df['車位'] == 0)
                                ]
                            after_count = len(filtered_df)
                            filter_steps.append(f"車位={filters['car_grip']}: {before_count} → {after_count}")
                            
                    except Exception as e:
                        result_text = f"❌ 篩選過程中發生錯誤: {e}"
                    
                    if not result_text.startswith("❌"):
                        # 每次新搜尋時更新計數器
                        st.session_state.ai_search_count += 1
                        
                        # 儲存到 session_state
                        st.session_state.ai_filtered_df = filtered_df
                        st.session_state.ai_search_city = city
                        st.session_state.ai_current_page = 1
                        
                        # 顯示結果數量
                        result_text = f"🔍 找到 **{len(filtered_df)}** 筆符合條件的物件"
                        st.session_state.ai_search_result_text = result_text
                        
                        # 儲存除錯資訊到 session_state
                        st.session_state.ai_debug_info = {
                            'csv_file': csv_file,
                            'original_count': original_count,
                            'filtered_count': len(filtered_df),
                            'filter_steps': filter_steps,
                            'filters': filters,
                            'columns': df.columns.tolist(),
                            'sample_data': df.head(5),
                            'filtered_sample': filtered_df.head(5) if len(filtered_df) > 0 else None
                        }
                
            except json.JSONDecodeError:
                result_text = "❌ AI 回應格式錯誤，請重新嘗試\n\n原始回應：\n" + ai_reply
            except Exception as e:
                result_text = f"❌ 發生錯誤: {e}"
                import traceback
                result_text += f"\n\n詳細錯誤：\n{traceback.format_exc()}"
            
            # 儲存 assistant 回應到聊天記錄
            st.session_state.chat_history.append({"role": "assistant", "content": result_text})
            st.rerun()
    
    # ====== 顯示搜尋結果 ======
    if 'ai_filtered_df' in st.session_state and not st.session_state.ai_filtered_df.empty:
        st.markdown("---")
        df = st.session_state.ai_filtered_df
        
        # 分頁處理
        items_per_page = 10
        total_items = len(df)
        total_pages = (total_items + items_per_page - 1) // items_per_page
        current_page = st.session_state.get('ai_current_page', 1)
        current_page = max(1, min(current_page, total_pages))
        
        start_idx = (current_page - 1) * items_per_page
        end_idx = min(start_idx + items_per_page, total_items)
        current_page_data = df.iloc[start_idx:end_idx]
        
        st.subheader(f"🏠 {st.session_state.ai_search_city}房產列表")
        
        # 顯示物件卡片
        search_count = st.session_state.ai_search_count
        for idx, (index, row) in enumerate(current_page_data.iterrows()):
            with st.container():
                global_idx = (current_page - 1) * 10 + idx + 1
                
                col1, col2, col3, col4 = st.columns([7, 1, 1, 2])
                with col1:
                    display_age = "預售" if row['屋齡'] == 0 else f"{row['屋齡']}年"
                    st.subheader(f"#{global_idx} 🏠 {row['標題']}")
                    st.write(f"**地址：** {row['地址']} | **屋齡：** {display_age} | **類型：** {row['類型']}")
                    st.write(f"**建坪：** {row['建坪']} | **主+陽：** {row['主+陽']} | **格局：** {row['格局']} | **樓層：** {row['樓層']}")
                    if '車位' in row and pd.notna(row['車位']):
                        st.write(f"**車位：** {row['車位']}")
                with col4:
                    st.metric("Price(NT$)", f"${int(row['總價(萬)'] * 10):,}K")
                    if pd.notna(row['建坪']) and row['建坪'] > 0:
                        unit_price = (row['總價(萬)'] * 10000) / row['建坪']
                        st.caption(f"單價: ${unit_price:,.0f}/坪")
                
                col1, col2, col3, col4, col5, col6, col7 = st.columns([1, 1, 1, 1, 1, 1, 1])
                with col1:
                    property_id = row['編號']
                    is_fav = property_id in st.session_state.favorites
                    unique_key = f"ai_fav_{property_id}"
                    if st.button("✅ 已收藏" if is_fav else "⭐ 收藏", key=unique_key):
                        if is_fav:
                            st.session_state.favorites.remove(property_id)
                        else:
                            st.session_state.favorites.add(property_id)
                        st.rerun()
                
                with col7:
                    property_url = f"https://www.sinyi.com.tw/buy/house/{row['編號']}?breadcrumb=list"
                    st.markdown(
                        f'<a href="{property_url}" target="_blank">'
                        f'<button style="padding:5px 10px;">Property Link</button></a>',
                        unsafe_allow_html=True
                    )
                
                st.markdown("---")
        
        # 分頁控制
        if total_pages > 1:
            col1, col2, col3, col4, col5 = st.columns([1, 1, 2, 1, 1])
            
            with col1:
                if st.button("⏮️ 第一頁", disabled=(current_page == 1), key="ai_first"):
                    st.session_state.ai_current_page = 1
                    st.rerun()
            
            with col2:
                if st.button("⏪ 上一頁", disabled=(current_page == 1), key="ai_prev"):
                    st.session_state.ai_current_page = max(1, current_page - 1)
                    st.rerun()
            
            with col3:
                new_page = st.selectbox(
                    "選擇頁面",
                    options=range(1, total_pages + 1),
                    index=current_page - 1,
                    key=f"ai_page_select_{current_page}"
                )
                if new_page != current_page:
                    st.session_state.ai_current_page = new_page
                    st.rerun()
            
            with col4:
                if st.button("下一頁 ⏩", disabled=(current_page == total_pages), key="ai_next"):
                    st.session_state.ai_current_page = current_page + 1
                    st.rerun()
            
            with col5:
                if st.button("最後一頁 ⏭️", disabled=(current_page == total_pages), key="ai_last"):
                    st.session_state.ai_current_page = total_pages
                    st.rerun()
            
            st.info(f"📄 第 {current_page} 頁，共 {total_pages} 頁 | 顯示第 {start_idx+1} - {end_idx} 筆資料")
