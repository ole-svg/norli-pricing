"""
Ekonomikalkylator - raknar prognos for en bokning.

Prismotorn raknar PROGNOS. CRM raknar verklig avrakning.
Samma regler, olika data.

Kostnadsordning:
  Bruttohyra
  - Plattformsavgift (t.ex. Airbnb 3%)
  - Logimoms (12/112 av brutto)
  = Avrakningsgrund

  x Agarandel = Agarandel fore kostnader
  x Norliandel = Norlis andel

  - Stad
  - Objektkostnader (forbrukningsmaterial etc)
  - Investeringskvittning (uppstartskostnader)
  = Utbetalning till agare
"""

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from db.models import Property


@dataclass
class CleaningEstimate:
    hours: Decimal
    gross_cost: Decimal
    rut_deduction: Decimal
    net_cost_for_owner: Decimal
    invoice_recipient: str
    rut_applicable: bool


@dataclass
class InvestmentRecoupment:
    balance_before: Decimal       # Saldo innan denna period
    recoupment_amount: Decimal    # Kvittas denna period
    balance_after: Decimal        # Aterstaende saldo


@dataclass
class BookingEconomyForecast:
    # Input
    gross_price: Decimal
    nights: int
    guests: int

    # Avdrag fran brutto
    platform_fee: Decimal
    vat_amount: Decimal
    settlement_base: Decimal

    # Fordelning
    owner_share_gross: Decimal
    norli_share: Decimal

    # Kostnader
    cleaning: CleaningEstimate
    object_costs: Decimal
    investment: InvestmentRecoupment

    # Slutresultat
    owner_net: Decimal

    # Forklaring
    explanation: str


class EconomyCalculator:
    """
    Raknar ekonomisk prognos for en bokning givet ett pris.

    Anvands av prismotorn for att visa forvantat agarnetTo
    och optimera mot agarens mal.
    """

    def __init__(self, prop: Property):
        self.prop = prop

    def calculate(
        self,
        gross_price: Decimal,
        nights: int,
        guests: int,
        manual_recoupment: Optional[Decimal] = None,
    ) -> BookingEconomyForecast:
        p = self.prop

        # Steg 1: Plattformsavgift
        platform_fee = _round(gross_price * p.platform_fee_rate)

        # Steg 2: Logimoms (baklangesmoms ur bruttopris)
        # Formel: brutto x vat_rate / (1 + vat_rate)
        vat_amount = _round(gross_price * p.vat_rate / (1 + p.vat_rate))

        # Steg 3: Avrakningsgrund
        settlement_base = _round(gross_price - platform_fee - vat_amount)

        # Steg 4: Fordelning
        owner_share_gross = _round(settlement_base * p.owner_share_pct)
        norli_share = _round(settlement_base * p.norli_share_pct)

        # Steg 5: Stad
        cleaning = self._calculate_cleaning(nights, guests)

        # Steg 6: Objektkostnader
        object_costs = p.object_costs_per_booking or Decimal("0")

        # Steg 7: Investeringskvittning
        cleaning_deduction = Decimal("0")
        if p.cleaning_invoice_recipient in ("owner_private", "owner_company"):
            cleaning_deduction = cleaning.net_cost_for_owner

        owner_before_investment = _round(owner_share_gross - cleaning_deduction - object_costs)
        investment = self._calculate_recoupment(owner_before_investment, manual_recoupment)

        # Steg 8: Agarens netto
        owner_net = _round(owner_before_investment - investment.recoupment_amount)

        explanation = self._build_explanation(
            gross_price, platform_fee, vat_amount, settlement_base,
            owner_share_gross, norli_share, cleaning, object_costs,
            investment, owner_net
        )

        return BookingEconomyForecast(
            gross_price=gross_price,
            nights=nights,
            guests=guests,
            platform_fee=platform_fee,
            vat_amount=vat_amount,
            settlement_base=settlement_base,
            owner_share_gross=owner_share_gross,
            norli_share=norli_share,
            cleaning=cleaning,
            object_costs=object_costs,
            investment=investment,
            owner_net=owner_net,
            explanation=explanation,
        )

    def _calculate_cleaning(self, nights: int, guests: int) -> CleaningEstimate:
        p = self.prop

        # Natttrappa: smooth kurva baserad pa 1n=3h, 5n=5h, 8n=7h
        NIGHT_TABLE = {1:Decimal("3.0"), 2:Decimal("3.5"), 3:Decimal("4.0"),
                       4:Decimal("4.5"), 5:Decimal("5.0"), 6:Decimal("5.5"),
                       7:Decimal("6.0"), 8:Decimal("7.0")}
        base_hours = NIGHT_TABLE.get(min(nights, 8), Decimal("7.0"))

        # Gastjustering i 2-personers intervall
        base_guests = int(p.cleaning_base_guests or 8)
        diff = guests - base_guests
        if diff > 0:
            # Fler gaster an bas: +0.5h per 2 extra gaster
            above_rate = p.cleaning_hours_per_2_guests_above or Decimal("0.5")
            adjustment = Decimal(str(diff)) / 2 * above_rate
        else:
            # Farre gaster an bas: -0.25h per 2 gaster under bas
            below_rate = p.cleaning_hours_per_2_guests_below or Decimal("0.25")
            adjustment = Decimal(str(diff)) / 2 * below_rate  # negativ

        hours = base_hours + adjustment

        # Golv: aldrig under minimum (default 3h)
        min_hours = p.cleaning_min_hours or Decimal("3.0")
        hours = max(hours, min_hours)

        # Tak: aldrig over max_hours
        hours = min(hours, p.cleaning_max_hours or Decimal("8.0"))

        # Avrunda till narmaste halvtimme
        hours = _round_hours(hours)

        gross_cost = _round(hours * p.cleaning_hourly_rate)

        # RUT for privatperson (50% avdrag)
        rut_deduction = Decimal("0")
        if p.cleaning_rut_applicable and p.cleaning_invoice_recipient == "owner_private":
            rut_deduction = _round(gross_cost * Decimal("0.50"))

        # Bolag: avdrag for ingaende moms (kostnaden ar ex moms)
        vat_deduction = Decimal("0")
        if p.owner_type in ("company_vat_registered",):
            # Bruttokostnaden inkl moms delas pa 1.25 for att fa ex moms
            vat_deduction = _round(gross_cost - gross_cost / Decimal("1.25"))

        net_cost = _round(gross_cost - rut_deduction - vat_deduction)

        return CleaningEstimate(
            hours=hours,
            gross_cost=gross_cost,
            rut_deduction=rut_deduction + vat_deduction,
            net_cost_for_owner=net_cost,
            invoice_recipient=p.cleaning_invoice_recipient,
            rut_applicable=p.cleaning_rut_applicable,
        )

    def _calculate_recoupment(
        self,
        owner_amount: Decimal,
        manual_override: Optional[Decimal],
    ) -> InvestmentRecoupment:
        p = self.prop
        balance = p.investment_balance

        if balance <= 0:
            return InvestmentRecoupment(
                balance_before=Decimal("0"),
                recoupment_amount=Decimal("0"),
                balance_after=Decimal("0"),
            )

        if p.investment_recoupment_mode == "manual":
            recoupment = manual_override or Decimal("0")

        elif p.investment_recoupment_mode == "auto_with_cap":
            recoupment = balance  # Starta med hela saldot
            if p.investment_recoupment_cap is not None:
                recoupment = min(recoupment, p.investment_recoupment_cap)
            if p.investment_recoupment_cap_pct is not None:
                cap_from_pct = _round(owner_amount * p.investment_recoupment_cap_pct)
                recoupment = min(recoupment, cap_from_pct)

        else:  # auto_full
            recoupment = balance

        # Kan aldrig kvitta mer an hela saldot
        recoupment = min(recoupment, balance)
        # Kan aldrig kvitta mer an agaren far ut (ingen negativ utbetalning)
        recoupment = min(recoupment, owner_amount)
        recoupment = _round(recoupment)

        return InvestmentRecoupment(
            balance_before=balance,
            recoupment_amount=recoupment,
            balance_after=_round(balance - recoupment),
        )

    def _build_explanation(
        self,
        gross_price, platform_fee, vat_amount, settlement_base,
        owner_share_gross, norli_share, cleaning, object_costs,
        investment, owner_net
    ) -> str:
        p = self.prop
        lines = [
            f"Bruttohyra                    {_fmt(gross_price)} kr",
            f"",
            f"- Airbnb avgift ({int(p.platform_fee_rate * 100)}%)          -{_fmt(platform_fee)} kr",
            f"- Logimoms ({int(p.vat_rate * 100)}/{int(p.vat_rate * 100) + 100})              -{_fmt(vat_amount)} kr",
            f"",
            f"= Avrakningsgrund             {_fmt(settlement_base)} kr",
            f"",
            f"Agarandel ({int(p.owner_share_pct * 100)}%)           {_fmt(owner_share_gross)} kr",
            f"Norliandel ({int(p.norli_share_pct * 100)}%)          {_fmt(norli_share)} kr",
            f"",
            f"Agarandel                     {_fmt(owner_share_gross)} kr",
            f"",
            f"- Stad ({cleaning.hours}h x {_fmt(p.cleaning_hourly_rate)} kr)    -{_fmt(cleaning.net_cost_for_owner)} kr",
        ]
        if cleaning.rut_applicable:
            lines.append(f"  (inkl RUT-avdrag -{_fmt(cleaning.rut_deduction)} kr)")
        if object_costs:
            lines.append(f"- Objektkostnader            -{_fmt(object_costs)} kr")
        if investment.recoupment_amount > 0:
            lines += [
                f"- Investeringskvittning      -{_fmt(investment.recoupment_amount)} kr",
                f"  (saldo fore: {_fmt(investment.balance_before)} kr, efter: {_fmt(investment.balance_after)} kr)",
            ]
        lines += [
            f"",
            f"= Utbetalning till agare      {_fmt(owner_net)} kr",
        ]
        return "\n".join(lines)


def _round(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _round_hours(hours: Decimal) -> Decimal:
    return (hours * 2).quantize(Decimal("1"), rounding=ROUND_HALF_UP) / 2


def _fmt(value: Decimal) -> str:
    return f"{float(value):,.0f}".replace(",", " ")
