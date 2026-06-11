import streamlit as st
import google.generativeai as genai
import json
import pandas as pd
import re
from components.favorites import FavoritesManager, normalize_property_id

def render_ai_chat_search():
    st.header("🤖 AI 房市顧問")
    st.write("你可以輸入自然語言查詢條件，AI 會幫你搜尋適合的物件。")

    gemini_key = st.session_state.get("GEMINI_KEY", "")
    if not gemini_key:
        st.error("❌ 右側 gemini API Key 未設定或有誤")
        st.stop()

    try:
        genai.configure(api_key=gemini_key)
        model = genai.GenerativeModel('gemini-2.5-flash')
    except Exception as e:
        st.error(f"❌ Gemini 初始化錯誤：{e}")
        st.stop()

    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
    if "ai_search_count" not in st.session_state:
        st.session_state.ai_search_count = 0
    if 'favorites' not in st.session_state:
        st.session_state.favorites = []

    for chat in st.session_state.chat_history:
        with st.chat_message(chat["role"]):
            st.markdown(chat["content"])

    if 'ai_latest_filters' in st.session_state and 'ai_latest_reply' in st.session_state:
        with st.chat_message("assistant"):
            st.success("✅ 已解析您的需求")

    if prompt := st.chat_input("請輸入查詢條件，例如：『台中市西屯區 2000 萬內 3房2廳2衛 5樓以上』"):
        for key in ['ai_latest_filters', 'ai_latest_reply', 'ai_debug_info', 'ai_search_result_text']:
            if key in st.session_state:
                del st.session_state[key]

        with st.chat_message("user"):
            st.markdown(prompt)
        st.session_state.chat_history.append({"role": "user", "content": prompt})

        with st.spinner("AI 正在分析您的查詢，並篩選資料中..."):
            result_text = ""
            try:
                system_prompt = """
你是一個房產搜尋助手。請根據使用者的自然語言查詢，提取出搜尋條件。

請以 JSON 格式回傳，格式如下：
{
    "city": "台北市 或 台中市",
    "district": "行政區名稱(例如: 西屯區、大安區)",
    "budget_min": 最低預算(萬),
    "budget_max": 最高預算(萬),
    "age_min": 最小屋齡,
    "age_max": 最大屋齡,
    "area_min": 最小建坪,
    "area_max": 最大建坪,
    "floor_min": 最低樓層,
    "floor_max": 最高樓層,
    "rooms": 房間數,
    "living_rooms": 廳數,
    "bathrooms": 衛數,
    "study_rooms": 室數,
    "housetype": "華廈/公寓/大樓/套房/透天/別墅",
    "car_grip": "需要/不要/不限"
}

注意：
- 只回傳 JSON，不要有其他文字
- 如果使用者沒提到某個條件，該欄位則可以省略
- 預算單位是「萬」
- 城市只能是「台中市」
- district 欄位請精確提取，如「西屯」回傳「西屯區」
- 如果使用者提到「左右」「大約」請自動計算合理範圍
- 格局：「3房2廳2衛」→ rooms:3, living_rooms:2, bathrooms:2
- 樓層：「5樓以上」→ floor_min:5；「10樓以下」→ floor_max:10
"""
                full_prompt = f"{system_prompt}\n\n使用者查詢：{prompt}"
                response = model.generate_content(full_prompt)
                ai_reply = response.text.strip()

                if ai_reply.startswith("```json"):
                    ai_reply = ai_reply.replace("```json", "").replace("```", "").strip()

                filters = json.loads(ai_reply)
                st.session_state.ai_latest_filters = filters
                st.session_state.ai_latest_reply = ai_reply
                st.session_state.ai_layout_target = {
                    'rooms':        filters.get('rooms', 0),
                    'living_rooms': filters.get('living_rooms', 0),
                    'bathrooms':    filters.get('bathrooms', 0),
                    'study_rooms':  filters.get('study_rooms', 0),
                }

                city = filters.get("city", "台中市")
                city_file_map = {"台中市": "Taichung-city_buy_properties.csv"}
                csv_file = city_file_map.get(city)

                if not csv_file:
                    result_text = "❌ 不支援的城市"
                else:
                    df = pd.read_csv(f"./Data/{csv_file}")

                    def parse_layout(layout_str):
                        if pd.isna(layout_str) or not isinstance(layout_str, str):
                            return None, None, None, None
                        rooms  = re.search(r'(\d+)房', layout_str)
                        living = re.search(r'(\d+)廳', layout_str)
                        bath   = re.search(r'(\d+)衛', layout_str)
                        study  = re.search(r'(\d+)室', layout_str)
                        return (
                            int(rooms.group(1))  if rooms  else None,
                            int(living.group(1)) if living else None,
                            int(bath.group(1))   if bath   else None,
                            int(study.group(1))  if study  else None,
                        )

                    if '格局' in df.columns:
                        df[['房間數', '廳數', '衛數', '室數']] = df['格局'].apply(
                            lambda x: pd.Series(parse_layout(x))
                        )

                    def quick_parse_district(addr):
                        if pd.isna(addr) or not isinstance(addr, str):
                            return ""
                        match = re.search(r'[市縣](.+?[區鄉鎮市])', addr)
                        return match.group(1) if match else ""

                    if '地址' in df.columns:
                        df['行政區'] = df['地址'].apply(quick_parse_district)

                    def parse_floor(floor_str):
                        if pd.isna(floor_str) or not isinstance(floor_str, str):
                            return None
                        match = re.search(r'^(\d+)樓', floor_str)
                        return int(match.group(1)) if match else None

                    if '樓層' in df.columns:
                        df['實際樓層'] = df['樓層'].apply(parse_floor)

                    filtered_df = df.copy()

                    num_cols = {
                        '總價(萬)': 'budget', '屋齡': 'age', '建坪': 'area',
                        '房間數': 'rooms', '廳數': 'living_rooms',
                        '衛數': 'bathrooms', '室數': 'study_rooms', '實際樓層': 'floor'
                    }
                    for col in num_cols.keys():
                        if col in filtered_df.columns:
                            cleaned = filtered_df[col].astype(str).str.replace(',', '')
                            if col == '屋齡':
                                cleaned = cleaned.str.replace('年', '').str.strip()
                            filtered_df[col] = pd.to_numeric(cleaned, errors='coerce')

                    # ── 只保留類型和車位的硬性過濾，其他改為相似度計算 ──
                    if filters.get('housetype') and filters['housetype'] != "不限":
                        if '類型' in filtered_df.columns:
                            filtered_df = filtered_df[
                                filtered_df['類型'].astype(str).str.contains(
                                    filters['housetype'], case=False, na=False
                                )
                            ]

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

                    # ── 相似度計算函式 ──
                    def calc_similarity(row, filters):
                        scores = []

                        # 1. 地區相似度
                        target_district = filters.get('district', '')
                        if target_district and target_district != '不限':
                            row_district = str(row.get('行政區', ''))
                            dist_list = [d.strip() for d in target_district.replace('、', ',').replace('，', ',').split(',') if d.strip()]
                            district_match = any(d in row_district or row_district in d for d in dist_list)
                            scores.append(100 if district_match else 30)

                        # 2. 價格相似度
                        bmin = filters.get('budget_min', 0)
                        bmax = filters.get('budget_max', 0)
                        if bmin > 0 or bmax > 0:
                            price = row.get('總價(萬)', 0) or 0
                            if bmin > 0 and bmax > 0:
                                if bmin <= price <= bmax:
                                    scores.append(100)
                                elif price < bmin:
                                    gap = (bmin - price) / bmin
                                    scores.append(max(0, round(100 - gap * 150)))
                                else:
                                    gap = (price - bmax) / bmax
                                    scores.append(max(0, round(100 - gap * 150)))
                            elif bmax > 0:
                                if price <= bmax:
                                    scores.append(100)
                                else:
                                    gap = (price - bmax) / bmax
                                    scores.append(max(0, round(100 - gap * 150)))
                            elif bmin > 0:
                                if price >= bmin:
                                    scores.append(100)
                                else:
                                    gap = (bmin - price) / bmin
                                    scores.append(max(0, round(100 - gap * 150)))

                        # 3. 格局相似度（房廳衛各自計算取平均）
                        layout_dims = [
                            ('房間數', 'rooms'),
                            ('廳數',   'living_rooms'),
                            ('衛數',   'bathrooms'),
                        ]
                        layout_dims = [
                                    ('房間數', 'rooms'),
                                    ('廳數',   'living_rooms'),
                                    ('衛數',   'bathrooms'),
                                ]
                                layout_scores = []
                                for col, key in layout_dims:
                                    target = filters.get(key, 0)
                                    if target > 0:
                                        raw = row.get(col, 0)
                                        actual = 0 if (raw is None or (isinstance(raw, float) and pd.isna(raw))) else int(raw)
                                        if actual == target:
                                            layout_scores.append(100)
                                        elif actual > target:
                                            layout_scores.append(max(60, round(100 - (actual - target) * 15)))
                                        else:
                                            layout_scores.append(max(0, round(100 - (target - actual) * 35)))
                                if layout_scores:
                                    scores.append(round(sum(layout_scores) / len(layout_scores)))

                        # 4. 樓層相似度
                        fmin = filters.get('floor_min', 0)
                        fmax = filters.get('floor_max', 0)
                        if fmin > 0 or fmax > 0:
                            floor = row.get('實際樓層', 0) or 0
                            if fmin > 0 and fmax > 0:
                                if fmin <= floor <= fmax:
                                    scores.append(100)
                                elif floor < fmin:
                                    scores.append(max(0, round(100 - (fmin - floor) * 20)))
                                else:
                                    scores.append(max(0, round(100 - (floor - fmax) * 20)))
                            elif fmin > 0:
                                if floor >= fmin:
                                    scores.append(100)
                                else:
                                    scores.append(max(0, round(100 - (fmin - floor) * 20)))
                            elif fmax > 0:
                                if floor <= fmax:
                                    scores.append(100)
                                else:
                                    scores.append(max(0, round(100 - (floor - fmax) * 20)))

                        # 5. 坪數相似度
                        amin = filters.get('area_min', 0)
                        amax = filters.get('area_max', 0)
                        if amin > 0 or amax > 0:
                            area = row.get('建坪', 0) or 0
                            if amin > 0 and amax > 0:
                                if amin <= area <= amax:
                                    scores.append(100)
                                elif area < amin:
                                    gap = (amin - area) / amin
                                    scores.append(max(0, round(100 - gap * 150)))
                                else:
                                    gap = (area - amax) / amax
                                    scores.append(max(0, round(100 - gap * 150)))
                            elif amin > 0:
                                if area >= amin:
                                    scores.append(100)
                                else:
                                    gap = (amin - area) / amin
                                    scores.append(max(0, round(100 - gap * 150)))
                            elif amax > 0:
                                if area <= amax:
                                    scores.append(100)
                                else:
                                    gap = (area - amax) / amax
                                    scores.append(max(0, round(100 - gap * 150)))

                        # 6. 屋齡相似度
                        age_min = filters.get('age_min', 0)
                        age_max = filters.get('age_max', 0)
                        if age_min > 0 or age_max > 0:
                            age = row.get('屋齡', 0) or 0
                            if age_min > 0 and age_max > 0:
                                if age_min <= age <= age_max:
                                    scores.append(100)
                                elif age < age_min:
                                    scores.append(max(0, round(100 - (age_min - age) * 8)))
                                else:
                                    scores.append(max(0, round(100 - (age - age_max) * 8)))
                            elif age_max > 0:
                                if age <= age_max:
                                    scores.append(100)
                                else:
                                    scores.append(max(0, round(100 - (age - age_max) * 8)))
                            elif age_min > 0:
                                if age >= age_min:
                                    scores.append(100)
                                else:
                                    scores.append(max(0, round(100 - (age_min - age) * 8)))

                        if not scores:
                            return 100
                        return round(sum(scores) / len(scores))

                    filtered_df['相似度'] = filtered_df.apply(
                        lambda row: calc_similarity(row, filters), axis=1
                    )
                    filtered_df = filtered_df.sort_values('相似度', ascending=False).reset_index(drop=True)

                    st.session_state.ai_search_count += 1
                    st.session_state.ai_filtered_df = filtered_df
                    st.session_state.ai_search_city = city
                    st.session_state.ai_current_page = 1
                    st.session_state.ai_active_filters = filters

                    result_text = f"🔍 找到 **{len(filtered_df)}** 筆物件，已依相似度排序"
                    st.session_state.ai_search_result_text = result_text

            except json.JSONDecodeError:
                result_text = "❌ AI 回應格式錯誤，請重新嘗試"
            except Exception as e:
                result_text = f"❌ 發生錯誤: {e}"
                import traceback
                result_text += f"\n\n{traceback.format_exc()}"

            st.session_state.chat_history.append({"role": "assistant", "content": result_text})
            st.rerun()

    # ── 顯示搜尋結果 ──
    if 'ai_filtered_df' in st.session_state and not st.session_state.ai_filtered_df.empty:
        st.markdown("---")
        df = st.session_state.ai_filtered_df.copy()

        sort_options = {
            "相似度由高到低": ("相似度", False),
            "相似度由低到高": ("相似度", True),
            "價錢由低到高":   ("總價(萬)", True),
            "價錢由高到低":   ("總價(萬)", False),
            "屋齡由低到高":   ("屋齡",    True),
            "屋齡由高到低":   ("屋齡",    False),
            "建坪由低到高":   ("建坪",    True),
            "建坪由高到低":   ("建坪",    False),
        }

        title_col, sort_col = st.columns([3, 2])
        with title_col:
            st.subheader(f"🏠 {st.session_state.ai_search_city}房產列表")
        with sort_col:
            selected_sort = st.selectbox(
                "排序方式",
                options=list(sort_options.keys()),
                index=0,
                key="ai_sort_selector",
                label_visibility="collapsed"
            )

        sort_col_name, ascending = sort_options[selected_sort]
        if sort_col_name in df.columns:
            df = df.sort_values(sort_col_name, ascending=ascending, na_position='last')

        items_per_page = 10
        total_items = len(df)
        total_pages = (total_items + items_per_page - 1) // items_per_page
        current_page = st.session_state.get('ai_current_page', 1)
        current_page = max(1, min(current_page, total_pages))
        start_idx = (current_page - 1) * items_per_page
        end_idx = min(start_idx + items_per_page, total_items)
        current_page_data = df.iloc[start_idx:end_idx]

        for idx, (index, row) in enumerate(current_page_data.iterrows()):
            with st.container():
                global_idx = (current_page - 1) * 10 + idx + 1
                similarity = int(row.get('相似度', 0))

                if similarity >= 90:
                    sim_color = "#1D9E75"
                elif similarity >= 70:
                    sim_color = "#EF9F27"
                else:
                    sim_color = "#888780"

                col1, col4 = st.columns([7, 2])
                with col1:
                    display_age = "預售" if pd.isna(row['屋齡']) or row['屋齡'] == 0 else f"{row['屋齡']}年"
                    st.subheader(f"#{global_idx} 🏠 {row['標題']}")
                    st.write(f"**地址：** {row['地址']} | **屋齡：** {display_age} | **類型：** {row['類型']}")
                    st.write(f"**建坪：** {row['建坪']} | **主+陽：** {row['主+陽']} | **格局：** {row['格局']} | **樓層：** {row['樓層']}")
                    if '車位' in row and pd.notna(row['車位']):
                        st.write(f"**車位：** {row['車位']}")

                    st.markdown(
                        f"""<div style="margin-top:8px">
                        <span style="font-size:13px;color:#888">相似度</span>
                        <div style="display:flex;align-items:center;gap:8px;margin-top:4px">
                            <div style="flex:1;height:6px;background:#e0e0e0;border-radius:3px;max-width:200px">
                                <div style="width:{similarity}%;height:100%;background:{sim_color};border-radius:3px"></div>
                            </div>
                            <span style="font-size:14px;font-weight:600;color:{sim_color}">{similarity}%</span>
                        </div></div>""",
                        unsafe_allow_html=True
                    )

                with col4:
                    st.metric("Price(NT$)", f"${int(row['總價(萬)'] * 10):,}K")
                    if pd.notna(row['建坪']) and row['建坪'] > 0:
                        unit_price = (row['總價(萬)'] * 10000) / row['建坪']
                        st.caption(f"單價: ${unit_price:,.0f}/坪")

                col1, col2, col3, col4, col5, col6, col7 = st.columns([1, 1, 1, 1, 1, 1, 1])
                with col1:
                    property_id = normalize_property_id(row['編號'])
                    is_fav = property_id in st.session_state.get('favorites', [])
                    if st.button("✅ 已收藏" if is_fav else "⭐ 收藏", key=f"ai_fav_{property_id}"):
                        if is_fav:
                            FavoritesManager.remove_favorite(property_id)
                        else:
                            FavoritesManager.add_favorite(row)
                        st.rerun()
                with col7:
                    property_url = f"https://www.sinyi.com.tw/buy/house/{row['編號']}?breadcrumb=list"
                    st.markdown(
                        f'<a href="{property_url}" target="_blank">'
                        f'<button style="padding:5px 10px;">Property Link</button></a>',
                        unsafe_allow_html=True
                    )
                st.markdown("---")

        if total_pages > 1:
            col1, col2, col3, col4, col5 = st.columns([1, 1, 2, 1, 1])
            with col1:
                if st.button("⏮️ 第一頁", disabled=(current_page == 1), key="ai_first"):
                    st.session_state.ai_current_page = 1
                    st.rerun()
            with col2:
                if st.button("⏪ 上一頁", disabled=(current_page == 1), key="ai_prev"):
                    st.session_state.ai_current_page = max(1, current_page - 1)
                    st.rerun()
            with col3:
                new_page = st.selectbox(
                    "選擇頁面",
                    options=range(1, total_pages + 1),
                    index=current_page - 1,
                    key=f"ai_page_select_{current_page}"
                )
                if new_page != current_page:
                    st.session_state.ai_current_page = new_page
                    st.rerun()
            with col4:
                if st.button("下一頁 ⏩", disabled=(current_page == total_pages), key="ai_next"):
                    st.session_state.ai_current_page = current_page + 1
                    st.rerun()
            with col5:
                if st.button("最後一頁 ⏭️", disabled=(current_page == total_pages), key="ai_last"):
                    st.session_state.ai_current_page = total_pages
                    st.rerun()

            st.info(f"📄 第 {current_page} 頁，共 {total_pages} 頁 | 顯示第 {start_idx+1} - {end_idx} 筆資料")
