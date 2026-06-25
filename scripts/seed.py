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
        cleaning_profile_code="default_villa",
        max_guests=12,
        rounding_rule="tiered",
        event_sensitivity="high",
        object_cost_per_booking=Decimal("200"),
        pricing_category_code="STOCKHOLM_URBAN_EVENT",
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
        # Midsommar hanteras som vanlig högsäsong + veckodag, inget extra påslag
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

def seed_cleaning_profiles(db):
    """Skapar globala stadsprofiler."""
    import json
    from db.models import CleaningProfile

    PROFILES = [
        {
            "code": "default_villa",
            "name": "Standard Villa",
            "description": "Universal stadsprofil for villor. Natttrappa 1n=3h->8n=7h, gastjustering per 2-intervall.",
            "base_guests": 8,
            "min_hours": "3.0",
            "max_hours": "8.0",
            "guest_interval": 2,
            "under_base_adjustment": "0.25",
            "over_base_adjustment": "0.50",
            "los_hours_json": json.dumps({"1":3.0,"2":3.5,"3":4.0,"4":4.5,"5":5.0,"6":5.5,"7":6.0,"8":7.0}),
        },
        {
            "code": "default_apartment",
            "name": "Standard Lagenhet",
            "description": "Stadsprofil for lagenheter. Kortare basstad.",
            "base_guests": 4,
            "min_hours": "2.0",
            "max_hours": "5.0",
            "guest_interval": 2,
            "under_base_adjustment": "0.25",
            "over_base_adjustment": "0.50",
            "los_hours_json": json.dumps({"1":2.0,"2":2.5,"3":3.0,"4":3.5,"5":4.0,"6":4.5,"7":5.0,"8":5.0}),
        },
        {
            "code": "default_leisure",
            "name": "Fritidshus",
            "description": "Stadsprofil for fritidshus. Langre stadtider, fler gaster och natter.",
            "base_guests": 8,
            "min_hours": "3.5",
            "max_hours": "10.0",
            "guest_interval": 2,
            "under_base_adjustment": "0.25",
            "over_base_adjustment": "0.75",
            "los_hours_json": json.dumps({"1":3.5,"2":4.0,"3":4.5,"4":5.0,"5":5.5,"6":6.0,"7":7.0,"8":8.0}),
        },
    ]

    count = 0
    for pd in PROFILES:
        from decimal import Decimal
        existing = db.query(CleaningProfile).filter_by(code=pd["code"]).first()
        if not existing:
            db.add(CleaningProfile(
                code=pd["code"],
                name=pd["name"],
                description=pd["description"],
                base_guests=pd["base_guests"],
                min_hours=Decimal(pd["min_hours"]),
                max_hours=Decimal(pd["max_hours"]),
                guest_interval=pd["guest_interval"],
                under_base_adjustment=Decimal(pd["under_base_adjustment"]),
                over_base_adjustment=Decimal(pd["over_base_adjustment"]),
                los_hours_json=pd["los_hours_json"],
            ))
            count += 1
    print(f"✓ {count} stadsprofiler skapade")


def seed_pricing_categories(db):
    """Lagger in de fyra prissattningskategorierna med manadsvisa multiplikatorer."""
    from db.models import PricingCategory, PricingCategoryMultiplier

    CATEGORIES = [
        {
            "code": "STOCKHOLM_URBAN_EVENT",
            "name": "Stockholm Urban / Event",
            "description": "Lagenheter och citynara villor. Stabil efterfragan med topp jun-aug och eventdrivna datum.",
            "is_active": True,
            "sort_order": 1,
            "multipliers": {1:0.75, 2:0.85, 3:0.95, 4:1.00, 5:1.10, 6:1.25, 7:1.30, 8:1.35, 9:1.15, 10:1.00, 11:0.85, 12:1.05}
        },
        {
            "code": "STOCKHOLM_SUBURBAN_FAMILY",
            "name": "Stockholm Suburban / Family",
            "description": "Storre villor i Storstockholm. Familje- och gruppboenden, semesterdriven efterfragan.",
            "is_active": True,
            "sort_order": 2,
            "multipliers": {1:0.70, 2:0.78, 3:0.88, 4:0.95, 5:1.05, 6:1.20, 7:1.30, 8:1.25, 9:1.00, 10:0.90, 11:0.75, 12:0.95}
        },
        {
            "code": "SUMMER_LEISURE",
            "name": "Summer Leisure / Fritidshus",
            "description": "Fritidshus, skargard, kustnara hus. Extremt sasongsbetonad med topp midsommar-juli.",
            "is_active": True,
            "sort_order": 3,
            "multipliers": {1:0.50, 2:0.55, 3:0.65, 4:0.80, 5:1.00, 6:1.35, 7:1.75, 8:1.55, 9:0.95, 10:0.70, 11:0.50, 12:0.75}
        },
        {
            "code": "WINTER_YEAR_ROUND_LEISURE",
            "name": "Winter & Year-round Leisure",
            "description": "Fjall, skidorter, spa/bastu. Stark vinterefterfragan. Forberedd men ej aktiv i v1.",
            "is_active": False,
            "sort_order": 4,
            "multipliers": {1:1.25, 2:1.35, 3:1.20, 4:0.90, 5:0.75, 6:0.90, 7:1.10, 8:1.00, 9:0.85, 10:0.85, 11:0.80, 12:1.30}
        },
    ]

    count = 0
    for cat_data in CATEGORIES:
        existing = db.query(PricingCategory).filter(PricingCategory.code == cat_data["code"]).first()
        if not existing:
            cat = PricingCategory(
                code=cat_data["code"],
                name=cat_data["name"],
                description=cat_data["description"],
                is_active=cat_data["is_active"],
                sort_order=cat_data["sort_order"],
            )
            db.add(cat)
            db.flush()

            for month, mult in cat_data["multipliers"].items():
                db.add(PricingCategoryMultiplier(
                    category_id=cat.id,
                    month=month,
                    multiplier=Decimal(str(mult)),
                ))
            count += 1

    print(f"✓ {count} prissattningskategorier skapade")


def seed_trosa(db):
    """Exklusiv havsdrom | Pool & privat sjomt — Trosa"""
    from db.models import Property
    existing = db.query(Property).filter_by(crm_property_id="trosa-havsdrom").first()
    if existing:
        print("ℹ Trosa finns redan i databasen")
        return existing

    prop = Property(
        crm_property_id="trosa-havsdrom",
        name="Exklusiv havsdröm | Pool & privat sjötomt",
        capacity=10,
        max_guests=10,
        bedrooms=4,
        bathrooms=2,
        base_price=Decimal("6500"),
        pricing_category_code="SUMMER_LEISURE",
        cleaning_profile_code="default_leisure",
        price_floor=Decimal("2500"),
        price_ceiling=Decimal("14000"),
        rounding_rule="nearest_10",
        event_sensitivity="low",
        owner_share_pct=Decimal("0.82"),
        norli_share_pct=Decimal("0.18"),
        platform_fee_rate=Decimal("0.03"),
        vat_rate=Decimal("0.12"),
        owner_type="company_vat_registered",
        cleaning_hourly_rate=Decimal("500"),
        cleaning_base_guests=8,
        cleaning_min_hours=Decimal("3.5"),
        cleaning_max_hours=Decimal("10.0"),
        cleaning_hours_per_2_guests_above=Decimal("0.75"),
        cleaning_hours_per_2_guests_below=Decimal("0.25"),
        cleaning_invoice_recipient="owner_company",
        cleaning_rut_applicable=False,
        object_cost_per_booking=Decimal("250"),
        last_minute_enabled=True,
        last_minute_start_days=20,
        last_minute_max_discount=Decimal("0.20"),
        investment_balance=Decimal("0"),
        is_active=True,
    )
    db.add(prop)
    db.flush()
    print(f"✓ Trosa havsdröm skapad (id={prop.id})")
    return prop


def seed_alta(db):
    """Villa 5 Min to Beach · 20 Min to Stockholm · Sauna — Alta"""
    from db.models import Property
    existing = db.query(Property).filter_by(crm_property_id="alta-beach-villa").first()
    if existing:
        print("ℹ Älta finns redan i databasen")
        return existing

    prop = Property(
        crm_property_id="alta-beach-villa",
        name="Villa 5 Min to Beach · 20 Min to Stockholm · Sauna",
        capacity=8,
        max_guests=8,
        bedrooms=3,
        bathrooms=2,
        base_price=Decimal("3000"),
        pricing_category_code="STOCKHOLM_SUBURBAN_FAMILY",
        cleaning_profile_code="default_villa",
        price_floor=Decimal("1200"),
        price_ceiling=Decimal("6000"),
        rounding_rule="nearest_10",
        event_sensitivity="medium",
        owner_share_pct=Decimal("0.82"),
        norli_share_pct=Decimal("0.18"),
        platform_fee_rate=Decimal("0.03"),
        vat_rate=Decimal("0.12"),
        owner_type="company_vat_registered",
        cleaning_hourly_rate=Decimal("500"),
        cleaning_base_guests=8,
        cleaning_min_hours=Decimal("3.0"),
        cleaning_max_hours=Decimal("8.0"),
        cleaning_hours_per_2_guests_above=Decimal("0.5"),
        cleaning_hours_per_2_guests_below=Decimal("0.25"),
        cleaning_invoice_recipient="owner_company",
        cleaning_rut_applicable=False,
        object_cost_per_booking=Decimal("200"),
        last_minute_enabled=True,
        last_minute_start_days=20,
        last_minute_max_discount=Decimal("0.20"),
        investment_balance=Decimal("0"),
        is_active=True,
    )
    db.add(prop)
    db.flush()
    print(f"✓ Älta Beach Villa skapad (id={prop.id})")
    return prop


def seed_alvsjö(db):
    """Spacious Stockholm Villa · Garden · AC · Parking — Alvsjö"""
    from db.models import Property
    existing = db.query(Property).filter_by(crm_property_id="alvsjö-tradgard").first()
    if existing:
        print("ℹ Älvsjö finns redan i databasen")
        return existing

    prop = Property(
        crm_property_id="alvsjö-tradgard",
        name="Spacious Stockholm Villa · Garden · AC · Parking",
        capacity=8,
        max_guests=8,
        bedrooms=4,
        bathrooms=2,
        base_price=Decimal("3000"),
        pricing_category_code="STOCKHOLM_SUBURBAN_FAMILY",
        cleaning_profile_code="default_villa",
        price_floor=Decimal("1200"),
        price_ceiling=Decimal("6500"),
        rounding_rule="nearest_10",
        event_sensitivity="medium",
        owner_share_pct=Decimal("0.82"),
        norli_share_pct=Decimal("0.18"),
        platform_fee_rate=Decimal("0.03"),
        vat_rate=Decimal("0.12"),
        owner_type="company_vat_registered",
        cleaning_hourly_rate=Decimal("500"),
        cleaning_base_guests=8,
        cleaning_min_hours=Decimal("3.0"),
        cleaning_max_hours=Decimal("8.0"),
        cleaning_hours_per_2_guests_above=Decimal("0.5"),
        cleaning_hours_per_2_guests_below=Decimal("0.25"),
        cleaning_invoice_recipient="owner_company",
        cleaning_rut_applicable=False,
        object_cost_per_booking=Decimal("200"),
        last_minute_enabled=True,
        last_minute_start_days=20,
        last_minute_max_discount=Decimal("0.20"),
        investment_balance=Decimal("0"),
        is_active=True,
    )
    db.add(prop)
    db.flush()
    print(f"✓ Älvsjö Trädgård skapad (id={prop.id})")
    return prop




def seed_strandvilla(db):
    """Älvsjö Strandvilla — Prästkragstigen 12, 125 53 Älvsjö"""
    from db.models import Property
    existing = db.query(Property).filter_by(crm_property_id="alvsjö-strandvilla").first()
    if existing:
        print("ℹ Älvsjö Strandvilla finns redan i databasen")
        return existing

    prop = Property(
        crm_property_id="alvsjö-strandvilla",
        name="Älvsjö Strandvilla",
        capacity=9,
        max_guests=9,
        bedrooms=4,
        bathrooms=2,
        base_price=Decimal("4500"),
        pricing_category_code="STOCKHOLM_URBAN_EVENT",
        cleaning_profile_code="default_villa",
        price_floor=Decimal("2000"),
        price_ceiling=Decimal("9000"),
        rounding_rule="nearest_10",
        event_sensitivity="high",
        owner_share_pct=Decimal("0.825"),
        norli_share_pct=Decimal("0.175"),
        platform_fee_rate=Decimal("0.03"),
        vat_rate=Decimal("0.12"),
        owner_type="company_vat_registered",
        cleaning_hourly_rate=Decimal("500"),
        cleaning_base_guests=6,
        cleaning_min_hours=Decimal("4.0"),
        cleaning_max_hours=Decimal("9.0"),
        cleaning_hours_per_2_guests_above=Decimal("0.5"),
        cleaning_hours_per_2_guests_below=Decimal("0.25"),
        last_minute_enabled=True,
        last_minute_start_days=20,
        last_minute_max_discount=Decimal("0.20"),
        object_cost_per_booking=Decimal("200"),
        is_active=True,
    )
    db.add(prop)
    db.flush()
    print(f"✓ Älvsjö Strandvilla skapad (id={prop.id})")
    return prop


def seed_ronneby(db):
    """Fritidshus · Ronneby"""
    from db.models import Property
    existing = db.query(Property).filter_by(crm_property_id="ronneby-fritidshus").first()
    if existing:
        print("ℹ Ronneby finns redan i databasen")
        return existing

    prop = Property(
        crm_property_id="ronneby-fritidshus",
        name="Fritidshus · Ronneby",
        capacity=8,
        max_guests=8,
        bedrooms=3,
        bathrooms=1,
        base_price=Decimal("2500"),
        pricing_category_code="STOCKHOLM_SUBURBAN_FAMILY",
        cleaning_profile_code="default_villa",
        price_floor=Decimal("1200"),
        price_ceiling=Decimal("5000"),
        rounding_rule="nearest_10",
        event_sensitivity="low",
        owner_share_pct=Decimal("0.80"),
        norli_share_pct=Decimal("0.20"),
        platform_fee_rate=Decimal("0.03"),
        vat_rate=Decimal("0.12"),
        owner_type="private",
        cleaning_hourly_rate=Decimal("500"),
        cleaning_base_guests=4,
        cleaning_min_hours=Decimal("3.0"),
        cleaning_max_hours=Decimal("6.0"),
        cleaning_hours_per_2_guests_above=Decimal("0.5"),
        cleaning_hours_per_2_guests_below=Decimal("0.25"),
        last_minute_enabled=True,
        last_minute_start_days=20,
        last_minute_max_discount=Decimal("0.20"),
        object_cost_per_booking=Decimal("100"),
        is_active=True,
    )
    db.add(prop)
    db.flush()
    print(f"✓ Fritidshus Ronneby skapad (id={prop.id})")
    return prop


def seed_island_cottage(db):
    """Island Cottage by Boat · Sauna & Private dock — Oxelösund/Nyköpings skärgård"""
    from db.models import Property
    existing = db.query(Property).filter_by(crm_property_id="island-cottage-oxelosund").first()
    if existing:
        print("ℹ Island Cottage finns redan")
        return existing
    prop = Property(
        crm_property_id="island-cottage-oxelosund",
        name="Island Cottage by Boat · Oxelösund",
        airbnb_listing_id="1714535794845606344",
        capacity=6, max_guests=6, bedrooms=2, bathrooms=1,
        base_price=Decimal("2800"),
        pricing_profile="destination",
        pricing_category_code="SUMMER_LEISURE",
        cleaning_profile_code="default_leisure",
        price_floor=Decimal("1800"), price_ceiling=Decimal("6000"),
        rounding_rule="nearest_10", event_sensitivity="low",
        owner_share_pct=Decimal("0.82"), norli_share_pct=Decimal("0.18"),
        platform_fee_rate=Decimal("0.03"), vat_rate=Decimal("0.12"),
        owner_type="company_vat_registered",
        cleaning_hourly_rate=Decimal("500"),
        cleaning_base_guests=4, cleaning_min_hours=Decimal("2.5"),
        cleaning_max_hours=Decimal("6.0"),
        cleaning_hours_per_2_guests_above=Decimal("0.5"),
        cleaning_hours_per_2_guests_below=Decimal("0.25"),
        cleaning_invoice_recipient="owner_company",
        cleaning_rut_applicable=False,
        object_cost_per_booking=Decimal("200"),
        last_minute_enabled=True, last_minute_start_days=20,
        last_minute_max_discount=Decimal("0.25"),
        weekly_discount_pct=Decimal("8"), monthly_discount_pct=Decimal("15"),
        latitude=Decimal("58.6700"), longitude=Decimal("17.1000"),
        investment_balance=Decimal("0"), is_active=True,
    )
    db.add(prop); db.flush()
    print(f"✓ Island Cottage skapad (id={prop.id})")
    return prop


def seed_seafront_cottage(db):
    """Seafront Cottage · Private Dock · Sea View — Oxelösund"""
    from db.models import Property
    existing = db.query(Property).filter_by(crm_property_id="seafront-cottage-oxelosund").first()
    if existing:
        print("ℹ Seafront Cottage finns redan")
        return existing
    prop = Property(
        crm_property_id="seafront-cottage-oxelosund-2",
        name="Seafront Cottage · Oxelösund",
        airbnb_listing_id="1710660504608521447",
        capacity=6, max_guests=6, bedrooms=2, bathrooms=1,
        base_price=Decimal("2750"),
        pricing_profile="destination",
        pricing_category_code="SUMMER_LEISURE",
        cleaning_profile_code="default_leisure",
        price_floor=Decimal("1800"), price_ceiling=Decimal("6000"),
        rounding_rule="nearest_10", event_sensitivity="low",
        owner_share_pct=Decimal("0.82"), norli_share_pct=Decimal("0.18"),
        platform_fee_rate=Decimal("0.03"), vat_rate=Decimal("0.12"),
        owner_type="company_vat_registered",
        cleaning_hourly_rate=Decimal("500"),
        cleaning_base_guests=4, cleaning_min_hours=Decimal("2.5"),
        cleaning_max_hours=Decimal("6.0"),
        cleaning_hours_per_2_guests_above=Decimal("0.5"),
        cleaning_hours_per_2_guests_below=Decimal("0.25"),
        cleaning_invoice_recipient="owner_company",
        cleaning_rut_applicable=False,
        object_cost_per_booking=Decimal("200"),
        last_minute_enabled=True, last_minute_start_days=20,
        last_minute_max_discount=Decimal("0.25"),
        weekly_discount_pct=Decimal("8"), monthly_discount_pct=Decimal("15"),
        latitude=Decimal("58.6700"), longitude=Decimal("17.1000"),
        investment_balance=Decimal("0"), is_active=True,
    )
    db.add(prop); db.flush()
    print(f"✓ Seafront Cottage skapad (id={prop.id})")
    return prop


def seed_klassbol(db):
    """Sjöutsikt · Badplats 250m · Klassbol Johanna — Arvika/Klassbol, Värmland"""
    from db.models import Property
    existing = db.query(Property).filter_by(crm_property_id="klassbol-sjoutsikt").first()
    if existing:
        print("ℹ Klassbol finns redan")
        return existing
    prop = Property(
        crm_property_id="klassbol-sjoutsikt",
        name="Sjöutsikt · Klassbol · Arvika",
        airbnb_listing_id="1712900532137830623",
        capacity=8, max_guests=8, bedrooms=3, bathrooms=2,
        base_price=Decimal("2750"),
        pricing_profile="destination",
        pricing_category_code="SUMMER_LEISURE",
        cleaning_profile_code="default_leisure",
        price_floor=Decimal("3000"), price_ceiling=Decimal("12000"),
        rounding_rule="nearest_10", event_sensitivity="low",
        owner_share_pct=Decimal("0.82"), norli_share_pct=Decimal("0.18"),
        platform_fee_rate=Decimal("0.03"), vat_rate=Decimal("0.12"),
        owner_type="company_vat_registered",
        cleaning_hourly_rate=Decimal("500"),
        cleaning_base_guests=6, cleaning_min_hours=Decimal("3.0"),
        cleaning_max_hours=Decimal("8.0"),
        cleaning_hours_per_2_guests_above=Decimal("0.5"),
        cleaning_hours_per_2_guests_below=Decimal("0.25"),
        cleaning_invoice_recipient="owner_company",
        cleaning_rut_applicable=False,
        object_cost_per_booking=Decimal("200"),
        last_minute_enabled=True, last_minute_start_days=20,
        last_minute_max_discount=Decimal("0.20"),
        weekly_discount_pct=Decimal("10"), monthly_discount_pct=Decimal("18"),
        # Koordinater: Klassbol, Värmland — 390 km från Stockholm, 0 km Arvika
        latitude=Decimal("59.5800"), longitude=Decimal("12.3600"),
        investment_balance=Decimal("0"), is_active=True,
    )
    db.add(prop); db.flush()
    print(f"✓ Klassbol skapad (id={prop.id})")
    return prop


def seed_strandvilla(db):
    """Strandvilla nära City — Älvsjö (redan i systemet men uppdaterar listing_id)"""
    from db.models import Property
    existing = db.query(Property).filter_by(crm_property_id="alvsjö-strandvilla").first()
    if existing:
        if not existing.airbnb_listing_id:
            existing.airbnb_listing_id = "1199944314328075124"
            existing.latitude = Decimal("59.2775")
            existing.longitude = Decimal("17.9860")
            print("ℹ Strandvilla uppdaterad med listing_id")
        else:
            print("ℹ Strandvilla finns redan")
        return existing
    prop = Property(
        crm_property_id="alvsjö-strandvilla",
        name="Strandvilla nära City · Älvsjö",
        airbnb_listing_id="1199944314328075124",
        capacity=10, max_guests=10, bedrooms=4, bathrooms=2,
        base_price=Decimal("4000"),
        pricing_profile="urban_hotel",
        pricing_category_code="STOCKHOLM_URBAN_EVENT",
        cleaning_profile_code="default_villa",
        price_floor=Decimal("2000"), price_ceiling=Decimal("7500"),
        rounding_rule="nearest_10", event_sensitivity="high",
        owner_share_pct=Decimal("0.82"), norli_share_pct=Decimal("0.18"),
        platform_fee_rate=Decimal("0.03"), vat_rate=Decimal("0.12"),
        owner_type="company_vat_registered",
        cleaning_hourly_rate=Decimal("500"),
        cleaning_base_guests=8, cleaning_min_hours=Decimal("3.0"),
        cleaning_max_hours=Decimal("8.0"),
        cleaning_hours_per_2_guests_above=Decimal("0.5"),
        cleaning_hours_per_2_guests_below=Decimal("0.25"),
        cleaning_invoice_recipient="owner_company",
        cleaning_rut_applicable=False,
        object_cost_per_booking=Decimal("200"),
        last_minute_enabled=True, last_minute_start_days=20,
        last_minute_max_discount=Decimal("0.20"),
        weekly_discount_pct=Decimal("10"), monthly_discount_pct=Decimal("15"),
        latitude=Decimal("59.2775"), longitude=Decimal("17.9860"),
        investment_balance=Decimal("0"), is_active=True,
    )
    db.add(prop); db.flush()
    print(f"✓ Strandvilla skapad (id={prop.id})")
    return prop


if __name__ == "__main__":
    print("\n=== Norli Pricing Engine — Databasinitiering ===\n")
    create_tables()

    db = SessionLocal()
    try:
        seed_cleaning_profiles(db)
        seed_pricing_categories(db)
        prop = seed_enskede(db)
        seed_trosa(db)
        seed_alta(db)
        seed_alvsjö(db)
        seed_strandvilla(db)
        seed_ronneby(db)
        seed_island_cottage(db)
        seed_seafront_cottage(db)
        seed_klassbol(db)
        seed_seasons(db)
        seed_calendar_events(db)
        seed_local_events(db)
        seed_enskede_rules(db, prop)
        db.commit()
        print("\n✓ Allt klart! Databasen är redo.\n")
    except Exception as e:
        db.rollback()
        print(f"\n✗ Fel: {e}\n")
        raise
    finally:
        db.close()
