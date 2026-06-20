"""
api/owner_periods.py
Hantering av ägarperioder — manuellt inmatade förvaltningsfönster.
"""

from datetime import date
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from db.session import get_db
from db.models import OwnerPeriod, Property

router = APIRouter()


class OwnerPeriodCreate(BaseModel):
    crm_property_id: str
    period_start: date
    period_end: date
    label: str = "Ägarperiod"
    cleaning_needed: bool = True
    cleaning_from: Optional[date] = None
    notes: Optional[str] = None


class OwnerPeriodUpdate(BaseModel):
    period_start: Optional[date] = None
    period_end: Optional[date] = None
    label: Optional[str] = None
    cleaning_needed: Optional[bool] = None
    cleaning_from: Optional[date] = None
    notes: Optional[str] = None


def _period_dict(p: OwnerPeriod, crm_id: str) -> dict:
    return {
        "id": p.id,
        "property_id": p.property_id,
        "crm_property_id": crm_id,
        "period_start": str(p.period_start),
        "period_end": str(p.period_end),
        "label": p.label,
        "cleaning_needed": p.cleaning_needed,
        "cleaning_from": str(p.cleaning_from) if p.cleaning_from else None,
        "notes": p.notes,
        "created_at": p.created_at.isoformat() if p.created_at else None,
    }


@router.get("/owner-periods")
def list_owner_periods(
    crm_property_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Hämta alla ägarperioder, ev. filtrerade per objekt."""
    q = db.query(OwnerPeriod, Property).join(
        Property, OwnerPeriod.property_id == Property.id
    )
    if crm_property_id:
        q = q.filter(Property.crm_property_id == crm_property_id)
    results = q.order_by(OwnerPeriod.period_start).all()
    return [_period_dict(p, prop.crm_property_id) for p, prop in results]


@router.post("/owner-periods")
def create_owner_period(data: OwnerPeriodCreate, db: Session = Depends(get_db)):
    """Skapa ett nytt förvaltningsfönster."""
    prop = db.query(Property).filter(
        Property.crm_property_id == data.crm_property_id
    ).first()
    if not prop:
        raise HTTPException(404, f"Objekt {data.crm_property_id} finns ej")
    
    if data.period_end <= data.period_start:
        raise HTTPException(422, "period_end måste vara efter period_start")
    
    period = OwnerPeriod(
        property_id=prop.id,
        period_start=data.period_start,
        period_end=data.period_end,
        label=data.label,
        cleaning_needed=data.cleaning_needed,
        cleaning_from=data.cleaning_from,
        notes=data.notes,
    )
    db.add(period)
    db.commit()
    db.refresh(period)
    return _period_dict(period, data.crm_property_id)


@router.patch("/owner-periods/{period_id}")
def update_owner_period(
    period_id: int,
    data: OwnerPeriodUpdate,
    db: Session = Depends(get_db)
):
    """Uppdatera ett förvaltningsfönster."""
    period = db.get(OwnerPeriod, period_id)
    if not period:
        raise HTTPException(404, "Ägarperiod ej hittad")
    prop = db.get(Property, period.property_id)
    
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(period, field, value)
    db.commit()
    return _period_dict(period, prop.crm_property_id if prop else "unknown")


@router.delete("/owner-periods/{period_id}")
def delete_owner_period(period_id: int, db: Session = Depends(get_db)):
    """Ta bort ett förvaltningsfönster."""
    period = db.get(OwnerPeriod, period_id)
    if not period:
        raise HTTPException(404, "Ägarperiod ej hittad")
    db.delete(period)
    db.commit()
    return {"deleted": period_id}
