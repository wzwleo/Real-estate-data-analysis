import streamlit as st
import google.generativeai as genai
import json
import pandas as pd
from utils import filter_properties
from components.property_list import render_property_list

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
        model = genai.GenerativeModel('gemini-2.0-flash')
    except Exception as e:
        st.error(f"❌ Gemini 初始化錯誤：{e}")
        st.stop()
    
    # ====== 初始化 session_state ======
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
    
    if "ai_search_count" not in st.session_state:
        st.session_state.ai_search_count = 0
    
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
                    # 建立 AI 提示詞
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
                    
                    # 清理回應（移除可能的 markdown 標記）
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
                    
                    # 過濾資料
                    filtered_df = filter_properties(df, filters)
                    
                    # 🔥 關鍵：每次新搜尋時更新計數器
                    st.session_state.ai_search_count += 1
                    
                    # 儲存到 session_state
                    st.session_state.filtered_df = filtered_df
                    st.session_state.search_params = {"city": city}
                    st.session_state.current_search_page = 1  # 重置頁碼
                    st.session_state.is_ai_search = True  # 標記為 AI 搜尋
                    
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
    
    # ====== 顯示搜尋結果（使用你的卡片格式） ======
    if st.session_state.get('is_ai_search', False) and \
       'filtered_df' in st.session_state and \
       not st.session_state.filtered_df.empty:
        st.markdown("---")
        render_property_list()
