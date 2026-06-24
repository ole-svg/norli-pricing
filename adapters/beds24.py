"""
adapters/beds24.py
Beds24 API v2 integration — Airbnb data bridge for Norli Stay AB.

Auth flow:
  1. POST /authentication/setup med longLifeToken → får token
  2. Använd token i header för alla anrop

Docs: https://beds24.com/api/v2
"""

import os
import requests
from datetime import datetime
from typing import Optional, List, Dict, Any

BEDS24_API_BASE = "https://beds24.com/api/v2"

# Cache access token i minnet
_cached_token: Optional[str] = None


def _get_long_life_token() -> str:
    return os.getenv("BEDS24_TOKEN", "").strip()


def _get_access_token() -> str:
    """
    Byter ut Long Life Token mot en access token via Beds24 auth endpoint.
    Cachas i minnet för sessionen.
    """
    global _cached_token

    if _cached_token:
        return _cached_token

    llt = _get_long_life_token()
    if not llt:
        raise ValueError("BEDS24_TOKEN saknas")

    # Försök 1: skicka direkt som token header (om det är en access token)
    test = requests.get(
        f"{BEDS24_API_BASE}/properties",
        headers={"token": llt, "Accept": "application/json"},
        timeout=15,
    )
    if test.status_code == 200:
        _cached_token = llt
        return llt

    # Försök 2: exchange via /authentication/setup
    resp = requests.post(
        f"{BEDS24_API_BASE}/authentication/setup",
        headers={"Content-Type": "application/json"},
        json={"longLifeToken": llt},
        timeout=15,
    )

    if resp.status_code == 200:
        data = resp.json()
        token = data.get("token") or data.get("access_token") or data.get("data", {}).get("token")
        if token:
            _cached_token = token
            return token
        raise ValueError(f"Auth setup svar saknar token: {data}")

    raise ValueError(f"Auth setup misslyckades: {resp.status_code} {resp.text[:200]}")


def _headers() -> dict:
    token = _get_access_token()
    return {
        "token": token,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def get_properties() -> List[Dict[str, Any]]:
    """Hämtar alla properties från Beds24."""
    resp = requests.get(
        f"{BEDS24_API_BASE}/properties",
        headers=_headers(),
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    return data.get("data", data) if isinstance(data, dict) else data


def get_bookings(
    property_id: Optional[int] = None,
    arrival_from: Optional[str] = None,
    arrival_to: Optional[str] = None,
    status: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Hämtar bokningar från Beds24."""
    params = {}
    if property_id:
        params["propertyId"] = property_id
    if arrival_from:
        params["arrivalFrom"] = arrival_from
    if arrival_to:
        params["arrivalTo"] = arrival_to
    if status:
        params["status"] = status

    resp = requests.get(
        f"{BEDS24_API_BASE}/bookings",
        headers=_headers(),
        params=params,
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    bookings = data.get("data", data) if isinstance(data, dict) else data
    return [_normalize_booking(b) for b in bookings]


def _normalize_booking(b: Dict[str, Any]) -> Dict[str, Any]:
    guest = (b.get("guestFirstName", "") + " " + b.get("guestLastName", "")).strip() or None
    check_in = b.get("arrival") or b.get("checkIn")
    check_out = b.get("departure") or b.get("checkOut")
    nights = 0
    if check_in and check_out:
        try:
            nights = (datetime.strptime(check_out, "%Y-%m-%d") - datetime.strptime(check_in, "%Y-%m-%d")).days
        except:
            pass
    status_map = {
        "confirmed": "active", "new": "active",
        "cancelled": "cancelled", "declined": "cancelled",
        "blocked": "ignored", "owner": "private",
    }
    raw_status = str(b.get("status", "")).lower()
    return {
        "source": "airbnb",
        "source_system": "beds24",
        "external_reservation_id": str(b.get("id", "")),
        "confirmation_code": b.get("externalId") or b.get("confirmationCode"),
        "beds24_property_id": b.get("propertyId"),
        "guest_name": guest,
        "guest_email": b.get("guestEmail"),
        "check_in": check_in,
        "check_out": check_out,
        "nights": nights,
        "num_guests": b.get("numAdult", 0) + b.get("numChild", 0),
        "status": status_map.get(raw_status, "active"),
        "is_block": raw_status in ("blocked", "owner"),
        "price_total": b.get("price"),
        "channel": b.get("channel", "airbnb"),
        "raw_payload": b,
    }


def push_prices(property_id: int, room_id: int, prices: List[Dict[str, Any]]) -> Dict[str, Any]:
    items = []
    for p in prices:
        item = {"propertyId": property_id, "roomId": room_id,
                "startDate": p["date"], "endDate": p["date"], "price": p.get("price")}
        if p.get("minStay"):
            item["minStay"] = p["minStay"]
        items.append(item)
    resp = requests.post(f"{BEDS24_API_BASE}/inventory/prices",
                         headers=_headers(), json=items, timeout=30)
    resp.raise_for_status()
    return resp.json()
