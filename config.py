# config.py - 專案根目錄
import os

# 基礎路徑
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 資料路徑
DATA_FOLDER = os.path.join(BASE_DIR, "Data")
PAGE_MODULES_FOLDER = os.path.join(BASE_DIR, "page_modules")
COMPONENTS_FOLDER = os.path.join(BASE_DIR, "components")
DOWNLOAD_DATA_FOLDER = os.path.join(BASE_DIR, "download_data")

# 顏色設定
CATEGORY_COLORS = {
    "教育": "#1E90FF",        # 藍色
    "購物": "#FF8C00",        # 橘色
    "交通運輸": "#800080",     # 紫色
    "健康與保健": "#32CD32",   # 綠色
    "餐飲美食": "#FF4500",     # 紅色
    "生活服務": "#FF1493",     # 深粉色
}

# 預設值
DEFAULT_RADIUS = 500
DEFAULT_RADIUS_RANGE = (100, 2000, 100)

# API 設定
GOOGLE_MAPS_BASE_URL = "https://maps.googleapis.com/maps/api/"
GEMINI_MODEL = "gemini-2.0-flash"

# 除錯模式
DEBUG = True

# 確保目錄存在
for folder in [DATA_FOLDER, PAGE_MODULES_FOLDER, COMPONENTS_FOLDER, DOWNLOAD_DATA_FOLDER]:
    os.makedirs(folder, exist_ok=True)
