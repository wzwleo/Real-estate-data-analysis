import streamlit as st
import google.generativeai as genai

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
    
    # ====== 聊天記錄初始化 ======
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
    
    # ====== 使用者輸入（先處理輸入） ======
    if prompt := st.chat_input("請輸入查詢條件，例如：『台北 2000 萬內 3 房』"):
        # 加入使用者訊息到歷史記錄
        st.session_state.chat_history.append({"role": "user", "content": prompt})
        
        try:
            # 呼叫 Gemini AI
            response = model.generate_content(prompt)
            ai_reply = response.text
        except Exception as e:
            ai_reply = f"❌ API 發生錯誤: {e}"
        
        # 加入 AI 回應到歷史記錄
        st.session_state.chat_history.append({"role": "assistant", "content": ai_reply})
    
    # ====== 顯示聊天記錄（在輸入框上方） ======
    for chat in st.session_state.chat_history:
        with st.chat_message(chat["role"]):
            st.markdown(chat["content"])
