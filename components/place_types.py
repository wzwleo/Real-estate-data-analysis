# components/place_types.py

PLACE_TYPES = {
    "教育": [
        "圖書館", "library",
        "幼兒園", "preschool",
        "小學", "primary_school",
        "國中", "secondary_school",
        "高中", "secondary_school",
        "大學", "university",
        "學校", "school",
    ],
    "購物": [
        "超市", "supermarket",
        "便利商店", "convenience_store",
        "全聯福利中心", "supermarket",  # 全聯使用 supermarket
        "家樂福", "supermarket",  # 家樂福使用 supermarket
        "大潤發", "supermarket",  # 大潤發使用 supermarket
        "好市多", "supermarket",  # 好市多使用 supermarket
        "屈臣氏", "drugstore",
        "康是美", "drugstore",
        "寶雅", "beauty_salon",  # 寶雅用 beauty_salon 替代
        "藥妝店", "drugstore",
        "五金行", "hardware_store",
        "家具行", "furniture_store",
        "書局", "book_store",
        "文具店", "office_supplies_store",  # 文具店用 office_supplies_store
        "手機行", "cell_phone_store",
        "電腦賣場", "electronics_store",
        "服飾店", "clothing_store",
        "鞋店", "shoe_store",
        "眼鏡行", "eyeglasses_store",  # 眼鏡行使用 eyeglasses_store
        "百貨公司", "department_store",
        "購物中心", "shopping_mall",
        "市場", "market",
        "傳統市場", "market",
        "夜市", "night_market",  # 夜市使用 night_market
        "批發", "wholesaler"
    ],
    "交通運輸": [
        "公車站", "bus_station",
        "捷運站", "subway_station",
        "火車站", "train_station",
        "高鐵站", "train_station",  # 高鐵站使用 train_station
        "客運站", "bus_station",
        "計程車行", "taxi_stand",
        "停車場", "parking",
        "加油站", "gas_station",
        "YouBike", "bicycle_store",  # YouBike 用 bicycle_store 替代
        "機車行", "motorcycle_repair",  # 使用自定義關鍵字
        "汽車維修", "car_repair"  # 使用自定義關鍵字
    ],
    "健康與保健": [
        "醫院", "hospital",
        "診所", "doctor",  # 診所使用 doctor
        "衛生所", "clinic",  # 衛生所使用 clinic
        "藥局", "pharmacy",
        "牙醫診所", "dentist",
        "中醫診所", "alternative_medicine",  # 中醫使用 alternative_medicine
        "西醫診所", "doctor",
        "小兒科診所", "doctor",  # 小兒科使用 doctor
        "婦產科診所", "doctor",  # 婦產科使用 doctor
        "眼科診所", "optometrist",  # 眼科使用 optometrist
        "皮膚科診所", "dermatologist",  # 皮膚科使用 dermatologist
        "復健科診所", "physiotherapist",
        "物理治療所", "physiotherapist",
        "按摩店", "massage",
        "養生館", "spa",
        "SPA", "spa",
        "健身中心", "gym",
        "健身房", "gym",
        "瑜珈教室", "yoga_studio",
        "運動中心", "sports_complex"  # 運動中心使用 sports_complex
    ],
    "餐飲美食": [
        "餐廳", "restaurant",
        "小吃店", "food",
        "早餐店", "breakfast_restaurant",
        "咖啡廳", "cafe",
        "星巴克", "cafe",
        "路易莎咖啡", "cafe",
        "85度C", "cafe",
        "手搖飲料店", "bubble_tea_shop",  # 手搖飲使用自定義
        "飲料店", "beverage_shop",  # 飲料店使用自定義
        "速食店", "fast_food_restaurant",
        "麥當勞", "fast_food_restaurant",
        "肯德基", "fast_food_restaurant",
        "摩斯漢堡", "fast_food_restaurant",
        "漢堡王", "fast_food_restaurant",
        "披薩店", "pizza_restaurant",
        "達美樂披薩", "pizza_restaurant",
        "拿坡里披薩", "pizza_restaurant",
        "必勝客", "pizza_restaurant",
        "火鍋店", "hot_pot_restaurant",  # 火鍋使用 hot_pot
        "燒烤店", "barbecue_restaurant",
        "牛排館", "steak_house",
        "鐵板燒", "teppanyaki",  # 鐵板燒使用自定義
        "日本料理", "japanese_restaurant",
        "壽司店", "sushi_restaurant",
        "拉麵店", "ramen_restaurant",
        "韓式料理", "korean_restaurant",
        "泰式料理", "thai_restaurant",
        "越南料理", "vietnamese_restaurant",
        "美式餐廳", "american_restaurant",
        "義大利麵餐廳", "italian_restaurant",
        "自助餐", "buffet",
        "便當店", "lunch_box",  # 便當店使用自定義
        "麵店", "noodle_restaurant",  # 麵店使用自定義
        "滷味店", "braised_food_shop",  # 滷味使用自定義
        "鹽酥雞", "fried_chicken_restaurant",
        "雞排店", "fried_chicken_restaurant",
        "甜點店", "dessert_shop",
        "蛋糕店", "bakery",
        "麵包店", "bakery",
        "冰店", "ice_cream_shop",
        "豆花店", "dessert_shop"
    ],
    "生活服務": [
        "銀行", "bank",
        "郵局", "post_office",
        "派出所", "police",
        "警察局", "police",
        "消防局", "fire_station",
        "區公所", "local_government_office",
        "戶政事務所", "government_office",
        "運動公園", "park",
        "公園", "park",
        "兒童公園", "park",
        "河濱公園", "park",
        "廟宇", "place_of_worship",
        "教堂", "church",
        "洗車場", "car_wash",
        "汽車美容", "car_wash",
        "洗衣店", "laundry",
        "影印店", "printing_shop",
        "電信行", "telecommunications_service",
        "中華電信", "telecommunications_service",
        "台灣大哥大", "telecommunications_service",
        "遠傳電信", "telecommunications_service",
        "寵物店", "pet_store",
        "動物醫院", "veterinary_care"
    ]
}

# 建立反向映射
ENGLISH_TO_CHINESE = {}
for category, items in PLACE_TYPES.items():
    for i in range(0, len(items), 2):
        if i+1 < len(items):
            ENGLISH_TO_CHINESE[items[i+1]] = items[i]
