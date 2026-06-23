"""
api/inbound_email.py
Pollar olehorn@gmail.com via IMAP var 15:e minut efter Airbnb-bokningsbekräftelser.
Extraherar bekräftelsekod, gästantal, datum och annonstitel,
matchar mot befintlig bokning och uppdaterar num_guests m.m.

Trigger: GET /inbound/poll-gmail  (anropas av Railway cron eller manuellt)
"""

import re
import json
import imaplib
import email as email_lib
import os
import urllib.request as _urllib_req
from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from db.session import get_db
from db.models import Booking, Property


def _notify(subject: str, html: str) -> None:
    """Skickar notifieringsmejl via Resend."""
    import urllib.request as _req
    api_key = os.environ.get("RESEND_API_KEY", "")
    if not api_key:
        return
    try:
        body = json.dumps({
            "from": "Norli System <notiser@norli.se>",
            "to": ["ole@horn.se"],
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

# ── Annonstitel → crm_property_id ───────────────────────────────────────────
LISTING_MAP: dict[str, str] = {
    "Exklusiv havsdröm | Pool & privat sjötomt":            "trosa-havsdrom",
    "Villa 5 Min to Beach · 20 Min to Stockholm · Sauna":   "alta-beach-villa",
    "Stockholm · Spacious garden villa · 10 min to city":   "enskede-79",
    "Spacious Stockholm Villa · Garden · AC · Parking":     "alvsjö-tradgard",
    "Swedish villa with pool jacuzzi cinema sauna, more":   "",  # ej Norli-objekt
    "Strandvilla nära City | Pool & fullt utrustat gym":    "alvsjö-strandvilla",
}

# ── Regex-mönster ────────────────────────────────────────────────────────────
RE_CONF_CODE = re.compile(r"Bekr[äa]ftelsekod\s*[\n:]\s*([A-Z0-9]{8,12})|Confirmation Code\s*[\n:]\s*([A-Z0-9]{8,12})", re.IGNORECASE)
RE_CHECKIN   = re.compile(r"Incheckning\s*[\n:]\s*\w+\s+(\d{1,2}\s+\w+|\d{4}-\d{2}-\d{2})|Check-?in\s*[\n:]\s*(\w+,?\s+\w+\s+\d{1,2}|\d{4}-\d{2}-\d{2})", re.IGNORECASE)
RE_ADULTS    = re.compile(r"(\d+)\s+vuxna?|(\d+)\s+adult", re.IGNORECASE)
RE_CHILDREN  = re.compile(r"(\d+)\s+barn|(\d+)\s+child", re.IGNORECASE)
RE_INFANTS   = re.compile(r"(\d+)\s+sp[äa]dbarn|(\d+)\s+infant", re.IGNORECASE)

MONTH_SV = {"januari":1,"februari":2,"mars":3,"april":4,"maj":5,"juni":6,
             "juli":7,"augusti":8,"september":9,"oktober":10,"november":11,"december":12}


def _parse_sv_date(s: str, ref_year: int = 2026) -> Optional[date]:
    s = s.strip()
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
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
    for title, crm_id in LISTING_MAP.items():
        if title.lower()[:20] in text.lower():
            return crm_id
    return None


def _find_booking(db: Session, crm_id: str, check_in: date, conf_code: str) -> Optional[Booking]:
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
    return db.query(Booking).filter(
        Booking.property_id == prop.id,
        Booking.check_in == check_in,
        Booking.status == "active",
    ).first()


def _get_email_text(msg) -> str:
    """Extrahera plaintext ur ett email.message-objekt."""
    parts = []
    if msg.is_multipart():
        for part in msg.walk():
            ct = part.get_content_type()
            if ct == "text/plain":
                charset = part.get_content_charset() or "utf-8"
                try:
                    parts.append(part.get_payload(decode=True).decode(charset, errors="replace"))
                except Exception:
                    pass
            elif ct == "text/html" and not parts:
                charset = part.get_content_charset() or "utf-8"
                try:
                    html = part.get_payload(decode=True).decode(charset, errors="replace")
                    parts.append(re.sub(r"<[^>]+>", " ", html))
                except Exception:
                    pass
    else:
        charset = msg.get_content_charset() or "utf-8"
        try:
            parts.append(msg.get_payload(decode=True).decode(charset, errors="replace"))
        except Exception:
            pass
    return "\n".join(parts)


def _poll_gmail(db: Session) -> dict:
    """
    Loggar in på olehorn@gmail.com via IMAP, hämtar olästa mejl från Airbnb,
    parsar bokningsbekräftelser och uppdaterar databasen.
    """
    gmail_user = os.environ.get("GMAIL_USER", "olehorn@gmail.com")
    gmail_pass = os.environ.get("GMAIL_APP_PASSWORD", "")

    if not gmail_pass:
        return {"status": "error", "reason": "GMAIL_APP_PASSWORD saknas"}

    results = []

    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com", 993)
        mail.login(gmail_user, gmail_pass)
        mail.select("INBOX")

        # Sök olästa mejl från Airbnb
        _, data = mail.search(None, 'UNSEEN FROM "automated@airbnb.com"')
        msg_ids = data[0].split()

        if not msg_ids:
            mail.logout()
            return {"status": "ok", "checked": 0, "processed": 0}

        processed = 0
        for mid in msg_ids:
            _, raw = mail.fetch(mid, "(RFC822)")
            msg = email_lib.message_from_bytes(raw[0][1])
            subject = str(msg.get("Subject", ""))
            full_text = subject + "\n" + _get_email_text(msg)

            # Är det en bokningsbekräftelse?
            is_booking = any(kw in subject.lower() for kw in [
                "ny bokning", "new reservation", "booking confirmed", "bokning bekräftad"
            ])
            if not is_booking:
                # Markera ändå som läst så vi inte processar om den
                mail.store(mid, "+FLAGS", "\\Seen")
                continue

            # Extrahera
            m_code = RE_CONF_CODE.search(full_text)
            conf_code = next((g for g in (m_code.groups() if m_code else [])), "") or ""

            adults   = _extract_int(RE_ADULTS, full_text)
            children = _extract_int(RE_CHILDREN, full_text)
            infants  = _extract_int(RE_INFANTS, full_text)
            total    = adults + children + infants

            crm_id = _find_listing(full_text)

            m_ci = RE_CHECKIN.search(full_text)
            check_in_str = next((g for g in (m_ci.groups() if m_ci else [])), None)
            check_in = _parse_sv_date(check_in_str) if check_in_str else None

            log = {
                "subject": subject,
                "conf_code": conf_code,
                "crm_id": crm_id,
                "check_in": str(check_in),
                "adults": adults, "children": children, "infants": infants,
            }

            if not crm_id or not check_in or total == 0:
                results.append({"status": "partial", "extracted": log})
                mail.store(mid, "+FLAGS", "\\Seen")
                continue

            booking = _find_booking(db, crm_id, check_in, conf_code)
            if not booking:
                results.append({"status": "no_match", "extracted": log})
                mail.store(mid, "+FLAGS", "\\Seen")
                continue

            booking.num_guests   = total
            booking.num_adults   = adults
            booking.num_children = children
            booking.num_infants  = infants
            if conf_code:
                booking.confirmation_code = conf_code
            db.commit()

            _notify(
                subject=f"[Airbnb] Ny bokning: {crm_id}",
                html=f"<h3>Ny bokning registrerad</h3>"
                     f"<p><strong>Objekt:</strong> {crm_id}<br>"
                     f"<strong>Incheckning:</strong> {check_in}<br>"
                     f"<strong>Gäster:</strong> {total} ({adults} vuxna, {children} barn, {infants} spädbarn)<br>"
                     f"<strong>Bekräftelsekod:</strong> {conf_code}</p>"
            )

            mail.store(mid, "+FLAGS", "\\Seen")
            processed += 1
            results.append({"status": "ok", "booking_id": booking.id, "extracted": log})

        mail.logout()
        return {"status": "ok", "checked": len(msg_ids), "processed": processed, "results": results}

    except imaplib.IMAP4.error as e:
        return {"status": "error", "reason": f"IMAP-fel: {e}"}
    except Exception as e:
        return {"status": "error", "reason": str(e)}


@router.get("/inbound/poll-gmail")
async def poll_gmail_endpoint(db: Session = Depends(get_db)):
    """
    Pollar olehorn@gmail.com efter nya Airbnb-bekräftelsemejl.
    Anropas av Railway cron (railway.toml) var 15:e minut.
    """
    return _poll_gmail(db)
