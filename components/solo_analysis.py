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
        包含所有房產資料的 DataFrame
    """
    
    # 確保 df 是 DataFrame
    if isinstance(df, pd.Series):
        df = pd.DataFrame([df])
    
    # 提取區域資訊
    df = df.copy()
    df['區域'] = df['地址'].str.extract(r'市(.+?)區')[0]
    df['類型'] = df['類型'].str.strip()
    
    # 取得目標房型的區域和類型
    target_district = target_row['區域'] if '區域' in target_row else target_row['地址'].split('市')[1].split('區')[0] if '市' in target_row['地址'] and '區' in target_row['地址'] else None
    target_type = target_row['類型'].strip() if '類型' in target_row else None
    
    if not target_district or not target_type:
        st.warning("⚠️ 無法取得目標房型的區域或類型資訊")
        return
    
    # 篩選同區同類型房屋
    df_filtered = df[(df['區域'] == target_district) & (df['類型'] == target_type)]
    
    if len(df_filtered) == 0:
        st.info(f"ℹ️ 找不到 {target_district}區 {target_type} 的其他房屋")
        return
    
    # 處理總價顯示格式
    def format_price(x):
        if x >= 10000:
            return f"{x/10000:.1f} 億"
        else:
            return f"{int(x)} 萬"
    
    # hover info 統一函式
    def make_hover(df_input):
        hover_text = []
        for i, row in df_input.iterrows():
            hover_text.append(
                f"<b>{row['標題']}</b><br>"
                f"地址：{row['地址']}<br>"
                f"樓層：{row['樓層']}<br>"
                f"屋齡：{row['屋齡']} 年<br>"
                f"實際坪數：{row['實際坪數']} 坪<br>"
                f"總價：{format_price(row['總價'])}"
            )
        return hover_text
    
    # 準備資料
    target_df = pd.DataFrame([target_row])
    others_df = df_filtered[df_filtered['標題'] != target_row['標題']]
    
    # 欄位重新命名（如果需要）
    if '建坪' in target_df.columns:
        target_df = target_df.rename(columns={'建坪': '建物面積'})
    if '總價(萬)' in target_df.columns:
        target_df = target_df.rename(columns={'總價(萬)': '總價'})
    if '建坪' in others_df.columns:
        others_df = others_df.rename(columns={'建坪': '建物面積'})
    if '總價(萬)' in others_df.columns:
        others_df = others_df.rename(columns={'總價(萬)': '總價'})
    
    # 轉換數值欄位
    target_df['實際坪數'] = pd.to_numeric(target_df['主+陽'], errors='coerce')
    others_df['實際坪數'] = pd.to_numeric(others_df['主+陽'], errors='coerce')
    target_df['總價'] = pd.to_numeric(target_df['總價'], errors='coerce')
    others_df['總價'] = pd.to_numeric(others_df['總價'], errors='coerce')
    
    # 移除 NaN
    others_df = others_df.dropna(subset=['實際坪數', '總價'])
    
    if others_df.empty:
        st.info(f"ℹ️ {target_district}區 {target_type} 沒有足夠的比較資料")
        return
    
    # 建立散點圖 (其他房型)
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
    
    # 加入目標房型紅星
    fig.add_scatter(
        x=target_df['實際坪數'],
        y=target_df['總價'],
        mode='markers',
        marker=dict(size=25, color='red', symbol='star'),
        name='目標房型',
        hovertemplate=make_hover(target_df)[0] + "<extra></extra>"
    )
    
    # 設定顯示範圍與正方形大小
    x_center = target_df['實際坪數'].iloc[0]
    y_center = target_df['總價'].iloc[0]
    
    x_range = (0, x_center * 2.5)
    y_range = (0, y_center * 2.5)
    
    fig.update_layout(
        title=f'{target_district}區 {target_type} 房價 vs 實際坪數 (共 {len(df_filtered)} 筆)',
        xaxis_title='實際坪數 (坪)',
        yaxis_title='總價 (萬)',
        template='plotly_white',
        width=500,
        height=500,
        xaxis=dict(range=x_range, showline=True, linewidth=1, linecolor='lightgrey', gridcolor='whitesmoke'),
        yaxis=dict(range=y_range, showline=True, linewidth=1, linecolor='lightgrey', gridcolor='whitesmoke'),
        showlegend=True,
        shapes=[                  # 用矩形當邊框
            dict(
                type='rect',
                xref='paper',
                yref='paper',
                x0=0,
                y0=0,
                x1=1,
                y1=1,
                line=dict(color='white', width=3),
                fillcolor='rgba(0,0,0,0)'  # 透明填充
            )
        ]
    )
    
    # 在 Streamlit 中顯示圖表
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
