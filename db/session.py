"""
Databasanslutning för Norli Pricing Engine.

SQLAlchemy hanterar kopplingen till PostgreSQL.
Vi använder 'session' som ett sätt att prata med databasen —
tänk på det som en transaktion: öppna, gör saker, stäng.
"""

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

# Läs databasadressen från miljövariabeln DATABASE_URL
# Format: postgresql://användare:lösenord@host:port/databasnamn
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://norli:norli_dev@localhost:5432/norli_pricing")
# Railway använder postgres:// men SQLAlchemy kräver postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Skapa "motorn" — SQLAlchemys anslutningshanterare
engine = create_engine(
    DATABASE_URL,
    echo=False,  # Sätt till True för att se SQL-queries i terminalen (bra vid debugging)
)

# SessionLocal är en fabrik för databassessioner
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Session:
    """
    Dependency för FastAPI — ger en databassession per request.

    Används så här i API-endpoints:
        def my_endpoint(db: Session = Depends(get_db)):
            ...

    'with'-blocket garanterar att sessionen alltid stängs,
    även om något går fel.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
