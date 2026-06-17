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

    Listing-ID mappning hämtas automatiskt från Pricelabs API
    och matchas mot objektnamn i databasen. Manuell fallback
    finns för kända objekt.
    """

    def __init__(self):
        self.api_key = os.getenv("PRICELABS_API_KEY")
        if not self.api_key:
            logger.warning("PRICELABS_API_KEY saknas")

        # Manuell fallback-mapping: crm_property_id -> pricelabs listing_id
        # Används om auto-discovery misslyckas
        self._fallback_map: dict[str, str] = {
            "enskede-79":      "1675878393965009957",
            "trosa-havsdrom":  "1673099638596438222",
            "alta-beach-villa": "1654943677598237856",
            "alvsjö-tradgard": "1678065319412002223",
        }

        # Cache för auto-hämtade listings: {listing_id: listing_name}
        self._listings_cache: dict[str, str] | None = None

    def _fetch_all_listings(self) -> dict[str, str]:
        """
        Hämtar alla listings från Pricelabs och returnerar
        {listing_id: listing_name} för matchning mot objekt.
        Cachas per instans.
        """
        if self._listings_cache is not None:
            return self._listings_cache

        try:
            resp = requests.get(
                f"{PRICELABS_API_BASE}/listings",
                headers=self._headers(),
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                # Pricelabs returnerar lista med listing-objekt
                listings = data if isinstance(data, list) else data.get("listings", [])
                self._listings_cache = {
                    str(l.get("id", l.get("listing_id", ""))): l.get("name", l.get("nickname", ""))
                    for l in listings
                    if l.get("id") or l.get("listing_id")
                }
                logger.info(f"Pricelabs: hämtade {len(self._listings_cache)} listings")
                return self._listings_cache
            else:
                logger.warning(f"Pricelabs /listings svarade {resp.status_code}")
                return {}
        except Exception as e:
            logger.error(f"Kunde inte hämta Pricelabs listings: {e}")
            return {}

    def get_listing_id(self, crm_property_id: str) -> Optional[str]:
        """
        Försöker hitta listing-ID via tre strategier:
        1. Exakt match i fallback-map (snabbast)
        2. Auto-match via Pricelabs API — matchar crm_property_id mot listing-namn
        3. Loggar tillgängliga listings om ingen match hittas
        """
        # 1. Fallback-map
        if crm_property_id in self._fallback_map:
            return self._fallback_map[crm_property_id]

        # 2. Auto-discovery via Pricelabs API
        listings = self._fetch_all_listings()
        if listings:
            # Normalisera crm_property_id för matchning
            # t.ex. "trosa-havsdrom" → matchar "havsdröm" eller "trosa"
            search_terms = crm_property_id.lower().replace("-", " ").split()

            for listing_id, listing_name in listings.items():
                name_lower = listing_name.lower()
                if any(term in name_lower for term in search_terms if len(term) > 3):
                    logger.info(f"Auto-matchade {crm_property_id} → {listing_id} ({listing_name})")
                    # Spara i fallback för nästa anrop
                    self._fallback_map[crm_property_id] = listing_id
                    return listing_id

            # Ingen match — logga tillgängliga listings för felsökning
            logger.warning(
                f"Inget listing-id hittades för '{crm_property_id}'. "
                f"Tillgängliga listings: {list(listings.values())}"
            )

        return None

    def list_all_listings(self) -> dict[str, str]:
        """Returnerar alla Pricelabs listings för debugging/admin."""
        return self._fetch_all_listings()

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
                listings = self._fetch_all_listings()
                logger.info(f"Pricelabs-anslutning OK — {len(listings)} listings")
            else:
                logger.error(f"Pricelabs svarade {resp.status_code}: {resp.text}")
            return ok
        except Exception as e:
            logger.error(f"Pricelabs-anslutning misslyckades: {e}")
            return False

    def publish_prices(self, updates: list[PriceUpdate]) -> AdapterResult:
        """
        Publicerar priser till Pricelabs.
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
        Pushar priser till Pricelabs via overrides-endpoint.
        """
        overrides = [
            {
                "date": u.date.isoformat(),
                "price": str(int(u.price)),
                "price_type": "fixed",
                "currency": "SEK",
            }
            for u in updates
        ]

        payload = {
            "pms": "airbnb",
            "overrides": overrides,
        }

        resp = requests.post(
            f"{PRICELABS_API_BASE}/listings/{listing_id}/overrides",
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
