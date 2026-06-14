"""
Basadapter - alla plattformsadaptrar arver fran denna.

En adapter tar motorns beraknade priser och publicerar dem
pa en specifik plattform (Airbnb, Booking.com etc).

Motor -> Adapter -> Plattform

Separationen gor att vi kan lagga till nya plattformar
utan att rora prismotorn.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Optional


@dataclass
class PriceUpdate:
    """Ett pris som ska publiceras pa en plattform."""
    property_id: str          # Norlis interna id (crm_property_id)
    platform_listing_id: str  # Plattformens id for objektet
    date: date
    price: Decimal
    min_nights: Optional[int] = None


@dataclass
class AdapterResult:
    """Resultat fran ett publiceringsforsk."""
    success: bool
    property_id: str
    dates_updated: int
    errors: list[str]
    message: str


class PlatformAdapter(ABC):
    """
    Abstrakt basadapter.
    Varje plattform implementerar sina egna metoder.
    """

    @abstractmethod
    def publish_prices(self, updates: list[PriceUpdate]) -> AdapterResult:
        """Publicerar priser pa plattformen."""
        pass

    @abstractmethod
    def get_listing_id(self, crm_property_id: str) -> Optional[str]:
        """Hamtar plattformens listing-id for ett objekt."""
        pass

    @abstractmethod
    def validate_connection(self) -> bool:
        """Testar att anslutningen till plattformen fungerar."""
        pass
