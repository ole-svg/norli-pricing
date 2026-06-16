"""
AI-driven eventsökning för nya städer och objekt.

Användaren skriver "Kalmar 2026-2027" och AI:n söker,
analyserar och returnerar relevanta evenemang med
prisrekommendationer - redo att lägga till med ett klick.
"""

import os
import json
from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db.session import get_db
from db.models import LocalEvent, CalendarEvent
from decimal import Decimal

router = APIRouter()


class EventSuggestion(BaseModel):
    name: str
    event_type: str
    location: str
    venue: Optional[str] = None
    start_date: str
    end_date: str
    suggested_multiplier: float
    confidence: str  # "confirmed" | "recurring_estimate" | "watchlist"
    reason: str      # Varför detta event driver priser


class AIEventSearchRequest(BaseModel):
    city: str
    year: Optional[int] = None
    property_category: Optional[str] = "STOCKHOLM_URBAN_EVENT"


class AIEventSearchResponse(BaseModel):
    city: str
    events: list[EventSuggestion]
    summary: str
    generated_at: str


@router.post("/search", response_model=AIEventSearchResponse)
async def search_events_with_ai(request: AIEventSearchRequest):
    """
    Söker efter prisdrivande evenemang för en stad via Claude AI.
    Returnerar strukturerade eventförslag redo att läggas till i systemet.
    """
    year = request.year or date.today().year

    prompt = f"""Du är en expert på dynamisk prissättning för korttidsuthyrning (Airbnb).

Analysera följande stad och period och returnera en lista med evenemang som driver 
Airbnb-priser för den perioden.

Stad: {request.city}
Period: {year}-{year+1}
Objektkategori: {request.property_category}

Returnera EXAKT detta JSON-format och ingenting annat:
{{
  "summary": "Kort sammanfattning av säsongen och de viktigaste prisdrivarna för {request.city}",
  "events": [
    {{
      "name": "Eventnamn",
      "event_type": "concert|sport|fair|congress|festival|public_holiday|school_break|other",
      "location": "{request.city}",
      "venue": "Specifik arena/plats eller null",
      "start_date": "YYYY-MM-DD",
      "end_date": "YYYY-MM-DD",
      "suggested_multiplier": 1.25,
      "confidence": "confirmed|recurring_estimate|watchlist",
      "reason": "Kort förklaring varför detta driver priser"
    }}
  ]
}}

Regler:
- Inkludera BARA evenemang som faktiskt driver Airbnb-priser (ej lokala sm-evenemang utan publik)
- suggested_multiplier: 1.10-1.30 (litet), 1.30-1.60 (medium), 1.60-2.00 (stort)
- Inkludera helgdagar, skollov, konserter, mässor, kongresser, sport
- Max 30 evenemang
- Returnera bara JSON, inga förklaringar utanför JSON-strukturen"""

    try:
        import requests as _req
        resp = _req.post(
            "https://api.anthropic.com/v1/messages",
            headers={"Content-Type": "application/json"},
            json={
                "model": "claude-sonnet-4-6",
                "max_tokens": 4000,
                "messages": [{"role": "user", "content": prompt}]
            },
            timeout=30
        )

        if resp.status_code != 200:
            raise HTTPException(status_code=502, detail="AI-sökning misslyckades")

        data = resp.json()
        text = data["content"][0]["text"]

        # Parsa JSON
        text = text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        text = text.strip().rstrip("```").strip()

        result = json.loads(text)

        events = [EventSuggestion(**e) for e in result.get("events", [])]

        return AIEventSearchResponse(
            city=request.city,
            events=events,
            summary=result.get("summary", ""),
            generated_at=date.today().isoformat()
        )

    except json.JSONDecodeError as e:
        raise HTTPException(status_code=500, detail=f"Kunde inte parsa AI-svar: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class AddEventRequest(BaseModel):
    event: EventSuggestion
    property_id: Optional[str] = None


@router.post("/add")
async def add_ai_event(request: AddEventRequest, db: Session = Depends(get_db)):
    """Lägger till ett AI-föreslaget evenemang i databasen."""
    ev = request.event

    is_calendar = ev.event_type in ("public_holiday", "school_break")

    if is_calendar:
        existing = db.query(CalendarEvent).filter_by(name=ev.name).first()
        if existing:
            return {"status": "exists", "message": f'"{ev.name}" finns redan'}
        db.add(CalendarEvent(
            name=ev.name,
            event_type=ev.event_type,
            start_date=date.fromisoformat(ev.start_date),
            end_date=date.fromisoformat(ev.end_date),
            multiplier=Decimal(str(ev.suggested_multiplier)),
            priority=15,
        ))
    else:
        existing = db.query(LocalEvent).filter_by(name=ev.name).first()
        if existing:
            return {"status": "exists", "message": f'"{ev.name}" finns redan'}
        db.add(LocalEvent(
            name=ev.name,
            event_type=ev.event_type,
            location=ev.location,
            venue=ev.venue,
            start_date=date.fromisoformat(ev.start_date),
            end_date=date.fromisoformat(ev.end_date),
            multiplier=Decimal(str(ev.suggested_multiplier)),
            radius_km=Decimal("15"),
        ))

    db.commit()
    return {"status": "added", "message": f'"{ev.name}" tillagd i systemet'}
