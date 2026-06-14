"""
Pricelabs-adapter - publicerar priser till Airbnb via Pricelabs API.

Pricelabs ar en godkand Airbnb-partner som tar emot priser
fran externa system och publicerar dem till Airbnb.

API-dokumentation: https://pricelabs.co/api/docs
"""

import os
import logging
from datetime import date
from decimal import Decimal
from typing import Optional

import requests

from adapters.base import PlatformAdapter, PriceUpdate, AdapterResult

logger = logging.getLogger(__name__)

PRICELABS_API_BASE = "https://api.pricelabs.co/v1"


class PricelabsAdapter(PlatformAdapter):
    """
    Publicerar priser till Airbnb via Pricelabs.

    Kräver:
    - PRICELABS_API_KEY (miljövariabel)
    """

    def __init__(self):
        self.api_key = os.getenv("PRICELABS_API_KEY")
        if not self.api_key:
            logger.warning("PRICELABS_API_KEY saknas")

        # Mapping: crm_property_id -> pricelabs listing_id
        self._listing_map: dict[str, str] = {
            "enskede-79": "1675878393965009957",
        }

    def validate_connection(self) -> bool:
        """Testar att Pricelabs-anslutningen fungerar."""
        try:
            resp = requests.get(
                f"{PRICELABS_API_BASE}/listings",
                headers=self._headers(),
                timeout=10,
            )
            ok = resp.status_code == 200
            if ok:
                logger.info("Pricelabs-anslutning OK")
            else:
                logger.error(f"Pricelabs svarade {resp.status_code}: {resp.text}")
            return ok
        except Exception as e:
            logger.error(f"Pricelabs-anslutning misslyckades: {e}")
            return False

    def get_listing_id(self, crm_property_id: str) -> Optional[str]:
        return self._listing_map.get(crm_property_id)

    def publish_prices(self, updates: list[PriceUpdate]) -> AdapterResult:
        """
        Publicerar priser till Pricelabs.

        Pricelabs API tar emot en lista med datum och priser
        per listing och synkar dem till Airbnb.
        """
        if not self.api_key:
            return AdapterResult(
                success=False,
                property_id=updates[0].property_id if updates else "",
                dates_updated=0,
                errors=["PRICELABS_API_KEY saknas"],
                message="Fel: API-nyckel saknas",
            )

        errors = []
        published = 0

        # Gruppera per listing
        by_listing: dict[str, list[PriceUpdate]] = {}
        for u in updates:
            listing_id = self.get_listing_id(u.property_id)
            if not listing_id:
                errors.append(f"Inget listing-id for {u.property_id}")
                continue
            by_listing.setdefault(listing_id, []).append(u)

        for listing_id, listing_updates in by_listing.items():
            try:
                result = self._push_prices(listing_id, listing_updates)
                if result:
                    published += len(listing_updates)
                else:
                    errors.append(f"Misslyckades publicera listing {listing_id}")
            except Exception as e:
                errors.append(f"Fel for listing {listing_id}: {str(e)}")
                logger.error(f"Pricelabs push-fel: {e}")

        return AdapterResult(
            success=len(errors) == 0,
            property_id=updates[0].property_id if updates else "",
            dates_updated=published,
            errors=errors,
            message=f"Publicerade {published} priser till Pricelabs/Airbnb" + (f" ({len(errors)} fel)" if errors else ""),
        )

    def _push_prices(self, listing_id: str, updates: list[PriceUpdate]) -> bool:
        """
        Pushar priser till Pricelabs API.

        Format: POST /v1/listings/{listing_id}/pricing
        """
        pricing = [
            {
                "date": u.date.isoformat(),
                "price": float(u.price),
            }
            for u in updates
        ]

        payload = {
            "listing_id": listing_id,
            "pricing": pricing,
        }

        resp = requests.post(
            f"{PRICELABS_API_BASE}/listings/{listing_id}/pricing",
            json=payload,
            headers=self._headers(),
            timeout=30,
        )

        if resp.status_code not in (200, 201, 204):
            logger.error(f"Pricelabs API-fel {resp.status_code}: {resp.text}")
            return False

        logger.info(f"Pricelabs: {len(updates)} priser publicerade for listing {listing_id}")
        return True

    def _headers(self) -> dict:
        return {
            "X-API-Key": self.api_key or "",
            "Content-Type": "application/json",
        }
