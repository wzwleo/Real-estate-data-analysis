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
    except Exception as e:
        st.error(f"❌ Gemini 初始化錯誤：{e}")
        st.stop()
    
    # ====== 聊天記錄 ======
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
    
    # ====== 顯示聊天記錄 ======
    for chat in st.session_state.chat_history:
        if chat["role"] == "user":
            st.markdown(f"**你:** {chat['content']}")
        else:
            st.markdown(f"**AI:** {chat['content']}")
    
    # ====== 使用者輸入 ======
    user_input = st.text_input("請輸入查詢條件，例如：『台北 2000 萬內 3 房』", key="ai_input")
    
    if st.button("送出"):
        if user_input:
            # 保存使用者訊息
            st.session_state.chat_history.append({"role": "user", "content": user_input})
            try:
                # 使用 generate_text / generate_content 呼叫 Gemini
                resp = genai.generate_text(
                    model="gemini-2.0-flash",
                    prompt=user_input,
                    temperature=0.7,
                    max_output_tokens=1024
                )
                ai_reply = resp.text  # 取回模型回覆
            except Exception as e:
                ai_reply = f"❌ API 發生錯誤: {e}"
            
            # 保存 AI 回答
            st.session_state.chat_history.append({"role": "ai", "content": ai_reply})
