"""
api/guest_import.py
CSV-import av gästantal från Airbnbs bokningsexport.

Matchar på: check_in-datum + annonstitel → property_id
Alternativ fallback: confirmation_code om den redan finns på bokningen.

Körs manuellt via POST /jobs/import-guests-csv (multipart/form-data, fält: file).
Returnerar antal matchade, missade och varningar.
"""

import csv
import io
from datetime import date, datetime
from typing import Optional
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, not_

from db.session import get_db
from db.models import Booking, Property

router = APIRouter()

# ── Annonstitel → crm_property_id ───────────────────────────────────────────
# Matchar Airbnbs exakta annonstitel (fritext) mot Norlis objekt-ID.
# Uppdatera när en ny annons skapas eller titeln ändras.
LISTING_MAP: dict[str, str] = {
    "Exklusiv havsdröm | Pool & privat sjötomt":            "trosa-havsdrom",
    "Villa 5 Min to Beach · 20 Min to Stockholm · Sauna":   "alta-beach-villa",
    "Stockholm · Spacious garden villa · 10 min to city":   "enskede-79",
    "Spacious Stockholm Villa · Garden · AC · Parking":     "alvsjö-tradgard",
    "Swedish villa with pool jacuzzi cinema sauna, more":   "",  # ej Norli-objekt, ignoreras
    "Strandvilla nära City | Pool & fullt utrustat gym":    "alvsjö-strandvilla",
}

# Varningströskel: saknad gästinfo inom X dagar flaggas
MISSING_GUEST_WARN_DAYS = 7


def _parse_date(s: str) -> Optional[date]:
    s = s.strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    return None


def _parse_int(s: str) -> int:
    try:
        return int(s.strip())
    except (ValueError, AttributeError):
        return 0


@router.post("/jobs/migrate-booking-columns")
def migrate_booking_columns(db: Session = Depends(get_db)):
    """Lägger till nya bokningskolumner om de saknas. Körs en gång efter deploy."""
    from sqlalchemy import text, inspect
    inspector = inspect(db.bind)
    existing = {col["name"] for col in inspector.get_columns("bookings")}
    added = []
    to_add = {
        "num_adults":        "INTEGER",
        "num_children":      "INTEGER",
        "num_infants":       "INTEGER",
        "confirmation_code": "VARCHAR(50)",
    }
    with db.bind.connect() as conn:
        for col, typ in to_add.items():
            if col not in existing:
                conn.execute(text(f"ALTER TABLE bookings ADD COLUMN {col} {typ}"))
                added.append(col)
        conn.commit()
    return {"added": added, "already_existed": [c for c in to_add if c not in added]}


@router.post("/jobs/import-guests-csv")
async def import_guests_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """
    Tar emot Airbnbs boknings-CSV (UTF-8, semikolon eller komma).
    Matchar varje rad mot en bokning i DB via check_in + property (via annonstitel).
    Sätter num_guests, num_adults, num_children, num_infants, confirmation_code.
    """
    raw = await file.read()
    # Airbnb exporterar ibland med BOM
    text = raw.decode("utf-8-sig")

    # Detektera separator
    sep = "," if text.count(",") > text.count(";") else ";"
    reader = csv.DictReader(io.StringIO(text), delimiter=sep)

    matched = 0
    skipped = 0
    unmatched_listings: set[str] = set()
    no_booking_found: list[str] = []

    for row in reader:
        # Normalisera kolumnnamn (strip whitespace + quotes)
        row = {k.strip().strip('"'): v.strip().strip('"') for k, v in row.items()}

        status = row.get("Status", "")
        # Hoppa över avbokade
        if "Avbokad" in status or "Cancelled" in status:
            skipped += 1
            continue

        listing_title = row.get("Annons", "").strip()
        crm_id = LISTING_MAP.get(listing_title)
        if not crm_id:
            unmatched_listings.add(listing_title)
            skipped += 1
            continue

        check_in_str = row.get("Startdatum", "") or row.get("Start Date", "")
        check_in = _parse_date(check_in_str)
        if not check_in:
            skipped += 1
            continue

        adults   = _parse_int(row.get("# av vuxna",    row.get("Adults",   "0")))
        children = _parse_int(row.get("# av barn",     row.get("Children", "0")))
        infants  = _parse_int(row.get("# av spädbarn", row.get("Infants",  "0")))
        total    = adults + children + infants
        conf_code = row.get("Bekräftelsekod", row.get("Confirmation Code", "")).strip()

        # Hitta property_id via crm_id
        prop = db.query(Property).filter(Property.crm_property_id == crm_id).first()
        if not prop:
            skipped += 1
            continue

        # Matcha bokning: property_id + check_in (datum är unik kombination)
        booking = (
            db.query(Booking)
            .filter(
                Booking.property_id == prop.id,
                Booking.check_in == check_in,
                Booking.status == "active",
            )
            .first()
        )

        if not booking:
            no_booking_found.append(f"{crm_id} {check_in}")
            skipped += 1
            continue

        booking.num_guests   = total
        booking.num_adults   = adults
        booking.num_children = children
        booking.num_infants  = infants
        if conf_code:
            booking.confirmation_code = conf_code
        matched += 1

    db.commit()

    return {
        "matched": matched,
        "skipped": skipped,
        "unmatched_listings": sorted(unmatched_listings),
        "no_booking_found": no_booking_found,
    }


@router.get("/jobs/missing-guests")
def missing_guests(
    days: int = 7,
    db: Session = Depends(get_db),
):
    """
    Returnerar bokningar där num_guests är null och incheckning är
    inom 'days' dagar. Används för varningsrad i UI.
    """
    today = date.today()
    cutoff = date.fromordinal(today.toordinal() + days)

    bookings = (
        db.query(Booking)
        .filter(
            Booking.status == "active",
            not_(Booking.source.in_(["airbnb_block", "cohost"])),
            Booking.num_guests == None,
            Booking.check_in >= today,
            Booking.check_in <= cutoff,
        )
        .order_by(Booking.check_in)
        .all()
    )

    # Bygg property_id → crm_property_id map
    prop_ids = {b.property_id for b in bookings}
    props = db.query(Property).filter(Property.id.in_(prop_ids)).all()
    crm_map = {p.id: p.crm_property_id for p in props}

    return [
        {
            "booking_id": b.id,
            "property_id": b.property_id,
            "crm_property_id": crm_map.get(b.property_id),
            "check_in": str(b.check_in),
            "check_out": str(b.check_out),
            "nights": (b.check_out - b.check_in).days,
            "guest_name": b.guest_name,
        }
        for b in bookings
    ]
