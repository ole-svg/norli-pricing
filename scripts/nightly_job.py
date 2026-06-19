"""
Nattjobb - kors automatiskt varje natt kl 02:00.

Gor tre saker i ordning for alla aktiva objekt:
1. Raknar om priser 365 dagar framat
2. Sparar i databasen
3. Publicerar till Pricelabs -> Airbnb

Kors av Railway Cron Schedule.
"""

import sys
import os
import logging
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.session import SessionLocal
from db.models import Property, Season, CalendarEvent, LocalEvent
from engine.pricing import PricingEngine
from adapters.publisher import Publisher
from scripts.seed import create_tables

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)


def run_nightly_job():
    logger.info("=" * 50)
    logger.info(f"NATTJOBB STARTAR: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 50)

    # Se till att tabeller finns
    create_tables()

    db = SessionLocal()
    try:
        # Hamta alla aktiva objekt
        properties = db.query(Property).filter(Property.is_active == True).all()

        if not properties:
            logger.warning("Inga aktiva objekt hittades - avslutar")
            return

        logger.info(f"Hittade {len(properties)} aktiva objekt")

        # Hamta globala data en gang
        seasons = db.query(Season).all()
        calendar_events = db.query(CalendarEvent).all()
        local_events = db.query(LocalEvent).all()

        total_calculated = 0
        total_published = 0
        errors = []

        for prop in properties:
            logger.info(f"\nBearbetar: {prop.name}")

            # Steg 1: Rakna om priser
            try:
                from datetime import date, timedelta
                from db.models import PriceSnapshot
                from sqlalchemy.orm import joinedload

                prop_with_rules = (
                    db.query(Property)
                    .options(joinedload(Property.price_rules))
                    .filter(Property.id == prop.id)
                    .first()
                )

                # Hamta kategorimultiplikatorer
                from db.models import PricingCategory, PricingCategoryMultiplier
                category_multipliers = {}
                if prop_with_rules.pricing_category_code:
                    cat = db.query(PricingCategory).filter(
                        PricingCategory.code == prop_with_rules.pricing_category_code,
                        PricingCategory.is_active == True
                    ).first()
                    if cat:
                        for m in cat.monthly_multipliers:
                            category_multipliers[m.month] = m.multiplier

                engine = PricingEngine(
                    prop_with_rules, seasons, calendar_events, local_events, category_multipliers
                )

                start = date.today()
                end = start + timedelta(days=364)
                results = engine.calculate_range(start, end)

                # Spara snapshots
                count = 0
                for result in results:
                    existing = (
                        db.query(PriceSnapshot)
                        .filter(
                            PriceSnapshot.property_id == prop.id,
                            PriceSnapshot.date == result.date,
                        )
                        .first()
                    )
                    if existing:
                        existing.recommended_price = result.recommended_price
                        existing.explanation = result.explanation
                        existing.is_clamped_floor = result.is_clamped_floor
                        existing.is_clamped_ceiling = result.is_clamped_ceiling
                        existing.engine_version = result.engine_version
                    else:
                        snapshot = PriceSnapshot(
                            property_id=prop.id,
                            date=result.date,
                            recommended_price=result.recommended_price,
                            explanation=result.explanation,
                            is_clamped_floor=result.is_clamped_floor,
                            is_clamped_ceiling=result.is_clamped_ceiling,
                            engine_version=result.engine_version,
                        )
                        db.add(snapshot)
                    count += 1

                db.commit()
                total_calculated += count
                logger.info(f"  ✓ {count} priser beraknade")

            except Exception as e:
                msg = f"Fel vid omrakning av {prop.name}: {e}"
                logger.error(f"  ✗ {msg}")
                errors.append(msg)
                continue

            # Steg 2: Publicera till Pricelabs
            try:
                publisher = Publisher(db)
                result = publisher.publish_property(prop.crm_property_id)
                if result.success:
                    total_published += result.dates_updated
                    logger.info(f"  ✓ {result.dates_updated} priser publicerade till Pricelabs")
                else:
                    msg = f"Publicering misslyckades for {prop.name}: {result.errors}"
                    logger.error(f"  ✗ {msg}")
                    errors.append(msg)
            except Exception as e:
                msg = f"Fel vid publicering av {prop.name}: {e}"
                logger.error(f"  ✗ {msg}")
                errors.append(msg)

        # Sammanfattning
        logger.info("\n" + "=" * 50)
        logger.info("NATTJOBB KLART")
        logger.info(f"  Objekt: {len(properties)}")
        logger.info(f"  Priser beraknade: {total_calculated}")
        logger.info(f"  Priser publicerade: {total_published}")
        if errors:
            logger.error(f"  Fel: {len(errors)}")
            for e in errors:
                logger.error(f"    - {e}")
        else:
            logger.info("  Inga fel!")
        logger.info("=" * 50)

    except Exception as e:
        logger.error(f"Kritiskt fel i nattjobb: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    run_nightly_job()

        # iCal synk ingår nu i nattjobbet
