"""
api/airbnb_prices.py
Hämtar faktiska priser som ligger på Airbnb via PriceLabs API.
Används för att jämföra våra beräknade priser mot det som gästerna faktiskt ser.
"""

import os
import requests
from datetime import date, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from db.session import get_db
from db.models import Property

router = APIRouter()

PRICELABS_API_BASE = "https://api.pricelabs.co/v1"

LISTING_IDS = {
    "enskede-79":       "1675878393965009957",
    "trosa-havsdrom":   "1673099638596438222",
    "alta-beach-villa": "1654943677598237856",
    "alvsjö-tradgard":  "1678065319412002223",
}


def _headers():
    return {
        "X-API-Key": os.getenv("PRICELABS_API_KEY", ""),
        "Content-Type": "application/json",
    }


@router.get("/airbnb-prices/{crm_property_id}")
def get_airbnb_prices(
    crm_property_id: str,
    start_date: str = Query(default=None),
    end_date: str = Query(default=None),
):
    """
    Hämtar faktiska priser från Airbnb via PriceLabs.
    Returnerar lista med {date, airbnb_price} för given period.
    """
    listing_id = LISTING_IDS.get(crm_property_id)
    if not listing_id:
        raise HTTPException(404, f"Inget listing-id för {crm_property_id}")

    if not start_date:
        start_date = date.today().isoformat()
    if not end_date:
        end_date = (date.today() + timedelta(days=60)).isoformat()

    api_key = os.getenv("PRICELABS_API_KEY")
    if not api_key:
        raise HTTPException(500, "PRICELABS_API_KEY saknas")

    try:
        # PriceLabs portfolio prices endpoint
        resp = requests.get(
            f"{PRICELABS_API_BASE}/portfolio/prices",
            params={
                "listing_ids": listing_id,
                "start_date": start_date,
                "end_date": end_date,
            },
            headers=_headers(),
            timeout=15,
        )

        if resp.status_code == 200:
            data = resp.json()
            # Normalisera response — PriceLabs returnerar olika format
            prices = []
            if isinstance(data, list):
                for item in data:
                    if str(item.get("listing_id", "")) == listing_id:
                        for day in item.get("prices", []):
                            prices.append({
                                "date": day.get("date"),
                                "airbnb_price": day.get("price"),
                                "available": day.get("available", True),
                            })
            elif isinstance(data, dict):
                for day in data.get("prices", data.get("data", [])):
                    prices.append({
                        "date": day.get("date"),
                        "airbnb_price": day.get("price"),
                        "available": day.get("available", True),
                    })
            return {"listing_id": listing_id, "prices": prices}

        # Fallback: try listing-specific endpoint
        resp2 = requests.get(
            f"{PRICELABS_API_BASE}/listings/{listing_id}/prices",
            params={"start_date": start_date, "end_date": end_date},
            headers=_headers(),
            timeout=15,
        )
        if resp2.status_code == 200:
            data2 = resp2.json()
            prices = [
                {
                    "date": d.get("date"),
                    "airbnb_price": d.get("price"),
                    "available": d.get("available", True),
                }
                for d in (data2 if isinstance(data2, list) else data2.get("prices", []))
            ]
            return {"listing_id": listing_id, "prices": prices}

        raise HTTPException(resp.status_code, f"PriceLabs svarade: {resp.text[:200]}")

    except requests.RequestException as e:
        raise HTTPException(503, f"Kunde inte nå PriceLabs: {str(e)}")


@router.post("/airbnb-prices/sync-all")
def sync_all_airbnb_prices(
    start_date: str = Query(default=None),
    end_date: str = Query(default=None),
):
    """
    Hämtar priser för alla objekt på en gång.
    """
    if not start_date:
        start_date = date.today().isoformat()
    if not end_date:
        end_date = (date.today() + timedelta(days=90)).isoformat()

    results = {}
    for crm_id, listing_id in LISTING_IDS.items():
        try:
            resp = requests.get(
                f"{PRICELABS_API_BASE}/portfolio/prices",
                params={"listing_ids": listing_id, "start_date": start_date, "end_date": end_date},
                headers=_headers(),
                timeout=15,
            )
            if resp.status_code == 200:
                data = resp.json()
                prices = []
                if isinstance(data, list):
                    for item in data:
                        for day in item.get("prices", []):
                            prices.append({"date": day.get("date"), "airbnb_price": day.get("price")})
                results[crm_id] = {"ok": True, "count": len(prices), "prices": prices}
            else:
                results[crm_id] = {"ok": False, "error": f"HTTP {resp.status_code}"}
        except Exception as e:
            results[crm_id] = {"ok": False, "error": str(e)}

    return results
