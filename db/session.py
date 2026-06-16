import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

def get_database_url():
    url = os.environ.get("DATABASE_URL", "postgresql://norli:norli_dev@localhost:5432/norli_pricing")
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return url

def get_engine():
    return create_engine(get_database_url(), echo=False, pool_pre_ping=True)

engine = get_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
