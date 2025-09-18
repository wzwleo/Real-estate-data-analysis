import streamlit as st


def render_analysis_page():
    st.title("📊 分析頁面")
    st.markdown("---")
    col1, col2, col3, col4, col5, col6, col7 = st.columns([1, 1, 1, 1, 1, 1, 1])
    with col7:
        analysis_scope = st.selectbox(
            "分析類別",
            ["⭐收藏類別", "已售出房產"],
            key="analysis_scope"
        )
