import streamlit as st
import pandas as pd
from utils import display_pagination

def display_pagination(df, items_per_page=10):
    if 'current_search_page' not in st.session_state:
        st.session_state.current_search_page = 1

    current_page = st.session_state.current_search_page
    total_items = len(df)
    total_pages = (total_items + items_per_page - 1) // items_per_page
    current_page = max(1, min(current_page, total_pages))
    st.session_state.current_search_page = current_page

    start_idx = (current_page - 1) * items_per_page
    end_idx = min(start_idx + items_per_page, total_items)
    current_page_data = df.iloc[start_idx:end_idx]

    return current_page_data, current_page, total_pages, total_items


def render_property_list():
    if 'favorites' not in st.session_state:
        st.session_state.favorites = set()

    if 'current_search_page' not in st.session_state:
        st.session_state.current_search_page = 1

    if 'filtered_df' not in st.session_state or st.session_state.filtered_df.empty:
        return

    df = st.session_state.filtered_df.copy()
    df = df.drop_duplicates(subset=['編號'], keep='first')

    search_params = st.session_state.search_params

    # ── 標題列 + 排序選單 ──────────────────────────────
    sort_options = {
        "(預設) 價錢由低到高":  ("總價(萬)", True),
        "價錢由高到低":         ("總價(萬)", False),
        "屋齡由低到高":         ("屋齡",    True),
        "屋齡由高到低":         ("屋齡",    False),
        "建坪由低到高":         ("建坪",    True),
        "建坪由高到低":         ("建坪",    False),
    }

    title_col, sort_col = st.columns([3, 2])
    with title_col:
        st.subheader(f"🏠 {search_params['city']}房產列表")
    with sort_col:
        selected_sort = st.selectbox(
            "排序方式",
            options=list(sort_options.keys()),
            index=0,
            key="sort_selector",
            label_visibility="collapsed"   # 隱藏標籤，讓版面更簡潔
        )

    # 套用排序
    sort_col_name, ascending = sort_options[selected_sort]
    if sort_col_name in df.columns:
        df = df.sort_values(by=sort_col_name, ascending=ascending, na_position='last')
    # ────────────────────────────────────────────────────

    current_page_data, current_page, total_pages, total_items = display_pagination(df, items_per_page=10)

    for idx, (index, row) in enumerate(current_page_data.iterrows()):
        render_property_card(row, current_page, idx)

    render_pagination_controls(current_page, total_pages, total_items)


def render_property_card(row, current_page, idx):
    with st.container():
        global_idx = (current_page - 1) * 10 + idx + 1

        col1, col2, col3, col4 = st.columns([7, 1, 1, 2])
        with col1:
            display_age = "預售" if row['屋齡'] == 0 else f"{row['屋齡']}年"
            st.subheader(f"#{global_idx} 🏠 {row['標題']}")
            st.write(f"**地址：** {row['地址']} | **屋齡：** {display_age} | **類型：** {row['類型']}")
            st.write(f"**建坪：** {row['建坪']} | **主+陽：** {row['主+陽']} | **格局：** {row['格局']} | **樓層：** {row['樓層']}")
            if '車位' in row and pd.notna(row['車位']):
                st.write(f"**車位：** {row['車位']}")
        with col4:
            st.metric("Price(NT$)", f"${int(row['總價(萬)'] * 10):,}K")
            if pd.notna(row['建坪']) and row['建坪'] > 0:
                unit_price = (row['總價(萬)'] * 10000) / row['建坪']
                st.caption(f"單價: ${unit_price:,.0f}/坪")

        col1, col2, col3, col4, col5, col6, col7 = st.columns([1, 1, 1, 1, 1, 1, 1])
        with col1:
            property_id = row['編號']
            is_fav = property_id in st.session_state.favorites
            if st.button("✅ 已收藏" if is_fav else "⭐ 收藏", key=f"filter_fav_{property_id}"):
                if is_fav:
                    st.session_state.favorites.remove(property_id)
                else:
                    st.session_state.favorites.add(property_id)
                st.rerun()
        with col7:
            property_url = f"https://www.sinyi.com.tw/buy/house/{row['編號']}?breadcrumb=list"
            st.markdown(
                f'<a href="{property_url}" target="_blank">'
                f'<button style="padding:5px 10px;">Property Link</button></a>',
                unsafe_allow_html=True
            )

        st.markdown("---")


def render_pagination_controls(current_page, total_pages, total_items):
    if total_pages <= 1:
        return

    col1, col2, col3, col4, col5 = st.columns([1, 1, 2, 1, 1])

    with col1:
        if st.button("⏮️ 第一頁", disabled=(current_page == 1), key="first_page"):
            st.session_state.current_search_page = 1
            st.rerun()
    with col2:
        if st.button("⏪ 上一頁", disabled=(current_page == 1), key="prev_page"):
            st.session_state.current_search_page = max(1, current_page - 1)
            st.rerun()
    with col3:
        new_page = st.selectbox(
            "選擇頁面",
            options=range(1, total_pages + 1),
            index=current_page - 1,
            key=f"page_selector_{current_page}"
        )
        if new_page != current_page:
            st.session_state.current_search_page = new_page
            st.rerun()
    with col4:
        if st.button("下一頁 ⏩", disabled=(current_page == total_pages), key="next_page"):
            st.session_state.current_search_page = current_page + 1
            st.rerun()
    with col5:
        if st.button("最後一頁 ⏭️", disabled=(current_page == total_pages), key="last_page"):
            st.session_state.current_search_page = total_pages
            st.rerun()

    st.info(f"📄 第 {current_page} 頁，共 {total_pages} 頁 | 顯示第 {(current_page-1)*10+1} - {min(current_page*10, total_items)} 筆資料")
