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

def plot_price_scatter(target_row, df):
    """
    繪製同區同類型房價 vs 實際坪數散佈圖
    
    Parameters:
    -----------
    target_row : pd.Series
        目標房型的資料列
    df : pd.DataFrame
        包含所有房產資料的 DataFrame (應已包含 '行政區' 欄位)
    """
    
    if isinstance(df, pd.Series):
        df = pd.DataFrame([df])
    
    df = df.copy()
    
    if '類型' in df.columns:
        df['類型'] = df['類型'].astype(str).str.strip()
    
    target_district = target_row.get('行政區', None)
    target_type = target_row.get('類型', None)
    
    if target_type and isinstance(target_type, str):
        target_type = target_type.strip()
        # 如果是混合類型（例如 '大樓/辦公'），取第一個
        if '/' in target_type:
            target_type = target_type.split('/')[0].strip()
    
    if not target_district or not target_type:
        st.warning("⚠️ 無法取得目標房型的行政區或類型資訊")
        return
    
    # ✅ 使用模糊比對（與搜尋邏輯一致）
    df_filtered = df[
        (df['行政區'] == target_district) & 
        (df['類型'].astype(str).str.contains(target_type, case=False, na=False))
    ].copy()
    
    if len(df_filtered) == 0:
        st.info(f"ℹ️ 找不到 {target_district} 包含「{target_type}」的房屋")
        return
    
    # 處理總價顯示格式
    def format_price(x):
        if pd.isna(x):
            return "未知"
        if x >= 10000:
            return f"{x/10000:.1f} 億"
        else:
            return f"{int(x)} 萬"
    
    # hover info 統一函式
    def make_hover(df_input):
        hover_text = []
        for i, row in df_input.iterrows():
            hover_text.append(
                f"<b>{row.get('標題', '未知')}</b><br>"
                f"地址：{row.get('地址', '未知')}<br>"
                f"類型：{row.get('類型', '未知')}<br>"
                f"樓層：{row.get('樓層', '未知')}<br>"
                f"屋齡：{row.get('屋齡', '未知')} 年<br>"
                f"實際坪數：{row.get('實際坪數', '未知')} 坪<br>"
                f"總價：{format_price(row.get('總價', None))}"
            )
        return hover_text
    
    # 準備資料
    target_df = pd.DataFrame([target_row])
    others_df = df_filtered[df_filtered['標題'] != target_row.get('標題')].copy()
    
    # 欄位重新命名
    for df_temp in [target_df, others_df]:
        if '建坪' in df_temp.columns and '建物面積' not in df_temp.columns:
            df_temp.rename(columns={'建坪': '建物面積'}, inplace=True)
        if '總價(萬)' in df_temp.columns and '總價' not in df_temp.columns:
            df_temp.rename(columns={'總價(萬)': '總價'}, inplace=True)
    
    # 轉換數值欄位
    target_df['實際坪數'] = pd.to_numeric(target_df.get('主+陽', [0]).iloc[0] if len(target_df) > 0 else 0, errors='coerce')
    others_df['實際坪數'] = pd.to_numeric(others_df.get('主+陽', 0), errors='coerce')
    target_df['總價'] = pd.to_numeric(target_df.get('總價', [0]).iloc[0] if len(target_df) > 0 else 0, errors='coerce')
    others_df['總價'] = pd.to_numeric(others_df.get('總價', 0), errors='coerce')
    
    # 移除 NaN
    others_df = others_df.dropna(subset=['實際坪數', '總價'])
    
    if others_df.empty:
        st.info(f"ℹ️ {target_district} 包含「{target_type}」沒有足夠的比較資料")
        return
    
    if pd.isna(target_df['實際坪數'].iloc[0]) or pd.isna(target_df['總價'].iloc[0]):
        st.warning("⚠️ 目標房型缺少必要的坪數或價格資訊")
        return
    
    # 建立散點圖
    fig = px.scatter(
        others_df,
        x='實際坪數',
        y='總價',
        render_mode='svg',
        opacity=0.4,
        width=500,
        height=500
    )
    
    hover_others = make_hover(others_df)
    fig.update_traces(
        hovertemplate='%{customdata}<extra></extra>',
        customdata=hover_others
    )
    
    # 加入目標房型紅星
    hover_target = make_hover(target_df)
    fig.add_scatter(
        x=target_df['實際坪數'],
        y=target_df['總價'],
        mode='markers',
        marker=dict(size=25, color='red', symbol='star'),
        name='目標房型',
        hovertemplate='%{customdata}<extra></extra>',
        customdata=[hover_target[0]]
    )
    
    # 設定顯示範圍
    x_center = target_df['實際坪數'].iloc[0]
    y_center = target_df['總價'].iloc[0]
    
    x_range = (0, x_center * 2.5)
    y_range = (0, y_center * 2.5)
    
    fig.update_layout(
        title=f'{target_district} 包含「{target_type}」的房型 房價 vs 實際坪數 (共 {len(df_filtered)} 筆)',
        xaxis_title='實際坪數 (坪)',
        yaxis_title='總價 (萬)',
        template='plotly_white',
        width=500,
        height=500,
        xaxis=dict(
            range=x_range, 
            showline=True, 
            linewidth=2, 
            linecolor='white', 
            mirror=True, 
            gridcolor='whitesmoke'
        ),
        yaxis=dict(
            range=y_range, 
            showline=True, 
            linewidth=2, 
            linecolor='white', 
            mirror=True, 
            gridcolor='whitesmoke'
        ),
        showlegend=True
    )
    
    st.plotly_chart(fig)

def plot_space_efficiency_scatter(target_row, df):
    """
    繪製建坪 vs 實際坪數散佈圖（空間效率分析）
    
    Parameters:
    -----------
    target_row : pd.Series
        目標房型的資料列
    df : pd.DataFrame
        包含所有房產資料的 DataFrame
    """
    
    if isinstance(df, pd.Series):
        df = pd.DataFrame([df])
    
    df = df.copy()
    
    # 使用行政區欄位
    if '類型' in df.columns:
        df['類型'] = df['類型'].astype(str).str.strip()
    
    target_district = target_row.get('行政區', None)
    target_type = target_row.get('類型', None)
    
    if target_type and isinstance(target_type, str):
        target_type = target_type.strip()
        # 處理混合類型
        if '/' in target_type:
            target_type_main = target_type.split('/')[0].strip()
        else:
            target_type_main = target_type
    else:
        st.warning("⚠️ 無法取得目標房型的類型資訊")
        return
    
    if not target_district:
        st.warning("⚠️ 無法取得目標房型的行政區資訊")
        return
    
    # 使用模糊比對篩選
    df_filtered = df[
        (df['行政區'] == target_district) & 
        (df['類型'].astype(str).str.contains(target_type_main, case=False, na=False))
    ].copy()
    
    if len(df_filtered) == 0:
        st.info(f"ℹ️ 找不到 {target_district} 包含「{target_type_main}」的房屋")
        return
    
    # 欄位重新命名
    if '建坪' not in df_filtered.columns and '建物面積' in df_filtered.columns:
        df_filtered.rename(columns={'建物面積': '建坪'}, inplace=True)
    if '總價(萬)' not in df_filtered.columns and '總價' in df_filtered.columns:
        df_filtered.rename(columns={'總價': '總價(萬)'}, inplace=True)
    
    # 轉換數值
    df_filtered['建坪'] = pd.to_numeric(df_filtered.get('建坪', 0), errors='coerce')
    df_filtered['主+陽'] = pd.to_numeric(df_filtered.get('主+陽', 0), errors='coerce')
    df_filtered['總價(萬)'] = pd.to_numeric(df_filtered.get('總價(萬)', 0), errors='coerce')
    
    # 避免異常值
    df_filtered = df_filtered[
        (df_filtered['建坪'] > 0) &
        (df_filtered['主+陽'] > 0) &
        (df_filtered['總價(萬)'] > 0)
    ].copy()
    
    if df_filtered.empty:
        st.info(f"ℹ️ {target_district} 包含「{target_type_main}」沒有足夠的有效資料")
        return
    
    # 基本衍生指標
    df_filtered['建坪單價(萬/坪)'] = df_filtered['總價(萬)'] / df_filtered['建坪']
    df_filtered['實際單價(萬/坪)'] = df_filtered['總價(萬)'] / df_filtered['主+陽']
    df_filtered['空間使用率'] = df_filtered['主+陽'] / df_filtered['建坪']
    
    # 目標房屋資料
    target_area = pd.to_numeric(target_row.get('建坪', 0), errors='coerce')
    target_actual_area = pd.to_numeric(target_row.get('主+陽', 0), errors='coerce')
    target_total_price = pd.to_numeric(target_row.get('總價(萬)', 0), errors='coerce')
    
    if pd.isna(target_area) or pd.isna(target_actual_area) or target_area == 0:
        st.warning("⚠️ 目標房型缺少必要的坪數資訊")
        return
    
    target_actual_price = target_total_price / target_actual_area if target_actual_area > 0 else 0
    target_usage_rate = (target_actual_area / target_area * 100) if target_area > 0 else 0
    
    # 建立 hover 資訊
    def make_hover_space(df_input):
        hover_text = []
        for i, row in df_input.iterrows():
            usage_rate = (row['主+陽'] / row['建坪'] * 100) if row['建坪'] > 0 else 0
            hover_text.append(
                f"<b>{row.get('標題', '未知')}</b><br>"
                f"建坪：{row.get('建坪', 0):.1f} 坪<br>"
                f"實際坪數：{row.get('主+陽', 0):.1f} 坪<br>"
                f"空間使用率：{usage_rate:.1f}%<br>"
                f"總價：{row.get('總價(萬)', 0):.0f} 萬"
            )
        return hover_text
    
    # 建立散點圖
    fig = px.scatter(
        df_filtered,
        x='建坪',
        y='主+陽',
        render_mode='svg',
        opacity=0.4,
        width=500,
        height=500
    )
    
    hover_others = make_hover_space(df_filtered)
    fig.update_traces(
        hovertemplate='%{customdata}<extra></extra>',
        customdata=hover_others
    )
    
    # 理想線：y = x（100% 使用率）
    max_area = df_filtered['建坪'].max()
    fig.add_scatter(
        x=[0, max_area],
        y=[0, max_area],
        mode='lines',
        line=dict(dash='dash', color='gray', width=1),
        name='100% 使用率',
        hoverinfo='skip'
    )
    
    # 目標房屋
    target_hover = (
        f"<b>{target_row.get('標題', '目標房屋')}</b><br>"
        f"建坪：{target_area:.1f} 坪<br>"
        f"實際坪數：{target_actual_area:.1f} 坪<br>"
        f"空間使用率：{target_usage_rate:.1f}%<br>"
        f"總價：{target_total_price:.0f} 萬"
    )
    
    fig.add_scatter(
        x=[target_area],
        y=[target_actual_area],
        mode='markers',
        marker=dict(size=25, color='red', symbol='star'),
        name='目標房型',
        hovertemplate='%{customdata}<extra></extra>',
        customdata=[target_hover]
    )
    
    fig.update_layout(
        title=dict(
            text=f'{target_district} 包含「{target_type_main}」的房型 建坪 vs 實際坪數 (共 {len(df_filtered)} 筆)',
            x=0.8,         # 0=左邊，0.5=中間，1=右邊
            xanchor='right' # 與 x 對齊方式，可選 'left', 'center', 'right'
        ),
        xaxis_title='建坪 (坪)',
        yaxis_title='實際坪數 (主+陽, 坪)',
        template='plotly_white',
        width=500,
        height=500,
        xaxis=dict(
            showline=True, 
            linewidth=2, 
            linecolor='white', 
            mirror=True, 
            gridcolor='whitesmoke'
        ),
        yaxis=dict(
            showline=True, 
            linewidth=2, 
            linecolor='white', 
            mirror=True, 
            gridcolor='whitesmoke'
        ),
        showlegend=True
    )
    
    st.plotly_chart(fig)
    
    # 顯示統計資訊
    avg_usage_rate = (df_filtered['空間使用率'].mean() * 100)
    st.caption(
        f"📊 空間效率統計：{target_district} 包含「{target_type_main}」平均使用率 {avg_usage_rate:.1f}%，"
        f"目標房型使用率 {target_usage_rate:.1f}%"
    )

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
        
        # ⭐ 補充：取得完整資料集
        all_df = None
        if 'all_properties_df' in st.session_state and not st.session_state.all_properties_df.empty:
            all_df = st.session_state.all_properties_df
        elif 'filtered_df' in st.session_state and not st.session_state.filtered_df.empty:
            all_df = st.session_state.filtered_df
        
        # ⭐ 補充：取得目標房屋的行政區和類型
        target_district = selected_row.get('行政區')
        target_type = selected_row.get('類型', '').strip()
        if '/' in target_type:
            target_type = target_type.split('/')[0].strip()
        
        # ⭐ 補充：篩選出比較母體（同區同類型）
        df_filtered = pd.DataFrame()
        if all_df is not None and not all_df.empty:
            df_filtered = all_df[
                (all_df['行政區'] == target_district) & 
                (all_df['類型'].astype(str).str.contains(target_type, case=False, na=False))
            ].copy()

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
        model = genai.GenerativeModel("gemini-2.5-flash")
        
        st.write("\n")
        analyze_clicked = st.button("開始分析", use_container_width=True, key="solo_analysis_button")
        
        if analyze_clicked:
            if not gemini_key:
                st.error("❌ 右側 gemini API Key 有誤")
                st.stop()
            try:
                with st.spinner("📊 正在計算市場價格指標..."):
                    # ===============================
                    # 價格分析
                    # ===============================
                    
                    # 比較母體（同區同類型）
                    compare_df = df_filtered.copy()
                    
                    # 確保數值欄位
                    compare_df['總價'] = pd.to_numeric(compare_df['總價(萬)'], errors='coerce')
                    compare_df['實際坪數'] = pd.to_numeric(compare_df['主+陽'], errors='coerce')
                    compare_df = compare_df.dropna(subset=['總價', '實際坪數'])
                    
                    target_price = float(selected_row['總價(萬)'])
                    target_area = float(selected_row['主+陽'])
                    price_per_ping = round(target_price / target_area, 2)
                    
                    # 價格百分位
                    price_percentile = (
                        (compare_df['總價'] < target_price).sum() / len(compare_df)
                    ) * 100
                    
                    # 排名
                    price_rank = (compare_df['總價'] < target_price).sum() + 1
                    total_count = len(compare_df)
                    
                    # 市場基準
                    median_price = compare_df['總價'].median()
                    mean_price = compare_df['總價'].mean()
                    price_vs_median_diff = round(target_price - median_price, 1)
                    
                    # 密集區（用 40~60 百分位當主流）
                    is_in_dense_area = 40 <= price_percentile <= 60
                    dense_ratio = (
                        ((compare_df['總價'] >= compare_df['總價'].quantile(0.4)) &
                         (compare_df['總價'] <= compare_df['總價'].quantile(0.6)))
                        .sum() / total_count
                    )
                    
                    analysis_payload = {
                        "區域": target_district,
                        "房屋類型": target_type,
                        "比較樣本數": total_count,
                    
                        "目標房屋": {
                            "總價(萬)": target_price,
                            "實際坪數": target_area,
                            "單價(萬/坪)": price_per_ping
                        },
                    
                        "價格分布": {
                            "價格百分位": round(price_percentile, 1),
                            "價格排名": f"{price_rank}/{total_count}",
                            "市場中位數(萬)": round(median_price, 1),
                            "與中位數差距(萬)": price_vs_median_diff
                        },
                    
                        "市場密集度": {
                            "是否位於主流價格帶": "是" if is_in_dense_area else "否",
                            "主流價格帶占比(%)": round(dense_ratio * 100, 1)
                        }
                    }
                prompt = f"""
                你是一位台灣房市分析顧問。
                
                以下是「已經計算完成」的價格分析數據（JSON），
                請 **只根據提供的數值進行說明**，不可自行推算或補充不存在的數據。
                
                請用繁體中文完成三件事：
                1️⃣ 解讀該房屋價格在市場中的位置（偏低 / 主流 / 偏高）
                2️⃣ 說明是否落在市場主流交易區間
                3️⃣ 提供一段理性、保守、不誇大的購屋建議
                
                分析數據如下：
                {json.dumps(analysis_payload, ensure_ascii=False, indent=2)}
                """
                
                with st.spinner("🧠AI 正在解讀圖表並產生分析結論..."):
                    response = model.generate_content(prompt)
                    
                st.success("✅ 分析完成")
                st.header("🏡 房屋逐項分析說明 ")
                # 使用三引號處理跨行文字
                st.write("""
                我們將針對所選房屋的六大面向逐一分析，包括價格、坪數、屋齡、樓層、格局與地段。
                每項分析都結合市場資料與 AI 評估，提供清楚、可理解的參考資訊。
                """)
                st.markdown("---")
                
                st.subheader("價格 💸")
                # 取得比較資料
                compare_base_df = pd.DataFrame()
                if 'all_properties_df' in st.session_state and not st.session_state.all_properties_df.empty:
                    compare_base_df = st.session_state.all_properties_df
                elif 'filtered_df' in st.session_state and not st.session_state.filtered_df.empty:
                    compare_base_df = st.session_state.filtered_df
                
                # 原有的圖表顯示
                col1, col2 = st.columns([1, 1])
                with col1:
                    if not compare_base_df.empty:
                        plot_price_scatter(selected_row, compare_base_df)
                    else:
                        st.warning("⚠️ 找不到比較基準資料，無法顯示圖表")
                with col2:
                    st.markdown("### 💰 價格分析結論")
                    st.write(response.text)
                st.markdown("---")

                st.subheader("坪數 📐")
                col1, col2 = st.columns([1, 1])
                
                with col1:
                    st.write("坪數分析文字說明（待補充）")
                
                with col2:
                    # 取得比較資料
                    compare_base_df = pd.DataFrame()
                    if 'all_properties_df' in st.session_state and not st.session_state.all_properties_df.empty:
                        compare_base_df = st.session_state.all_properties_df
                    elif 'filtered_df' in st.session_state and not st.session_state.filtered_df.empty:
                        compare_base_df = st.session_state.filtered_df
                    
                    if not compare_base_df.empty:
                        # 呼叫空間效率圖表函式
                        plot_space_efficiency_scatter(selected_row, compare_base_df)
                    else:
                        st.warning("⚠️ 找不到比較基準資料，無法顯示圖表")
                
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
