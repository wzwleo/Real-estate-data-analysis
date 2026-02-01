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

def diagnose_filter_difference(selected_row, compare_base_df):
    """診斷搜尋與製圖篩選差異"""
    
    st.write("### 🔍 詳細診斷報告")
    
    # 1. 檢查目標房型資訊
    st.write("#### 1️⃣ 目標房型資訊")
    target_district = selected_row.get('行政區')
    target_type = selected_row.get('類型')
    st.write(f"- 行政區：`{target_district}` (type: {type(target_district)})")
    st.write(f"- 類型：`{target_type}` (type: {type(target_type)})")
    
    # 2. 檢查比較資料集的行政區和類型
    st.write("#### 2️⃣ 比較資料集概況")
    st.write(f"- 總筆數：{len(compare_base_df)}")
    st.write(f"- 行政區欄位存在：{'行政區' in compare_base_df.columns}")
    st.write(f"- 類型欄位存在：{'類型' in compare_base_df.columns}")
    
    # 3. 顯示行政區的唯一值
    if '行政區' in compare_base_df.columns:
        st.write("#### 3️⃣ 資料集中的行政區分布")
        district_counts = compare_base_df['行政區'].value_counts()
        st.dataframe(district_counts.head(20))
        
        # 檢查目標行政區是否存在
        if target_district in district_counts.index:
            st.success(f"✅ 找到 {target_district}：{district_counts[target_district]} 筆")
        else:
            st.error(f"❌ 找不到 {target_district}")
            st.write("相似的行政區名稱：")
            similar = [d for d in district_counts.index if target_district and target_district in str(d)]
            st.write(similar[:10])
    
    # 4. 顯示類型的唯一值
    if '類型' in compare_base_df.columns:
        st.write("#### 4️⃣ 資料集中的類型分布")
        type_counts = compare_base_df['類型'].value_counts()
        st.dataframe(type_counts)
        
        # 檢查目標類型是否存在
        if target_type in type_counts.index:
            st.success(f"✅ 找到 {target_type}：{type_counts[target_type]} 筆")
        else:
            st.error(f"❌ 找不到 {target_type}")
    
    # 5. 逐步篩選測試
    st.write("#### 5️⃣ 逐步篩選測試")
    
    # 只篩選行政區
    filter_district = compare_base_df[compare_base_df['行政區'] == target_district]
    st.write(f"- 只篩選行政區 ({target_district})：{len(filter_district)} 筆")
    
    # 只篩選類型
    filter_type = compare_base_df[compare_base_df['類型'].astype(str).str.strip() == target_type]
    st.write(f"- 只篩選類型 ({target_type})：{len(filter_type)} 筆")
    
    # 同時篩選
    filter_both = compare_base_df[
        (compare_base_df['行政區'] == target_district) &
        (compare_base_df['類型'].astype(str).str.strip() == target_type)
    ]
    st.write(f"- 同時篩選：{len(filter_both)} 筆")
    
    # 6. 檢查是否有空白或特殊字符
    st.write("#### 6️⃣ 字串檢查")
    if '類型' in compare_base_df.columns:
        # 檢查類型欄位是否有前後空白
        has_whitespace = compare_base_df['類型'].astype(str).str.contains(r'^\s|\s$', regex=True).any()
        st.write(f"- 類型欄位有前後空白：{has_whitespace}")
        
        # 顯示目標類型的所有變體
        similar_types = compare_base_df[
            compare_base_df['類型'].astype(str).str.contains(target_type, case=False, na=False)
        ]['類型'].unique()
        st.write(f"- 包含 '{target_type}' 的所有變體：")
        for t in similar_types:
            st.write(f"  - `{repr(t)}` (長度: {len(str(t))})")
    
    # 7. 顯示篩選結果的前幾筆
    st.write("#### 7️⃣ 篩選結果範例")
    if len(filter_both) > 0:
        st.dataframe(filter_both[['標題', '地址', '行政區', '類型', '總價(萬)']].head(10))
    else:
        st.warning("無篩選結果")
    
    return filter_both

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
    
    # 確保 df 是 DataFrame
    if isinstance(df, pd.Series):
        df = pd.DataFrame([df])
    
    df = df.copy()
    
    # ✅ 統一使用 '類型' 欄位處理
    if '類型' in df.columns:
        df['類型'] = df['類型'].astype(str).str.strip()
    
    # ✅ 統一使用 '行政區' 欄位（與搜尋邏輯一致）
    target_district = target_row.get('行政區', None)
    target_type = target_row.get('類型', None)
    
    if target_type and isinstance(target_type, str):
        target_type = target_type.strip()
    
    # 驗證必要欄位
    if not target_district:
        st.warning("⚠️ 無法取得目標房型的行政區資訊")
        return
    
    if not target_type:
        st.warning("⚠️ 無法取得目標房型的類型資訊")
        return
    
    # ✅ 使用與搜尋相同的篩選邏輯（精確比對）
    df_filtered = df[
        (df['行政區'] == target_district) & 
        (df['類型'].astype(str).str.strip() == target_type)
    ].copy()
    
    if len(df_filtered) == 0:
        st.info(f"ℹ️ 找不到 {target_district} {target_type} 的其他房屋")
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
                f"樓層：{row.get('樓層', '未知')}<br>"
                f"屋齡：{row.get('屋齡', '未知')} 年<br>"
                f"實際坪數：{row.get('實際坪數', '未知')} 坪<br>"
                f"總價：{format_price(row.get('總價', None))}"
            )
        return hover_text
    
    # 準備資料
    target_df = pd.DataFrame([target_row])
    others_df = df_filtered[df_filtered['標題'] != target_row.get('標題')].copy()
    
    # 欄位重新命名（如果需要）
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
        st.info(f"ℹ️ {target_district} {target_type} 沒有足夠的比較資料")
        return
    
    # 驗證目標資料
    if pd.isna(target_df['實際坪數'].iloc[0]) or pd.isna(target_df['總價'].iloc[0]):
        st.warning("⚠️ 目標房型缺少必要的坪數或價格資訊")
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
    
    # 為其他點設置 hover
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
        title=f'{target_district} {target_type} 房價 vs 實際坪數 (共 {len(df_filtered)} 筆)',
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
    
    # 在 Streamlit 中顯示圖表
    st.plotly_chart(fig)
    
    # 📊 顯示統計資訊
    st.caption(f"📊 資料統計：{target_district} 共有 {len(df_filtered)} 筆 {target_type} 物件")

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
                
                # 取得比較資料
                compare_base_df = pd.DataFrame()
                if 'all_properties_df' in st.session_state and not st.session_state.all_properties_df.empty:
                    compare_base_df = st.session_state.all_properties_df
                elif 'filtered_df' in st.session_state and not st.session_state.filtered_df.empty:
                    compare_base_df = st.session_state.filtered_df
                
                # 🔍 診斷區塊
                with st.expander("🔍 詳細診斷", expanded=True):
                    if not compare_base_df.empty:
                        diagnosed_df = diagnose_filter_difference(selected_row, compare_base_df)
                    else:
                        st.error("找不到比較資料")
                
                # 原有的圖表顯示
                col1, col2 = st.columns([1, 1])
                with col1:
                    if not compare_base_df.empty:
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
