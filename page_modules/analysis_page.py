import streamlit as st
import pandas as pd

def render_analysis_page():
    st.title("📊 分析頁面")
    
    if 'favorites' not in st.session_state:
        st.session_state.favorites = set()
        
    col1, col2, col3, col4 = st.columns([1, 1, 1, 1])
    with col4:
        analysis_scope = st.selectbox(
            "",
            ["⭐收藏類別", "已售出房產"],
            key="analysis_scope"
        )
    st.markdown("---")
    
    # 取得資料
    if analysis_scope == "⭐收藏類別":
        if not st.session_state.favorites:
            st.info("⭐ 你尚未收藏任何房產")
            return

        # 假設總資料存在 st.session_state.all_properties_df
        all_df = st.session_state.all_properties_df
        fav_ids = st.session_state.favorites
        fav_df = all_df[all_df['編號'].isin(fav_ids)]

        st.subheader("⭐ 我的收藏清單")
        
        # 顯示收藏清單
        for idx, row in fav_df.iterrows():
            st.markdown(f"**#{idx+1} {row['標題']}**")
            st.write(f"地址：{row['地址']} | 屋齡：{row['屋齡']} | 類型：{row['類型']}")
            st.write(f"總價：{row['總價(萬)']} 萬 | 建坪：{row['建坪']} | 格局：{row['格局']} | 樓層：{row['樓層']}")
            if '車位' in row and pd.notna(row['車位']):
                st.write(f"車位：{row['車位']}")
            property_url = f"https://www.sinyi.com.tw/buy/house/{row['編號']}?breadcrumb=list"
            st.markdown(f'[🔗 物件連結]({property_url})')
            st.markdown("---")

