# config.py - 放置在專案根目錄

# 關鍵字顏色設定
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

# 路徑設定
DATA_FOLDER = "./Data"
PAGE_MODULES_FOLDER = "./page_modules"
