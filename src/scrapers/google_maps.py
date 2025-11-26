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

# Log Setting
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GoogleMapsScraper:
    def __init__(self, headless=True):
        self.options = Options()
        
        # --- Docker envioriment parameter ---
        if headless:
            self.options.add_argument("--headless=new") 
        
        self.options.add_argument("--no-sandbox") 
        self.options.add_argument("--disable-dev-shm-usage") 
        self.options.add_argument("--disable-gpu") 
        self.options.add_argument("--window-size=1920,1080")
        self.options.add_argument("--disable-extensions")
        self.options.add_argument("--disable-infobars")
        self.options.add_argument("--remote-debugging-port=9222")
        
   
        self.options.add_argument("--lang=zh-TW")
        self.options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        self.options.add_experimental_option("excludeSwitches", ["enable-automation"])
        
        logger.info("🔧 [Scraper] Initializing Chrome Driver...")
        
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
            
            try:
                if "/maps/place/" in self.driver.current_url:
                    logger.info("   ✨ Already on detail page")
                else:
                    logger.info("   👆 [2/3] Clicking first result...")
                    first_result = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "a[href*='/maps/place/']")))
                    first_result.click()
                    time.sleep(3)
            except Exception as e:
                logger.warning(f"   ⚠️ Click skipped or failed: {e}")

            time.sleep(5)
            logger.info("   👀 [3/3] Analyzing page...")
            
            full_text = self.driver.find_element(By.TAG_NAME, "body").text
            
            if "即時" in full_text:
                logger.info("   🎯 Live data found!")
                if "不如平常繁忙" in full_text or "不太忙" in full_text or "人潮不多" in full_text: return 2
                if "略微繁忙" in full_text or "有點忙" in full_text: return 3
                if "比平常繁忙" in full_text or "很忙" in full_text or "繁忙" in full_text: return 4
                return 3
            
            if "通常" in full_text and "忙" in full_text:
                logger.info("   ⚠️ Historical data only")
                if "通常不太忙" in full_text: return 2
                if "通常有點忙" in full_text: return 3
                if "通常很忙" in full_text: return 5
                return 3

            logger.info("   ⚠️ No data found")
            return 0

        except Exception as e:
            logger.error(f"   ❌ Scraping error: {e}")
            return 0

    def close(self):
        if hasattr(self, 'driver'):
            self.driver.quit()

if __name__ == "__main__":
    scraper = GoogleMapsScraper(headless=False)
    scraper.close()