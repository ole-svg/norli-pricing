"""
adapters/beds24.py
Beds24 API v2 — Airbnb data bridge for Norli Stay AB.

Auth:
  BEDS24_TOKEN = Invite Code (used to get access token)
  Access token expires 24h → auto-refreshed via refresh token
  Refresh token stored in BEDS24_REFRESH_TOKEN env var

Docs: https://beds24.com/api/v2
"""

import os
import requests
from datetime import datetime
from typing import Optional, List, Dict, Any

BEDS24_API_BASE = "https://beds24.com/api/v2"

# In-memory token cache
_access_token: Optional[str] = None
_refresh_token: Optional[str] = None


def _get_invite_code() -> str:
    return os.getenv("BEDS24_TOKEN", "").strip()

def _get_stored_refresh() -> str:
    return os.getenv("BEDS24_REFRESH_TOKEN", "").strip()


def _exchange_invite_code(invite_code: str) -> dict:
    """Byt ut Invite Code mot access token + refresh token."""
    resp = requests.get(
        f"{BEDS24_API_BASE}/authentication/setup",
        headers={
            "accept": "application/json",
            "code": invite_code,
            "deviceName": "OLE Integration",
        },
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def _refresh_access_token(refresh_token: str) -> dict:
    """Hämta ny access token via refresh token."""
    resp = requests.get(
        f"{BEDS24_API_BASE}/authentication/token",
        headers={
            "accept": "application/json",
            "refreshToken": refresh_token,
        },
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def _get_access_token() -> str:
    """Hämtar giltig access token — refreshar automatiskt vid behov."""
    global _access_token, _refresh_token

    if _access_token:
        return _access_token

    # Försök med refresh token (env var eller cachad)
    refresh = _refresh_token or _get_stored_refresh()
    if refresh:
        try:
            data = _refresh_access_token(refresh)
            _access_token = data.get("token")
            _refresh_token = data.get("refreshToken", refresh)
            if _access_token:
                return _access_token
        except Exception as e:
            print(f"Beds24 refresh misslyckades: {e}")

    # Fallback: exchange invite code
    invite = _get_invite_code()
    if not invite:
        raise ValueError("BEDS24_TOKEN saknas")

    data = _exchange_invite_code(invite)
    _access_token = data.get("token")
    _refresh_token = data.get("refreshToken")
    if not _access_token:
        raise ValueError(f"Beds24 auth gav inget token: {data}")
    return _access_token


def _headers() -> dict:
    return {
        "token": _get_access_token(),
        "accept": "application/json",
        "Content-Type": "application/json",
    }


def get_properties() -> List[Dict[str, Any]]:
    resp = requests.get(f"{BEDS24_API_BASE}/properties",
                        headers=_headers(), timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return data.get("data", data) if isinstance(data, dict) else data


def get_bookings(
    property_id: Optional[int] = None,
    arrival_from: Optional[str] = None,
    arrival_to: Optional[str] = None,
    status: Optional[str] = None,
) -> List[Dict[str, Any]]:
    params = {}
    if property_id: params["propertyId"] = property_id
    if arrival_from: params["arrivalFrom"] = arrival_from
    if arrival_to: params["arrivalTo"] = arrival_to
    if status: params["status"] = status

    resp = requests.get(f"{BEDS24_API_BASE}/bookings",
                        headers=_headers(), params=params, timeout=30)
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
            nights = (datetime.strptime(check_out, "%Y-%m-%d") -
                     datetime.strptime(check_in, "%Y-%m-%d")).days
        except: pass
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
    items = [{"propertyId": property_id, "roomId": room_id,
              "startDate": p["date"], "endDate": p["date"],
              "price": p.get("price"),
              **({"minStay": p["minStay"]} if p.get("minStay") else {})}
             for p in prices]
    resp = requests.post(f"{BEDS24_API_BASE}/inventory/prices",
                         headers=_headers(), json=items, timeout=30)
    resp.raise_for_status()
    return resp.json()
