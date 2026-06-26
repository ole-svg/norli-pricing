"""
Endpoints för priser.

Hämtar beräknade priser och triggar omräkning.
Plattformsadaptrar (Airbnb, Booking.com) läser härifrån.
"""

from datetime import date, timedelta
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload

from db.session import get_db
from db.models import Property, Season, CalendarEvent, LocalEvent, PriceSnapshot
from engine.pricing import PricingEngine

router = APIRouter()


# ─── Pydantic-scheman ────────────────────────────────────────────────────────

class PriceSnapshotResponse(BaseModel):
    """Prisinformation för ett specifikt datum."""
    property_id: int
    date: date
    recommended_price: Decimal
    published_price: Optional[Decimal]
    explanation: str
    is_clamped_floor: bool
    is_clamped_ceiling: bool
    engine_version: str
    manually_overridden: Optional[bool] = False

    class Config:
        from_attributes = True


class RecalculateResponse(BaseModel):
    """Svar efter omräkning."""
    property_crm_id: str
    days_calculated: int
    message: str


# ─── Endpoints ───────────────────────────────────────────────────────────────

@router.get("/{crm_property_id}", response_model=list[PriceSnapshotResponse])
def get_prices(
    crm_property_id: str,
    start_date: date = Query(default=None),
    end_date: date = Query(default=None),
    db: Session = Depends(get_db),
):
    """
    Hämtar beräknade priser för ett objekt över ett datumintervall.

    Om start/end saknas returneras dagens datum + 365 dagar framåt.
    """
    if start_date is None:
        start_date = date.today()
    if end_date is None:
        end_date = start_date + timedelta(days=365)

    prop = db.query(Property).filter(Property.crm_property_id == crm_property_id).first()
    if not prop:
        raise HTTPException(status_code=404, detail=f"Objekt '{crm_property_id}' hittades inte.")

    from sqlalchemy import text
    rows = db.execute(text(
        "SELECT property_id, date, recommended_price, published_price, "
        "explanation, is_clamped_floor, is_clamped_ceiling, engine_version, "
        "COALESCE(manually_overridden, FALSE) as manually_overridden "
        "FROM price_snapshots "
        "WHERE property_id = :prop_id AND date >= :start AND date <= :end "
        "ORDER BY date"
    ), {"prop_id": prop.id, "start": start_date, "end": end_date}).fetchall()

    return [
        PriceSnapshotResponse(
            property_id=r[0],
            date=r[1],
            recommended_price=r[2],
            published_price=r[3],
            explanation=r[4] or "",
            is_clamped_floor=r[5] or False,
            is_clamped_ceiling=r[6] or False,
            engine_version=r[7] or "1.0.0",
            manually_overridden=bool(r[8]),
        )
        for r in rows
    ]


@router.post("/{crm_property_id}/recalculate", response_model=RecalculateResponse)
def recalculate_prices(
    crm_property_id: str,
    days_ahead: int = Query(default=365, ge=1, le=730),
    db: Session = Depends(get_db),
):
    """
    Triggar omräkning av priser för ett objekt.

    Räknar om priserna för 'days_ahead' dagar framåt (standard: 365).
    Uppdaterar befintliga snapshots eller skapar nya.

    Kallas:
    - Manuellt via API när regler ändras
    - Nattligen av schemalagda jobb (alla objekt)
    - Av Airbnb-adaptern vid behov
    """
    # Hämta objektet med dess prisregler
    prop = (
        db.query(Property)
        .options(joinedload(Property.price_rules))
        .filter(Property.crm_property_id == crm_property_id)
        .first()
    )
    if not prop:
        raise HTTPException(status_code=404, detail=f"Objekt '{crm_property_id}' hittades inte.")

    # Hämta globala data
    seasons = db.query(Season).all()
    calendar_events = db.query(CalendarEvent).all()
    local_events = db.query(LocalEvent).all()

    # Kör regelmotorn
    engine = PricingEngine(prop, seasons, calendar_events, local_events)
    start = date.today()
    end = start + timedelta(days=days_ahead - 1)
    results = engine.calculate_range(start, end)

    # Spara snapshots (upsert: uppdatera om den finns, skapa annars)
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

    return RecalculateResponse(
        property_crm_id=crm_property_id,
        days_calculated=count,
        message=f"Priserna för '{prop.name}' är omräknade för {count} dagar ({start} – {end}).",
    )


@router.patch("/{crm_property_id}/{price_date}/published", response_model=PriceSnapshotResponse)
def set_published_price(
    crm_property_id: str,
    price_date: date,
    published_price: Decimal = Query(...),
    db: Session = Depends(get_db),
):
    """
    Sätter det publicerade priset för ett specifikt datum.

    Norli kan avvika från motorns rekommendation.
    Både rekommenderat och publicerat pris sparas för framtida analys.
    """
    prop = db.query(Property).filter(Property.crm_property_id == crm_property_id).first()
    if not prop:
        raise HTTPException(status_code=404, detail=f"Objekt '{crm_property_id}' hittades inte.")

    snapshot = (
        db.query(PriceSnapshot)
        .filter(
            PriceSnapshot.property_id == prop.id,
            PriceSnapshot.date == price_date,
        )
        .first()
    )
    if not snapshot:
        raise HTTPException(status_code=404, detail=f"Inget prissnapshot för {price_date}.")

    snapshot.published_price = published_price
    db.commit()
    db.refresh(snapshot)
    return snapshot

@router.post("/{crm_property_id}/override")
def override_price(
    crm_property_id: str,
    body: dict,
    db: Session = Depends(get_db),
):
    """Sätter ett manuellt pris för ett datum. Åsidosätter prismotorns värde."""
    from datetime import date as date_type
    prop = db.query(Property).filter(Property.crm_property_id == crm_property_id).first()
    if not prop:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Objekt '{crm_property_id}' hittades inte.")

    date_str = body.get("date")
    price = body.get("price")
    if not date_str or not price:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="date och price krävs.")

    snap = db.query(PriceSnapshot).filter(
        PriceSnapshot.property_id == prop.id,
        PriceSnapshot.date == date_str,
    ).first()

    from sqlalchemy import text
    if snap:
        db.execute(text(
            "UPDATE price_snapshots SET published_price = :price, manually_overridden = TRUE "
            "WHERE property_id = :prop_id AND date = :date"
        ), {"price": str(price), "prop_id": prop.id, "date": date_str})
    else:
        db.execute(text(
            "INSERT INTO price_snapshots (property_id, date, recommended_price, published_price, "
            "manually_overridden, engine_version, explanation, is_clamped_floor, is_clamped_ceiling) "
            "VALUES (:prop_id, :date, :price, :price, TRUE, 'manual', 'Manuellt satt pris', FALSE, FALSE)"
        ), {"prop_id": prop.id, "date": date_str, "price": str(price)})

    db.commit()
    return {"success": True, "date": date_str, "price": price, "manually_overridden": True}


@router.delete("/{crm_property_id}/override")
def reset_price(
    crm_property_id: str,
    date: str,
    db: Session = Depends(get_db),
):
    """Återställer ett manuellt pris till prismotorns recommended_price."""
    prop = db.query(Property).filter(Property.crm_property_id == crm_property_id).first()
    if not prop:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Objekt '{crm_property_id}' hittades inte.")

    snap = db.query(PriceSnapshot).filter(
        PriceSnapshot.property_id == prop.id,
        PriceSnapshot.date == date,
    ).first()

    if snap:
        snap.published_price = snap.recommended_price
        snap.manually_overridden = False
        db.commit()
        return {"success": True, "date": date, "price": float(snap.recommended_price), "manually_overridden": False}

    from fastapi import HTTPException
    raise HTTPException(status_code=404, detail=f"Ingen prissnapshot för {date}.")
