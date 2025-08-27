import os
import streamlit as st
import pandas as pd
from modules.data_utils import get_city_options, filter_properties
from modules.pagination import display_pagination

def render_search():
    st.title("🔍 搜尋頁面")
    with st.form("property_requirements"):
        st.subheader("📍 房產篩選條件")
        housetype = ["不限", "大樓", "華廈", "公寓", "套房", "透天", "店面", "辦公", "別墅", "倉庫", "廠房", "土地", "單售車位", "其它"]
        options = get_city_options()
        col1, col2 = st.columns([1, 1])
        with col1:
            selected_label = st.selectbox("請選擇城市：", list(options.keys()))
            housetype_change = st.selectbox("請選擇房產類別；", housetype, key="housetype")
        with col2:
            budget_max = st.number_input("💰預算上限(萬)", min_value=0, max_value=1000000, value=1000000, step=100)
            budget_min = st.number_input("💰預算下限(萬)", min_value=0, max_value=1000000, value=0, step=100)
            if budget_min > budget_max and budget_max > 0:
                st.error("⚠️ 預算下限不能大於上限！")
        # 屋齡、建坪、車位輸入
        col1, col2, col3 = st.columns([1,1,1])
        with col1:
            age_max = st.number_input("屋齡上限", min_value=0, max_value=100, value=100)
            age_min = st.number_input("屋齡下限", min_value=0, max_value=100, value=0)
            if age_min > age_max:
                st.error("⚠️ 屋齡下限不能大於上限！")
        with col2:
            area_max = st.number_input("建坪上限", min_value=0, max_value=1000, value=1000, step=10)
            area_min = st.number_input("建坪下限", min_value=0, max_value=1000, value=0, step=10)
            if area_min > area_max:
                st.error("⚠️ 建坪下限不能大於上限！")
        with col3:
            car_grip = st.selectbox("🅿️車位選擇", ["不限", "需要","不要"], key="car_grip")
        Special_Requests = st.text_area("請輸入您的需求", placeholder="輸入文字...")
        col1, col2, col3, col4, col5 = st.columns([1,1,1,1,1])
        with col3:
            submit = st.form_submit_button("搜尋", use_container_width=True)
    if submit:
        valid_input = True
        if budget_min > budget_max and budget_max > 0:
            st.error("❌ 請修正預算範圍設定")
            valid_input = False
        if age_min > age_max:
            st.error("❌ 請修正屋齡範圍設定")
            valid_input = False
        if area_min > area_max:
            st.error("❌ 請修正建坪範圍設定")
            valid_input = False
        if valid_input:
            st.session_state.current_search_page = 1
            selected_file = options[selected_label]
            file_path = os.path.join("./Data", selected_file)
            try:
                df = pd.read_csv(file_path)
                filters = {
                    'housetype': housetype_change,
                    'budget_min': budget_min,
                    'budget_max': budget_max,
                    'age_min': age_min,
                    'age_max': age_max,
                    'area_min': area_min,
                    'area_max': area_max,
                    'car_grip': car_grip
                }
                filtered_df = filter_properties(df, filters)
                st.session_state.filtered_df = filtered_df
                st.session_state.search_params = {
                    'city': selected_label,
                    'housetype': housetype_change,
                    'budget_range': f"{budget_min}-{budget_max}萬" if budget_max < 1000000 else f"{budget_min}萬以上",
                    'age_range': f"{age_min}-{age_max}年" if age_max < 100 else f"{age_min}年以上",
                    'area_range': f"{area_min}-{area_max}坪" if area_max < 1000 else f"{area_min}坪以上",
                    'car_grip': car_grip,
                    'original_count': len(df),
                    'filtered_count': len(filtered_df)
                }
                if len(filtered_df) == 0:
                    st.warning("😅 沒有找到符合條件的房產")
                else:
                    st.success(f"✅ 從 {len(df)} 筆資料中篩選出 {len(filtered_df)} 筆符合條件的房產")
            except Exception as e:
                st.error(f"❌ 讀取 CSV 發生錯誤: {e}")
    
    # 分頁顯示結果
    if 'filtered_df' in st.session_state and not st.session_state.filtered_df.empty:
        df = st.session_state.filtered_df
        search_params = st.session_state.search_params
        current_page_data, current_page, total_pages, total_items = display_pagination(df, items_per_page=10)
        st.subheader(f"🏠 {search_params['city']}房產列表")
        for idx, (index, row) in enumerate(current_page_data.iterrows()):
            with st.container():
                global_idx = (current_page - 1) * 10 + idx + 1
                col1, col2, col3, col4 = st.columns([7,1,1,2])
                with col1:
                    st.subheader(f"#{global_idx} 🏠 {row['標題']}")    
                    st.write(f"**地址：** {row['地址']} | **屋齡：** {row['屋齡']} | **類型：** {row['類型']}")
                    st.write(f"**建坪：** {row['建坪']} | **主+陽：** {row['主+陽']} | **格局：** {row['格局']} | **樓層：** {row['樓層']}")
                    if '車位' in row and pd.notna(row['車位']):
                        st.write(f"**車位：** {row['車位']}")
                with col4:
                    st.metric("Price(NT$)", f"${int(row['總價(萬)'] * 10):,}K")
                    if pd.notna(row['建坪']) and row['建坪'] > 0:
                        unit_price = (row['總價(萬)'] * 10000) / row['建坪']
                        st.caption(f"單價: ${unit_price:,.0f}/坪")
        # 分頁控制
        if total_pages > 1:
            col1, col2, col3, col4, col5 = st.columns([1,1,2,1,1])
            with col1:
                if st.button("⏮️ 第一頁", disabled=(current_page==1)):
                    st.session_state.current_search_page = 1
                    st.rerun()
            with col2:
                if st.button("⏪ 上一頁", disabled=(current_page==1)):
                    st.session_state.current_search_page = max(1, current_page-1)
                    st.rerun()
            with col3:
                new_page = st.selectbox("", range(1, total_pages+1), index=current_page-1, key="page_selector")
                if new_page != current_page:
                    st.session_state.current_search_page = new_page
                    st.rerun()
            with col4:
                if st.button("下一頁 ⏩", disabled=(current_page==total_pages)):
                    st.session_state.current_search_page = min(total_pages, current_page+1)
                    st.rerun()
            with col5:
                if st.button("最後一頁 ⏭️", disabled=(current_page==total_pages)):
                    st.session_state.current_search_page = total_pages
                    st.rerun()
            st.info(f"📄 第 {current_page} 頁，共 {total_pages} 頁 | 顯示第 {(current_page-1)*10+1}-{min(current_page*10, total_items)} 筆資料")
