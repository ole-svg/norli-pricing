"""
Norli Pricing Engine — API
"""
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from api import properties, prices, rules, health, economy, publish, jobs, categories, ai_events, events_api, ical_sync, owner_periods

from contextlib import asynccontextmanager
from db.session import engine
from db.models import Base

@asynccontextmanager
async def lifespan(app):
    # Auto-migrate vid varje deploy — skapar nya tabeller, rör ej befintliga
    Base.metadata.create_all(bind=engine)
    yield

app = FastAPI(
    title="Norli Pricing Engine",
    description="Dynamisk prissättningsmotor för Norli Stay AB",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, tags=["Hälsokontroll"])
app.include_router(properties.router, prefix="/properties", tags=["Objekt"])
app.include_router(prices.router, prefix="/prices", tags=["Priser"])
app.include_router(rules.router, prefix="/rules", tags=["Prisregler"])
app.include_router(economy.router, prefix="/economy", tags=["Ekonomi"])
app.include_router(publish.router, prefix="/publish", tags=["Publicering"])
app.include_router(jobs.router, prefix="/jobs", tags=["Jobb"])
app.include_router(categories.router, prefix="/categories", tags=["Kategorier"])
app.include_router(ai_events.router, prefix="/ai/events", tags=["AI Evenemang"])
app.include_router(events_api.router, tags=["Evenemang"])
app.include_router(ical_sync.router, tags=["Bokningar"])
app.include_router(owner_periods.router, tags=["Ägarperioder"])

@app.post("/setup/migrate")
def run_migrate():
    from sqlalchemy import text, inspect
    from db.session import engine
    from db.models import Base
    try:
        # Skapar alla tabeller som inte finns (inkl bookings, cleaning_profiles etc)
        Base.metadata.create_all(bind=engine)
        with engine.connect() as conn:
            inspector = inspect(engine)
            all_tables = inspector.get_table_names()
            if 'properties' not in all_tables:
                return {"status": "ok", "message": "Alla tabeller skapade från scratch"}
            # Rapportera vilka tabeller som finns
            booking_exists = 'bookings' in all_tables
            existing = {col['name'] for col in inspector.get_columns('properties')}
            new_columns = {
                'cleaning_profile_code': "VARCHAR(50) DEFAULT 'default_villa'",
                'max_guests': 'INTEGER DEFAULT 12',
                'rounding_rule': "VARCHAR(20) DEFAULT 'nearest_10'",
                'event_sensitivity': "VARCHAR(10) DEFAULT 'high'",
                'pricing_category_code': "VARCHAR(50) DEFAULT 'STOCKHOLM_URBAN_EVENT'",
                'object_cost_per_booking': 'NUMERIC(10,2) DEFAULT 200',
                'object_cost_per_night': 'NUMERIC(10,2)',
                'object_cost_per_guest': 'NUMERIC(10,2)',
                'cleaning_base_guests': 'INTEGER DEFAULT 8',
                'cleaning_min_hours': 'NUMERIC(4,2) DEFAULT 3.0',
                'cleaning_hours_per_2_guests_above': 'NUMERIC(4,2) DEFAULT 0.5',
                'cleaning_hours_per_2_guests_below': 'NUMERIC(4,2) DEFAULT 0.25',
                'last_minute_enabled': 'BOOLEAN DEFAULT TRUE',
                'last_minute_start_days': 'INTEGER DEFAULT 20',
                'last_minute_max_discount': 'NUMERIC(5,4) DEFAULT 0.20',
                'last_minute_min_price': 'NUMERIC(10,2)',
                'cleaning_fee_per_stay': 'NUMERIC(10,2)',
                'cleaning_fee_short_stay': 'NUMERIC(10,2)',
                'cleaning_fee_short_stay_max_nights': 'INTEGER DEFAULT 2',
                'pet_fee_per_stay': 'NUMERIC(10,2)',
                'extra_guest_fee_per_night': 'NUMERIC(10,2)',
                'extra_guest_fee_trigger': 'INTEGER DEFAULT 8',
                'admin_fee_per_stay': 'NUMERIC(10,2)',
                'local_fee_per_stay': 'NUMERIC(10,2)',
                'linen_fee_per_stay': 'NUMERIC(10,2)',
                'hotel_fee_per_stay': 'NUMERIC(10,2)',
            }
            added = []
            for col_name, col_def in new_columns.items():
                if col_name not in existing:
                    conn.execute(text(f'ALTER TABLE properties ADD COLUMN IF NOT EXISTS {col_name} {col_def}'))
                    added.append(col_name)
            conn.commit()
        return {"status": "ok", "added": added, "tables": all_tables, "bookings_table": booking_exists}
    except Exception as e:
        return {"status": "error", "detail": str(e)}

@app.post("/setup/seed")
def run_seed():
    import subprocess
    env = os.environ.copy()
    result = subprocess.run(
        ["python", "scripts/seed.py"],
        capture_output=True, text=True, cwd="/app",
        env=env
    )
    return {"stdout": result.stdout, "stderr": result.stderr, "returncode": result.returncode}

@app.post("/setup/seed-events")
def run_seed_events():
    import subprocess
    env = os.environ.copy()
    result = subprocess.run(
        ["python", "scripts/seed_events_2026_2027.py"],
        capture_output=True, text=True, cwd="/app",
        env=env
    )
    return {"stdout": result.stdout, "stderr": result.stderr, "returncode": result.returncode}

admin_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "admin")
if os.path.exists(admin_dir):
    app.mount("/admin", StaticFiles(directory=admin_dir, html=True), name="admin")
