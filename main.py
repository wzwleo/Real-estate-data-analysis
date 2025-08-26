import streamlit as st
import os
import pandas as pd
import math
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

def display_pagination(df, items_per_page=10):
    """
    處理分頁邏輯並返回當前頁面的資料
    """
    # 初始化頁面狀態
    if 'current_search_page' not in st.session_state:
        st.session_state.current_search_page = 1
    
    total_items = len(df)
    total_pages = math.ceil(total_items / items_per_page) if total_items > 0 else 1
    
    # 確保頁面數在有效範圍內
    if st.session_state.current_search_page > total_pages:
        st.session_state.current_search_page = 1
    
    # 計算當前頁面的資料範圍
    start_idx = (st.session_state.current_search_page - 1) * items_per_page
    end_idx = min(start_idx + items_per_page, total_items)
    
    current_page_data = df.iloc[start_idx:end_idx]
    
    return current_page_data, st.session_state.current_search_page, total_pages, total_items

def main():
    st.set_page_config(layout="wide")

    # 初始化頁面狀態
    if 'current_page' not in st.session_state:
        st.session_state.current_page = 'home'

    # 側邊欄按鈕 - 每個都有唯一的 key
    if st.sidebar.button("🏠 首頁", use_container_width=True, key="home_button"):
        st.session_state.current_page = 'home'
        # 重置搜尋頁面
        if 'current_search_page' in st.session_state:
            del st.session_state.current_search_page

    if st.sidebar.button("🔍 搜尋頁面", use_container_width=True, key="search_button"):
        st.session_state.current_page = 'search'

    if st.sidebar.button("📊 分析頁面", use_container_width=True, key="analysis_button"):
        st.session_state.current_page = 'analysis'
        # 重置搜尋頁面
        if 'current_search_page' in st.session_state:
            del st.session_state.current_search_page

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
            
            housetype = ["大樓", "華廈", "公寓", "套房", "透天", "店面", "辦公", "別墅", "倉庫", "廠房", "土地", "單售車位", "其它"]
            options = get_city_options()
            col1, col2 = st.columns([1, 1])
            with col1:
                # 下拉選單
                selected_label = st.selectbox("請選擇城市：", list(options.keys()))

                
            with col2:
                housetype_change = st.selectbox("請選擇房產類別；", housetype, key="housetype")
                
            # 提交按鈕
            submit = st.form_submit_button("開始篩選")
            
            # 只有按下按鈕才會執行
        if submit:
            # 重置搜尋頁面到第一頁
            st.session_state.current_search_page = 1
            selected_file = options[selected_label]
            file_path = os.path.join("./data", selected_file)
            
            try:
                df = pd.read_csv(file_path)

                # 如果需要篩選房產類型
                df = df[df['類型'] == housetype_change]
                
                # 儲存篩選後的資料到 session state
                st.session_state.filtered_df = df
                st.session_state.search_params = {
                    'city': selected_label,
                    'housetype': housetype_change
                }
                
            except Exception as e:
                st.error(f"讀取 CSV 發生錯誤: {e}")

        # 顯示搜尋結果和分頁
        if 'filtered_df' in st.session_state and not st.session_state.filtered_df.empty:
            df = st.session_state.filtered_df
            search_params = st.session_state.search_params
            
            # 使用分頁功能
            current_page_data, current_page, total_pages, total_items = display_pagination(df, items_per_page=10)
            
            # 顯示結果統計
            st.subheader(f"🏠 {search_params['city']}房產列表")
            st.write(f"📊 共找到 **{total_items}** 筆資料，第 **{current_page}** 頁，共 **{total_pages}** 頁")
            
            # 顯示當前頁面的資料
            for idx, (index, row) in enumerate(current_page_data.iterrows()):
                with st.container():
                    # 計算全域索引
                    global_idx = (current_page - 1) * 10 + idx + 1
                    
                    # 標題與指標
                    col1, col2, col3, col4 = st.columns([7, 1, 1, 2])
                    with col1:
                        st.subheader(f"#{global_idx} 🏠 {row['標題']}")
                        st.write(f"**地址：** {row['地址']} | **屋齡：** {row['屋齡']} | **類型：** {row['類型']}")
                        st.write(f"**建坪：** {row['建坪']} | **主+陽：** {row['主+陽']} | **格局：** {row['格局']} | **樓層：** {row['樓層']}")
                    with col4:
                        st.metric("Price(NT$)", f"${int(row['總價(萬)'] * 10):,}K")

                    
                    col1, col2, col3, col4, col5, col6, col7 = st.columns([1, 1, 1, 1, 1, 1, 1])
                    with col7:
                        property_url = f"https://www.sinyi.com.tw/buy/house/{row['編號']}?breadcrumb=list"
                        st.markdown(
                            f'<a href="{property_url}" target="_blank">'
                            f'<button style="padding:5px 10px;">Property Link</button></a>',
                            unsafe_allow_html=True
                        )

                    st.markdown("---")
            
            # 分頁控制按鈕
            if total_pages > 1:
                col1, col2, col3, col4, col5 = st.columns([1, 1, 2, 1, 1])
                
                with col1:
                    if st.button("⏮️ 第一頁", disabled=(current_page == 1)):
                        st.session_state.current_search_page = 1
                        st.rerun()
                
                with col2:
                    if st.button("⏪ 上一頁", disabled=(current_page == 1)):
                        st.session_state.current_search_page = max(1, current_page - 1)
                        st.rerun()
                
                with col3:
                    # 頁面跳轉選擇器
                    new_page = st.selectbox(
                        "",
                        range(1, total_pages + 1),
                        index=current_page - 1,
                        key="page_selector"
                    )
                    if new_page != current_page:
                        st.session_state.current_search_page = new_page
                        st.rerun()
                
                with col4:
                    if st.button("下一頁 ⏩", disabled=(current_page == total_pages)):
                        st.session_state.current_search_page = min(total_pages, current_page + 1)
                        st.rerun()
                
                with col5:
                    if st.button("最後一頁 ⏭️", disabled=(current_page == total_pages)):
                        st.session_state.current_search_page = total_pages
                        st.rerun()
                
                # 顯示頁面資訊
                st.info(f"📄 第 {current_page} 頁，共 {total_pages} 頁 | 顯示第 {(current_page-1)*10+1} - {min(current_page*10, total_items)} 筆資料")

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
