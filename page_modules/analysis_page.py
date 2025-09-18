import streamlit as st
import pandas as pd

def get_favorites_data():
    """
    取得收藏房產的資料
    """
    if 'favorites' not in st.session_state or not st.session_state.favorites:
        return pd.DataFrame()
    
    # 嘗試從不同來源取得完整房產資料
    all_df = None
    
    # 優先從 all_properties_df 取得資料
    if 'all_properties_df' in st.session_state and not st.session_state.all_properties_df.empty:
        all_df = st.session_state.all_properties_df
    # 如果沒有 all_properties_df，則從 filtered_df 取得
    elif 'filtered_df' in st.session_state and not st.session_state.filtered_df.empty:
        all_df = st.session_state.filtered_df
    
    if all_df is None or all_df.empty:
        return pd.DataFrame()
    
    # 篩選收藏的房產
    fav_ids = st.session_state.favorites
    fav_df = all_df[all_df['編號'].isin(fav_ids)].copy()
    
    return fav_df

def render_favorites_list(fav_df):
    """
    渲染收藏清單
    """
    st.subheader("⭐ 我的收藏清單")
    
    if fav_df.empty:
        st.info("⭐ 你尚未收藏任何房產")
        return
    
    # 顯示收藏數量統計
    st.metric("收藏總數", len(fav_df))
    
    # 顯示收藏清單
    for idx, (_, row) in enumerate(fav_df.iterrows()):
        with st.container():
            col1, col2 = st.columns([8, 2])
            
            with col1:
                st.markdown(f"**#{idx+1} 🏠 {row['標題']}**")
                st.write(f"**地址：** {row['地址']} | **屋齡：** {row['屋齡']} | **類型：** {row['類型']}")
                st.write(f"**建坪：** {row['建坪']} | **格局：** {row['格局']} | **樓層：** {row['樓層']}")
                if '車位' in row and pd.notna(row['車位']):
                    st.write(f"**車位：** {row['車位']}")
            
            with col2:
                st.metric("總價", f"{row['總價(萬)']} 萬")
                # 計算單價
                if pd.notna(row['建坪']) and row['建坪'] > 0:
                    unit_price = (row['總價(萬)'] * 10000) / row['建坪']
                    st.caption(f"單價: ${unit_price:,.0f}/坪")
                
                # 移除收藏按鈕
                property_id = row['編號']
                if st.button("❌ 移除", key=f"remove_fav_{property_id}"):
                    st.session_state.favorites.remove(property_id)
                    st.rerun()
                
                # 物件連結
                property_url = f"https://www.sinyi.com.tw/buy/house/{row['編號']}?breadcrumb=list"
                st.markdown(f'[🔗 物件連結]({property_url})')
            
            st.markdown("---")


def render_analysis_page():
    """
    渲染分析頁面
    """
    st.title("📊 分析頁面")
    
    # 初始化收藏（確保兼容性）
    if 'favorites' not in st.session_state:
        st.session_state.favorites = set()
    
    # 選擇分析範圍
    col1, col2, col3, col4 = st.columns([1, 1, 1, 1])
    with col4:
        analysis_scope = st.selectbox(
            "選擇分析範圍",
            ["⭐收藏類別", "已售出房產"],
            key="analysis_scope"
        )
    
    st.markdown("---")
    
    # 根據選擇的範圍進行分析
    if analysis_scope == "⭐收藏類別":
        fav_df = get_favorites_data()
        
        if fav_df.empty and st.session_state.favorites:
            st.warning("⚠️ 找不到收藏房產的詳細資料，請先在搜尋頁面載入房產資料")
            st.info("💡 提示：請先到搜尋頁面進行搜尋，載入房產資料後再回到分析頁面")
        elif not st.session_state.favorites:
            st.info("⭐ 你尚未收藏任何房產，請先到房產列表頁面收藏一些房產")
        else:
            render_favorites_list(fav_df)
    
    elif analysis_scope == "已售出房產":
        st.info("🚧 已售出房產分析功能開發中...")

# 輔助函數：在主程式中確保資料同步
def ensure_data_sync():
    """
    確保房產資料在不同模塊間保持同步
    建議在主程式的開始處呼叫此函數
    """
    # 如果有 filtered_df 但沒有 all_properties_df，則複製一份
    if ('filtered_df' in st.session_state and 
        not st.session_state.filtered_df.empty and
        'all_properties_df' not in st.session_state):
        st.session_state.all_properties_df = st.session_state.filtered_df.copy()
    
    # 確保 favorites 已初始化
    if 'favorites' not in st.session_state:
        st.session_state.favorites = set()
