import streamlit as st
import requests
import math
from streamlit.components.v1 import html


def render_analysis_page():
    """
    渲染分析頁面：Google Maps API 周邊地點查詢
    """
    st.title("📊 分析頁面")
    
