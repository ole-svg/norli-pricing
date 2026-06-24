"""
api/beds24_api.py
API-endpoints för Beds24-integration.
"""

import os
from datetime import date, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from db.session import get_db
from db.models import Booking, Property
from pydantic import BaseModel

router = APIRouter()

# Token läses vid varje anrop (inte vid import) för att plocka upp Railway env vars
def _get_token() -> str:
    return os.getenv("BEDS24_TOKEN", "")

# Mapping: Beds24 property ID → Norli CRM property ID
# Fylls i när Beds24-objekt är kopplade
BEDS24_PROPERTY_MAP: dict = {}


class Beds24WebhookPayload(BaseModel):
    bookingId: Optional[int] = None
    propertyId: Optional[int] = None
    action: Optional[str] = None


@router.post("/beds24/webhook")
async def beds24_webhook(
    payload: Beds24WebhookPayload,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Tar emot webhook från Beds24 vid ny/ändrad/avbruten bokning.
    Beds24 skickar ett litet ping — vi hämtar sedan full bokning via API.
    """
    if payload.bookingId:
        background_tasks.add_task(
            _sync_single_booking, payload.bookingId, db
        )
    return {"status": "ok", "booking_id": payload.bookingId}


async def _sync_single_booking(booking_id: int, db: Session):
    """Hämtar och sparar en enskild bokning från Beds24."""
    try:
        from adapters.beds24 import get_bookings
        # Hämta specifik bokning
        bookings = get_bookings()
        bk = next((b for b in bookings
                   if b["external_reservation_id"] == str(booking_id)), None)
        if bk:
            _upsert_booking(bk, db)
    except Exception as e:
        print(f"Beds24 booking sync error: {e}")


def _upsert_booking(bk: dict, db: Session):
    """Skapar eller uppdaterar bokning i databasen."""
    from datetime import datetime

    # Hitta property_id från Beds24 property mapping
    prop = db.query(Property).filter(
        Property.crm_property_id.in_(BEDS24_PROPERTY_MAP.values())
    ).first()

    if not prop:
        return

    existing = db.query(Booking).filter(
        Booking.ical_uid == f"beds24-{bk['external_reservation_id']}"
    ).first()

    if existing:
        existing.guest_name = bk.get("guest_name")
        existing.status = bk.get("status", "active")
    else:
        from datetime import date as d_type
        check_in = bk.get("check_in")
        check_out = bk.get("check_out")
        if not check_in or not check_out:
            return

        new_booking = Booking(
            property_id=prop.id,
            ical_uid=f"beds24-{bk['external_reservation_id']}",
            check_in=check_in,
            check_out=check_out,
            nights=bk.get("nights", 0),
            guest_name=bk.get("guest_name"),
            status=bk.get("status", "active"),
            source="airbnb",
            manually_overridden=False,
        )
        db.add(new_booking)

    db.commit()


@router.get("/beds24/bookings")
def list_beds24_bookings():
    """Hämtar bokningar direkt från Beds24 API (utan DB-cache)."""
    BEDS24_TOKEN = _get_token()
    if not BEDS24_TOKEN:
        raise HTTPException(500, "BEDS24_TOKEN saknas")

    try:
        from adapters.beds24 import get_bookings
        bookings = get_bookings(
            arrival_from=str(date.today()),
            arrival_to=str(date.today() + timedelta(days=180)),
        )
        return {
            "total": len(bookings),
            "real_bookings": [b for b in bookings if not b["is_block"]],
            "blocks": [b for b in bookings if b["is_block"]],
        }
    except Exception as e:
        raise HTTPException(503, str(e))


@router.get("/beds24/properties")
def list_beds24_properties():
    """Hämtar alla properties från Beds24."""
    BEDS24_TOKEN = _get_token()
    if not BEDS24_TOKEN:
        raise HTTPException(500, "BEDS24_TOKEN saknas")
    try:
        from adapters.beds24 import get_properties
        return get_properties()
    except Exception as e:
        raise HTTPException(503, str(e))

@router.get("/beds24/debug")
def debug_beds24():
    """Debug: visa token-info utan att exponera hela token."""
    token = _get_token()
    return {
        "token_set": bool(token),
        "token_length": len(token),
        "token_preview": token[:10] + "..." if len(token) > 10 else "EMPTY",
        "env_vars": [k for k in __import__("os").environ.keys() if "BEDS24" in k or "TOKEN" in k],
    }

@router.post("/beds24/sync")
def sync_beds24_bookings(db: Session = Depends(get_db)):
    """Synkar bokningar från Beds24 → OLE-databas."""
    try:
        from adapters.beds24 import get_bookings
        from datetime import date, timedelta
        from db.models import Booking, Property

        bookings = get_bookings(
            arrival_from=str(date.today()),
            arrival_to=str(date.today() + timedelta(days=365)),
        )

        synced = 0
        skipped = 0
        errors = []

        for bk in bookings:
            if bk.get("is_block"):
                skipped += 1
                continue

            try:
                # Hämta gästnamn från raw_payload
                raw = bk.get("raw_payload", {})
                first = raw.get("firstName", "") or ""
                last = raw.get("lastName", "") or ""
                guest_name = (first + " " + last).strip() or None
                confirmation_code = raw.get("apiReference") or None
                beds24_prop_id = bk.get("beds24_property_id")

                # Hitta Norli-property via Beds24 property ID
                # Beds24 property 337219 = enskede-79
                BEDS24_TO_CRM = {
                    337219: "enskede-79",
                }
                crm_id = BEDS24_TO_CRM.get(beds24_prop_id)
                if not crm_id:
                    skipped += 1
                    continue

                prop = db.query(Property).filter(
                    Property.crm_property_id == crm_id
                ).first()
                if not prop:
                    skipped += 1
                    continue

                uid = f"beds24-{bk['external_reservation_id']}"
                check_in = bk.get("check_in")
                check_out = bk.get("check_out")
                if not check_in or not check_out:
                    skipped += 1
                    continue

                existing = db.query(Booking).filter(
                    Booking.ical_uid == uid
                ).first()

                if existing:
                    existing.guest_name = guest_name
                    existing.status = bk.get("status", "active")
                    existing.num_guests = raw.get("numAdult", 0) + raw.get("numChild", 0)
                else:
                    new_b = Booking(
                        property_id=prop.id,
                        ical_uid=uid,
                        check_in=check_in,
                        check_out=check_out,
                        guest_name=guest_name,
                        num_guests=raw.get("numAdult", 0) + raw.get("numChild", 0),
                        status=bk.get("status", "active"),
                        source="airbnb",
                        manually_overridden=False,
                    )
                    db.add(new_b)

                synced += 1

            except Exception as e:
                errors.append(str(e))
                continue

        db.commit()
        return {
            "status": "ok",
            "synced": synced,
            "skipped": skipped,
            "total": len(bookings),
            "errors": errors[:5] if errors else [],
        }

    except Exception as e:
        import traceback
        return {"status": "error", "detail": str(e), "trace": traceback.format_exc()[-500:]}
