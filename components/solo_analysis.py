import streamlit as st
import pandas as pd
import google.generativeai as genai

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
                # 轉成數字後加上萬單位後的0，並加逗號
                formatted_price = f"{int(raw_price)*10000:,}"  # 乘 10000，把萬轉成元，並加逗號
            except:
                formatted_price = raw_price

        # 先處理建坪文字
        area = selected_row.get('建坪', '未提供')
        area_text = f"{area} 坪" if area != '未提供' else area
        
        # 先處理坪數文字
        Actual_space = selected_row.get('主+陽', '未提供')
        Actual_space_text = f"{Actual_space} 坪" if Actual_space != '未提供' else Actual_space

        #建坪單價/實際單價
        total_price = int(raw_price) * 10000
        area_Price_per = f"{int(total_price)/area:,.0f}"
        Actual_space_Price_per = f"{int(total_price)/Actual_space:,.0f}"
        
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
                flex-direction:column;  /* 垂直排列 */
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
        
        # 置中長條按鈕（純 Streamlit）
        col1, col2, col3 = st.columns([1, 2, 1])  # 中間欄較寬
        with col2:
            st.write("")  # 增加一點空白
            st.markdown("<div style='text-align:center;'>", unsafe_allow_html=True)
            analyze_clicked = st.button("開始分析", use_container_width=True, key="solo_analysis_button")
            st.markdown("</div>", unsafe_allow_html=True)

        if analyze_clicked:
            if not gemini_key:
                st.error("❌ 右側 gemini API Key 有誤")
                st.stop()
        try:
            genai.configure(api_key=gemini_key)
            model = genai.GenerativeModel("gemini-2.0-flash")

            prompt = f"""
            請針對以下房屋資料進行分析，並以中文簡潔說明市場價值與優缺點：

            標題：{selected_row.get('標題','未提供')}
            地址：{selected_row.get('地址','未提供')}
            類型：{selected_row.get('類型','未提供')}
            總價：{formatted_price} 元
            建坪：{area_text}
            實際坪數：{actual_space_text}
            格局：{selected_row.get('格局','未提供')}
            屋齡：{selected_row.get('屋齡','未提供')}
            樓層：{selected_row.get('樓層','未提供')}
            車位：{selected_row.get('車位','未提供')}
            建坪單價：{area_Price_per} 元/坪
            實際單價：{Actual_space_Price_per} 元/坪

            請生成具參考價值的分析摘要，建議字數約 100-200 字。
            """

            with st.spinner("Gemini 正在分析中..."):
                response = model.generate_content(prompt)

            st.success("✅ 分析完成")
            st.markdown("### 🔍 Gemini AI 分析結果")
            st.markdown(response.text)

        except Exception as e:
            st.error(f"❌ 分析過程發生錯誤：{e}")




            



