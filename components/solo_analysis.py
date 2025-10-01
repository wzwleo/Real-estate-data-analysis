import streamlit as st
import pandas as pd

def get_favorites_data():
    """取得收藏房產的資料"""
    if 'favorites' not in st.session_state or not st.session_state.favorites:
        return pd.DataFrame()
    
    all_df = None
    if 'all_properties_df' in st.session_state and not st.session_state.all_properties_df.empty:
        all_df = st.session_state.all_properties_df
    elif 'filtered_df' in st.session_state and not st.session_state.filtered_df.empty:
        all_df = st.session_state.filtered_df
    
    if all_df is None or all_df.empty:
        return pd.DataFrame()
    
    fav_ids = st.session_state.favorites
    fav_df = all_df[all_df['編號'].isin(fav_ids)].copy()
    return fav_df

def tab1_module():
    fav_df = get_favorites_data()
    if fav_df.empty:
            st.header("個別分析")
            st.info("⭐ 尚未有收藏房產，無法比較")
    else:
        options = fav_df['標題']
        col1, col2 = st.columns([2, 1])
        with col1:
            st.header("個別分析")
        with col2:
            choice = st.selectbox("選擇房屋", options, key="analysis_solo")
        # 篩選出選中的房子
        selected_row = fav_df[fav_df['標題'] == choice].iloc[0]

        # 顯示標題
        st.subheader(selected_row['標題'])
        st.write("📍 地址：", selected_row.get("地址", "未提供"))
        
        st.markdown(f"""
        <div style="
            border:2px solid #4CAF50;
            border-radius:10px;
            padding:10px;
            margin:5px 0;
            background-color:#1f1f1f;
            font-size: 25px;
            display: flex;
            gap: 20px;         /* 每個資訊之間的間距 */
            align-items: center; /* 垂直置中對齊 */
        ">
            <div>📍 地址：{selected_row.get('地址','未提供')}</div>
            <div>💰 總價：{selected_row.get('總價(萬)','未提供')}</div>
            <div>🏠 坪數：{selected_row.get('建物坪數','未提供')}</div>
        </div>
        """, unsafe_allow_html=True)



