"""
Endpoints för objekt (properties).

CRM pushar hit när ett objekt skapas eller uppdateras.
Motorn speglar de attribut den behöver för prissättning.
"""

from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db.session import get_db
from db.models import Property

router = APIRouter()


# ─── Pydantic-scheman (request/response-format) ─────────────────────────────

class PropertyCreate(BaseModel):
    """Data som krävs för att skapa ett nytt objekt."""
    crm_property_id: str
    name: str
    capacity: int
    base_price: Decimal
    pricing_strategy: str = "balanced"

    # Kostnader (valfria i v1, reserverade för ägarnetto-beräkning)
    cleaning_cost: Optional[Decimal] = None
    norli_commission_pct: Optional[Decimal] = None
    other_costs: Optional[Decimal] = None

    # Skyddsräcken
    price_floor: Optional[Decimal] = None
    price_ceiling: Optional[Decimal] = None
    min_margin: Optional[Decimal] = None
    min_owner_net: Optional[Decimal] = None


class PropertyPatch(BaseModel):
    """Partiell uppdatering — alla fält valfria."""
    name: Optional[str] = None
    capacity: Optional[int] = None
    base_price: Optional[Decimal] = None
    pricing_strategy: Optional[str] = None
    pricing_profile: Optional[str] = None
    pricing_category_code: Optional[str] = None
    cleaning_profile_code: Optional[str] = None
    price_floor: Optional[Decimal] = None
    price_ceiling: Optional[Decimal] = None
    rounding_rule: Optional[str] = None
    event_sensitivity: Optional[str] = None
    weekly_discount_pct: Optional[Decimal] = None
    monthly_discount_pct: Optional[Decimal] = None
    last_minute_enabled: Optional[bool] = None
    last_minute_start_days: Optional[int] = None
    last_minute_max_discount: Optional[Decimal] = None
    last_minute_min_price: Optional[Decimal] = None
    owner_type: Optional[str] = None
    owner_share_pct: Optional[Decimal] = None
    norli_share_pct: Optional[Decimal] = None
    cleaning_hourly_rate: Optional[Decimal] = None
    cleaning_base_guests: Optional[int] = None
    cleaning_min_hours: Optional[Decimal] = None
    cleaning_max_hours: Optional[Decimal] = None
    cleaning_invoice_recipient: Optional[str] = None
    cleaning_rut_applicable: Optional[bool] = None
    object_cost_per_booking: Optional[Decimal] = None
    object_cost_per_night: Optional[Decimal] = None
    max_guests: Optional[int] = None
    bedrooms: Optional[int] = None
    bathrooms: Optional[int] = None
    cleaning_fee_per_stay: Optional[Decimal] = None
    cleaning_fee_short_stay: Optional[Decimal] = None
    pet_fee_per_stay: Optional[Decimal] = None
    extra_guest_fee_per_night: Optional[Decimal] = None
    extra_guest_fee_trigger: Optional[int] = None
    airbnb_listing_id: Optional[str] = None


class PropertyResponse(BaseModel):
    """Vad API:et returnerar för ett objekt."""
    id: int
    crm_property_id: str
    name: str
    capacity: Optional[int] = None
    max_guests: Optional[int] = None
    bedrooms: Optional[int] = None
    bathrooms: Optional[int] = None
    base_price: Decimal
    pricing_strategy: Optional[str] = None
    pricing_category_code: Optional[str] = None
    cleaning_profile_code: Optional[str] = None
    price_floor: Optional[Decimal] = None
    price_ceiling: Optional[Decimal] = None
    rounding_rule: Optional[str] = None
    event_sensitivity: Optional[str] = None
    owner_share_pct: Optional[Decimal] = None
    norli_share_pct: Optional[Decimal] = None
    platform_fee_rate: Optional[Decimal] = None
    vat_rate: Optional[Decimal] = None
    owner_type: Optional[str] = None
    cleaning_hourly_rate: Optional[Decimal] = None
    cleaning_base_guests: Optional[int] = None
    cleaning_min_hours: Optional[Decimal] = None
    cleaning_max_hours: Optional[Decimal] = None
    cleaning_hours_per_2_guests_above: Optional[Decimal] = None
    cleaning_hours_per_2_guests_below: Optional[Decimal] = None
    cleaning_invoice_recipient: Optional[str] = None
    cleaning_rut_applicable: Optional[bool] = None
    object_cost_per_booking: Optional[Decimal] = None
    object_cost_per_night: Optional[Decimal] = None
    object_cost_per_guest: Optional[Decimal] = None
    last_minute_enabled: Optional[bool] = None
    last_minute_start_days: Optional[int] = None
    last_minute_max_discount: Optional[Decimal] = None
    last_minute_min_price: Optional[Decimal] = None
    pet_fee_per_stay: Optional[Decimal] = None
    extra_guest_fee_per_night: Optional[Decimal] = None
    extra_guest_fee_trigger: Optional[int] = None
    admin_fee_per_stay: Optional[Decimal] = None
    linen_fee_per_stay: Optional[Decimal] = None
    local_fee_per_stay: Optional[Decimal] = None
    hotel_fee_per_stay: Optional[Decimal] = None
    is_active: bool
    airbnb_listing_id: Optional[str] = None

    class Config:
        from_attributes = True


# ─── Endpoints ───────────────────────────────────────────────────────────────

@router.post("/", response_model=PropertyResponse, status_code=201)
def create_property(data: PropertyCreate, db: Session = Depends(get_db)):
    """
    Skapar ett nytt objekt i prissättningsmotorn.
    Anropas av CRM när ett nytt objekt läggs till.
    """
    # Kontrollera att crm_property_id inte redan finns
    existing = db.query(Property).filter(Property.crm_property_id == data.crm_property_id).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"Objekt med crm_property_id '{data.crm_property_id}' finns redan.")

    prop = Property(**data.model_dump())
    db.add(prop)
    db.commit()
    db.refresh(prop)
    return prop


@router.get("/", response_model=list[PropertyResponse])
def list_properties(db: Session = Depends(get_db)):
    """Listar alla aktiva objekt."""
    return db.query(Property).filter(Property.is_active == True).all()


@router.get("/{crm_property_id}", response_model=PropertyResponse)
def get_property(crm_property_id: str, db: Session = Depends(get_db)):
    """Hämtar ett specifikt objekt med dess CRM-id."""
    prop = db.query(Property).filter(Property.crm_property_id == crm_property_id).first()
    if not prop:
        raise HTTPException(status_code=404, detail=f"Objekt '{crm_property_id}' hittades inte.")
    return prop


@router.patch("/{crm_property_id}", response_model=PropertyResponse)
def update_property(crm_property_id: str, data: PropertyPatch, db: Session = Depends(get_db)):
    """
    Uppdaterar ett objekts prisattribut.
    Anropas av CRM när objekt-data ändras.
    """
    prop = db.query(Property).filter(Property.crm_property_id == crm_property_id).first()
    if not prop:
        raise HTTPException(status_code=404, detail=f"Objekt '{crm_property_id}' hittades inte.")

    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(prop, key, value)

    db.commit()
    db.refresh(prop)
    return prop
