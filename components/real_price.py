import io
import math
import re
import zipfile
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import requests
import streamlit as st


REAL_PRICE_DOWNLOAD_URLS = {
    "default": "https://plvr.land.moi.gov.tw/DownloadOpenData?type=zip&fileName=lvr_landcsv.zip",
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


def get_cache_path():
    """Return local cache directory for real price data."""
    base = Path(__file__).resolve().parents[1]
    path = base / "data" / "real_price"
    path.mkdir(parents=True, exist_ok=True)
    return path


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


def _safe_filename(city):
    city = normalize_city_name(city) or "unknown"
    return re.sub(r"[^0-9A-Za-z\u4e00-\u9fff_-]+", "_", city)


def _cache_csv_path(city):
    return get_cache_path() / f"{_safe_filename(city)}.csv"


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


def download_latest_real_price_data(city):
    """Download official ZIP/CSV real price data for a city and cache it locally."""
    city = normalize_city_name(city)
    if not city:
        raise ValueError("未提供縣市，無法下載實價登錄資料")

    url = REAL_PRICE_DOWNLOAD_URLS.get(city) or REAL_PRICE_DOWNLOAD_URLS.get("default")
    if not url:
        raise ValueError("未設定實價登錄下載 URL，請設定 REAL_PRICE_DOWNLOAD_URLS")

    try:
        resp = requests.get(url, timeout=60)
    except Exception as e:
        err = str(e)
        if "SSL" in err or "CERTIFICATE_VERIFY_FAILED" in err or "certificate verify failed" in err:
            st.warning("內政部實價登錄下載站 SSL 憑證驗證失敗，改用官方來源備援下載。")
            requests.packages.urllib3.disable_warnings()
            resp = requests.get(url, timeout=60, verify=False)
        else:
            raise
    resp.raise_for_status()
    raw = resp.content
    cache_file = _cache_csv_path(city)

    dfs = []
    if zipfile.is_zipfile(io.BytesIO(raw)):
        code = CITY_FILE_CODES.get(city)
        with zipfile.ZipFile(io.BytesIO(raw)) as zf:
            names = zf.namelist()
            target_names = []
            if code:
                target_names = [n for n in names if n.lower().endswith(f"{code}_lvr_land_a.csv")]
            if not target_names and code:
                target_names = [n for n in names if f"{code}_lvr_land" in n.lower() and n.lower().endswith(".csv")]
            if not target_names:
                target_names = [n for n in names if n.lower().endswith("_lvr_land_a.csv")]
            for name in target_names:
                with zf.open(name) as f:
                    dfs.append(_read_csv_bytes(f.read()))
    else:
        dfs.append(_read_csv_bytes(raw))

    if not dfs:
        raise ValueError(f"下載資料中找不到 {city} 的實價登錄 CSV")

    merged = pd.concat(dfs, ignore_index=True)
    prepared = _prepare_real_price_df(merged, city)
    if prepared.empty:
        raise ValueError(f"{city} 實價登錄資料解析後為空")

    prepared.to_csv(cache_file, index=False, encoding="utf-8-sig")
    return prepared


def load_cached_real_price_data(city):
    """Load cached real price CSV for a city."""
    cache_file = _cache_csv_path(city)
    if not cache_file.exists():
        return pd.DataFrame()
    df = pd.read_csv(cache_file, encoding="utf-8-sig")
    if "交易日期" in df.columns:
        df["交易日期"] = pd.to_datetime(df["交易日期"], errors="coerce")
    return df


def update_real_price_cache_if_needed(city, max_age_days=10):
    """Refresh cache if missing or older than max_age_days."""
    cache_file = _cache_csv_path(city)
    if cache_file.exists():
        age = datetime.now() - datetime.fromtimestamp(cache_file.stat().st_mtime)
        if age <= timedelta(days=max_age_days):
            return load_cached_real_price_data(city)
    return download_latest_real_price_data(city)


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
    return selected.sort_values("交易日期", ascending=False).reset_index(drop=True)


def calculate_price_metrics(transactions, target_house):
    """Calculate price metrics for target house and comparable transactions."""
    target = target_house or {}
    area = _parse_number(target.get("建坪"))
    price = _parse_number(target.get("總價(萬)"))
    target_unit_price = price / area if area and not math.isnan(area) and not math.isnan(price) else math.nan

    tx = transactions.copy() if transactions is not None else pd.DataFrame()
    metrics = {
        "target_unit_price": target_unit_price,
        "nearby_one_year_avg": math.nan,
        "price_gap_pct": math.nan,
        "yearly_avg_unit_price": pd.DataFrame(columns=["年份", "平均單價(萬/坪)"]),
        "yearly_volume": pd.DataFrame(columns=["年份", "成交量"]),
        "five_year_change_pct": math.nan,
        "similar_cases": pd.DataFrame(),
        "transaction_count": 0,
        "message": "",
    }

    if tx.empty:
        metrics["message"] = "資料不足，建議放寬條件"
        return metrics

    tx["交易日期"] = pd.to_datetime(tx["交易日期"], errors="coerce")
    tx = tx.dropna(subset=["交易日期", "單價(萬/坪)"])
    metrics["transaction_count"] = int(len(tx))
    if len(tx) < 10:
        metrics["message"] = "資料不足，建議放寬條件"

    one_year_cutoff = pd.Timestamp(datetime.now() - timedelta(days=365))
    recent = tx[tx["交易日期"] >= one_year_cutoff]
    if not recent.empty:
        metrics["nearby_one_year_avg"] = float(recent["單價(萬/坪)"].mean())
    elif not tx.empty:
        metrics["nearby_one_year_avg"] = float(tx["單價(萬/坪)"].mean())

    if not math.isnan(target_unit_price) and not math.isnan(metrics["nearby_one_year_avg"]) and metrics["nearby_one_year_avg"]:
        metrics["price_gap_pct"] = (target_unit_price - metrics["nearby_one_year_avg"]) / metrics["nearby_one_year_avg"] * 100

    tx["年份"] = tx["交易日期"].dt.year
    yearly = tx.groupby("年份", as_index=False)["單價(萬/坪)"].mean().sort_values("年份")
    volume = tx.groupby("年份", as_index=False).size().rename(columns={"size": "成交量"}).sort_values("年份")
    metrics["yearly_avg_unit_price"] = yearly.rename(columns={"單價(萬/坪)": "平均單價(萬/坪)"})
    metrics["yearly_volume"] = volume

    if len(yearly) >= 2 and yearly.iloc[0]["單價(萬/坪)"]:
        first = yearly.iloc[0]["單價(萬/坪)"]
        last = yearly.iloc[-1]["單價(萬/坪)"]
        metrics["five_year_change_pct"] = (last - first) / first * 100

    display_cols = ["交易日期", "行政區", "建物型態", "地址", "建坪", "屋齡", "總價(萬)", "單價(萬/坪)"]
    available = [c for c in display_cols if c in tx.columns]
    cases = tx.sort_values("交易日期", ascending=False).head(10)[available].copy()
    if "交易日期" in cases.columns:
        cases["交易日期"] = cases["交易日期"].dt.strftime("%Y-%m-%d")
    for col in ["建坪", "屋齡", "總價(萬)", "單價(萬/坪)"]:
        if col in cases.columns:
            cases[col] = pd.to_numeric(cases[col], errors="coerce").round(2)
    metrics["similar_cases"] = cases
    return metrics


def _fmt_metric(value, suffix=""):
    try:
        if value is None or math.isnan(float(value)):
            return "無資料"
        return f"{float(value):.2f}{suffix}"
    except Exception:
        return "無資料"


def render_real_price_analysis(metrics):
    """Render real price analysis in Streamlit."""
    if not metrics:
        st.info("資料不足，建議放寬條件")
        return

    message = metrics.get("message", "")
    if message:
        st.warning(message)

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("本案單價", _fmt_metric(metrics.get("target_unit_price"), " 萬/坪"))
    c2.metric("周邊近一年均價", _fmt_metric(metrics.get("nearby_one_year_avg"), " 萬/坪"))
    gap = metrics.get("price_gap_pct")
    c3.metric("價格差距", _fmt_metric(gap, "%"))
    c4.metric("近 5 年漲跌幅", _fmt_metric(metrics.get("five_year_change_pct"), "%"))
    c5.metric("成交量", f"{metrics.get('transaction_count', 0)} 筆")

    yearly = metrics.get("yearly_avg_unit_price")
    if isinstance(yearly, pd.DataFrame) and not yearly.empty:
        chart_df = yearly.set_index("年份")
        st.line_chart(chart_df)
    else:
        st.info("近 5 年趨勢資料不足")

    cases = metrics.get("similar_cases")
    st.markdown("#### 相似成交案例前 10 筆")
    if isinstance(cases, pd.DataFrame) and not cases.empty:
        st.dataframe(cases, use_container_width=True, hide_index=True)
    else:
        st.info("資料不足，建議放寬條件")


def format_real_price_metrics_for_prompt(real_price_results):
    if not real_price_results:
        return "\n【實價登錄價格分析】\n無實價登錄分析資料\n"
    lines = ["\n【實價登錄價格分析】", "=" * 60]
    for house_name, result in real_price_results.items():
        if not result or result.get("error"):
            lines.append(f"- {house_name}：{result.get('error', '資料不足，建議放寬條件') if isinstance(result, dict) else '資料不足，建議放寬條件'}")
            continue
        metrics = result.get("metrics", {})
        lines.append(
            f"- {house_name}：本案單價 {_fmt_metric(metrics.get('target_unit_price'), ' 萬/坪')}；"
            f"周邊近一年均價 {_fmt_metric(metrics.get('nearby_one_year_avg'), ' 萬/坪')}；"
            f"價格差距 {_fmt_metric(metrics.get('price_gap_pct'), '%')}；"
            f"近5年漲跌幅 {_fmt_metric(metrics.get('five_year_change_pct'), '%')}；"
            f"相似成交量 {metrics.get('transaction_count', 0)} 筆。"
        )
    return "\n".join(lines) + "\n"
