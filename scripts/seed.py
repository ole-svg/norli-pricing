"""
Initierar databasen och lägger in testdata för Enskedevägen 79.

Körs en gång vid setup: python scripts/seed.py
"""

import sys
import os

# Lägg till projektrooten i Python-sökvägen
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import date
from decimal import Decimal

from db.session import engine, SessionLocal
from db.models import Base, Property, Season, CalendarEvent, LocalEvent


def create_tables():
    """Skapar alla tabeller i databasen."""
    print("Skapar databastabeller...")
    Base.metadata.create_all(bind=engine)
    print("✓ Tabeller skapade")


def seed_enskede(db):
    """Lägger in Enskedevägen 79 som testobjekt med riktiga ekonomivärden."""
    existing = db.query(Property).filter(Property.crm_property_id == "enskede-79").first()
    if existing:
        print("ℹ Enskedevägen 79 finns redan i databasen")
        return existing

    prop = Property(
        crm_property_id="enskede-79",
        name="Enskedevägen 79 — Enskede Villa",
        capacity=8,
        bedrooms=4,
        bathrooms=2,
        linen_included=True,
        base_price=Decimal("3500"),           # Grundpris per natt
        pricing_strategy="balanced",

        # Skyddsräcken
        price_floor=Decimal("1500"),
        price_ceiling=Decimal("6500"),
        min_margin=None,
        min_owner_net=None,

        # Ekonomimodell
        revenue_model="commission",
        owner_type="company_vat_registered",  # Enskede Villa AB
        platform_fee_rate=Decimal("0.03"),    # Airbnb 3%
        vat_rate=Decimal("0.12"),             # Logimoms 12%
        owner_share_pct=Decimal("0.82"),      # 82% till ägaren
        norli_share_pct=Decimal("0.18"),      # 18% till Norli
        object_costs_per_booking=Decimal("200"),

        # Investeringar / uppstartskostnader
        investment_balance=Decimal("0"),            # Norli fakturerar utlagg separat
        investment_recoupment_mode="manual",       # Manuell kvittning - Norli fakturerar separat
        investment_recoupment_cap=None,           # Inget tak for Enskede

        # Städmodell
        cleaning_hourly_rate=Decimal("500"),  # 500 kr/h inkl moms → exkl moms ~400 kr (bolag lyfter moms)
        cleaning_base_hours=Decimal("2.0"),   # Grundtid
        cleaning_hours_per_bedroom=Decimal("0.5"),
        cleaning_hours_per_bathroom=Decimal("0.5"),
        cleaning_hours_per_guest=Decimal("0.25"),
        cleaning_extra_hours_per_night=Decimal("0.2"),
        cleaning_night_threshold=3,
        cleaning_max_hours=Decimal("8.0"),
        cleaning_invoice_recipient="owner_company",  # Enskede Villa AB betalar städet
        cleaning_rut_applicable=False,               # Bolag → ingen RUT
    )
    db.add(prop)
    db.flush()
    print(f"✓ Enskedevägen 79 skapad (id={prop.id})")
    return prop


def seed_seasons(db):
    """Lägger in säsonger för Stockholm."""
    seasons_data = [
        {
            "name": "Högsäsong sommar",
            "start_date": date(2025, 6, 15),
            "end_date": date(2025, 8, 15),
            "multiplier": Decimal("1.40"),
            "priority": 10,
        },
        {
            "name": "Högsäsong sommar",
            "start_date": date(2026, 6, 15),
            "end_date": date(2026, 8, 15),
            "multiplier": Decimal("1.40"),
            "priority": 10,
        },
        {
            "name": "Mellansäsong vår",
            "start_date": date(2026, 4, 1),
            "end_date": date(2026, 6, 14),
            "multiplier": Decimal("1.15"),
            "priority": 5,
        },
        {
            "name": "Mellansäsong höst",
            "start_date": date(2026, 8, 16),
            "end_date": date(2026, 10, 31),
            "multiplier": Decimal("1.10"),
            "priority": 5,
        },
        {
            "name": "Lågsäsong vinter",
            "start_date": date(2026, 1, 7),
            "end_date": date(2026, 3, 31),
            "multiplier": Decimal("0.85"),
            "priority": 5,
        },
    ]
    count = 0
    for s in seasons_data:
        existing = db.query(Season).filter(
            Season.name == s["name"],
            Season.start_date == s["start_date"]
        ).first()
        if not existing:
            db.add(Season(**s))
            count += 1
    print(f"✓ {count} säsonger skapade")


def seed_calendar_events(db):
    """Lägger in helger och lov för 2025–2026."""
    events_data = [
        # Jul/nyår — de mest lönsamma perioderna
        {
            "name": "Julhelg",
            "event_type": "public_holiday",
            "start_date": date(2025, 12, 23),
            "end_date": date(2025, 12, 26),
            "multiplier": Decimal("1.50"),
            "priority": 20,
        },
        {
            "name": "Nyår",
            "event_type": "public_holiday",
            "start_date": date(2025, 12, 27),
            "end_date": date(2026, 1, 2),
            "multiplier": Decimal("1.60"),
            "priority": 25,
        },
        # Påsk 2026
        {
            "name": "Påsk",
            "event_type": "public_holiday",
            "start_date": date(2026, 4, 2),
            "end_date": date(2026, 4, 6),
            "multiplier": Decimal("1.30"),
            "priority": 20,
        },
        # Kristi himmelsfärd 2026
        {
            "name": "Kristi himmelsfärd",
            "event_type": "public_holiday",
            "start_date": date(2026, 5, 14),
            "end_date": date(2026, 5, 17),
            "multiplier": Decimal("1.20"),
            "priority": 15,
        },
        # Midsommar 2026
        {
            "name": "Midsommar",
            "event_type": "public_holiday",
            "start_date": date(2026, 6, 19),
            "end_date": date(2026, 6, 22),
            "multiplier": Decimal("1.15"),
            "priority": 20,
        },
        # Höstlov 2025
        {
            "name": "Höstlov Stockholm",
            "event_type": "school_break",
            "start_date": date(2025, 10, 27),
            "end_date": date(2025, 11, 2),
            "multiplier": Decimal("1.20"),
            "priority": 10,
        },
        # Sportlov 2026
        {
            "name": "Sportlov Stockholm",
            "event_type": "school_break",
            "start_date": date(2026, 2, 23),
            "end_date": date(2026, 3, 1),
            "multiplier": Decimal("1.25"),
            "priority": 10,
        },
    ]
    count = 0
    for e in events_data:
        existing = db.query(CalendarEvent).filter(
            CalendarEvent.name == e["name"],
            CalendarEvent.start_date == e["start_date"]
        ).first()
        if not existing:
            db.add(CalendarEvent(**e))
            count += 1
    print(f"✓ {count} kalenderhändelser skapade")


def seed_local_events(db):
    """Lägger in kända Stockholms-evenemang som testdata."""
    events_data = [
        {
            "name": "Stockholm Marathon",
            "event_type": "sport",
            "location": "Stockholm",
            "venue": "Stadion",
            "start_date": date(2026, 6, 6),
            "end_date": date(2026, 6, 7),
            "multiplier": Decimal("1.25"),
            "radius_km": Decimal("15"),
        },
        {
            "name": "Stockholm Music & Arts",
            "event_type": "concert",
            "location": "Stockholm",
            "venue": "Djurgårdsön",
            "start_date": date(2026, 8, 7),
            "end_date": date(2026, 8, 9),
            "multiplier": Decimal("1.30"),
            "radius_km": Decimal("10"),
        },
    ]
    count = 0
    for e in events_data:
        existing = db.query(LocalEvent).filter(
            LocalEvent.name == e["name"],
            LocalEvent.start_date == e["start_date"]
        ).first()
        if not existing:
            db.add(LocalEvent(**e))
            count += 1
    print(f"✓ {count} lokala evenemang skapade")


def seed_enskede_rules(db, prop):
    """Lagg till prisregler for Enskede."""
    from db.models import PriceRule
    import json

    rules = [
        # Vistelselangdsrabatter
        {
            "rule_type": "length_of_stay",
            "name": "Enkelnat tillagg",
            "parameters": {"min_nights": 1, "max_nights": 1, "multiplier": 1.20},
            "priority": 10,
        },
        {
            "rule_type": "length_of_stay",
            "name": "Standardvistelse 2-3 natter",
            "parameters": {"min_nights": 2, "max_nights": 3, "multiplier": 1.00},
            "priority": 10,
        },
        {
            "rule_type": "length_of_stay",
            "name": "Langvistelse 4-6 natter",
            "parameters": {"min_nights": 4, "max_nights": 6, "multiplier": 0.95},
            "priority": 10,
        },
        {
            "rule_type": "length_of_stay",
            "name": "Veckovistelse 7-13 natter",
            "parameters": {"min_nights": 7, "max_nights": 13, "multiplier": 0.90},
            "priority": 10,
        },
        {
            "rule_type": "length_of_stay",
            "name": "Langtidsvistelse 14+ natter",
            "parameters": {"min_nights": 14, "max_nights": 9999, "multiplier": 0.85},
            "priority": 10,
        },
        # Veckodagsjusteringar (asidosatter standardvarden)
        {
            "rule_type": "weekday_adjustment",
            "name": "Lordag justering",
            "parameters": {"days": [5], "multiplier": 1.15},  # Ned fran 1.20
            "priority": 5,
        },
    ]

    count = 0
    for r in rules:
        existing = db.query(PriceRule).filter(
            PriceRule.property_id == prop.id,
            PriceRule.name == r["name"]
        ).first()
        if not existing:
            rule = PriceRule(
                property_id=prop.id,
                rule_type=r["rule_type"],
                name=r["name"],
                parameters=json.dumps(r["parameters"]),
                priority=r["priority"],
            )
            db.add(rule)
            count += 1
    print(f"✓ {count} prisregler skapade for Enskede")
    return count

if __name__ == "__main__":
    print("\n=== Norli Pricing Engine — Databasinitiering ===\n")
    create_tables()

    db = SessionLocal()
    try:
        seed_enskede(db)
        seed_seasons(db)
        seed_calendar_events(db)
        prop = db.query(__import__("db.models", fromlist=["Property"]).Property).filter_by(crm_property_id="enskede-79").first()
        seed_enskede_rules(db, prop)
        db.commit()
        print("\n✓ Allt klart! Databasen är redo.\n")
    except Exception as e:
        db.rollback()
        print(f"\n✗ Fel: {e}\n")
        raise
    finally:
        db.close()

