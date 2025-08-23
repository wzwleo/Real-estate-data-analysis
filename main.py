import streamlit as st
from Analysis import User_Analysis
#from (檔案名稱) import (函式名稱)

def main():
    st.set_page_config(layout="wide")
    
    st.title("🏠AI購屋分析")
    st.sidebar.title("⚙️設置")

    st.sidebar.button("首頁", use_container_width=True)
        
    with st.sidebar.expander("🔑Gemini API KEY"):
        api_key_input = st.text_input("請輸入 Gemini API 金鑰", type="password")
    with st.sidebar.expander("其他功能一"):
        st.write("施工中...")
    with st.sidebar.expander("其他功能二"):
        st.write("施工中...")

    with st.form("property_requirements"):
    st.subheader("📍 Location & Budget")
    
    col1, col2 = st.columns(2)
    with col1:
        city = st.text_input("City", value="New York City")
    with col2:
        min_price = st.number_input("Minimum Price ($)", value=500000)
    
    # 可以添加提交按鈕或者設置為自動提交
    submit = st.form_submit_button("Update Search")

if __name__ == "__main__":

    main()



























