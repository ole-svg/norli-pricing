"""
Publisher - koordinerar publicering fran prismotorn till plattformar.

Används av:
- Schemalagda nattjobb (publicerar alla objekt)
- Manuell trigger via API
- Vid regeländringar (publicerar enskilt objekt)
"""

import logging
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from db.models import Property, PriceSnapshot
from adapters.base import PriceUpdate, AdapterResult
from adapters.airbnb import AirbnbAdapter

logger = logging.getLogger(__name__)


class Publisher:
    """Publicerar priser från databasen till plattformar."""

    def __init__(self, db: Session):
        self.db = db
        self.airbnb = AirbnbAdapter()

    def publish_property(
        self,
        crm_property_id: str,
        days_ahead: int = 365,
    ) -> AdapterResult:
        """
        Publicerar alla priser för ett objekt till Airbnb.

        Hämtar sparade snapshots från databasen och skickar
        till Airbnb. Sätter published_price = recommended_price
        om inget manuellt pris finns.
        """
        prop = self.db.query(Property).filter(
            Property.crm_property_id == crm_property_id
        ).first()

        if not prop:
            return AdapterResult(
                success=False,
                property_id=crm_property_id,
                dates_updated=0,
                errors=[f"Objekt '{crm_property_id}' hittades inte"],
                message="Fel: objekt saknas",
            )

        start = date.today()
        end = start + timedelta(days=days_ahead)

        snapshots = (
            self.db.query(PriceSnapshot)
            .filter(
                PriceSnapshot.property_id == prop.id,
                PriceSnapshot.date >= start,
                PriceSnapshot.date <= end,
            )
            .order_by(PriceSnapshot.date)
            .all()
        )

        if not snapshots:
            return AdapterResult(
                success=False,
                property_id=crm_property_id,
                dates_updated=0,
                errors=["Inga prissnapshots att publicera - kör omräkning först"],
                message="Inga priser att publicera",
            )

        # Bygg PriceUpdate-lista
        updates = []
        for snap in snapshots:
            price = snap.published_price or snap.recommended_price
            updates.append(PriceUpdate(
                property_id=crm_property_id,
                platform_listing_id=self.airbnb.get_listing_id(crm_property_id) or "",
                date=snap.date,
                price=price,
            ))

            # Uppdatera published_price i databasen
            if not snap.published_price:
                snap.published_price = snap.recommended_price

        self.db.commit()

        # Publicera till Airbnb
        result = self.airbnb.publish_prices(updates)
        logger.info(result.message)
        return result

    def publish_all(self, days_ahead: int = 365) -> list[AdapterResult]:
        """Publicerar alla aktiva objekt."""
        properties = self.db.query(Property).filter(Property.is_active == True).all()
        results = []
        for prop in properties:
            result = self.publish_property(prop.crm_property_id, days_ahead)
            results.append(result)
            logger.info(f"{prop.name}: {result.message}")
        return results
