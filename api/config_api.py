"""
api/config_api.py
Objektkonfiguration — läs och spara inställningar per objekt.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel

from db.session import get_db
from db.models import Property

router = APIRouter(prefix="/config", tags=["Objektkonfiguration"])


class PropertyConfigUpdate(BaseModel):
    """Alla konfigurerbara parametrar för ett objekt."""
    # Grundinfo
    name: Optional[str] = None
    base_price: Optional[float] = None
    capacity: Optional[int] = None
    max_guests: Optional[int] = None

    # Lönsamhetsmål per natt (ägarens netto)
    owner_net_floor: Optional[float] = None
    owner_net_target: Optional[float] = None
    owner_net_strong: Optional[float] = None
    owner_net_event: Optional[float] = None

    # Ekonomimodell
    norli_share_pct: Optional[float] = None
    airbnb_fee_model: Optional[str] = None
    airbnb_host_fee_pct: Optional[float] = None
    object_cost_per_booking: Optional[float] = None

    # LOS
    pricing_profile: Optional[str] = None
    weekly_discount_pct: Optional[float] = None
    monthly_discount_pct: Optional[float] = None

    # Pristak/golv
    price_floor: Optional[float] = None
    price_ceiling: Optional[float] = None

    # Minimum stay
    min_stay_default: Optional[int] = None
    min_stay_weekend: Optional[int] = None
    min_stay_highseason: Optional[int] = None
    min_stay_event: Optional[int] = None
    allow_one_night: Optional[bool] = None

    # Städ
    cleaning_base_guests: Optional[int] = None
    cleaning_min_hours: Optional[float] = None
    cleaning_hours_per_2_guests_above: Optional[float] = None

    # Last-minute
    last_minute_enabled: Optional[bool] = None
    last_minute_start_days: Optional[int] = None
    last_minute_max_discount: Optional[float] = None


@router.get("/{crm_property_id}")
def get_property_config(crm_property_id: str, db: Session = Depends(get_db)):
    """Hämtar fullständig konfiguration för ett objekt."""
    prop = db.query(Property).filter(
        Property.crm_property_id == crm_property_id
    ).first()
    if not prop:
        raise HTTPException(404, f"Objekt {crm_property_id} hittades inte")

    def d(val):
        return float(val) if val is not None else None

    return {
        "crm_property_id": prop.crm_property_id,
        "name": prop.name,
        "base_price": d(prop.base_price),
        "capacity": prop.capacity,
        "max_guests": prop.max_guests,
        "pricing_profile": prop.pricing_profile,

        # Lönsamhetsmål
        "owner_net_floor": d(getattr(prop, "owner_net_floor", None)),
        "owner_net_target": d(getattr(prop, "owner_net_target", None)),
        "owner_net_strong": d(getattr(prop, "owner_net_strong", None)),
        "owner_net_event": d(getattr(prop, "owner_net_event", None)),

        # Ekonomi
        "norli_share_pct": d(getattr(prop, "norli_share_pct", None)) or 0.18,
        "airbnb_fee_model": getattr(prop, "airbnb_fee_model", "split_fee"),
        "airbnb_host_fee_pct": d(getattr(prop, "airbnb_host_fee_pct", None)) or 0.03,
        "object_cost_per_booking": d(prop.object_cost_per_booking),

        # Pristak/golv
        "price_floor": d(prop.price_floor),
        "price_ceiling": d(prop.price_ceiling),

        # LOS
        "weekly_discount_pct": d(prop.weekly_discount_pct),
        "monthly_discount_pct": d(prop.monthly_discount_pct),

        # Minimum stay
        "min_stay_default": getattr(prop, "min_stay_default", 1),
        "min_stay_weekend": getattr(prop, "min_stay_weekend", 2),
        "min_stay_highseason": getattr(prop, "min_stay_highseason", 3),
        "min_stay_event": getattr(prop, "min_stay_event", 2),
        "allow_one_night": getattr(prop, "allow_one_night", True),

        # Städ
        "cleaning_base_guests": prop.cleaning_base_guests,
        "cleaning_min_hours": d(prop.cleaning_min_hours),
        "cleaning_hours_per_2_guests_above": d(prop.cleaning_hours_per_2_guests_above),

        # Last-minute
        "last_minute_enabled": prop.last_minute_enabled,
        "last_minute_start_days": prop.last_minute_start_days,
        "last_minute_max_discount": d(prop.last_minute_max_discount),

        # Beräknat lönsamhetsgolv per vistelselängd
        "profitability_floors": _calculate_profitability_floors(prop),
    }


def _calculate_profitability_floors(prop: Property) -> list[dict]:
    """
    Räknar ut minimalt bruttopris per vistelselängd baserat på lönsamhetsmål.
    Formel: min_gross = (nettomål × nätter + städ + objektkostnad) / konversionsfaktor
    """
    from engine.los import get_cleaning_cost, CLEANING_CURVES

    profile = getattr(prop, "pricing_profile", "urban_hotel") or "urban_hotel"
    norli_pct = float(getattr(prop, "norli_share_pct", None) or 0.18)
    airbnb_pct = float(getattr(prop, "airbnb_host_fee_pct", None) or 0.03)
    vat_factor = 12 / 112  # logimoms
    obj_cost = float(prop.object_cost_per_booking or 200)

    # Konversionsfaktor: hur mycket av brutto går till ägaren före städ
    conversion = (1 - airbnb_pct - vat_factor) * (1 - norli_pct)

    target = float(getattr(prop, "owner_net_target", None) or 1600)
    floor = float(getattr(prop, "owner_net_floor", None) or 900)

    rows = []
    for nights in [1, 2, 3, 4, 5, 6, 7, 14, 28]:
        cleaning = get_cleaning_cost(profile, nights)
        cleaning_cost = float(cleaning.cost)

        min_gross_target = (target * nights + cleaning_cost + obj_cost) / conversion
        min_gross_floor = (floor * nights + cleaning_cost + obj_cost) / conversion

        rows.append({
            "nights": nights,
            "min_gross_target": round(min_gross_target / 10) * 10,
            "min_gross_floor": round(min_gross_floor / 10) * 10,
            "min_per_night_target": round(min_gross_target / nights / 10) * 10,
            "min_per_night_floor": round(min_gross_floor / nights / 10) * 10,
            "cleaning_cost": cleaning_cost,
        })
    return rows


@router.patch("/{crm_property_id}")
def update_property_config(
    crm_property_id: str,
    updates: PropertyConfigUpdate,
    db: Session = Depends(get_db),
):
    """Uppdaterar konfiguration för ett objekt. Bara angivna fält uppdateras."""
    prop = db.query(Property).filter(
        Property.crm_property_id == crm_property_id
    ).first()
    if not prop:
        raise HTTPException(404, f"Objekt {crm_property_id} hittades inte")

    field_map = {
        "name": ("name", str),
        "base_price": ("base_price", Decimal),
        "capacity": ("capacity", int),
        "max_guests": ("max_guests", int),
        "owner_net_floor": ("owner_net_floor", Decimal),
        "owner_net_target": ("owner_net_target", Decimal),
        "owner_net_strong": ("owner_net_strong", Decimal),
        "owner_net_event": ("owner_net_event", Decimal),
        "norli_share_pct": ("norli_share_pct", Decimal),
        "airbnb_fee_model": ("airbnb_fee_model", str),
        "airbnb_host_fee_pct": ("airbnb_host_fee_pct", Decimal),
        "object_cost_per_booking": ("object_cost_per_booking", Decimal),
        "pricing_profile": ("pricing_profile", str),
        "weekly_discount_pct": ("weekly_discount_pct", Decimal),
        "monthly_discount_pct": ("monthly_discount_pct", Decimal),
        "price_floor": ("price_floor", Decimal),
        "price_ceiling": ("price_ceiling", Decimal),
        "min_stay_default": ("min_stay_default", int),
        "min_stay_weekend": ("min_stay_weekend", int),
        "min_stay_highseason": ("min_stay_highseason", int),
        "min_stay_event": ("min_stay_event", int),
        "allow_one_night": ("allow_one_night", bool),
        "cleaning_base_guests": ("cleaning_base_guests", int),
        "cleaning_min_hours": ("cleaning_min_hours", Decimal),
        "cleaning_hours_per_2_guests_above": ("cleaning_hours_per_2_guests_above", Decimal),
        "last_minute_enabled": ("last_minute_enabled", bool),
        "last_minute_start_days": ("last_minute_start_days", int),
        "last_minute_max_discount": ("last_minute_max_discount", Decimal),
    }

    updated = []
    for field, (attr, cast) in field_map.items():
        val = getattr(updates, field, None)
        if val is not None:
            try:
                setattr(prop, attr, cast(val))
                updated.append(field)
            except Exception:
                pass

    db.commit()
    return {"updated": updated, "crm_property_id": crm_property_id}
