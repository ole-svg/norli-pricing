"""
Prisavrundning innan publicering till Airbnb/Pricelabs.

Standard: narmaste 10-tal — snyggt och konsekvent oavsett belopp.

Exempel:
  4 427 kr -> 4 430 kr
  5 145 kr -> 5 150 kr
  6 037 kr -> 6 040 kr
  3 931 kr -> 3 930 kr
"""

from decimal import Decimal


def round_price(price: Decimal, rule: str = "nearest_10") -> Decimal:
    """
    Avrundar priset till jamna tiotal (standard).
    
    Args:
        price: Priset att avrunda
        rule: "nearest_10" (standard) | "nearest_50" | "nearest_100"
    
    Returns:
        Avrundat pris
    """
    p = float(price)

    step = {
        "nearest_10": 10,
        "nearest_50": 50,
        "nearest_100": 100,
        "nearest_200": 200,
        "tiered": 10,  # tiered ar nu alias for nearest_10
    }.get(rule, 10)

    rounded = round(p / step) * step
    return Decimal(str(int(rounded)))


def apply_rounding(price: Decimal, rule: str = "nearest_10") -> tuple[Decimal, bool]:
    """
    Applicerar avrundning och returnerar (avrundat_pris, avrundades).
    """
    rounded = round_price(price, rule)
    was_rounded = rounded != price
    return rounded, was_rounded


if __name__ == "__main__":
    test_cases = [847, 1340, 2847, 3931, 4427, 5145, 6037, 6537, 7203]
    print("Nearest-10 avrundning:")
    print(f"{"Original":>12} {"Avrundat":>12}")
    print("-" * 26)
    for p in test_cases:
        d = Decimal(str(p))
        r = round_price(d, "nearest_10")
        print(f"{p:>12,} {int(r):>12,}")
