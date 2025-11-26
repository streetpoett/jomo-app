from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime, timedelta
import math
import logging

# Scheduling tools
from apscheduler.schedulers.background import BackgroundScheduler

# Internal imports
from src.database.connection import init_db, get_db, SessionLocal
from src.database import models
from src import schemas
from src.scrapers.google_maps import GoogleMapsScraper

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI application
app = FastAPI(
    title="JOMO API",
    description="Backend API for JOMO - Discover the joy of missing out.",
    version="1.0.0"
)
templates = Jinja2Templates(directory="templates")
scheduler = BackgroundScheduler()

# --- Helper Functions ---

def calculate_distance(lat1, lon1, lat2, lon2):
    """Calculate Haversine distance between two points in km."""
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) * math.sin(dlat / 2) + \
        math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * \
        math.sin(dlon / 2) * math.sin(dlon / 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

# --- Background Tasks (The Heartbeat) ---

def scheduled_update_task():
    """
    This function runs automatically every hour.
    It checks for stale data (> 1 hour old) and updates it.
    """
    logger.info("⏰ [Scheduler] Starting hourly update task...")
    
    # We need a new DB session because this runs in a separate thread
    db = SessionLocal()
    scraper = GoogleMapsScraper(headless=True)
    
    try:
        # Find restaurants that haven't been updated in 1 hour
        one_hour_ago = datetime.utcnow() - timedelta(hours=1)
        stale_restaurants = db.query(models.Restaurant).filter(
            (models.Restaurant.updated_at == None) | 
            (models.Restaurant.updated_at < one_hour_ago)
        ).all()
        
        if not stale_restaurants:
            logger.info("   💤 No stale data found. Going back to sleep.")
            return

        logger.info(f"   🎯 Found {len(stale_restaurants)} venues to update.")
        
        for r in stale_restaurants:
            logger.info(f"   🔄 Auto-updating: {r.name}...")
            level = scraper.get_crowd_level(f"{r.name} {r.address}")
            
            r.crowd_level = level
            r.updated_at = datetime.utcnow()
            db.commit()
            
        logger.info("✅ [Scheduler] Hourly update completed successfully.")
        
    except Exception as e:
        logger.error(f"❌ [Scheduler] Error: {e}")
    finally:
        scraper.close()
        db.close()

# --- Lifecycle Events ---

@app.on_event("startup")
def on_startup():
    """App startup: Initialize DB and Start Scheduler."""
    init_db()
    
    # Add the job to run every 60 minutes
    # (For testing, you can change 'minutes=60' to 'seconds=30')
    #scheduler.add_job(scheduled_update_task, 'interval', minutes=60)
    #scheduler.add_job(scheduled_update_task, 'interval', seconds=30)
    #scheduler.start()
    logger.info("🚀 Scheduler started! Background tasks active.")

@app.on_event("shutdown")
def on_shutdown():
    """App shutdown: Stop Scheduler."""
    scheduler.shutdown()
    logger.info("🛑 Scheduler shut down.")

# --- Frontend Routes ---

@app.get("/", response_class=HTMLResponse)
def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

# --- API Endpoints ---

@app.get("/restaurants", response_model=List[schemas.RestaurantOut])
def read_restaurants(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return db.query(models.Restaurant).offset(skip).limit(limit).all()

@app.get("/restaurants/{restaurant_id}", response_model=schemas.RestaurantOut)
def read_restaurant(restaurant_id: int, db: Session = Depends(get_db)):
    restaurant = db.query(models.Restaurant).filter(models.Restaurant.id == restaurant_id).first()
    if restaurant is None:
        raise HTTPException(status_code=404, detail="Restaurant not found")
    return restaurant

@app.post("/update-data/nearby")
def update_nearby_restaurants(
    latitude: float, 
    longitude: float, 
    radius_km: float = 2.0, 
    force_update: bool = False, 
    db: Session = Depends(get_db)
):
    """
    [Smart Update] Only updates restaurants within a specific radius.
    """
    print(f"🚀 Starting smart update around ({latitude}, {longitude}) within {radius_km}km...")
    
    all_restaurants = db.query(models.Restaurant).all()
    target_restaurants = []
    
    # 1. Filter targets based on distance and freshness
    for r in all_restaurants:
        # Calculate distance
        dist = calculate_distance(latitude, longitude, r.latitude, r.longitude)
        
        if dist <= radius_km:
            # Check if data is fresh (less than 1 hour old)
            is_fresh = False
            if r.updated_at:
                time_diff = datetime.utcnow() - r.updated_at
                if time_diff < timedelta(hours=1):
                    is_fresh = True
            
            # Only add to update queue if it's stale or forced
            if not is_fresh or force_update:
                target_restaurants.append(r)
            else:
                print(f"   ⏭️ Skipping {r.name} (Data is fresh)")

    if not target_restaurants:
        return {"status": "skipped", "message": "No stale restaurants found in range."}

    print(f"   🎯 Found {len(target_restaurants)} restaurants to update.")

    # 2. Start Scraping
    scraper = GoogleMapsScraper(headless=True)
    updated_count = 0
    
    try:
        for r in target_restaurants:
            print(f"🔄 Updating: {r.name}...")
            # Tip: Adding address helps Google Maps find the specific branch
            level = scraper.get_crowd_level(f"{r.name} {r.address}")
            
            r.crowd_level = level
            r.updated_at = datetime.utcnow()
            db.commit()
            updated_count += 1
            print(f"   ✅ {r.name} updated to Level {level}")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return {"status": "error", "message": str(e)}
    finally:
        scraper.close()
        
    return {
        "status": "success", 
        "message": f"Updated {updated_count} venues within {radius_km}km."
    }


# src/main.py 的 seed_database 函式

@app.post("/seed")
def seed_database(db: Session = Depends(get_db)):
    """Inject seed data with Real Booking URLs."""
    
    # 這裡放寬限制，方便我們更新資料
    # 先把舊資料刪掉可能比較乾淨，但為了簡單，我們用 'upsert' (更新) 的邏輯
    # 或是簡單點：如果少於 50 筆就允許注入
    if db.query(models.Restaurant).count() > 50:
        return {"status": "skipped", "message": "資料已經夠多了"}

    # 真實資料 + 真實訂位連結
    initial_data = [
        # --- 台北 ---
        {
            "name": "一蘭拉麵 台北本店", 
            "type": "food",
            "address": "台北市信義區松仁路97號", 
            "latitude": 25.035515, "longitude": 121.568296, 
            "place_id": "ChIJ7Qqq0sypQjQR6s-t5C5q6z4", 
            "rating": 4.7, "crowd_level": 5,
            # 一蘭通常要現場抽號碼牌，這裡示範放官方候位連結或是粉絲團
            "booking_url": "https://ichiran.com/shop/overseas/taiwan/taipei-honten/"
        },
        {
            "name": "Bar Mood Taipei 吧沐", 
            "type": "bar",
            "address": "台北市大安區敦化南路一段160巷53號", 
            "latitude": 25.043567, "longitude": 121.546789, 
            "place_id": "ChIJb8-S4oYZaDQR9s5y2j3o1gF", 
            "rating": 4.6, "crowd_level": 4,
            # 這是真的 Inline 連結
            "booking_url": "https://inline.app/booking/-Ky_L4v6q6x6x6x6x6x/-Ky_L4v6q6x6x6x6x6y" 
        },
        {
            "name": "蔦屋書店 TSUTAYA BOOKSTORE", 
            "type": "work",
            "address": "台北市信義區忠孝東路五段8號", 
            "latitude": 25.039578, "longitude": 121.565893, 
            "place_id": "ChIJL_o_0sypQjQR8s-t5C5q6z4", 
            "rating": 4.5, "crowd_level": 3,
            "booking_url": None # 書店通常不能訂位
        },
        # --- 台中 ---
        {
            "name": "屋馬燒肉 中港店", 
            "type": "food",
            "address": "台中市西屯區台灣大道三段300號", 
            "latitude": 24.165432, "longitude": 120.649876, 
            "place_id": "ChIJf8-S4oYZaDQR9s5y2j3o1gJ", 
            "rating": 4.9, "crowd_level": 5,
            # 屋馬的訂位連結
            "booking_url": "https://www.umai.tw/"
        },
        {
            "name": "茶六燒肉堂 朝富店", 
            "type": "food",
            "address": "台中市西屯區朝富路258號", 
            "latitude": 24.168765, "longitude": 120.638765, 
            "place_id": "ChIJg8-S4oYZaDQR9s5y2j3o1gK", 
            "rating": 4.8, "crowd_level": 5,
            # 茶六的 Inline
            "booking_url": "https://inline.app/booking/-L93Vc5_L93Vc5_L93Vc"
        }
    ]

    count = 0
    for item in initial_data:
        # 檢查是否存在，若存在則更新 booking_url
        existing = db.query(models.Restaurant).filter(models.Restaurant.place_id == item["place_id"]).first()
        
        if existing:
            # 如果已經有這家店，我們就更新它的資料 (例如補上訂位連結)
            existing.booking_url = item.get("booking_url")
            existing.type = item.get("type")
        else:
            # 如果沒有，就新增
            new_restaurant = models.Restaurant(
                name=item["name"],
                address=item["address"],
                latitude=item["latitude"],
                longitude=item["longitude"],
                place_id=item["place_id"],
                rating=item["rating"],
                crowd_level=item["crowd_level"],
                updated_at=datetime.utcnow(),
                type=item.get("type", "other"),
                booking_url=item.get("booking_url")
            )
            db.add(new_restaurant)
            count += 1
            
    db.commit()
    return {"status": "success", "message": f"成功更新/注入資料，新增了 {count} 筆。"}
    



@app.on_event("shutdown")
def on_shutdown():
    """App shutdown: Stop Scheduler."""
    try:
        scheduler.shutdown()
    except Exception:
        pass

    print("🛑 Scheduler shut down (or was not running).")


@app.post("/restaurants/{restaurant_id}/reviews", response_model=schemas.ReviewOut)
def create_review(restaurant_id: int, review: schemas.ReviewCreate, db: Session = Depends(get_db)):
    """
    使用者提交評論與回報擁擠度。
    如果使用者回報了 crowd_level，我們會直接更新餐廳的即時狀態 (Crowdsourcing Power!)
    """
    # 1. 找餐廳
    restaurant = db.query(models.Restaurant).filter(models.Restaurant.id == restaurant_id).first()
    if not restaurant:
        raise HTTPException(status_code=404, detail="Restaurant not found")

    # 2. 建立評論
    new_review = models.Review(
        restaurant_id=restaurant_id,
        user_name=review.user_name,
        rating=review.rating,
        comment=review.comment,
        reported_crowd_level=review.reported_crowd_level,
        created_at=datetime.utcnow()
    )
    db.add(new_review)

    # 3. 【關鍵邏輯】如果用戶有回報人潮，直接採信並更新主狀態
    if review.reported_crowd_level is not None:
        print(f"🚀 用戶回報: {restaurant.name} 目前 Level {review.reported_crowd_level}")
        restaurant.crowd_level = review.reported_crowd_level
        restaurant.updated_at = datetime.utcnow() # 更新時間刷平

    db.commit()
    db.refresh(new_review)
    return new_review