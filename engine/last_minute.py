"""
Last-minute prissattning.

Rabattkurvan ar mjuk och gradvis - inte ett hack.
Matematisk modell: exponentiell kurva fran 0% till max_discount.

Exempel med start_days=20, max_discount=20%:
  20 dagar kvar:  -0%   (ingen rabatt)
  15 dagar kvar:  -5%
  10 dagar kvar:  -10%
   7 dagar kvar:  -14%
   3 dagar kvar:  -18%
   1 dag kvar:    -20%
   0 dagar kvar:  -20%  (max)

Skyddsracke: priset far aldrig ga under minimum lonsamt pris.
Det minimumet beraknas som:
  Stadskostnad (exkl moms) + Norlis provision + min agarnetto
"""

import math
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from db.models import Property


def calculate_last_minute_factor(
    prop: Property,
    target_date: date,
    today: Optional[date] = None,
) -> tuple[Decimal, int]:
    """
    Beraknar last-minute-multiplikatorn for ett givet datum.

    Returnerar (multiplikator, dagar_kvar).
    Multiplikator 1.0 = ingen rabatt, 0.80 = 20% rabatt.
    """
    if not prop.last_minute_enabled:
        return Decimal("1.0"), 0

    today = today or date.today()
    days_until = (target_date - today).days

    if days_until < 0:
        # Passerat datum - ingen rabatt
        return Decimal("1.0"), 0

    start_days = prop.last_minute_start_days or 20
    max_discount = prop.last_minute_max_discount or Decimal("0.20")

    if days_until >= start_days:
        # Utanfor rabattfonstret - fullt pris
        return Decimal("1.0"), days_until

    if days_until == 0:
        # Sista dagen - max rabatt
        factor = Decimal("1.0") - max_discount
        return factor, 0

    # Mjuk exponentiell kurva
    # Nar days_until narmar sig 0, okar rabatten exponentiellt
    # ratio: 0.0 = sista dagen, 1.0 = borjan av rabattfonstret
    ratio = days_until / start_days

    # Exponentiell kurva: discount = max_discount * (1 - ratio^1.5)
    # ^1.5 ger mjuk inledning och snabbare rabatt de sista dagarna
    discount_pct = float(max_discount) * (1 - ratio ** 1.5)
    discount = Decimal(str(round(discount_pct, 4)))

    factor = (Decimal("1.0") - discount).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)

    return factor, days_until


def apply_last_minute_floor(
    price: Decimal,
    prop: Property,
    nights: int = 1,
) -> tuple[Decimal, bool]:
    """
    Klampar last-minute-priset mot minimum lonsamt pris.

    Returnerar (slutpris, klampat).
    """
    # Anvand manuellt satt minimum om det finns
    if prop.last_minute_min_price:
        min_price = prop.last_minute_min_price
    else:
        # Berakna minimum lonsamt pris:
        # Stadskostnad (enkel uppskattning: base_hours * hourly_rate / nights)
        cleaning_per_night = Decimal("0")
        if prop.cleaning_hourly_rate and prop.cleaning_base_hours:
            cleaning_total = prop.cleaning_hourly_rate * prop.cleaning_base_hours
            cleaning_per_night = (cleaning_total / nights).quantize(Decimal("1"), rounding=ROUND_HALF_UP)

        # Norlis provision av avrakningsgrunden
        # Avrakningsgrund ≈ pris * (1 - platform_fee - vat_rate/(1+vat_rate))
        # Vi anvander baspriset * norli_share som approximation
        norli_cut_pct = prop.norli_share_pct or Decimal("0.18")
        platform_fee = prop.platform_fee_rate or Decimal("0.03")
        vat_rate = prop.vat_rate or Decimal("0.12")
        vat_factor = vat_rate / (1 + vat_rate)

        # Min pris = det pris dar agaren atar minst 0 efter alla avdrag
        # Forenkl: min_price = cleaning_per_night / (owner_share * (1 - platform - vat))
        owner_share = prop.owner_share_pct or Decimal("0.82")
        net_factor = owner_share * (1 - platform_fee - vat_factor)

        if net_factor > 0 and cleaning_per_night > 0:
            min_price = (cleaning_per_night / net_factor).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        else:
            # Fallback: anvand prisgolvet om det finns
            min_price = prop.price_floor or Decimal("0")

    if price < min_price:
        return min_price, True

    return price, False


def get_last_minute_description(days_until: int, factor: Decimal) -> str:
    """Returnerar en lasbar beskrivning av last-minute-rabatten."""
    if factor >= Decimal("1.0"):
        return ""
    discount_pct = int((1 - factor) * 100)
    if days_until == 0:
        return f"Idag! -{discount_pct}% last-minute"
    elif days_until == 1:
        return f"Imorgon -{discount_pct}% last-minute"
    else:
        return f"{days_until} dagar kvar -{discount_pct}% last-minute"
