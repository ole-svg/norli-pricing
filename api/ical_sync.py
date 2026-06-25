"""
api/ical_sync.py
iCal-synk för bokningar från Airbnb (och framtida Booking.com, VRBO).

Parsear RFC 5545 iCal-format och lagrar bokningar i databasen.
Körs automatiskt var 15:e minut via nattjobbet, eller manuellt via API.

Bokningsstatus:
  active    — visas i systemet
  ignored   — importerad men dold (t.ex. Cohoast-blockeringar)
  private   — visas bara för admin, ej i rapporter
"""

import re
import httpx
from datetime import datetime, date
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel

from db.session import get_db
from db.models import Booking, Property

router = APIRouter()

# ── iCal-URL:er per objekt ──────────────────────────────────────────────────
# Nyckel = crm_property_id, värde = Airbnb iCal-URL
ICAL_URLS: dict[str, str] = {
    "trosa-havsdrom":              "https://www.airbnb.se/calendar/ical/1673099638596438222.ics?t=c827f6ae049c487383c223bf7d6350d8",
    "alta-beach-villa":            "https://www.airbnb.se/calendar/ical/1654943677598237856.ics?t=04874d5900074752b47a6916eacc8395",
    "alvsjö-tradgard":             "https://www.airbnb.se/calendar/ical/1678065319412002223.ics?t=4bc9760528df4acb9114141c71ee8ddb",
    "enskede-79":                  "https://www.airbnb.se/calendar/ical/1675878393965009957.ics?t=3472475a24714b1ca71344e1ad3e9ebe",
    "alvsjö-strandvilla":          "https://www.airbnb.se/calendar/ical/1199944314328075124.ics?t=9fcd78ac01db4259b9e7e6de6f468f2e",
    "island-cottage-oxelosund":      "https://www.airbnb.se/calendar/ical/1714535794845606344.ics?t=07fd9673b7c7478a90745161844d5c52",
    "ronneby-fritidshus":            "https://www.airbnb.se/calendar/ical/1710660504608521447.ics?t=d80d1562a0dd48c0a5479ee71c5b4bf5",
    "klassbol-sjoutsikt":            "https://www.airbnb.se/calendar/ical/1712900532137830623.ics?t=8d349635db214ab7b1f85c21725f1890",
    "seafront-cottage-oxelosund-2":  "https://www.airbnb.se/calendar/ical/1710660504608521447.ics?t=d80d1562a0dd48c0a5479ee71c5b4bf5",  # Samma listing som Ronneby — verifiera
}


# ── iCal-parser ─────────────────────────────────────────────────────────────

def parse_ical(raw: str) -> list[dict]:
    """Parsear iCal-text och returnerar lista med event-dicts."""
    events = []
    current = {}
    in_event = False

    for line in raw.splitlines():
        line = line.strip()
        if line == "BEGIN:VEVENT":
            in_event = True
            current = {}
        elif line == "END:VEVENT":
            in_event = False
            if current:
                events.append(current)
        elif in_event and ":" in line:
            key, _, value = line.partition(":")
            key = key.split(";")[0]  # Ta bort parametrar som TZID
            current[key] = value

    return events


def parse_ical_date(s: str) -> Optional[date]:
    """Parsear datum i format YYYYMMDD eller YYYYMMDDTHHMMSSZ."""
    s = s.strip()
    try:
        if "T" in s:
            return datetime.strptime(s[:8], "%Y%m%d").date()
        return datetime.strptime(s[:8], "%Y%m%d").date()
    except Exception:
        return None


def classify_booking(summary: str) -> tuple[str, str]:
    """
    Klassificerar bokning baserat på summary-fältet.
    Returnerar (status, source).
    """
    s = summary.lower()
    if "not available" in s or "airbnb (not available)" in s:
        return "ignored", "airbnb_block"
    if "cohost" in s:
        return "ignored", "cohost"
    if "blocked" in s or "block" in s:
        return "ignored", "block"
    # Airbnb döljer alltid gästnamn i iCal — "Reserved" = riktig bokning
    return "active", "airbnb"


# ── Synk-logik ───────────────────────────────────────────────────────────────

async def sync_property(crm_id: str, ical_url: str, db: Session) -> dict:
    """Hämtar och synkar iCal för ett objekt. Returnerar statistik."""
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(ical_url, follow_redirects=True)
            resp.raise_for_status()
            raw = resp.text
    except Exception as e:
        return {"property": crm_id, "error": str(e), "synced": 0}

    events = parse_ical(raw)
    synced = 0
    skipped = 0

    for ev in events:
        uid = ev.get("UID", "")
        summary = ev.get("SUMMARY", "")
        dtstart = parse_ical_date(ev.get("DTSTART", ""))
        dtend = parse_ical_date(ev.get("DTEND", ""))

        if not uid or not dtstart or not dtend:
            skipped += 1
            continue

        status, source = classify_booking(summary)

        # Hämta property
        prop = db.query(Property).filter(Property.crm_property_id == crm_id).first()
        if not prop:
            skipped += 1
            continue

        # Upsert — uppdatera om finns, skapa annars
        existing = db.query(Booking).filter(Booking.ical_uid == uid).first()
        if existing:
            # Uppdatera bara om status inte manuellt ändrats av användaren
            if not existing.manually_overridden:
                existing.check_in = dtstart
                existing.check_out = dtend
                existing.guest_name = summary if status == "active" else None
                existing.source = source
                existing.synced_at = datetime.utcnow()
        else:
            booking = Booking(
                property_id=prop.id,
                ical_uid=uid,
                check_in=dtstart,
                check_out=dtend,
                guest_name=summary if status == "active" else None,
                status=status,
                source=source,
                synced_at=datetime.utcnow(),
                manually_overridden=False,
            )
            db.add(booking)

        synced += 1

    db.commit()
    return {"property": crm_id, "synced": synced, "skipped": skipped, "total_events": len(events)}


# ── API-endpoints ─────────────────────────────────────────────────────────────

@router.post("/bookings/sync")
async def sync_all_bookings(background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Synkar alla objekt asynkront. Returnerar direkt med task-info."""
    results = []
    for crm_id, url in ICAL_URLS.items():
        result = await sync_property(crm_id, url, db)
        results.append(result)
    return {"status": "ok", "results": results}


@router.post("/bookings/sync/{crm_property_id}")
async def sync_one_booking(crm_property_id: str, db: Session = Depends(get_db)):
    """Synkar ett specifikt objekt manuellt."""
    url = ICAL_URLS.get(crm_property_id)
    if not url:
        raise HTTPException(404, f"Ingen iCal-URL för {crm_property_id}")
    result = await sync_property(crm_property_id, url, db)
    return result


@router.get("/bookings")
def list_bookings(
    property_id: Optional[str] = None,
    status: Optional[str] = None,
    include_blocks: bool = False,
    db: Session = Depends(get_db)
):
    """Listar bokningar med valfria filter.
    include_blocks=true inkluderar airbnb_block och cohost-ignorerade poster
    så att serviceteam-sidan kan detektera ägarperioder i gap.
    """
    q = db.query(Booking)
    if property_id:
        prop = db.query(Property).filter(Property.crm_property_id == property_id).first()
        if prop:
            q = q.filter(Booking.property_id == prop.id)
    if include_blocks:
        # Inkludera aktiva + airbnb_block/cohost (men ej manuellt ignorerade)
        from sqlalchemy import or_
        q = q.filter(or_(
            Booking.status == "active",
            Booking.source.in_(["airbnb_block", "cohost"])
        ))
    elif status:
        q = q.filter(Booking.status == status)
    else:
        q = q.filter(Booking.status == "active")
    bookings = q.order_by(Booking.check_in).all()
    return [_booking_dict(b) for b in bookings]


class BookingStatusUpdate(BaseModel):
    status: str  # "active" | "ignored" | "private"


@router.patch("/bookings/{booking_id}/status")
def update_booking_status(booking_id: int, body: BookingStatusUpdate, db: Session = Depends(get_db)):
    """Manuell statusändring — markeras som manually_overridden så synken inte skriver över."""
    b = db.get(Booking, booking_id)
    if not b:
        raise HTTPException(404, "Bokning ej hittad")
    if body.status not in ("active", "ignored", "private"):
        raise HTTPException(422, "Status måste vara active, ignored eller private")
    b.status = body.status
    b.manually_overridden = True
    db.commit()
    return _booking_dict(b)


def _booking_dict(b) -> dict:
    return {
        "id": b.id,
        "property_id": b.property_id,
        "ical_uid": b.ical_uid,
        "check_in": str(b.check_in),
        "check_out": str(b.check_out),
        "nights": (b.check_out - b.check_in).days,
        "guest_name": b.guest_name,
        "status": b.status,
        "source": b.source,
        "is_block": b.source in ("airbnb_block", "cohost"),
        "manually_overridden": b.manually_overridden,
        "synced_at": b.synced_at.isoformat() if b.synced_at else None,
    }

@router.post("/bookings/reclassify")
def reclassify_bookings(db: Session = Depends(get_db)):
    """Räknar om status för alla bokningar baserat på source-fältet.
    Kör detta efter att classify_booking-logiken uppdaterats."""
    bookings = db.query(Booking).filter(Booking.manually_overridden == False).all()
    fixed = 0
    for b in bookings:
        if b.source == "airbnb_block" and b.status == "active":
            b.status = "ignored"
            fixed += 1
        elif b.source in ("block", "cohost") and b.status == "active":
            b.status = "ignored"
            fixed += 1
        elif b.status == "ignored" and b.source == "airbnb" and not b.manually_overridden:
            # Restore falsely ignored real bookings
            b.status = "active"
            fixed += 1
    db.commit()
    return {"fixed": fixed, "total": len(bookings)}
