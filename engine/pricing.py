"""
Deterministisk regelmotor — hjärtat i Norli Pricing Engine.

Principer:
- Samma input ger ALLTID samma output (deterministisk)
- Helt oberoende av AI — fungerar utan det
- Varje steg dokumenteras i prisförklaringen
- Slutpriset klampar alltid mot objektets golv/tak

Beräkningsordning (fast, alltid i denna ordning):
  1. Baspris
  2. Säsong
  3. Veckodag
  4. Helg / röda dagar
  5. Skollov
  6. Lokala evenemang
  7. Vistelselängd (om känd)
  8. Efterfrågejustering (öppen plats för framtida signaler + AI)
  9. Klampning mot golv/tak
"""

import json
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from db.models import Property, Season, CalendarEvent, LocalEvent, PriceRule


ENGINE_VERSION = "1.0.0"

from engine.rounding import apply_rounding

# Importera last-minute-logiken
from engine.last_minute import calculate_last_minute_factor, apply_last_minute_floor, get_last_minute_description

# Multiplikatorer för veckodagar (0=måndag … 6=söndag)
# Kan åsidosättas av objektspecifika PriceRule
DEFAULT_WEEKDAY_MULTIPLIERS = {
    0: Decimal("1.00"),  # Måndag
    1: Decimal("1.00"),  # Tisdag
    2: Decimal("1.00"),  # Onsdag
    3: Decimal("1.05"),  # Torsdag (lite mer efterfrågan in mot helg)
    4: Decimal("1.15"),  # Fredag
    5: Decimal("1.20"),  # Lördag
    6: Decimal("1.10"),  # Söndag
}


@dataclass
class PriceStep:
    """Ett steg i prisberäkningen — bygger upp förklaringen."""
    label: str          # t.ex. "Baspris", "Högsäsong sommar"
    factor: Decimal     # multiplikator, t.ex. 1.30
    price_after: Decimal  # priset efter detta steg


@dataclass
class PriceResult:
    """
    Resultatet från regelmotorn för ett objekt och ett datum.

    Innehåller det rekommenderade priset OCH en fullständig
    förklaring av hur det räknades fram.
    """
    property_id: int
    date: date
    recommended_price: Decimal
    explanation: str          # läsbar sammanfattning
    steps: list[PriceStep]    # detaljerade steg
    is_clamped_floor: bool = False
    is_clamped_ceiling: bool = False
    engine_version: str = ENGINE_VERSION


class PricingEngine:
    """
    Räknar ut det rekommenderade priset för ett objekt och ett datum.

    Används så här:
        engine = PricingEngine(property, seasons, calendar_events, local_events)
        result = engine.calculate(target_date, nights=3)
    """

    def __init__(
        self,
        property: Property,
        seasons: list[Season],
        calendar_events: list[CalendarEvent],
        local_events: list[LocalEvent],
    ):
        self.property = property
        self.seasons = seasons
        self.calendar_events = calendar_events
        self.local_events = local_events

    def calculate(
        self,
        target_date: date,
        nights: Optional[int] = None,
        demand_adjustment: Optional[Decimal] = None,
    ) -> PriceResult:
        """
        Räknar ut priset för target_date.

        nights: antal nätter i vistelsen (om känt, påverkar längdrabatt)
        demand_adjustment: multiplikator från AI eller externt system (1.0 = ingen justering)
        """
        steps: list[PriceStep] = []
        price = self.property.base_price

        # --- Steg 1: Baspris ---
        steps.append(PriceStep(
            label="Baspris",
            factor=Decimal("1.00"),
            price_after=price,
        ))

        # --- Steg 2: Säsong ---
        season_factor = self._get_season_factor(target_date)
        if season_factor != Decimal("1.00"):
            season_name = self._get_season_name(target_date)
            price = price * season_factor
            steps.append(PriceStep(
                label=f"Säsong: {season_name}",
                factor=season_factor,
                price_after=_round(price),
            ))

        # --- Steg 3: Veckodag ---
        weekday_factor = self._get_weekday_factor(target_date)
        if weekday_factor != Decimal("1.00"):
            weekday_name = ["Mån", "Tis", "Ons", "Tor", "Fre", "Lör", "Sön"][target_date.weekday()]
            price = price * weekday_factor
            steps.append(PriceStep(
                label=f"Veckodag: {weekday_name}",
                factor=weekday_factor,
                price_after=_round(price),
            ))

        # --- Steg 4 & 5: Helg, röda dagar, lov ---
        for cal_event in self._get_calendar_events(target_date):
            price = price * cal_event.multiplier
            steps.append(PriceStep(
                label=f"Kalenderhändelse: {cal_event.name}",
                factor=cal_event.multiplier,
                price_after=_round(price),
            ))

        # --- Steg 6: Lokala evenemang ---
        for event in self._get_local_events(target_date):
            price = price * event.multiplier
            steps.append(PriceStep(
                label=f"Evenemang: {event.name}",
                factor=event.multiplier,
                price_after=_round(price),
            ))

        # --- Steg 7: Vistelselängd ---
        if nights is not None:
            los_factor = self._get_length_of_stay_factor(nights)
            if los_factor != Decimal("1.00"):
                price = price * los_factor
                steps.append(PriceStep(
                    label=f"Vistelselängd: {nights} nätter",
                    factor=los_factor,
                    price_after=_round(price),
                ))

        # --- Steg 8: Efterfrågejustering (AI / externa signaler) ---
        # Detta är den öppna platsen för framtida integrationer.
        # AI-lagret skickar in en demand_adjustment-multiplikator,
        # men om den saknas kör motorn oförändrat — alltid deterministisk utan AI.
        if demand_adjustment is not None and demand_adjustment != Decimal("1.00"):
            price = price * demand_adjustment
            steps.append(PriceStep(
                label=f"Efterfrågejustering (AI/extern)",
                factor=demand_adjustment,
                price_after=_round(price),
            ))

        # --- Steg 9: Last-minute rabatt ---
        lm_factor, days_until = calculate_last_minute_factor(self.property, target_date)
        if lm_factor < Decimal("1.0"):
            price = _round(price * lm_factor)
            desc = get_last_minute_description(days_until, lm_factor)
            steps.append(PriceStep(
                label=desc,
                factor=lm_factor,
                price_after=price,
            ))
            # Skyddsracke: aldrig under minimum lonsamt pris
            nights_val = nights or 1
            price_after_floor, was_floored = apply_last_minute_floor(price, self.property, nights_val)
            if was_floored:
                steps.append(PriceStep(
                    label="Klampat mot minimum lonsamt pris",
                    factor=Decimal("1.00"),
                    price_after=price_after_floor,
                ))
                price = price_after_floor

        # --- Steg 10: Klampning mot golv/tak ---
        price = _round(price)
        is_clamped_floor = False
        is_clamped_ceiling = False

        if self.property.price_floor is not None and price < self.property.price_floor:
            price = self.property.price_floor
            is_clamped_floor = True
            steps.append(PriceStep(
                label=f"Klampat mot prisgolv",
                factor=Decimal("1.00"),
                price_after=price,
            ))

        if self.property.price_ceiling is not None and price > self.property.price_ceiling:
            price = self.property.price_ceiling
            is_clamped_ceiling = True
            steps.append(PriceStep(
                label=f"Klampat mot pristak",
                factor=Decimal("1.00"),
                price_after=price,
            ))

        # --- Sista steget: Avrundning till jamna tiotal ---
        rounding_rule = getattr(self.property, 'rounding_rule', 'nearest_10') or 'nearest_10'
        rounded_price, was_rounded = apply_rounding(price, rounding_rule)
        if was_rounded:
            steps.append(PriceStep(
                label=f"Avrundning (nearest 10)",
                factor=Decimal("1.00"),
                price_after=rounded_price,
            ))
            price = rounded_price

        # Bygg läsbar förklaring
        explanation = _build_explanation(steps)

        return PriceResult(
            property_id=self.property.id,
            date=target_date,
            recommended_price=price,
            explanation=explanation,
            steps=steps,
            is_clamped_floor=is_clamped_floor,
            is_clamped_ceiling=is_clamped_ceiling,
        )

    def calculate_range(
        self,
        start_date: date,
        end_date: date,
        nights: Optional[int] = None,
        demand_adjustment: Optional[Decimal] = None,
    ) -> list[PriceResult]:
        """
        Räknar ut priset för alla dagar i ett datumintervall.
        Returnerar en lista med PriceResult, ett per dag.
        """
        results = []
        current = start_date
        while current <= end_date:
            results.append(self.calculate(current, nights=nights, demand_adjustment=demand_adjustment))
            current += timedelta(days=1)
        return results

    # ─── Hjälpmetoder ───────────────────────────────────────────────────────

    def _get_category_factor(self, d: date) -> Decimal:
        """Returnerar kategorins manadsmultiplikator for det givna datumet."""
        if not self.category_multipliers:
            return Decimal("1.00")
        return self.category_multipliers.get(d.month, Decimal("1.00"))

    def _get_season_factor(self, d: date) -> Decimal:
        """Returnerar multiplikatorn för den säsong som matchar datumet (högst prioritet vinner)."""
        matching = [s for s in self.seasons if s.start_date <= d <= s.end_date]
        if not matching:
            return Decimal("1.00")
        best = max(matching, key=lambda s: s.priority)
        return best.multiplier

    def _get_season_name(self, d: date) -> str:
        matching = [s for s in self.seasons if s.start_date <= d <= s.end_date]
        if not matching:
            return "Ingen säsong"
        best = max(matching, key=lambda s: s.priority)
        return best.name

    def _get_weekday_factor(self, d: date) -> Decimal:
        """Kollar objektspecifika veckodagsregler först, annars standardvärden."""
        weekday_rules = [
            r for r in self.property.price_rules
            if r.rule_type == "weekday_adjustment" and r.is_active
        ]
        for rule in weekday_rules:
            params = json.loads(rule.parameters)
            if d.weekday() in params.get("days", []):
                return Decimal(str(params["multiplier"]))
        return DEFAULT_WEEKDAY_MULTIPLIERS.get(d.weekday(), Decimal("1.00"))

    def _get_calendar_events(self, d: date) -> list[CalendarEvent]:
        """Returnerar alla kalenderhändelser som täcker datumet, sorterade på prioritet."""
        matching = [e for e in self.calendar_events if e.start_date <= d <= e.end_date]
        return sorted(matching, key=lambda e: e.priority)

    def _get_local_events(self, d: date) -> list[LocalEvent]:
        """Returnerar lokala evenemang som täcker datumet."""
        return [e for e in self.local_events if e.start_date <= d <= e.end_date]

    def _get_length_of_stay_factor(self, nights: int) -> Decimal:
        """Returnerar rabatt/påslag baserat på vistelselängd."""
        los_rules = [
            r for r in self.property.price_rules
            if r.rule_type == "length_of_stay" and r.is_active
        ]
        # Hitta den regel som matchar (min_nights <= nights <= max_nights)
        best_factor = Decimal("1.00")
        for rule in sorted(los_rules, key=lambda r: r.priority, reverse=True):
            params = json.loads(rule.parameters)
            min_n = params.get("min_nights", 0)
            max_n = params.get("max_nights", 9999)
            if min_n <= nights <= max_n:
                best_factor = Decimal(str(params["multiplier"]))
                break
        return best_factor


# ─── Hjälpfunktioner ────────────────────────────────────────────────────────

def _round(price: Decimal) -> Decimal:
    """Avrundar till närmaste hela krona."""
    return price.quantize(Decimal("1"), rounding=ROUND_HALF_UP)


def _build_explanation(steps: list[PriceStep]) -> str:
    """
    Bygger en läsbar prisförklaring från stegenlistan.

    Exempel:
      Baspris 4 000 kr → Säsong: Högsäsong sommar ×1.30 → 5 200 kr
      → Evenemang: The Weeknd ×1.60 → 8 320 kr
      → Klampat mot pristak → 7 000 kr
      Slutpris: 7 000 kr
    """
    if not steps:
        return "Inget pris beräknat."

    parts = []
    for i, step in enumerate(steps):
        if i == 0:
            parts.append(f"Baspris {_fmt(step.price_after)} kr")
        else:
            parts.append(f"→ {step.label} ×{step.factor} → {_fmt(step.price_after)} kr")

    final_price = steps[-1].price_after
    explanation = "\n".join(parts)
    explanation += f"\nSlutpris: {_fmt(final_price)} kr"
    return explanation


def _fmt(price: Decimal) -> str:
    """Formaterar pris med tusentalsavgränsare: 10000 → '10 000'."""
    return f"{int(price):,}".replace(",", " ")
