"""
api/inbound_email.py
Tar emot Airbnb-bokningsbekräftelser via Resend Inbound webhook.

Resend parsar inkommande mejl och POST:ar JSON till denna endpoint.
Vi extraherar bekräftelsekod, gästantal, datum och annonstitel,
matchar mot befintlig bokning och uppdaterar num_guests m.m.

Webhook-URL: POST /inbound/airbnb-email
"""

import re
import json
import hmac
import hashlib
import os
from datetime import date
from typing import Optional
from fastapi import APIRouter, Request, HTTPException
from sqlalchemy.orm import Session
from fastapi import Depends
from db.session import get_db
from db.models import Booking, Property

def _notify(subject: str, html: str) -> None:
    """Skickar notifieringsmejl. TODO vid go-live: routing per objekt/städbolag."""
    import os, json
    import urllib.request as _req
    api_key = os.environ.get("RESEND_API_KEY", "")
    if not api_key:
        return
    try:
        body = json.dumps({
            "from": "Norli System <notiser@norli.se>",
            "to": ["ole@horn.se"],  # TODO vid go-live: städbolagets mejl per objekt
            "subject": subject,
            "html": html,
        }).encode()
        req = _req.Request("https://api.resend.com/emails", data=body,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            method="POST")
        with _req.urlopen(req, timeout=5) as r:
            r.read()
    except Exception as e:
        print(f"⚠ Mejlfel: {e}")


router = APIRouter()

# ── Annonstitel → crm_property_id (samma som i guest_import.py) ─────────────
LISTING_MAP: dict[str, str] = {
    "Exklusiv havsdröm | Pool & privat sjötomt":            "trosa-havsdrom",
    "Villa 5 Min to Beach · 20 Min to Stockholm · Sauna":   "alta-beach-villa",
    "Stockholm · Spacious garden villa · 10 min to city":   "enskede-79",
    "Spacious Stockholm Villa · Garden · AC · Parking":     "alvsjö-tradgard",
    "Swedish villa with pool jacuzzi cinema sauna, more":   "",  # ej Norli-objekt, ignoreras
    "Strandvilla nära City | Pool & fullt utrustat gym":    "alvsjö-strandvilla",
}

# ── Regex-mönster för Airbnbs mejlformat ────────────────────────────────────
# Matchar "Bekräftelsekod\nHMF4ZJXXE2" eller "Confirmation Code\nHMF4ZJXXE2"
RE_CONF_CODE  = re.compile(r"Bekr[äa]ftelsekod\s*[\n:]\s*([A-Z0-9]{8,12})|Confirmation Code\s*[\n:]\s*([A-Z0-9]{8,12})", re.IGNORECASE)
RE_CHECKIN    = re.compile(r"Incheckning\s*[\n:]\s*\w+\s+(\d{1,2}\s+\w+|\d{4}-\d{2}-\d{2})|Check-?in\s*[\n:]\s*(\w+,?\s+\w+\s+\d{1,2}|\d{4}-\d{2}-\d{2})", re.IGNORECASE)
RE_CHECKOUT   = re.compile(r"Utcheckning\s*[\n:]\s*\w+\s+(\d{1,2}\s+\w+|\d{4}-\d{2}-\d{2})|Check-?out\s*[\n:]\s*(\w+,?\s+\w+\s+\d{1,2}|\d{4}-\d{2}-\d{2})", re.IGNORECASE)
RE_ADULTS     = re.compile(r"(\d+)\s+vuxna?|(\d+)\s+adult", re.IGNORECASE)
RE_CHILDREN   = re.compile(r"(\d+)\s+barn|(\d+)\s+child", re.IGNORECASE)
RE_INFANTS    = re.compile(r"(\d+)\s+sp[äa]dbarn|(\d+)\s+infant", re.IGNORECASE)
RE_LISTING    = re.compile(r"(Stockholm · Spacious garden villa[^\n]*|Exklusiv havsdröm[^\n]*|Villa 5 Min[^\n]*|Spacious Stockholm Villa[^\n]*|Swedish villa[^\n]*|Strandvilla nära City[^\n]*)", re.IGNORECASE)

# ISO-datum från Airbnbs svenska format, t.ex. "7 juli" + år från context
MONTH_SV = {"januari":1,"februari":2,"mars":3,"april":4,"maj":5,"juni":6,
             "juli":7,"augusti":8,"september":9,"oktober":10,"november":11,"december":12}

def _parse_sv_date(s: str, ref_year: int = 2026) -> Optional[date]:
    """Försöker parsa 'tis 7 juli' eller '2026-07-07' till date."""
    s = s.strip()
    # ISO-format
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    # Svensk: "7 juli" eller "tis 7 juli"
    m = re.search(r"(\d{1,2})\s+(\w+)", s)
    if m:
        day = int(m.group(1))
        month = MONTH_SV.get(m.group(2).lower())
        if month:
            return date(ref_year, month, day)
    return None

def _extract_int(pattern: re.Pattern, text: str) -> int:
    m = pattern.search(text)
    if not m: return 0
    return int(next(g for g in m.groups() if g is not None))

def _find_listing(text: str) -> Optional[str]:
    """Hitta annonstitel i mejltext och slå upp crm_property_id."""
    for title, crm_id in LISTING_MAP.items():
        if title.lower()[:20] in text.lower():
            return crm_id
    return None

def _find_booking(db: Session, crm_id: str, check_in: date, conf_code: str) -> Optional[Booking]:
    """Matcha bokning: försök bekräftelsekod först, sedan datum + property."""
    prop = db.query(Property).filter(Property.crm_property_id == crm_id).first()
    if not prop:
        return None
    if conf_code:
        b = db.query(Booking).filter(
            Booking.property_id == prop.id,
            Booking.confirmation_code == conf_code,
        ).first()
        if b:
            return b
    # Fallback: datum
    return db.query(Booking).filter(
        Booking.property_id == prop.id,
        Booking.check_in == check_in,
        Booking.status == "active",
    ).first()


@router.post("/inbound/airbnb-email")
async def receive_airbnb_email(request: Request, db: Session = Depends(get_db)):
    """
    Resend Inbound webhook.
    Resend skickar metadata i webhook-payloaden (email_id, subject).
    Vi hämtar mejlinnehållet via Resend API med email_id.
    """
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(400, "Ogiltig JSON")

    # Resend webhook-struktur: { type: "email.received", data: { email_id, subject, ... } }
    event_type = payload.get("type", "")
    if event_type != "email.received":
        return {"status": "ignored", "reason": f"event type: {event_type}"}

    data = payload.get("data", {})
    email_id = data.get("email_id", "")
    subject = data.get("subject", "") or ""

    # Kolla subject direkt från metadata
    is_booking = any(kw in subject.lower() for kw in [
        "ny bokning", "new reservation", "booking confirmed", "bokning bekräftad"
    ])
    if not is_booking:
        return {"status": "ignored", "reason": "not a booking confirmation", "subject": subject}

    # Hämta mejlinnehållet via Resend API
    api_key = os.environ.get("RESEND_API_KEY", "")
    full = subject  # fallback om API-anropet misslyckas
    if api_key and email_id:
        try:
            req = _urllib_req.Request(
                f"https://api.resend.com/emails/{email_id}",
                headers={"Authorization": f"Bearer {api_key}"},
                method="GET",
            )
            with _urllib_req.urlopen(req, timeout=10) as r:
                email_data = json.loads(r.read())
            text = email_data.get("text", "") or ""
            html_raw = email_data.get("html", "") or ""
            full = subject + "\n" + text + "\n" + re.sub(r"<[^>]+>", " ", html_raw)
        except Exception as e:
            print(f"⚠ Kunde inte hämta mejlinnehåll: {e}")

    # Extrahera fält
    m_code = RE_CONF_CODE.search(full)
    conf_code = ""
    if m_code:
        conf_code = next(g for g in m_code.groups() if g is not None)

    adults   = _extract_int(RE_ADULTS, full)
    children = _extract_int(RE_CHILDREN, full)
    infants  = _extract_int(RE_INFANTS, full)
    total    = adults + children + infants

    crm_id = _find_listing(full)

    m_ci = RE_CHECKIN.search(full)
    check_in_str = next((g for g in (m_ci.groups() if m_ci else [])), None)
    check_in = _parse_sv_date(check_in_str) if check_in_str else None

    log = {
        "subject": subject,
        "email_id": email_id,
        "conf_code": conf_code,
        "crm_id": crm_id,
        "check_in": str(check_in),
        "adults": adults, "children": children, "infants": infants,
    }

    if not crm_id or not check_in or total == 0:
        return {"status": "partial", "extracted": log, "reason": "could not extract all fields"}

    booking = _find_booking(db, crm_id, check_in, conf_code)
    if not booking:
        return {"status": "no_match", "extracted": log}

    booking.num_guests   = total
    booking.num_adults   = adults
    booking.num_children = children
    booking.num_infants  = infants
    if conf_code:
        booking.confirmation_code = conf_code
    db.commit()

    # Notis till Ole (go-live: routing per städbolag)
    _notify(
        subject=f"[Airbnb] Ny bokning: {crm_id}",
        html=f"<h3>Ny bokning registrerad</h3>"
             f"<p><strong>Objekt:</strong> {crm_id}<br>"
             f"<strong>Incheckning:</strong> {check_in}<br>"
             f"<strong>Gäster:</strong> {total} ({adults} vuxna, {children} barn, {infants} spädbarn)<br>"
             f"<strong>Bekräftelsekod:</strong> {conf_code}</p>"
    )

    return {
        "status": "ok",
        "booking_id": booking.id,
        "updated": {"num_guests": total, "confirmation_code": conf_code},
        "extracted": log,
    }
