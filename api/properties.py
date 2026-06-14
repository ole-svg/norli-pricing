"""
Endpoints för objekt (properties).

CRM pushar hit när ett objekt skapas eller uppdateras.
Motorn speglar de attribut den behöver för prissättning.
"""

from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db.session import get_db
from db.models import Property

router = APIRouter()


# ─── Pydantic-scheman (request/response-format) ─────────────────────────────

class PropertyCreate(BaseModel):
    """Data som krävs för att skapa ett nytt objekt."""
    crm_property_id: str
    name: str
    capacity: int
    base_price: Decimal
    pricing_strategy: str = "balanced"

    # Kostnader (valfria i v1, reserverade för ägarnetto-beräkning)
    cleaning_cost: Optional[Decimal] = None
    norli_commission_pct: Optional[Decimal] = None
    other_costs: Optional[Decimal] = None

    # Skyddsräcken
    price_floor: Optional[Decimal] = None
    price_ceiling: Optional[Decimal] = None
    min_margin: Optional[Decimal] = None
    min_owner_net: Optional[Decimal] = None


class PropertyResponse(BaseModel):
    """Vad API:et returnerar för ett objekt."""
    id: int
    crm_property_id: str
    name: str
    capacity: int
    base_price: Decimal
    pricing_strategy: str
    cleaning_cost: Optional[Decimal]
    norli_commission_pct: Optional[Decimal]
    other_costs: Optional[Decimal]
    price_floor: Optional[Decimal]
    price_ceiling: Optional[Decimal]
    min_margin: Optional[Decimal]
    min_owner_net: Optional[Decimal]
    is_active: bool

    class Config:
        from_attributes = True  # Tillåter konvertering från SQLAlchemy-objekt


# ─── Endpoints ───────────────────────────────────────────────────────────────

@router.post("/", response_model=PropertyResponse, status_code=201)
def create_property(data: PropertyCreate, db: Session = Depends(get_db)):
    """
    Skapar ett nytt objekt i prissättningsmotorn.
    Anropas av CRM när ett nytt objekt läggs till.
    """
    # Kontrollera att crm_property_id inte redan finns
    existing = db.query(Property).filter(Property.crm_property_id == data.crm_property_id).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"Objekt med crm_property_id '{data.crm_property_id}' finns redan.")

    prop = Property(**data.model_dump())
    db.add(prop)
    db.commit()
    db.refresh(prop)
    return prop


@router.get("/", response_model=list[PropertyResponse])
def list_properties(db: Session = Depends(get_db)):
    """Listar alla aktiva objekt."""
    return db.query(Property).filter(Property.is_active == True).all()


@router.get("/{crm_property_id}", response_model=PropertyResponse)
def get_property(crm_property_id: str, db: Session = Depends(get_db)):
    """Hämtar ett specifikt objekt med dess CRM-id."""
    prop = db.query(Property).filter(Property.crm_property_id == crm_property_id).first()
    if not prop:
        raise HTTPException(status_code=404, detail=f"Objekt '{crm_property_id}' hittades inte.")
    return prop


@router.patch("/{crm_property_id}", response_model=PropertyResponse)
def update_property(crm_property_id: str, data: PropertyCreate, db: Session = Depends(get_db)):
    """
    Uppdaterar ett objekts prisattribut.
    Anropas av CRM när objekt-data ändras.
    """
    prop = db.query(Property).filter(Property.crm_property_id == crm_property_id).first()
    if not prop:
        raise HTTPException(status_code=404, detail=f"Objekt '{crm_property_id}' hittades inte.")

    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(prop, key, value)

    db.commit()
    db.refresh(prop)
    return prop
