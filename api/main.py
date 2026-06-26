"""
Norli Pricing Engine — API
"""
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from api import properties, prices, rules, health, economy, publish, jobs, categories, ai_events, events_api, ical_sync, airbnb_prices, beds24_api, owner_periods, cleaning_state, guest_import

from contextlib import asynccontextmanager
from db.session import engine
from db.models import Base

@asynccontextmanager
async def lifespan(app):
    # Auto-migrate vid varje deploy — skapar nya tabeller, rör ej befintliga
    try:
        Base.metadata.create_all(bind=engine)
        print("✓ DB-tabeller verifierade vid startup")
    except Exception as e:
        print(f"⚠ DB-migrate vid startup misslyckades (icke-kritiskt): {e}")
    try:
        from sqlalchemy import text
        with engine.connect() as conn:
            for table, col, typ in [
                ("cleaning_job_state", "outgoing_guests", "INTEGER"),
                ("cleaning_job_state", "bedding_for_guests", "INTEGER"),
                ("bookings", "num_adults", "INTEGER"),
                ("bookings", "num_children", "INTEGER"),
                ("bookings", "num_infants", "INTEGER"),
                ("bookings", "confirmation_code", "VARCHAR(50)"),
                ("properties", "airbnb_listing_id", "VARCHAR(50)"),
                ("properties", "pricing_profile", "VARCHAR(30) DEFAULT 'urban_hotel'"),
                ("properties", "weekly_discount_pct", "NUMERIC(5,2)"),
                ("properties", "monthly_discount_pct", "NUMERIC(5,2)"),
                ("price_snapshots", "min_stay", "INTEGER"),
                ("price_snapshots", "manually_overridden", "BOOLEAN DEFAULT FALSE"),
                ("properties", "latitude", "NUMERIC(9,6)"),
                ("properties", "longitude", "NUMERIC(9,6)"),
                ("local_events", "venue_lat", "NUMERIC(9,6)"),
                ("local_events", "venue_lng", "NUMERIC(9,6)"),
            ]:
                try:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {col} {typ}"))
                    conn.commit()
                except Exception:
                    conn.rollback()
        print("✓ Kolumn-migration klar")
    except Exception as e:
        print(f"⚠ Kolumn-migration: {e}")
    # Lägg till saknade kolumner utan att röra befintlig data
    try:
        from sqlalchemy import text
        with engine.connect() as conn:
            missing_cols = [
                ("cleaning_job_state", "outgoing_guests", "INTEGER"),
                ("cleaning_job_state", "bedding_for_guests", "INTEGER"),
                ("bookings", "num_adults", "INTEGER"),
                ("bookings", "num_children", "INTEGER"),
                ("bookings", "num_infants", "INTEGER"),
                ("bookings", "confirmation_code", "VARCHAR(50)"),
                ("properties", "airbnb_listing_id", "VARCHAR(50)"),
            ]
            for table, col, typ in missing_cols:
                try:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {col} {typ}"))
                    conn.commit()
                except Exception:
                    conn.rollback()
        print("✓ Kolumn-migration klar")
    except Exception as e:
        print(f"⚠ Kolumn-migration misslyckades: {e}")
    # Sätt Airbnb listing-ID:n automatiskt
    try:
        from db.session import SessionLocal
        from db.models import Property
        LISTING_IDS = {
            "enskede-79":       "1675878393965009957",
            "trosa-havsdrom":   "1673099638596438222",
            "alta-beach-villa": "1654943677598237856",
            "alvsjö-tradgard":  "1678065319412002223",
        }
        db = SessionLocal()
        try:
            for crm_id, lid in LISTING_IDS.items():
                prop = db.query(Property).filter(Property.crm_property_id == crm_id).first()
                if prop and hasattr(prop, 'airbnb_listing_id') and prop.airbnb_listing_id != lid:
                    prop.airbnb_listing_id = lid
            db.commit()
            print("✓ Airbnb listing-ID:n satta")
        finally:
            db.close()
    except Exception as e:
        print(f"⚠ Listing-ID setup: {e}")
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
app.include_router(airbnb_prices.router, tags=["Airbnb-priser"])
app.include_router(beds24_api.router, tags=["Beds24"])
app.include_router(owner_periods.router, tags=["Ägarperioder"])
app.include_router(cleaning_state.router, tags=["Städuppdrag"])
app.include_router(guest_import.router, tags=["Gästimport"])

@app.get("/setup/debug-price")
def debug_price(date: str, prop: str = "enskede-79"):
    """Debug: läs manually_overridden direkt från DB med raw SQL."""
    from sqlalchemy import text
    from db.session import engine
    with engine.connect() as conn:
        result = conn.execute(text(
            "SELECT ps.date, ps.recommended_price, ps.published_price, ps.manually_overridden "
            "FROM price_snapshots ps "
            "JOIN properties p ON p.id = ps.property_id "
            "WHERE p.crm_property_id = :prop AND ps.date = :date"
        ), {"prop": prop, "date": date})
        row = result.fetchone()
        if row:
            return {"date": str(row[0]), "recommended": str(row[1]), "published": str(row[2]), "manually_overridden": row[3]}
        return {"error": "not found"}


@app.post("/setup/fix-schema")
def fix_schema():
    """Kör ALTER TABLE direkt för att lägga till saknade kolumner."""
    from sqlalchemy import text
    from db.session import engine
    results = []
    with engine.connect() as conn:
        for sql in [
            "ALTER TABLE price_snapshots ADD COLUMN IF NOT EXISTS manually_overridden BOOLEAN DEFAULT FALSE",
            "UPDATE price_snapshots SET manually_overridden = FALSE WHERE manually_overridden IS NULL",
        ]:
            try:
                conn.execute(text(sql))
                conn.commit()
                results.append(f"OK: {sql[:80]}")
            except Exception as e:
                results.append(f"ERR: {str(e)[:80]}")
    return {"results": results}


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


@app.post("/setup/set-listing-ids")
def set_listing_ids():
    """Sätter Airbnb listing-ID:n för alla objekt i databasen."""
    from db.session import SessionLocal
    from db.models import Property
    
    LISTING_IDS = {
        "enskede-79":       "1675878393965009957",
        "trosa-havsdrom":   "1673099638596438222",
        "alta-beach-villa": "1654943677598237856",
        "alvsjö-tradgard":  "1678065319412002223",
    }
    
    db = SessionLocal()
    updated = []
    try:
        for crm_id, listing_id in LISTING_IDS.items():
            prop = db.query(Property).filter(
                Property.crm_property_id == crm_id
            ).first()
            if prop:
                # Set airbnb_listing_id if column exists
                if hasattr(prop, 'airbnb_listing_id'):
                    prop.airbnb_listing_id = listing_id
                    updated.append(crm_id)
        db.commit()
        return {"status": "ok", "updated": updated}
    except Exception as e:
        db.rollback()
        return {"status": "error", "detail": str(e)}
    finally:
        db.close()
