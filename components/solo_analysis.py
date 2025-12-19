import streamlit as st
import pandas as pd
import google.generativeai as genai
import hnswlib
from sentence_transformers import SentenceTransformer
import os
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import json
import re

# 檔名對照
name_map = {
    "Taichung-city_buy_properties.csv": "台中市",
    "Taipei-city_buy_properties.csv": "台北市"
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
    all_df = st.session_state.get('all_properties_df') or st.session_state.get('filtered_df')
    if all_df is None or all_df.empty:
        return pd.DataFrame()
    fav_ids = st.session_state.favorites
    return all_df[all_df['編號'].isin(fav_ids)].copy()

def read_city_csv(city_name):
    """讀取城市 CSV 並回傳 DataFrame"""
    filename = reverse_name_map.get(city_name)
    if not filename:
        return pd.DataFrame()
    file_path = os.path.join("./Data", filename)
    if not os.path.exists(file_path):
        return pd.DataFrame()
    return pd.read_csv(file_path)

def compute_avg_price(df, house_type=None):
    """計算各區平均建坪單價"""
    df = df[df['建坪'] > 0.1].copy()
    df['地坪單價(萬/坪)'] = df['總價(萬)'] / df['建坪']
    if house_type:
        df = df[df['類型'].str.contains(house_type, na=False)]
    df['區域'] = df['地址'].str.extract(r'市(.+?)區')[0]
    avg_price = df.groupby('區域', as_index=False)['地坪單價(萬/坪)'].mean()
    avg_price['區域'] = avg_price['區域'] + '區'
    return avg_price

def tab1_module():
    fav_df = get_favorites_data()
    if fav_df.empty:
        st.header("個別分析")
        st.info("⭐ 尚未有收藏房產，無法比較")
        return

    options = fav_df['標題']
    col1, col2 = st.columns([2, 1])
    with col1:
        st.header("個別分析")
    with col2:
        choice = st.selectbox("選擇房屋", options, key="analysis_solo")

    selected_row = fav_df[fav_df['標題'] == choice].iloc[0]

    # 卡片顯示
    st.markdown(f"""
    <div style="border:2px solid #4CAF50; border-radius:10px; padding:10px; background-color:#1f1f1f; text-align:center; color:white;">
        <div style="font-size:40px; font-weight:bold;">{selected_row.get('標題','未提供')}</div>
        <div style="font-size:20px;">📍 {selected_row.get('地址','未提供')}</div>
    </div>
    """, unsafe_allow_html=True)

    # 總價與坪單價
    raw_price = selected_row.get('總價(萬)')
    try:
        total_price = int(raw_price) * 10000
    except:
        total_price = 0

    area = selected_row.get('建坪')
    Actual_space = selected_row.get('主+陽')

    area_text = f"{area} 坪" if area else "未提供"
    Actual_space_text = f"{Actual_space} 坪" if Actual_space else "未提供"

    area_Price_per = f"{total_price / area:,.0f}" if area else "無資料"
    Actual_space_Price_per = f"{total_price / Actual_space:,.0f}" if Actual_space else "無資料"

    col1, col2 = st.columns([1, 1])
    with col1:
        st.markdown(f"""
        <div style="border:2px solid #4CAF50; border-radius:10px; padding:10px; background-color:#1f1f1f; text-align:left; font-size:20px; color:white;">
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
        analyze_clicked = st.button("1開始分析", use_container_width=True, key="solo_analysis_button")
    with col2:
        st.markdown(f"""
        <div style="border:2px solid #4CAF50; border-radius:10px; padding:10px; background-color:#1f1f1f; text-align:center; font-size:30px; color:white; min-height:247px; display:flex; flex-direction:column; justify-content:center;">
            <div>💰 總價：{total_price:,} 元</div>
            <div style="font-size:14px; color:#cccccc; margin-top:5px;">建坪單價：{area_Price_per} 元/坪</div>
            <div style="font-size:14px; color:#cccccc; margin-top:5px;">實際單價：{Actual_space_Price_per} 元/坪</div>
        </div>
        """, unsafe_allow_html=True)

        st.write("\n")
        chart_clicked = st.button("可視化圖表分析", use_container_width=True, key="chart_analysis_button")

    gemini_key = st.session_state.get("GEMINI_KEY","")
    ai_score_clean = None

    if analyze_clicked:
        if not gemini_key:
            st.error("❌ 右側 gemini API Key 有誤")
            st.stop()
        try:
            genai.configure(api_key=gemini_key)
            model = genai.GenerativeModel("gemini-2.0-flash")

            city = selected_row['地址'][:3]
            df = read_city_csv(city)
            if df.empty:
                st.error("❌ 無法讀取城市 CSV")
                st.stop()

            house_title = str(selected_row.get('標題','')).strip()
            selected_df_rows = df[df['標題'] == house_title]
            if selected_df_rows.empty:
                st.error("❌ CSV 中找不到此房屋資料")
                st.stop()
            selected_row_csv = selected_df_rows.iloc[0]

            # 轉文字
            embed_model = SentenceTransformer('all-MiniLM-L6-v2')
            def row_to_text(row):
                return f"地址:{row['地址']}, 建坪:{row['建坪']}, 主+陽:{row['主+陽']}, 總價:{row['總價(萬)']}萬, 屋齡:{row['屋齡']}, 類型:{row['類型']}, 格局:{row['格局']}, 樓層:{row['樓層']}, 車位:{row['車位']}"
            texts = df.apply(row_to_text, axis=1).tolist()
            embeddings = np.array(embed_model.encode(texts, show_progress_bar=True), dtype='float32')

            # HNSW index
            dimension = embeddings.shape[1]
            num_elements = len(embeddings)
            index = hnswlib.Index(space='l2', dim=dimension)
            index.init_index(max_elements=num_elements, ef_construction=200, M=16)
            index.add_items(embeddings, np.arange(num_elements))
            index.set_ef(50)

            selected_idx = df[df['標題'] == house_title].index[0]
            query_vec = embeddings[selected_idx:selected_idx+1]
            labels, distances = index.knn_query(query_vec, k=11)

            relevant_data = []
            for idx in labels[0]:
                if idx != selected_idx:
                    relevant_data.append(df.iloc[idx].to_dict())

            selected_text_display = f"{house_title} - {row_to_text(selected_row_csv)}"
            relevant_text = "\n".join([f"{r['標題']} - {row_to_text(r)}" for r in relevant_data])

            prompt_score = f"""
            你是一位台灣不動產估價師，請對下列房屋進行0~10分評分：價格、坪數、屋齡、樓層、格局、地段
            目標房型資料：
            {selected_text_display}
            相似房屋資料：
            {relevant_text}
            以純 JSON 回覆，不要加入任何解釋文字。
            {{ "價格":0,"坪數":0,"屋齡":0,"樓層":0,"格局":0,"地段":0 }}
            """

            with st.spinner("Gemini 正在分析中..."):
                response_score = model.generate_content(prompt_score)
                ai_score_clean = (response_score.text or "").strip()
                st.session_state['current_analysis_result'] = {
                    "house_title": house_title,
                    "result_text": "",  # 可改成完整分析文字
                    "similar_data": relevant_data
                }

        except Exception as e:
            st.error(f"❌ 分析過程發生錯誤：{e}")

    # 顯示雷達圖
    if ai_score_clean:
        try:
            scores = json.loads(ai_score_clean)
            st.plotly_chart(plot_radar(scores), use_container_width=True)
        except Exception as e:
            st.error(f"❌ JSON 解析錯誤: {e}")
            st.text(ai_score_clean)

    # 可視化柱狀圖
    if chart_clicked:
        house_input_text_chart = f"""
        地址：{selected_row.get('地址','未提供')}
        建坪：{area_text}
        建坪單價：{area_Price_per} 元/坪
        類型：{selected_row.get('類型','未提供')}
        格局：{selected_row.get('格局','未提供')}
        樓層：{selected_row.get('樓層','未提供')}
        屋齡：{selected_row.get('屋齡','未提供')}
        車位：{selected_row.get('車位','未提供')}
        """
        try:
            avg_price = compute_avg_price(df, selected_row.get('類型'))
            fig = px.bar(avg_price, x='區域', y='地坪單價(萬/坪)', color='區域', title=f'{city}平均建坪單價柱狀圖')
            fig.update_traces(textposition='outside')
            fig.update_layout(xaxis_title='行政區', yaxis_title='平均建坪單價 (萬/坪)', title_x=0.5, showlegend=False, template='plotly_white')
            st.plotly_chart(fig, use_container_width=True)
        except Exception as e:
            st.error(f"❌ 圖表生成過程發生錯誤：{e}")
