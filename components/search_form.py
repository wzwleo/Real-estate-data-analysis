import os
import re
import pandas as pd
import streamlit as st
from utils import get_city_options, filter_properties

def render_search_form():
    with st.form("property_requirements"):
        st.subheader("📍 房產篩選條件")

        housetype = [
            "不限", "大樓", "華廈", "公寓", "套房", "透天", "店面",
            "辦公", "別墅", "倉庫", "廠房", "土地", "單售車位", "其它"
        ]

        options = get_city_options()
        col1, col2 = st.columns([1, 1])

        with col1:
            selected_label = st.selectbox("🏙️ 請選擇城市", list(options.keys()))
            housetype_change = st.selectbox("🏠 房產類別", housetype)

        district_options = [
            "不限", "中區", "東區", "西區", "南區", "北區",
            "西屯區", "南屯區", "北屯區", "豐原區", "大里區",
            "太平區", "清水區", "沙鹿區", "大甲區", "東勢區",
            "梧棲區", "烏日區", "神岡區", "大肚區", "大雅區",
            "后里區", "霧峰區", "潭子區", "龍井區", "外埔區",
            "和平區", "石岡區", "大安區", "新社區"
        ]

        with col2:
            selected_district = st.selectbox("📍 行政區", district_options)

        col1, col2 = st.columns(2)
        with col1:
            budget_min = st.number_input("💰 預算下限(萬)", 0, 1_000_000, 0, 100)
        with col2:
            budget_max = st.number_input("💰 預算上限(萬)", 0, 1_000_000, 1_000_000, 100)

        if budget_min > budget_max and budget_max > 0:
            st.error("⚠️ 預算下限不能大於上限")

        st.subheader("🎯 房產條件細項")
        col1, col2, col3 = st.columns(3)

        with col1:
            num_rooms = st.selectbox("格局數(房)", options=["不限"] + list(range(1, 11)), index=0)
            age_label = st.selectbox(
                "屋齡範圍",
                ["不限", "預售", "1~5年", "6~10年", "11~15年", "16~20年", "20年以上"]
            )

        with col2:
            num_living = st.selectbox("格局數(廳)", options=["不限"] + list(range(1, 11)), index=0)
            area_min = st.number_input("建坪下限", 0, 1000, 0, 10)

        with col3:
            num_baths = st.selectbox("格局數(衛)", options=["不限"] + list(range(1, 11)), index=0)
            car_grip = st.selectbox("🅿️ 車位需求", ["不限", "需要", "不要"])

        submit = st.form_submit_button("🔍 搜尋", use_container_width=True)

        if submit:
            return handle_search_submit(
                selected_label, options, housetype_change,
                budget_min, budget_max, age_label, area_min, car_grip,
                selected_district, num_rooms, num_living, num_baths
            )

    return None


def parse_district(address):
    if not isinstance(address, str):
        return None
    match = re.search(r'(?<=[省市])(.+?[區鄉鎮市])', address)
    if match:
        return match.group(1)
    match = re.search(r'(.+?[區鄉鎮市])', address)
    if match:
        return match.group(1)
    return None


def handle_search_submit(
    selected_label, options, housetype_change,
    budget_min, budget_max, age_label, area_min, car_grip,
    selected_district, num_rooms, num_living, num_baths
):
    if budget_min > budget_max and budget_max > 0:
        st.error("❌ 預算範圍錯誤")
        return False

    # 屋齡標籤轉數值範圍
    age_range_map = {
        "不限":    (0,   100),
        "預售":    (0,   0),
        "1~5年":  (1,   5),
        "6~10年": (6,   10),
        "11~15年": (11, 15),
        "16~20年": (16, 20),
        "20年以上": (21, 100),
    }
    age_min, age_max = age_range_map.get(age_label, (0, 100))

    file_path = os.path.join("./Data", options[selected_label])

    try:
        df = pd.read_csv(file_path)

        if '地址' in df.columns:
            df['行政區'] = df['地址'].apply(parse_district)

        if '屋齡' in df.columns:
            df['屋齡'] = (
                df['屋齡']
                .astype(str)
                .str.replace('年', '', regex=False)
                .replace('預售', '0')
            )
            df['屋齡'] = pd.to_numeric(df['屋齡'], errors='coerce').fillna(0)

        def parse_layout(layout):
            if not isinstance(layout, str):
                return pd.Series([None, None, None])
            m = re.match(r'(\d+)房(\d+)廳(\d+)衛', layout)
            if m:
                return pd.Series(map(int, m.groups()))
            nums = re.findall(r'\d+', layout)
            nums += [None] * (3 - len(nums))
            return pd.Series(nums[:3])

        if '格局' in df.columns:
            df[['房間數', '廳數', '衛數']] = df['格局'].apply(parse_layout)

        filters = {
            'district': selected_district,
            'housetype': housetype_change,
            'budget_min': budget_min,
            'budget_max': budget_max,
            'age_min': age_min,   # ← 新增
            'age_max': age_max,   # ← 改為區間上限
            'area_min': area_min,
            'car_grip': car_grip,
            'num_rooms': num_rooms,
            'num_living': num_living,
            'num_baths': num_baths,
        }

        filtered_df = filter_properties(df, filters)

        st.session_state.filtered_df = filtered_df
        st.session_state.search_params = {
            'city': selected_label,
            'district': selected_district,
            'original_count': len(df),
            'filtered_count': len(filtered_df)
        }

        if filtered_df.empty:
            st.warning("😅 沒有找到符合條件的房產")
        else:
            st.success(f"✅ 從 {len(df)} 筆中找到 {len(filtered_df)} 筆")

        return True

    except FileNotFoundError:
        st.error(f"❌ 找不到檔案：{file_path}")
    except Exception as e:
        st.error(f"❌ 讀取資料錯誤：{e}")

    return False
