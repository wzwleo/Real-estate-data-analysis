import streamlit as st
import pandas as pd
import google.generativeai as genai
import os
import plotly.graph_objects as go
import plotly.express as px
import json
import re
import numpy as np
import time
from scipy import stats

try:
    from components.favorites import FavoritesManager, normalize_property_id
except ImportError:
    from favorites import FavoritesManager, normalize_property_id

# 在檔案開頭, name_map 下方加入反向對照表
name_map = {
    "Taichung-city_buy_properties.csv": "台中市",
}
# 建立反向對照表: 中文 -> 英文檔名
reverse_name_map = {v: k for k, v in name_map.items()}

import plotly.graph_objects as go

def create_radar_chart(scores_dict, title="房屋綜合評分雷達圖"):
    """
    生成五大面向雷達圖
    
    Parameters
    ----------
    scores_dict : dict
        五大面向分數，例如：
        {
            "價格競爭力": 7.5,
            "空間效率": 6.0,
            "屋齡優勢": 8.0,
            "樓層定位": 5.5,
            "格局流動性": 7.0
        }
        
    title : str
        圖表標題
    
    Returns
    -------
    fig : plotly.graph_objects.Figure
    """

    categories = list(scores_dict.keys())
    values = list(scores_dict.values())

    # 雷達圖需要首尾相接
    categories.append(categories[0])
    values.append(values[0])

    fig = go.Figure()

    fig.add_trace(go.Scatterpolar(
        r=values,
        theta=categories,
        fill='toself',
        name='評分'
    ))

    fig.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, 10]
            )
        ),
        showlegend=False,
        title=title
    )

    return fig

def plot_layout_distribution(target_row, df, chart_key=None):
    """
    繪製同區同類型格局分布與平均單價圖
    顯示前五大熱門格局，若目標房型在其中則標示紅星
    
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
    
    # ========== 解析格局 ==========
    def parse_layout(text):
        text = str(text)
        result = {
            '房數': 0,
            '廳數': 0,
            '衛數': 0,
            '室數': 0
        }
        for key in result.keys():
            match = re.search(rf'(\d+){key[0]}', text)
            if match:
                result[key] = int(match.group(1))
        return pd.Series(result)
    
    df_layout = df_filtered.copy()
    df_layout[['房數', '廳數', '衛數', '室數']] = df_layout['格局'].apply(parse_layout)
    
    # 確保有總價和建坪欄位
    if '總價(萬)' in df_layout.columns:
        df_layout['總價'] = pd.to_numeric(df_layout['總價(萬)'], errors='coerce')
    elif '總價' in df_layout.columns:
        df_layout['總價'] = pd.to_numeric(df_layout['總價'], errors='coerce')
    else:
        df_layout['總價'] = 0
    
    if '建坪' in df_layout.columns:
        df_layout['建坪數值'] = pd.to_numeric(df_layout['建坪'], errors='coerce')
    elif '建物面積' in df_layout.columns:
        df_layout['建坪數值'] = pd.to_numeric(df_layout['建物面積'], errors='coerce')
    else:
        df_layout['建坪數值'] = 0
    
    # 計算單價
    df_valid = df_layout[(df_layout['總價'] > 0) & (df_layout['建坪數值'] > 0)].copy()
    
    if len(df_valid) == 0:
        st.info("ℹ️ 無足夠有效價格資料進行分析")
        return
    
    df_valid['單價'] = df_valid['總價'] / df_valid['建坪數值']
    
    # ========== 計算每個格局出現次數 ==========
    layout_counts = df_valid['格局'].value_counts()
    
    # 前五名格局
    top5_layouts = layout_counts.head(5).index.tolist()
    
    if len(top5_layouts) == 0:
        st.info("ℹ️ 無足夠格局資料進行分析")
        return
    
    # 過濾只保留前五名
    df_top5 = df_valid[df_valid['格局'].isin(top5_layouts)]
    
    # 計算統計：數量 + 平均單價
    layout_stats = df_top5.groupby('格局').agg(
        數量=('標題', 'count'),
        平均單價=('單價', 'mean')
    ).reset_index()
    
    # 排序（按數量由多到少）
    layout_stats = layout_stats.sort_values('數量', ascending=False)
    
    # ========== 取得目標格局 ==========
    target_layout = target_row.get('格局', None)
    target_in_top5 = target_layout in top5_layouts if target_layout else False
    
    # ========== 繪製圖表 ==========
    fig = go.Figure()
    
    # 長條圖：數量
    fig.add_trace(go.Bar(
        x=layout_stats['格局'],
        y=layout_stats['數量'],
        name='物件數量',
        marker=dict(color='lightblue', line=dict(color='black', width=1)),
        yaxis='y'
    ))
    
    # 🔴 如果目標格局在前五名，標示紅星
    if target_in_top5:
        target_layout_data = layout_stats[layout_stats['格局'] == target_layout].iloc[0]
        
        fig.add_trace(go.Scatter(
            x=[target_layout],
            y=[target_layout_data['數量']],
            mode="markers+text",
            marker=dict(symbol="star", size=16, color="red"),
            text=["目標房屋"],
            textposition="top center",
            name="目標房屋",
            yaxis='y',
            showlegend=True
        ))
    
    # 折線圖：平均單價
    fig.add_trace(go.Scatter(
        x=layout_stats['格局'],
        y=layout_stats['平均單價'],
        name='平均單價',
        yaxis='y2',
        mode='lines+markers',
        line=dict(color='orange', width=2),
        marker=dict(size=10, color='orange'),
        hovertemplate='<b>%{x}</b><br>平均單價: %{y:.2f} 萬/坪<extra></extra>'
    ))
    
    # ========== 雙軸設定 ==========
    fig.update_layout(
        title=f"{target_district} 包含「{target_type_main}」的房型 前五格局供給與平均單價 (共 {len(df_valid)} 筆)",
        xaxis_title='格局',
        yaxis=dict(
            title='物件數量',
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
    
    st.plotly_chart(fig, use_container_width=True, key=chart_key)

def plot_floor_distribution(target_row, df, chart_key=None):
    """
    繪製同區同類型樓層分布直方圖（含平均單價趨勢線）
    與 plot_age_distribution 架構完全一致
    """

    if isinstance(df, pd.Series):
        df = pd.DataFrame([df])

    df = df.copy()

    # ========= 樓層字串 → 數字 =========
    def parse_floor(x):
        if pd.isna(x):
            return np.nan
        try:
            return int(str(x).split('樓')[0])
        except:
            return np.nan

    df['樓層數值'] = df['樓層'].apply(parse_floor)

    # ========= 類型清理 =========
    if '類型' in df.columns:
        df['類型'] = df['類型'].astype(str).str.strip()

    target_district = target_row.get('行政區')
    target_type = target_row.get('類型')

    if not target_district or not target_type:
        st.warning("⚠️ 缺少行政區或類型資訊")
        return

    target_type_main = target_type.split('/')[0].strip()

    # ========= 篩選同區同類型 =========
    df_filtered = df[
        (df['行政區'] == target_district) &
        (df['類型'].str.contains(target_type_main, case=False, na=False))
    ].copy()

    if len(df_filtered) == 0:
        st.info("ℹ️ 無符合條件資料")
        return

    # ========= 目標樓層 =========
    target_floor = parse_floor(target_row.get('樓層'))
    if pd.isna(target_floor):
        st.warning("⚠️ 目標房屋缺少樓層資訊")
        return

    # ========= 有效樓層 =========
    floors = df_filtered['樓層數值'].dropna().values
    if len(floors) == 0:
        st.info("ℹ️ 無足夠樓層資料")
        return

    # ========= 分箱（每 5 樓） =========
    bin_width = 5
    bins = np.arange(0, floors.max() + bin_width, bin_width)

    hist, bin_edges = np.histogram(floors, bins=bins)

    x_labels = [
        f"{int(bin_edges[i])}-{int(bin_edges[i+1])} 樓"
        for i in range(len(hist))
    ]

    # ========= 計算平均單價 =========
    if '總價(萬)' in df_filtered.columns:
        df_filtered['總價'] = pd.to_numeric(df_filtered['總價(萬)'], errors='coerce')
    else:
        df_filtered['總價'] = pd.to_numeric(df_filtered.get('總價', 0), errors='coerce')

    if '建坪' in df_filtered.columns:
        df_filtered['建坪數值'] = pd.to_numeric(df_filtered['建坪'], errors='coerce')
    else:
        df_filtered['建坪數值'] = pd.to_numeric(df_filtered.get('建物面積', 0), errors='coerce')

    df_valid = df_filtered[
        (df_filtered['總價'] > 0) &
        (df_filtered['建坪數值'] > 0)
    ].copy()

    df_valid['單價'] = df_valid['總價'] / df_valid['建坪數值']

    df_valid['樓層區間'] = pd.cut(
        df_valid['樓層數值'],
        bins=bins,
        labels=x_labels,
        include_lowest=True
    )

    avg_price = df_valid.groupby('樓層區間', observed=True)['單價'].mean()

    y_price = [avg_price.get(label, None) for label in x_labels]

    # ========= 建圖 =========
    fig = go.Figure()

    # 柱狀圖：數量
    fig.add_trace(go.Bar(
        x=x_labels,
        y=hist,
        name="房屋數量",
        marker=dict(color='lightblue', line=dict(color='black', width=1)),
        yaxis='y'
    ))

    # 🔴 目標樓層紅星（關鍵）
    target_bin_index = np.digitize(target_floor, bins) - 1

    if 0 <= target_bin_index < len(hist):
        fig.add_trace(go.Scatter(
            x=[x_labels[target_bin_index]],
            y=[hist[target_bin_index]],
            mode="markers+text",
            marker=dict(symbol="star", size=16, color="red"),
            text=["目標房屋"],
            textposition="top center",
            name="目標房屋",
            yaxis='y'
        ))

    # 折線：平均單價
    fig.add_trace(go.Scatter(
        x=x_labels,
        y=y_price,
        mode='lines+markers',
        name='平均單價',
        line=dict(color='orange', width=2),
        marker=dict(size=8, color='orange'),
        yaxis='y2',
        hovertemplate='<b>%{x}</b><br>平均單價: %{y:.2f} 萬/坪<extra></extra>'
    ))

    # ========= Layout =========
    fig.update_layout(
        title=f"{target_district}「{target_type_main}」樓層分布與單價趨勢 (共 {len(df_filtered)} 筆)",
        xaxis_title="樓層區間",
        yaxis=dict(title="房屋數量", showgrid=True),
        yaxis2=dict(title="平均單價 (萬/坪)", overlaying='y', side='right'),
        template="plotly_white",
        hovermode="x unified",
        width=600,
        height=500,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        )
    )

    st.plotly_chart(fig, use_container_width=True, key=chart_key)

def plot_age_distribution(target_row, df, chart_key=None):
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
    
    st.plotly_chart(fig, use_container_width=True, key=chart_key)
    

def plot_price_scatter(target_row, df, chart_key=None):
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
    
    st.plotly_chart(fig, key=chart_key)

def plot_space_efficiency_scatter(target_row, df, chart_key=None):
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
    
    st.plotly_chart(fig, key=chart_key)

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
        col1, col2 = st.columns([1, 1])
        with col1:
            analyze_clicked = st.button("開始分析", use_container_width=True, key="solo_analysis_button")
        with col2:    
            # 篩選出選中的房子
            selected_row = fav_df[fav_df['標題'] == choice].iloc[0]
            
            # ⭐ 新增：取得房產編號並生成連結
            property_id = selected_row.get('編號', '')
            if property_id:
                property_url = f"https://www.sinyi.com.tw/buy/house/{property_id}?breadcrumb=list"
                st.link_button("🏠 查看房產詳情", property_url, use_container_width=True)
        
        if analyze_clicked:
            if not gemini_key:
                st.error("❌ 右側 gemini API Key 有誤")
                st.stop()
            try:
                with st.spinner("📊 正在計算市場價格指標..."):
                    # ✅ 預設值，避免巢狀 if 未執行時 NameError
                    age_percentile = 50.0
                    floor_percentile = 50.0
                    same_layout_pct = 0.0
                    age_analysis_payload = None
                    floor_analysis_payload = None
                    layout_analysis_payload = None
                    age_response_text = "（無屋齡資料）"
                    floor_response_text = "（無樓層資料）"
                    layout_response_text = "（無格局資料）"
                    
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
                    target_usage_rate = selected_row['主+陽'] / float(selected_row['建坪']) if selected_row['建坪'] > 0 else 0
                    usage_percentile = (compare_df['空間使用率'] <= target_usage_rate).sum() / total_count * 100
                    median_usage = compare_df['空間使用率'].median()  # 同區中位數
                    mean_usage = compare_df['空間使用率'].mean()      # 同區平均使用率
                    actual_price_per_ping = target_price / target_area
                
                    floor_area_payload = {
                        "區域": target_district,
                        "房屋類型": target_type,
                        "比較樣本數": total_count,
                        "目標房屋": {
                            "建坪": selected_row['建坪'],
                            "實際坪數": selected_row['主+陽'],
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
                        
                        if len(df_valid_price) > 1:
                            unique_ages = df_valid_price['屋齡數值'].nunique()  # ✅ 新增
                            if unique_ages > 1:  # ✅ 新增
                                try:  # ✅ 新增
                                    slope, intercept, r_value, p_value, std_err = stats.linregress(
                                        df_valid_price['屋齡數值'], 
                                        df_valid_price['建坪單價']
                                    )
                                    price_decline_per_year = slope
                                    correlation = r_value
                                except Exception as e:  # ✅ 新增
                                    price_decline_per_year = 0
                                    correlation = 0
                            else:  # ✅ 新增
                                price_decline_per_year = 0
                                correlation = 0
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
                        # ===============================
                        # 樓層分析
                        # ===============================
                        # 樓層字串 → 數字
                        def parse_floor(x):
                            if pd.isna(x):
                                return np.nan
                            try:
                                return int(str(x).split('樓')[0])
                            except:
                                return np.nan
                        
                        compare_df['樓層數值'] = compare_df['樓層'].apply(parse_floor)
                        
                        # 取得目標樓層
                        target_floor = parse_floor(selected_row['樓層'])
                        
                        # 移除 NaN 值
                        df_filtered_floor = compare_df.dropna(subset=['樓層數值'])
                        
                        if len(df_filtered_floor) > 0 and not pd.isna(target_floor):
                            # 基本統計
                            median_floor = df_filtered_floor['樓層數值'].median()
                            mean_floor = df_filtered_floor['樓層數值'].mean()
                            min_floor = df_filtered_floor['樓層數值'].min()
                            max_floor = df_filtered_floor['樓層數值'].max()
                            floor_percentile = (df_filtered_floor['樓層數值'] < target_floor).sum() / len(df_filtered_floor) * 100
                            
                            # 簡單分類
                            if floor_percentile <= 33:
                                floor_category = "低樓層"
                            elif floor_percentile <= 66:
                                floor_category = "中樓層"
                            else:
                                floor_category = "高樓層"
                            
                            # ========== 定義樓層區間（bins） ==========
                            bin_width = 5  # 每個區間 5 層
                            bins = np.arange(0, max_floor + bin_width, bin_width)
                            
                            # 為資料添加樓層區間
                            df_filtered_floor['樓層區間'] = pd.cut(
                                df_filtered_floor['樓層數值'], 
                                bins=bins, 
                                include_lowest=True
                            )
                            
                            # 確保有總價和建坪欄位
                            if '總價(萬)' in df_filtered_floor.columns:
                                df_filtered_floor['總價'] = pd.to_numeric(df_filtered_floor['總價(萬)'], errors='coerce')
                            elif '總價' in df_filtered_floor.columns:
                                df_filtered_floor['總價'] = pd.to_numeric(df_filtered_floor['總價'], errors='coerce')
                            else:
                                df_filtered_floor['總價'] = 0
                            
                            if '建坪' in df_filtered_floor.columns:
                                df_filtered_floor['建坪數值'] = pd.to_numeric(df_filtered_floor['建坪'], errors='coerce')
                            elif '建物面積' in df_filtered_floor.columns:
                                df_filtered_floor['建坪數值'] = pd.to_numeric(df_filtered_floor['建物面積'], errors='coerce')
                            else:
                                df_filtered_floor['建坪數值'] = 0
                            
                            # 計算建坪單價
                            df_valid_floor = df_filtered_floor[(df_filtered_floor['總價'] > 0) & (df_filtered_floor['建坪數值'] > 0)].copy()
                            df_valid_floor['建坪單價'] = df_valid_floor['總價'] / df_valid_floor['建坪數值']
                            
                            # 目標房屋的建坪單價（使用前面計算過的）
                            # target_building_price_per_ping 已在屋齡分析中計算
                            
                            # 同樓層區間的平均建坪單價
                            avg_price_per_floor_group = df_valid_floor.groupby('樓層區間', observed=True)['建坪單價'].mean()
                            target_floor_group = pd.cut([target_floor], bins=bins, include_lowest=True)[0]
                            same_floor_avg_price = avg_price_per_floor_group.get(target_floor_group, np.nan)
                            
                            # 整體市場建坪單價統計（各樓層平均）
                            overall_avg_floor_price = df_valid_floor['建坪單價'].mean()
                            overall_median_floor_price = df_valid_floor['建坪單價'].median()
                            
                            # 單價隨樓層的變化率（線性回歸斜率）
                            if len(df_valid_floor) > 1:
                                unique_floors = df_valid_floor['樓層數值'].nunique()  # ✅ 新增
                                if unique_floors > 1:  # ✅ 新增
                                    try:  # ✅ 新增
                                        slope_floor, intercept_floor, r_value_floor, p_value_floor, std_err_floor = stats.linregress(
                                            df_valid_floor['樓層數值'], 
                                            df_valid_floor['建坪單價']
                                        )
                                        price_change_per_floor = slope_floor
                                        correlation_floor = r_value_floor
                                    except Exception as e:  # ✅ 新增
                                        price_change_per_floor = 0
                                        correlation_floor = 0
                                else:  # ✅ 新增
                                    price_change_per_floor = 0
                                    correlation_floor = 0
                            else:
                                price_change_per_floor = 0
                                correlation_floor = 0
                            
                            # 找出最高價和最低價的樓層區間
                            if len(avg_price_per_floor_group) > 0:
                                highest_price_floor_group = avg_price_per_floor_group.idxmax()
                                lowest_price_floor_group = avg_price_per_floor_group.idxmin()
                                highest_floor_price_value = avg_price_per_floor_group.max()
                                lowest_floor_price_value = avg_price_per_floor_group.min()
                                floor_price_range = highest_floor_price_value - lowest_floor_price_value
                            else:
                                highest_price_floor_group = None
                                lowest_price_floor_group = None
                                highest_floor_price_value = 0
                                lowest_floor_price_value = 0
                                floor_price_range = 0
                            
                            # 目標房屋在同樓層區間的單價排名
                            if not pd.isna(same_floor_avg_price) and same_floor_avg_price > 0:
                                price_vs_same_floor = target_building_price_per_ping - same_floor_avg_price
                                price_vs_same_floor_pct = (price_vs_same_floor / same_floor_avg_price) * 100
                            else:
                                price_vs_same_floor = 0
                                price_vs_same_floor_pct = 0
                            
                            # 建立 floor_analysis_payload
                            floor_analysis_payload = {
                                "區域": target_district,
                                "房屋類型": target_type,
                                "比較樣本數": len(df_filtered_floor),
                                
                                "目標房屋": {
                                    "樓層": int(target_floor),
                                    "所在樓層區間": str(target_floor_group),
                                    "建坪單價(萬/坪)": round(target_building_price_per_ping, 2)
                                },
                                
                                "樓層分布": {
                                    "樓層百分位": round(floor_percentile, 1),
                                    "樓層評估": floor_category,
                                    "高於物件比例(%)": round(floor_percentile, 1),
                                    "同區平均樓層": round(mean_floor, 1),
                                    "同區中位數樓層": round(median_floor, 1),
                                    "樓層範圍": f"{int(min_floor)} ~ {int(max_floor)} 樓",
                                    "與中位數差距(樓層)": round(target_floor - median_floor, 1)
                                },
                                
                                "建坪單價分析": {
                                    "同區平均建坪單價(萬/坪)": round(overall_avg_floor_price, 2),
                                    "同區中位數建坪單價(萬/坪)": round(overall_median_floor_price, 2),
                                    "同樓層區間平均建坪單價(萬/坪)": round(same_floor_avg_price, 2) if not pd.isna(same_floor_avg_price) else "無資料",
                                    "與同樓層區間差距(萬/坪)": round(price_vs_same_floor, 2),
                                    "與同樓層區間差距比例(%)": round(price_vs_same_floor_pct, 1)
                                },
                                
                                "單價與樓層關聯": {
                                    "單價隨樓層變化率(萬/坪/層)": round(price_change_per_floor, 3),
                                    "相關係數": round(correlation_floor, 3),
                                    "最高單價樓層區間": str(highest_price_floor_group) if highest_price_floor_group else "無資料",
                                    "最高單價(萬/坪)": round(highest_floor_price_value, 2),
                                    "最低單價樓層區間": str(lowest_price_floor_group) if lowest_price_floor_group else "無資料",
                                    "最低單價(萬/坪)": round(lowest_floor_price_value, 2),
                                    "單價波動範圍(萬/坪)": round(floor_price_range, 2)
                                }
                            }
                            
                            # ========== Prompt ==========
                            floor_prompt = f"""
                        
                        ---
                        
                        以下是「已經計算完成」的樓層分析數據（JSON），
                        請 **只根據提供的數值進行說明**，不可自行推算或補充不存在的數據。
                        
                        請用繁體中文完成以下分析（每項不超過 50 字）：
                        
                        1️⃣ **樓層評估**：評價該房屋的樓層位置（{floor_analysis_payload['樓層分布']['樓層評估']}）及在市場中的分布
                        
                        2️⃣ **價值分析**：
                           - 說明該房屋建坪單價與同樓層區間平均的比較
                           - 解釋單價隨樓層變化的趨勢（每層約變化 {price_change_per_floor:.2f} 萬/坪）
                        
                        3️⃣ **購屋建議**：
                           - 樓層帶來的優缺點（採光、噪音、景觀、逃生等）
                           - 是否適合購買及需注意事項
                        
                        樓層分析數據如下：
                        {json.dumps(floor_analysis_payload, ensure_ascii=False, indent=2)}
                        """
                            
                        # ===============================
                        # 格局分析
                        # ===============================
                        
                        # 解析格局
                        def parse_layout(text):
                            text = str(text)
                            result = {
                                '房數': 0,
                                '廳數': 0,
                                '衛數': 0,
                                '室數': 0
                            }
                            for key in result.keys():
                                match = re.search(rf'(\d+){key[0]}', text)
                                if match:
                                    result[key] = int(match.group(1))
                            return pd.Series(result)
                        
                        df_layout = compare_df.copy()
                        df_layout[['房數', '廳數', '衛數', '室數']] = df_layout['格局'].apply(parse_layout)
                        
                        # 過濾出有效格局資料（至少有房數）
                        df_layout = df_layout[df_layout['房數'] > 0].copy()
                        
                        if len(df_layout) > 0:
                            # 確保有總價和建坪欄位
                            if '總價(萬)' in df_layout.columns:
                                df_layout['總價'] = pd.to_numeric(df_layout['總價(萬)'], errors='coerce')
                            elif '總價' in df_layout.columns:
                                df_layout['總價'] = pd.to_numeric(df_layout['總價'], errors='coerce')
                            else:
                                df_layout['總價'] = 0
                            
                            if '建坪' in df_layout.columns:
                                df_layout['建坪數值'] = pd.to_numeric(df_layout['建坪'], errors='coerce')
                            elif '建物面積' in df_layout.columns:
                                df_layout['建坪數值'] = pd.to_numeric(df_layout['建物面積'], errors='coerce')
                            else:
                                df_layout['建坪數值'] = 0
                            
                            # 計算單價
                            df_valid_layout = df_layout[(df_layout['總價'] > 0) & (df_layout['建坪數值'] > 0)].copy()
                            df_valid_layout['單價'] = df_valid_layout['總價'] / df_valid_layout['建坪數值']
                            
                            # 取得目標格局
                            target_layout = selected_row.get('格局', None)
                            target_layout_parsed = parse_layout(target_layout) if target_layout else None
                            
                            if target_layout and not target_layout_parsed.isna().all():
                                target_rooms = int(target_layout_parsed['房數'])
                                target_baths = int(target_layout_parsed['衛數'])
                                target_living = int(target_layout_parsed['廳數'])
                                
                                # ========== 計算格局統計 ==========
                                
                                # 1. 格局出現次數排名
                                layout_counts = df_valid_layout['格局'].value_counts()
                                top5_layouts = layout_counts.head(5).index.tolist()
                                
                                # 目標格局是否在前五名
                                target_in_top5 = target_layout in top5_layouts
                                target_layout_rank = list(layout_counts.index).index(target_layout) + 1 if target_layout in layout_counts.index else None
                                target_layout_count = layout_counts.get(target_layout, 0)
                                
                                # 2. 前五名格局的統計
                                df_top5 = df_valid_layout[df_valid_layout['格局'].isin(top5_layouts)]
                                layout_stats = df_top5.groupby('格局').agg(
                                    數量=('標題', 'count'),
                                    平均單價=('單價', 'mean')
                                ).reset_index()
                                layout_stats = layout_stats.sort_values('數量', ascending=False)
                                
                                # 3. 同格局的統計
                                same_layout_df = df_valid_layout[df_valid_layout['格局'] == target_layout]
                                same_layout_avg_price = same_layout_df['單價'].mean() if len(same_layout_df) > 0 else np.nan
                                same_layout_count = len(same_layout_df)
                                same_layout_pct = (same_layout_count / len(df_valid_layout)) * 100
                                
                                # 4. 同房數的統計
                                same_rooms_df = df_valid_layout[df_valid_layout['房數'] == target_rooms]
                                same_rooms_avg_price = same_rooms_df['單價'].mean() if len(same_rooms_df) > 0 else np.nan
                                same_rooms_count = len(same_rooms_df)
                                same_rooms_pct = (same_rooms_count / len(df_valid_layout)) * 100
                                
                                # 5. 整體市場格局分布
                                avg_rooms = df_valid_layout['房數'].mean()
                                median_rooms = df_valid_layout['房數'].median()
                                avg_baths = df_valid_layout['衛數'].mean()
                                median_baths = df_valid_layout['衛數'].median()
                                avg_living = df_valid_layout['廳數'].mean()
                                
                                # 6. 計算每房平均坪數
                                df_valid_layout['每房平均坪數'] = df_valid_layout['建坪數值'] / df_valid_layout['房數']
                                target_per_room_area = target_building_area / target_rooms if target_rooms > 0 else 0
                                avg_per_room_area = df_valid_layout['每房平均坪數'].mean()
                                median_per_room_area = df_valid_layout['每房平均坪數'].median()
                                
                                # 7. 格局舒適度分類
                                def classify_layout_comfort(row):
                                    if row['房數'] <= 2 and row['衛數'] <= 1:
                                        return "小型格局"
                                    elif row['房數'] == 3 and row['衛數'] == 2:
                                        return "標準格局"
                                    elif row['房數'] >= 4 or row['衛數'] >= 3:
                                        return "豪華格局"
                                    else:
                                        return "其他格局"
                                
                                df_valid_layout['格局分類'] = df_valid_layout.apply(classify_layout_comfort, axis=1)
                                target_layout_category = classify_layout_comfort(pd.Series({
                                    '房數': target_rooms,
                                    '衛數': target_baths
                                }))
                                
                                # 8. 格局分類的市場分布
                                layout_category_dist = df_valid_layout['格局分類'].value_counts()
                                target_category_count = layout_category_dist.get(target_layout_category, 0)
                                target_category_pct = (target_category_count / len(df_valid_layout)) * 100
                                
                                # 9. 前五大格局的單價範圍
                                top5_prices = layout_stats['平均單價'].tolist()
                                highest_layout_in_top5 = layout_stats.iloc[0]['格局']
                                highest_price_in_top5 = layout_stats.iloc[0]['平均單價']
                                lowest_layout_in_top5 = layout_stats.iloc[-1]['格局']
                                lowest_price_in_top5 = layout_stats.iloc[-1]['平均單價']
                                top5_price_range = highest_price_in_top5 - lowest_price_in_top5
                                
                                # 10. 單價與房數的關聯
                                if len(df_valid_layout) > 1:
                                    unique_rooms = df_valid_layout['房數'].nunique()  # ✅ 新增
                                    if unique_rooms > 1:  # ✅ 新增
                                        try:  # ✅ 新增
                                            slope_layout, intercept_layout, r_value_layout, p_value_layout, std_err_layout = stats.linregress(
                                                df_valid_layout['房數'], 
                                                df_valid_layout['單價']
                                            )
                                            price_change_per_room = slope_layout
                                            correlation_layout = r_value_layout
                                        except Exception as e:  # ✅ 新增
                                            price_change_per_room = 0
                                            correlation_layout = 0
                                    else:  # ✅ 新增
                                        price_change_per_room = 0
                                        correlation_layout = 0
                                else:
                                    price_change_per_room = 0
                                    correlation_layout = 0
                                
                                # 11. 目標格局與同格局平均的比較
                                if not pd.isna(same_layout_avg_price) and same_layout_avg_price > 0:
                                    price_vs_same_layout = target_building_price_per_ping - same_layout_avg_price
                                    price_vs_same_layout_pct = (price_vs_same_layout / same_layout_avg_price) * 100
                                else:
                                    price_vs_same_layout = 0
                                    price_vs_same_layout_pct = 0
                                
                                # 建立 layout_analysis_payload
                                layout_analysis_payload = {
                                    "區域": target_district,
                                    "房屋類型": target_type,
                                    "比較樣本數": len(df_valid_layout),
                                    
                                    "目標房屋": {
                                        "格局": target_layout,
                                        "房數": target_rooms,
                                        "廳數": target_living,
                                        "衛數": target_baths,
                                        "格局分類": target_layout_category,
                                        "建坪單價(萬/坪)": round(target_building_price_per_ping, 2),
                                        "每房平均坪數": round(target_per_room_area, 2)
                                    },
                                    
                                    "格局排名": {
                                        "格局資料量排名": target_layout_rank if target_layout_rank else "未在排名中",
                                        "是否為前五多資料量格局": "是" if target_in_top5 else "否",
                                        "相同格局數量": same_layout_count,
                                        "相同格局占比(%)": round(same_layout_pct, 1),
                                        "資料量前五多格局": [
                                            {
                                                "格局": row['格局'],
                                                "數量": int(row['數量']),
                                                "平均單價(萬/坪)": round(row['平均單價'], 2)
                                            }
                                            for _, row in layout_stats.iterrows()
                                        ]
                                    },
                                    
                                    "格局分布": {
                                        "同區平均房數": round(avg_rooms, 1),
                                        "同區中位數房數": round(median_rooms, 1),
                                        "同區平均衛數": round(avg_baths, 1),
                                        "同房數物件數量": same_rooms_count,
                                        "同房數物件占比(%)": round(same_rooms_pct, 1),
                                        "格局分類占比(%)": round(target_category_pct, 1)
                                    },
                                    
                                    "空間效率": {
                                        "每房平均坪數": round(target_per_room_area, 2),
                                        "同區每房平均坪數": round(avg_per_room_area, 2),
                                        "同區每房中位數坪數": round(median_per_room_area, 2),
                                        "與市場平均差距(坪)": round(target_per_room_area - avg_per_room_area, 2)
                                    },
                                    
                                    "格局單價分析": {
                                        "相同格局平均單價(萬/坪)": round(same_layout_avg_price, 2) if not pd.isna(same_layout_avg_price) else "無資料",
                                        "同房數平均單價(萬/坪)": round(same_rooms_avg_price, 2) if not pd.isna(same_rooms_avg_price) else "無資料",
                                        "與同格局差距(萬/坪)": round(price_vs_same_layout, 2),
                                        "與同格局差距比例(%)": round(price_vs_same_layout_pct, 1),
                                        "前五大格局單價範圍(萬/坪)": round(top5_price_range, 2),
                                        "最高單價格局": highest_layout_in_top5,
                                        "最低單價格局": lowest_layout_in_top5
                                    },
                                    
                                    "單價與房數關聯": {
                                        "單價隨房數變化率(萬/坪/房)": round(price_change_per_room, 3),
                                        "相關係數": round(correlation_layout, 3)
                                    }
                                }
                                
                                # ========== Prompt ==========
                                layout_prompt = f"""
                        
                        ---
                        
                        以下是「已經計算完成」的格局分析數據（JSON），
                        請 **只根據提供的數值進行說明**，不可自行推算或補充不存在的數據。
                        
                        請用繁體中文完成以下分析（每項不超過 50 字）：
                        
                        1️⃣ **格局市場定位**：
                           - 說明該房屋格局（{layout_analysis_payload['目標房屋']['格局分類']}）在目前待售市場中的供給排序
                           - 目標格局「{target_layout}」排名第 {target_layout_rank if target_layout_rank else '未知'} 位
                           - {'屬於前五大主要供給類型' if target_in_top5 else '不屬於前五大主要供給類型'}
                        
                        2️⃣ **空間效率分析**：
                           - 說明每房平均坪數（{target_per_room_area:.2f} 坪/房）與市場平均（{avg_per_room_area:.2f} 坪/房）的比較
                           - 評估空間配置的合理性
                        
                        3️⃣ **單價分析**：
                           - 說明該房屋單價與相同格局平均單價的差異情形
                           - 解釋前五大主要供給類型之間的單價差距（範圍 {top5_price_range:.2f} 萬/坪）
                        
                        4️⃣ **購屋建議**：
                           - 格局帶來的優缺點（房數、衛數配置）
                           - 是否適合購買及需注意事項
                        
                        格局分析數據如下：
                        {json.dumps(layout_analysis_payload, ensure_ascii=False, indent=2)}
                        """
                        # ===============================
                        # 綜合總結 Prompt（新增）
                        # ===============================
                        
                        summary_prompt = f"""
                        你是一位專業的台灣房市分析顧問。
                        
                        你已經完成了以下五個面向的獨立分析：
                        1. 價格分析
                        2. 坪數分析  
                        3. 屋齡分析
                        4. 樓層分析
                        5. 格局分析
                        
                        現在請基於以下「已經計算完成」的所有數據，提供一個綜合總結。
                        
                        ---
                        
                        ## 📊 完整分析數據
                        
                        ### 1️⃣ 價格數據
                        {json.dumps(analysis_payload, ensure_ascii=False, indent=2)}
                        
                        ### 2️⃣ 坪數數據
                        {json.dumps(floor_area_payload, ensure_ascii=False, indent=2)}
                        
                        ### 3️⃣ 屋齡數據
                        {json.dumps(age_analysis_payload if age_analysis_payload else {}, ensure_ascii=False, indent=2)}
                        
                        ### 4️⃣ 樓層數據
                        {json.dumps(floor_analysis_payload if floor_analysis_payload else {}, ensure_ascii=False, indent=2)}
                        
                        ### 5️⃣ 格局數據
                        {json.dumps(layout_analysis_payload if layout_analysis_payload else {}, ensure_ascii=False, indent=2)}
                        ---
                        
                        ## 📝 請完成綜合總結（200 字內）
                        
                        請用繁體中文完成以下四個部分：
                        
                        **1. 整體評價**
                        - 綜合五個面向，給出一句話的整體評價
                        - 明確說明這間房屋的市場定位（例如：高性價比小家庭首選、主流價格帶標準物件等）
                        
                        **2. 三大優勢**
                        - 列出最明顯的 3 個優點
                        - 每個優點用一句話說明，並引用具體數據支持
                        
                        **3. 三大劣勢**
                        - 列出最需要注意的 3 個缺點或風險
                        - 每個缺點用一句話說明，並引用具體數據支持
                        
                        **4. 購屋建議**
                        - 給出明確的購買建議：「強烈推薦」、「值得考慮」、「需謹慎評估」或「不建議」
                        - 說明最適合的買家類型（例如：首購族、小家庭、退休族、投資客）
                        
                        ---
                        
                        ## ⚠️ 重要原則
                        
                        1. **只使用提供的數據**：不推測、不補充
                        2. **保持客觀中立**：不誇大優點，不隱瞞缺點
                        3. **給出明確判斷**：避免模糊用語
                        4. **嚴格字數限制**：各項字數不超過100字
                        5. **使用繁體中文**：符合台灣用語習慣
                        
                        請開始撰寫綜合總結。
                        """

                        combined_prompt = f"""
                        你是一位專業的台灣房市分析顧問。
                        請根據以下已完成的分析數據，一次輸出 JSON，鍵固定為：
                        price, space, age, floor, layout, summary。

                        規則：
                        1. 只輸出 JSON，不要加任何前言或 markdown。
                        2. 每個欄位都用繁體中文。
                        3. 每個欄位內容請控制在 60~120 字內，summary 可到 180 字。
                        4. 只根據提供數據，不補充不存在資訊。
                        5. 若某面向資料不足，請明確寫「資料不足，無法完整判斷」。

                        價格分析資料：
                        {json.dumps(analysis_payload, ensure_ascii=False, indent=2)}

                        坪數分析資料：
                        {json.dumps(floor_area_payload, ensure_ascii=False, indent=2)}

                        屋齡分析資料：
                        {json.dumps(age_analysis_payload if age_analysis_payload else {}, ensure_ascii=False, indent=2)}

                        樓層分析資料：
                        {json.dumps(floor_analysis_payload if floor_analysis_payload else {}, ensure_ascii=False, indent=2)}

                        格局分析資料：
                        {json.dumps(layout_analysis_payload if layout_analysis_payload else {}, ensure_ascii=False, indent=2)}
                        """

                def _build_local_ai_bundle():
                    price_pct = analysis_payload.get("價格分布", {}).get("價格百分位", 50)
                    if price_pct <= 33:
                        price_pos = "價格偏低"
                    elif price_pct <= 66:
                        price_pos = "價格落在主流帶"
                    else:
                        price_pos = "價格偏高"

                    usage_pct = floor_area_payload.get("坪數分布", {}).get("使用率百分位", 50)
                    if usage_pct <= 33:
                        space_pos = "空間效率偏低"
                    elif usage_pct <= 66:
                        space_pos = "空間效率中等"
                    else:
                        space_pos = "空間效率偏高"

                    age_eval = (age_analysis_payload or {}).get("屋齡分布", {}).get("屋齡評估", "資料不足")
                    floor_eval = (floor_analysis_payload or {}).get("樓層分布", {}).get("樓層評估", "資料不足")
                    layout_rank = (layout_analysis_payload or {}).get("格局排名", {}).get("格局資料量排名", "未知")
                    layout_share = (layout_analysis_payload or {}).get("格局排名", {}).get("相同格局占比(%)", "未知")
                    market_flag = analysis_payload.get("市場密集度", {}).get("是否位於主流價格帶", "未知")

                    return {
                        "price": f"{price_pos}，價格百分位約 {price_pct}% ，{market_flag}市場主流交易區間，可作為價格判斷參考。",
                        "space": f"{space_pos}，使用率百分位約 {usage_pct}% ，可與同區同類型物件互相比較坪效表現。",
                        "age": f"屋齡評估為{age_eval}，建議結合維護成本與後續整修需求一起評估，不宜只看總價。",
                        "floor": f"樓層定位屬於{floor_eval}，需搭配採光、通風、出入便利性與市場接受度一起判斷。",
                        "layout": f"格局供給排名第 {layout_rank}，相同格局占比約 {layout_share}% ，可作為流通性與市場接受度參考。",
                        "summary": f"本次分析改用本地規則摘要：價格面 {price_pos}、坪效面 {space_pos}、屋齡為{age_eval}、樓層為{floor_eval}。建議把總價、空間效率與後續持有成本一起看。"
                    }

                def _extract_json_candidates(raw_text):
                    text = (raw_text or "").strip()
                    if not text:
                        return []

                    candidates = [text]

                    fence_matches = re.findall(r"```(?:json)?\s*(.*?)\s*```", text, flags=re.DOTALL | re.IGNORECASE)
                    for block in fence_matches:
                        block = block.strip()
                        if block:
                            candidates.append(block)

                    first_brace = text.find("{")
                    if first_brace != -1:
                        depth = 0
                        start = None
                        for i in range(first_brace, len(text)):
                            ch = text[i]
                            if ch == "{":
                                if depth == 0:
                                    start = i
                                depth += 1
                            elif ch == "}":
                                depth -= 1
                                if depth == 0 and start is not None:
                                    candidates.append(text[start:i+1].strip())
                                    break

                    deduped = []
                    seen = set()
                    for item in candidates:
                        if item not in seen:
                            deduped.append(item)
                            seen.add(item)
                    return deduped

                def _normalize_ai_bundle(candidate, fallback_bundle):
                    required_keys = ["price", "space", "age", "floor", "layout", "summary"]
                    if not isinstance(candidate, dict):
                        return None, "AI 回傳不是 JSON 物件"

                    normalized = {}
                    non_empty_count = 0
                    missing_keys = []

                    for key in required_keys:
                        value = candidate.get(key)
                        if isinstance(value, str):
                            value = value.strip()
                        elif isinstance(value, (dict, list)):
                            value = json.dumps(value, ensure_ascii=False)
                        elif value is None:
                            value = ""
                        else:
                            value = str(value).strip()

                        if value:
                            non_empty_count += 1
                        else:
                            missing_keys.append(key)
                            value = fallback_bundle[key]

                        normalized[key] = value

                    if non_empty_count == 0:
                        return None, "AI JSON 缺少有效內容"

                    note = None
                    if missing_keys:
                        note = f"AI JSON 缺少欄位，已用本地摘要補齊：{', '.join(missing_keys)}"
                    return normalized, note

                def _parse_ai_bundle(raw_text, fallback_bundle):
                    parse_errors = []
                    for candidate_text in _extract_json_candidates(raw_text):
                        try:
                            parsed = json.loads(candidate_text)
                        except Exception as e:
                            parse_errors.append(f"JSON 解析失敗：{e}")
                            continue

                        normalized, note = _normalize_ai_bundle(parsed, fallback_bundle)
                        if normalized is not None:
                            return normalized, note, parse_errors

                        if note:
                            parse_errors.append(note)

                    if not raw_text or not raw_text.strip():
                        parse_errors.append("AI 沒有回傳文字")
                    else:
                        parse_errors.append("找不到可解析的 JSON 區塊")
                    return None, None, parse_errors

                compact_prompt = f"""
                你是台灣房市分析顧問。只輸出 JSON，鍵固定為 price, space, age, floor, layout, summary。
                每個值控制在 45~90 字，summary 不超過 120 字。
                價格：{json.dumps(analysis_payload, ensure_ascii=False)}
                坪數：{json.dumps(floor_area_payload, ensure_ascii=False)}
                屋齡：{json.dumps(age_analysis_payload if age_analysis_payload else {}, ensure_ascii=False)}
                樓層：{json.dumps(floor_analysis_payload if floor_analysis_payload else {}, ensure_ascii=False)}
                格局：{json.dumps(layout_analysis_payload if layout_analysis_payload else {}, ensure_ascii=False)}
                """

                with st.spinner("🧠AI 正在解讀圖表並產生分析結論..."):
                    genai.configure(api_key=gemini_key)
                    fallback_bundle = _build_local_ai_bundle()
                    ai_bundle = None
                    gemini_errors = []
                    gemini_debug_logs = []
                    gemini_notes = []

                    for prompt_name, prompt_text, max_tokens in [
                        ("完整版", combined_prompt, 1000),
                        ("精簡版", compact_prompt, 700),
                    ]:
                        try:
                            response = model.generate_content(
                                prompt_text,
                                generation_config={
                                    "temperature": 0.3,
                                    "max_output_tokens": max_tokens,
                                    "response_mime_type": "application/json",
                                },
                            )
                            raw_response_text = getattr(response, "text", "")
                            ai_bundle, note, parse_errors = _parse_ai_bundle(raw_response_text, fallback_bundle)

                            gemini_debug_logs.append({
                                "prompt_name": prompt_name,
                                "raw_response": raw_response_text,
                                "parse_errors": parse_errors,
                            })

                            if note:
                                gemini_notes.append(note)

                            if ai_bundle:
                                break

                            if parse_errors:
                                gemini_errors.append(parse_errors[-1])
                            else:
                                gemini_errors.append("AI 回傳格式異常")
                        except Exception as gemini_error:
                            gemini_errors.append(str(gemini_error))
                            gemini_debug_logs.append({
                                "prompt_name": prompt_name,
                                "raw_response": "",
                                "parse_errors": [str(gemini_error)],
                            })
                            time.sleep(1.2)

                    if ai_bundle is None:
                        ai_bundle = fallback_bundle
                        if gemini_errors:
                            st.warning("⚠️ AI 服務逾時或回傳異常，已改用本地規則摘要。")
                            st.caption(f"最後一次 Gemini 錯誤：{gemini_errors[-1]}")
                    elif gemini_notes:
                        st.info(f"ℹ️ {gemini_notes[-1]}")

                    if gemini_debug_logs and (gemini_errors or gemini_notes):
                        with st.expander("🔍 查看 Gemini 原始回應與解析紀錄", expanded=False):
                            for idx, log in enumerate(gemini_debug_logs, start=1):
                                st.markdown(f"**第 {idx} 次嘗試：{log['prompt_name']}**")
                                if log["parse_errors"]:
                                    for err in log["parse_errors"]:
                                        st.caption(f"解析訊息：{err}")
                                raw_text = log["raw_response"] or "（無回應文字）"
                                st.code(raw_text, language="json")

                    price_text = ai_bundle.get("price", "資料不足，無法完整判斷。")
                    space_text = ai_bundle.get("space", "資料不足，無法完整判斷。")
                    age_text = ai_bundle.get("age", "資料不足，無法完整判斷。")
                    floor_text = ai_bundle.get("floor", "資料不足，無法完整判斷。")
                    layout_text = ai_bundle.get("layout", "資料不足，無法完整判斷。")
                    summary_text = ai_bundle.get("summary", "資料不足，無法完整判斷。")
                    
                # ── ✅ 在 session_state 存入前先算好分數 ──────────────────────────
                # 給還沒算到的變數加預設值，避免 NameError
                if 'age_percentile' not in dir():
                    age_percentile = 50.0
                if 'floor_percentile' not in dir():
                    floor_percentile = 50.0
                if 'median_usage' not in dir() or median_usage == 0:
                    median_usage = 1.0
                if 'same_layout_pct' not in dir():
                    same_layout_pct = 0.0
                
                score_price = max(0, min(10, 10 - price_percentile / 10))
                score_space = max(0, min(10, (target_usage_rate / median_usage) * 5))
                score_age   = max(0, min(10, 10 - age_percentile / 10))
                score_floor = max(0, min(10, 10 - abs(floor_percentile - 50) / 5))
                score_layout = max(0, min(10, same_layout_pct / 3))
                
                scores = {
                    "價格競爭力": round(score_price, 1),
                    "空間效率":   round(score_space, 1),
                    "屋齡優勢":   round(score_age, 1),
                    "樓層定位":   round(score_floor, 1),
                    "格局流動性": round(score_layout, 1)
                }
                total_score = sum(scores.values()) / len(scores) * 10 
                
                # ✅ 分析完成後，存進 session_state
                st.session_state['solo_analysis_result'] = {
                    'price_text':             price_text,
                    'space_text':             space_text,
                    'age_text':               age_text,
                    'floor_text':             floor_text,
                    'layout_text':            layout_text,
                    'summary_text':           summary_text,
                    'scores':                 scores,
                    'total_score':            total_score,
                    'analysis_payload':       analysis_payload,
                    'floor_area_payload':     floor_area_payload,
                    'age_analysis_payload':   age_analysis_payload,
                    'floor_analysis_payload': floor_analysis_payload,
                    'layout_analysis_payload':layout_analysis_payload,
                    'selected_row':           selected_row.to_dict(),
                    'compare_base_df': (
                        all_df.to_dict('records')
                        if all_df is not None and not all_df.empty
                        else []
                    ),
                }
            except Exception as e:
                st.error(f"❌ 分析過程發生錯誤：{e}")
        
        # ── ✅ 渲染區塊：只要 session_state 有結果就顯示，不依賴 analyze_clicked ──
        if 'solo_analysis_result' in st.session_state:
            r = st.session_state['solo_analysis_result']
    
            # 還原資料（用於重新繪圖）
            _selected_row = pd.Series(r['selected_row'])
            _compare_df = pd.DataFrame(r['compare_base_df'])
    
            st.success("✅ 分析完成")
            st.header("🏡 房屋分析說明")
            st.write("我們將針對所選房屋的五大面向逐一分析，包括價格、坪數、屋齡、樓層與格局。每項分析都結合市場資料與 AI 評估，提供清楚、可理解的參考資訊。")
            st.markdown("---")
    
            # ── 價格 ──
            st.subheader("價格 💸")
            col1, col2 = st.columns([1, 1])
            with col1:
                if not _compare_df.empty:
                    plot_price_scatter(_selected_row, _compare_df)
                else:
                    st.warning("⚠️ 找不到比較基準資料，無法顯示圖表")
            with col2:
                st.markdown("### 📌 價格分析結論")
                st.write(r['price_text'])
            st.markdown("---")
    
            # ── 坪數 ──
            st.subheader("坪數 📐")
            col1, col2 = st.columns([1, 1])
            with col1:
                st.markdown("### 📌 坪數分析結論")
                st.write(r['space_text'])
            with col2:
                if not _compare_df.empty:
                    plot_space_efficiency_scatter(_selected_row, _compare_df)
                else:
                    st.warning("⚠️ 找不到比較基準資料，無法顯示圖表")
            st.markdown("---")
    
            # ── 屋齡 ──
            st.subheader("屋齡 🕰")
            st.markdown("### 📌 屋齡分析結論")
            st.write(r['age_text'])
            if not _compare_df.empty:
                plot_age_distribution(_selected_row, _compare_df)
            else:
                st.warning("⚠️ 找不到比較基準資料，無法顯示圖表")
            st.markdown("---")
    
            # ── 樓層 ──
            st.subheader("樓層 🏢")
            st.markdown("### 📌 樓層分析結論")
            st.write(r['floor_text'])
            if not _compare_df.empty:
                plot_floor_distribution(_selected_row, _compare_df)
            else:
                st.warning("⚠️ 找不到比較基準資料，無法顯示圖表")
            st.markdown("---")
    
            # ── 格局 ──
            st.subheader("格局 🛋")
            st.markdown("### 📌 格局分析結論")
            st.write(r['layout_text'])
            if not _compare_df.empty:
                plot_layout_distribution(_selected_row, _compare_df)
            else:
                st.warning("⚠️ 找不到比較基準資料，無法顯示圖表")
            st.markdown("---")
    
            # ── 最終結論 & 雷達圖 ──
            st.markdown("### 📌 最終結論")
            st.write(r['summary_text'])
    
            col1, col2 = st.columns([1, 1])
            with col1:
                fig = create_radar_chart(r['scores'])
                st.plotly_chart(fig)
            with col2:
                st.markdown(
                    f"""
                    <h1 style='color:#00C853; font-size:60px; text-align:center; margin-top:170px;'>
                    {r['total_score']:.1f} / 100
                    </h1>
                    """,
                    unsafe_allow_html=True
                )
            
            # ── 儲存按鈕 ──
            st.markdown("---")
            scores = r['scores']
            col1, col2, col3 = st.columns([1, 1, 1])
            with col2:
                save_button = st.button("💾 儲存本次分析結果", use_container_width=True, type="primary", key="save_analysis")

            if save_button:
                if 'ai_results' not in st.session_state:
                    st.session_state.ai_results = []
                if "ai_results_summary" not in st.session_state:
                    st.session_state.ai_results_summary = []
                if "analysis_store" not in st.session_state:
                    st.session_state.analysis_store = {}

                property_id = normalize_property_id(selected_row.get('編號', ''))
                basic_info = {
                    '編號': property_id,
                    '標題': selected_row.get('標題', '未提供'),
                    '類型': selected_row.get('類型', '未提供'),
                    '地址': selected_row.get('地址', '未提供'),
                    '行政區': selected_row.get('行政區', '未提供'),
                    '建坪': selected_row.get('建坪', '未提供'),
                    '實際坪數': selected_row.get('主+陽', '未提供'),
                    '格局': selected_row.get('格局', '未提供'),
                    '樓層': selected_row.get('樓層', '未提供'),
                    '屋齡': selected_row.get('屋齡', '未提供'),
                    '車位': selected_row.get('車位', '未提供'),
                    '總價': selected_row.get('總價(萬)', '未提供'),
                }
                texts = {
                    'price': r['price_text'],
                    'space': r['space_text'],
                    'age': r['age_text'],
                    'floor': r['floor_text'],
                    'layout': r['layout_text'],
                    'summary': r['summary_text'],
                }
                analysis_data = {
                    'price_data': r['analysis_payload'],
                    'space_data': r['floor_area_payload'],
                    'age_data': r['age_analysis_payload'],
                    'floor_data': r['floor_analysis_payload'],
                    'layout_data': r['layout_analysis_payload'],
                }
                analysis_result = {
                    'property_id': property_id,
                    'timestamp': pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'house_title': basic_info['標題'],
                    'house_address': basic_info['地址'],
                    'house_data': {
                        '總價(萬)': basic_info['總價'],
                        '建坪': basic_info['建坪'],
                        '實際坪數': basic_info['實際坪數'],
                        '格局': basic_info['格局'],
                        '樓層': basic_info['樓層'],
                        '屋齡': basic_info['屋齡'],
                        '車位': basic_info['車位'],
                        '類型': basic_info['類型'],
                        '行政區': basic_info['行政區'],
                        '編號': property_id,
                    },
                    'ai_analysis': texts,
                    'analysis_data': analysis_data,
                    'compare_base_df': r['compare_base_df'],
                    'selected_row': r['selected_row'],
                    'scores': r['scores'],
                    'total_score': r['total_score'],
                }
                analysis_summary = {
                    'property_id': property_id,
                    'timestamp': analysis_result['timestamp'],
                    'basic_info': basic_info,
                    'analysis_data': analysis_data,
                    'scores': r['scores'],
                    'total_score': r['total_score'],
                    'texts': texts,
                }

                st.session_state.ai_results_summary.append(analysis_summary)
                st.session_state.ai_results.append(analysis_result)
                st.session_state.analysis_store[property_id] = {
                    'property_id': property_id,
                    'timestamp': analysis_result['timestamp'],
                    'basic_info': basic_info,
                    'analysis_data': analysis_data,
                    'scores': r['scores'],
                    'total_score': r['total_score'],
                    'texts': texts,
                }
                st.success(f"✅ 已儲存！目前共有 {len(st.session_state.ai_results)} 筆分析記錄")
                st.info("💡 前往「分析記錄」頁面查看所有儲存的分析結果")

                # ── 除錯資訊 ──
                st.write(st.session_state.ai_results_summary)
                

