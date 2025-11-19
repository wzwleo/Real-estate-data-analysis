import streamlit as st
import json
import pandas as pd
import os
from streamlit_echarts import st_echarts
from modules.updater import check_missing_periods
from modules.real_estate_merger_pro import main as process_season

st.set_page_config(page_title="台灣不動產分析", layout="wide")

# 初始化 state
def init_state(defaults):
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_state({
    "selected_city": None,
    "selected_district": None,
    "show_filtered_data": False,
})

# -----------------------------
# Sidebar - 資料更新
# -----------------------------
with st.sidebar:
    st.markdown("## 📥 資料更新")

    if 'updating' not in st.session_state:
        st.session_state.updating = False
    if 'update_complete' not in st.session_state:
        st.session_state.update_complete = False
    if 'update_result' not in st.session_state:
        st.session_state.update_result = None

    if not st.session_state.updating and not st.session_state.update_complete:
        if st.button("一鍵更新至當前期數"):
            st.session_state.updating = True
            st.rerun()

    if st.session_state.updating:
        with st.spinner("正在檢查和更新資料..."):
            try:
                local, online, missing = check_missing_periods()
                st.info(f"本地共有 {len(local)} 期資料")
                st.info(f"內政部目前共提供 {len(online)} 期資料")

                if missing:
                    st.warning(f"缺少以下期數：{', '.join(missing)}")

                    progress_bar = st.progress(0)
                    status_text = st.empty()

                    success_count = 0
                    failed_periods = []

                    for i, period in enumerate(missing):
                        status_text.text(f"正在處理期數：{period} ({i+1}/{len(missing)})")
                        progress_bar.progress((i) / len(missing))

                        try:
                            process_season(period)
                            success_count += 1
                            st.success(f"完成期數 {period}")
                        except Exception:
                            failed_periods.append(period)
                            st.error(f"期數 {period} 更新失敗")

                    progress_bar.progress(1.0)
                    status_text.text("更新完成！")

                    if failed_periods:
                        st.session_state.update_result = f"部分成功：成功 {success_count} 期，失敗 {len(failed_periods)} 期"
                    else:
                        st.session_state.update_result = f"全部更新完成！成功 {success_count} 期資料"

                else:
                    st.session_state.update_result = "資料已經是最新！"

                st.session_state.updating = False
                st.session_state.update_complete = True
                st.rerun()

            except Exception as e:
                st.error(f"更新過程發生錯誤：{e}")
                st.session_state.updating = False
                st.rerun()

    if st.session_state.update_complete and st.session_state.update_result:
        st.success(st.session_state.update_result)
        if st.button("重新檢查更新"):
            st.session_state.updating = False
            st.session_state.update_complete = False
            st.session_state.update_result = None
            st.rerun()

    st.markdown("---")
    st.markdown("## 📌 縣市選擇")

# -----------------------------
# 讀取地區座標（只用來抓行政區清單）
# -----------------------------
with open("district_coords.json", "r", encoding="utf-8") as f:
    district_coords = json.load(f)

city_list = list(district_coords.keys())

# -----------------------------
# 讀取 CSV 資料
# -----------------------------
folder = "./"
file_names = [f for f in os.listdir(folder) if f.startswith("合併後不動產統計_") and f.endswith(".csv")]
dfs = []
for file in file_names:
    try:
        df = pd.read_csv(os.path.join(folder, file))
        dfs.append(df)
    except Exception as e:
        print("讀取失敗：", file, e)

combined_df = pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()

# -----------------------------
# 內容主畫面
# -----------------------------
st.title("📊 台灣不動產資料分析（無地圖 / 無 Gemini）")

chart_type = st.sidebar.selectbox("選擇圖表類型", ["不動產價格趨勢分析", "交易筆數分布"])

col1, col2 = st.columns([3, 1])

# -----------------------------
# 右側：縣市 / 行政區選擇
# -----------------------------
with col2:
    st.subheader("縣市列表")
    for city in city_list:
        if st.button(city):
            st.session_state.selected_city = city
            st.session_state.selected_district = None
            st.session_state.show_filtered_data = True

    if st.session_state.selected_city:
        st.markdown(f"### 行政區：{st.session_state.selected_city}")
        district_names = ["全部"] + list(district_coords[st.session_state.selected_city].keys())

        for name in district_names:
            if st.button(name):
                st.session_state.selected_district = None if name == "全部" else name
                st.session_state.show_filtered_data = True

        if st.button("回到全台"):
            st.session_state.selected_city = None
            st.session_state.selected_district = None
            st.session_state.show_filtered_data = False

# -----------------------------
# 左側：圖表 + 資料表
# -----------------------------
with col1:

    if st.session_state.show_filtered_data:
        filtered_df = combined_df.copy()

        if st.session_state.selected_city:
            filtered_df = filtered_df[filtered_df["縣市"] == st.session_state.selected_city]

        if st.session_state.selected_district:
            filtered_df = filtered_df[filtered_df["行政區"] == st.session_state.selected_district]

        st.markdown("## 📂 篩選結果資料")
        st.write(f"共 {len(filtered_df)} 筆資料")
        st.dataframe(filtered_df)

        # -----------------------------
        # 圖表：價格趨勢
        # -----------------------------
        if chart_type == "不動產價格趨勢分析" and len(filtered_df) > 0:
            filtered_df['年份'] = filtered_df['季度'].str[:3].astype(int) + 1911
            yearly_avg = filtered_df.groupby(['年份', 'BUILD'])['平均單價元平方公尺'].mean().reset_index()

            years = sorted(yearly_avg['年份'].unique())
            year_labels = [str(y) for y in years]

            new_data = [
                int(yearly_avg[(yearly_avg['年份'] == y) & (yearly_avg['BUILD'] == '新成屋')]['平均單價元平方公尺'].values[0])
                if not yearly_avg[(yearly_avg['年份'] == y) & (yearly_avg['BUILD'] == '新成屋')].empty else 0
                for y in years
            ]

            old_data = [
                int(yearly_avg[(yearly_avg['年份'] == y) & (yearly_avg['BUILD'] == '中古屋')]['平均單價元平方公尺'].values[0])
                if not yearly_avg[(yearly_avg['年份'] == y) & (yearly_avg['BUILD'] == '中古屋')].empty else 0
                for y in years
            ]

            options = {
                "title": {"text": "不動產價格趨勢分析"},
                "tooltip": {"trigger": "axis"},
                "legend": {"data": ["新成屋", "中古屋"]},
                "xAxis": {"type": "category", "data": year_labels},
                "yAxis": {"type": "value"},
                "series": [
                    {"name": "新成屋", "type": "line", "data": new_data},
                    {"name": "中古屋", "type": "line", "data": old_data},
                ],
            }
            st_echarts(options, height="400px")

        # -----------------------------
        # 圖表：交易筆數
        # -----------------------------
        elif chart_type == "交易筆數分布" and len(filtered_df) > 0:

            group_col = "縣市" if st.session_state.selected_city is None else "行政區"

            if "交易筆數" in filtered_df.columns:
                counts = filtered_df.groupby(group_col)["交易筆數"].sum().reset_index()
            else:
                counts = filtered_df.groupby(group_col).size().reset_index(name="交易筆數")

            pie_data = [
                {"value": int(row["交易筆數"]), "name": row[group_col]} 
                for _, row in counts.iterrows()
            ]

            pie_data = sorted(pie_data, key=lambda x: x['value'], reverse=True)[:10]

            options = {
                "title": {"text": "交易筆數分布", "left": "center"},
                "tooltip": {"trigger": "item"},
                "legend": {"orient": "vertical", "left": "left"},
                "series": [{
                    "name": "交易筆數",
                    "type": "pie",
                    "radius": "50%",
                    "data": pie_data,
                }],
            }

            st_echarts(options, height="400px")
