# components/market_trend.py
import streamlit as st
import pandas as pd
import os
import sys

# 修正匯入路徑
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

try:
    from config import PAGE_MODULES_FOLDER
    CONFIG_LOADED = True
except ImportError as e:
    CONFIG_LOADED = False
    st.warning(f"無法載入設定: {e}")


class MarketTrendAnalyzer:
    """市場趨勢分析器"""
    
    def __init__(self):
        self.combined_df = None
        self.population_df = None
    
    def render_analysis_tab(self):
        """渲染市場趨勢分析頁面"""
        st.subheader("📊 市場趨勢分析")
        
        # 載入資料
        self.combined_df = self._load_real_estate_data()
        self.population_df = self._load_population_data()
        
        if self.combined_df.empty or self.population_df.empty:
            st.warning("無法載入資料")
            return
        
        # 顯示基本資訊
        col1, col2 = st.columns(2)
        with col1:
            st.metric("不動產資料筆數", f"{len(self.combined_df):,}")
        with col2:
            st.metric("人口資料筆數", f"{len(self.population_df):,}")
        
        # 選擇分析類型
        st.markdown("---")
        st.subheader("📈 圖表分析")
        
        chart_type = st.selectbox(
            "選擇分析類型",
            [
                "不動產價格趨勢分析",
                "交易筆數分布",
                "人口與成交量關係"
            ],
            key="market_chart_type"
        )
        
        # 根據選擇顯示不同的分析
        if chart_type == "不動產價格趨勢分析":
            self._show_price_trend(self.combined_df)
        elif chart_type == "交易筆數分布":
            self._show_transaction_distribution(self.combined_df)
        elif chart_type == "人口與成交量關係":
            self._show_population_transaction_relation(self.combined_df, self.population_df)
    
    def _load_real_estate_data(self):
        """載入不動產資料"""
        try:
            # 尋找不動產 CSV 檔案
            data_dir = PAGE_MODULES_FOLDER
            csv_files = [f for f in os.listdir(data_dir) 
                        if f.startswith("合併後不動產統計_") and f.endswith(".csv")]
            
            if not csv_files:
                st.warning("找不到不動產資料檔案")
                return pd.DataFrame()
            
            dfs = []
            for file in csv_files:
                file_path = os.path.join(data_dir, file)
                try:
                    df = pd.read_csv(file_path, encoding="utf-8")
                except:
                    try:
                        df = pd.read_csv(file_path, encoding="big5")
                    except:
                        continue
                dfs.append(df)
            
            if dfs:
                combined_df = pd.concat(dfs, ignore_index=True)
                # 基本清理
                if "季度" in combined_df.columns:
                    combined_df["民國年"] = combined_df["季度"].str[:3].astype(int)
                return combined_df
            else:
                return pd.DataFrame()
                
        except Exception as e:
            st.error(f"載入不動產資料失敗: {e}")
            return pd.DataFrame()
    
    def _load_population_data(self):
        """載入人口資料"""
        try:
            data_dir = PAGE_MODULES_FOLDER
            file_path = os.path.join(data_dir, "NEWWWW.csv")
            
            if not os.path.exists(file_path):
                st.warning(f"找不到人口資料檔案: {file_path}")
                return pd.DataFrame()
            
            try:
                df = pd.read_csv(file_path, encoding="utf-8")
            except:
                df = pd.read_csv(file_path, encoding="big5")
            
            # 基本清理
            df.columns = [str(c).strip().replace("　", "") for c in df.columns]
            return df
            
        except Exception as e:
            st.error(f"載入人口資料失敗: {e}")
            return pd.DataFrame()
    
    def _show_price_trend(self, df):
        """顯示價格趨勢"""
        st.markdown("### 📈 價格趨勢分析")
        
        if "平均單價元平方公尺" in df.columns and "BUILD" in df.columns:
            # 分組計算平均價格
            price_by_type = df.groupby("BUILD")["平均單價元平方公尺"].mean().reset_index()
            
            # 顯示表格
            st.dataframe(price_by_type, use_container_width=True)
            
            # 簡單圖表
            st.bar_chart(price_by_type.set_index("BUILD")["平均單價元平方公尺"])
        else:
            st.warning("資料中缺少必要的欄位")
    
    def _show_transaction_distribution(self, df):
        """顯示交易筆數分布"""
        st.markdown("### 📊 交易筆數分布")
        
        if "交易筆數" in df.columns:
            total_transactions = df["交易筆數"].sum()
            st.metric("總交易筆數", f"{total_transactions:,}")
            
            # 如果有行政區資訊
            if "行政區" in df.columns:
                trans_by_district = df.groupby("行政區")["交易筆數"].sum().reset_index()
                trans_by_district = trans_by_district.sort_values("交易筆數", ascending=False).head(10)
                
                st.write("交易筆數 Top 10 行政區:")
                st.dataframe(trans_by_district, use_container_width=True)
        else:
            st.warning("資料中缺少交易筆數欄位")
    
    def _show_population_transaction_relation(self, re_df, pop_df):
        """顯示人口與成交量關係"""
        st.markdown("### 👥 人口與成交量關係")
        
        # 簡單的資料預覽
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("不動產資料預覽:")
            st.dataframe(re_df.head(), use_container_width=True)
        
        with col2:
            st.write("人口資料預覽:")
            st.dataframe(pop_df.head(), use_container_width=True)
        
        st.info("人口與成交量分析功能將在此實作")
