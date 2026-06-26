"""
engine/los.py
LOS-prissättning (Length of Stay) — Modell C (Hybrid)

Baserat på extern expertanalys (juni 2026):
- Normalpris = 4 nätters kostnadsbas
- Kortvistelsepremie i motorn, långvistelserabatt i presentationen
- Städkostnadskurva per objektkategori
- Min stay som skydd mot olönsamma korta bokningar

Tre profiler:
  urban_hotel  — Enskede, Älta, Älvsjö (max 12 gäster, standard 8)
  suburban     — Större villor utanför city (standard 6 av 8 gäster)
  destination  — Trosa, Ronneby, Oxelösund, Klassbol (säsongsstyrd)
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Optional


@dataclass
class LOSResult:
    """LOS-beräkning för ett givet antal nätter."""
    nights: int
    multiplier: Decimal
    min_stay: int
    label: str


@dataclass
class CleaningCost:
    """Städkostnad för en bokning."""
    hours: Decimal
    cost: Decimal
    label: str


# ── Städkostnadskurvor per profil ────────────────────────────────────────────
# Timkostnad städ: 500 kr/h ex moms
# Enskede: standard 8 av 12 gäster
# Kurvan planar ut efter 5 nätter

CLEANING_CURVES = {
    "urban_hotel": [
        # (max_nights, hours, label)
        (1,  Decimal("3.0"),  "3h (1 natt, 8 gäster standard)"),
        (2,  Decimal("3.5"),  "3,5h (2 nätter)"),
        (3,  Decimal("4.0"),  "4h (3 nätter)"),
        (4,  Decimal("4.5"),  "4,5h (4 nätter)"),
        (5,  Decimal("5.0"),  "5h (5+ nätter, tak)"),
    ],
    "suburban": [
        (1,  Decimal("3.5"),  "3,5h (1 natt, 6 gäster standard)"),
        (2,  Decimal("4.0"),  "4h (2 nätter)"),
        (3,  Decimal("4.5"),  "4,5h (3 nätter)"),
        (4,  Decimal("5.0"),  "5h (4 nätter)"),
        (5,  Decimal("5.5"),  "5,5h (5+ nätter, tak)"),
    ],
    "destination": [
        (1,  Decimal("4.0"),  "4h (1 natt, större hus)"),
        (2,  Decimal("4.5"),  "4,5h (2 nätter)"),
        (3,  Decimal("5.0"),  "5h (3 nätter)"),
        (4,  Decimal("5.5"),  "5,5h (4 nätter)"),
        (5,  Decimal("6.0"),  "6h (5+ nätter, tak)"),
    ],
}

CLEANING_RATE = Decimal("500")  # kr/h ex moms
OBJECT_COST_PER_BOOKING = Decimal("200")  # admin, slitage etc


def get_cleaning_cost(profile: str, nights: int) -> CleaningCost:
    """Beräknar städkostnad för given profil och antal nätter."""
    curve = CLEANING_CURVES.get(profile, CLEANING_CURVES["urban_hotel"])
    hours = curve[-1][1]  # default: sista (tak)
    label = curve[-1][2]
    for max_n, h, lbl in curve:
        if nights <= max_n:
            hours = h
            label = lbl
            break
    cost = hours * CLEANING_RATE + OBJECT_COST_PER_BOOKING
    return CleaningCost(hours=hours, cost=cost, label=label)


# ── LOS-multiplikatorer per profil (Modell C) ────────────────────────────────
# Referenspunkt: 4 nätter = 1.00 (normalpris)
# Källa: ChatGPT expertanalys juni 2026

URBAN_HOTEL_LOS: list[tuple[int, int, Decimal, str]] = [
    # (min_nights, max_nights, multiplier, label)
    (1,  1,  Decimal("1.30"), "1 natt: +30% engångspremie"),
    (2,  2,  Decimal("1.12"), "2 nätter: +12%"),
    (3,  3,  Decimal("1.04"), "3 nätter: +4%"),
    (4,  4,  Decimal("1.00"), "4 nätter: normalpris"),
    (5,  5,  Decimal("0.98"), "5 nätter: -2%"),
    (6,  6,  Decimal("0.96"), "6 nätter: -4%"),
    (7,  13, Decimal("0.90"), "7-13 nätter: veckorabatt -10%"),
    (14, 27, Decimal("0.86"), "14-27 nätter: -14%"),
    (28, 9999, Decimal("0.78"), "28+ nätter: månadsrabatt -22%"),
]

SUBURBAN_LOS: list[tuple[int, int, Decimal, str]] = [
    (1,  1,  Decimal("1.40"), "1 natt: +40% engångspremie"),
    (2,  2,  Decimal("1.18"), "2 nätter: +18%"),
    (3,  3,  Decimal("1.06"), "3 nätter: +6%"),
    (4,  4,  Decimal("1.00"), "4 nätter: normalpris"),
    (5,  5,  Decimal("0.97"), "5 nätter: -3%"),
    (6,  6,  Decimal("0.95"), "6 nätter: -5%"),
    (7,  13, Decimal("0.90"), "7-13 nätter: veckorabatt -10%"),
    (14, 27, Decimal("0.85"), "14-27 nätter: -15%"),
    (28, 9999, Decimal("0.75"), "28+ nätter: månadsrabatt -25%"),
]

DESTINATION_LOS_HIGHSEASON: list[tuple[int, int, Decimal, str]] = [
    # Högsäsong (jul/aug): 1 natt ej tillåten, start på 2
    (1,  1,  Decimal("1.50"), "1 natt: ej rekommenderat högsäsong"),
    (2,  2,  Decimal("1.30"), "2 nätter: +30% högsäsong"),
    (3,  3,  Decimal("1.12"), "3 nätter: +12% högsäsong"),
    (4,  4,  Decimal("1.05"), "4 nätter: +5% högsäsong"),
    (5,  6,  Decimal("1.00"), "5-6 nätter: normalpris högsäsong"),
    (7,  13, Decimal("0.97"), "7-13 nätter: -3% högsäsong"),
    (14, 9999, Decimal("0.92"), "14+ nätter: -8% högsäsong"),
]

DESTINATION_LOS_LOWSEASON: list[tuple[int, int, Decimal, str]] = [
    # Lågsäsong: mer flexibel
    (1,  1,  Decimal("1.45"), "1 natt: +45% lågsäsong"),
    (2,  2,  Decimal("1.20"), "2 nätter: +20%"),
    (3,  3,  Decimal("1.08"), "3 nätter: +8%"),
    (4,  4,  Decimal("1.00"), "4 nätter: normalpris"),
    (5,  6,  Decimal("0.97"), "5-6 nätter: -3%"),
    (7,  13, Decimal("0.90"), "7-13 nätter: veckorabatt -10%"),
    (14, 27, Decimal("0.85"), "14-27 nätter: -15%"),
    (28, 9999, Decimal("0.75"), "28+ nätter: månadsrabatt -25%"),
]


# ── Min stay per profil ───────────────────────────────────────────────────────

URBAN_HOTEL_MIN_STAY: dict[int, int] = {
    0: 1, 1: 1, 2: 1, 3: 1,  # mån-tor: 1 natt OK
    4: 2,                      # fre: min 2 nätter
    5: 2,                      # lör: min 2 nätter
    6: 1,                      # sön: 1 natt OK
}

SUBURBAN_MIN_STAY: dict[int, int] = {
    0: 1, 1: 1, 2: 1, 3: 2,  # tor: 2 nätter
    4: 2,                      # fre: 2 nätter
    5: 2,                      # lör: 2 nätter
    6: 1,
}


def get_los_multiplier(
    profile: str,
    nights: int,
    weekly_discount_pct: Optional[Decimal] = None,
    monthly_discount_pct: Optional[Decimal] = None,
    is_high_season: bool = False,
) -> LOSResult:
    """
    Returnerar LOS-multiplikator för givet antal nätter och profil.
    Modell C: normalpris vid 4 nätter, premie kortare, rabatt längre.
    """
    if profile == "urban_hotel":
        table = URBAN_HOTEL_LOS
    elif profile == "suburban":
        table = SUBURBAN_LOS
    else:  # destination
        table = DESTINATION_LOS_HIGHSEASON if is_high_season else DESTINATION_LOS_LOWSEASON

    for min_n, max_n, mult, label in table:
        if min_n <= nights <= max_n:
            # Objektspecifik vecko/månadsrabatt override
            if nights >= 28 and monthly_discount_pct is not None:
                actual_mult = Decimal("1.00") - (monthly_discount_pct / Decimal("100"))
                return LOSResult(nights=nights, multiplier=actual_mult, min_stay=1,
                                 label=f"28+ nätter: månadsrabatt -{monthly_discount_pct}%")
            if nights >= 7 and weekly_discount_pct is not None:
                actual_mult = Decimal("1.00") - (weekly_discount_pct / Decimal("100"))
                return LOSResult(nights=nights, multiplier=actual_mult, min_stay=1,
                                 label=f"7+ nätter: veckorabatt -{weekly_discount_pct}%")
            return LOSResult(nights=nights, multiplier=mult, min_stay=1, label=label)

    return LOSResult(nights=nights, multiplier=Decimal("1.00"), min_stay=1, label="Standard")


def get_min_stay(
    profile: str,
    target_date: date,
    is_high_season: bool = False,
    custom_min_stay: Optional[int] = None,
) -> int:
    """Beräknar min_stay för ett givet datum och profil."""
    if custom_min_stay is not None:
        return custom_min_stay

    if profile == "destination":
        return 3 if is_high_season else 2

    if profile == "suburban":
        return SUBURBAN_MIN_STAY.get(target_date.weekday(), 1)

    # urban_hotel
    return URBAN_HOTEL_MIN_STAY.get(target_date.weekday(), 1)


def get_los_table_for_publishing(
    profile: str,
    is_high_season: bool = False,
    weekly_discount_pct: Optional[Decimal] = None,
    monthly_discount_pct: Optional[Decimal] = None,
) -> list[dict]:
    """
    Returnerar LOS-tabellen i format redo för PriceLabs-publicering.
    Skickas separat från dagspriser.
    """
    results = []
    for nights in [1, 2, 3, 4, 5, 6, 7, 14, 28]:
        result = get_los_multiplier(
            profile=profile,
            nights=nights,
            weekly_discount_pct=weekly_discount_pct,
            monthly_discount_pct=monthly_discount_pct,
            is_high_season=is_high_season,
        )
        pct_change = (result.multiplier - Decimal("1.00")) * 100
        results.append({
            "nights": nights,
            "multiplier": float(result.multiplier),
            "pct_change": float(pct_change),
            "label": result.label,
        })
    return results


def is_high_season_date(d: date) -> bool:
    """Högsäsongskontroll — juli, aug, sportlov, påsklov."""
    if d.month in (7, 8):
        return True
    if d.month == 2 and 16 <= d.day <= 28:
        return True
    if d.month == 4 and 1 <= d.day <= 14:
        return True
    return False
