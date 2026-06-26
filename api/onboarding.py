"""
Onboarding-endpoint: skapa nytt objekt med full konfiguration.
"""
import re
from decimal import Decimal
from typing import Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import text

from db.session import get_db
from db.models import Property

router = APIRouter(prefix="/onboarding", tags=["Onboarding"])

CLEANING_COMPANIES = [
    {"id": "hustrend", "name": "Hustrend Sverige AB", "region": "Stockholm + Trosa"},
    {"id": "plus55",   "name": "Plus55",              "region": "Ronneby"},
    {"id": "buskhaga", "name": "Buskhaga Städ",        "region": "Klassbol"},
    {"id": "sam_kiander", "name": "Sam Kiander",       "region": "Oxelösund"},
]

PRICING_PROFILES = [
    {"id": "urban_hotel",   "name": "Urban / Innerstadsboende",    "desc": "Enskede, Älta, Älvsjö — cityläge, eventdrivet"},
    {"id": "destination",   "name": "Destination / Fritidshus",    "desc": "Trosa, Ronneby, Djurö — säsongsstyrt"},
]


class OnboardingCreate(BaseModel):
    # Steg 1 — Objektinfo
    name: str
    address: str
    property_type: str = "villa"
    bedrooms: int
    max_guests: int
    airbnb_listing_id: Optional[str] = None
    ical_url: Optional[str] = None

    # Steg 2 — Ägare (valfritt)
    owner_id: Optional[int] = None  # befintlig ägare

    # Steg 3 — Städbolag
    cleaning_company_id: Optional[str] = None

    # Steg 4 — Prissättning
    pricing_profile: str = "destination"
    base_price: Decimal = Decimal("1500")
    price_floor: Optional[Decimal] = None
    price_ceiling: Optional[Decimal] = None
    owner_share_pct: Decimal = Decimal("0.82")
    norli_share_pct: Decimal = Decimal("0.18")
    owner_net_floor: Decimal = Decimal("900")
    owner_net_target: Decimal = Decimal("1600")
    min_booking_net: Decimal = Decimal("3000")
    min_stay_default: int = 2


class OnboardingResponse(BaseModel):
    success: bool
    crm_property_id: str
    property_id: int
    message: str


@router.get("/cleaning-companies")
def get_cleaning_companies():
    return CLEANING_COMPANIES


@router.get("/pricing-profiles")
def get_pricing_profiles():
    return PRICING_PROFILES


@router.get("/owners-list")
def get_owners_list(db: Session = Depends(get_db)):
    """Lista befintliga ägare för dropdown."""
    try:
        result = db.execute(text("SELECT id, name, email FROM owners WHERE is_active = TRUE ORDER BY name"))
        rows = result.fetchall()
        return [{"id": r[0], "name": r[1], "email": r[2]} for r in rows]
    except Exception:
        return []


@router.post("")
def create_property(data: OnboardingCreate, db: Session = Depends(get_db)):
    """Skapa nytt objekt med full onboarding-konfiguration."""

    # Generera crm_property_id från namn
    slug = re.sub(r'[^a-z0-9]+', '-', data.name.lower()).strip('-')
    crm_id = slug[:50]

    # Kontrollera att ID inte redan finns
    existing = db.query(Property).filter(Property.crm_property_id == crm_id).first()
    if existing:
        crm_id = f"{crm_id}-{int(datetime.utcnow().timestamp()) % 10000}"

    # Bygg defaults baserade på prisprofil
    if data.pricing_profile == "urban_hotel":
        min_stay_weekend = 2
        min_stay_highseason = 3
        event_sensitivity = "high"
    else:
        min_stay_weekend = 3
        min_stay_highseason = 4
        event_sensitivity = "medium"

    prop = Property(
        crm_property_id=crm_id,
        airbnb_listing_id=data.airbnb_listing_id,
        name=data.name,
        capacity=data.max_guests,
        bedrooms=data.bedrooms,
        bathrooms=1,
        linen_included=True,
        max_guests=data.max_guests,
        base_price=data.base_price,
        pricing_profile=data.pricing_profile,
        pricing_strategy="balanced",
        pricing_category_code="STOCKHOLM_URBAN_EVENT" if data.pricing_profile == "urban_hotel" else "DESTINATION_SEASONAL",
        price_floor=data.price_floor,
        price_ceiling=data.price_ceiling,
        owner_share_pct=data.owner_share_pct,
        norli_share_pct=data.norli_share_pct,
        owner_net_floor=data.owner_net_floor,
        owner_net_target=data.owner_net_target,
        owner_net_strong=Decimal("2300"),
        owner_net_event=Decimal("3000"),
        min_booking_net=data.min_booking_net,
        min_stay_default=data.min_stay_default,
        min_stay_weekend=min_stay_weekend,
        min_stay_highseason=min_stay_highseason,
        min_stay_event=2,
        allow_one_night=data.pricing_profile == "urban_hotel",
        airbnb_fee_model="split_fee",
        airbnb_host_fee_pct=Decimal("0.03"),
        vat_rate=Decimal("0.12"),
        revenue_model="commission",
        owner_type="private_person",
        cleaning_hourly_rate=Decimal("500"),
        cleaning_base_hours=Decimal("3.0"),
        cleaning_base_guests=data.max_guests,
        cleaning_min_hours=Decimal("3.0"),
        cleaning_max_hours=Decimal("8.0"),
        cleaning_hours_per_bedroom=Decimal("0.5"),
        cleaning_hours_per_bathroom=Decimal("0.5"),
        cleaning_hours_per_guest=Decimal("0.25"),
        cleaning_extra_hours_per_night=Decimal("0.2"),
        cleaning_night_threshold=3,
        cleaning_invoice_recipient="owner_company",
        cleaning_rut_applicable=False,
        last_minute_enabled=False,
        event_sensitivity=event_sensitivity,
        rounding_rule="nearest_10",
        object_cost_per_booking=Decimal("200"),
        investment_balance=Decimal("0"),
        investment_recoupment_mode="auto_full",
        is_active=True,
    )

    db.add(prop)
    db.commit()
    db.refresh(prop)

    # Spara iCal-URL om angiven (för framtida synk)
    if data.ical_url:
        try:
            db.execute(text(
                "INSERT INTO property_ical_urls (property_id, url, created_at) "
                "VALUES (:pid, :url, NOW()) ON CONFLICT DO NOTHING"
            ), {"pid": prop.id, "url": data.ical_url})
            db.commit()
        except Exception:
            pass  # Tabellen kanske inte finns ännu

    return {
        "success": True,
        "crm_property_id": crm_id,
        "property_id": prop.id,
        "message": f"Objektet {data.name} skapades med ID {crm_id}"
    }
