"""Endpoints for kalenderhandelser och lokala evenemang."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from db.session import get_db
from db.models import CalendarEvent, LocalEvent

router = APIRouter()

@router.get("/calendar-events")
def list_calendar_events(db: Session = Depends(get_db)):
    events = db.query(CalendarEvent).order_by(CalendarEvent.start_date).all()
    return [{"id": e.id, "name": e.name, "event_type": e.event_type,
             "start_date": str(e.start_date), "end_date": str(e.end_date),
             "multiplier": str(e.multiplier), "priority": e.priority} for e in events]

@router.get("/local-events")
def list_local_events(db: Session = Depends(get_db)):
    events = db.query(LocalEvent).order_by(LocalEvent.start_date).all()
    return [{"id": e.id, "name": e.name, "event_type": e.event_type,
             "location": e.location, "venue": e.venue,
             "start_date": str(e.start_date), "end_date": str(e.end_date),
             "multiplier": str(e.multiplier)} for e in events]
