import streamlit as st
import pandas as pd
import numpy as np
import re
import json
import google.generativeai as genai
from components.favorites import FavoritesManager, normalize_property_id


# ══════════════════════════════════════════════
# 工具函式
# ══════════════════════════════════════════════

def _load_data():
    if 'all_properties_df' in st.session_state and not st.session_state.all_properties_df.empty:
        return st.session_state.all_properties_df
    try:
        df = pd.read_csv('./Data/Taichung-city_buy_properties.csv')
        if '行政區' not in df.columns and '地址' in df.columns:
            df['行政區'] = df['地址'].apply(
                lambda addr: re.search(r'[市縣](.+?[區鄉鎮市])', str(addr)).group(1)
                if pd.notna(addr) and re.search(r'[市縣](.+?[區鄉鎮市])', str(addr)) else ""
            )
        st.session_state.all_properties_df = df
        return df
    except Exception as e:
        return None


def _parse_age(x):
    if pd.isna(x): return np.nan
    match = re.search(r'(\d+\.?\d*)', str(x))
    return float(match.group(1)) if match else np.nan


def _parse_floor(x):
    if pd.isna(x): return np.nan
    try:
        val = re.search(r'\d+', str(x).split('樓')[0])
        return int(val.group()) if val else np.nan
    except:
        return np.nan


def tool_search_properties(district="", housetype="", budget_max=0, budget_min=0, rooms=0, age_max=0):
    """搜尋房屋工具"""
    df = _load_data()
    if df is None:
        return []

    result = df.copy()

    if district and district != "不限":
        result = result[result['行政區'].astype(str).str.contains(district, na=False)]

    if housetype and housetype != "不限":
        result = result[result['類型'].astype(str).str.contains(housetype, case=False, na=False)]

    if budget_max > 0:
        result['_price'] = pd.to_numeric(result['總價(萬)'], errors='coerce')
        result = result[result['_price'] <= budget_max]

    if budget_min > 0:
        result['_price'] = pd.to_numeric(result['總價(萬)'], errors='coerce')
        result = result[result['_price'] >= budget_min]

    if rooms > 0 and '格局' in result.columns:
        def get_rooms(layout):
            m = re.search(r'(\d+)房', str(layout))
            return int(m.group(1)) if m else 0
        result['_rooms'] = result['格局'].apply(get_rooms)
        result = result[result['_rooms'] >= rooms]

    if age_max > 0 and '屋齡' in result.columns:
        result['_age'] = result['屋齡'].apply(_parse_age)
        result = result[result['_age'] <= age_max]

    return result.to_dict('records')


def tool_score_properties(properties, weights=None, use_pool=None):
    if not properties:
        return []

    if weights is None:
        weights = st.session_state.get('score_weights', {
            "價格競爭力": 30, "空間效率": 25,
            "屋齡優勢": 20, "樓層定位": 15, "格局流動性": 10
        })

    first = properties[0]
    district = first.get('行政區', '')
    housetype = str(first.get('類型', '')).strip()
    if '/' in housetype:
        housetype = housetype.split('/')[0].strip()

    if use_pool is not None:
        # 有額外條件：用傳入的搜尋結果當母體
        df_pool = pd.DataFrame(use_pool)
    else:
        # 只有區域類型：用全區當母體
        all_df = _load_data()
        if all_df is not None and not all_df.empty and district:
            df_pool = all_df[
                (all_df['行政區'] == district) &
                (all_df['類型'].astype(str).str.contains(housetype, case=False, na=False))
            ].copy()
        else:
            df_pool = pd.DataFrame(properties)

        if df_pool.empty:
            df_pool = pd.DataFrame(properties)

    def score_one(row):
        try:
            target_price = pd.to_numeric(row.get('總價(萬)', np.nan), errors='coerce')
            target_area  = pd.to_numeric(row.get('建坪', np.nan), errors='coerce')
            if pd.isna(target_price) or pd.isna(target_area) or target_area == 0:
                return np.nan

            compare = df_pool.copy()
            compare['_p'] = pd.to_numeric(compare['總價(萬)'], errors='coerce')
            compare['_a'] = pd.to_numeric(compare['建坪'], errors='coerce')
            compare = compare.dropna(subset=['_p', '_a'])
            n = len(compare)
            if n == 0: return np.nan

            price_pct = (compare['_p'] < target_price).sum() / n * 100
            score_price = max(0.0, min(10.0, 10 - price_pct / 10))

            score_space = 5.0
            actual = pd.to_numeric(row.get('主+陽', np.nan), errors='coerce')
            if not pd.isna(actual) and float(actual) > 0 and float(target_area) > 0:
                usage = float(actual) / float(target_area)
                compare['_r'] = pd.to_numeric(compare['主+陽'], errors='coerce') / compare['_a']
                med = compare['_r'].median()
                if not pd.isna(med) and med > 0:
                    score_space = max(0.0, min(10.0, (usage / med) * 5))

            score_age = 5.0
            compare['_age'] = compare['屋齡'].apply(_parse_age)
            target_age = _parse_age(row.get('屋齡'))
            df_age = compare.dropna(subset=['_age'])
            if len(df_age) > 0 and not pd.isna(target_age):
                age_pct = (df_age['_age'] < target_age).sum() / len(df_age) * 100
                score_age = max(0.0, min(10.0, 10 - age_pct / 10))

            score_floor = 5.0
            compare['_floor'] = compare['樓層'].apply(_parse_floor)
            target_floor = _parse_floor(row.get('樓層'))
            df_floor = compare.dropna(subset=['_floor'])
            if len(df_floor) > 0 and not pd.isna(target_floor):
                floor_pct = (df_floor['_floor'] < target_floor).sum() / len(df_floor) * 100
                score_floor = max(0.0, min(10.0, 10 - abs(floor_pct - 50) / 5))

            score_layout = 0.0
            target_layout = str(row.get('格局', '')).strip()
            if target_layout and '格局' in compare.columns:
                same = (compare['格局'].astype(str).str.strip() == target_layout).sum()
                score_layout = max(0.0, min(10.0, (same / n * 100) / 3))

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

    # 對全區所有房屋評分，不只是搜尋結果
    all_records = df_pool.to_dict('records')
    scored = []
    for p in all_records:
        cp = score_one(p)
        p['CP分數'] = cp if not pd.isna(cp) else 0
        scored.append(p)

    scored.sort(key=lambda x: x.get('CP分數', 0), reverse=True)
    return scored

def tool_get_market_stats(district="", housetype=""):
    """取得市場統計工具"""
    df = _load_data()
    if df is None:
        return {}

    filtered = df.copy()
    if district:
        filtered = filtered[filtered['行政區'].astype(str).str.contains(district, na=False)]
    if housetype:
        filtered = filtered[filtered['類型'].astype(str).str.contains(housetype, case=False, na=False)]

    if filtered.empty:
        return {}

    filtered['_price'] = pd.to_numeric(filtered['總價(萬)'], errors='coerce')
    filtered['_area']  = pd.to_numeric(filtered['建坪'], errors='coerce')
    filtered['_age']   = filtered['屋齡'].apply(_parse_age)

    stats = {
        "區域": district or "全台中市",
        "類型": housetype or "不限",
        "總筆數": int(len(filtered)),
        "中位數總價(萬)": round(filtered['_price'].median(), 0),
        "平均總價(萬)": round(filtered['_price'].mean(), 0),
        "最低總價(萬)": round(filtered['_price'].min(), 0),
        "最高總價(萬)": round(filtered['_price'].max(), 0),
        "中位數建坪": round(filtered['_area'].median(), 1),
        "中位數屋齡": round(filtered['_age'].median(), 1),
    }

    if filtered['_area'].notna().any() and filtered['_price'].notna().any():
        valid = filtered.dropna(subset=['_price', '_area'])
        valid = valid[valid['_area'] > 0]
        valid['_unit'] = valid['_price'] / valid['_area']
        stats["中位數單價(萬/坪)"] = round(valid['_unit'].median(), 2)
    stats = {k: (int(v) if isinstance(v, np.integer) else float(v) if isinstance(v, np.floating) else v) for k, v in stats.items()}
    return stats


# ══════════════════════════════════════════════
# Gemini Function Calling 定義
# ══════════════════════════════════════════════

TOOLS = [
    {
        "function_declarations": [
            {
                "name": "search_properties",
                "description": "搜尋台中市房屋，可依行政區、類型、預算、房間數、屋齡篩選",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "district":   {"type": "string",  "description": "行政區，例如：西屯區、北屯區"},
                        "housetype":  {"type": "string",  "description": "房屋類型：大樓、華廈、公寓、套房、透天、別墅"},
                        "budget_max": {"type": "number",  "description": "預算上限（萬）"},
                        "budget_min": {"type": "number",  "description": "預算下限（萬）"},
                        "rooms":      {"type": "integer", "description": "最少房間數"},
                        "age_max":    {"type": "number",  "description": "最大屋齡（年）"},
                    },
                    "required": []
                }
            },
            {
                "name": "score_properties",
                "description": "對房屋清單計算 CP 值評分，依五大面向加權計算，回傳評分後排序的清單",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "property_titles": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "要評分的房屋標題清單（從 search_properties 結果取得）"
                        }
                    },
                    "required": ["property_titles"]
                }
            },
            {
                "name": "get_market_stats",
                "description": "取得特定區域與類型的市場統計數據，包含中位數價格、平均坪數、屋齡等",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "district":  {"type": "string", "description": "行政區名稱"},
                        "housetype": {"type": "string", "description": "房屋類型"},
                    },
                    "required": []
                }
            }
        ]
    }
]


# ══════════════════════════════════════════════
# Agent 執行邏輯
# ══════════════════════════════════════════════

def run_agent(user_input, model, step_container):
    """執行 Agent，回傳最終回覆與推薦房屋"""

    history = st.session_state.get('assistant_history', [])

    messages = []
    for h in history[-6:]:
        if h['role'] == 'user':
            messages.append({"role": "user", "parts": [{"text": h['content']}]})
        elif h['role'] == 'assistant' and h.get('text'):
            messages.append({"role": "model", "parts": [{"text": h['text']}]})

    messages.append({"role": "user", "parts": [{"text": user_input}]})

    current_search_results = st.session_state.get('_agent_search_cache', [])
    recommended = []
    step_num = [0]

    def show_step(icon, text, detail=""):
        step_num[0] += 1
        with step_container:
            st.markdown(f"**{icon} 步驟 {step_num[0]}：{text}**")
            if detail:
                st.caption(detail)

    max_iterations = 5
    iteration = 0

    while iteration < max_iterations:
        iteration += 1

        try:
            response = model.generate_content(
                messages,
                tools=TOOLS,
                generation_config={"temperature": 0.3}
            )
        except Exception as e:
            return f"❌ Gemini 呼叫錯誤：{e}", []

        candidate = response.candidates[0]
        parts = candidate.content.parts

        has_tool_call = any(hasattr(p, 'function_call') and p.function_call.name for p in parts)
        text_parts = [p.text for p in parts if hasattr(p, 'text') and p.text]

        if not has_tool_call:
            final_text = "\n".join(text_parts)

            one_keywords = ["最推薦", "推薦一間", "推薦1間", "你最推薦", "最好的一間", "哪一間", "哪間最好", "你推薦"]
            is_one = any(k in user_input for k in one_keywords)

            scored_cache = st.session_state.get('_agent_scored_cache', [])
            search_pool = scored_cache if scored_cache else current_search_results

            if not recommended:
                if is_one:
                    mentioned = []
                    for house in search_pool:
                        title = house.get('標題', '')
                        if not title:
                            continue
                        if title[:10] in final_text:
                            mentioned.append(house)
                    recommended = mentioned[:1] if mentioned else (scored_cache[:1] if scored_cache else [])
                else:
                    recommended = scored_cache[:10] if scored_cache else []

            return final_text, recommended
        
        tool_results = []
        for part in parts:
            if not (hasattr(part, 'function_call') and part.function_call.name):
                continue

            fn_name = part.function_call.name
            fn_args = dict(part.function_call.args)

            if fn_name == "search_properties":
                show_step("🔍", "搜尋房屋",
                    f"條件：{fn_args.get('district','')} {fn_args.get('housetype','')} "
                    f"預算{fn_args.get('budget_max','')}萬 {fn_args.get('rooms','')}房")

                results = tool_search_properties(**fn_args)
                current_search_results = results
                st.session_state['_agent_search_cache'] = results

                show_step("✅", f"找到 {len(results)} 筆房屋，開始計算 CP 值...")

                # 判斷是否有額外條件
                has_extra_conditions = any([
                    fn_args.get('budget_max', 0) > 0,
                    fn_args.get('budget_min', 0) > 0,
                    fn_args.get('rooms', 0) > 0,
                    fn_args.get('age_max', 0) > 0,
                ])

                if has_extra_conditions:
                    # 有額外條件：用搜尋結果當母體
                    scored = tool_score_properties(results, use_pool=results)
                else:
                    # 只有區域和類型：用全區當母體
                    scored = tool_score_properties(results)
                st.session_state['_agent_scored_cache'] = scored

                show_step("📊", f"CP 值計算完成，前 5 名整理完畢")

                # 傳給 Gemini 的是已排序的 CP 值結果
                top_for_gemini = scored[:10]
                simplified = [{
                    '排名': i + 1,
                    '標題': r.get('標題', ''),
                    '行政區': r.get('行政區', ''),
                    '總價(萬)': r.get('總價(萬)', ''),
                    '建坪': r.get('建坪', ''),
                    '格局': r.get('格局', ''),
                    '樓層': r.get('樓層', ''),
                    '屋齡': r.get('屋齡', ''),
                    '類型': r.get('類型', ''),
                    'CP分數': r.get('CP分數', 0),
                } for i, r in enumerate(top_for_gemini)]

                tool_results.append({
                    "function_response": {
                        "name": fn_name,
                        "response": {"result": json.dumps(simplified, ensure_ascii=False)}
                    }
                })

            elif fn_name == "score_properties":
                show_step("📊", "計算 CP 值評分")

                titles = fn_args.get('property_titles', [])
                to_score = [r for r in current_search_results
                            if r.get('標題', '') in titles] if titles else current_search_results

                scored = tool_score_properties(to_score)
                st.session_state['_agent_scored_cache'] = scored
                top_n = 1 if any(k in user_input for k in ["最推薦", "推薦一間", "推薦1間", "你最推薦", "最好的", "哪一間", "哪間最好", "你推薦"]) else 5
                recommended = scored[:top_n]

                show_step("🏆", f"評分完成，前 5 名已整理")

                score_summary = [{
                    '標題': r.get('標題', ''),
                    '總價(萬)': r.get('總價(萬)', ''),
                    '格局': r.get('格局', ''),
                    '屋齡': r.get('屋齡', ''),
                    'CP分數': r.get('CP分數', 0),
                } for r in recommended]

                tool_results.append({
                    "function_response": {
                        "name": fn_name,
                        "response": {"result": json.dumps(score_summary, ensure_ascii=False)}
                    }
                })

            elif fn_name == "get_market_stats":
                show_step("📈", "取得市場統計",
                    f"{fn_args.get('district','')} {fn_args.get('housetype','')}")

                stats = tool_get_market_stats(**fn_args)

                show_step("✅", "市場數據取得完成")

                tool_results.append({
                    "function_response": {
                        "name": fn_name,
                        "response": {"result": json.dumps(stats, ensure_ascii=False)}
                    }
                })

        messages.append({"role": "model", "parts": parts})
        messages.append({"role": "user", "parts": tool_results})

    return "（已完成分析）", recommended


# ══════════════════════════════════════════════
# 頁面渲染
# ══════════════════════════════════════════════

def render_assistant_page():
    st.title("🤖 智能小幫手 — 房小智")
    st.caption("告訴我你的需求，我來幫你找最適合的房子")

    gemini_key = st.session_state.get("GEMINI_KEY", "")
    if not gemini_key:
        st.error("❌ 請先在側邊欄設定 Gemini API Key")
        return

    try:
        genai.configure(api_key=gemini_key)
        system_instruction = """你是台中市房產 AI 助手，名字叫「房小智」。

你可以使用以下工具幫助使用者：
- search_properties：搜尋房屋（系統會自動計算CP值並排序）
- score_properties：不需要再呼叫，search_properties 已包含CP值計算
- get_market_stats：取得市場統計數據

判斷原則：
- 任何找房子的需求 → 只需呼叫 search_properties，不需要再呼叫 score_properties
- 使用者問「市場行情」「房價概況」→ 呼叫 get_market_stats
- 一般問題不需要工具，直接回答

注意：
- 用繁體中文回答
- 語氣親切自然
- 搜尋結果已依CP值由高到低排序，直接列出前10名並逐一說明
- 每間都要包含：排名、標題、總價、格局、屋齡、CP分數、推薦理由
- 使用者後續針對任何一間提問，直接根據已列出的資料回答
- 推薦時房屋標題必須完整引用原始資料的標題，不可縮寫或修改
- 不要說「請稍等」之類的話，直接呼叫工具執行"""

        model = genai.GenerativeModel(
            'gemini-2.5-flash',
            system_instruction=system_instruction
        )

    except Exception as e:
        st.error(f"❌ Gemini 初始化錯誤：{e}")
        return

    if 'assistant_history' not in st.session_state:
        st.session_state.assistant_history = []

    # ── 快速提問 ──
    st.markdown("#### 💡 快速提問")
    preset_cols = st.columns(3)
    presets = [
        "幫我找西屯區 2000 萬內 3 房大樓",
        "北屯區 CP 值最高的大樓有哪些？",
        "西屯區目前的房價行情如何？",
        "找一間屋齡 10 年內、3 房、預算 1500 萬的房子",
        "南屯區華廈的市場概況",
        "推薦幾間適合小家庭的房子",
    ]
    for i, preset in enumerate(presets):
        with preset_cols[i % 3]:
            if st.button(preset, key=f"preset_{i}", use_container_width=True):
                st.session_state['_pending_input'] = preset
                st.rerun()

    st.markdown("---")

    # ── 對話歷史 ──
    chat_container = st.container()
    with chat_container:
        for i, msg in enumerate(st.session_state.assistant_history):
            if msg['role'] == 'user':
                with st.chat_message("user"):
                    st.write(msg['content'])
            elif msg['role'] == 'assistant':
                with st.chat_message("assistant"):
                    if msg.get('text'):
                        st.write(msg['text'])

                    if msg.get('recommended'):
                        st.markdown("#### 🏆 推薦房屋")
                        msg_content = msg.get('user_query', '')
                        one_keywords = ["最推薦", "推薦一間", "推薦1間", "你最推薦", "最好的一間", "最好的房子", "哪一間最好"]
                        show_limit = 1 if any(k in msg_content for k in one_keywords) else 10
                        for j, house in enumerate(msg['recommended'][:show_limit]):
                            with st.container(border=True):
                                cp = house.get('CP分數', 0)
                                color = "#1D9E75" if cp >= 70 else "#EF9F27" if cp >= 50 else "#888780"
                                rank_medal = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"][j] if j < 5 else f"#{j+1}"

                                col1, col2, col3 = st.columns([4, 1, 1])
                                with col1:
                                    st.markdown(f"**{rank_medal} {house.get('標題', '')}**")
                                    st.caption(
                                        f"📍 {house.get('行政區', '')} ｜ "
                                        f"💰 {house.get('總價(萬)', '')} 萬 ｜ "
                                        f"{house.get('格局', '')} ｜ "
                                        f"屋齡 {house.get('屋齡', '')} ｜ "
                                        f"建坪 {house.get('建坪', '')} 坪"
                                    )
                                with col2:
                                    st.markdown(
                                        f"<div style='text-align:center;padding:8px'>"
                                        f"<div style='font-size:11px;color:#aaa'>CP分數</div>"
                                        f"<div style='font-size:22px;font-weight:bold;color:{color}'>{cp}</div>"
                                        f"</div>",
                                        unsafe_allow_html=True
                                    )
                                with col3:
                                    property_id = normalize_property_id(house.get('編號', ''))
                                    is_fav = property_id in st.session_state.get('favorites', [])
                                    if st.button(
                                        "✅ 已收藏" if is_fav else "⭐ 收藏",
                                        key=f"asst_fav_{i}_{j}_{property_id}",
                                        disabled=is_fav,
                                        use_container_width=True
                                    ):
                                        all_df = _load_data()
                                        if all_df is not None and property_id:
                                            matched = all_df[
                                                all_df['編號'].map(normalize_property_id) == property_id
                                            ]
                                            if not matched.empty:
                                                FavoritesManager.add_favorite(matched.iloc[0])
                                                st.rerun()

    # ── 輸入框 ──
    col_input, col_clear = st.columns([5, 1])
    with col_clear:
        if st.button("🗑️ 清除對話", use_container_width=True):
            st.session_state.assistant_history = []
            st.session_state.pop('_agent_search_cache', None)
            st.rerun()

    user_input = st.chat_input("輸入你的需求，例如：幫我找西屯區 2000 萬內 3 房大樓")

    pending = st.session_state.pop('_pending_input', None)
    final_input = pending or user_input

    if final_input:
        # 每次新問題清掉上一次的 cache
        st.session_state.pop('_agent_scored_cache', None)
        st.session_state.pop('_agent_search_cache', None)
        
        st.session_state.assistant_history.append({
            'role': 'user',
            'content': final_input
        })

        with st.chat_message("assistant"):
            step_placeholder = st.empty()
            with step_placeholder.container():
                st.markdown("**⚙️ Agent 執行中...**")
                step_box = st.container()

            with st.spinner("思考中..."):
                final_reply, recommended = run_agent(final_input, model, step_box)

            step_placeholder.empty()

            st.write(final_reply)

            if recommended:
                st.markdown("#### 🏆 推薦房屋")
                # 判斷顯示幾筆
                one_keywords = ["最推薦", "推薦一間", "推薦1間", "你最推薦", "最好的一間", "最好的房子", "哪一間最好"]
                show_limit = 1 if any(k in final_input for k in one_keywords) else 10
                for j, house in enumerate(recommended[:show_limit]):
                    with st.container(border=True):
                        cp = house.get('CP分數', 0)
                        color = "#1D9E75" if cp >= 70 else "#EF9F27" if cp >= 50 else "#888780"
                        rank_medal = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"][j] if j < 5 else f"#{j+1}"

                        col1, col2, col3 = st.columns([4, 1, 1])
                        with col1:
                            st.markdown(f"**{rank_medal} {house.get('標題', '')}**")
                            st.caption(
                                f"📍 {house.get('行政區', '')} ｜ "
                                f"💰 {house.get('總價(萬)', '')} 萬 ｜ "
                                f"{house.get('格局', '')} ｜ "
                                f"屋齡 {house.get('屋齡', '')} ｜ "
                                f"建坪 {house.get('建坪', '')} 坪"
                            )
                        with col2:
                            st.markdown(
                                f"<div style='text-align:center;padding:8px'>"
                                f"<div style='font-size:11px;color:#aaa'>CP分數</div>"
                                f"<div style='font-size:22px;font-weight:bold;color:{color}'>{cp}</div>"
                                f"</div>",
                                unsafe_allow_html=True
                            )
                        with col3:
                            property_id = normalize_property_id(house.get('編號', ''))
                            is_fav = property_id in st.session_state.get('favorites', [])
                            if st.button(
                                "✅ 已收藏" if is_fav else "⭐ 收藏",
                                key=f"asst_new_fav_{j}_{property_id}",
                                disabled=is_fav,
                                use_container_width=True
                            ):
                                all_df = _load_data()
                                if all_df is not None and property_id:
                                    matched = all_df[
                                        all_df['編號'].map(normalize_property_id) == property_id
                                    ]
                                    if not matched.empty:
                                        FavoritesManager.add_favorite(matched.iloc[0])
                                        st.rerun()

        st.session_state.assistant_history.append({
            'role': 'assistant',
            'text': final_reply,
            'recommended': recommended,
            'user_query': final_input
        })

        st.rerun()
