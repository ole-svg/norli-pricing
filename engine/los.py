"""
engine/los.py
LOS-prissättning (Length of Stay) och min_stay per objekt och datum.

Två profiler:
  urban_hotel  — Enskede, Älta, Älvsjö Trädgård
                 Högt 1-nattspris, tydlig trappa ner mot marknadspris vid 3+ nätter
  destination  — Trosa, Ronneby
                 Säsongsstyrd, sällan 1-natt, min_stay styr mer än LOS-rabatt
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Optional


@dataclass
class LOSResult:
    """LOS-beräkning för ett givet antal nätter."""
    nights: int
    multiplier: Decimal      # påslag/rabatt på nattpriset
    min_stay: int            # miniminätter för detta datum
    label: str               # förklaring, t.ex. "1 natt: +43% engångspremium"


# ── Urban hotel-profil ──────────────────────────────────────────────────────
# Baserat på Enskedemall: baspris = 3-4 nätters marknadspris
# 1 natt: +43%  (~6 000 på 4 200-bas)
# 2 nätter: +7%  (~4 500)
# 3 nätter: ±0%  (marknadspris, bas)
# 4 nätter: -5%
# 5 nätter: -7%
# 6 nätter: -10%
# 7+ nätter: weekly_discount_pct (sätts per objekt, default 12%)
# 14+ nätter: monthly_discount_pct (sätts per objekt, default 18%)

URBAN_HOTEL_LOS: list[tuple[int, int, Decimal, str]] = [
    # (min_nights, max_nights, multiplier, label)
    (1,  1,  Decimal("1.43"), "1 natt: engångspremium +43%"),
    (2,  2,  Decimal("1.07"), "2 nätter: +7%"),
    (3,  3,  Decimal("1.00"), "3 nätter: marknadspris"),
    (4,  4,  Decimal("0.95"), "4 nätter: -5%"),
    (5,  5,  Decimal("0.93"), "5 nätter: -7%"),
    (6,  6,  Decimal("0.90"), "6 nätter: -10%"),
    (7,  13, Decimal("1.00"), "7+ nätter: veckorabatt (per objekt)"),
    (14, 9999, Decimal("1.00"), "14+ nätter: månadsrabatt (per objekt)"),
]

URBAN_HOTEL_MIN_STAY: dict[int, int] = {
    # weekday (0=mån) → min_stay
    0: 1, 1: 1, 2: 1, 3: 1,  # mån-tor: 1 natt OK
    4: 2,                      # fre: min 2 nätter (helgbokning)
    5: 2,                      # lör: min 2 nätter
    6: 1,                      # sön: 1 natt OK
}


# ── Destination-profil ──────────────────────────────────────────────────────
# Trosa, Ronneby: festrisken gör att vi aldrig vill ha 1 natt
# Säsong styr pris mer än LOS
# Minimal LOS-trappa, fokus på min_stay

DESTINATION_LOS: list[tuple[int, int, Decimal, str]] = [
    (1,  1,  Decimal("1.50"), "1 natt: ej rekommenderat — högt pris"),
    (2,  2,  Decimal("1.10"), "2 nätter: +10%"),
    (3,  6,  Decimal("1.00"), "3-6 nätter: marknadspris"),
    (7,  13, Decimal("1.00"), "7+ nätter: veckorabatt (per objekt)"),
    (14, 9999, Decimal("1.00"), "14+ nätter: månadsrabatt (per objekt)"),
]

DESTINATION_MIN_STAY_DEFAULT = 2  # Aldrig 1 natt som standard
DESTINATION_MIN_STAY_HIGHSEASON = 3  # Jul/aug/sport: 3 nätter minimum


def get_los_multiplier(
    profile: str,
    nights: int,
    weekly_discount_pct: Optional[Decimal] = None,
    monthly_discount_pct: Optional[Decimal] = None,
) -> LOSResult:
    """
    Returnerar LOS-multiplikator och label för givet antal nätter.

    weekly_discount_pct och monthly_discount_pct är objektspecifika rabatter (0-100).
    """
    table = URBAN_HOTEL_LOS if profile == "urban_hotel" else DESTINATION_LOS

    for min_n, max_n, mult, label in table:
        if min_n <= nights <= max_n:
            # Ersätt med objektets weekly/monthly discount om definierat
            if nights >= 14 and monthly_discount_pct is not None:
                actual_mult = Decimal("1.00") - (monthly_discount_pct / Decimal("100"))
                label = f"14+ nätter: månadsrabatt -{monthly_discount_pct}%"
                return LOSResult(nights=nights, multiplier=actual_mult, min_stay=1, label=label)
            elif nights >= 7 and weekly_discount_pct is not None:
                actual_mult = Decimal("1.00") - (weekly_discount_pct / Decimal("100"))
                label = f"7+ nätter: veckorabatt -{weekly_discount_pct}%"
                return LOSResult(nights=nights, multiplier=actual_mult, min_stay=1, label=label)
            return LOSResult(nights=nights, multiplier=mult, min_stay=1, label=label)

    # Fallback
    return LOSResult(nights=nights, multiplier=Decimal("1.00"), min_stay=1, label="Standard")


def get_min_stay(
    profile: str,
    target_date: date,
    is_high_season: bool = False,
    custom_min_stay: Optional[int] = None,
) -> int:
    """
    Beräknar min_stay för ett givet datum och profil.

    custom_min_stay: manuell override per objekt eller datum.
    is_high_season: juli-aug och sportlov → destination får min 3 nätter.
    """
    if custom_min_stay is not None:
        return custom_min_stay

    if profile == "destination":
        if is_high_season:
            return DESTINATION_MIN_STAY_HIGHSEASON
        return DESTINATION_MIN_STAY_DEFAULT

    # urban_hotel: veckodagsbaserat
    return URBAN_HOTEL_MIN_STAY.get(target_date.weekday(), 1)


def is_high_season_date(d: date) -> bool:
    """Enkel högsäsongskontroll — juli, aug, sportlov feb, påsklov apr."""
    if d.month in (7, 8):
        return True
    if d.month == 2 and 16 <= d.day <= 28:  # Sportlov
        return True
    if d.month == 4 and 1 <= d.day <= 14:   # Påsklov
        return True
    return False
