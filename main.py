import streamlit as st
#from (檔案名稱) import (函式名稱)

def main():
    st.set_page_config(layout="wide")

    st.title("🏠AI購屋分析")
    st.sidebar.title("⚙️設置")

    with st.sidebar.expander("🔑Gemini API KEY"):
        api_key_input = st.text_input("請輸入 Gemini API 金鑰", type="password")

if __name__ == "__main__":

    main()














