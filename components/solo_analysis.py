import streamlit as st
import pandas as pd
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer
import google.generativeai as genai

# -----------------------------
# 載入資料與向量 / FAISS 索引
# -----------------------------
@st.cache_resource
def load_data():
    df = st.session_state.all_properties_df if 'all_properties_df' in st.session_state else pd.DataFrame()
    embeddings = np.load("embeddings.npy")  # 事先向量化保存
    index = faiss.read_index("faiss_index.bin")  # 事先建立 FAISS 索引
    model = SentenceTransformer('all-MiniLM-L6-v2', device='cpu')  # query vector 使用 CPU
    return df, embeddings, index, model

df, embeddings, index, model = load_data()

# -----------------------------
# 取得收藏房產資料
# -----------------------------
def get_favorites_data():
    if 'favorites' not in st.session_state or not st.session_state.favorites:
        return pd.DataFrame()
    
    all_df = df
    fav_ids = st.session_state.favorites
    fav_df = all_df[all_df['編號'].isin(fav_ids)].copy()
    return fav_df

# -----------------------------
# Tab1 模組：個別分析 + RAG
# -----------------------------
def tab1_module():
    fav_df = get_favorites_data()
    if fav_df.empty:
        st.header("個別分析")
        st.info("⭐ 尚未有收藏房產，無法比較")
        return

    options = fav_df['標題']
    col1, col2 = st.columns([2,1])
    with col1:
        st.header("個別分析")
    with col2:
        choice = st.selectbox("選擇房屋", options, key="analysis_solo")

    selected_row = fav_df[fav_df['標題'] == choice].iloc[0]

    # 顯示房屋卡片
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

    # 總價、建坪單價等
    raw_price = selected_row.get('總價(萬)')
    if raw_price in [None,'','未提供']:
        formatted_price = '未提供'
    else:
        try:
            formatted_price = f"{int(raw_price)*10000:,}"
        except:
            formatted_price = raw_price

    area = selected_row.get('建坪','未提供')
    area_text = f"{area} 坪" if area != '未提供' else area
    Actual_space = selected_row.get('主+陽','未提供')
    Actual_space_text = f"{Actual_space} 坪" if Actual_space != '未提供' else Actual_space
    if raw_price not in [None,'','未提供']:
        total_price = int(raw_price)*10000
        area_Price_per = f"{int(total_price)/area:,.0f}"
        Actual_space_Price_per = f"{int(total_price)/Actual_space:,.0f}"
    else:
        area_Price_per = Actual_space_Price_per = '未提供'

    # 詳細資訊顯示
    col1, col2 = st.columns([1,1])
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

    # 置中分析按鈕
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.write("")
        st.markdown("<div style='text-align:center;'>", unsafe_allow_html=True)
        analyze_clicked = st.button("開始分析 (RAG)", key="rag_analysis_button")
        st.markdown("</div>", unsafe_allow_html=True)

    # -----------------------------
    # RAG 分析流程
    # -----------------------------
    if analyze_clicked:
        gemini_key = st.session_state.get("GEMINI_KEY","")
        if not gemini_key:
            st.error("❌ 右側 gemini API Key 有誤")
            st.stop()

        try:
            genai.configure(api_key=gemini_key)
            model_gen = genai.GenerativeModel("gemini-2.0-flash")

            # 建立單筆 query vector
            query_text = f"地址:{selected_row['地址']}, 建坪:{selected_row['建坪']}, 主+陽:{selected_row['主+陽']}, 總價:{selected_row['總價(萬)']}萬, 屋齡:{selected_row['屋齡']}, 類型:{selected_row['類型']}, 格局:{selected_row['格局']}, 樓層:{selected_row['樓層']}, 車位:{selected_row['車位']}"
            query_vec = model.encode([query_text]).astype("float32")

            # 檢索相似房屋
            top_k = 6  # 包含自己
            D, I = index.search(query_vec, k=top_k)
            relevant_data = df.iloc[I[0]].to_dict(orient="records")
            # 過濾掉自己
            relevant_data = [row for row in relevant_data if row['編號'] != selected_row['編號']]
            
            # 構建 RAG 文字
            relevant_text = "\n".join([
                f"{row['標題']} - 地址:{row['地址']}, 建坪:{row['建坪']}, 主+陽:{row['主+陽']}, 總價:{row['總價(萬)']}萬, 屋齡:{row['屋齡']}, 類型:{row['類型']}, 格局:{row['格局']}, 樓層:{row['樓層']}, 車位:{row['車位']}"
                for row in relevant_data
            ])

            prompt = f"""
請根據以下房屋資料生成中文市場分析：
單筆房型：
{query_text}

相似房屋資料：
{relevant_text}

請分析價格合理性、坪數與屋齡，提供購買建議，避免編造不存在的數字。
"""

            with st.spinner("Gemini 正在分析中..."):
                response = model_gen.generate_content(prompt)

            st.success("✅ 分析完成")
            st.markdown("### 🔍 RAG 分析結果")
            st.markdown(response.text)

        except Exception as e:
            st.error(f"❌ 分析過程發生錯誤：{e}")
