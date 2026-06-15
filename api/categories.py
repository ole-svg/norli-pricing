"""
Endpoints for prissattningskategorier.
"""

from decimal import Decimal
from typing import Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db.session import get_db
from db.models import PricingCategory, PricingCategoryMultiplier

router = APIRouter()


class MultiplierResponse(BaseModel):
    month: int
    multiplier: Decimal

    class Config:
        from_attributes = True


class CategoryResponse(BaseModel):
    id: int
    code: str
    name: str
    description: Optional[str]
    is_active: bool
    sort_order: int
    monthly_multipliers: list[MultiplierResponse]

    class Config:
        from_attributes = True


@router.get("/", response_model=list[CategoryResponse])
def list_categories(include_inactive: bool = False, db: Session = Depends(get_db)):
    """Listar alla prissattningskategorier."""
    q = db.query(PricingCategory)
    if not include_inactive:
        q = q.filter(PricingCategory.is_active == True)
    return q.order_by(PricingCategory.sort_order).all()


@router.get("/{code}", response_model=CategoryResponse)
def get_category(code: str, db: Session = Depends(get_db)):
    """Hamtar en specifik kategori med alla manadsmultiplikatorer."""
    cat = db.query(PricingCategory).filter(PricingCategory.code == code).first()
    if not cat:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Kategori '{code}' hittades inte.")
    return cat
