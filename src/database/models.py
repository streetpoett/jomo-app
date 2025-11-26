from sqlalchemy import Column, Integer, String, Float, DateTime
from sqlalchemy.orm import declarative_base
from datetime import datetime

# Base class for SQLAlchemy models
Base = declarative_base()

class Restaurant(Base):
    """
    Represents a restaurant entity in the database.
    
    This model stores static information (name, address, location) 
    and dynamic status (crowd level) for venues.
    """
    __tablename__ = "restaurants"  # Database table name

    # --- 1. Identity ---
    id = Column(Integer, primary_key=True, index=True)
    place_id = Column(String, unique=True, index=True)
    """
    Google Maps Place ID. Unique identifier for the location.
    Used for synchronization with Google API.
    """

    # --- 2. Basic Information ---
    name = Column(String, nullable=False)
    address = Column(String)
    rating = Column(Float)
    url = Column(String)
    opening_hours = Column(String)  # Stored as text for MVP, can be JSON later
    type = Column(String, default="other") # cafe, food, work, bar
    booking_url = Column(String, nullable=True)


    # --- 3. Location Data ---
    latitude = Column(Float)
    longitude = Column(Float)

    # --- 4. Real-time Status ---
    crowd_level = Column(Integer, default=0)
    """
    Current crowd density level.
    Range: 0 (Unknown), 1 (Empty) to 5 (Full).
    """

    # --- 5. Metadata ---
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    """Timestamp of the last record update (UTC)."""

    def __repr__(self):
        """
        Returns a string representation of the Restaurant object.
        Useful for debugging in the console.
        """
        return f"<Restaurant(name={self.name}, crowd_level={self.crowd_level})>"
    
