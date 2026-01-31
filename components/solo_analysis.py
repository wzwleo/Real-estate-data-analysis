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

# 在檔案開頭,name_map 下方加入反向對照表
name_map = {
    "Taichung-city_buy_properties.csv": "台中市",
}
# 建立反向對照表:中文 -> 英文檔名
reverse_name_map = {v: k for k, v in name_map.items()}

def plot_radar(scores):
    categories = list(scores.keys())
    values = list(scores.values())

    # 關閉環線前需要把首點補上（Plotly 要環狀）
    categories.append(categories[0])
    values.append(values[0])

    fig = go.Figure()

    fig.add_trace(go.Scatterpolar(
        r=values,
        theta=categories,
        fill='toself',
        name='AI 評分'
    ))

    fig.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, 10]   # 0～10 分
            )
        ),
        showlegend=False,
        title="AI 房屋評分雷達圖"
    )

    return fig

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
            area_Price_per = f"{int(total_price)/area:,.0f}"
            Actual_space_Price_per = f"{int(total_price)/float(Actual_space):,.0f}" if Actual_space != '未提供' else "未提供"
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
            st.write("\n")
            # 刪除原有的分析按鈕
            analyze_clicked = st.button("開始分析", use_container_width=True, key="solo_analysis_button")
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

            st.write("\n")
            chart_clicked = st.button("可視化圖表分析", use_container_width=True, key="chart_analysis_button")

        gemini_key = st.session_state.get("GEMINI_KEY","")
        if analyze_clicked:
            st.write("hi")
        # -------------------- 保留：圖表分析邏輯 --------------------
        if chart_clicked:
            if not gemini_key:
                st.error("❌ 右側 gemini API Key 有誤")
            else:
                try:
                    genai.configure(api_key=gemini_key)
                    model = genai.GenerativeModel("gemini-2.0-flash")

                    address = selected_row.get('地址')
                    city = address[:3]

                    english_filename = reverse_name_map.get(city)
                    file_path = os.path.join("./Data", english_filename)

                    df = pd.read_csv(file_path)
                    df['區域'] = df['地址'].str.extract(r'市(.+?)區')[0]
                    df = df[df['建坪'] > 0.1].copy()
                    df['地坪單價(萬/坪)'] = df['總價(萬)'] / df['建坪']

                    selected_type = f"{selected_row.get('類型')}"
                    if selected_type:
                        df = df[df['類型'].str.contains(selected_type, na=False)]

                    avg_price = df.groupby('區域', as_index=False)['地坪單價(萬/坪)'].mean()
                    avg_price['區域'] = avg_price['區域'] + '區'

                    fig = px.bar(
                        avg_price,
                        x='區域',
                        y='地坪單價(萬/坪)',
                        color='區域',
                        title=f'{city}平均建坪單價柱狀圖'
                    )
                    fig.update_traces(textposition='outside')
                    fig.update_layout(
                        xaxis_title='行政區',
                        yaxis_title='平均建坪單價 (萬/坪)',
                        title_x=0.5,
                        showlegend=False,
                        template='plotly_white'
                    )
                    st.plotly_chart(fig, use_container_width=True)

                    # 圖表下方的 AI 分析
                    avg_text = "\n".join([f"{row['區域']} 平均地坪單價: {row['地坪單價(萬/坪)']} 萬/坪" 
                                          for _, row in avg_price.iterrows()])
                    
                    target_house_info = f"""
                    地址：{selected_row.get('地址','未提供')}
                    建坪：{area_text}
                    建坪單價：{area_Price_per} 元/坪
                    類型：{selected_row.get('類型','未提供')}
                    格局：{selected_row.get('格局','未提供')}
                    屋齡：{selected_row.get('屋齡','未提供')}
                    """

                    prompt = f"""
                    你是一位台灣不動產市場專家，請針對下列目標房屋的建坪單價和區域平均建坪單價資訊，提供簡短的價格評估：
                    目標房屋：
                    {target_house_info}
                    
                    區域平均建坪單價：
                    {avg_text}
                    
                    請指出目標房價是否高於或低於平均水平，並給予專業分析。
                    """

                    with st.spinner("Gemini 正在分析圖表數據..."):
                        response = model.generate_content(prompt)
                    
                    st.success("✅ 圖表分析完成")
                    st.markdown("### 📊 **Gemini 建坪圖表分析結果**")
                    st.markdown(response.text)

                except Exception as e:
                    st.error(f"❌ 處理過程發生錯誤：{e}")
