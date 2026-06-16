# Deploy trigger v2
"""
Norli Pricing Engine — API
"""
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from api import properties, prices, rules, health, economy, publish, jobs, categories, ai_events, events_api

app = FastAPI(
    title="Norli Pricing Engine",
    description="Dynamisk prissättningsmotor för Norli Stay AB",
    version="1.0.0",
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

@app.get("/setup/env")
def check_env():
    db_url = os.environ.get("DATABASE_URL", "NOT SET")
    pg_host = os.environ.get("PGHOST", "NOT SET")
    pg_url = os.environ.get("PGURL", "NOT SET")
    if "@" in db_url:
        masked = db_url.split("@")[1]
    else:
        masked = db_url
    return {
        "DATABASE_URL_host": masked,
        "PGHOST": pg_host,
        "PGURL": pg_url,
        "all_keys": sorted(os.environ.keys())
    }

@app.post("/setup/migrate")
def run_migrate():
    from sqlalchemy import text, inspect
    from db.session import engine
    from db.models import Base
    try:
        Base.metadata.create_all(bind=engine)
        with engine.connect() as conn:
            inspector = inspect(engine)
            if 'properties' not in inspector.get_table_names():
                return {"status": "ok", "message": "Tabeller skapade"}
            existing = {col['name'] for col in inspector.get_columns('properties')}
            new_columns = {
                'cleaning_profile_code': "VARCHAR(50) DEFAULT 'default_villa'",
                'max_guests': 'INTEGER DEFAULT 12',
                'pricing_category_code': "VARCHAR(50) DEFAULT 'STOCKHOLM_URBAN_EVENT'",
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
        return {"status": "ok", "added": added}
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
