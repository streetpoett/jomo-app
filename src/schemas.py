from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional

# define structure 
class RestaurantBase(BaseModel):
    name: str
    address: Optional[str] = None
    rating: Optional[float] = None
    url: Optional[str] = None
    opening_hours: Optional[str] = None
    latitude: float
    longitude: float
    crowd_level: int = 0
    type: Optional[str] = "other"

class ReviewBase(BaseModel):
    user_name: str = "匿名綠洲客"
    rating: int
    comment: Optional[str] = None
    reported_crowd_level: Optional[int] = None    

class ReviewCreate(ReviewBase):
    pass

class ReviewOut(ReviewBase):
    id: int
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)
# create necessnary structure
class RestaurantCreate(RestaurantBase):
    place_id: str

# output to front-end(ID, Config)
class RestaurantOut(RestaurantBase):
    id: int
    place_id: str
    updated_at: Optional[datetime] = None
    reviews: List[ReviewOut] = []
    
    model_config = ConfigDict(from_attributes=True)

    class Config:
        from_attributes = True 
        orm_mode = True        