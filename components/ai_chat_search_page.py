import streamlit as st

def render_ai_chat_search():
    gemini_key = st.session_state.get("GEMINI_KEY","")
    if not gemini_key:
        st.error("❌ 右側 gemini API Key 有誤")
        st.stop()
    
