import streamlit as st
import pandas as pd
import google.generativeai as genai
import os
import plotly.graph_objects as go
import plotly.express as px
import json
import re
import numpy as np

# 在檔案開頭, name_map 下方加入反向對照表
name_map = {
    "Taichung-city_buy_properties.csv": "台中市",
}
# 建立反向對照表: 中文 -> 英文檔名
reverse_name_map = {v: k for k, v in name_map.items()}

def plot_floor_distribution(target_row, df):
    """
    繪製同區同類型樓層分布與平均單價圖
    
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
    
    # 統一使用 '類型' 欄位處理
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
    
    # ========== 提取樓層數值 ==========
    def extract_floor(floor_str):
        """從樓層字串中提取數字"""
        if pd.isna(floor_str):
            return np.nan
        try:
            # 嘗試提取 "X樓" 中的 X
            floor_num = str(floor_str).split('樓')[0].strip()
            return int(floor_num)
        except:
            return np.nan
    
    df_filtered['樓層數值'] = df_filtered['樓層'].apply(extract_floor)
    
    # 取得目標樓層（在移除 NaN 之前）
    target_floor = extract_floor(target_row.get('樓層', None))
    
    # 移除樓層數值為 NaN 的資料
    df_filtered_copy = df_filtered.dropna(subset=['樓層數值']).copy()
    
    if len(df_filtered_copy) == 0:
        st.info("ℹ️ 無足夠樓層資料進行分析")
        return
    
    # 確保有總價和建坪欄位
    if '總價(萬)' in df_filtered_copy.columns:
        df_filtered_copy['總價'] = pd.to_numeric(df_filtered_copy['總價(萬)'], errors='coerce')
    elif '總價' in df_filtered_copy.columns:
        df_filtered_copy['總價'] = pd.to_numeric(df_filtered_copy['總價'], errors='coerce')
    else:
        df_filtered_copy['總價'] = 0
    
    if '建坪' in df_filtered_copy.columns:
        df_filtered_copy['建坪數值'] = pd.to_numeric(df_filtered_copy['建坪'], errors='coerce')
    elif '建物面積' in df_filtered_copy.columns:
        df_filtered_copy['建坪數值'] = pd.to_numeric(df_filtered_copy['建物面積'], errors='coerce')
    else:
        df_filtered_copy['建坪數值'] = 0
    
    # 計算單價
    df_filtered_copy = df_filtered_copy[(df_filtered_copy['總價'] > 0) & (df_filtered_copy['建坪數值'] > 0)].copy()
    
    if len(df_filtered_copy) == 0:
        st.info("ℹ️ 無足夠有效價格資料進行分析")
        return
    
    df_filtered_copy['單價(萬/坪)'] = df_filtered_copy['總價'] / df_filtered_copy['建坪數值']
    
    # ========== 建立樓層區間 ==========
    # 設定樓層區間（每 5 層一組）
    max_floor = df_filtered_copy['樓層數值'].max()
    bin_width = 5
    bins = list(range(0, int(max_floor) + bin_width, bin_width))
    
    df_filtered_copy['樓層區間'] = pd.cut(
        df_filtered_copy['樓層數值'],
        bins=bins,
        labels=[f"{bins[i]}-{bins[i+1]}樓" for i in range(len(bins)-1)],
        include_lowest=True
    )
    
    # ========== 計算統計數據 ==========
    floor_stats = df_filtered_copy.groupby('樓層區間', observed=True).agg({
        '單價(萬/坪)': 'mean',
        '標題': 'count'
    }).reset_index()
    
    floor_stats.columns = ['樓層區間', '平均單價', '房屋數量']
    
    if len(floor_stats) == 0:
        st.info("ℹ️ 無足夠資料進行樓層分析")
        return
    
    # ========== 建立圖表 ==========
    fig = go.Figure()
    
    # 添加長條圖（房屋數量）
    fig.add_trace(go.Bar(
        x=floor_stats['樓層區間'].astype(str),
        y=floor_stats['房屋數量'],
        name='房屋數量',
        marker=dict(color='lightblue', line=dict(color='black', width=1)),
        yaxis='y'
    ))
    
    # 添加折線圖（平均單價）
    fig.add_trace(go.Scatter(
        x=floor_stats['樓層區間'].astype(str),
        y=floor_stats['平均單價'],
        mode='lines+markers',
        name='平均單價',
        line=dict(color='orange', width=2),
        marker=dict(size=8, color='orange'),
        yaxis='y2',
        hovertemplate='<b>%{x}</b><br>平均單價: %{y:.2f} 萬/坪<extra></extra>'
    ))
    
    # ========== 標記目標房屋所在樓層區間 ==========
    if not pd.isna(target_floor):
        target_floor_group = pd.cut([target_floor], bins=bins, include_lowest=True)[0]
        target_floor_label = str(target_floor_group)
        
        # 找到目標樓層區間在圖表中的位置
        if target_floor_label in floor_stats['樓層區間'].astype(str).values:
            target_bin_index = np.digitize(target_floor, bins) - 1
            
            if 0 <= target_bin_index < len(floor_stats):
                fig.add_trace(go.Scatter(
                    x=[floor_stats.iloc[target_bin_index]['樓層區間']],
                    y=[floor_stats.iloc[target_bin_index]['房屋數量']],
                    mode="markers+text",
                    marker=dict(color="red", size=15, symbol="star"),
                    text=["目標房屋"],
                    textposition="top center",
                    name="目標房屋",
                    yaxis='y'
                ))
    
    # 設定雙 Y 軸 layout
    fig.update_layout(
        title=f"{target_district} 包含「{target_type_main}」的房型 樓層分布與平均單價 (共 {len(df_filtered_copy)} 筆)",
        xaxis_title='樓層區間',
        yaxis=dict(
            title='房屋數量',
            side='left',
            showgrid=True,
            gridcolor='whitesmoke'
        ),
        yaxis2=dict(
            title='平均單價 (萬/坪)',
            overlaying='y',
            side='right',
            showgrid=False
        ),
        template='plotly_white',
        width=600,
        height=500,
        hovermode='x unified',
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),
        bargap=0.3
    )
    
    st.plotly_chart(fig, use_container_width=True)
def plot_age_distribution(target_row, df):
    """
    繪製同區同類型屋齡分布直方圖（含建坪單價趨勢線）
    """
    if isinstance(df, pd.Series):
        df = pd.DataFrame([df])
    
    df = df.copy()
    
    # 文字 -> 數字
    def parse_age(x):
        if pd.isna(x):
            return np.nan
        match = re.search(r"(\d+\.?\d*)", str(x))
        if match:
            return float(match.group(1))
        return np.nan
    
    df['屋齡數值'] = df['屋齡'].apply(parse_age)
    
    # 統一使用 '類型' 欄位處理
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
    df_filtered_age = df[
        (df['行政區'] == target_district) & 
        (df['類型'].astype(str).str.contains(target_type_main, case=False, na=False))
    ].copy()
    
    if len(df_filtered_age) == 0:
        st.info(f"ℹ️ 找不到 {target_district} 包含「{target_type_main}」的房屋")
        return
    
    # 取得目標屋齡
    target_age = parse_age(target_row.get('屋齡', None))
    
    if pd.isna(target_age):
        st.warning("⚠️ 目標房型缺少屋齡資訊")
        return
    
    # 取屋齡數值，並移除 NaN 值
    ages = df_filtered_age['屋齡數值'].dropna().values
    
    if len(ages) == 0:
        st.info("ℹ️ 無足夠屋齡資料進行屋齡分佈分析")
        return
    
    # 設定箱子範圍
    bin_width = 5  # 每個長方條範圍 5 年
    bins = np.arange(0, ages.max() + bin_width, bin_width)
    
    # 計算每個箱子數量
    hist, bin_edges = np.histogram(ages, bins=bins)
    
    # ========== 計算每個屋齡區間的平均建坪單價 ==========
    df_filtered_age['屋齡區間'] = pd.cut(
        df_filtered_age['屋齡數值'], 
        bins=bins, 
        labels=[f"{int(bin_edges[i])}-{int(bin_edges[i+1])} 年" for i in range(len(hist))],
        include_lowest=True
    )
    
    # 確保有總價和建坪欄位
    if '總價(萬)' in df_filtered_age.columns:
        df_filtered_age['總價'] = pd.to_numeric(df_filtered_age['總價(萬)'], errors='coerce')
    elif '總價' in df_filtered_age.columns:
        df_filtered_age['總價'] = pd.to_numeric(df_filtered_age['總價'], errors='coerce')
    else:
        df_filtered_age['總價'] = 0
    
    if '建坪' in df_filtered_age.columns:
        df_filtered_age['建坪數值'] = pd.to_numeric(df_filtered_age['建坪'], errors='coerce')
    elif '建物面積' in df_filtered_age.columns:
        df_filtered_age['建坪數值'] = pd.to_numeric(df_filtered_age['建物面積'], errors='coerce')
    else:
        df_filtered_age['建坪數值'] = 0
    
    # 過濾有效資料
    df_valid = df_filtered_age[(df_filtered_age['總價'] > 0) & (df_filtered_age['建坪數值'] > 0)].copy()
    df_valid['建坪單價'] = df_valid['總價'] / df_valid['建坪數值']
    
    # 計算每個區間的平均建坪單價
    avg_price_per_age = df_valid.groupby('屋齡區間', observed=True)['建坪單價'].mean()
    
    # ========== 建立圖表 ==========
    fig = go.Figure()
    
    # 屋齡分布長條圖
    x_labels = [f"{int(bin_edges[i])}-{int(bin_edges[i+1])} 年" for i in range(len(hist))]
    
    fig.add_trace(go.Bar(
        x=x_labels,
        y=hist,
        marker=dict(color='lightblue', line=dict(color='black', width=1)),
        name="屋齡分布",
        yaxis='y'
    ))
    
    # 標記目標房屋
    target_bin_index = np.digitize(target_age, bins) - 1
    if 0 <= target_bin_index < len(hist):
        fig.add_trace(go.Scatter(
            x=[x_labels[target_bin_index]],
            y=[hist[target_bin_index]],
            mode="markers+text",
            marker=dict(color="red", size=15, symbol="star"),
            text=["目標房屋"],
            textposition="top center",
            name="目標房屋", 
            showlegend=True,
            yaxis='y'
        ))
    
    # 加上建坪單價折線（使用次座標軸）
    y_price = [avg_price_per_age.get(label, None) for label in x_labels]
    
    fig.add_trace(go.Scatter(
        x=x_labels,
        y=y_price,
        mode='lines+markers',
        line=dict(color='orange', width=2),
        marker=dict(size=8, color='orange'),
        name='平均建坪單價',
        yaxis='y2',
        hovertemplate='<b>%{x}</b><br>平均建坪單價: %{y:.2f} 萬/坪<extra></extra>'
    ))
    
    # 設定 layout（雙 Y 軸）
    fig.update_layout(
        title=f"{target_district} 包含「{target_type_main}」的房型 屋齡分布與單價趨勢 (共 {len(df_filtered_age)} 筆)",
        xaxis_title="屋齡範圍 (年)",
        yaxis=dict(
            title="房屋數量",
            side='left',
            showgrid=True,
            gridcolor='whitesmoke'
        ),
        yaxis2=dict(
            title="平均建坪單價 (萬/坪)",
            overlaying='y',
            side='right',
            showgrid=False
        ),
        bargap=0.3,
        template="plotly_white",
        width=600,
        height=500,
        hovermode='x unified',
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        )
    )
    
    st.plotly_chart(fig, use_container_width=True)
    

def plot_price_scatter(target_row, df):
    """
    繪製同區同類型房價 vs 建坪散佈圖
    
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
    
    # hover info 統一函式（簡化版：只顯示名稱、建坪、總價、單價）
    def make_hover(df_input):
        hover_text = []
        for i, row in df_input.iterrows():
            building_area = row.get('建坪', 0)
            total_price = row.get('總價', 0)
            
            # 計算單坪價
            if building_area > 0 and total_price > 0:
                price_per_ping = total_price / building_area
            else:
                price_per_ping = 0
            
            hover_text.append(
                f"<b>{row.get('標題', '未知')}</b><br>"
                f"建坪：{building_area:.2f} 坪<br>"
                f"總價：{format_price(total_price)}<br>"
                f"單坪價：{price_per_ping:.2f} 萬/坪"
            )
        return hover_text
    
    # 準備資料
    target_df = pd.DataFrame([target_row])
    others_df = df_filtered[df_filtered['標題'] != target_row.get('標題')].copy()
    
    # 欄位重新命名
    for df_temp in [target_df, others_df]:
        if '總價(萬)' in df_temp.columns and '總價' not in df_temp.columns:
            df_temp.rename(columns={'總價(萬)': '總價'}, inplace=True)
        if '建物面積' in df_temp.columns and '建坪' not in df_temp.columns:
            df_temp.rename(columns={'建物面積': '建坪'}, inplace=True)
    
    # 轉換數值欄位（改用建坪）
    target_df['建坪'] = pd.to_numeric(target_df.get('建坪', [0]).iloc[0] if len(target_df) > 0 else 0, errors='coerce')
    others_df['建坪'] = pd.to_numeric(others_df.get('建坪', 0), errors='coerce')
    target_df['總價'] = pd.to_numeric(target_df.get('總價', [0]).iloc[0] if len(target_df) > 0 else 0, errors='coerce')
    others_df['總價'] = pd.to_numeric(others_df.get('總價', 0), errors='coerce')
    
    # 移除 NaN
    others_df = others_df.dropna(subset=['建坪', '總價'])
    
    if others_df.empty:
        st.info(f"ℹ️ {target_district} 包含「{target_type}」沒有足夠的比較資料")
        return
    
    if pd.isna(target_df['建坪'].iloc[0]) or pd.isna(target_df['總價'].iloc[0]):
        st.warning("⚠️ 目標房型缺少必要的建坪或價格資訊")
        return
    
    # 建立散點圖
    fig = px.scatter(
        others_df,
        x='建坪',
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
        x=target_df['建坪'],
        y=target_df['總價'],
        mode='markers',
        marker=dict(size=25, color='red', symbol='star'),
        name='目標房型',
        hovertemplate='%{customdata}<extra></extra>',
        customdata=[hover_target[0]]
    )
    
    # 設定顯示範圍
    x_center = target_df['建坪'].iloc[0]
    y_center = target_df['總價'].iloc[0]
    
    x_range = (0, x_center * 2.5)
    y_range = (0, y_center * 2.5)
    
    fig.update_layout(
        title=f'{target_district} 包含「{target_type}」的房型 房價 vs 建坪 (共 {len(df_filtered)} 筆)',
        xaxis_title='建坪 (坪)',
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

    max_area = max(df_filtered['建坪'].max(), df_filtered['主+陽'].max())
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
    fig.add_scatter(
        x=[0, max_area],
        y=[0, max_area],
        mode='lines',
        line=dict(dash='dash', color='gray'),
        name='100% 使用率'
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
    buffer = 1.5  # 放大倍率
    fig.update_layout(
        title=dict(
            text=f'{target_district} 包含「{target_type_main}」的房型 建坪 vs 實際坪數 (共 {len(df_filtered)} 筆)',
            x=0.9,         # 0=左邊，0.5=中間，1=右邊
            xanchor='right' # 與 x 對齊方式，可選 'left', 'center', 'right'
        ),
        xaxis_title='建坪 (坪)',
        yaxis_title='實際坪數 (坪)',
        template='plotly_white',
        width=500,
        height=500,
        xaxis=dict(range=[0, target_area*buffer], showline=True, linewidth=1, linecolor='white', mirror=True, gridcolor='whitesmoke'),
        yaxis=dict(range=[0, target_area*buffer], showline=True, linewidth=1, linecolor='white', mirror=True, gridcolor='whitesmoke', scaleanchor="x", scaleratio=1),
        showlegend=True
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
                    # 價格分析（使用建坪）
                    # ===============================
                    # 比較母體（同區同類型）
                    compare_df = df_filtered.copy()
                    
                    # 確保數值欄位 - 改用建坪
                    compare_df['總價'] = pd.to_numeric(compare_df['總價(萬)'], errors='coerce')
                    compare_df['建坪數'] = pd.to_numeric(compare_df['建坪'], errors='coerce')  # ✅ 改用建坪
                    compare_df = compare_df.dropna(subset=['總價', '建坪數'])  # ✅ 改用建坪數
                    
                    target_price = float(selected_row['總價(萬)'])
                    target_area = float(selected_row['建坪'])  # ✅ 改用建坪
                    price_per_ping = round(target_price / target_area, 2)  # ✅ 建坪單價
                    
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
                            "建坪": target_area,  # ✅ 改為建坪
                            "建坪單價(萬/坪)": price_per_ping  # ✅ 明確標示為建坪單價
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
                    
                    price_prompt = f"""
                    你是一位台灣房市分析顧問。
                    
                    以下是「已經計算完成」的價格分析數據（JSON），
                    請 **只根據提供的數值進行說明**，不可自行推算或補充不存在的數據。
                    
                    請用繁體中文完成三件事：
                    1️⃣ 解讀該房屋價格在市場中的位置（偏低 / 主流 / 偏高）
                    2️⃣ 說明是否落在市場主流交易區間
                    3️⃣ 提供一段理性、保守、不誇大的購屋建議
                    
                    **注意：此分析使用建坪計算單價，非實際坪數。**
                    
                    分析數據如下：
                    {json.dumps(analysis_payload, ensure_ascii=False, indent=2)}
                    """
                    
                    # ===============================
                    # 坪數分析
                    # ===============================
                    compare_df['實際坪數'] = pd.to_numeric(compare_df.get('主+陽', 0), errors='coerce')
                    compare_df['建坪'] = pd.to_numeric(compare_df.get('建坪', 0), errors='coerce')
                    
                    compare_df['空間使用率'] = compare_df['實際坪數'] / compare_df['建坪']
                    target_usage_rate = target_area / float(selected_row['建坪']) if selected_row['建坪'] > 0 else 0
                    usage_percentile = (compare_df['空間使用率'] < target_usage_rate).sum() / total_count * 100
                    median_usage = compare_df['空間使用率'].median()  # 同區中位數
                    mean_usage = compare_df['空間使用率'].mean()      # 同區平均使用率
                    actual_price_per_ping = target_price / target_area
                
                    floor_area_payload = {
                        "區域": target_district,
                        "房屋類型": target_type,
                        "比較樣本數": total_count,
                        "目標房屋": {
                            "建坪": selected_row['建坪'],
                            "實際坪數": target_area,
                            "空間使用率": round(target_usage_rate, 2),
                            "實際單價(萬/坪)": round(actual_price_per_ping, 2)
                        },
                        "坪數分布": {
                            "使用率百分位": round(usage_percentile, 1),
                            "中位數使用率": round(median_usage, 2),
                            "平均使用率": round(mean_usage, 2)
                        }
                    }
                
                    space_prompt = f"""
                    你是一位台灣房市分析顧問。
                
                    以下是「已經計算完成」的坪數分析數據（JSON），
                    請 **只根據提供的數值進行說明**，不可自行推算或補充不存在的數據。
                
                    請用繁體中文完成三件事：
                    1️⃣ 解讀該房屋空間使用效率（偏高 / 主流 / 偏低）
                    2️⃣ 說明在同區同類型中使用效率的排名與百分位
                    3️⃣ 提供一段理性、保守、不誇大的購屋建議
                
                    分析數據如下：
                    {json.dumps(floor_area_payload, ensure_ascii=False, indent=2)}
                    """
                    # ===============================
                    # 屋齡分析
                    # ===============================
                    
                    # 文字 -> 數字
                    def parse_age(x):
                        if pd.isna(x):
                            return np.nan
                        match = re.search(r"(\d+\.?\d*)", str(x))
                        if match:
                            return float(match.group(1))
                        return np.nan
                    
                    # 為比較資料集添加屋齡數值
                    compare_df['屋齡數值'] = compare_df['屋齡'].apply(parse_age)
                    
                    # 取得目標屋齡
                    target_age = parse_age(selected_row['屋齡'])
                    
                    # 移除 NaN 值
                    df_filtered_age = compare_df.dropna(subset=['屋齡數值'])
                    
                    if len(df_filtered_age) > 0 and not pd.isna(target_age):
                        # 基本統計
                        median_age = df_filtered_age['屋齡數值'].median()
                        mean_age = df_filtered_age['屋齡數值'].mean()
                        min_age = df_filtered_age['屋齡數值'].min()
                        max_age = df_filtered_age['屋齡數值'].max()
                        age_percentile = (df_filtered_age['屋齡數值'] < target_age).sum() / len(df_filtered_age) * 100
                        
                        # 簡單分類
                        if age_percentile <= 33:
                            age_category = "偏新"
                        elif age_percentile <= 66:
                            age_category = "主流"
                        else:
                            age_category = "偏舊"
                        
                        # ========== 定義屋齡區間（bins） ==========
                        bin_width = 5  # 每個區間 5 年
                        bins = np.arange(0, max_age + bin_width, bin_width)
                        
                        # 為資料添加屋齡區間
                        df_filtered_age['屋齡區間'] = pd.cut(
                            df_filtered_age['屋齡數值'], 
                            bins=bins, 
                            include_lowest=True
                        )
                        
                        # 確保有總價和建坪欄位
                        if '總價(萬)' in df_filtered_age.columns:
                            df_filtered_age['總價'] = pd.to_numeric(df_filtered_age['總價(萬)'], errors='coerce')
                        elif '總價' in df_filtered_age.columns:
                            df_filtered_age['總價'] = pd.to_numeric(df_filtered_age['總價'], errors='coerce')
                        else:
                            df_filtered_age['總價'] = 0
                        
                        if '建坪' in df_filtered_age.columns:
                            df_filtered_age['建坪數值'] = pd.to_numeric(df_filtered_age['建坪'], errors='coerce')
                        elif '建物面積' in df_filtered_age.columns:
                            df_filtered_age['建坪數值'] = pd.to_numeric(df_filtered_age['建物面積'], errors='coerce')
                        else:
                            df_filtered_age['建坪數值'] = 0
                        
                        # 計算建坪單價
                        df_valid_price = df_filtered_age[(df_filtered_age['總價'] > 0) & (df_filtered_age['建坪數值'] > 0)].copy()
                        df_valid_price['建坪單價'] = df_valid_price['總價'] / df_filtered_age['建坪數值']
                        
                        # 目標房屋的建坪單價
                        target_building_area = pd.to_numeric(selected_row.get('建坪', selected_row.get('建物面積', 0)), errors='coerce')
                        target_building_price_per_ping = target_price / target_building_area if target_building_area > 0 else 0
                        
                        # 同屋齡區間的平均建坪單價
                        avg_price_per_age_group = df_valid_price.groupby('屋齡區間', observed=True)['建坪單價'].mean()
                        target_age_group = pd.cut([target_age], bins=bins, include_lowest=True)[0]
                        same_age_avg_price = avg_price_per_age_group.get(target_age_group, np.nan)
                        
                        # 整體市場建坪單價統計
                        overall_avg_building_price = df_valid_price['建坪單價'].mean()
                        overall_median_building_price = df_valid_price['建坪單價'].median()
                        
                        # 單價隨屋齡的變化率（線性回歸斜率）
                        from scipy import stats
                        if len(df_valid_price) > 1:
                            slope, intercept, r_value, p_value, std_err = stats.linregress(
                                df_valid_price['屋齡數值'], 
                                df_valid_price['建坪單價']
                            )
                            price_decline_per_year = slope  # 每增加1年屋齡，單價變化（通常為負值）
                            correlation = r_value  # 相關係數
                        else:
                            price_decline_per_year = 0
                            correlation = 0
                        
                        # 找出最高價和最低價的屋齡區間
                        if len(avg_price_per_age_group) > 0:
                            highest_price_age_group = avg_price_per_age_group.idxmax()
                            lowest_price_age_group = avg_price_per_age_group.idxmin()
                            highest_price_value = avg_price_per_age_group.max()
                            lowest_price_value = avg_price_per_age_group.min()
                            price_range_by_age = highest_price_value - lowest_price_value
                        else:
                            highest_price_age_group = None
                            lowest_price_age_group = None
                            highest_price_value = 0
                            lowest_price_value = 0
                            price_range_by_age = 0
                        
                        # 目標房屋在同屋齡區間的單價排名
                        if not pd.isna(same_age_avg_price) and same_age_avg_price > 0:
                            price_vs_same_age = target_building_price_per_ping - same_age_avg_price
                            price_vs_same_age_pct = (price_vs_same_age / same_age_avg_price) * 100
                        else:
                            price_vs_same_age = 0
                            price_vs_same_age_pct = 0
                        
                        # 建立 age_analysis_payload
                        age_analysis_payload = {
                            "區域": target_district,
                            "房屋類型": target_type,
                            "比較樣本數": len(df_filtered_age),
                            
                            "目標房屋": {
                                "屋齡(年)": round(target_age, 1),
                                "建坪單價(萬/坪)": round(target_building_price_per_ping, 2)
                            },
                            
                            "屋齡分布": {
                                "屋齡百分位": round(age_percentile, 1),
                                "屋齡評估": age_category,
                                "新於物件比例(%)": round(100 - age_percentile, 1),
                                "同區平均屋齡(年)": round(mean_age, 1),
                                "同區中位數屋齡(年)": round(median_age, 1),
                                "屋齡範圍": f"{min_age:.1f} ~ {max_age:.1f} 年",
                                "與中位數差距(年)": round(target_age - median_age, 1)
                            },
                            
                            "建坪單價分析": {
                                "同區平均建坪單價(萬/坪)": round(overall_avg_building_price, 2),
                                "同區中位數建坪單價(萬/坪)": round(overall_median_building_price, 2),
                                "同屋齡區間平均建坪單價(萬/坪)": round(same_age_avg_price, 2) if not pd.isna(same_age_avg_price) else "無資料",
                                "與同屋齡區間差距(萬/坪)": round(price_vs_same_age, 2),
                                "與同屋齡區間差距比例(%)": round(price_vs_same_age_pct, 1)
                            },
                            
                            "單價與屋齡關聯": {
                                "單價隨屋齡變化率(萬/坪/年)": round(price_decline_per_year, 3),
                                "相關係數": round(correlation, 3),
                                "最高單價屋齡區間": str(highest_price_age_group) if highest_price_age_group else "無資料",
                                "最高單價(萬/坪)": round(highest_price_value, 2),
                                "最低單價屋齡區間": str(lowest_price_age_group) if lowest_price_age_group else "無資料",
                                "最低單價(萬/坪)": round(lowest_price_value, 2),
                                "單價波動範圍(萬/坪)": round(price_range_by_age, 2)
                            }
                        }
                        
                        # ========== 優化的 Prompt ==========
                        age_prompt = f"""
                        以下是「已經計算完成」的屋齡分析數據（JSON），
                        請 **只根據提供的數值進行說明**，不可自行推算或補充不存在的數據。
                        請用繁體中文完成以下分析（每項不超過 50 字）：
                        1️⃣ **屋齡評估**：評價該房屋的屋齡狀態（{age_analysis_payload['屋齡分布']['屋齡評估']}）及在市場中的位置
                        2️⃣ **價值分析**：
                           - 說明該房屋建坪單價與同屋齡區間平均的比較
                           - 解釋單價隨屋齡變化的趨勢（每年約變化 {price_decline_per_year:.2f} 萬/坪）
                        3️⃣ **購屋建議**：
                           - 屋齡帶來的維護成本考量
                           - 是否適合購買及需注意事項
                        屋齡分析數據如下：
                        {json.dumps(age_analysis_payload, ensure_ascii=False, indent=2)}
                        """


                
                        
                with st.spinner("🧠AI 正在解讀圖表並產生分析結論..."):
                    # price_response = model.generate_content(price_prompt)
                    # space_response = model.generate_content(space_prompt)
                    # age_response = model.generate_content(age_prompt)
                    price_response = type("obj", (object,), {"text":"❌ AI 分析已暫時關閉"})()
                    space_response = type("obj", (object,), {"text":"❌ AI 分析已暫時關閉"})()
                    age_response = type("obj", (object,), {"text":"❌ AI 分析已暫時關閉"})()
                    
                st.success("✅ 分析完成")
                st.header("🏡 房屋分析說明 ")
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
                    st.markdown("### 📌 價格分析結論")
                    st.write(price_response.text)
                st.markdown("---")

                st.subheader("坪數 📐")
                col1, col2 = st.columns([1, 1])
                
                with col1:
                    st.markdown("### 📌 坪數分析結論")
                    st.write(space_response.text)
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
                # 取得比較資料
                compare_base_df = pd.DataFrame()
                if 'all_properties_df' in st.session_state and not st.session_state.all_properties_df.empty:
                    compare_base_df = st.session_state.all_properties_df
                elif 'filtered_df' in st.session_state and not st.session_state.filtered_df.empty:
                    compare_base_df = st.session_state.filtered_df
                st.markdown("### 📌 屋齡分析結論")
                st.write(age_response.text)
                if not compare_base_df.empty:
                    plot_age_distribution(selected_row, compare_base_df)
                else:
                    st.warning("⚠️ 找不到比較基準資料，無法顯示圖表")
                st.markdown("---")
                
                st.subheader("樓層 🏢")
                # 取得比較資料
                compare_base_df = pd.DataFrame()
                if 'all_properties_df' in st.session_state and not st.session_state.all_properties_df.empty:
                    compare_base_df = st.session_state.all_properties_df
                elif 'filtered_df' in st.session_state and not st.session_state.filtered_df.empty:
                    compare_base_df = st.session_state.filtered_df
                st.markdown("### 📌 樓層分析結論")
                st.write(age_response.text)
                if not compare_base_df.empty:
                    plot_floor_distribution(selected_row, compare_base_df)
                else:
                    st.warning("⚠️ 找不到比較基準資料，無法顯示圖表")
                st.markdown("---")
                
                st.subheader("格局 🛋")
                st.markdown("---")
                
                st.subheader("地段 🗺")
                st.markdown("---")
                
            except Exception as e:
                st.error(f"❌ 分析過程發生錯誤：{e}")
