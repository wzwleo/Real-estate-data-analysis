# -*- coding: utf-8 -*-
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import pandas as pd
import re
import time
import random
import os

# -----------------------------
# 目標城市列表 (台灣主要縣市 buy 頁面)
# -----------------------------
cities = [
    "Taipei-city", "NewTaipei-city", "Keelung-city", "Yilan-county",
    "Hsinchu-city", "Hsinchu-county", "Taoyuan-city", "Miaoli-county",
    "Taichung-city", "Changhua-county", "Nantou-county", "Yunlin-county",
    "Chiayi-city", "Chiayi-county", "Tainan-city", "Kaohsiung-city",
    "Pingtung-county", "Penghu-county", "Taitung-county", "Hualien-county",
    "Kinmen-county", "Lienchiang-county"
]

# -----------------------------
# Selenium 設定
# -----------------------------
options = Options()
options.add_argument("--headless=new")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--disable-gpu")
options.add_argument("--window-size=1920,1080")

driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

# 建立資料夾
os.makedirs("./Data", exist_ok=True)

# -----------------------------
# 工具函數：安全提取數字
# -----------------------------
def extract_number(text):
    if not text:
        return ""
    match = re.search(r'[\d.]+', text)
    return match.group() if match else ""

# -----------------------------
# 主抓取流程
# -----------------------------
for city in cities:
    print(f"\n開始抓取 {city} ...")
    all_properties = []
    page = 1

    while True:
        url = f"https://www.sinyi.com.tw/buy/list/{city}/default-desc/{page}"
        print(f"正在抓取第 {page} 頁: {url}")
        driver.get(url)

        # 等待房屋列表載入
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.buy-list-item"))
            )
        except:
            print(f"第 {page} 頁載入超時，跳過")
            break

        # 逐步滾動確保 JS 渲染完成
        for _ in range(3):
            driver.execute_script("window.scrollBy(0, document.body.scrollHeight/3);")
            time.sleep(1)

        soup = BeautifulSoup(driver.page_source, 'html.parser')
        property_list = soup.find_all('div', class_='buy-list-item')

        if not property_list:
            print("已經沒有更多房源，結束本城市抓取")
            break

        for item in property_list:
            try:
                # 標題
                title = item.find('div', class_='LongInfoCard_Type_Name').get_text(strip=True)

                # 地址 / 屋齡 / 類型
                address_tag = item.find('div', class_='LongInfoCard_Type_Address')
                spans = address_tag.find_all('span') if address_tag else []
                address = spans[0].get_text(strip=True) if len(spans) > 0 else ''
                age = spans[1].get_text(strip=True) if len(spans) > 1 else ''
                age = "" if age == "--" else age
                house_type = spans[2].get_text(strip=True) if len(spans) > 2 else ''

                # 建坪 / 主+陽 / 格局 / 樓層
                house_info_tag = item.find('div', class_='longInfoCard_LongInfoCard_Type_HouseInfo__tZXDa')
                spans = house_info_tag.find_all('span') if house_info_tag else []

                area = extract_number(spans[0].get_text(strip=True)) if len(spans) > 0 else ""
                Actual_space = extract_number(spans[1].get_text(strip=True)) if len(spans) > 1 else ""
                layout = spans[2].get_text(strip=True) if len(spans) > 2 else ""
                layout = "" if layout == "--" else layout
                floor = spans[3].get_text(strip=True) if len(spans) > 3 else ""
                floor = "" if floor == "--樓/--樓" else floor

                # 車位
                Car_Grip_tag = item.find('span', class_='longInfoCard_LongInfoCard_Type_Parking__ZXl_e')
                Car_Grip = Car_Grip_tag.get_text(strip=True) if Car_Grip_tag and Car_Grip_tag.get_text(strip=True) != '' else '無車位'

                # 總價
                price = ""
                price_block = item.find('div', class_='LongInfoCard_Type_Right')
                if price_block:
                    red_price_span = price_block.find('span', style=lambda s: s and "color: rgb(221, 37, 37)" in s)
                    if red_price_span:
                        price_text = red_price_span.get_text(strip=True)
                        price = extract_number(price_text)

                # 編號
                a_tag = item.find('a', href=True)
                house_id = '無編號'
                if a_tag:
                    match = re.search(r'/buy/house/([A-Za-z0-9]+)', a_tag['href'])
                    if match:
                        house_id = match.group(1)

                all_properties.append({
                    '標題': title,
                    '地址': address,
                    '屋齡': age,
                    '類型': house_type,
                    '建坪': area,
                    '主+陽': Actual_space,
                    '格局': layout,
                    '樓層': floor,
                    '車位': Car_Grip,
                    '總價(萬)': price,
                    '編號': house_id
                })
            except Exception as e:
                print(f"解析錯誤: {e}")
                continue

        page += 1
        # 隨機延遲，避免被封鎖
        time.sleep(random.uniform(1.5, 3.5))

    # 存 CSV
    df = pd.DataFrame(all_properties)
    csv_name = f"./Data/{city}_buy_properties.csv"
    df.to_csv(csv_name, index=False, encoding='utf-8-sig')
    print(f"{city} 共抓取 {len(all_properties)} 筆資料，已存成 {csv_name}")

driver.quit()
print("所有城市抓取完成。")

