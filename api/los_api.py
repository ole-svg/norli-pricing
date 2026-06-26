"""
api/los_api.py
LOS-prissättning API — hämta och konfigurera LOS-tabeller per objekt.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from decimal import Decimal
from typing import Optional

from db.session import get_db
from db.models import Property
from engine.los import (
    get_los_multiplier, get_min_stay, get_los_table_for_publishing,
    get_cleaning_cost, is_high_season_date, CLEANING_CURVES
)
from datetime import date

router = APIRouter(prefix="/los", tags=["LOS-prissättning"])


@router.get("/{crm_property_id}")
def get_los_profile(
    crm_property_id: str,
    db: Session = Depends(get_db),
):
    """
    Hämtar LOS-profil och multiplikatortabell för ett objekt.
    Visar städkostnadskurva och lönsamhetsanalys per antal nätter.
    """
    prop = db.query(Property).filter(
        Property.crm_property_id == crm_property_id
    ).first()
    if not prop:
        raise HTTPException(404, f"Objekt {crm_property_id} hittades inte")

    profile = getattr(prop, "pricing_profile", "urban_hotel") or "urban_hotel"
    weekly_disc = getattr(prop, "weekly_discount_pct", None)
    monthly_disc = getattr(prop, "monthly_discount_pct", None)
    base_price = float(prop.base_price) if prop.base_price else 4000

    # Bygg tabell för båda säsongerna
    rows = []
    for nights in [1, 2, 3, 4, 5, 6, 7, 14, 28]:
        for is_hs in ([False, True] if profile == "destination" else [False]):
            los = get_los_multiplier(
                profile=profile,
                nights=nights,
                weekly_discount_pct=weekly_disc,
                monthly_discount_pct=monthly_disc,
                is_high_season=is_hs,
            )
            cleaning = get_cleaning_cost(profile, nights)
            price_per_night = base_price * float(los.multiplier)
            total = price_per_night * nights
            # Enkel lönsamhetskoll: ägarens netto per natt
            gross = price_per_night
            platform = gross * 0.03
            vat = gross * 12 / 112
            settlement = gross - platform - vat
            owner_gross = settlement * 0.82
            cleaning_per_night = float(cleaning.cost) / nights
            owner_net_per_night = owner_gross - cleaning_per_night - (200 / nights)

            rows.append({
                "nights": nights,
                "season": "högsäsong" if is_hs else "lågsäsong",
                "multiplier": float(los.multiplier),
                "pct_change": round((float(los.multiplier) - 1.0) * 100, 1),
                "label": los.label,
                "price_per_night": round(price_per_night),
                "cleaning_hours": float(cleaning.hours),
                "cleaning_cost": float(cleaning.cost),
                "owner_net_per_night": round(owner_net_per_night),
                "profitable": owner_net_per_night > 0,
            })

    return {
        "crm_property_id": crm_property_id,
        "profile": profile,
        "base_price": base_price,
        "weekly_discount_pct": float(weekly_disc) if weekly_disc else None,
        "monthly_discount_pct": float(monthly_disc) if monthly_disc else None,
        "los_table": rows,
    }


@router.get("/{crm_property_id}/publishing-table")
def get_publishing_table(
    crm_property_id: str,
    is_high_season: bool = False,
    db: Session = Depends(get_db),
):
    """
    Returnerar LOS-tabellen i format redo för PriceLabs-publicering.
    """
    prop = db.query(Property).filter(
        Property.crm_property_id == crm_property_id
    ).first()
    if not prop:
        raise HTTPException(404, f"Objekt {crm_property_id} hittades inte")

    profile = getattr(prop, "pricing_profile", "urban_hotel") or "urban_hotel"
    weekly_disc = getattr(prop, "weekly_discount_pct", None)
    monthly_disc = getattr(prop, "monthly_discount_pct", None)

    table = get_los_table_for_publishing(
        profile=profile,
        is_high_season=is_high_season,
        weekly_discount_pct=weekly_disc,
        monthly_discount_pct=monthly_disc,
    )
    return {
        "crm_property_id": crm_property_id,
        "profile": profile,
        "is_high_season": is_high_season,
        "table": table,
    }


@router.get("/{crm_property_id}/min-stay")
def get_min_stay_info(
    crm_property_id: str,
    target_date: date,
    db: Session = Depends(get_db),
):
    """Hämtar min stay för ett specifikt datum."""
    prop = db.query(Property).filter(
        Property.crm_property_id == crm_property_id
    ).first()
    if not prop:
        raise HTTPException(404, f"Objekt {crm_property_id} hittades inte")

    profile = getattr(prop, "pricing_profile", "urban_hotel") or "urban_hotel"
    hs = is_high_season_date(target_date)
    min_stay = get_min_stay(profile=profile, target_date=target_date, is_high_season=hs)

    return {
        "crm_property_id": crm_property_id,
        "date": str(target_date),
        "min_stay": min_stay,
        "is_high_season": hs,
        "profile": profile,
    }
