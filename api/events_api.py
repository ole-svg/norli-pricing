"""Endpoints for kalenderhandelser och lokala evenemang."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from datetime import date
from db.session import get_db
from db.models import CalendarEvent, LocalEvent

router = APIRouter()


# ── Schema ──────────────────────────────────────────────────────────────────

class LocalEventCreate(BaseModel):
    name: str
    start_date: date
    end_date: date
    price_multiplier: float = 1.25
    event_type: str = "other"
    location: str = "Stockholm"
    venue: Optional[str] = None
    description: Optional[str] = None


class LocalEventUpdate(BaseModel):
    name: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    price_multiplier: Optional[float] = None
    event_type: Optional[str] = None
    location: Optional[str] = None
    venue: Optional[str] = None
    description: Optional[str] = None


def _event_dict(e: LocalEvent) -> dict:
    return {
        "id": e.id,
        "name": e.name,
        "event_type": e.event_type,
        "location": e.location,
        "venue": e.venue,
        "start_date": str(e.start_date),
        "end_date": str(e.end_date),
        "price_multiplier": str(e.multiplier),
        "description": getattr(e, "description", None),
    }


# ── Calendar events (read-only) ──────────────────────────────────────────────

@router.get("/calendar-events")
def list_calendar_events(db: Session = Depends(get_db)):
    events = db.query(CalendarEvent).order_by(CalendarEvent.start_date).all()
    return [
        {
            "id": e.id,
            "name": e.name,
            "event_type": e.event_type,
            "start_date": str(e.start_date),
            "end_date": str(e.end_date),
            "multiplier": str(e.multiplier),
            "priority": e.priority,
        }
        for e in events
    ]


# ── Local events CRUD ────────────────────────────────────────────────────────

@router.get("/local-events")
def list_local_events(db: Session = Depends(get_db)):
    events = db.query(LocalEvent).order_by(LocalEvent.start_date).all()
    return [_event_dict(e) for e in events]


@router.get("/local-events/{event_id}")
def get_local_event(event_id: int, db: Session = Depends(get_db)):
    e = db.get(LocalEvent, event_id)
    if not e:
        raise HTTPException(status_code=404, detail="Event not found")
    return _event_dict(e)


@router.post("/local-events", status_code=201)
def create_local_event(body: LocalEventCreate, db: Session = Depends(get_db)):
    if body.end_date < body.start_date:
        raise HTTPException(status_code=422, detail="end_date must be >= start_date")
    e = LocalEvent(
        name=body.name,
        start_date=body.start_date,
        end_date=body.end_date,
        multiplier=body.price_multiplier,
        event_type=body.event_type,
        location=body.location or "Stockholm",
        venue=body.venue,
    )
    db.add(e)
    db.commit()
    db.refresh(e)
    return _event_dict(e)


@router.patch("/local-events/{event_id}")
def update_local_event(event_id: int, body: LocalEventUpdate, db: Session = Depends(get_db)):
    e = db.get(LocalEvent, event_id)
    if not e:
        raise HTTPException(status_code=404, detail="Event not found")
    if body.name is not None:
        e.name = body.name
    if body.start_date is not None:
        e.start_date = body.start_date
    if body.end_date is not None:
        e.end_date = body.end_date
    if body.price_multiplier is not None:
        e.multiplier = body.price_multiplier
    if body.event_type is not None:
        e.event_type = body.event_type
    if body.location is not None:
        e.location = body.location
    if body.venue is not None:
        e.venue = body.venue
    db.commit()
    db.refresh(e)
    return _event_dict(e)


@router.delete("/local-events/{event_id}", status_code=204)
def delete_local_event(event_id: int, db: Session = Depends(get_db)):
    e = db.get(LocalEvent, event_id)
    if not e:
        raise HTTPException(status_code=404, detail="Event not found")
    db.delete(e)
    db.commit()
    return None
