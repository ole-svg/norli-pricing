"""
Tester för den deterministiska regelmotorn.

Kör med: pytest tests/test_engine.py -v
"""

import pytest
from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock

from engine.pricing import PricingEngine, PriceResult
from db.models import Property, Season, CalendarEvent, LocalEvent, PriceRule


def make_property(**kwargs) -> Property:
    """Skapar ett testojekt med standardvärden."""
    defaults = dict(
        id=1,
        crm_property_id="test-001",
        name="Testobjekt",
        capacity=4,
        base_price=Decimal("2500"),
        pricing_strategy="balanced",
        price_floor=Decimal("1000"),
        price_ceiling=Decimal("7000"),
        price_rules=[],
    )
    defaults.update(kwargs)
    prop = MagicMock(spec=Property)
    for k, v in defaults.items():
        setattr(prop, k, v)
    return prop


class TestBasicCalculation:
    def test_grundpris_utan_regler(self):
        """Utan säsonger eller event ska baspriset gälla (justerat för veckodag)."""
        prop = make_property(base_price=Decimal("2500"), price_floor=None, price_ceiling=None)
        engine = PricingEngine(prop, seasons=[], calendar_events=[], local_events=[])

        # Måndag (faktor 1.00)
        monday = date(2026, 6, 15)  # måndag
        result = engine.calculate(monday)
        assert result.recommended_price == Decimal("2500")

    def test_prisforklaring_finns(self):
        """Prisförklaringen ska alltid finnas och inte vara tom."""
        prop = make_property()
        engine = PricingEngine(prop, seasons=[], calendar_events=[], local_events=[])
        result = engine.calculate(date(2026, 6, 15))
        assert result.explanation
        assert "Slutpris" in result.explanation

    def test_fredag_har_hogre_pris(self):
        """Fredagar ska ha högre pris än måndagar."""
        prop = make_property(price_floor=None, price_ceiling=None)
        engine = PricingEngine(prop, seasons=[], calendar_events=[], local_events=[])

        monday = date(2026, 6, 15)   # måndag
        friday = date(2026, 6, 19)   # fredag

        result_mon = engine.calculate(monday)
        result_fri = engine.calculate(friday)

        assert result_fri.recommended_price > result_mon.recommended_price


class TestSeasons:
    def test_hogsasong_okar_priset(self):
        """Högsäsong ska öka priset med rätt multiplikator."""
        prop = make_property(base_price=Decimal("2000"), price_floor=None, price_ceiling=None)
        season = MagicMock(spec=Season)
        season.name = "Högsäsong"
        season.start_date = date(2026, 6, 1)
        season.end_date = date(2026, 8, 31)
        season.multiplier = Decimal("1.40")
        season.priority = 10

        engine = PricingEngine(prop, seasons=[season], calendar_events=[], local_events=[])

        # Måndag i högsäsong
        monday = date(2026, 6, 15)
        result = engine.calculate(monday)

        # 2000 * 1.40 = 2800
        assert result.recommended_price == Decimal("2800")

    def test_datum_utanfor_sasong_paverkas_inte(self):
        """Datum utanför säsongen ska inte påverkas."""
        prop = make_property(base_price=Decimal("2000"), price_floor=None, price_ceiling=None)
        season = MagicMock(spec=Season)
        season.name = "Högsäsong"
        season.start_date = date(2026, 6, 15)
        season.end_date = date(2026, 8, 15)
        season.multiplier = Decimal("1.40")
        season.priority = 10

        engine = PricingEngine(prop, seasons=[season], calendar_events=[], local_events=[])

        # Måndag i januari — utanför säsongen
        result = engine.calculate(date(2026, 1, 5))
        assert result.recommended_price == Decimal("2000")


class TestGuards:
    def test_prisgolv_klampar_for_laga_priser(self):
        """Priset ska aldrig gå under prisgolvet."""
        prop = make_property(
            base_price=Decimal("500"),   # Lågt baspris
            price_floor=Decimal("1000"), # Men golvet är 1000
            price_ceiling=None,
        )
        engine = PricingEngine(prop, seasons=[], calendar_events=[], local_events=[])
        result = engine.calculate(date(2026, 1, 5))

        assert result.recommended_price == Decimal("1000")
        assert result.is_clamped_floor is True

    def test_pristak_klampar_for_hoga_priser(self):
        """Priset ska aldrig gå över pristaket."""
        prop = make_property(
            base_price=Decimal("10000"),  # Högt baspris
            price_floor=None,
            price_ceiling=Decimal("7000"),  # Taket är 7000
        )
        engine = PricingEngine(prop, seasons=[], calendar_events=[], local_events=[])
        result = engine.calculate(date(2026, 6, 15))

        assert result.recommended_price == Decimal("7000")
        assert result.is_clamped_ceiling is True

    def test_klampning_noteras_i_forklaring(self):
        """Klampning ska synas i prisförklaringen."""
        prop = make_property(base_price=Decimal("500"), price_floor=Decimal("1500"), price_ceiling=None)
        engine = PricingEngine(prop, seasons=[], calendar_events=[], local_events=[])
        result = engine.calculate(date(2026, 1, 5))

        assert "prisgolv" in result.explanation.lower()


class TestDemandAdjustment:
    def test_ai_justering_appliceras(self):
        """AI-lagrets efterfrågejustering ska multiplicera priset."""
        prop = make_property(base_price=Decimal("2000"), price_floor=None, price_ceiling=None)
        engine = PricingEngine(prop, seasons=[], calendar_events=[], local_events=[])

        # Måndag utan AI
        result_without_ai = engine.calculate(date(2026, 1, 5))

        # Samma dag med AI-justering +20%
        result_with_ai = engine.calculate(date(2026, 1, 5), demand_adjustment=Decimal("1.20"))

        assert result_with_ai.recommended_price > result_without_ai.recommended_price

    def test_ingen_ai_ger_samma_resultat(self):
        """Utan AI-justering ska resultatet vara identiskt med demand_adjustment=1.0."""
        prop = make_property(base_price=Decimal("2000"), price_floor=None, price_ceiling=None)
        engine = PricingEngine(prop, seasons=[], calendar_events=[], local_events=[])

        d = date(2026, 1, 5)
        r1 = engine.calculate(d)
        r2 = engine.calculate(d, demand_adjustment=Decimal("1.00"))

        assert r1.recommended_price == r2.recommended_price


class TestDeterminism:
    def test_samma_input_ger_samma_output(self):
        """Regelmotorn är deterministisk — samma input ger alltid samma output."""
        prop = make_property()
        engine = PricingEngine(prop, seasons=[], calendar_events=[], local_events=[])

        d = date(2026, 7, 15)
        results = [engine.calculate(d) for _ in range(5)]
        prices = [r.recommended_price for r in results]

        assert len(set(prices)) == 1, "Alla priser ska vara identiska"
