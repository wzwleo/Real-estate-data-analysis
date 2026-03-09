import streamlit as st

def render_home_page(): 
    """
    渲染首頁內容 - 不動產智能分析平台
    """
    st.title("🏠 不動產智能分析平台")
    
    # 黑底白字的歡迎訊息
    st.markdown("""
    <div style='background-color: #1E1E1E; padding: 20px; border-radius: 10px; margin-bottom: 20px; border: 1px solid #333;'>
        <h3 style='margin-top: 0; color: #FFFFFF;'>👋 歡迎來到 AI 購屋分析系統</h3>
        <p style='font-size: 16px; color: #FFFFFF;'>本系統整合 AI 技術與數據分析，提供完整的購屋決策支援。</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("## 📋 系統功能總覽")
    
    col1, col2 = st.columns(2)

    with col1:
        # 左上：搜尋頁面
        with st.container(border=True):
            st.subheader("🔍 智能房產搜尋")
            st.markdown("""
            **支援自然語言查詢**，輕鬆找到符合條件的房子：
            - 💬 輸入「台中市西屯區 2000 萬內 3房」
            - 🤖 AI 自動解析需求並篩選
            - 📄 即時瀏覽搜尋結果
            - ⭐ 收藏感興趣的物件
            """)
            if st.button("🚀 開始搜尋", key="search_btn", use_container_width=True):
                st.session_state.current_page = 'search'

        # 左下：個別房屋深度分析
        with st.container(border=True):
            st.subheader("📊 個別房屋深度分析")
            st.markdown("""
            **五大面向量化評估**，全面了解房屋價值：
            - 💰 **價格分析**：計算同區域價格百分位、與市場中位數比較
            - 📐 **空間效率**：分析建坪與實際坪數使用率
            - 🕰 **屋齡趨勢**：線性回歸分析屋齡對單價影響
            - 🏢 **樓層價值**：評估樓層與單價關聯性
            - 🛋 **格局供給**：分析市場格局分布與稀有性
            """)
            st.markdown("**產出結果**：")
            st.markdown("- 五大面向評分雷達圖")
            st.markdown("- 綜合總分 (0-100)")
            st.markdown("- AI 智能分析報告")
            if st.button("📈 開始分析", key="solo_btn", use_container_width=True):
                st.session_state.current_page = 'analysis'
                st.session_state.analysis_mode = '單一房屋分析'

    with col2:
        # 右上：生活機能比較
        with st.container(border=True):
            st.subheader("🏪 生活機能比較")
            st.markdown("""
            **周邊設施完整分析**，了解居住環境：
            - 🚇 交通運輸（捷運、公車、火車站）
            - 🏫 教育機構（學校、幼兒園）
            - 🏥 醫療保健（醫院、診所、藥局）
            - 🛒 購物場所（超市、便利商店、市場）
            - ☕ 餐飲美食（餐廳、咖啡廳）
            - 🌳 休閒設施（公園、健身房）
            """)
            st.markdown("**特色功能**：")
            st.markdown("- 支援 5 種買家類型（首購族/家庭/退休族等）")
            st.markdown("- 自動推薦適合的生活機能")
            st.markdown("- 多房屋同時比較")
            if st.button("🏙️ 開始比較", key="life_btn", use_container_width=True):
                st.session_state.current_page = 'analysis'
                st.session_state.analysis_mode = '多房屋比較'

        # 右下：嫌惡設施警示
        with st.container(border=True):
            st.subheader("⚠️ 嫌惡設施警示系統")
            st.markdown("""
            **主動提醒潛在風險**，避免買到有問題的房子：
            """)
            
            # 用三欄顯示三種等級
            col_a, col_b, col_c = st.columns(3)
            with col_a:
                st.markdown("🔴 **高度注意**")
                st.caption("加油站、特種行業、工業區、宮廟")
            with col_b:
                st.markdown("🟡 **中度注意**")
                st.caption("基地台、垃圾場、市場、醫院")
            with col_c:
                st.markdown("🟢 **低度注意**")
                st.caption("警察局、消防局")
            
            st.markdown("**分析內容**：")
            st.markdown("- 依距離計算風險評分")
            st.markdown("- 地圖上以紅色標示")
            st.markdown("- 獨立表格顯示所有嫌惡設施")

    # 底部：系統特色說明
    st.markdown("---")
    st.markdown("## ✨ 平台特色")
    
    col_feat1, col_feat2, col_feat3, col_feat4 = st.columns(4)
    
    with col_feat1:
        st.markdown("""
        <div style='text-align: center; padding: 10px;'>
            <h3 style='color: #1E90FF;'>🤖</h3>
            <h4>AI 驅動</h4>
            <p style='font-size: 12px;'>自然語言搜尋 + 智能分析報告</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col_feat2:
        st.markdown("""
        <div style='text-align: center; padding: 10px;'>
            <h3 style='color: #1E90FF;'>📊</h3>
            <h4>數據導向</h4>
            <p style='font-size: 12px;'>百分位分析、線性回歸、市場比較</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col_feat3:
        st.markdown("""
        <div style='text-align: center; padding: 10px;'>
            <h3 style='color: #1E90FF;'>🗺️</h3>
            <h4>視覺化地圖</h4>
            <p style='font-size: 12px;'>Google Maps 整合，設施一目瞭然</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col_feat4:
        st.markdown("""
        <div style='text-align: center; padding: 10px;'>
            <h3 style='color: #1E90FF;'>⚠️</h3>
            <h4>風險警示</h4>
            <p style='font-size: 12px;'>20類嫌惡設施主動提醒</p>
        </div>
        """, unsafe_allow_html=True)

    # 技術架構簡介
    with st.expander("🔧 技術架構"):
        st.markdown("""
        - **前端框架**：Streamlit
        - **AI 模型**：Google Gemini AI
        - **地圖服務**：Google Maps API
        - **數據處理**：Pandas, NumPy
        - **視覺化**：Plotly, Streamlit ECharts
        """)
