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


@app.post("/seed")
def seed_database(db: Session = Depends(get_db)):
    """Inject seed data for Taipei/Taichung with Categories."""
    
    if db.query(models.Restaurant).count() > 30:
        return {"status": "skipped", "message": "資料庫已經很豐富了(>30筆)，跳過注入。"}


    initial_data = [
        # --- 台北：信義區 ---
        {"name": "Starbucks 台北 101 35F", "address": "台北市信義區信義路五段7號35樓", "latitude": 25.033964, "longitude": 121.564472, "place_id": "ChIJmQQiTcupQjQRz5yu0p_u4hQ", "rating": 4.3, "crowd_level": 4, "type": "cafe"},
        {"name": "一蘭拉麵 台北本店", "address": "台北市信義區松仁路97號", "latitude": 25.035515, "longitude": 121.568296, "place_id": "ChIJ7Qqq0sypQjQR6s-t5C5q6z4", "rating": 4.7, "crowd_level": 5, "type": "food"},
        {"name": "Louisa Coffee 信義松仁", "address": "台北市信義區松仁路100號", "latitude": 25.036123, "longitude": 121.567123, "place_id": "ChIJ_z8_8cqpQjQR8y5x1j2o1fA", "rating": 4.1, "crowd_level": 2, "type": "cafe"},
        {"name": "蔦屋書店 TSUTAYA BOOKSTORE 信義店", "address": "台北市信義區忠孝東路五段8號", "latitude": 25.039578, "longitude": 121.565893, "place_id": "ChIJL_o_0sypQjQR8s-t5C5q6z4", "rating": 4.5, "crowd_level": 3, "type": "work"},

        # --- 台北：大安/中正區 (適合讀書工作) ---
        {"name": "國家圖書館", "address": "台北市中正區中山南路20號", "latitude": 25.036660, "longitude": 121.517336, "place_id": "ChIJ7z8_8cqpQjQR8y5x1j2o1fB", "rating": 4.6, "crowd_level": 3, "type": "work"},
        {"name": "Notch咖啡工廠 站前店", "address": "台北市中正區信陽街6號", "latitude": 25.044123, "longitude": 121.516123, "place_id": "ChIJ8z8_8cqpQjQR8y5x1j2o1fC", "rating": 4.2, "crowd_level": 4, "type": "cafe"},
        {"name": "Cama Coffee Roasters 豆留森林", "address": "台北市士林區格致路70號", "latitude": 25.134567, "longitude": 121.556789, "place_id": "ChIJ9z8_8cqpQjQR8y5x1j2o1fD", "rating": 4.8, "crowd_level": 2, "type": "cafe"},
        {"name": "森高砂咖啡館", "address": "台北市大同區延平北路二段1號", "latitude": 25.053123, "longitude": 121.511123, "place_id": "ChIJa8-S4oYZaDQR9s5y2j3o1gE", "rating": 4.7, "crowd_level": 1, "type": "cafe"},

        # --- 台北：中山區 (夜貓/酒吧) ---
        {"name": "Bar Mood Taipei 吧沐", "address": "台北市大安區敦化南路一段160巷53號", "latitude": 25.043567, "longitude": 121.546789, "place_id": "ChIJb8-S4oYZaDQR9s5y2j3o1gF", "rating": 4.6, "crowd_level": 4, "type": "bar"},
        {"name": "榕 RON Xinyi", "address": "台北市信義區基隆路二段12號", "latitude": 25.029876, "longitude": 121.557654, "place_id": "ChIJc8-S4oYZaDQR9s5y2j3o1gG", "rating": 4.4, "crowd_level": 3, "type": "bar"},

        # --- 台中：西區/勤美 (文青集散地) ---
        {"name": "Solidbean Coffee Roasters", "address": "台中市西區精誠三街28號", "latitude": 24.156123, "longitude": 120.658123, "place_id": "ChIJlb-S4oYZaDQR9s5y2j3o1gC", "rating": 4.8, "crowd_level": 1, "type": "cafe"},
        {"name": "The Factory Mojocoffee", "address": "台中市西區精誠六街22號", "latitude": 24.155432, "longitude": 120.657543, "place_id": "ChIJd8-S4oYZaDQR9s5y2j3o1gH", "rating": 4.5, "crowd_level": 2, "type": "cafe"},
        {"name": "勤美 誠品綠園道", "address": "台中市西區公益路68號", "latitude": 24.151123, "longitude": 120.663123, "place_id": "ChIJe8-S4oYZaDQR9s5y2j3o1gI", "rating": 4.4, "crowd_level": 5, "type": "work"},
        
        # --- 台中：中區/北區 ---
        {"name": "宮原眼科", "address": "台中市中區中山路20號", "latitude": 24.137512, "longitude": 120.683456, "place_id": "ChIJkb-S4oYZaDQR8s5y2j3o1gB", "rating": 4.6, "crowd_level": 5, "type": "food"},
        {"name": "屋馬燒肉 中港店", "address": "台中市西屯區台灣大道三段300號", "latitude": 24.165432, "longitude": 120.649876, "place_id": "ChIJf8-S4oYZaDQR9s5y2j3o1gJ", "rating": 4.9, "crowd_level": 5, "type": "food"},
        {"name": "茶六燒肉堂 朝富店", "address": "台中市西屯區朝富路258號", "latitude": 24.168765, "longitude": 120.638765, "place_id": "ChIJg8-S4oYZaDQR9s5y2j3o1gK", "rating": 4.8, "crowd_level": 5, "type": "food"},
        {"name": "中央書局", "address": "台中市中區台灣大道一段235號", "latitude": 24.142345, "longitude": 120.679876, "place_id": "ChIJh8-S4oYZaDQR9s5y2j3o1gL", "rating": 4.7, "crowd_level": 1, "type": "work"}
    ]

    try:
        count = 0
        for item in initial_data:
            exists = db.query(models.Restaurant).filter(models.Restaurant.place_id == item["place_id"]).first()
            if not exists:
                new_restaurant = models.Restaurant(
                    name=item["name"],
                    address=item["address"],
                    latitude=item["latitude"],
                    longitude=item["longitude"],
                    place_id=item["place_id"],
                    rating=item["rating"],
                    crowd_level=item["crowd_level"],
                    updated_at=datetime.utcnow(),

                    type=item.get("type", "other")
                )
                db.add(new_restaurant)
                count += 1
        db.commit()
        return {"status": "success", "message": f"成功注入 {count} 筆新地點！"}
    except Exception as e:
        db.rollback()
        return {"status": "error", "message": str(e)}
    



@app.on_event("shutdown")
def on_shutdown():
    try:
        scheduler.shutdown()
    except Exception:
        pass
    logger.info("🛑 Scheduler shut down.")