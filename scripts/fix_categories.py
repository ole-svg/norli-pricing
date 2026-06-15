"""
Engangsskript: Lagger till prissattningskategorier i Railway-databasen.
Kor en gang: python scripts/fix_categories.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from decimal import Decimal
from db.session import SessionLocal, engine
from db.models import Base, PricingCategory, PricingCategoryMultiplier

# Skapa tabeller om de saknas
Base.metadata.create_all(bind=engine)

CATEGORIES = [
    ("STOCKHOLM_URBAN_EVENT", "Stockholm Urban / Event", True, 1,
     {1:0.75,2:0.85,3:0.95,4:1.00,5:1.10,6:1.25,7:1.30,8:1.35,9:1.15,10:1.00,11:0.85,12:1.05}),
    ("STOCKHOLM_SUBURBAN_FAMILY", "Stockholm Suburban / Family", True, 2,
     {1:0.70,2:0.78,3:0.88,4:0.95,5:1.05,6:1.20,7:1.30,8:1.25,9:1.00,10:0.90,11:0.75,12:0.95}),
    ("SUMMER_LEISURE", "Summer Leisure / Fritidshus", True, 3,
     {1:0.50,2:0.55,3:0.65,4:0.80,5:1.00,6:1.35,7:1.75,8:1.55,9:0.95,10:0.70,11:0.50,12:0.75}),
    ("WINTER_YEAR_ROUND_LEISURE", "Winter and Year-round Leisure", False, 4,
     {1:1.25,2:1.35,3:1.20,4:0.90,5:0.75,6:0.90,7:1.10,8:1.00,9:0.85,10:0.85,11:0.80,12:1.30}),
]

db = SessionLocal()
try:
    count = 0
    for code, name, active, order, mults in CATEGORIES:
        existing = db.query(PricingCategory).filter_by(code=code).first()
        if not existing:
            cat = PricingCategory(code=code, name=name, is_active=active, sort_order=order)
            db.add(cat)
            db.flush()
            for m, v in mults.items():
                db.add(PricingCategoryMultiplier(
                    category_id=cat.id,
                    month=m,
                    multiplier=Decimal(str(v))
                ))
            count += 1
            print(f"  + {code}")
        else:
            print(f"  = {code} (finns redan)")
    db.commit()
    print(f"\nKlart! {count} kategorier skapade.")
except Exception as e:
    db.rollback()
    print(f"Fel: {e}")
    raise
finally:
    db.close()
