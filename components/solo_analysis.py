import streamlit as st
import pandas as pd
import google.generativeai as genai
import hnswlib
from sentence_transformers import SentenceTransformer
import os
import numpy as np
import plotly.express as px

# 名稱對照表
name_map = {
    "Taichung-city_buy_properties.csv": "台中市",
    "Taipei-city_buy_properties.csv": "台北市"
}

# 反向對照表:中文 -> 英文檔名
reverse_name_map = {v: k for k, v in name_map.items()}

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

def format_price(raw_price):
    """格式化價格"""
    if raw_price is None or raw_price == '' or raw_price == '未提供':
        return '未提供'
    try:
        return f"{int(raw_price)*10000:,}"
    except:
        return raw_price

def format_area(area):
    """格式化坪數"""
    return f"{area} 坪" if area != '未提供' else area

def row_to_text(row):
    """將每列資料轉為文字描述"""
    return (
        f"地址:{row['地址']}, 建坪:{row['建坪']}, 主+陽:{row['主+陽']}, "
        f"總價:{row['總價(萬)']}萬, 屋齡:{row['屋齡']}, 類型:{row['類型']}, "
        f"格局:{row['格局']}, 樓層:{row['樓層']}, 車位:{row['車位']}"
    )

def analyze_single_property(selected_row, gemini_key):
    """個別房屋分析"""
    genai.configure(api_key=gemini_key)
    model = genai.GenerativeModel("gemini-2.0-flash")
    
    address = selected_row.get('地址')
    city = address[:3]
    english_filename = reverse_name_map.get(city)
    file_path = os.path.join("./Data", english_filename)
    
    df = pd.read_csv(file_path)
    house_title = str(selected_row.get('標題', '')).strip()
    selected_row = df[df['標題'] == house_title].iloc[0]
    
    embed_model = SentenceTransformer('all-MiniLM-L6-v2')
    
    with st.spinner("正在將資料進行向量化處理..."):
        texts = df.apply(row_to_text, axis=1).tolist()
        embeddings = embed_model.encode(texts, show_progress_bar=True)
        embeddings = np.array(embeddings).astype('float32')
        
        dimension = embeddings.shape[1]
        num_elements = len(embeddings)
        
        index = hnswlib.Index(space='l2', dim=dimension)
        index.init_index(max_elements=num_elements, ef_construction=200, M=16)
        index.add_items(embeddings, np.arange(num_elements))
        index.set_ef(50)
        
        selected_idx = df[df['標題'] == house_title].index[0]
        selected_text = row_to_text(selected_row)
        query_vec = embeddings[selected_idx:selected_idx+1]
        
        top_k = 11
        labels, distances = index.knn_query(query_vec, k=top_k)
        
        relevant_data = []
        for idx, dist in zip(labels[0], distances[0]):
            if idx != selected_idx:
                house_data = df.iloc[idx].to_dict()
                relevant_data.append(house_data)
    
    selected_text_display = f"{selected_row['標題']} - {selected_text}"
    relevant_text = "\n".join([f"{r['標題']} - {row_to_text(r)}" for r in relevant_data])
    
    prompt = f"""
你是一位台灣不動產市場專家，具有多年房屋估價與市場分析經驗。
請根據以下房屋資料生成中文市場分析：

目標房型：
{selected_text_display}

相似房屋資料：
{relevant_text}

請分析價格合理性、坪數與屋齡，提供購買建議，避免編造不存在的數字。
"""
    
    with st.spinner("Gemini 正在分析中..."):
        response = model.generate_content(prompt)
    
    st.success("✅ 分析完成")
    st.markdown("### 🧠 **Gemini 市場分析結果**")
    st.markdown(response.text)
    
    with st.expander("相似房型資料"):
        if relevant_data:
            similar_df = pd.DataFrame(relevant_data)
            display_cols = ['標題', '地址', '建坪', '主+陽', '總價(萬)', '屋齡', '類型', '格局', '樓層', '車位']
            similar_df = similar_df[display_cols]
            st.dataframe(similar_df)
        else:
            st.write("沒有找到相似房型")

def analyze_price_chart(selected_row, city, gemini_key, house_input_text_chart):
    """圖表價格分析"""
    genai.configure(api_key=gemini_key)
    model = genai.GenerativeModel("gemini-2.0-flash")
    
    english_filename = reverse_name_map.get(city)
    file_path = os.path.join("./Data", english_filename)
    df = pd.read_csv(file_path)
    
    # 數據處理
    df['區域'] = df['地址'].str.extract(r'市(.+?)區')[0]
    df = df[df['建坪'] > 0.1].copy()
    df['地坪單價(萬/坪)'] = df['總價(萬)'] / df['建坪']
    
    selected_type = f"{selected_row.get('類型')}"
    if selected_type:
        df = df[df['類型'].str.contains(selected_type, na=False)]
    
    avg_price = df.groupby('區域', as_index=False)['地坪單價(萬/坪)'].mean()
    avg_price['區域'] = avg_price['區域'] + '區'
    
    # 繪製圖表
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
    
    # AI 分析
    if st.button("請AI分析", key="bar_chart_analysis"):
        try:
            avg_text = "\n".join([
                f"{row['區域']} 平均地坪單價: {row['地坪單價(萬/坪)']} 萬/坪"
                for _, row in avg_price.iterrows()
            ])
            
            prompt = f"""
你是一位台灣不動產市場專家，請針對下列目標房屋的建坪單價和區域平均建坪單價資訊，提供簡短的價格評估：

目標房屋：
{house_input_text_chart}

區域平均建坪單價：
{avg_text}

指出是否高於或低於平均水平。
"""
            
            with st.spinner("Gemini 正在分析中..."):
                response = model.generate_content(prompt)
            
            st.success("✅ 分析完成")
            st.markdown("### 📊 **Gemini 建坪圖表分析結果**")
            st.markdown(response.text)
        except Exception as e:
            st.error(f"❌ 分析過程發生錯誤：{e}")

def tab1_module():
    """標籤頁 1：個別分析模組"""
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
    
    # 顯示房屋卡片
    st.markdown(f"""
### {selected_row.get('標題', '未提供')}
📍 {selected_row.get('地址', '未提供')}
""", unsafe_allow_html=True)
    
    # 價格處理
    raw_price = selected_row.get('總價(萬)')
    formatted_price = format_price(raw_price)
    
    area = selected_row.get('建坪', '未提供')
    area_text = format_area(area)
    
    actual_space = selected_row.get('主+陽', '未提供')
    actual_space_text = format_area(actual_space)
    
    # 計算單價
    if formatted_price != '未提供' and area != '未提供':
        total_price = int(raw_price) * 10000
        area_price_per = f"{int(total_price)/area:,.0f}"
        actual_space_price_per = f"{int(total_price)/actual_space:,.0f}"
    else:
        area_price_per = "未提供"
        actual_space_price_per = "未提供"
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.markdown(f"""
**基本資訊**
- 類型：{selected_row.get('類型', '未提供')}
- 建坪：{area_text}
- 實際坪數：{actual_space_text}
- 格局：{selected_row.get('格局', '未提供')}
- 樓層：{selected_row.get('樓層', '未提供')}
- 屋齡：{selected_row.get('屋齡', '未提供')}
- 車位：{selected_row.get('車位', '未提供')}
""")
        analyze_clicked = st.button("開始分析", use_container_width=True, key="solo_analysis_button")
    
    with col2:
        st.markdown(f"""
**價格資訊**
- 💰 總價：{formatted_price} 元
- 建坪單價：{area_price_per} 元/坪
- 實際單價：{actual_space_price_per} 元/坪
""")
        chart_clicked = st.button("可視化圖表分析", use_container_width=True, key="chart_analysis_button")
    
    gemini_key = st.session_state.get("GEMINI_KEY", "")
    
    # 個別分析
    if analyze_clicked:
        if not gemini_key:
            st.error("❌ 右側 Gemini API Key 有誤")
            return
        
        try:
            analyze_single_property(selected_row, gemini_key)
            
            if st.button("🗃️ 儲存分析結果", use_container_width=True, key="data_storage"):
                st.write("分析結果已儲存")
        
        except Exception as e:
            st.error(f"❌ 分析過程發生錯誤：{e}")
    
    # 圖表分析
    if chart_clicked:
        if not gemini_key:
            st.error("❌ 右側 Gemini API Key 有誤")
            return
        
        try:
            house_input_text_chart = f"""
地址：{selected_row.get('地址', '未提供')}
建坪：{area_text}
建坪單價：{area_price_per} 元/坪
類型：{selected_row.get('類型', '未提供')}
格局：{selected_row.get('格局', '未提供')}
樓層：{selected_row.get('樓層', '未提供')}
屋齡：{selected_row.get('屋齡', '未提供')}
車位：{selected_row.get('車位', '未提供')}
"""
            address = selected_row.get('地址')
            city = address[:3]
            
            analyze_price_chart(selected_row, city, gemini_key, house_input_text_chart)
        
        except Exception as e:
            st.error(f"❌ 圖表生成過程發生錯誤：{e}")

# 主程式
if __name__ == "__main__":
    tab1_module()
