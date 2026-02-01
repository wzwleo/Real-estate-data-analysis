import streamlit as st
import pandas as pd
import google.generativeai as genai
import os
import plotly.graph_objects as go
import plotly.express as px
import json
import re

# 在檔案開頭, name_map 下方加入反向對照表
name_map = {
    "Taichung-city_buy_properties.csv": "台中市",
}
# 建立反向對照表: 中文 -> 英文檔名
reverse_name_map = {v: k for k, v in name_map.items()}

def plot_price_scatter(df, target_row):
    """自動過濾同區同類型房型，繪製總價 vs 實際坪數散佈圖"""
    
    # 1️⃣ 先過濾同區同類型
    df['區域'] = df['地址'].str.extract(r'市(.+?)區')[0]
    df['類型'] = df['類型'].str.strip()
    
    target_district = target_row['區域']
    target_type = target_row['類型']
    
    df_filtered = df[(df['區域'] == target_district) & (df['類型'] == target_type)].copy()
    
    # 移除目標房型
    others_df = df_filtered[df_filtered['標題'] != target_row['標題']].copy()
    
    # 2️⃣ 總價顯示格式
    def format_price(x):
        if x >= 10000:
            return f"{x/10000:.1f} 億"
        else:
            return f"{int(x)} 萬"
    
    # 3️⃣ hover info 統一
    def make_hover(df):
        hover_text = []
        for _, row in df.iterrows():
            hover_text.append(
                f"<b>{row['標題']}</b><br>"
                f"地址：{row['地址']}<br>"
                f"樓層：{row['樓層']}<br>"
                f"屋齡：{row['屋齡']} 年<br>"
                f"實際坪數：{row['主+陽']} 坪<br>"
                f"總價：{format_price(row.get('總價(萬)', row.get('總價')))}"
            )
        return hover_text
    
    # 4️⃣ 轉換數值欄位
    target_df = pd.DataFrame([target_row])
    for df_ in [target_df, others_df]:
        df_['總價'] = pd.to_numeric(df_.get('總價(萬)', df_.get('總價')), errors='coerce')
        df_['實際坪數'] = pd.to_numeric(df_.get('主+陽'), errors='coerce')
    
    others_df = others_df.dropna(subset=['總價','實際坪數'])
    
    # 5️⃣ 繪圖底圖
    fig = px.scatter(
        others_df,
        x='實際坪數',
        y='總價',
        render_mode='svg',
        opacity=0.4,
        width=500,
        height=500
    )
    fig.update_traces(hovertemplate=make_hover(others_df))
    
    # 6️⃣ 加入目標房型紅星
    customdata = target_df[['標題','地址','樓層','屋齡']].values.tolist()
    fig.add_scatter(
        x=target_df['實際坪數'],
        y=target_df['總價'],
        mode='markers',
        marker=dict(size=25, color='red', symbol='star', line=dict(width=2,color='DarkSlateGrey')),
        name='目標房型',
        customdata=customdata,
        hovertemplate=make_hover(target_df)[0] + "<extra></extra>"
    )
    
    # 7️⃣ 固定顯示範圍 (2.5 倍)
    x_center = target_df['實際坪數'].iloc[0]
    y_center = target_df['總價'].iloc[0]
    
    fig.update_layout(
        title='市場行情分布：總價 vs 實際坪數',
        xaxis_title='實際坪數 (坪)',
        yaxis_title='總價',
        template='plotly_white',
        xaxis=dict(range=[0, x_center*2.5], showline=True, linewidth=1, linecolor='lightgrey', gridcolor='whitesmoke'),
        yaxis=dict(range=[0, y_center*2.5], showline=True, linewidth=1, linecolor='lightgrey', gridcolor='whitesmoke'),
        width=500,
        height=500,
        margin=dict(l=20,r=20,t=50,b=20),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    
    st.plotly_chart(fig)

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

        st.write("\n")
        
        # 取得總價，並處理格式
        raw_price = selected_row.get('總價(萬)')
        if raw_price is None or raw_price == '' or raw_price == '未提供':
            formatted_price = '未提供'
        else:
            try:
                formatted_price = f"{int(raw_price)*10000:,}"
            except:
                formatted_price = raw_price

        # 先處理建坪文字
        area = selected_row.get('建坪', 1) # 預設1避免除以0
        area_text = f"{area} 坪" if area != '未提供' else area

        # 先處理主+陽文字
        Actual_space = selected_row.get('主+陽', '未提供')
        Actual_space_text = f"{Actual_space} 坪" if Actual_space != '未提供' else Actual_space

        # 計算單價
        try:
            total_price = int(raw_price) * 10000
            area_Price_per = f"{int(total_price/area):,}"
            Actual_space_Price_per = f"{int(total_price/float(Actual_space)):,}" if Actual_space != '未提供' and float(Actual_space) != 0 else "未提供"
        except:
            area_Price_per = "未提供"
            Actual_space_Price_per = "未提供"

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
                <div> 類型：{selected_row.get('類型','未提供')}</div>
                <div> 建坪：{area_text}</div>
                <div> 實際坪數：{Actual_space_text}</div>
                <div> 格局：{selected_row.get('格局','未提供')}</div>
                <div> 樓層：{selected_row.get('樓層','未提供')}</div>
                <div> 屋齡：{selected_row.get('屋齡','未提供')}</div>
                <div> 車位：{selected_row.get('車位','未提供')}</div>
            </div>
            """, unsafe_allow_html=True)
            
        with col2:
            st.markdown(f"""
            <div style="
                border:2px solid #4CAF50;
                border-radius:10px;
                padding:10px;
                background-color:#1f1f1f;
                text-align:center;
                font-size:30px;
                color:white;
                min-height:247px;
                display:flex;
                flex-direction:column;
                justify-content:center;
            ">
                <div>💰 總價：{formatted_price} 元</div>
                <div style="font-size:14px; color:#cccccc; margin-top:5px;">
                    建坪單價：{area_Price_per} 元/坪
                </div>
                <div style="font-size:14px; color:#cccccc; margin-top:5px;">
                    實際單價：{Actual_space_Price_per} 元/坪
                </div>
            </div>
            """, unsafe_allow_html=True)

        gemini_key = st.session_state.get("GEMINI_KEY","")
        
        st.write("\n")
        analyze_clicked = st.button("開始分析", use_container_width=True, key="solo_analysis_button")
        
        if analyze_clicked:
            if not gemini_key:
                st.error("❌ 右側 gemini API Key 有誤")
                st.stop()
            try:
                st.success("✅ 分析完成")
                st.header("🏡 房屋逐項分析說明 ")
                # 使用三引號處理跨行文字
                st.write("""
                我們將針對所選房屋的六大面向逐一分析，包括價格、坪數、屋齡、樓層、格局與地段。
                每項分析都結合市場資料與 AI 評估，提供清楚、可理解的參考資訊。
                """)
                st.markdown("---")
                
                st.subheader("價格 💸")
                col1, col2 = st.columns([1, 1])
                with col1:
                    # 取得所有房產資料作為比較背景
                    compare_base_df = pd.DataFrame()
                    if 'all_properties_df' in st.session_state and not st.session_state.all_properties_df.empty:
                        compare_base_df = st.session_state.all_properties_df
                    elif 'filtered_df' in st.session_state and not st.session_state.filtered_df.empty:
                        compare_base_df = st.session_state.filtered_df
            
                    if not compare_base_df.empty:
                        # 呼叫圖表函式
                        plot_price_scatter(selected_row, compare_base_df)
                    else:
                        st.warning("⚠️ 找不到比較基準資料，無法顯示圖表")
                st.markdown("---")

                
                st.subheader("坪數 📐")
                st.markdown("---")
                
                st.subheader("屋齡 🕰")
                st.markdown("---")
                
                st.subheader("樓層 🏢")
                st.markdown("---")
                
                st.subheader("格局 🛋")
                st.markdown("---")
                
                st.subheader("地段 🗺")
                st.markdown("---")
                
            except Exception as e:
                st.error(f"❌ 分析過程發生錯誤：{e}")
