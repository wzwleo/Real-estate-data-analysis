import os
import re
import json
import pandas as pd
import streamlit as st
import google.generativeai as genai
from utils import filter_properties  # 確認你已改寫 filter_properties() 支援 rooms/living_rooms/bathrooms/floor

# ----- Helper functions -----
def parse_layout(layout_str):
    """解析格局字串，如 '2房2廳1衛' → {'房間數': 2, '廳數': 2, '衛數': 1}"""
    if not isinstance(layout_str, str):
        return {"房間數": None, "廳數": None, "衛數": None}
    rooms = re.search(r'(\d+)房', layout_str)
    living = re.search(r'(\d+)廳', layout_str)
    baths = re.search(r'(\d+)衛', layout_str)
    return {
        "房間數": int(rooms.group(1)) if rooms else None,
        "廳數": int(living.group(1)) if living else None,
        "衛數": int(baths.group(1)) if baths else None
    }

def parse_floor(floor_str):
    """解析樓層欄位，如 '5/10'、'B1/5' → 取實際樓層數字"""
    if not isinstance(floor_str, str):
        return None
    m = re.match(r'(\d+)', floor_str)
    return int(m.group(1)) if m else None

def _extract_json_text(text: str):
    """嘗試抓出第一個 { ... } 或 [ ... ] 作為 JSON"""
    if not text:
        return None
    start = text.find('{')
    end = text.rfind('}')
    if start != -1 and end != -1 and end > start:
        return text[start:end+1]
    start = text.find('[')
    end = text.rfind(']')
    if start != -1 and end != -1 and end > start:
        return text[start:end+1]
    return None

def _normalize_value(val):
    """把單一欄位值轉成 int 或區間 dict"""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return int(val)
    s = str(val).strip()
    if s == '':
        return None
    m = re.match(r'^\s*(\d+)\s*[-~–]\s*(\d+)\s*$', s)
    if m:
        return {"min": int(m.group(1)), "max": int(m.group(2))}
    m = re.search(r'(\d+)\s*(以上|\+|>=)', s)
    if m:
        return {"min": int(m.group(1))}
    m = re.search(r'(以下|<=)\s*(\d+)', s)
    if m:
        return {"max": int(m.group(2))}
    m = re.match(r'^\s*(\d+)\s*$', s)
    if m:
        return int(m.group(1))
    if '低' in s:
        return {"min": 1, "max": 5}
    if '高' in s:
        return {"min": 6}
    m = re.search(r'(\d+)', s)
    if m:
        return int(m.group(1))
    return None

def _normalize_parsed_req(parsed: dict):
    """把 Gemini JSON 轉成 filter_properties 可用的 key"""
    if not parsed or not isinstance(parsed, dict):
        return {}
    out = {}
    keymap = {
        "房間數": "rooms", "rooms": "rooms", "房間": "rooms", "臥室": "rooms",
        "廳數": "living_rooms", "廳": "living_rooms", "living_rooms": "living_rooms",
        "衛數": "bathrooms", "衛": "bathrooms", "bathrooms": "bathrooms",
        "樓層": "floor", "floor": "floor"
    }
    for k, v in parsed.items():
        if not k:
            continue
        target = keymap.get(k.strip()) or keymap.get(k.strip().lower())
        if target:
            normalized = _normalize_value(v)
            if normalized is not None:
                out[target] = normalized
    return out

# ----- 主函式 -----
def handle_search_submit(selected_label, options, housetype_change, budget_min, budget_max,
                         age_min, age_max, area_min, area_max, car_grip, Special_Requests):
    valid_input = True
    if budget_min > budget_max and budget_max > 0:
        st.error("❌ 請修正預算範圍設定")
        valid_input = False
    if age_min > age_max:
        st.error("❌ 請修正屋齡範圍設定")
        valid_input = False
    if area_min > area_max:
        st.error("❌ 請修正建坪範圍設定")
        valid_input = False
    if not valid_input:
        return False

    st.session_state.current_search_page = 1
    file_path = os.path.join("./Data", options[selected_label])

    try:
        df = pd.read_csv(file_path)

        # ----- 解析格局與樓層 -----
        df[['房間數','廳數','衛數']] = df['格局'].apply(lambda x: pd.Series(parse_layout(x)))
        df['樓層'] = df['樓層'].apply(parse_floor)

        # ----- 基本篩選條件 -----
        filters = {
            'housetype': housetype_change,
            'budget_min': budget_min,
            'budget_max': budget_max,
            'age_min': age_min,
            'age_max': age_max,
            'area_min': area_min,
            'area_max': area_max,
            'car_grip': car_grip
        }

        # ----- Gemini AI 特殊要求 -----
        parsed_req = {}
        gemini_key = st.session_state.get("GEMINI_KEY", "")
        if Special_Requests.strip() and gemini_key:
            try:
                genai.configure(api_key=gemini_key)
                model = genai.GenerativeModel("gemini-2.0-flash")
                prompt = f"""
                請將下列房產需求解析為純 JSON：
                \"\"\"{Special_Requests}\"\"\"
                JSON 欄位包含：房間數、廳數、衛數、樓層
                範例：
                {{
                  "房間數": 2,
                  "廳數": 1,
                  "衛數": 1,
                  "樓層": {{"min": 1, "max": 5}}
                }}
                注意：回傳必須是合法 JSON，不能有多餘文字。
                """
                response = model.generate_content(prompt)
                resp_text = (response.text or "").strip()

                # 顯示 debug
                with st.expander("🔎 Gemini 回傳（debug）", expanded=False):
                    st.code(resp_text)

                parsed_obj = None
                try:
                    parsed_obj = json.loads(resp_text)
                except Exception:
                    json_text = _extract_json_text(resp_text)
                    if json_text:
                        try:
                            parsed_obj = json.loads(json_text.replace('：', ':').replace('，', ','))
                        except Exception:
                            parsed_obj = None
                parsed_req = _normalize_parsed_req(parsed_obj)
            except Exception as e:
                st.error(f"❌ Gemini 解析特殊要求失敗: {e}")

        # ----- 套用到篩選條件 -----
        for k in ['rooms','living_rooms','bathrooms','floor']:
            if parsed_req.get(k) is not None:
                filters[k] = parsed_req[k]

        # ----- 執行篩選 -----
        filtered_df = filter_properties(df, filters)
        st.session_state.filtered_df = filtered_df
        st.session_state.search_params = {
            'city': selected_label,
            'housetype': housetype_change,
            'budget_range': f"{budget_min}-{budget_max}萬" if budget_max < 1000000 else f"{budget_min}萬以上",
            'age_range': f"{age_min}-{age_max}年" if age_max < 100 else f"{age_min}年以上",
            'area_range': f"{area_min}-{area_max}坪" if area_max < 1000 else f"{area_min}坪以上",
            'car_grip': car_grip,
            'original_count': len(df),
            'filtered_count': len(filtered_df)
        }

        if len(filtered_df) == 0:
            st.warning("😅 沒有找到符合條件的房產，請調整篩選條件後重新搜尋")
        else:
            st.success(f"✅ 從 {len(df)} 筆資料中篩選出 {len(filtered_df)} 筆符合條件的房產")
        return True

    except FileNotFoundError:
        st.error(f"❌ 找不到檔案: {file_path}")
    except Exception as e:
        st.error(f"❌ 讀取 CSV 發生錯誤: {e}")
    return False
