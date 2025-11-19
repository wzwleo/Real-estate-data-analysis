import streamlit as st

def render_analysis_records_page():
    st.title("分析結果總覽")
    
    if 'ai_results' not in st.session_state or not st.session_state.ai_results:
        st.info("還沒有儲存任何分析結果喔～\n快去「個別分析」頁面按下「開始分析」→「儲存分析結果」吧！")
        return
    
    # 顯示總共有幾筆
    st.success(f"已儲存 {len(st.session_state.ai_results)} 筆分析報告")
    
    # 逐筆顯示
    for i, result in enumerate(st.session_state.ai_results):
        with st.expander(f"{i+1}. {result.get('house_title', '未知房屋')}", expanded=False):
            st.markdown(result.get('result_text', '無分析內容'))
            
            # 顯示相似房屋表格
            similar = result.get('similar_data', [])
            if similar:
                st.write("相似房屋（10 筆）")
                st.dataframe(pd.DataFrame(similar), use_container_width=True)
