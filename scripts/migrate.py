"""
Koer databasmigrering vid startup.
Lagger till saknade kolumner utan att radera data.
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text, inspect
from db.session import engine
from db.models import Base

def migrate():
    print("Kontrollerar databasschema...")
    
    # Skapa tabeller som saknas
    Base.metadata.create_all(bind=engine)
    print("✓ Tabeller skapade/verifierade")
    
    # Lagg till saknade kolumner med ALTER TABLE
    with engine.connect() as conn:
        inspector = inspect(engine)
        
        # Hamta befintliga kolumner i properties-tabellen
        existing = {col['name'] for col in inspector.get_columns('properties')}
        
        # Alla kolumner som ska finnas
        new_columns = {
            'pricing_category_code': 'VARCHAR(50) DEFAULT \'STOCKHOLM_URBAN_EVENT\'',
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
        
        added = 0
        for col_name, col_def in new_columns.items():
            if col_name not in existing:
                conn.execute(text(f'ALTER TABLE properties ADD COLUMN IF NOT EXISTS {col_name} {col_def}'))
                print(f"  + Kolumn tillagd: {col_name}")
                added += 1
        
        conn.commit()
        
        if added == 0:
            print("✓ Alla kolumner finns redan")
        else:
            print(f"✓ {added} kolumner tillagda")

if __name__ == '__main__':
    migrate()
