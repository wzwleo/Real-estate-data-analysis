import streamlit as st
import google.generativeai as genai
import json
import pandas as pd

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
    
    # ====== 使用者輸入 ======
    if prompt := st.chat_input("請輸入查詢條件，例如：『台北 2000 萬內 3 房』"):
        # 立即顯示使用者訊息
        with st.chat_message("user"):
            st.markdown(prompt)
        st.session_state.chat_history.append({"role": "user", "content": prompt})
        
        # 呼叫 AI 解析查詢
        with st.chat_message("assistant"):
            with st.spinner("正在解析您的需求..."):
                try:
                    system_prompt = """
你是一個房產搜尋助手。請根據使用者的自然語言查詢，提取出搜尋條件。

請以 JSON 格式回傳，格式如下：
{
    "city": "台北市 或 台中市",
    "budget_min": 最低預算(萬),
    "budget_max": 最高預算(萬),
    "rooms": 房間數 或 {"min": 最小房數, "max": 最大房數},
    "living_rooms": 廳數,
    "bathrooms": 衛數,
    "age_min": 最小屋齡,
    "age_max": 最大屋齡,
    "area_min": 最小建坪,
    "area_max": 最大建坪,
    "housetype": "華廈/公寓/電梯大樓/透天厝",
    "car_grip": "需要/不要/不限",
    "floor": 樓層 或 {"min": 最小樓層, "max": 最大樓層}
}

注意：
- 只回傳 JSON，不要有其他文字
- 如果使用者沒提到某個條件，該欄位可以省略
- 預算單位是「萬」
- 城市只能是「台北市」或「台中市」
"""
                    
                    full_prompt = f"{system_prompt}\n\n使用者查詢：{prompt}"
                    response = model.generate_content(full_prompt)
                    ai_reply = response.text.strip()
                    st.markdown("### 🤖 AI 解析結果（原始輸出）")
                    st.code(ai_reply, language="json")
                    
                    # 清理回應
                    if ai_reply.startswith("```json"):
                        ai_reply = ai_reply.replace("```json", "").replace("```", "").strip()
                    
                    # 解析 JSON
                    filters = json.loads(ai_reply)
                    
                    # 顯示解析結果
                    st.success("✅ 已解析您的需求：")
                    st.json(filters)
                    
                    # 執行搜尋
                    city = filters.get("city", "台中市")
                    city_file_map = {
                        "台中市": "Taichung-city_buy_properties.csv",
                        "台北市": "Taipei-city_buy_properties.csv"
                    }
                    
                    csv_file = city_file_map.get(city)
                    if not csv_file:
                        st.error("❌ 不支援的城市")
                        st.stop()
                    
                    # 載入資料
                    df = pd.read_csv(f"./Data/{csv_file}")
                    
                    # 過濾資料（內嵌函式）
                    filtered_df = df.copy()
                    try:
                        if filters.get('housetype') and filters['housetype'] != "不限":
                            if '類型' in filtered_df.columns:
                                filtered_df = filtered_df[
                                    filtered_df['類型'].astype(str).str.contains(filters['housetype'], case=False, na=False)
                                ]
                        if filters.get('budget_min', 0) > 0 and '總價(萬)' in filtered_df.columns:
                            filtered_df = filtered_df[filtered_df['總價(萬)'] >= filters['budget_min']]
                        if filters.get('budget_max', 1000000) < 1000000 and '總價(萬)' in filtered_df.columns:
                            filtered_df = filtered_df[filtered_df['總價(萬)'] <= filters['budget_max']]
                        if filters.get('age_min', 0) > 0 and '屋齡' in filtered_df.columns:
                            filtered_df = filtered_df[filtered_df['屋齡'] >= filters['age_min']]
                        if filters.get('age_max', 100) < 100 and '屋齡' in filtered_df.columns:
                            filtered_df = filtered_df[filtered_df['屋齡'] <= filters['age_max']]
                        if filters.get('area_min', 0) > 0 and '建坪' in filtered_df.columns:
                            filtered_df = filtered_df[filtered_df['建坪'] >= filters['area_min']]
                        if filters.get('area_max', 1000) < 1000 and '建坪' in filtered_df.columns:
                            filtered_df = filtered_df[filtered_df['建坪'] <= filters['area_max']]
                        if 'car_grip' in filters and '車位' in filtered_df.columns:
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
                        if "rooms" in filters:
                            rooms = filters["rooms"]
                            if isinstance(rooms, dict):
                                filtered_df = filtered_df[(filtered_df['房間數'] >= rooms.get("min", 0)) &
                                                          (filtered_df['房間數'] <= rooms.get("max", 100))]
                            else:
                                filtered_df = filtered_df[filtered_df['房間數'] >= rooms]
                        if "living_rooms" in filters:
                            filtered_df = filtered_df[filtered_df['廳數'] >= filters["living_rooms"]]
                        if "bathrooms" in filters:
                            filtered_df = filtered_df[filtered_df['衛數'] >= filters["bathrooms"]]
                    except Exception as e:
                        st.error(f"篩選過程中發生錯誤: {e}")
                    
                    # 每次新搜尋時更新計數器
                    st.session_state.ai_search_count += 1
                    
                    # 儲存到 session_state
                    st.session_state.ai_filtered_df = filtered_df
                    st.session_state.ai_search_city = city
                    st.session_state.ai_current_page = 1
                    
                    # 顯示結果數量
                    result_text = f"🔍 找到 **{len(filtered_df)}** 筆符合條件的物件"
                    st.markdown(result_text)
                    
                except json.JSONDecodeError:
                    result_text = "❌ AI 回應格式錯誤，請重新嘗試"
                    st.error(result_text)
                    st.code(ai_reply)
                except Exception as e:
                    result_text = f"❌ 發生錯誤: {e}"
                    st.error(result_text)
        
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
                    unique_key = f"ai_s{search_count}_p{current_page}_i{idx}_{property_id}"
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
