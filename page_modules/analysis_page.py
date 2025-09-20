import streamlit as st
import pandas as pd

def get_favorites_data():
    """
    取得收藏房產的資料
    """
    if 'favorites' not in st.session_state or not st.session_state.favorites:
        return pd.DataFrame()
    
    all_df = None
    # 優先從 all_properties_df 取得資料
    if 'all_properties_df' in st.session_state and not st.session_state.all_properties_df.empty:
        all_df = st.session_state.all_properties_df
    # 如果沒有 all_properties_df，則從 filtered_df 取得
    elif 'filtered_df' in st.session_state and not st.session_state.filtered_df.empty:
        all_df = st.session_state.filtered_df
    
    if all_df is None or all_df.empty:
        return pd.DataFrame()
    
    fav_ids = st.session_state.favorites
    fav_df = all_df[all_df['編號'].isin(fav_ids)].copy()
    return fav_df


def render_favorites_list(fav_df):
    """
    渲染收藏清單
    """
    st.subheader("⭐ 我的收藏清單")
    
    for idx, (_, row) in enumerate(fav_df.iterrows()):
        with st.container():
            col1, col2 = st.columns([8, 2])
            with col1:
                st.markdown(f"**#{idx+1} 🏠 {row['標題']}**")
                st.write(f"**地址：** {row['地址']} | **屋齡：** {row['屋齡']} | **類型：** {row['類型']}")
                st.write(f"**建坪：** {row['建坪']} | **格局：** {row['格局']} | **樓層：** {row['樓層']}")
                if '車位' in row and pd.notna(row['車位']):
                    st.write(f"**車位：** {row['車位']}")
            with col2:
                st.metric("總價", f"{row['總價(萬)']} 萬")
                if pd.notna(row['建坪']) and row['建坪'] > 0:
                    unit_price = (row['總價(萬)'] * 10000) / row['建坪']
                    st.caption(f"單價: ${unit_price:,.0f}/坪")

                property_id = row['編號']
                if st.button("❌ 移除", key=f"remove_fav_{property_id}"):
                    st.session_state.favorites.remove(property_id)
                    st.rerun()

                property_url = f"https://www.sinyi.com.tw/buy/house/{row['編號']}?breadcrumb=list"
                st.markdown(f'[🔗 物件連結]({property_url})')
            st.markdown("---")


def render_analysis_page():
    """
    渲染分析頁面
    """
    st.title("📊 分析頁面")
    
    if 'favorites' not in st.session_state:
        st.session_state.favorites = set()
    
    col1, col2, col3, col4 = st.columns([1, 1, 1, 1])
    with col4:
        analysis_scope = st.selectbox(
            "選擇分析範圍",
            ["⭐收藏類別", "已售出房產"],
            key="analysis_scope"
        )
    
    # 三個分頁：個別分析、房屋比較、市場趨勢分析
    tab1, tab2, tab3 = st.tabs(["個別分析", "房屋比較", "市場趨勢分析"])
    
    with tab1:
        if analysis_scope == "⭐收藏類別":
            fav_df = get_favorites_data()
            if fav_df.empty and st.session_state.favorites:
                st.warning("⚠️ 找不到收藏房產的詳細資料，請先在搜尋頁面載入房產資料")
                st.info("💡 請先到搜尋頁面進行搜尋，載入房產資料後再回到分析頁面")
            elif not st.session_state.favorites:
                st.info("⭐ 你尚未收藏任何房產")
            else:
                render_favorites_list(fav_df)
        elif analysis_scope == "已售出房產":
            st.info("🚧 已售出房產分析功能開發中...")

    with tab2:
        st.subheader("🏠 房屋比較")
        fav_df = get_favorites_data()
        if fav_df.empty:
            st.info("⭐ 尚未有收藏房產，無法比較")
        else:
            options = fav_df['標題'] + " | " + fav_df['地址']
            col1, col2 = st.columns(2)
            with col1:
                choice_a = st.selectbox("選擇房屋 A", options, key="compare_a")
            with col2:
                choice_b = st.selectbox("選擇房屋 B", options, key="compare_b")
            
            if choice_a and choice_b and choice_a != choice_b:
                house_a = fav_df.iloc[options[options == choice_a].index[0]]
                house_b = fav_df.iloc[options[options == choice_b].index[0]]

                # 建立比較表格
                compare_data = {
                    "項目": ["標題", "地址", "總價(萬)", "建坪", "單價(元/坪)", "格局", "樓層", "屋齡", "類型", "車位"],
                    "房屋 A": [
                        house_a.get("標題", ""),
                        house_a.get("地址", ""),
                        house_a.get("總價(萬)", ""),
                        house_a.get("建坪", ""),
                        f"{(house_a['總價(萬)']*10000/house_a['建坪']):,.0f}" if pd.notna(house_a["建坪"]) and house_a["建坪"]>0 else "—",
                        house_a.get("格局", ""),
                        house_a.get("樓層", ""),
                        house_a.get("屋齡", ""),
                        house_a.get("類型", ""),
                        house_a.get("車位", "")
                    ],
                    "房屋 B": [
                        house_b.get("標題", ""),
                        house_b.get("地址", ""),
                        house_b.get("總價(萬)", ""),
                        house_b.get("建坪", ""),
                        f"{(house_b['總價(萬)']*10000/house_b['建坪']):,.0f}" if pd.notna(house_b["建坪"]) and house_b["建坪"]>0 else "—",
                        house_b.get("格局", ""),
                        house_b.get("樓層", ""),
                        house_b.get("屋齡", ""),
                        house_b.get("類型", ""),
                        house_b.get("車位", "")
                    ]
                }
                compare_df = pd.DataFrame(compare_data)
                st.dataframe(compare_df, use_container_width=True)

            else:
                st.warning("⚠️ 請選擇兩個不同的房屋進行比較")

    with tab3:
        st.subheader("📈 市場趨勢分析")
        st.info("🚧 市場趨勢分析功能開發中...")


def ensure_data_sync():
    """
    確保房產資料在不同模塊間保持同步
    """
    if ('filtered_df' in st.session_state and 
        not st.session_state.filtered_df.empty and
        'all_properties_df' not in st.session_state):
        st.session_state.all_properties_df = st.session_state.filtered_df.copy()
    if 'favorites' not in st.session_state:
        st.session_state.favorites = set()
