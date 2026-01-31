import streamlit as st
import pandas as pd
import google.generativeai as genai
import hnswlib
from sentence_transformers import SentenceTransformer
import os
import numpy as np
import plotly.express as px
import json
import plotly.graph_objects as go
import re

# 名稱對照表
name_map = {
    "Taichung-city_buy_properties.csv": "台中市",
}
reverse_name_map = {v: k for k, v in name_map.items()}

def plot_radar(scores):
    categories = list(scores.keys())
    values = list(scores.values())
    categories.append(categories[0])
    values.append(values[0])
    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(r=values, theta=categories, fill='toself', name='AI 評分'))
    fig.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, 10])),
        showlegend=False,
        title="AI 房屋評分雷達圖"
    )
    return fig

def get_favorites_data():
    if 'favorites' not in st.session_state or not st.session_state.favorites:
        return pd.DataFrame()
    all_df = st.session_state.get('all_properties_df')
    if all_df is None or all_df.empty:
        all_df = st.session_state.get('filtered_df')
    if all_df is None or all_df.empty:
        return pd.DataFrame()
    fav_ids = st.session_state.favorites
    return all_df[all_df['編號'].isin(fav_ids)].copy()

# 注意：這裡將函式名稱改為 render_analysis_page 以配合你的 main_test.py
def render_analysis_page():
    fav_df = get_favorites_data()
    if fav_df.empty:
        st.header("個別分析")
        st.info("⭐ 尚未有收藏房產，無法比較")
        return

    options = fav_df['標題'].tolist()
    col1, col2 = st.columns([2, 1])
    with col1:
        st.header("個別分析")
    with col2:
        choice = st.selectbox("選擇房屋", options, key="analysis_solo")
    
    selected_row = fav_df[fav_df['標題'] == choice].iloc[0]

    st.markdown(f"""
    <div style="border:2px solid #4CAF50; border-radius:10px; padding:10px; background-color:#1f1f1f; text-align:center; color:white;">
        <div style="font-size:40px; font-weight:bold;">{selected_row.get('標題','未提供')}</div>
        <div style="font-size:20px;">📍 {selected_row.get('地址','未提供')}</div>
    </div>
    """, unsafe_allow_html=True)

    # 數據處理與介面顯示 (略，保持你原本的邏輯...)
    # ... (請確保這裡的縮進是 4 個空格) ...
    st.write("已成功載入房屋數據，請點擊下方按鈕進行分析。")
    
    # 這裡放你原本按鈕之後的所有邏輯
    # (為了節省空間，請確保你貼上時整個 def 下方的程式碼都縮進 4 個空格)
