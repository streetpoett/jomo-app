import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup

class GoogleMapsScraper:
    def __init__(self, headless=True):    # Debug : False
        self.options = Options()
     
        if headless:
            self.options.add_argument("--headless=new") 
        
        self.options.add_argument("--window-size=1920,1080")
        self.options.add_argument("--lang=zh-TW")
        self.options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        self.options.add_experimental_option("excludeSwitches", ["enable-automation"])
        
        self.driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()), 
            options=self.options
        )

    def get_crowd_level(self, place_name: str):
        search_url = f"https://www.google.com.tw/maps/search/{place_name}?hl=zh-TW"
        print(f"🔍 [1/3] 搜尋地點: {place_name}")
        
        try:
            self.driver.get(search_url)
            
            # click and wait
            wait = WebDriverWait(self.driver, 10)
            
            try:
                if "/maps/place/" in self.driver.current_url:
                    print("    直接命中詳情頁，無需點擊")
                else:
                    print("    [2/3] 找到搜尋列表，正在點擊第一個結果...")
                  
                    first_result = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "a[href*='/maps/place/']")))
                    first_result.click()
                    time.sleep(3)
            except Exception as e:
                print(f"   ⚠️ 點擊失敗 (可能只有唯一結果已自動展開): {e}")

        
            time.sleep(5)
            
            print("   👀 [3/3] 分析詳情頁數據...")
            page_source = self.driver.page_source
            full_text = self.driver.find_element(By.TAG_NAME, "body").text
            
            if "即時" in full_text:
                print("   🎯 抓到【即時】數據！")
                if "不如平常繁忙" in full_text: return 2
                if "不太忙" in full_text: return 2
                if "人潮不多" in full_text: return 1
                if "略微繁忙" in full_text: return 3
                if "有點忙" in full_text: return 3
                if "比平常繁忙" in full_text: return 4
                if "很忙" in full_text: return 5
                if "繁忙" in full_text: return 4
                return 3 
            
            # backup
            if "通常" in full_text and "忙" in full_text:
                print("   ⚠️ 僅有歷史數據 (通常...)")
                if "通常不太忙" in full_text: return 2
                if "通常有點忙" in full_text: return 3
                if "通常很忙" in full_text: return 5
                return 3

            print("   ⚠️ 無法人潮數據 (可能該店現在已打烊或無資料)")
            return 0

        except Exception as e:
            print(f"   ❌ 發生錯誤: {e}")
            return 0

    def close(self):
        self.driver.quit()

if __name__ == "__main__":
    target_place = "台北車站" 
    # target_place = "IKEA 新店店" 
    
    scraper = GoogleMapsScraper(headless=False) # Debug : False
    try:
        level = scraper.get_crowd_level(target_place)
        print(f"📊 最終結果: Level {level}")
    finally:
        scraper.close()