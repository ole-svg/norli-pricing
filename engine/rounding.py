"""
Prisavrundning innan publicering till Airbnb/Pricelabs.

Tiered-regeln (standard):
  < 1 000 kr:   narmaste 50 kr
  1 000-3 000:  narmaste 100 kr
  3 000-6 000:  narmaste 100 kr
  > 6 000 kr:   narmaste 200 kr

Snygg avrundning ger professionellt intryck.
2 847 kr -> 2 800 kr  ✓
4 427 kr -> 4 400 kr  ✓
6 537 kr -> 6 600 kr  ✓
"""

from decimal import Decimal, ROUND_HALF_UP


def round_price(price: Decimal, rule: str = "tiered") -> Decimal:
    """
    Avrundar priset enligt vald regel.
    
    Args:
        price: Priset att avrunda
        rule: "tiered" (standard) | "nearest_50" | "nearest_100" | "nearest_200"
    
    Returns:
        Avrundat pris
    """
    p = float(price)

    if rule == "nearest_50":
        step = 50
    elif rule == "nearest_100":
        step = 100
    elif rule == "nearest_200":
        step = 200
    else:
        # tiered — vart standard
        if p < 1000:
            step = 50
        elif p < 6000:
            step = 100
        else:
            step = 200

    rounded = round(p / step) * step
    return Decimal(str(int(rounded)))


def apply_rounding(price: Decimal, rule: str = "tiered") -> tuple[Decimal, bool]:
    """
    Applicerar avrundning och returnerar (avrundat_pris, avrundades).
    """
    rounded = round_price(price, rule)
    was_rounded = rounded != price
    return rounded, was_rounded


# Testa
if __name__ == "__main__":
    test_cases = [847, 1340, 2847, 3500, 4427, 5145, 6037, 6537, 7200]
    print("Tiered avrundning:")
    print(f"{'Originalt':>12} {'Avrundat':>12} {'Steg':>8}")
    print("-" * 36)
    for p in test_cases:
        d = Decimal(str(p))
        r = round_price(d, "tiered")
        step = 50 if p < 1000 else 200 if p >= 6000 else 100
        print(f"{p:>12,} {int(r):>12,} {step:>8}")
