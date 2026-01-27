# utils/data_loaders.py
import os
import pandas as pd


def load_real_estate_csv(folder="./page_modules"):
    """載入不動產 CSV 資料"""
    file_names = [
        f for f in os.listdir(folder)
        if f.startswith("合併後不動產統計_") and f.endswith(".csv")
    ]
    
    dfs = []
    for file in file_names:
        path = os.path.join(folder, file)
        try:
            df = pd.read_csv(path, encoding="utf-8")
        except:
            try:
                df = pd.read_csv(path, encoding="big5")
            except:
                continue
        dfs.append(df)
    
    if dfs:
        return pd.concat(dfs, ignore_index=True)
    return pd.DataFrame()


def load_population_csv(folder="./page_modules"):
    """載入人口 CSV 資料"""
    path = os.path.join(folder, "NEWWWW.csv")
    if not os.path.exists(path):
        return pd.DataFrame()
    
    try:
        df = pd.read_csv(path, encoding="utf-8")
    except:
        df = pd.read_csv(path, encoding="big5")
    
    return df
