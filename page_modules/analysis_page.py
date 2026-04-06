"""分析頁面主模組"""

import os
import sys
import traceback
import streamlit as st
import pandas as pd

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
components_dir = os.path.join(parent_dir, "components")

for path in [parent_dir, components_dir]:
    if path not in sys.path and os.path.exists(path):
        sys.path.insert(0, path)

import_success = False
ComparisonAnalyzer = None
tab1_module = None

try:
    try:
        from components.solo_analysis import tab1_module as solo_module
        tab1_module = solo_module
    except ImportError:
        from solo_analysis import tab1_module as solo_module
        tab1_module = solo_module

    try:
        from components.comparison import ComparisonAnalyzer as CA
        ComparisonAnalyzer = CA
    except ImportError:
        from comparison import ComparisonAnalyzer as CA
        ComparisonAnalyzer = CA

    import_success = True
except Exception:
    import_success = False


def _ensure_state():
    st.session_state.setdefault('analysis_target', 'solo')
    st.session_state.setdefault('pending_solo_property_ids', [])
    st.session_state.setdefault('comparison_notice', '')


def render_analysis_page():
    _ensure_state()
    st.title("📊 不動產分析平台")

    if not import_success:
        st.error("⚠️ 模組導入失敗，部分功能可能受限")

    labels = {
        'solo': '🏠 個別分析',
        'comparison': '🔄 房屋比較',
    }
    current_target = st.session_state.get('analysis_target', 'solo')
    if current_target not in labels:
        current_target = 'solo'
        st.session_state.analysis_target = 'solo'

    options = [labels['solo'], labels['comparison']]
    index = 0 if current_target == 'solo' else 1
    selected_label = st.radio('選擇分析模式', options, index=index, horizontal=True, key='analysis_mode_switcher')
    selected_target = 'solo' if selected_label == labels['solo'] else 'comparison'
    st.session_state.analysis_target = selected_target

    if st.session_state.get('comparison_notice'):
        st.info(st.session_state.pop('comparison_notice'))

    if selected_target == 'solo':
        pending = st.session_state.get('pending_solo_property_ids', [])
        if pending:
            st.warning(f"⚠️ 尚有 {len(pending)} 間房屋缺少個別分析，請先在本頁完成分析。")
        st.header("🏠 個別房屋分析")
        if tab1_module:
            try:
                tab1_module()
            except Exception as e:
                st.error(f"個別分析模組執行錯誤: {e}")
                st.code(traceback.format_exc())
        else:
            st.warning("個別分析模組暫時不可用")
    else:
        st.header("🔄 房屋比較分析")
        if ComparisonAnalyzer:
            try:
                analyzer = ComparisonAnalyzer()
                analyzer.render_comparison_tab()
            except Exception as e:
                st.error(f"房屋比較模組執行錯誤: {e}")
                st.code(traceback.format_exc())
        else:
            st.warning("房屋比較模組暫時不可用")


if __name__ == '__main__':
    st.set_page_config(page_title='不動產分析平台', page_icon='🏠', layout='wide', initial_sidebar_state='expanded')
    render_analysis_page()
