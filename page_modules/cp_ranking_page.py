import streamlit as st
import pandas as pd
import numpy as np
import re

try:
    from components.favorites import FavoritesManager, normalize_property_id
except Exception:
    def normalize_property_id(value):
        return "" if value is None else str(value).strip()


def _parse_age(x):
    if pd.isna(x): return np.nan
    match = re.search(r'(\d+\.?\d*)', str(x))
    return float(match.group(1)) if match else np.nan


def _parse_floor(x):
    if pd.isna(x): return np.nan
    try:
        parts = str(x).split('樓')
        val = re.search(r'\d+', parts[0])
        return int(val.group()) if val else np.nan
    except:
        return np.nan


def _score_one_fast(row, df_pool, weights):
    try:
        target_price = pd.to_numeric(row.get('總價(萬)', np.nan), errors='coerce')
        target_area  = pd.to_numeric(row.get('建坪', np.nan), errors='coerce')
        if pd.isna(target_price) or pd.isna(target_area) or target_area == 0:
            return np.nan

        compare_df = df_pool.copy()
        compare_df['_總價'] = pd.to_numeric(compare_df['總價(萬)'], errors='coerce')
        compare_df['_建坪'] = pd.to_numeric(compare_df['建坪'], errors='coerce')
        compare_df = compare_df.dropna(subset=['_總價', '_建坪'])
        n = len(compare_df)
        if n == 0: return np.nan

        price_pct = (compare_df['_總價'] < target_price).sum() / n * 100
        score_price = max(0.0, min(10.0, 10 - price_pct / 10))

        score_space = 5.0
        actual = pd.to_numeric(row.get('主+陽', np.nan), errors='coerce')
        if not pd.isna(actual) and float(actual) > 0:
            usage = float(actual) / float(target_area)
            compare_df['_實際'] = pd.to_numeric(compare_df['主+陽'], errors='coerce')
            compare_df['_使用率'] = compare_df['_實際'] / compare_df['_建坪']
            med = compare_df['_使用率'].median()
            if not pd.isna(med) and med > 0:
                score_space = max(0.0, min(10.0, (usage / med) * 5))

        score_age = 5.0
        compare_df['_屋齡'] = compare_df['屋齡'].apply(_parse_age)
        target_age = _parse_age(row.get('屋齡'))
        df_age = compare_df.dropna(subset=['_屋齡'])
        if len(df_age) > 0 and not pd.isna(target_age):
            age_pct = (df_age['_屋齡'] < target_age).sum() / len(df_age) * 100
            score_age = max(0.0, min(10.0, 10 - age_pct / 10))

        score_floor = 5.0
        compare_df['_樓層'] = compare_df['樓層'].apply(_parse_floor)
        target_floor = _parse_floor(row.get('樓層'))
        df_floor = compare_df.dropna(subset=['_樓層'])
        if len(df_floor) > 0 and not pd.isna(target_floor):
            floor_pct = (df_floor['_樓層'] < target_floor).sum() / len(df_floor) * 100
            score_floor = max(0.0, min(10.0, 10 - abs(floor_pct - 50) / 5))

        score_layout = 0.0
        target_layout = str(row.get('格局', '')).strip()
        if target_layout and '格局' in compare_df.columns:
            same_cnt = (compare_df['格局'].astype(str).str.strip() == target_layout).sum()
            score_layout = max(0.0, min(10.0, (same_cnt / n * 100) / 3))

        weighted = (
            score_price  * (weights['價格競爭力'] / 100) +
            score_space  * (weights['空間效率']   / 100) +
            score_age    * (weights['屋齡優勢']   / 100) +
            score_floor  * (weights['樓層定位']   / 100) +
            score_layout * (weights['格局流動性'] / 100)
        )
        return round(weighted * 10, 1)
    except:
        return np.nan


def render_cp_ranking_page():
    st.title("🏆 地區 CP 值排行榜")
    st.write("各行政區依房屋類型自動計算 CP 值，顯示每區前三名。")

    # ── 載入資料 ──
    all_df = None
    if 'all_properties_df' in st.session_state and not st.session_state.all_properties_df.empty:
        all_df = st.session_state.all_properties_df
    else:
        try:
            all_df = pd.read_csv('./Data/Taichung-city_buy_properties.csv')
            if '行政區' not in all_df.columns and '地址' in all_df.columns:
                all_df['行政區'] = all_df['地址'].apply(
                    lambda addr: re.search(r'[市縣](.+?[區鄉鎮市])', str(addr)).group(1)
                    if pd.notna(addr) and re.search(r'[市縣](.+?[區鄉鎮市])', str(addr)) else ""
                )
            st.session_state.all_properties_df = all_df
        except Exception as e:
            st.error(f"❌ 無法載入資料：{e}")
            return

    # ── 篩選條件 ──
    housetypes = ["大樓", "華廈", "公寓", "套房", "透天", "別墅"]

    col1, col2 = st.columns([2, 1])
    with col1:
        selected_type = st.selectbox("🏠 房屋類型", housetypes, key="cp_type")
    with col2:
        st.write("")
        calc_btn = st.button("🔍 計算各地區前三名", use_container_width=True, key="calc_cp_btn", type="primary")

    weights = st.session_state.get('score_weights', {
        "價格競爭力": 30, "空間效率": 25,
        "屋齡優勢": 20, "樓層定位": 15, "格局流動性": 10
    })

    if calc_btn:
        districts = sorted(all_df['行政區'].dropna().unique().tolist())
        districts = [d for d in districts if d]

        all_results = []
        progress = st.progress(0)
        status = st.empty()

        for i, district in enumerate(districts):
            status.info(f"⏳ 計算中：{district}（{i+1}/{len(districts)}）")
            progress.progress((i + 1) / len(districts))

            df_pool = all_df[
                (all_df['行政區'] == district) &
                (all_df['類型'].astype(str).str.contains(selected_type, case=False, na=False))
            ].copy()

            if len(df_pool) < 3:
                continue

            df_pool['CP分數'] = df_pool.apply(
                lambda row: _score_one_fast(row, df_pool, weights), axis=1
            )
            df_pool = df_pool.dropna(subset=['CP分數'])
            df_pool = df_pool.sort_values('CP分數', ascending=False).reset_index(drop=True)
            top3 = df_pool.head(3).copy()
            top3['行政區'] = district
            top3.insert(0, '區內排名', range(1, len(top3) + 1))
            all_results.append(top3)

        progress.empty()
        status.empty()

        if all_results:
            st.session_state['cp_all_results'] = pd.concat(all_results, ignore_index=True).to_dict('records')
            st.session_state['cp_selected_type'] = selected_type
            st.success(f"✅ 計算完成，共 {len(districts)} 個行政區")
        else:
            st.warning("⚠️ 找不到足夠資料")

    # ── 顯示結果 ──
    if 'cp_all_results' in st.session_state and st.session_state['cp_all_results']:
            df_all = pd.DataFrame(st.session_state['cp_all_results'])
            selected_type_display = st.session_state.get('cp_selected_type', '')
    
            st.markdown("---")
            st.subheader(f"📊 各行政區「{selected_type_display}」CP 值前三名")
    
            districts_in_result = df_all['行政區'].unique().tolist()
    
            for row_start in range(0, len(districts_in_result), 2):
                row_districts = districts_in_result[row_start:row_start + 2]
                cols = st.columns(2)
    
                for col_idx, district in enumerate(row_districts):
                    df_dist = df_all[df_all['行政區'] == district].copy()
    
                    with cols[col_idx]:
                        with st.container(border=True):
                            st.markdown(f"#### 📍 {district}")
    
                            for _, row in df_dist.iterrows():
                                rank = int(row['區內排名'])
                                medal = "🥇" if rank == 1 else "🥈" if rank == 2 else "🥉"
                                cp = row.get('CP分數', 0)
                                color = "#1D9E75" if cp >= 70 else "#EF9F27" if cp >= 50 else "#888780"
                                price = row.get('總價(萬)', '')
                                layout = row.get('格局', '')
                                age = row.get('屋齡', '')
                                title = str(row.get('標題', ''))[:18]
                                property_id = normalize_property_id(row.get('編號', ''))
                                current_favs = st.session_state.get('favorites', [])
                                is_fav = property_id in current_favs
    
                                c1, c2 = st.columns([4, 1])
                                with c1:
                                    st.markdown(
                                        f"<div style='margin-bottom:2px'>"
                                        f"<span style='font-size:14px;font-weight:500;color:white'>{medal} {title}</span>"
                                        f"<span style='font-size:14px;font-weight:bold;color:{color};margin-left:8px'>{cp} 分</span>"
                                        f"</div>"
                                        f"<div style='font-size:11px;color:#888;margin-bottom:6px'>"
                                        f"💰 {price} 萬 ｜ {layout} ｜ 屋齡 {age}"
                                        f"</div>",
                                        unsafe_allow_html=True
                                    )
                                with c2:
                                    if st.button(
                                        "✅" if is_fav else "⭐",
                                        key=f"cp_fav_{district}_{rank}_{property_id}",
                                        disabled=is_fav,
                                        use_container_width=True
                                    ):
                                        new_favs = list(st.session_state.get('favorites', []))
                                        if property_id and property_id not in new_favs:
                                            new_favs.append(property_id)
                                            st.session_state.favorites = new_favs
                                            st.rerun()
    
                                st.divider()
    
