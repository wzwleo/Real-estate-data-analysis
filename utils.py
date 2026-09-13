import os
import html
import pandas as pd
import math
import streamlit as st
from streamlit.components.v1 import html as st_html

IMAGE_URL_COLUMNS = ("圖片網址", "圖片", "image_url")


def get_property_image_url(row):
    """從房屋資料列取出可用的圖片網址。"""
    if row is None:
        return ""
    for col in IMAGE_URL_COLUMNS:
        try:
            value = row[col] if col in row else None
        except Exception:
            value = None
        if value is None or (isinstance(value, float) and pd.isna(value)):
            continue
        url = str(value).strip()
        if url.lower() in ("", "nan", "none", "-", "無"):
            continue
        if url.startswith("http://") or url.startswith("https://"):
            return url
    return ""


def render_property_image(row, height=140, placeholder=True):
    """在 Streamlit 畫面顯示房屋照片（搜尋清單用縮圖）。"""
    url = get_property_image_url(row)
    if url:
        safe_url = html.escape(url, quote=True)
        st_html(
            (
                '<div style="margin:0;padding:0;background:transparent;">'
                f'<img src="{safe_url}" alt="房屋照片" referrerpolicy="no-referrer" '
                f'style="width:100%;height:{int(height)}px;object-fit:cover;'
                'border-radius:8px;display:block;" />'
                "</div>"
            ),
            height=int(height) + 12,
            scrolling=False,
        )
        return True
    if placeholder:
        st.markdown(
            f'<div style="width:100%;height:{int(height)}px;border-radius:8px;'
            f'background:rgb(38,39,48);display:flex;align-items:center;justify-content:center;'
            f'color:rgb(136,135,128);font-size:13px;">無圖片</div>',
            unsafe_allow_html=True,
        )
    return False


def render_analysis_hero(row, eyebrow="個別分析"):
    """分析頁雜誌風封面：全幅照片，標題疊在圖下緣。"""
    title = html.escape(str(row.get("標題", "未提供")), quote=True)
    address = html.escape(str(row.get("地址", "未提供")), quote=True)
    house_type = html.escape(str(row.get("類型", "")), quote=True)
    url = get_property_image_url(row)

    if url:
        safe_url = html.escape(url, quote=True)
        media = (
            f'<img src="{safe_url}" alt="房屋照片" referrerpolicy="no-referrer" '
            'style="width:100%;height:360px;object-fit:cover;display:block;" />'
        )
    else:
        media = '<div style="width:100%;height:360px;background:rgb(26,26,26);"></div>'

    type_line = (
        f'<div style="font-size:13px;color:rgb(208,208,208);margin-top:6px;">{house_type}</div>'
        if house_type and house_type not in ("", "未提供", "nan")
        else ""
    )
    eyebrow_text = html.escape(eyebrow, quote=True)
    st.markdown(
        (
            '<div style="position:relative;border-radius:12px;overflow:hidden;'
            'background:rgb(17,17,17);margin-bottom:4px;">'
            f"{media}"
            '<div style="position:absolute;left:0;right:0;bottom:0;padding:48px 32px 28px;'
            "background:linear-gradient(to top, rgba(14,17,23,0.94) 0%, "
            'rgba(14,17,23,0.62) 48%, rgba(14,17,23,0) 100%);color:rgb(255,255,255);">'
            f'<div style="font-size:12px;letter-spacing:3px;color:rgb(200,230,201);'
            f'margin-bottom:8px;">{eyebrow_text}</div>'
            f'<div style="font-size:34px;font-weight:700;line-height:1.25;">{title}</div>'
            f'<div style="font-size:15px;color:rgb(232,232,232);margin-top:10px;">📍 {address}</div>'
            f"{type_line}"
            "</div></div>"
        ),
        unsafe_allow_html=True,
    )


def render_analysis_photo_strip(rows, title_key="標題"):
    """比較頁雜誌風封面卡：照片當封面，標題疊在圖下緣。"""
    if not rows:
        return

    cards = []
    for row in rows:
        title = html.escape(str(row.get(title_key) or row.get("房屋") or ""), quote=True)
        address = html.escape(str(row.get("地址", "")), quote=True)
        url = get_property_image_url(row)
        if url:
            safe_url = html.escape(url, quote=True)
            photo = (
                f'<img src="{safe_url}" alt="" referrerpolicy="no-referrer" '
                'style="width:100%;height:200px;object-fit:cover;display:block;" />'
            )
        else:
            photo = '<div style="height:200px;background:rgb(26,26,26);"></div>'
        cards.append(
            '<div style="flex:1;min-width:200px;position:relative;border-radius:12px;'
            'overflow:hidden;background:rgb(17,17,17);color:rgb(255,255,255);">'
            f"{photo}"
            '<div style="position:absolute;left:0;right:0;bottom:0;padding:28px 14px 14px;'
            "background:linear-gradient(to top, rgba(14,17,23,0.92) 0%, "
            'rgba(14,17,23,0.45) 70%, rgba(14,17,23,0) 100%);">'
            f'<div style="font-size:15px;font-weight:700;line-height:1.35;">{title}</div>'
            f'<div style="font-size:12px;color:rgb(216,216,216);margin-top:6px;">{address}</div>'
            "</div></div>"
        )

    st.markdown(
        f'<div style="display:flex;gap:12px;flex-wrap:wrap;margin:4px 0 12px 0;">{"".join(cards)}</div>',
        unsafe_allow_html=True,
    )

def get_city_options(data_dir="./Data"):
    """ 獲取城市選項，只顯示對照表內有定義的檔案 """
    if not os.path.exists(data_dir):
        return {}
    name_map = {
        "Taichung-city_buy_properties.csv": "台中市",
    }
    files = [f for f in os.listdir(data_dir) if f.endswith(".csv")]
    options = {name_map[f]: f for f in files if f in name_map}
    return dict(sorted(options.items(), key=lambda x: x[0]))


def filter_properties(df, filters):
    """ 根據篩選條件過濾房產資料 """
    filtered_df = df.copy()
    try:
        # 行政區
        if filters.get('district') and filters['district'] != "不限":
            if '行政區' in filtered_df.columns:
                filtered_df = filtered_df[filtered_df['行政區'] == filters['district']]

        # 類型
        if filters.get('housetype') and filters['housetype'] != "不限":
            if '類型' in filtered_df.columns:
                filtered_df = filtered_df[
                    filtered_df['類型'].astype(str).str.contains(filters['housetype'], case=False, na=False)
                ]

        # 預算
        if filters.get('budget_min', 0) > 0 and '總價(萬)' in filtered_df.columns:
            filtered_df = filtered_df[filtered_df['總價(萬)'] >= filters['budget_min']]
        if filters.get('budget_max', 1000000) < 1000000 and '總價(萬)' in filtered_df.columns:
            filtered_df = filtered_df[filtered_df['總價(萬)'] <= filters['budget_max']]

        # 屋齡（改為區間篩選，支援 age_min + age_max）
        if '屋齡' in filtered_df.columns:
            age_min = filters.get('age_min', 0)
            age_max = filters.get('age_max', 100)
            # 非「不限」(0~100 全範圍) 才套用篩選
            if not (age_min == 0 and age_max == 100):
                filtered_df = filtered_df[
                    (filtered_df['屋齡'] >= age_min) & (filtered_df['屋齡'] <= age_max)
                ]

        # 建坪
        if filters.get('area_min', 0) > 0 and '建坪' in filtered_df.columns:
            filtered_df = filtered_df[filtered_df['建坪'] >= filters['area_min']]

        # 車位
        if 'car_grip' in filters and '車位' in filtered_df.columns:
            if filters['car_grip'] == "需要":
                filtered_df = filtered_df[
                    (filtered_df['車位'].notna()) &
                    (filtered_df['車位'] != "無車位") &
                    (filtered_df['車位'] != 0)
                ]
            elif filters['car_grip'] == "不要":
                filtered_df = filtered_df[
                    (filtered_df['車位'].isna()) |
                    (filtered_df['車位'] == "無車位") |
                    (filtered_df['車位'] == 0)
                ]

        # 房間數
        if filters.get('num_rooms') and filters['num_rooms'] != "不限":
            filtered_df = filtered_df[
                pd.to_numeric(filtered_df['房間數'], errors='coerce') == filters['num_rooms']
            ]

        # 廳數
        if filters.get('num_living') and filters['num_living'] != "不限":
            filtered_df = filtered_df[
                pd.to_numeric(filtered_df['廳數'], errors='coerce') == filters['num_living']
            ]

        # 衛數
        if filters.get('num_baths') and filters['num_baths'] != "不限":
            filtered_df = filtered_df[
                pd.to_numeric(filtered_df['衛數'], errors='coerce') == filters['num_baths']
            ]

    except Exception as e:
        st.error(f"篩選過程中發生錯誤: {e}")
        return df

    return filtered_df


def display_pagination(df, items_per_page=10):
    """ 處理分頁邏輯 """
    if 'current_search_page' not in st.session_state:
        st.session_state.current_search_page = 1
    total_items = len(df)
    total_pages = math.ceil(total_items / items_per_page) if total_items > 0 else 1
    if st.session_state.current_search_page > total_pages:
        st.session_state.current_search_page = 1
    start_idx = (st.session_state.current_search_page - 1) * items_per_page
    end_idx = min(start_idx + items_per_page, total_items)
    current_page_data = df.iloc[start_idx:end_idx]
    return current_page_data, st.session_state.current_search_page, total_pages, total_items
