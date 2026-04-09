# components/place_types.py
# 生活機能類別
# 以台灣房地產生活機能分析常用設施為主，保留 comparison.py 已使用的核心子項。
PLACE_TYPES = {
    "教育": [
        "幼兒園",
        "小學",
        "國中",
        "高中",
        "大學",
        "教育機構",
        "圖書館",
        "補習班",
    ],
    "購物": [
        "便利商店",
        "超市",
        "量販店",
        "傳統市場",
        "市場",
        "百貨公司",
        "購物中心",
        "藥妝店",
        "五金行",
        "家具行",
        "書局",
        "寵物店",
    ],
    "交通運輸": [
        "公車站",
        "捷運站",
        "火車站",
        "台鐵站",
        "高鐵站",
        "客運站",
        "輕軌站",
        "公共自行車站",
        "停車場",
        "轉運站",
        "加油站",
    ],
    "健康與保健": [
        "醫院",
        "診所",
        "藥局",
        "牙醫",
        "牙醫診所",
        "小兒科",
        "復健科",
        "中醫",
        "健身房",
    ],
    "餐飲美食": [
        "餐廳",
        "咖啡廳",
        "早餐店",
        "早餐餐廳",
        "早午餐餐廳",
        "飲料店",
        "小吃",
        "麵店",
        "火鍋",
        "便當店",
        "速食店",
        "親子餐廳",
        "素食餐廳",
    ],
    "生活服務": [
        "公園",
        "河濱公園",
        "登山步道",
        "兒童遊戲場",
        "寵物公園",
        "運動中心",
        "社區中心",
        "洗衣店",
        "警察局",
        "消防局",
        "廟宇",
        "教堂",
        "電影院",
    ],
    "金融機構": [
        "銀行",
        "郵局",
        "ATM",
        "信用合作社",
    ],
}

# 嫌惡設施類別 - 只保留影響類型，沒有預設權重
NUISANCE_TYPES = {
    "加油站/瓦斯行": {
        "level": "高",
        "impacts": ["生命安全", "空氣品質"],
        "suggested_distance": 600,
        "keywords": ["加油站", "瓦斯行", "瓦斯桶", "加氣站"]
    },
    "基地台/電塔/變電所": {
        "level": "中",
        "impacts": ["健康疑慮", "視野"],
        "suggested_distance": 900,
        "keywords": ["基地台", "電塔", "變電所", "高壓電塔"]
    },
    "警察局/消防局": {
        "level": "低",
        "impacts": ["噪音"],
        "suggested_distance": 300,
        "keywords": ["警察局", "消防局", "派出所", "消防隊"]
    },
    "垃圾場/回收場": {
        "level": "中",
        "impacts": ["環境衛生", "空氣品質"],
        "suggested_distance": 300,
        "keywords": ["垃圾場", "回收場", "資源回收", "垃圾處理"]
    },
    "市場(傳統市場/夜市)": {
        "level": "中",
        "impacts": ["環境衛生", "交通", "噪音"],
        "suggested_distance": 300,
        "keywords": ["傳統市場", "夜市", "菜市場", "早市", "黃昏市場"]
    },
    "高架道路/地下道/捷運": {
        "level": "中",
        "impacts": ["噪音", "交通"],
        "suggested_distance": 300,
        "keywords": ["高架道路", "地下道", "捷運", "快速道路", "高速公路"]
    },
    "特種行業/KTV/遊樂場": {
        "level": "高",
        "impacts": ["噪音", "安全"],
        "suggested_distance": 600,
        "keywords": ["KTV", "酒店", "舞廳", "夜店", "遊樂場", "特種行業"]
    },
    "醫院": {
        "level": "中",
        "impacts": ["噪音", "心理"],
        "suggested_distance": 300,
        "keywords": ["醫院", "醫療中心", "綜合醫院"]
    },
    "大型賣場/停車場": {
        "level": "中",
        "impacts": ["交通", "噪音"],
        "suggested_distance": 300,
        "keywords": ["大賣場", "量販店", "購物中心", "停車場"]
    },
    "交流道": {
        "level": "高",
        "impacts": ["交通", "噪音"],
        "suggested_distance": 900,
        "keywords": ["交流道", "高速公路交流道"]
    },
    "工業區/工廠": {
        "level": "高",
        "impacts": ["噪音", "空氣品質", "汙水", "環境衛生"],
        "suggested_distance": 900,
        "keywords": ["工業區", "工廠", "工業園區", "加工區"]
    },
    "禮儀社/葬儀社": {
        "level": "高",
        "impacts": ["風水", "心理"],
        "suggested_distance": 1200,
        "keywords": ["禮儀社", "葬儀社", "生命禮儀"]
    },
    "宮廟/神壇": {
        "level": "高",
        "impacts": ["噪音", "交通", "空氣品質"],
        "suggested_distance": 1200,
        "keywords": ["宮廟", "神壇", "寺廟", "媽祖廟", "土地公廟"]
    },
    "焚化爐": {
        "level": "高",
        "impacts": ["環境衛生", "空氣品質"],
        "suggested_distance": 900,
        "keywords": ["焚化爐", "垃圾焚化"]
    },
    "發電廠": {
        "level": "高",
        "impacts": ["健康疑慮", "視野"],
        "suggested_distance": 900,
        "keywords": ["發電廠", "火力發電", "核電廠"]
    },
    "監獄": {
        "level": "高",
        "impacts": ["風水", "心理"],
        "suggested_distance": 900,
        "keywords": ["監獄", "看守所", "矯正署"]
    },
    "汙水處理廠": {
        "level": "高",
        "impacts": ["空氣品質", "環境衛生", "汙水"],
        "suggested_distance": 1200,
        "keywords": ["汙水處理廠", "水資源中心"]
    },
    "飛機場": {
        "level": "高",
        "impacts": ["噪音", "安全"],
        "suggested_distance": 1200,
        "keywords": ["機場", "航空站"]
    },
    "公墓/靈骨塔/殯儀館": {
        "level": "高",
        "impacts": ["風水", "心理"],
        "suggested_distance": 1200,
        "keywords": ["公墓", "靈骨塔", "殯儀館", "墓園", "納骨塔"]
    },
    "畜牧業": {
        "level": "高",
        "impacts": ["環境衛生", "空氣品質", "噪音"],
        "suggested_distance": 1200,
        "keywords": ["畜牧場", "養豬場", "養雞場", "牧場"]
    }
}

# 影響類型定義（用於權重設定介面）
IMPACT_TYPES = {
    "噪音": {
        "description": "車輛、廟會、KTV、高架道路、交流道等噪音源",
        "color": "#ff9800"
    },
    "空氣品質": {
        "description": "工廠廢氣、焚化爐、宮廟香火、加油站油氣",
        "color": "#f44336"
    },
    "生命安全": {
        "description": "加油站爆炸、高壓電塔輻射、飛安風險",
        "color": "#d32f2f"
    },
    "環境衛生": {
        "description": "垃圾場、夜市、畜牧業、汙水處理廠、工業區",
        "color": "#795548"
    },
    "風水": {
        "description": "公墓、殯儀館、監獄、禮儀社",
        "color": "#9c27b0"
    },
    "心理": {
        "description": "醫院、警察局、監獄帶來的心理壓力",
        "color": "#e91e63"
    },
    "交通": {
        "description": "交流道、大型賣場、停車場、高架道路",
        "color": "#2196f3"
    },
    "視野": {
        "description": "高壓電塔、基地台、發電廠影響視野",
        "color": "#00bcd4"
    },
    "健康疑慮": {
        "description": "基地台、發電廠、工業區的健康影響",
        "color": "#4caf50"
    },
    "安全": {
        "description": "特種行業、KTV、遊樂場、治安問題",
        "color": "#ff5722"
    },
    "汙水": {
        "description": "工業區、汙水處理廠的水質影響",
        "color": "#3f51b5"
    }
}

# 建立反向映射
CHINESE_TO_CATEGORY = {}

for category, items in PLACE_TYPES.items():
    for item in items:
        CHINESE_TO_CATEGORY[item] = category
