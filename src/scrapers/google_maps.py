import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import logging

# 設定 Log
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GoogleMapsScraper:
    def __init__(self, headless=True):
        self.options = Options()
        
        # --- 關鍵修改：Docker 環境必備的防崩潰參數 ---
        if headless:
            self.options.add_argument("--headless=new") 
        
        self.options.add_argument("--no-sandbox") # Docker 裡必備：停用沙箱
        self.options.add_argument("--disable-dev-shm-usage") # Docker 裡必備：解決共享記憶體不足
        self.options.add_argument("--disable-gpu") # 伺服器沒有 GPU，必須停用
        self.options.add_argument("--window-size=1920,1080")
        self.options.add_argument("--disable-extensions") # 停用擴充功能省資源
        self.options.add_argument("--disable-infobars")
        self.options.add_argument("--remote-debugging-port=9222") # 解決 DevToolsActivePort 錯誤
        
        # 偽裝設定
        self.options.add_argument("--lang=zh-TW")
        self.options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        self.options.add_experimental_option("excludeSwitches", ["enable-automation"])
        
        logger.info("🔧 [Scraper] Initializing Chrome Driver with anti-crash flags...")
        
        try:
            self.driver = webdriver.Chrome(
                service=Service(ChromeDriverManager().install()), 
                options=self.options
            )
            logger.info("✅ [Scraper] Chrome started successfully!")
        except Exception as e:
            logger.error(f"❌ [Scraper] Chrome failed to start: {e}")
            raise e

    def get_crowd_level(self, place_name: str):
        search_url = f"https://www.google.com.tw/maps/search/{place_name}?hl=zh-TW"
        logger.info(f"🔍 [1/3] Searching: {place_name}")
        
        try:
            self.driver.get(search_url)
            wait = WebDriverWait(self.driver, 10)
            
            # 嘗試點擊第一個結果
            try:
                if "/maps/place/" in self.driver.current_url:
                    logger.info("   ✨ Already on detail page")
                else:
                    logger.info("   👆 [2/3] Clicking first result...")
                    first_result = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "a[href*='/maps/place/']")))
                    first_result.click()
                    time.sleep(3)
            except Exception as e: