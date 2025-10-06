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

        # 顯示卡片，標題直排，詳細資訊橫排
        st.markdown(f"""
        <div style="
            border:2px solid #4CAF50;
            border-radius:10px;
            padding:10px;
            background-color:#1f1f1f;
            text-align:center;
            color:white;
        ">
            <div style="font-size:40px; font-weight:bold;">{selected_row.get('標題','未提供')}</div>
            <div style="font-size:20px;">📍 {selected_row.get('地址','未提供')}</div>
        </div>
        """, unsafe_allow_html=True)

        # 取得總價，並處理格式
        raw_price = selected_row.get('總價(萬)')
        if raw_price is None or raw_price == '' or raw_price == '未提供':
            formatted_price = '未提供'
        else:
            try:
                # 轉成數字後加上萬單位後的0，並加逗號
                formatted_price = f"{int(raw_price)*10000:,}"  # 乘 10000，把萬轉成元，並加逗號
            except:
                formatted_price = raw_price
       
        col1, col2 = st.columns([1, 1])
        with col1:
            st.markdown(f"""
            <div style="
                border:2px solid #4CAF50;
                border-radius:10px;
                padding:10px;
                background-color:#1f1f1f;
                text-align:left;
                font-size:20px;
                color:white;
            ">
                <div>💰 總價：{formatted_price} 元</div>
                <div>🏠 坪數：{selected_row.get('主+陽','未提供')}</div>
            </div>
            """, unsafe_allow_html=True)



