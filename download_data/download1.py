# -*- coding: utf-8 -*-
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import pandas as pd
import re
import time

cities = ["Taipei-city", "NewTaipei-city", "Keelung-city", "Yilan-county"]

def setup_driver():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    driver = webdriver.Chrome(options=options)
    return driver

def extract_number(text):
    match = re.search(r'[\d.]+', text) if text else None
    return match.group() if match else ""

def get_text(element, default=""):
    return element.get_text(strip=True) if element else default

def parse_property(item):
    title = get_text(item.find('div', class_='LongInfoCard_Type_Name'))
    
    addr_tag = item.find('div', class_='LongInfoCard_Type_Address')
    spans = addr_tag.find_all('span') if addr_tag else []
    address = get_text(spans[0]) if len(spans) > 0 else ''
    age = get_text(spans[1]) if len(spans) > 1 else ''
    house_type = get_text(spans[2]) if len(spans) > 2 else ''
    
    info_tag = item.find('div', class_='longInfoCard_LongInfoCard_Type_HouseInfo__tZXDa')
    spans = info_tag.find_all('span') if info_tag else []
    area = extract_number(get_text(spans[0])) if len(spans) > 0 else ""
    actual_space = extract_number(get_text(spans[1])) if len(spans) > 1 else ""
    layout = get_text(spans[2]) if len(spans) > 2 else ""
    floor = get_text(spans[3]) if len(spans) > 3 else ""
    
    car = get_text(item.find('span', class_='longInfoCard_LongInfoCard_Type_Parking__ZXl_e'), '無車位')
    
    price = ""
    price_block = item.find('div', class_='LongInfoCard_Type_Right')
    if price_block:
        red_span = price_block.find('span', style=lambda s: s and "color: rgb(221, 37, 37)" in s)
        if red_span:
            price = extract_number(get_text(red_span))
    
    house_id = '無編號'
    a_tag = item.find('a', href=True)
    if a_tag:
        match = re.search(r'/buy/house/([A-Za-z0-9]+)', a_tag['href'])
        if match:
            house_id = match.group(1)
    
    return {
        '標題': title, '地址': address, '屋齡': age, '類型': house_type,
        '建坪': area, '主+陽': actual_space, '格局': layout, '樓層': floor,
        '車位': car, '總價(萬)': price, '編號': house_id
    }

def scrape_city(driver, city):
    all_properties = []
    page = 1
    
    while True:
        url = f"https://www.sinyi.com.tw/buy/list/{city}/default-desc/{page}"
        print(f"抓取 {city} 第 {page} 頁")
        
        try:
            driver.get(url)
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.buy-list-item"))
            )
            time.sleep(2)
            
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            items = soup.find_all('div', class_='buy-list-item')
            
            if not items:
                break
            
            for item in items:
                try:
                    all_properties.append(parse_property(item))
                except:
                    continue
            
            print(f"第 {page} 頁: {len(items)} 筆")
            page += 1
            time.sleep(2)
            
        except:
            break
    
    return all_properties

def main():
    driver = setup_driver()
    
    for city in cities:
        print(f"\n=== {city} ===")
        properties = scrape_city(driver, city)
        
        if properties:
            df = pd.DataFrame(properties)
            df.to_csv(f"{city}_properties.csv", index=False, encoding='utf-8-sig')
            print(f"完成: {len(properties)} 筆")
    
    driver.quit()

if __name__ == "__main__":
    main()
