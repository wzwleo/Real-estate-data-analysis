import streamlit as st
import google.generativeai as genai

def render_ai_chat_search():
    
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
    
    # ====== 顯示現有的聊天記錄 ======
    for chat in st.session_state.chat_history:
        with st.chat_message(chat["role"]):
            st.markdown(chat["content"])
    
    # ====== 使用者輸入（固定在底部） ======
    if prompt := st.chat_input(""):
        # 立即顯示使用者訊息
        with st.chat_message("user"):
            st.markdown(prompt)
        st.session_state.chat_history.append({"role": "user", "content": prompt})
        
        # 呼叫 AI 並顯示回應
        with st.chat_message("assistant"):
            with st.spinner("思考中..."):
                try:
                    response = model.generate_content(prompt)
                    ai_reply = response.text
                except Exception as e:
                    ai_reply = f"❌ API 發生錯誤: {e}"
            
            st.markdown(ai_reply)
        
        st.session_state.chat_history.append({"role": "assistant", "content": ai_reply})
        st.rerun()  # 重新整理畫面
