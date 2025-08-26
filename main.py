import streamlit as st
import os
#from (檔案名稱) import (函式名稱)

def get_city_options(data_dir="./data"):
    # 讀取 CSV 檔
    files = [f for f in os.listdir(data_dir) if f.endswith(".csv")]
    # 中文對照表
    name_map = {
        "Taichung-city_buy_properties.csv": "台中市",
    }
    # 自動 fallback 顯示英文檔名（去掉 -city_buy_properties.csv）
    options = {name_map.get(f, f.replace("-city_buy_properties.csv", "")): f for f in files}
    return options

def main():
    st.set_page_config(layout="wide")

    # 初始化頁面狀態
    if 'current_page' not in st.session_state:
        st.session_state.current_page = 'home'

    # 側邊欄按鈕 - 每個都有唯一的 key
    if st.sidebar.button("🏠 首頁", use_container_width=True, key="home_button"):
        st.session_state.current_page = 'home'

    if st.sidebar.button("🔍 搜尋頁面", use_container_width=True, key="search_button"):
        st.session_state.current_page = 'search'

    if st.sidebar.button("📊 分析頁面", use_container_width=True, key="analysis_button"):
        st.session_state.current_page = 'analysis'
    # 頁面內容
    if st.session_state.current_page == 'home':
        st.title("🏠AI購屋分析")
        st.write("👋歡迎來到房地產分析系統")
        st.write("以下是使用說明：")

        col1, col2 = st.columns(2)

        with col1:
            # 左上表單
            with st.form("search"):
                st.subheader("🔍 搜尋頁面")
                st.write("第一步：阿對對對 就是這樣 嗯嗯嗯 沒錯沒錯")
                search_bt = st.form_submit_button("開始")
                if search_bt:
                    st.session_state.current_page = 'search'

            # 左下表單
            with st.form("form2"):
                st.subheader("表單 2")
                submit2 = st.form_submit_button("提交")
                if submit2:
                    st.write("施工中...")

        with col2:
            # 右上表單
            with st.form("analysis"):
                st.subheader("📊 分析頁面")
                st.write("第二步：阿對對對 就是這樣 嗯嗯嗯 沒錯沒錯")
                analysis_bt = st.form_submit_button("開始")
                if analysis_bt:
                    st.session_state.current_page = 'analysis'

            # 右下表單
            with st.form("form4"):
                st.subheader("表單 4")
                submit4 = st.form_submit_button("提交")
                if submit4:
                    st.write("施工中...")

    elif st.session_state.current_page == 'search':
        st.title("🔍 搜尋頁面")
        # -------- 搜尋頁面 --------
        with st.form("property_requirements"):
            st.subheader("📍 房產篩選條件")
            
            options = get_city_options()
            # 下拉選單
            selected_label = st.selectbox("請選擇城市：", list(options.keys()))
            
            # 提交按鈕
            submit = st.form_submit_button("開始篩選")
            
            # 只有按下按鈕才會執行
            if submit:
                selected_file = options[selected_label]
                st.write("✅ 你選擇的城市：", selected_label)
                st.write("📂 對應到的檔案：", selected_file)

    elif st.session_state.current_page == 'analysis':
        st.title("📊 分析頁面")
        st.write("房產分析和數據")


    st.sidebar.title("⚙️設置")

    with st.sidebar.expander("🔑Gemini API KEY"):
        api_key_input = st.text_input("請輸入 Gemini API 金鑰", type="password")
        if st.button("確定", key="api_confirm_button"):
            st.success("✅API KEY已設定")
    with st.sidebar.expander("🗺️MAP API KEY"):
        st.write("施工中...")
    with st.sidebar.expander("🔄更新資料"):
        st.write("施工中...")

    if st.sidebar.button("其他功能一", use_container_width=True, key="updata_button"):
        st.sidebar.write("施工中...")

    if st.sidebar.button("💬智能小幫手", use_container_width=True, key="line_button"):
        st.sidebar.write("施工中...")

if __name__ == "__main__":

    main()

'''
streamlit run "C:/專題_購屋/main.py"
'''
