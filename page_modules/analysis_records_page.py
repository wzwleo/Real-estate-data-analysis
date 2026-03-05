import streamlit as st
import pandas as pd

def render_analysis_records_page():
    st.title("📚 分析結果總覽")
    
    if 'ai_results' not in st.session_state or not st.session_state.ai_results:
        st.info("📭 還沒有儲存任何分析結果喔～\n\n快去「個別分析」頁面按下「開始分析」→「💾 儲存本次分析結果」吧！")
        return
    
    # 顯示總共有幾筆
    st.success(f"✅ 已儲存 {len(st.session_state.ai_results)} 筆分析報告")
    
    # 排序選項
    col1, col2 = st.columns([3, 1])
    with col1:
        st.write("")
    with col2:
        sort_order = st.selectbox("排序方式", ["最新到最舊", "最舊到最新"], key="sort_order")
    
    # 根據排序顯示
    results = st.session_state.ai_results.copy()
    if sort_order == "最舊到最新":
        results = results
    else:
        results = list(reversed(results))
    
    # 逐筆顯示
    for i, result in enumerate(results):
        # 計算實際索引（用於刪除）
        actual_index = len(st.session_state.ai_results) - 1 - i if sort_order == "最新到最舊" else i
        
        with st.expander(
            f"🏠 {result.get('house_title', '未知房屋')} - {result.get('timestamp', '未知時間')}", 
            expanded=False
        ):
            # ===============================
            # 顯示基本資訊
            # ===============================
            st.markdown(f"""
            <div style="
                border:2px solid #4CAF50;
                border-radius:10px;
                padding:10px;
                background-color:#1f1f1f;
                text-align:center;
                color:white;
            ">
                <div style="font-size:40px; font-weight:bold;">{result.get('house_title','未提供')}</div>
                <div style="font-size:20px;">📍 {result.get('house_address','未提供')}</div>
                <div style="font-size:14px; color:#cccccc; margin-top:5px;">
                    分析時間：{result.get('timestamp', '未知')}
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            st.write("\n")
            
            # 房屋資料卡片
            house_data = result.get('house_data', {})
            
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
                    <div> 類型：{house_data.get('類型','未提供')}</div>
                    <div> 建坪：{house_data.get('建坪','未提供')} 坪</div>
                    <div> 實際坪數：{house_data.get('實際坪數','未提供')} 坪</div>
                    <div> 格局：{house_data.get('格局','未提供')}</div>
                    <div> 樓層：{house_data.get('樓層','未提供')}</div>
                    <div> 屋齡：{house_data.get('屋齡','未提供')}</div>
                    <div> 車位：{house_data.get('車位','未提供')}</div>
                </div>
                """, unsafe_allow_html=True)
                
            with col2:
                # 計算單價
                try:
                    total_price = int(house_data.get('總價(萬)', 0)) * 10000
                    area = house_data.get('建坪', 1)
                    actual_space = house_data.get('實際坪數', 1)
                    area_price_per = f"{int(total_price/area):,}" if area > 0 else "未提供"
                    actual_space_price_per = f"{int(total_price/float(actual_space)):,}" if actual_space and float(actual_space) > 0 else "未提供"
                    formatted_price = f"{total_price:,}"
                except:
                    formatted_price = house_data.get('總價(萬)', '未提供')
                    area_price_per = "未提供"
                    actual_space_price_per = "未提供"
                
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
                        建坪單價：{area_price_per} 元/坪
                    </div>
                    <div style="font-size:14px; color:#cccccc; margin-top:5px;">
                        實際單價：{actual_space_price_per} 元/坪
                    </div>
                </div>
                """, unsafe_allow_html=True)
            
            st.markdown("---")
            
            # ===============================
            # 顯示 AI 分析結果
            # ===============================
            
            st.header("🏡 房屋分析說明")
            st.write("""
            針對所選房屋的六大面向逐一分析，包括價格、坪數、屋齡、樓層、格局與地段。
            """)
            st.markdown("---")
            
            ai_analysis = result.get('ai_analysis', {})
            selected_row_dict = result.get('selected_row', {})
            compare_data = result.get('compare_base_df', [])
            
            # 重建 DataFrame
            selected_row = pd.Series(selected_row_dict)
            compare_base_df = pd.DataFrame(compare_data) if compare_data else pd.DataFrame()
            
            # 價格分析
            st.subheader("價格 💸")
            col1, col2 = st.columns([1, 1])
            with col1:
                if not compare_base_df.empty:
                    plot_price_scatter(selected_row, compare_base_df)
                else:
                    st.warning("⚠️ 無比較資料")
            with col2:
                st.markdown("### 📌 價格分析結論")
                st.write(ai_analysis.get('price', '無分析內容'))
            st.markdown("---")
            
            # 坪數分析
            st.subheader("坪數 📐")
            col1, col2 = st.columns([1, 1])
            with col1:
                st.markdown("### 📌 坪數分析結論")
                st.write(ai_analysis.get('space', '無分析內容'))
            with col2:
                if not compare_base_df.empty:
                    plot_space_efficiency_scatter(selected_row, compare_base_df)
                else:
                    st.warning("⚠️ 無比較資料")
            st.markdown("---")
            
            # 屋齡分析
            st.subheader("屋齡 🕰")
            st.markdown("### 📌 屋齡分析結論")
            st.write(ai_analysis.get('age', '無分析內容'))
            if not compare_base_df.empty:
                plot_age_distribution(selected_row, compare_base_df)
            else:
                st.warning("⚠️ 無比較資料")
            st.markdown("---")
            
            # 樓層分析
            st.subheader("樓層 🏢")
            st.markdown("### 📌 樓層分析結論")
            st.write(ai_analysis.get('floor', '無分析內容'))
            if not compare_base_df.empty:
                plot_floor_distribution(selected_row, compare_base_df)
            else:
                st.warning("⚠️ 無比較資料")
            st.markdown("---")
            
            # 格局分析
            st.subheader("格局 🛋")
            st.markdown("### 📌 格局分析結論")
            st.write(ai_analysis.get('layout', '無分析內容'))
            if not compare_base_df.empty:
                plot_layout_distribution(selected_row, compare_base_df)
            else:
                st.warning("⚠️ 無比較資料")
            st.markdown("---")
            
            # 地段分析
            st.subheader("地段 🗺")
            st.markdown("---")
            
            # 綜合總結
            st.markdown("---")
            st.markdown("---")
            st.header("🎯 綜合總結與購屋建議")
            st.markdown("### 📊 整體評估")
            st.write(ai_analysis.get('summary', '無綜合分析'))
            st.markdown("---")
            
            # ===============================
            # 刪除按鈕
            # ===============================
            col1, col2, col3 = st.columns([1, 1, 1])
            with col2:
                if st.button(f"🗑️ 刪除此筆記錄", key=f"delete_{actual_index}", use_container_width=True):
                    st.session_state.ai_results.pop(actual_index)
                    st.rerun()
