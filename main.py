import streamlit as st
#from (檔案名稱) import (函式名稱)

def main():
    st.set_page_config(layout="wide")
    
    st.title("🏠AI購屋分析")
    st.sidebar.title("側邊欄")

    with st.expander("操作區"):
        st.button("按鈕")
        st.text_input("輸入框")

if __name__ == "__main__":

    main()







