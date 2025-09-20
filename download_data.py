# -*- coding: utf-8 -*-
import logging
import subprocess
import os
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import TimeoutException, WebDriverException
from bs4 import BeautifulSoup
import pandas as pd
import re
import time
import random
from datetime import datetime

# 設定日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('scraper.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 目標城市列表
cities = [
    "Taipei-city", "NewTaipei-city", "Keelung-city", "Yilan-county",
    "Hsinchu-city", "Hsinchu-county", "Taoyuan-city", "Miaoli-county",
    "Taichung-city", "Changhua-county", "Nantou-county", "Yunlin-county",
    "Chiayi-city", "Chiayi-county", "Tainan-city", "Kaohsiung-city",
    "Pingtung-county", "Penghu-county", "Taitung-county", "Hualien-county",
    "Kinmen-county", "Lienchiang-county"
]

class IncrementalPropertyScraper:
    def __init__(self):
        self.driver = None
        self.setup_driver()
    
    def setup_driver(self):
        """設定 Chrome driver"""
        options = Options()
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ]
        options.add_argument(f"--user-agent={random.choice(user_agents)}")
        
        try:
            self.driver = webdriver.Chrome(
                service=Service(ChromeDriverManager().install()), 
                options=options
            )
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            logger.info("Chrome driver 初始化成功")
        except Exception as e:
            logger.error(f"Chrome driver 初始化失敗: {e}")
            raise

    def extract_number(self, text):
        """安全提取數字"""
        if not text:
            return ""
        match = re.search(r'[\d.]+', text)
        return match.group() if match else ""

    def safe_get_text(self, element, default=""):
        """安全提取文字"""
        try:
            return element.get_text(strip=True) if element else default
        except:
            return default

    def git_commit_city(self, city):
        """提交特定城市的資料到 Git"""
        try:
            csv_file = f"./Data/{city}_buy_properties.csv"
            if not os.path.exists(csv_file):
                logger.warning(f"{city} 的 CSV 檔案不存在，跳過提交")
                return False
            
            # 設定 Git 用戶資訊
            subprocess.run(['git', 'config', 'user.name', 'github-actions[bot]'], check=True)
            subprocess.run(['git', 'config', 'user.email', '41898282+github-actions[bot]@users.noreply.github.com'], check=True)
            
            # 檢查檔案大小
            file_size = os.path.getsize(csv_file) / (1024 * 1024)  # MB
            logger.info(f"{city} 檔案大小: {file_size:.2f} MB")
            
            # 加入檔案到 Git
            subprocess.run(['git', 'add', csv_file], check=True)
            
            # 檢查是否有變更
            result = subprocess.run(['git', 'diff', '--cached', '--quiet'], capture_output=True)
            if result.returncode == 0:
                logger.info(f"{city} 沒有變更，跳過提交")
                return False
            
            # 提交
            commit_message = f"Auto update {city} data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}"
            subprocess.run(['git', 'commit', '-m', commit_message], check=True)
            
            # 推送 (嘗試 main 和 master)
            try:
                subprocess.run(['git', 'push', 'origin', 'main'], check=True, timeout=60)
                logger.info(f"{city} 資料已成功推送到 main 分支")
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
                try:
                    subprocess.run(['git', 'push', 'origin', 'master'], check=True, timeout=60)
                    logger.info(f"{city} 資料已成功推送到 master 分支")
                except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
                    logger.error(f"{city} 推送失敗: {e}")
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Git 操作失敗 ({city}): {e}")
            return False

    def scrape_city(self, city):
        """爬取特定城市的房產資料"""
        logger.info(f"開始抓取 {city}")
        all_properties = []
        page = 1
        consecutive_failures = 0
        
        while consecutive_failures < 3:
            url = f"https://www.sinyi.com.tw/buy/list/{city}/default-desc/{page}"
            logger.info(f"正在抓取第 {page} 頁: {url}")
            
            try:
                self.driver.get(url)
                
                WebDriverWait(self.driver, 15).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "div.buy-list-item"))
                )
                
                for i in range(3):
                    self.driver.execute_script("window.scrollBy(0, document.body.scrollHeight/3);")
                    time.sleep(random.uniform(0.5, 1.5))
                
                soup = BeautifulSoup(self.driver.page_source, 'html.parser')
                property_list = soup.find_all('div', class_='buy-list-item')
                
                if not property_list:
                    logger.info(f"{city} 第 {page} 頁沒有找到房源，結束抓取")
                    break
                
                page_properties = self.parse_properties(property_list)
                all_properties.extend(page_properties)
                
                logger.info(f"第 {page} 頁成功抓取 {len(page_properties)} 筆資料")
                consecutive_failures = 0
                page += 1
                
                time.sleep(random.uniform(2, 4))
                
            except TimeoutException:
                logger.warning(f"{city} 第 {page} 頁載入超時")
                consecutive_failures += 1
                time.sleep(random.uniform(3, 6))
            except Exception as e:
                logger.error(f"{city} 第 {page} 頁抓取錯誤: {e}")
                consecutive_failures += 1
                time.sleep(random.uniform(3, 6))
        
        return all_properties

    def parse_properties(self, property_list):
        """解析房產列表"""
        properties = []
        
        for item in property_list:
            try:
                property_data = self.parse_single_property(item)
                if property_data:
                    properties.append(property_data)
            except Exception as e:
                logger.warning(f"解析單筆房產資料時出錯: {e}")
                continue
        
        return properties

    def parse_single_property(self, item):
        """解析單筆房產資料"""
        try:
            title_element = item.find('div', class_='LongInfoCard_Type_Name')
            title = self.safe_get_text(title_element)
            
            address_tag = item.find('div', class_='LongInfoCard_Type_Address')
            spans = address_tag.find_all('span') if address_tag else []
            
            address = self.safe_get_text(spans[0]) if len(spans) > 0 else ''
            age = self.safe_get_text(spans[1]) if len(spans) > 1 else ''
            age = "" if age == "--" else age
            house_type = self.safe_get_text(spans[2]) if len(spans) > 2 else ''
            
            house_info_tag = item.find('div', class_='longInfoCard_LongInfoCard_Type_HouseInfo__tZXDa')
            spans = house_info_tag.find_all('span') if house_info_tag else []
            
            area = self.extract_number(self.safe_get_text(spans[0])) if len(spans) > 0 else ""
            actual_space = self.extract_number(self.safe_get_text(spans[1])) if len(spans) > 1 else ""
            layout = self.safe_get_text(spans[2]) if len(spans) > 2 else ""
            layout = "" if layout == "--" else layout
            floor = self.safe_get_text(spans[3]) if len(spans) > 3 else ""
            floor = "" if floor == "--樓/--樓" else floor
            
            car_grip_tag = item.find('span', class_='longInfoCard_LongInfoCard_Type_Parking__ZXl_e')
            car_grip = self.safe_get_text(car_grip_tag, '無車位') if car_grip_tag and self.safe_get_text(car_grip_tag) != '' else '無車位'
            
            price = ""
            price_block = item.find('div', class_='LongInfoCard_Type_Right')
            if price_block:
                red_price_span = price_block.find('span', style=lambda s: s and "color: rgb(221, 37, 37)" in s)
                if red_price_span:
                    price_text = self.safe_get_text(red_price_span)
                    price = self.extract_number(price_text)
            
            a_tag = item.find('a', href=True)
            house_id = '無編號'
            if a_tag:
                match = re.search(r'/buy/house/([A-Za-z0-9]+)', a_tag['href'])
                if match:
                    house_id = match.group(1)
            
            return {
                '標題': title,
                '地址': address,
                '屋齡': age,
                '類型': house_type,
                '建坪': area,
                '主+陽': actual_space,
                '格局': layout,
                '樓層': floor,
                '車位': car_grip,
                '總價(萬)': price,
                '編號': house_id,
                '抓取時間': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
        except Exception as e:
            logger.error(f"解析房產資料時出錯: {e}")
            return None

    def save_data(self, city, properties):
        """儲存資料到 CSV"""
        if not properties:
            logger.warning(f"{city} 沒有資料可儲存")
            return False
        
        os.makedirs("./Data", exist_ok=True)
        df = pd.DataFrame(properties)
        csv_name = f"./Data/{city}_buy_properties.csv"
        
        try:
            df.to_csv(csv_name, index=False, encoding='utf-8-sig')
            file_size = os.path.getsize(csv_name) / (1024 * 1024)
            logger.info(f"{city} 共抓取 {len(properties)} 筆資料，已存成 {csv_name}")
            logger.info(f"檔案大小: {file_size:.2f} MB")
            return True
        except Exception as e:
            logger.error(f"儲存 {city} 資料時出錯: {e}")
            return False

    def run(self):
        """執行爬蟲 - 每個城市完成後立即提交"""
        logger.info("開始執行房產資料爬蟲 (逐城市提交模式)")
        
        # 檢查是否指定單一城市
        single_city = os.environ.get('SINGLE_CITY', '').strip()
        if single_city:
            target_cities = [single_city] if single_city in cities else []
            if not target_cities:
                logger.error(f"指定的城市 '{single_city}' 不在支援列表中")
                return
        else:
            target_cities = cities
        
        successful_cities = []
        failed_cities = []
        
        for city in target_cities:
            try:
                logger.info(f"=== 開始處理 {city} ({target_cities.index(city) + 1}/{len(target_cities)}) ===")
                
                # 抓取資料
                properties = self.scrape_city(city)
                
                # 儲存資料
                if self.save_data(city, properties):
                    # 立即提交到 Git
                    if self.git_commit_city(city):
                        successful_cities.append(city)
                        logger.info(f"✓ {city} 完成並已推送")
                    else:
                        failed_cities.append(city)
                        logger.warning(f"✗ {city} 抓取成功但推送失敗")
                else:
                    failed_cities.append(city)
                    logger.error(f"✗ {city} 儲存失敗")
                
                # 城市間休息
                if city != target_cities[-1]:  # 不是最後一個城市
                    rest_time = random.uniform(10, 20)
                    logger.info(f"休息 {rest_time:.1f} 秒後繼續下一個城市...")
                    time.sleep(rest_time)
                
            except Exception as e:
                logger.error(f"處理 {city} 時發生錯誤: {e}")
                failed_cities.append(city)
                continue
        
        # 最終報告
        logger.info("=== 執行完成報告 ===")
        logger.info(f"成功: {len(successful_cities)} 個城市")
        logger.info(f"失敗: {len(failed_cities)} 個城市")
        if successful_cities:
            logger.info(f"成功城市: {', '.join(successful_cities)}")
        if failed_cities:
            logger.info(f"失敗城市: {', '.join(failed_cities)}")
        
        self.cleanup()

    def cleanup(self):
        """清理資源"""
        if self.driver:
            self.driver.quit()
            logger.info("Chrome driver 已關閉")

if __name__ == "__main__":
    scraper = IncrementalPropertyScraper()
    try:
        scraper.run()
    except KeyboardInterrupt:
        logger.info("程式被使用者中斷")
        scraper.cleanup()
    except Exception as e:
        logger.error(f"程式執行出錯: {e}")
        scraper.cleanup()
        raise
