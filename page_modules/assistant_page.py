import inspect
import streamlit as st
import pandas as pd
import numpy as np
import re
import json
import html
import google.generativeai as genai
from components.favorites import FavoritesManager, normalize_property_id
from utils import get_property_image_url
from components.nuisance_lookup import (
    lookup_nearby_nuisances,
    gemini_nuisance_payload,
    render_nuisance_result,
    DEFAULT_RADIUS as NUISANCE_RADIUS,
)


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


def _native(value):
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    return value


def _simplify_house(row, extra=None):
    area = pd.to_numeric(row.get("建坪"), errors="coerce")
    price = pd.to_numeric(row.get("總價(萬)"), errors="coerce")
    unit = ""
    if pd.notna(area) and pd.notna(price) and float(area) > 0:
        unit = round(float(price) / float(area), 2)
    data = {
        "標題": row.get("標題", ""),
        "編號": str(row.get("編號", "")),
        "行政區": row.get("行政區", ""),
        "地址": row.get("地址", ""),
        "類型": row.get("類型", ""),
        "總價(萬)": _native(row.get("總價(萬)", "")),
        "建坪": _native(row.get("建坪", "")),
        "主+陽": _native(row.get("主+陽", "")),
        "格局": row.get("格局", ""),
        "樓層": row.get("樓層", ""),
        "屋齡": _native(row.get("屋齡", "")),
        "車位": row.get("車位", ""),
        "單價(萬/坪)": unit,
        "CP分數": _native(row.get("CP分數", "")),
    }
    if extra:
        data.update(extra)
    return data


def _lookup_houses(titles=None, property_id=""):
    """從快取或完整資料找出房屋。"""
    titles = [str(t).strip() for t in (titles or []) if str(t).strip()]
    pid = normalize_property_id(property_id)
    pools = []
    for key in ("_agent_scored_cache", "_agent_search_cache"):
        cached = st.session_state.get(key) or []
        if cached:
            pools.append(pd.DataFrame(cached))
    df = _load_data()
    if df is not None and not df.empty:
        pools.append(df)

    found = []
    seen = set()

    def take_row(row):
        hid = normalize_property_id(row.get("編號", ""))
        title = str(row.get("標題", ""))
        key = hid or title
        if not key or key in seen:
            return
        seen.add(key)
        found.append(row if isinstance(row, dict) else row.to_dict())

    for pool in pools:
        if pool is None or pool.empty:
            continue
        if pid and "編號" in pool.columns:
            matched = pool[pool["編號"].map(normalize_property_id) == pid]
            for _, row in matched.iterrows():
                take_row(row)
        if titles and "標題" in pool.columns:
            for title in titles:
                matched = pool[pool["標題"].astype(str).str.contains(title, na=False, regex=False)]
                if matched.empty:
                    matched = pool[pool["標題"].astype(str) == title]
                for _, row in matched.head(3).iterrows():
                    take_row(row)
        if found and (pid or (titles and len(found) >= len(titles))):
            break
    return found


def tool_search_properties(
    district="", housetype="", budget_max=0, budget_min=0, rooms=0,
    age_max=0, age_min=0, area_min=0, floor_min=0, parking=""
):
    """搜尋房屋工具"""
    df = _load_data()
    if df is None:
        return []

    result = df.copy()

    if district and district != "不限":
        result = result[result["行政區"].astype(str).str.contains(district, na=False)]

    if housetype and housetype != "不限":
        result = result[result["類型"].astype(str).str.contains(housetype, case=False, na=False)]

    result["_price"] = pd.to_numeric(result["總價(萬)"], errors="coerce")
    if budget_max and float(budget_max) > 0:
        result = result[result["_price"] <= float(budget_max)]
    if budget_min and float(budget_min) > 0:
        result = result[result["_price"] >= float(budget_min)]

    if rooms and int(rooms) > 0 and "格局" in result.columns:
        def get_rooms(layout):
            m = re.search(r"(\d+)房", str(layout))
            return int(m.group(1)) if m else 0
        result["_rooms"] = result["格局"].apply(get_rooms)
        result = result[result["_rooms"] >= int(rooms)]

    if (age_max and float(age_max) > 0) or (age_min and float(age_min) > 0):
        result["_age"] = result["屋齡"].apply(_parse_age)
        if age_max and float(age_max) > 0:
            result = result[result["_age"] <= float(age_max)]
        if age_min and float(age_min) > 0:
            result = result[result["_age"] >= float(age_min)]

    if area_min and float(area_min) > 0:
        result["_area"] = pd.to_numeric(result["建坪"], errors="coerce")
        result = result[result["_area"] >= float(area_min)]

    if floor_min and int(floor_min) > 0:
        result["_floor"] = result["樓層"].apply(_parse_floor)
        result = result[result["_floor"] >= int(floor_min)]

    if parking in ("需要", "要", "有車位"):
        result = result[
            (result["車位"].notna())
            & (result["車位"].astype(str) != "無車位")
            & (result["車位"].astype(str) != "0")
        ]
    elif parking in ("不要", "無車位"):
        result = result[
            (result["車位"].isna())
            | (result["車位"].astype(str) == "無車位")
            | (result["車位"].astype(str) == "0")
        ]

    return result.to_dict("records")


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


def tool_get_property_detail(title="", property_id=""):
    houses = _lookup_houses([title] if title else [], property_id)
    if not houses:
        return {"error": "找不到這間房屋，請提供更完整的標題或編號"}
    return _simplify_house(houses[0])


def tool_compare_properties(titles=None):
    if isinstance(titles, str):
        titles = [t.strip() for t in re.split(r"[,，、]", titles) if t.strip()]
    titles = titles or []
    houses = _lookup_houses(titles)
    if len(houses) < 2:
        return {"error": "請提供至少兩間房屋標題才能比較"}

    simplified = [_simplify_house(h) for h in houses[:4]]
    prices = [pd.to_numeric(h.get("總價(萬)"), errors="coerce") for h in simplified]
    units = [pd.to_numeric(h.get("單價(萬/坪)"), errors="coerce") for h in simplified]
    notes = []
    valid_prices = [(i, p) for i, p in enumerate(prices) if pd.notna(p)]
    if valid_prices:
        cheapest = min(valid_prices, key=lambda x: x[1])
        notes.append(f"總價最低：{simplified[cheapest[0]].get('標題')}（{cheapest[1]} 萬）")
    valid_units = [(i, u) for i, u in enumerate(units) if pd.notna(u) and u != ""]
    if valid_units:
        lowest_unit = min(valid_units, key=lambda x: x[1])
        notes.append(f"單價最低：{simplified[lowest_unit[0]].get('標題')}（{lowest_unit[1]} 萬/坪）")
    return {"houses": simplified, "notes": notes}


def tool_find_similar_properties(title="", limit=5):
    houses = _lookup_houses([title] if title else [])
    if not houses:
        return {"error": "找不到基準房屋，請先搜尋或提供完整標題"}
    target = houses[0]
    df = _load_data()
    if df is None or df.empty:
        return []

    district = str(target.get("行政區", ""))
    housetype = str(target.get("類型", "")).split("/")[0].strip()
    price = pd.to_numeric(target.get("總價(萬)"), errors="coerce")
    area = pd.to_numeric(target.get("建坪"), errors="coerce")
    target_id = normalize_property_id(target.get("編號", ""))

    pool = df.copy()
    if district:
        pool = pool[pool["行政區"].astype(str) == district]
    if housetype:
        pool = pool[pool["類型"].astype(str).str.contains(housetype, case=False, na=False)]
    if target_id:
        pool = pool[pool["編號"].map(normalize_property_id) != target_id]
    pool = pool[pool["標題"].astype(str) != str(target.get("標題", ""))]

    pool["_price"] = pd.to_numeric(pool["總價(萬)"], errors="coerce")
    pool["_area"] = pd.to_numeric(pool["建坪"], errors="coerce")
    if pd.notna(price) and price > 0:
        pool = pool[pool["_price"].between(price * 0.75, price * 1.25)]
    if pd.notna(area) and area > 0:
        pool["_area_diff"] = (pool["_area"] - area).abs()
        pool = pool.sort_values("_area_diff")
    similar = pool.head(int(limit) or 5)
    return [_simplify_house(row) for _, row in similar.iterrows()]


def tool_list_favorites():
    fav_df = FavoritesManager.get_favorites_data()
    if fav_df is None or fav_df.empty:
        return {"count": 0, "houses": [], "message": "目前沒有收藏"}
    houses = [_simplify_house(row) for _, row in fav_df.iterrows()]
    return {"count": len(houses), "houses": houses}


def tool_add_to_favorites(title="", property_id=""):
    houses = _lookup_houses([title] if title else [], property_id)
    if not houses:
        return {"ok": False, "message": "找不到要收藏的房屋"}
    FavoritesManager.add_favorite(pd.Series(houses[0]))
    return {"ok": True, "message": f"已收藏：{houses[0].get('標題', '')}", "house": _simplify_house(houses[0])}


def tool_rank_districts(housetype="", sort_by="median_unit"):
    df = _load_data()
    if df is None or df.empty:
        return []
    pool = df.copy()
    if housetype:
        pool = pool[pool["類型"].astype(str).str.contains(housetype, case=False, na=False)]
    pool["_price"] = pd.to_numeric(pool["總價(萬)"], errors="coerce")
    pool["_area"] = pd.to_numeric(pool["建坪"], errors="coerce")
    pool = pool.dropna(subset=["行政區", "_price"])
    pool["_unit"] = pool["_price"] / pool["_area"].replace(0, np.nan)

    grouped = pool.groupby("行政區").agg(
        物件數=("_price", "count"),
        中位數總價萬=("_price", "median"),
        平均總價萬=("_price", "mean"),
        中位數單價萬坪=("_unit", "median"),
        中位數建坪=("_area", "median"),
    ).reset_index()
    sort_col = "中位數單價萬坪" if sort_by != "median_price" else "中位數總價萬"
    grouped = grouped.sort_values(sort_col, ascending=True)
    rows = []
    for _, row in grouped.head(12).iterrows():
        rows.append({
            "行政區": row["行政區"],
            "物件數": int(row["物件數"]),
            "中位數總價(萬)": round(float(row["中位數總價萬"]), 0),
            "平均總價(萬)": round(float(row["平均總價萬"]), 0),
            "中位數單價(萬/坪)": round(float(row["中位數單價萬坪"]), 2) if pd.notna(row["中位數單價萬坪"]) else "",
            "中位數建坪": round(float(row["中位數建坪"]), 1) if pd.notna(row["中位數建坪"]) else "",
        })
    return rows


def tool_check_nearby_nuisances(title="", property_id="", radius=500):
    houses = _lookup_houses([title] if title else [], property_id)
    if not houses:
        scored = st.session_state.get("_agent_scored_cache") or []
        if scored and not title and not property_id:
            houses = scored[:1]
    if not houses:
        return {"error": "請先指出要查哪一間，或先搜尋推薦物件"}, None, []

    house = houses[0]
    result = lookup_nearby_nuisances(
        address=str(house.get("地址", "")),
        title=str(house.get("標題", "")),
        radius=int(radius or NUISANCE_RADIUS),
    )
    return gemini_nuisance_payload(result), result, houses[:1]


# ══════════════════════════════════════════════
# Gemini Function Calling 定義
# ══════════════════════════════════════════════

TOOLS = [
    {
        "function_declarations": [
            {
                "name": "search_properties",
                "description": "搜尋台中市房屋。可用行政區、類型、預算、房間、屋齡、建坪、樓層、車位篩選。系統會自動計算 CP 值並排序。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "district":   {"type": "string",  "description": "行政區，例如：西屯區、北屯區"},
                        "housetype":  {"type": "string",  "description": "房屋類型：大樓、華廈、公寓、套房、透天、別墅"},
                        "budget_max": {"type": "number",  "description": "預算上限（萬）"},
                        "budget_min": {"type": "number",  "description": "預算下限（萬）"},
                        "rooms":      {"type": "integer", "description": "最少房間數"},
                        "age_max":    {"type": "number",  "description": "最大屋齡（年）"},
                        "age_min":    {"type": "number",  "description": "最小屋齡（年）"},
                        "area_min":   {"type": "number",  "description": "最小建坪"},
                        "floor_min":  {"type": "integer", "description": "最低樓層"},
                        "parking":    {"type": "string",  "description": "車位：需要 或 不要"},
                    },
                    "required": []
                }
            },
            {
                "name": "get_market_stats",
                "description": "取得特定區域與類型的市場統計，含中位數價格、坪數、屋齡、單價",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "district":  {"type": "string", "description": "行政區名稱"},
                        "housetype": {"type": "string", "description": "房屋類型"},
                    },
                    "required": []
                }
            },
            {
                "name": "get_property_detail",
                "description": "查詢單筆房屋完整資訊。用於追問某一間的車位、樓層、單價、地址等細節。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string", "description": "房屋標題，可使用完整標題或關鍵片段"},
                        "property_id": {"type": "string", "description": "房屋編號"},
                    },
                    "required": []
                }
            },
            {
                "name": "compare_properties",
                "description": "比較兩間以上房屋的總價、單價、坪數、屋齡、格局、車位",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "titles": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "要比較的房屋標題清單"
                        }
                    },
                    "required": ["titles"]
                }
            },
            {
                "name": "find_similar_properties",
                "description": "找出與指定房屋同區、同類型、價格接近的替代物件",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string", "description": "基準房屋標題"},
                        "limit": {"type": "integer", "description": "最多回傳幾筆，預設 5"},
                    },
                    "required": ["title"]
                }
            },
            {
                "name": "list_favorites",
                "description": "列出使用者目前收藏的房屋",
                "parameters": {"type": "object", "properties": {}}
            },
            {
                "name": "add_to_favorites",
                "description": "把指定房屋加入收藏，之後可到分析頁做深度分析",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string", "description": "房屋標題"},
                        "property_id": {"type": "string", "description": "房屋編號"},
                    },
                    "required": []
                }
            },
            {
                "name": "rank_districts",
                "description": "比較台中各行政區行情，預設依中位數單價由低到高排序",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "housetype": {"type": "string", "description": "可限定類型，例如大樓"},
                        "sort_by": {"type": "string", "description": "median_unit 或 median_price"},
                    },
                    "required": []
                }
            },
            {
                "name": "check_nearby_nuisances",
                "description": "查詢單一房屋周邊嫌惡設施（加油站、基地台、垃圾場、夜市、宮廟、工業區等），回傳最近距離與數量。一次只查一間。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string", "description": "房屋標題，追問時用上一間推薦的完整標題"},
                        "property_id": {"type": "string", "description": "房屋編號"},
                        "radius": {"type": "number", "description": "搜尋半徑公尺，預設 500"},
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

def _pack_tool(name, payload):
    return {
        "function_response": {
            "name": name,
            "response": {"result": json.dumps(payload, ensure_ascii=False, default=str)}
        }
    }


def run_agent(user_input, model, step_container):
    """執行 Agent，回傳最終回覆與推薦房屋"""

    history = st.session_state.get('assistant_history', [])

    messages = []
    for h in history[-8:]:
        if h['role'] == 'user':
            messages.append({"role": "user", "parts": [{"text": h['content']}]})
        elif h['role'] == 'assistant' and h.get('text'):
            messages.append({"role": "model", "parts": [{"text": h['text']}]})

    last_titles = [h.get('標題', '') for h in (st.session_state.get('_agent_scored_cache') or [])[:5] if h.get('標題')]
    fav_n = len(st.session_state.get('favorites') or [])
    context = (
        f"【系統狀態】收藏 {fav_n} 間。"
        + (f" 上次推薦：{'、'.join(last_titles)}。" if last_titles else "")
        + f"\n使用者問題：{user_input}"
    )
    messages.append({"role": "user", "parts": [{"text": context}]})

    current_search_results = st.session_state.get('_agent_search_cache', []) or []
    recommended = []
    step_num = [0]

    def show_step(icon, text, detail=""):
        step_num[0] += 1
        with step_container:
            st.markdown(f"**{icon} 步驟 {step_num[0]}：{text}**")
            if detail:
                st.caption(detail)

    max_iterations = 6
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
            scored_cache = st.session_state.get('_agent_scored_cache', []) or []
            search_pool = scored_cache if scored_cache else current_search_results

            if not recommended:
                if is_one:
                    mentioned = [h for h in search_pool if h.get('標題') and h.get('標題')[:10] in final_text]
                    recommended = mentioned[:1] if mentioned else (scored_cache[:1] if scored_cache else [])
                elif any(k in user_input for k in ["比較", "類似", "收藏", "詳情", "這一間", "那一間"]):
                    recommended = recommended
                else:
                    recommended = scored_cache[:10] if scored_cache else []
            return final_text, recommended

        tool_results = []
        for part in parts:
            if not (hasattr(part, 'function_call') and part.function_call.name):
                continue

            fn_name = part.function_call.name
            fn_args = dict(part.function_call.args)
            allowed = inspect.signature({
                "search_properties": tool_search_properties,
                "get_market_stats": tool_get_market_stats,
                "get_property_detail": tool_get_property_detail,
                "compare_properties": tool_compare_properties,
                "find_similar_properties": tool_find_similar_properties,
                "list_favorites": tool_list_favorites,
                "add_to_favorites": tool_add_to_favorites,
                "rank_districts": tool_rank_districts,
                "check_nearby_nuisances": tool_check_nearby_nuisances,
            }.get(fn_name, lambda **kwargs: None)).parameters
            fn_args = {k: v for k, v in fn_args.items() if k in allowed and v is not None}

            if fn_name == "search_properties":
                show_step("🔍", "搜尋房屋",
                    f"{fn_args.get('district','')} {fn_args.get('housetype','')} "
                    f"預算{fn_args.get('budget_max','')}萬 {fn_args.get('rooms','')}房 {fn_args.get('parking','')}")
                results = tool_search_properties(**fn_args)
                current_search_results = results
                st.session_state['_agent_search_cache'] = results
                show_step("✅", f"找到 {len(results)} 筆，開始計算 CP 值")

                has_extra = any([
                    float(fn_args.get('budget_max') or 0) > 0,
                    float(fn_args.get('budget_min') or 0) > 0,
                    int(fn_args.get('rooms') or 0) > 0,
                    float(fn_args.get('age_max') or 0) > 0,
                    float(fn_args.get('age_min') or 0) > 0,
                    float(fn_args.get('area_min') or 0) > 0,
                    int(fn_args.get('floor_min') or 0) > 0,
                    bool(fn_args.get('parking')),
                ])
                scored = tool_score_properties(results, use_pool=results if has_extra else None)
                st.session_state['_agent_scored_cache'] = scored
                recommended = scored[:10]
                show_step("📊", "CP 值計算完成")
                top_for_gemini = [_simplify_house(r, {"排名": i + 1}) for i, r in enumerate(scored[:10])]
                tool_results.append(_pack_tool(fn_name, top_for_gemini))

            elif fn_name == "get_market_stats":
                show_step("📈", "取得市場統計", f"{fn_args.get('district','')} {fn_args.get('housetype','')}")
                stats = tool_get_market_stats(**fn_args)
                show_step("✅", "市場數據取得完成")
                tool_results.append(_pack_tool(fn_name, stats))

            elif fn_name == "get_property_detail":
                show_step("🏠", "查詢房屋詳情", fn_args.get("title") or fn_args.get("property_id") or "")
                houses = _lookup_houses([fn_args.get("title", "")] if fn_args.get("title") else [], fn_args.get("property_id", ""))
                if houses:
                    recommended = houses[:1]
                detail = tool_get_property_detail(**fn_args)
                tool_results.append(_pack_tool(fn_name, detail))

            elif fn_name == "compare_properties":
                titles = list(fn_args.get("titles") or [])
                show_step("⚖️", "比較房屋", "、".join(titles[:4]))
                houses = _lookup_houses(titles)
                if houses:
                    recommended = houses[:4]
                tool_results.append(_pack_tool(fn_name, tool_compare_properties(titles)))

            elif fn_name == "find_similar_properties":
                show_step("🔁", "尋找類似物件", fn_args.get("title", ""))
                similar = tool_find_similar_properties(**fn_args)
                if isinstance(similar, list):
                    full = _lookup_houses([h.get("標題", "") for h in similar])
                    recommended = full or similar
                tool_results.append(_pack_tool(fn_name, similar))

            elif fn_name == "list_favorites":
                show_step("⭐", "讀取收藏清單")
                data = tool_list_favorites()
                fav_df = FavoritesManager.get_favorites_data()
                if fav_df is not None and not fav_df.empty:
                    recommended = fav_df.to_dict("records")
                tool_results.append(_pack_tool(fn_name, data))

            elif fn_name == "add_to_favorites":
                show_step("⭐", "加入收藏", fn_args.get("title", ""))
                result = tool_add_to_favorites(**fn_args)
                if result.get("ok"):
                    houses = _lookup_houses([fn_args.get("title", "")], fn_args.get("property_id", ""))
                    recommended = houses[:1]
                tool_results.append(_pack_tool(fn_name, result))

            elif fn_name == "rank_districts":
                show_step("🗺️", "比較各行政區行情", fn_args.get("housetype", ""))
                ranks = tool_rank_districts(**fn_args)
                tool_results.append(_pack_tool(fn_name, ranks))

            elif fn_name == "check_nearby_nuisances":
                show_step("⚠️", "查詢周邊嫌惡設施", fn_args.get("title", "上一間推薦"))
                payload, view, houses = tool_check_nearby_nuisances(**fn_args)
                if houses:
                    recommended = houses[:1]
                if view:
                    st.session_state["_agent_nuisance_result"] = view
                show_step("✅", "嫌惡設施查詢完成")
                tool_results.append(_pack_tool(fn_name, payload))

            else:
                tool_results.append(_pack_tool(fn_name, {"error": f"未知工具：{fn_name}"}))

        messages.append({"role": "model", "parts": parts})
        messages.append({"role": "user", "parts": tool_results})

    return "（已完成分析）", recommended


def _render_house_cards(houses, key_prefix, user_query=""):
    if not houses:
        return
    one_keywords = ["最推薦", "推薦一間", "推薦1間", "你最推薦", "最好的一間", "最好的房子", "哪一間最好"]
    show_limit = 1 if any(k in (user_query or "") for k in one_keywords) else 10
    st.markdown("#### 🏆 相關房屋")
    for j, house in enumerate(houses[:show_limit]):
        with st.container(border=True):
            cp = house.get("CP分數", 0) or 0
            try:
                cp = float(cp)
            except Exception:
                cp = 0
            color = "#1D9E75" if cp >= 70 else "#EF9F27" if cp >= 50 else "#888780"
            rank_medal = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"][j] if j < 5 else f"#{j+1}"
            img_url = get_property_image_url(house)
            property_id = normalize_property_id(house.get("編號", ""))

            col_img, col1, col2, col3 = st.columns([1.3, 3.2, 1, 1.3])
            with col_img:
                if img_url:
                    safe_url = html.escape(img_url, quote=True)
                    st.markdown(
                        f'<img src="{safe_url}" alt="" referrerpolicy="no-referrer" '
                        f'style="width:100%;height:92px;object-fit:cover;border-radius:8px;display:block;" />',
                        unsafe_allow_html=True,
                    )
            with col1:
                st.markdown(f"**{rank_medal} {house.get('標題', '')}**")
                st.caption(
                    f"📍 {house.get('行政區', '') or house.get('地址', '')} ｜ "
                    f"💰 {house.get('總價(萬)', '')} 萬 ｜ "
                    f"{house.get('格局', '')} ｜ "
                    f"屋齡 {house.get('屋齡', '')} ｜ "
                    f"{house.get('建坪', '')} 坪"
                    + (f" ｜ {house.get('車位', '')}" if house.get("車位") else "")
                )
            with col2:
                if cp:
                    st.markdown(
                        f"<div style='text-align:center;padding:8px'>"
                        f"<div style='font-size:11px;color:#aaa'>CP分數</div>"
                        f"<div style='font-size:22px;font-weight:bold;color:{color}'>{cp}</div>"
                        f"</div>",
                        unsafe_allow_html=True
                    )
            with col3:
                is_fav = property_id in st.session_state.get("favorites", [])
                if st.button(
                    "✅ 已收藏" if is_fav else "⭐ 收藏",
                    key=f"{key_prefix}_fav_{j}_{property_id}",
                    disabled=is_fav,
                    use_container_width=True,
                ):
                    all_df = _load_data()
                    if all_df is not None and property_id:
                        matched = all_df[all_df["編號"].map(normalize_property_id) == property_id]
                        if not matched.empty:
                            FavoritesManager.add_favorite(matched.iloc[0])
                            st.rerun()
                    elif house:
                        FavoritesManager.add_favorite(pd.Series(house))
                        st.rerun()
                if property_id:
                    st.link_button("詳情", f"https://www.sinyi.com.tw/buy/house/{property_id}?breadcrumb=list", use_container_width=True)
                if st.button("去分析", key=f"{key_prefix}_ana_{j}_{property_id}", use_container_width=True):
                    if property_id:
                        all_df = _load_data()
                        if all_df is not None:
                            matched = all_df[all_df["編號"].map(normalize_property_id) == property_id]
                            if not matched.empty:
                                FavoritesManager.add_favorite(matched.iloc[0])
                    elif house:
                        FavoritesManager.add_favorite(pd.Series(house))
                    st.session_state.current_page = "analysis"
                    st.rerun()


def _build_followups(user_query, houses):
    """依上一輪結果產生追問，而不是把收藏當成開場白。"""
    houses = houses or []
    title1 = str(houses[0].get("標題", "")).strip() if len(houses) >= 1 else ""
    title2 = str(houses[1].get("標題", "")).strip() if len(houses) >= 2 else ""
    district = str((houses[0].get("行政區") if houses else "") or "").strip()
    query = user_query or ""

    items = []

    def add(label, prompt):
        if prompt and prompt not in {p for _, p in items}:
            items.append((label, prompt))

    if title1:
        add("查周邊嫌惡設施", f"請查「{title1}」半徑500公尺內的嫌惡設施，並列出最近的類型與距離")
        add("第一名細節", f"請查「{title1}」的完整細節，包含車位、單價、樓層和屋齡")
        add("找類似更便宜的", f"找跟「{title1}」同區同類型、價格更便宜的類似物件")
    if title1 and title2:
        add("跟第二名比一比", f"比較「{title1}」和「{title2}」哪間比較划算")
    if district:
        add("這區行情", f"{district}目前的房價行情如何？")
    if "車位" not in query:
        add("加上車位條件", "同樣條件下只要有車位的")
    if houses and "屋齡" not in query:
        add("只要十年內", "把條件改成屋齡 10 年內再找一次")
    if not houses:
        add("改找推薦物件", "依照剛才的行情，推薦幾間 CP 值高的大樓")
        add("哪區比較親民", "台中哪幾個行政區大樓單價比較親民？")

    return items[:4]


def _render_followups(items, key_prefix):
    if not items:
        return
    st.caption("可以接著問")
    cols = st.columns(len(items))
    for i, (label, prompt) in enumerate(items):
        with cols[i]:
            if st.button(label, key=f"{key_prefix}_fu_{i}", use_container_width=True):
                st.session_state["_pending_input"] = prompt
                st.rerun()

def render_assistant_page():
    st.title("🤖 智能小幫手 — 房小智")
    st.caption("用對話找房、看行情、比較物件。收藏請直接點推薦卡片上的按鈕。")

    gemini_key = st.session_state.get("GEMINI_KEY", "")
    if not gemini_key:
        st.error("❌ 請先在側邊欄設定 Gemini API Key")
        return

    try:
        genai.configure(api_key=gemini_key)
        system_instruction = """你是台中市房產 AI 助手，名字叫「房小智」。

你可以使用這些工具：
- search_properties：找房子（會自動算 CP 值）。支援預算、房數、屋齡、建坪、樓層、車位。
- get_market_stats：某一區、某一類型的行情統計。
- get_property_detail：查某一間的完整細節（追問車位、樓層、單價時用）。
- compare_properties：比較兩間以上房屋。
- find_similar_properties：找類似替代物件。
- list_favorites：看使用者收藏。
- add_to_favorites：幫使用者收藏某間房子。
- rank_districts：比較各行政區哪裡相對便宜。
- check_nearby_nuisances：查單一房屋周邊嫌惡設施與最近距離。一次只查一間。

判斷原則：
- 找房子、推薦、CP 值 → search_properties
- 行情、均價、市場概況 → get_market_stats
- 問「這一間」細節 → get_property_detail，標題用上次推薦的完整標題
- 「這兩間比一比」→ compare_properties
- 「有沒有類似的」→ find_similar_properties
- 「我收藏了什麼」→ list_favorites
- 「幫我收藏」→ add_to_favorites
- 「哪一區比較便宜」→ rank_districts
- 「附近有沒有嫌惡設施」「這間安不安全」→ check_nearby_nuisances，標題用上次推薦第一名的完整標題
- 一般知識題可直接回答

回答規則：
- 用繁體中文，語氣親切
- 房屋標題必須完整引用，不可縮寫
- 搜尋時說明前 5～10 名：排名、標題、總價、格局、屋齡、車位、CP 分數、一句推薦理由
- 比較時清楚寫出誰總價低、誰單價低、誰較新
- 嫌惡設施用摘要說明：有幾類、最近是什麼、多遠；不要列座標
- 不要說請稍等，直接呼叫工具"""

        model = genai.GenerativeModel(
            'gemini-2.5-flash',
            system_instruction=system_instruction
        )

    except Exception as e:
        st.error(f"❌ Gemini 初始化錯誤：{e}")
        return

    if 'assistant_history' not in st.session_state:
        st.session_state.assistant_history = []

    if not st.session_state.assistant_history:
        st.markdown("#### 💡 快速提問")
        presets = [
            "幫我找西屯區 2000 萬內 3 房大樓",
            "北屯區 CP 值最高的大樓有哪些？",
            "西屯區目前的房價行情如何？",
            "找一間屋齡 10 年內、3 房、預算 1500 萬的房子",
            "南屯區華廈的市場概況",
            "推薦幾間適合小家庭的房子",
        ]
        preset_cols = st.columns(3)
        for i, preset in enumerate(presets):
            with preset_cols[i % 3]:
                if st.button(preset, key=f"preset_{i}", use_container_width=True):
                    st.session_state["_pending_input"] = preset
                    st.rerun()
        st.markdown("---")
    else:
        with st.expander("換一個新問題"):
            presets = [
                "幫我找西屯區 2000 萬內 3 房大樓",
                "北屯區 CP 值最高的大樓有哪些？",
                "西屯區目前的房價行情如何？",
                "找一間屋齡 10 年內、3 房、預算 1500 萬的房子",
                "南屯區華廈的市場概況",
                "推薦幾間適合小家庭的房子",
            ]
            for i, preset in enumerate(presets):
                if st.button(preset, key=f"preset_more_{i}", use_container_width=True):
                    st.session_state["_pending_input"] = preset
                    st.rerun()

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
                        _render_house_cards(msg['recommended'], key_prefix=f"hist_{i}", user_query=msg.get('user_query', ''))
                    if msg.get('nuisance'):
                        render_nuisance_result(msg['nuisance'])
                    if i == len(st.session_state.assistant_history) - 1:
                        _render_followups(msg.get("followups") or [], key_prefix=f"last_{i}")

    # ── 輸入框 ──
    col_input, col_clear = st.columns([5, 1])
    with col_clear:
        if st.button("🗑️ 清除對話", use_container_width=True):
            st.session_state.assistant_history = []
            st.session_state.pop('_agent_search_cache', None)
            st.session_state.pop('_agent_scored_cache', None)
            st.rerun()

    user_input = st.chat_input("例如：西屯區 2000 萬內 3 房大樓")

    pending = st.session_state.pop('_pending_input', None)
    final_input = pending or user_input

    if final_input:
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
            _render_house_cards(recommended, key_prefix="asst_new", user_query=final_input)
            nuisance = st.session_state.pop("_agent_nuisance_result", None)
            if nuisance:
                render_nuisance_result(nuisance)
            followups = _build_followups(final_input, recommended)

        st.session_state.assistant_history.append({
            'role': 'assistant',
            'text': final_reply,
            'recommended': recommended,
            'user_query': final_input,
            'followups': followups,
            'nuisance': nuisance,
        })

        st.rerun()
