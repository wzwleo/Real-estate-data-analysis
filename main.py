import streamlit as st
from Analysis import User_Analysis
#from (檔案名稱) import (函式名稱)

def main():
    st.set_page_config(layout="wide")
    
    st.title("🏠AI購屋分析")
    st.sidebar.title("⚙️設置")


    st.sidebar.button("首頁")
        
    with st.sidebar.expander("🔑Gemini API KEY"):
        api_key_input = st.text_input("請輸入 Gemini API 金鑰", type="password")
    with st.sidebar.expander("其他功能一"):
        st.write("施工中...")
    with st.sidebar.expander("其他功能二"):
        st.write("施工中...")

if __name__ == "__main__":

    main()























