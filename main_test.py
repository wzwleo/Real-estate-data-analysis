import streamlit as st
from sidebar import render_sidebar
from page_modules.home_page import render_home_page
from page_modules.search_page import render_search_page
from page_modules.analysis_page import render_analysis_page
from page_modules.analysis_records_page import render_analysis_records_page
from page_modules.cp_ranking_page import render_cp_ranking_page

def main():
    st.set_page_config(layout="wide")
    
    if 'current_page' not in st.session_state:
        st.session_state.current_page = 'home'

    render_sidebar()
    
    if st.session_state.current_page == 'home':
        render_home_page()
    elif st.session_state.current_page == 'search':
        render_search_page()
    elif st.session_state.current_page == 'analysis':
        render_analysis_page()
    elif st.session_state.current_page == 'compare':
        render_compare_page()
    elif st.session_state.current_page == 'records':
        render_analysis_records_page()
    elif st.session_state.current_page == 'cp_ranking':
        render_cp_ranking_page()

if __name__ == "__main__":
    main()
