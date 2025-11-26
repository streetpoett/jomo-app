from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.database.models import Base

# SQLite database file path.
# In a production environment, this should come from environment variables (e.g., PostgreSQL URL).
SQLALCHEMY_DATABASE_URL = "sqlite:///./city_oasis.db"

# Create the SQLAlchemy engine.
# "check_same_thread": False is required for SQLite when used with FastAPI,
# because FastAPI handles requests in multiple threads.
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)

# Create a session factory.
# Each instance of SessionLocal will be a database session.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    """
    Initializes the database by creating all tables defined in the models.
    
    This function should be called when the application starts to ensure
    the schema exists in the database file.
    """
    Base.metadata.create_all(bind=engine)
    print("✅ Database and tables created successfully! (city_oasis.db)")

def get_db():
    """
    Dependency generator that creates a new database session for a request
    and closes it after the request is finished.

    Yields:
        Session: A SQLAlchemy database session.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()