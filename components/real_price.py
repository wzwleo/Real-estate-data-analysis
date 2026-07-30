import io
import math
import re
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import streamlit as st


SUPPORTED_REAL_PRICE_CITY = "臺中市"

REAL_PRICE_DATA_DIR = Path(__file__).resolve().parents[1] / "real_price"

CITY_FOLDER_MAP = {
    "臺中市": "taichung",
    "台中市": "taichung",
}

# Backward compatible fallback: still supports one merged CSV if present.
CITY_FILE_MAP = {
    "臺中市": "taichung_real_price.csv",
    "台中市": "taichung_real_price.csv",
}


CITY_FILE_CODES = {
    "臺北市": "a", "台北市": "a",
    "臺中市": "b", "台中市": "b",
    "基隆市": "c",
    "臺南市": "d", "台南市": "d",
    "高雄市": "e",
    "新北市": "f",
    "宜蘭縣": "g",
    "桃園市": "h",
    "嘉義市": "i",
    "新竹縣": "j",
    "苗栗縣": "k",
    "南投縣": "m",
    "彰化縣": "n",
    "新竹市": "o",
    "雲林縣": "p",
    "嘉義縣": "q",
    "屏東縣": "t",
    "花蓮縣": "u",
    "臺東縣": "v", "台東縣": "v",
    "金門縣": "w",
    "澎湖縣": "x",
    "連江縣": "z",
}

CITY_ALIASES = {
    "台北市": "臺北市",
    "台中市": "臺中市",
    "台南市": "臺南市",
    "台東縣": "臺東縣",
}

CITY_NAMES = sorted(set(CITY_FILE_CODES.keys()) | set(CITY_ALIASES.keys()), key=len, reverse=True)



def normalize_city_name(city):
    if not city:
        return ""
    city = str(city).strip()
    return CITY_ALIASES.get(city, city)


def infer_city_from_address(address):
    text = "" if address is None else str(address)
    for city in CITY_NAMES:
        if city and city in text:
            return normalize_city_name(city)
    return ""




def _parse_number(value):
    if value is None:
        return math.nan
    if isinstance(value, (int, float)) and not pd.isna(value):
        return float(value)
    text = str(value).strip().replace(",", "")
    if not text:
        return math.nan
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    return float(match.group(0)) if match else math.nan


def _parse_tw_date(value):
    if value is None or pd.isna(value):
        return pd.NaT
    text = str(value).strip().replace("/", "").replace("-", "")
    if not text:
        return pd.NaT
    digits = re.sub(r"\D", "", text)
    try:
        if len(digits) == 7:
            year = int(digits[:3]) + 1911
            month = int(digits[3:5])
            day = int(digits[5:7])
            return pd.Timestamp(year=year, month=month, day=day)
        if len(digits) == 8:
            year = int(digits[:4])
            month = int(digits[4:6])
            day = int(digits[6:8])
            return pd.Timestamp(year=year, month=month, day=day)
    except Exception:
        return pd.NaT
    return pd.NaT


def _pick_column(df, candidates):
    for col in candidates:
        if col in df.columns:
            return col
    return None


def _decode_csv_text(data):
    for enc in ("utf-8-sig", "utf-8", "cp950", "big5"):
        try:
            return data.decode(enc), enc
        except Exception:
            continue
    return data.decode("utf-8", errors="ignore"), "utf-8-ignore"


def _find_real_price_header_line(lines):
    required_tokens = ["交易年月日", "總價", "建物"]
    for idx, line in enumerate(lines):
        if all(token in line for token in required_tokens):
            return idx
    for idx, line in enumerate(lines):
        if "鄉鎮市區" in line and "交易" in line:
            return idx
    return None


def _read_csv_bytes(data):
    text, enc = _decode_csv_text(data)
    lines = text.splitlines()
    header_idx = _find_real_price_header_line(lines)
    if header_idx is None:
        preview = "\n".join(lines[:5])[:500]
        raise ValueError(f"找不到實價登錄 CSV 表頭，可能下載到非 CSV 內容。前段內容：{preview}")

    csv_text = "\n".join(lines[header_idx:])
    read_kwargs = {
        "dtype": str,
        "engine": "python",
        "on_bad_lines": "skip",
    }
    try:
        return pd.read_csv(io.StringIO(csv_text), **read_kwargs)
    except TypeError:
        return pd.read_csv(io.StringIO(csv_text), dtype=str, engine="python", error_bad_lines=False)


def _prepare_real_price_df(df, city=""):
    if df is None or df.empty:
        return pd.DataFrame()

    df = df.copy()
    date_col = _pick_column(df, ["交易年月日", "交易日期"])
    district_col = _pick_column(df, ["鄉鎮市區", "行政區"])
    building_type_col = _pick_column(df, ["建物型態", "建物類型"])
    area_col = _pick_column(df, ["建物移轉總面積平方公尺", "建物移轉總面積", "建坪"])
    price_col = _pick_column(df, ["總價元", "總價(元)", "總價"])
    age_col = _pick_column(df, ["屋齡", "建物現況格局-屋齡"])
    address_col = _pick_column(df, ["土地位置建物門牌", "地址"])

    out = pd.DataFrame()
    out["交易日期"] = df[date_col].apply(_parse_tw_date) if date_col else pd.NaT
    out["行政區"] = df[district_col].astype(str).str.strip() if district_col else ""
    out["建物型態"] = df[building_type_col].astype(str).str.strip() if building_type_col else ""
    area_m2 = df[area_col].apply(_parse_number) if area_col else math.nan
    out["建坪"] = pd.to_numeric(area_m2, errors="coerce") / 3.305785
    total_yuan = df[price_col].apply(_parse_number) if price_col else math.nan
    out["總價(萬)"] = pd.to_numeric(total_yuan, errors="coerce") / 10000
    out["屋齡"] = df[age_col].apply(_parse_number) if age_col else math.nan
    out["地址"] = df[address_col].astype(str).str.strip() if address_col else ""
    out["城市"] = normalize_city_name(city)
    out["單價(萬/坪)"] = out["總價(萬)"] / out["建坪"]

    out = out.dropna(subset=["交易日期", "建坪", "總價(萬)", "單價(萬/坪)"])
    out = out[(out["建坪"] > 0) & (out["總價(萬)"] > 0)]
    return out.reset_index(drop=True)


def _read_manual_real_price_csv(file_path):
    """Read manually committed real price CSV from real_price."""
    file_path = Path(file_path)
    try:
        return _read_csv_bytes(file_path.read_bytes())
    except Exception:
        pass

    for enc in ("utf-8-sig", "utf-8", "cp950", "big5"):
        try:
            return pd.read_csv(file_path, encoding=enc, dtype=str, engine="python", on_bad_lines="skip")
        except UnicodeDecodeError:
            continue
        except TypeError:
            return pd.read_csv(file_path, encoding=enc, dtype=str, engine="python", error_bad_lines=False)
    return pd.read_csv(file_path, dtype=str, engine="python", on_bad_lines="skip")


def _normalize_manual_real_price_df(df, city):
    """Normalize either prepared CSV columns or raw MOI CSV columns."""
    prepared_columns = {"交易日期", "行政區", "建物型態", "建坪", "總價(萬)", "單價(萬/坪)"}
    if df is None or df.empty:
        return pd.DataFrame()
    if prepared_columns.issubset(set(df.columns)):
        df = df.copy()
        df["交易日期"] = pd.to_datetime(df["交易日期"], errors="coerce")
        for col in ["建坪", "屋齡", "總價(萬)", "單價(萬/坪)"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        return df.dropna(subset=["交易日期", "建坪", "總價(萬)", "單價(萬/坪)"]).reset_index(drop=True)
    return _prepare_real_price_df(df, city)


def _load_manual_real_price_file(file_path, city):
    """Load and normalize one manually downloaded period CSV."""
    return _normalize_manual_real_price_df(_read_manual_real_price_csv(file_path), city)


def load_cached_real_price_data(city):
    """Load manually provided real price CSV files for a city from the GitHub project."""
    city = normalize_city_name(city)
    folder_name = CITY_FOLDER_MAP.get(city)
    if folder_name:
        folder_path = REAL_PRICE_DATA_DIR / folder_name
        if folder_path.exists():
            frames = []
            for file_path in sorted(folder_path.glob("*.csv")):
                try:
                    frame = _load_manual_real_price_file(file_path, city)
                    if not frame.empty:
                        frame["資料檔案"] = file_path.name
                        frames.append(frame)
                except Exception as e:
                    st.warning(f"實價登錄 CSV 讀取失敗：{file_path.name}，已略過。原因：{e}")
            if frames:
                return pd.concat(frames, ignore_index=True)

    filename = CITY_FILE_MAP.get(city)
    if not filename:
        return pd.DataFrame()

    file_path = REAL_PRICE_DATA_DIR / filename
    if not file_path.exists():
        return pd.DataFrame()

    return _load_manual_real_price_file(file_path, city)


def _matches_building_type(series, target_type):
    target_type = "" if target_type is None else str(target_type).strip()
    if not target_type:
        return pd.Series(True, index=series.index)
    token = target_type.split("(")[0].split("/")[0].strip()
    if not token:
        return pd.Series(True, index=series.index)
    return series.astype(str).str.contains(re.escape(token), na=False)


def filter_nearby_transactions(df, target_house):
    """Filter transactions by recent 5 years and similar property conditions."""
    if df is None or df.empty:
        return pd.DataFrame()

    target = target_house or {}
    district = str(target.get("行政區", "")).strip()
    building_type = str(target.get("類型", target.get("建物型態", ""))).strip()
    area = _parse_number(target.get("建坪"))
    age = _parse_number(target.get("屋齡"))

    work = df.copy()
    work["交易日期"] = pd.to_datetime(work["交易日期"], errors="coerce")
    cutoff = pd.Timestamp(datetime.now() - timedelta(days=365 * 5))
    work = work[work["交易日期"] >= cutoff]
    if work.empty:
        return work

    base = work.copy()
    steps = []
    mask = pd.Series(True, index=base.index)
    if district:
        mask &= base["行政區"].astype(str).str.contains(re.escape(district), na=False)
    if building_type:
        mask &= _matches_building_type(base["建物型態"], building_type)
    if not math.isnan(area) and area > 0:
        mask &= base["建坪"].between(area * 0.7, area * 1.3)
    if not math.isnan(age):
        mask &= base["屋齡"].fillna(age).between(max(age - 10, 0), age + 10)
    steps.append(mask)

    mask = pd.Series(True, index=base.index)
    if district:
        mask &= base["行政區"].astype(str).str.contains(re.escape(district), na=False)
    if building_type:
        mask &= _matches_building_type(base["建物型態"], building_type)
    if not math.isnan(area) and area > 0:
        mask &= base["建坪"].between(area * 0.7, area * 1.3)
    steps.append(mask)

    mask = pd.Series(True, index=base.index)
    if district:
        mask &= base["行政區"].astype(str).str.contains(re.escape(district), na=False)
    if building_type:
        mask &= _matches_building_type(base["建物型態"], building_type)
    if not math.isnan(area) and area > 0:
        mask &= base["建坪"].between(area * 0.5, area * 1.5)
    steps.append(mask)

    mask = pd.Series(True, index=base.index)
    if district:
        mask &= base["行政區"].astype(str).str.contains(re.escape(district), na=False)
    if building_type:
        mask &= _matches_building_type(base["建物型態"], building_type)
    steps.append(mask)

    mask = pd.Series(True, index=base.index)
    if district:
        mask &= base["行政區"].astype(str).str.contains(re.escape(district), na=False)
    steps.append(mask)

    steps.append(pd.Series(True, index=base.index))

    selected = pd.DataFrame()
    for mask in steps:
        selected = base[mask].copy()
        if len(selected) >= 10:
            break
    selected = selected.sort_values("交易日期", ascending=False).reset_index(drop=True)
    selected.attrs["recent_city_transactions"] = base.reset_index(drop=True)
    selected.attrs["filter_target"] = target
    return selected



def _safe_mean(df, column):
    if df is None or df.empty or column not in df.columns:
        return math.nan
    value = pd.to_numeric(df[column], errors="coerce").dropna()
    return float(value.mean()) if not value.empty else math.nan


def _period_avg(tx, days):
    if tx is None or tx.empty:
        return math.nan
    cutoff = pd.Timestamp(datetime.now() - timedelta(days=days))
    return _safe_mean(tx[tx["\u4ea4\u6613\u65e5\u671f"] >= cutoff], "\u55ae\u50f9(\u842c/\u576a)")


def _fmt_metric(value, suffix=""):
    try:
        if value is None or math.isnan(float(value)):
            return "\u7121\u8cc7\u6599"
        return f"{float(value):.2f}{suffix}"
    except Exception:
        return "\u7121\u8cc7\u6599"


def _fmt_money_range(low, high):
    try:
        if low is None or high is None or math.isnan(float(low)) or math.isnan(float(high)):
            return "\u7121\u8cc7\u6599"
        return f"{float(low):.0f} ~ {float(high):.0f} \u842c"
    except Exception:
        return "\u7121\u8cc7\u6599"


def _price_band_label(value, bins):
    try:
        value = float(value)
    except Exception:
        return "\u7121\u8cc7\u6599"
    if not bins:
        return "\u7121\u8cc7\u6599"
    for i in range(len(bins) - 1):
        left, right = bins[i], bins[i + 1]
        if value >= left and (value < right or i == len(bins) - 2):
            return f"{left:.0f}-{right:.0f} \u842c/\u576a"
    return "\u7121\u8cc7\u6599"


def _build_similarity_reason(row, target):
    reasons = []
    score = 0
    district = str(target.get("\u884c\u653f\u5340", "")).strip()
    building_type = str(target.get("\u985e\u578b", target.get("\u5efa\u7269\u578b\u614b", ""))).strip()
    area = _parse_number(target.get("\u5efa\u576a"))
    age = _parse_number(target.get("\u5c4b\u9f61"))

    if district and district in str(row.get("\u884c\u653f\u5340", "")):
        score += 30
        reasons.append("\u540c\u884c\u653f\u5340")
    if building_type and _matches_building_type(pd.Series([row.get("\u5efa\u7269\u578b\u614b", "")]), building_type).iloc[0]:
        score += 25
        reasons.append("\u540c\u5efa\u7269\u578b\u614b")
    row_area = _parse_number(row.get("\u5efa\u576a"))
    if not math.isnan(area) and area > 0 and not math.isnan(row_area):
        diff_pct = abs(row_area - area) / area * 100
        if diff_pct <= 15:
            score += 25
            reasons.append(f"\u5efa\u576a\u5dee {diff_pct:.0f}%")
        elif diff_pct <= 30:
            score += 15
            reasons.append(f"\u5efa\u576a\u5dee {diff_pct:.0f}%")
    row_age = _parse_number(row.get("\u5c4b\u9f61"))
    if not math.isnan(age) and not math.isnan(row_age):
        age_diff = abs(row_age - age)
        if age_diff <= 5:
            score += 15
            reasons.append(f"\u5c4b\u9f61\u5dee {age_diff:.0f} \u5e74")
        elif age_diff <= 10:
            score += 8
            reasons.append(f"\u5c4b\u9f61\u5dee {age_diff:.0f} \u5e74")
    tx_date = row.get("\u4ea4\u6613\u65e5\u671f")
    if pd.notna(tx_date):
        months = abs((pd.Timestamp(datetime.now()) - pd.Timestamp(tx_date)).days) / 30
        if months <= 12:
            score += 5
            reasons.append("\u4e00\u5e74\u5167\u6210\u4ea4")
    label = "\u9ad8" if score >= 80 else "\u4e2d" if score >= 55 else "\u4f4e"
    return label, "\u3001".join(reasons) if reasons else "\u689d\u4ef6\u76f8\u4f3c\u5ea6\u6709\u9650"


def _build_price_distribution(tx, target_unit_price):
    col = "\u55ae\u50f9(\u842c/\u576a)"
    if tx is None or tx.empty or col not in tx.columns:
        return pd.DataFrame()
    prices = pd.to_numeric(tx[col], errors="coerce").dropna()
    if prices.empty:
        return pd.DataFrame()
    low = max(0, math.floor(prices.quantile(0.05) / 5) * 5)
    high = math.ceil(prices.quantile(0.95) / 5) * 5
    if high <= low:
        high = low + 5
    bins = list(range(int(low), int(high) + 6, 5))
    rows = []
    for i in range(len(bins) - 1):
        left, right = bins[i], bins[i + 1]
        mask = (prices >= left) & ((prices < right) if i < len(bins) - 2 else (prices <= right))
        rows.append({"\u55ae\u50f9\u5340\u9593": f"{left}-{right} \u842c/\u576a", "\u6210\u4ea4\u7b46\u6578": int(mask.sum())})
    dist = pd.DataFrame(rows)
    dist.attrs["target_band"] = _price_band_label(target_unit_price, bins)
    return dist


def calculate_price_metrics(transactions, target_house):
    """Calculate price metrics for target house and comparable transactions."""
    target = target_house or {}
    area = _parse_number(target.get("\u5efa\u576a"))
    price = _parse_number(target.get("\u7e3d\u50f9(\u842c)"))
    target_unit_price = price / area if area and not math.isnan(area) and not math.isnan(price) else math.nan

    tx = transactions.copy() if transactions is not None else pd.DataFrame()
    city_tx = transactions.attrs.get("recent_city_transactions", pd.DataFrame()).copy() if transactions is not None else pd.DataFrame()
    metrics = {
        "target_unit_price": target_unit_price,
        "nearby_one_year_avg": math.nan,
        "nearby_three_year_avg": math.nan,
        "nearby_five_year_avg": math.nan,
        "price_gap_pct": math.nan,
        "reasonable_unit_price_low": math.nan,
        "reasonable_unit_price_high": math.nan,
        "reasonable_total_low": math.nan,
        "reasonable_total_high": math.nan,
        "suggested_offer_low": math.nan,
        "suggested_offer_high": math.nan,
        "negotiation_space_pct": math.nan,
        "yearly_avg_unit_price": pd.DataFrame(columns=["\u5e74\u4efd", "\u5e73\u5747\u55ae\u50f9(\u842c/\u576a)"]),
        "yearly_volume": pd.DataFrame(columns=["\u5e74\u4efd", "\u6210\u4ea4\u91cf"]),
        "price_distribution": pd.DataFrame(),
        "district_ranking": pd.DataFrame(),
        "district_rank_text": "\u7121\u8cc7\u6599",
        "market_heat_label": "\u7121\u8cc7\u6599",
        "market_heat_detail": "\u7121\u8cc7\u6599",
        "one_year_volume": 0,
        "previous_year_volume": 0,
        "volume_change_pct": math.nan,
        "five_year_change_pct": math.nan,
        "similar_cases": pd.DataFrame(),
        "transaction_count": 0,
        "message": "",
    }

    if tx.empty:
        metrics["message"] = "\u8cc7\u6599\u4e0d\u8db3\uff0c\u5efa\u8b70\u653e\u5bec\u689d\u4ef6"
        return metrics

    date_col = "\u4ea4\u6613\u65e5\u671f"
    unit_col = "\u55ae\u50f9(\u842c/\u576a)"
    tx[date_col] = pd.to_datetime(tx[date_col], errors="coerce")
    tx = tx.dropna(subset=[date_col, unit_col])
    tx[unit_col] = pd.to_numeric(tx[unit_col], errors="coerce")
    tx = tx.dropna(subset=[unit_col])
    metrics["transaction_count"] = int(len(tx))
    if len(tx) < 10:
        metrics["message"] = "\u8cc7\u6599\u4e0d\u8db3\uff0c\u5efa\u8b70\u653e\u5bec\u689d\u4ef6"

    now = pd.Timestamp(datetime.now())
    one_year_cutoff = now - timedelta(days=365)
    prev_year_cutoff = now - timedelta(days=365 * 2)
    recent = tx[tx[date_col] >= one_year_cutoff]
    previous = tx[(tx[date_col] >= prev_year_cutoff) & (tx[date_col] < one_year_cutoff)]

    metrics["nearby_one_year_avg"] = _period_avg(tx, 365)
    metrics["nearby_three_year_avg"] = _period_avg(tx, 365 * 3)
    metrics["nearby_five_year_avg"] = _period_avg(tx, 365 * 5)
    if math.isnan(metrics["nearby_one_year_avg"]):
        metrics["nearby_one_year_avg"] = metrics["nearby_five_year_avg"]

    if not math.isnan(target_unit_price) and not math.isnan(metrics["nearby_one_year_avg"]) and metrics["nearby_one_year_avg"]:
        metrics["price_gap_pct"] = (target_unit_price - metrics["nearby_one_year_avg"]) / metrics["nearby_one_year_avg"] * 100

    base_avg = metrics["nearby_one_year_avg"] if not math.isnan(metrics["nearby_one_year_avg"]) else metrics["nearby_five_year_avg"]
    if not math.isnan(base_avg):
        metrics["reasonable_unit_price_low"] = base_avg * 0.95
        metrics["reasonable_unit_price_high"] = base_avg * 1.05
        if not math.isnan(area) and area > 0:
            metrics["reasonable_total_low"] = metrics["reasonable_unit_price_low"] * area
            metrics["reasonable_total_high"] = metrics["reasonable_unit_price_high"] * area
            metrics["suggested_offer_low"] = base_avg * 0.92 * area
            metrics["suggested_offer_high"] = base_avg * 0.98 * area
            if not math.isnan(price) and price > 0:
                gap_total = max(price - metrics["reasonable_total_high"], 0)
                metrics["negotiation_space_pct"] = gap_total / price * 100

    tx["\u5e74\u4efd"] = tx[date_col].dt.year
    yearly = tx.groupby("\u5e74\u4efd", as_index=False)[unit_col].mean().sort_values("\u5e74\u4efd")
    volume = tx.groupby("\u5e74\u4efd", as_index=False).size().rename(columns={"size": "\u6210\u4ea4\u91cf"}).sort_values("\u5e74\u4efd")
    metrics["yearly_avg_unit_price"] = yearly.rename(columns={unit_col: "\u5e73\u5747\u55ae\u50f9(\u842c/\u576a)"})
    metrics["yearly_volume"] = volume

    if len(yearly) >= 2 and yearly.iloc[0][unit_col]:
        first = yearly.iloc[0][unit_col]
        last = yearly.iloc[-1][unit_col]
        metrics["five_year_change_pct"] = (last - first) / first * 100

    metrics["one_year_volume"] = int(len(recent))
    metrics["previous_year_volume"] = int(len(previous))
    if metrics["previous_year_volume"] > 0:
        metrics["volume_change_pct"] = (metrics["one_year_volume"] - metrics["previous_year_volume"]) / metrics["previous_year_volume"] * 100
    if metrics["one_year_volume"] >= 80:
        metrics["market_heat_label"] = "\u9ad8"
    elif metrics["one_year_volume"] >= 25:
        metrics["market_heat_label"] = "\u4e2d"
    else:
        metrics["market_heat_label"] = "\u4f4e"
    change_text = _fmt_metric(metrics["volume_change_pct"], "%") if not math.isnan(metrics["volume_change_pct"]) else "\u7121\u53bb\u5e74\u540c\u671f\u8cc7\u6599"
    metrics["market_heat_detail"] = f"\u8fd1\u4e00\u5e74 {metrics['one_year_volume']} \u7b46\uff0c\u524d\u4e00\u5e74 {metrics['previous_year_volume']} \u7b46\uff0c\u91cf\u8b8a\u5316 {change_text}"

    metrics["price_distribution"] = _build_price_distribution(tx, target_unit_price)

    target_district = str(target.get("\u884c\u653f\u5340", "")).strip()
    if city_tx is not None and not city_tx.empty:
        city_tx[date_col] = pd.to_datetime(city_tx[date_col], errors="coerce")
        city_tx[unit_col] = pd.to_numeric(city_tx[unit_col], errors="coerce")
        rank_base = city_tx[(city_tx[date_col] >= one_year_cutoff)].dropna(subset=["\u884c\u653f\u5340", unit_col])
        if rank_base.empty:
            rank_base = city_tx.dropna(subset=["\u884c\u653f\u5340", unit_col])
        if not rank_base.empty:
            district_rank = rank_base.groupby("\u884c\u653f\u5340", as_index=False).agg({unit_col: "mean"})
            counts = rank_base.groupby("\u884c\u653f\u5340").size().reset_index(name="\u6210\u4ea4\u91cf")
            district_rank = district_rank.merge(counts, on="\u884c\u653f\u5340", how="left")
            district_rank = district_rank.rename(columns={unit_col: "\u5e73\u5747\u55ae\u50f9"}).sort_values("\u5e73\u5747\u55ae\u50f9", ascending=False).reset_index(drop=True)
            district_rank["\u6392\u540d"] = district_rank.index + 1
            metrics["district_ranking"] = district_rank[["\u6392\u540d", "\u884c\u653f\u5340", "\u5e73\u5747\u55ae\u50f9", "\u6210\u4ea4\u91cf"]].copy()
            if target_district and target_district in district_rank["\u884c\u653f\u5340"].astype(str).tolist():
                row = district_rank[district_rank["\u884c\u653f\u5340"].astype(str) == target_district].iloc[0]
                metrics["district_rank_text"] = f"{target_district} \u8fd1\u4e00\u5e74\u5747\u50f9 {row['\u5e73\u5747\u55ae\u50f9']:.2f} \u842c/\u576a\uff0c\u53f0\u4e2d\u5e02\u6392\u540d\u7b2c {int(row['\u6392\u540d'])}/{len(district_rank)}"

    display_cols = [date_col, "\u884c\u653f\u5340", "\u5efa\u7269\u578b\u614b", "\u5730\u5740", "\u5efa\u576a", "\u5c4b\u9f61", "\u7e3d\u50f9(\u842c)", unit_col]
    available = [c for c in display_cols if c in tx.columns]
    cases = tx.sort_values(date_col, ascending=False).head(10)[available].copy()
    if not cases.empty:
        labels = []
        reasons = []
        for _, row in cases.iterrows():
            label, reason = _build_similarity_reason(row, target)
            labels.append(label)
            reasons.append(reason)
        cases["\u53ef\u6bd4\u6027"] = labels
        cases["\u76f8\u4f3c\u539f\u56e0"] = reasons
    if date_col in cases.columns:
        cases[date_col] = cases[date_col].dt.strftime("%Y-%m-%d")
    for col in ["\u5efa\u576a", "\u5c4b\u9f61", "\u7e3d\u50f9(\u842c)", unit_col]:
        if col in cases.columns:
            cases[col] = pd.to_numeric(cases[col], errors="coerce").round(2)
    metrics["similar_cases"] = cases
    return metrics




def _build_real_price_ai_explanation(metrics):
    """Build a concise local explanation from real price metrics."""
    def _num(value):
        try:
            n = float(value)
            return n if not math.isnan(n) else math.nan
        except (TypeError, ValueError):
            return math.nan

    if not metrics:
        return "\u8cc7\u6599\u4e0d\u8db3\uff0c\u66ab\u6642\u7121\u6cd5\u5f62\u6210\u50f9\u683c\u5224\u8b80\u3002"

    lines = []
    target = metrics.get("target_unit_price")
    one_year = metrics.get("nearby_one_year_avg")
    gap = metrics.get("price_gap_pct")
    five_change = metrics.get("five_year_change_pct")
    heat = metrics.get("market_heat_label", "\u7121\u8cc7\u6599")
    heat_detail = metrics.get("market_heat_detail", "")
    rank_text = metrics.get("district_rank_text", "")

    if not math.isnan(_num(target)) and not math.isnan(_num(one_year)):
        gap_value = _num(gap)
        if not math.isnan(gap_value):
            if gap_value > 10:
                lines.append(f"\u672c\u6848\u55ae\u50f9 {_fmt_metric(target, ' \u842c/\u576a')}\uff0c\u6bd4\u5468\u908a\u8fd1\u4e00\u5e74\u5747\u50f9 {_fmt_metric(one_year, ' \u842c/\u576a')} \u9ad8\u7d04 {_fmt_metric(gap, '%')}\uff0c\u50f9\u683c\u504f\u9ad8\uff0c\u5efa\u8b70\u628a\u5be6\u50f9\u6848\u4f8b\u3001\u6a13\u5c64\u3001\u5c4b\u6cc1\u8207\u8eca\u4f4d\u689d\u4ef6\u62ff\u4f86\u8b70\u50f9\u3002")
            elif gap_value < -10:
                lines.append(f"\u672c\u6848\u55ae\u50f9 {_fmt_metric(target, ' \u842c/\u576a')}\uff0c\u4f4e\u65bc\u5468\u908a\u8fd1\u4e00\u5e74\u5747\u50f9\u7d04 {_fmt_metric(abs(gap_value), '%')}\uff0c\u50f9\u683c\u5177\u5438\u5f15\u529b\uff0c\u4f46\u4ecd\u8981\u78ba\u8a8d\u662f\u5426\u6709\u5c4b\u6cc1\u3001\u6a13\u5c64\u6216\u7522\u6b0a\u689d\u4ef6\u5dee\u7570\u3002")
            else:
                lines.append(f"\u672c\u6848\u55ae\u50f9 {_fmt_metric(target, ' \u842c/\u576a')} \u8207\u5468\u908a\u8fd1\u4e00\u5e74\u5747\u50f9 {_fmt_metric(one_year, ' \u842c/\u576a')} \u63a5\u8fd1\uff0c\u521d\u6b65\u770b\u5c6c\u65bc\u884c\u60c5\u9644\u8fd1\u3002")
    else:
        lines.append("\u672c\u6848\u55ae\u50f9\u6216\u8fd1\u4e00\u5e74\u5747\u50f9\u4e0d\u8db3\uff0c\u50f9\u683c\u5408\u7406\u6027\u9700\u8981\u642d\u914d\u76f8\u4f3c\u6210\u4ea4\u6848\u4f8b\u4eba\u5de5\u6bd4\u5c0d\u3002")

    money_range = _fmt_money_range(metrics.get("reasonable_total_low"), metrics.get("reasonable_total_high"))
    offer_range = _fmt_money_range(metrics.get("suggested_offer_low"), metrics.get("suggested_offer_high"))
    negotiation = _fmt_metric(metrics.get("negotiation_space_pct"), "%")
    lines.append(f"\u4ee5\u76ee\u524d\u7be9\u51fa\u7684\u8fd1\u4f3c\u4ea4\u6613\u63a8\u4f30\uff0c\u5408\u7406\u7e3d\u50f9\u5340\u9593\u7d04 {money_range}\uff0c\u5efa\u8b70\u51fa\u50f9\u5340\u9593\u7d04 {offer_range}\uff0c\u4f30\u8a08\u8b70\u50f9\u7a7a\u9593\u7d04 {negotiation}\u3002")

    five_value = _num(five_change)
    if not math.isnan(five_value):
        if five_value > 8:
            trend_text = "\u8fd1\u4e94\u5e74\u50f9\u683c\u5448\u660e\u986f\u4e0a\u5347\uff0c\u4ee3\u8868\u5340\u57df\u884c\u60c5\u6709\u652f\u6490\uff0c\u4f46\u8ffd\u50f9\u98a8\u96aa\u4e5f\u8f03\u9ad8\u3002"
        elif five_value < -8:
            trend_text = "\u8fd1\u4e94\u5e74\u50f9\u683c\u504f\u5f31\uff0c\u51fa\u50f9\u6642\u61c9\u66f4\u4fdd\u5b88\uff0c\u4e26\u78ba\u8a8d\u662f\u5426\u70ba\u5340\u57df\u6216\u7522\u54c1\u689d\u4ef6\u9020\u6210\u3002"
        else:
            trend_text = "\u8fd1\u4e94\u5e74\u50f9\u683c\u8b8a\u5316\u76f8\u5c0d\u5e73\u7a69\uff0c\u53ef\u512a\u5148\u7528\u8fd1\u4e00\u5e74\u8207\u76f8\u4f3c\u6848\u4f8b\u4f5c\u70ba\u51fa\u50f9\u4f9d\u64da\u3002"
        lines.append(f"{trend_text} \u76ee\u524d\u8fd1\u4e94\u5e74\u6f32\u8dcc\u5e45\u70ba {_fmt_metric(five_change, '%')}\u3002")

    if heat_detail:
        lines.append(f"\u4ea4\u6613\u71b1\u5ea6\u70ba {heat}\u3002{heat_detail}\uff0c\u53ef\u7528\u4f86\u5224\u65b7\u8b70\u50f9\u6642\u8ce3\u65b9\u662f\u5426\u5bb9\u6613\u627e\u5230\u66ff\u4ee3\u8cb7\u65b9\u3002")
    if rank_text:
        lines.append(f"\u884c\u653f\u5340\u6bd4\u8f03\uff1a{rank_text}\u3002")

    lines.append("\u63d0\u9192\uff1a\u6b64\u8aaa\u660e\u7531\u5be6\u50f9\u767b\u9304\u7d71\u8a08\u8cc7\u6599\u81ea\u52d5\u6574\u7406\uff0c\u5c6c\u65bc\u8f14\u52a9\u5224\u8b80\uff0c\u4e0d\u7b49\u65bc\u4f30\u50f9\u6216\u4fdd\u8b49\u6210\u4ea4\u50f9\uff1b\u4ecd\u9700\u6bd4\u5c0d\u6a13\u5c64\u3001\u5c4b\u6cc1\u3001\u8eca\u4f4d\u3001\u88dd\u6f62\u3001\u7ba1\u7406\u54c1\u8cea\u8207\u5be6\u969b\u6210\u4ea4\u689d\u4ef6\u3002")
    return "\n\n".join(lines)


def render_real_price_analysis(metrics):
    """Render real price analysis in Streamlit."""
    if not metrics:
        st.info("\u8cc7\u6599\u4e0d\u8db3\uff0c\u5efa\u8b70\u653e\u5bec\u689d\u4ef6")
        return

    message = metrics.get("message", "")
    if message:
        st.warning(message)

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("\u672c\u6848\u55ae\u50f9", _fmt_metric(metrics.get("target_unit_price"), " \u842c/\u576a"))
    c2.metric("\u5468\u908a\u8fd1\u4e00\u5e74\u5747\u50f9", _fmt_metric(metrics.get("nearby_one_year_avg"), " \u842c/\u576a"))
    c3.metric("\u50f9\u683c\u5dee\u8ddd", _fmt_metric(metrics.get("price_gap_pct"), "%"))
    c4.metric("\u8fd1 5 \u5e74\u6f32\u8dcc\u5e45", _fmt_metric(metrics.get("five_year_change_pct"), "%"))
    c5.metric("\u6210\u4ea4\u91cf", f"{metrics.get('transaction_count', 0)} \u7b46")

    tabs = st.tabs(["\U0001f916 AI\u8aaa\u660e", "\U0001f4b0 \u8b70\u50f9", "\U0001f4c8 \u8da8\u52e2", "\U0001f4ca \u5206\u5e03", "\U0001f3d9\ufe0f \u884c\u653f\u5340", "\U0001f4cb \u6848\u4f8b"])

    with tabs[0]:
        st.markdown("#### AI \u50f9\u683c\u5224\u8b80")
        st.info(_build_real_price_ai_explanation(metrics))

    with tabs[1]:
        st.markdown("#### \u8b70\u50f9\u8207\u884c\u60c5\u5224\u65b7")
        p1, p2, p3, p4 = st.columns(4)
        p1.metric("\u5408\u7406\u55ae\u50f9\u5340\u9593", f"{_fmt_metric(metrics.get('reasonable_unit_price_low'), '')} ~ {_fmt_metric(metrics.get('reasonable_unit_price_high'), ' \u842c/\u576a')}")
        p2.metric("\u5408\u7406\u7e3d\u50f9\u5340\u9593", _fmt_money_range(metrics.get("reasonable_total_low"), metrics.get("reasonable_total_high")))
        p3.metric("\u5efa\u8b70\u51fa\u50f9\u5340\u9593", _fmt_money_range(metrics.get("suggested_offer_low"), metrics.get("suggested_offer_high")))
        p4.metric("\u4f30\u8a08\u8b70\u50f9\u7a7a\u9593", _fmt_metric(metrics.get("negotiation_space_pct"), "%"))
        st.caption("\u5340\u9593\u6703\u53d7\u5efa\u576a\u3001\u5c4b\u9f61\u3001\u5efa\u7269\u578b\u614b\u8207\u7be9\u9078\u5230\u7684\u76f8\u4f3c\u6210\u4ea4\u8cc7\u6599\u5f71\u97ff\uff0c\u8acb\u642d\u914d\u5be6\u969b\u5c4b\u6cc1\u5224\u65b7\u3002")

    with tabs[2]:
        st.markdown("#### \u8fd1 1 / 3 / 5 \u5e74\u884c\u60c5")
        a1, a2, a3, a4 = st.columns(4)
        a1.metric("\u8fd1\u4e00\u5e74\u5747\u50f9", _fmt_metric(metrics.get("nearby_one_year_avg"), " \u842c/\u576a"))
        a2.metric("\u8fd1\u4e09\u5e74\u5747\u50f9", _fmt_metric(metrics.get("nearby_three_year_avg"), " \u842c/\u576a"))
        a3.metric("\u8fd1\u4e94\u5e74\u5747\u50f9", _fmt_metric(metrics.get("nearby_five_year_avg"), " \u842c/\u576a"))
        a4.metric("\u4ea4\u6613\u71b1\u5ea6", metrics.get("market_heat_label", "\u7121\u8cc7\u6599"))
        st.caption(metrics.get("market_heat_detail", ""))
        yearly = metrics.get("yearly_avg_unit_price")
        if isinstance(yearly, pd.DataFrame) and not yearly.empty:
            st.markdown("#### \u8fd1 5 \u5e74\u5e73\u5747\u55ae\u50f9\u8da8\u52e2")
            st.line_chart(yearly.set_index("\u5e74\u4efd"))
        else:
            st.info("\u8fd1 5 \u5e74\u8da8\u52e2\u8cc7\u6599\u4e0d\u8db3")

    with tabs[3]:
        dist = metrics.get("price_distribution")
        st.markdown("#### \u5468\u908a\u6210\u4ea4\u55ae\u50f9\u5206\u5e03")
        if isinstance(dist, pd.DataFrame) and not dist.empty:
            st.bar_chart(dist.set_index("\u55ae\u50f9\u5340\u9593"))
            target_band = dist.attrs.get("target_band", "")
            if target_band:
                st.caption(f"\u672c\u6848\u55ae\u50f9\u7d04\u843d\u5728\uff1a{target_band}")
        else:
            st.info("\u6210\u4ea4\u55ae\u50f9\u5206\u5e03\u8cc7\u6599\u4e0d\u8db3")

    with tabs[4]:
        ranking = metrics.get("district_ranking")
        st.markdown("#### \u884c\u653f\u5340\u884c\u60c5\u6392\u540d")
        if isinstance(ranking, pd.DataFrame) and not ranking.empty:
            st.caption(metrics.get("district_rank_text", ""))
            display_rank = ranking.head(10).copy()
            if "\u5e73\u5747\u55ae\u50f9" in display_rank.columns:
                display_rank["\u5e73\u5747\u55ae\u50f9"] = pd.to_numeric(display_rank["\u5e73\u5747\u55ae\u50f9"], errors="coerce").round(2)
            st.dataframe(display_rank, use_container_width=True, hide_index=True)
        else:
            st.info("\u884c\u653f\u5340\u6392\u540d\u8cc7\u6599\u4e0d\u8db3")

    with tabs[5]:
        cases = metrics.get("similar_cases")
        st.markdown("#### \u76f8\u4f3c\u6210\u4ea4\u6848\u4f8b\u524d 10 \u7b46")
        if isinstance(cases, pd.DataFrame) and not cases.empty:
            st.dataframe(cases, use_container_width=True, hide_index=True)
        else:
            st.info("\u8cc7\u6599\u4e0d\u8db3\uff0c\u5efa\u8b70\u653e\u5bec\u689d\u4ef6")

def format_real_price_metrics_for_prompt(real_price_results):
    if not real_price_results:
        return "\n\u3010\u5be6\u50f9\u767b\u9304\u50f9\u683c\u5206\u6790\u3011\n\u7121\u5be6\u50f9\u767b\u9304\u5206\u6790\u8cc7\u6599\n"
    lines = ["\n\u3010\u5be6\u50f9\u767b\u9304\u50f9\u683c\u5206\u6790\u3011", "=" * 60]
    for house_name, result in real_price_results.items():
        if not result or result.get("error"):
            msg = result.get("error", "\u8cc7\u6599\u4e0d\u8db3\uff0c\u5efa\u8b70\u653e\u5bec\u689d\u4ef6") if isinstance(result, dict) else "\u8cc7\u6599\u4e0d\u8db3\uff0c\u5efa\u8b70\u653e\u5bec\u689d\u4ef6"
            lines.append(f"- {house_name}\uff1a{msg}")
            continue
        metrics = result.get("metrics", {})
        lines.append(
            f"- {house_name}\uff1a\u672c\u6848\u55ae\u50f9 {_fmt_metric(metrics.get('target_unit_price'), ' \u842c/\u576a')}\uff1b"
            f"\u5468\u908a\u8fd1\u4e00\u5e74\u5747\u50f9 {_fmt_metric(metrics.get('nearby_one_year_avg'), ' \u842c/\u576a')}\uff1b"
            f"\u8fd1\u4e09\u5e74\u5747\u50f9 {_fmt_metric(metrics.get('nearby_three_year_avg'), ' \u842c/\u576a')}\uff1b"
            f"\u8fd1\u4e94\u5e74\u5747\u50f9 {_fmt_metric(metrics.get('nearby_five_year_avg'), ' \u842c/\u576a')}\uff1b"
            f"\u50f9\u683c\u5dee\u8ddd {_fmt_metric(metrics.get('price_gap_pct'), '%')}\uff1b"
            f"\u5408\u7406\u7e3d\u50f9\u5340\u9593 {_fmt_money_range(metrics.get('reasonable_total_low'), metrics.get('reasonable_total_high'))}\uff1b"
            f"\u5efa\u8b70\u51fa\u50f9\u5340\u9593 {_fmt_money_range(metrics.get('suggested_offer_low'), metrics.get('suggested_offer_high'))}\uff1b"
            f"\u4f30\u8a08\u8b70\u50f9\u7a7a\u9593 {_fmt_metric(metrics.get('negotiation_space_pct'), '%')}\uff1b"
            f"\u8fd15\u5e74\u6f32\u8dcc\u5e45 {_fmt_metric(metrics.get('five_year_change_pct'), '%')}\uff1b"
            f"\u4ea4\u6613\u71b1\u5ea6 {metrics.get('market_heat_label', '\u7121\u8cc7\u6599')}\uff08{metrics.get('market_heat_detail', '\u7121\u8cc7\u6599')}\uff09\uff1b"
            f"\u884c\u653f\u5340\u6392\u540d {metrics.get('district_rank_text', '\u7121\u8cc7\u6599')}\uff1b"
            f"\u76f8\u4f3c\u6210\u4ea4\u91cf {metrics.get('transaction_count', 0)} \u7b46\u3002"
        )
    return "\n".join(lines) + "\n"
