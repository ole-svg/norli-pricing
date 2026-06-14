"""
Endpoint for ekonomisk prognos.
"""

from decimal import Decimal
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db.session import get_db
from db.models import Property
from engine.economy import EconomyCalculator

router = APIRouter()


class CleaningResponse(BaseModel):
    hours: Decimal
    gross_cost: Decimal
    rut_deduction: Decimal
    net_cost_for_owner: Decimal
    invoice_recipient: str
    rut_applicable: bool


class InvestmentResponse(BaseModel):
    balance_before: Decimal
    recoupment_amount: Decimal
    balance_after: Decimal


class EconomyForecastResponse(BaseModel):
    gross_price: Decimal
    nights: int
    guests: int
    platform_fee: Decimal
    vat_amount: Decimal
    settlement_base: Decimal
    owner_share_gross: Decimal
    norli_share: Decimal
    cleaning: CleaningResponse
    object_costs: Decimal
    investment: InvestmentResponse
    owner_net: Decimal
    explanation: str


@router.get("/{crm_property_id}/forecast", response_model=EconomyForecastResponse)
def get_economy_forecast(
    crm_property_id: str,
    gross_price: Decimal = Query(...),
    nights: int = Query(..., ge=1),
    guests: int = Query(..., ge=1),
    manual_recoupment: Optional[Decimal] = Query(default=None),
    db: Session = Depends(get_db),
):
    """
    Ekonomisk prognos for en bokning.

    Visar hur intakten fordelas: plattformsavgift, moms,
    Norli-andel, stad, objektkostnader, investeringskvittning
    och agarens utbetalning.

    Exempel:
    GET /economy/enskede-79/forecast?gross_price=10000&nights=3&guests=4
    """
    prop = db.query(Property).filter(Property.crm_property_id == crm_property_id).first()
    if not prop:
        raise HTTPException(status_code=404, detail=f"Objekt '{crm_property_id}' hittades inte.")

    calc = EconomyCalculator(prop)
    f = calc.calculate(
        gross_price=gross_price,
        nights=nights,
        guests=guests,
        manual_recoupment=manual_recoupment,
    )

    return EconomyForecastResponse(
        gross_price=f.gross_price,
        nights=f.nights,
        guests=f.guests,
        platform_fee=f.platform_fee,
        vat_amount=f.vat_amount,
        settlement_base=f.settlement_base,
        owner_share_gross=f.owner_share_gross,
        norli_share=f.norli_share,
        cleaning=CleaningResponse(
            hours=f.cleaning.hours,
            gross_cost=f.cleaning.gross_cost,
            rut_deduction=f.cleaning.rut_deduction,
            net_cost_for_owner=f.cleaning.net_cost_for_owner,
            invoice_recipient=f.cleaning.invoice_recipient,
            rut_applicable=f.cleaning.rut_applicable,
        ),
        object_costs=f.object_costs,
        investment=InvestmentResponse(
            balance_before=f.investment.balance_before,
            recoupment_amount=f.investment.recoupment_amount,
            balance_after=f.investment.balance_after,
        ),
        owner_net=f.owner_net,
        explanation=f.explanation,
    )
