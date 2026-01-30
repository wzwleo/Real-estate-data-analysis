import streamlit as st
import google.generativeai as genai
import json
import pandas as pd

# 1. 效能優化：快取資料載入
@st.cache_data
def load_data(city_file):
    try:
        return pd.read_csv(f"./Data/{city_file}")
    except Exception as e:
        st.error(f"無法讀取資料檔案: {e}")
        return pd.DataFrame()

def render_ai_chat_search():
    st.header("🤖 AI 房市顧問")
    st.write("你可以輸入自然語言查詢條件，例如：『台中 1500 萬內的三房大樓』")
    
    # ====== API 驗證 ======
    gemini_key = st.session_state.get("GEMINI_KEY", "")
    if not gemini_key:
        st.error("❌ 請先設定 Gemini API Key")
        st.stop()
    
    # ====== 初始化 Gemini (啟用 JSON 模式) ======
    try:
        genai.configure(api_key=gemini_key)
        # 使用 generation_config 強制回傳 JSON
        model = genai.GenerativeModel(
            'gemini-1.5-flash',
            generation_config={"response_mime_type": "application/json"}
        )
    except Exception as e:
        st.error(f"❌ Gemini 初始化錯誤：{e}")
        st.stop()
    
    # ====== 初始化 Session State ======
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
    if "ai_search_count" not in st.session_state:
        st.session_state.ai_search_count = 0
    if 'favorites' not in st.session_state:
        st.session_state.favorites = set()

    # 顯示聊天記錄
    for chat in st.session_state.chat_history:
        with st.chat_message(chat["role"]):
            st.markdown(chat["content"])
    
    # ====== 使用者輸入處理 ======
    if prompt := st.chat_input("請輸入查詢條件..."):
        with st.chat_message("user"):
            st.markdown(prompt)
        st.session_state.chat_history.append({"role": "user", "content": prompt})
        
        with st.chat_message("assistant"):
            with st.spinner("AI 正在分析需求並搜尋物件..."):
                try:
                    system_prompt = """
                    你是一個房產搜尋助手。請從使用者查詢中提取條件並以 JSON 格式回傳。
                    必須包含以下欄位（若無則設為 null）：
                    {
                        "city": "台北市" 或 "台中市",
                        "budget_min": int, "budget_max": int,
                        "rooms": int 或 {"min": int, "max": int},
                        "housetype": "華廈/公寓/電梯大樓/透天厝",
                        "car_grip": "需要/不要/不限",
                        "area_min": int, "age_max": int
                    }
                    預算單位為「萬」。
                    """
                    
                    response = model.generate_content(f"{system_prompt}\n\n使用者查詢：{prompt}")
                    filters = json.loads(response.text)
                    
                    # 顯示解析後的條件（可選）
                    st.caption("🔍 解析條件：")
                    st.json(filters)
                    
                    # 載入與過濾資料
                    city = filters.get("city") or "台中市"
                    city_file_map = {"台中市": "Taichung-city_buy_properties.csv", "台北市": "Taipei-city_buy_properties.csv"}
                    
                    df = load_data(city_file_map.get(city, "Taichung-city_buy_properties.csv"))
                    
                    if not df.empty:
                        filtered_df = df.copy()
                        # --- 動態過濾邏輯 ---
                        if filters.get('housetype'):
                            filtered_df = filtered_df[filtered_df['類型'].str.contains(filters['housetype'], na=False)]
                        
                        if filters.get('budget_max'):
                            filtered_df = filtered_df[filtered_df['總價(萬)'] <= filters['budget_max']]
                        
                        if filters.get('rooms'):
                            r = filters['rooms']
                            if isinstance(r, dict):
                                filtered_df = filtered_df[(filtered_df['房間數'] >= r.get('min', 0)) & (filtered_df['房間數'] <= r.get('max', 99))]
                            else:
                                filtered_df = filtered_df[filtered_df['房間數'] >= r]

                        # 儲存結果到 session
                        st.session_state.ai_filtered_df = filtered_df
                        st.session_state.ai_search_city = city
                        st.session_state.ai_current_page = 1
                        st.session_state.ai_search_count += 1
                        
                        msg = f"🔍 幫您在 **{city}** 找到了 **{len(filtered_df)}** 筆物件！"
                        st.success(msg)
                        st.session_state.chat_history.append({"role": "assistant", "content": msg})
                        st.rerun()

                except Exception as e:
                    st.error(f"搜尋出錯了: {e}")

    # ====== 搜尋結果展示 (分頁邏輯保持不變) ======
    # ... (你原本的分頁與卡片程式碼)
