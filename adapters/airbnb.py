"""
Airbnb-adapter - publicerar priser till Airbnb via deras API.

Airbnb Host API dokumentation:
https://platform.airbnb.com/docs

Autentisering: OAuth2 med client_id och client_secret.
Priser sätts via: PUT /v2/calendars/{listing_id}

Stodjer:
- Dag-for-dag priser
- Minimum vistelselangd per datum
- Blockering av datum
"""

import os
import logging
from datetime import date, timedelta
from decimal import Decimal
from typing import Optional

import requests

from adapters.base import PlatformAdapter, PriceUpdate, AdapterResult

logger = logging.getLogger(__name__)

AIRBNB_API_BASE = "https://api.airbnb.com/v2"


class AirbnbAdapter(PlatformAdapter):
    """
    Publicerar priser till Airbnb.

    Kräver:
    - AIRBNB_CLIENT_ID (miljövariabel)
    - AIRBNB_CLIENT_SECRET (miljövariabel)
    - AIRBNB_ACCESS_TOKEN (miljövariabel, hämtas via OAuth)
    """

    def __init__(self):
        self.access_token = os.getenv("AIRBNB_ACCESS_TOKEN")
        self.client_id = os.getenv("AIRBNB_CLIENT_ID")
        self.client_secret = os.getenv("AIRBNB_CLIENT_SECRET")

        if not self.access_token:
            logger.warning("AIRBNB_ACCESS_TOKEN saknas - adapter i simuleringsläge")

        # Mapping: crm_property_id -> airbnb_listing_id
        # Fylls i när vi har riktiga listing-ids
        self._listing_map: dict[str, str] = {
            # "enskede-79": "AIRBNB_LISTING_ID_HÄR",
        }

    def validate_connection(self) -> bool:
        """Testar att Airbnb-anslutningen fungerar."""
        if not self.access_token:
            logger.info("Simuleringsläge: ingen riktig anslutning")
            return False

        try:
            resp = requests.get(
                f"{AIRBNB_API_BASE}/account",
                headers=self._headers(),
                timeout=10,
            )
            return resp.status_code == 200
        except Exception as e:
            logger.error(f"Airbnb-anslutning misslyckades: {e}")
            return False

    def get_listing_id(self, crm_property_id: str) -> Optional[str]:
        """Returnerar Airbnbs listing-id för ett objekt."""
        return self._listing_map.get(crm_property_id)

    def publish_prices(self, updates: list[PriceUpdate]) -> AdapterResult:
        """
        Publicerar priser till Airbnb.

        Om access_token saknas körs i simuleringsläge —
        loggar vad som SKULLE ha publicerats, utan att göra riktiga anrop.
        """
        if not self.access_token:
            return self._simulate(updates)

        errors = []
        published = 0

        # Gruppera updates per listing_id
        by_listing: dict[str, list[PriceUpdate]] = {}
        for u in updates:
            listing_id = self.get_listing_id(u.property_id)
            if not listing_id:
                errors.append(f"Inget listing-id för {u.property_id}")
                continue
            by_listing.setdefault(listing_id, []).append(u)

        # Publicera per listing
        for listing_id, listing_updates in by_listing.items():
            try:
                result = self._put_calendar(listing_id, listing_updates)
                if result:
                    published += len(listing_updates)
                else:
                    errors.append(f"Misslyckades publicera {listing_id}")
            except Exception as e:
                errors.append(f"Fel för {listing_id}: {str(e)}")

        return AdapterResult(
            success=len(errors) == 0,
            property_id=updates[0].property_id if updates else "",
            dates_updated=published,
            errors=errors,
            message=f"Publicerade {published} priser till Airbnb" + (f" ({len(errors)} fel)" if errors else ""),
        )

    def _put_calendar(self, listing_id: str, updates: list[PriceUpdate]) -> bool:
        """
        Uppdaterar Airbnbs kalender för ett listing.

        Airbnb API: PUT /v2/calendars/{listing_id}
        """
        # Bygg payload enligt Airbnbs format
        days = []
        for u in updates:
            day = {
                "date": u.date.isoformat(),
                "price": {"local_price": float(u.price), "local_currency": "SEK"},
                "availability": "available",
            }
            if u.min_nights:
                day["min_nights"] = u.min_nights
            days.append(day)

        payload = {"listing_id": listing_id, "days": days}

        resp = requests.put(
            f"{AIRBNB_API_BASE}/calendars/{listing_id}",
            json=payload,
            headers=self._headers(),
            timeout=30,
        )

        if resp.status_code not in (200, 204):
            logger.error(f"Airbnb API fel {resp.status_code}: {resp.text}")
            return False

        return True

    def _simulate(self, updates: list[PriceUpdate]) -> AdapterResult:
        """
        Simuleringsläge — loggar utan att göra riktiga API-anrop.
        Används tills vi har riktiga credentials.
        """
        logger.info(f"[SIMULERING] Skulle publicera {len(updates)} priser till Airbnb:")
        for u in updates[:5]:  # Visa max 5 i loggen
            logger.info(f"  {u.date}: {u.price} SEK (listing: {u.platform_listing_id or 'okänt'})")
        if len(updates) > 5:
            logger.info(f"  ... och {len(updates) - 5} till")

        return AdapterResult(
            success=True,
            property_id=updates[0].property_id if updates else "",
            dates_updated=len(updates),
            errors=[],
            message=f"[SIMULERING] {len(updates)} priser redo att publiceras till Airbnb",
        )

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
            "X-Airbnb-API-Key": self.client_id or "",
        }
