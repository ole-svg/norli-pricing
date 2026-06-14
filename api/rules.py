"""
Endpoints för prisregler.

Objektspecifika regler som finjusterar prissättningen:
- Veckodagsjusteringar
- Vistelselängdsrabatter
- Manuella efterfrågejusteringar
"""

import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db.session import get_db
from db.models import Property, PriceRule

router = APIRouter()


class PriceRuleCreate(BaseModel):
    crm_property_id: str
    rule_type: str      # "weekday_adjustment" | "length_of_stay" | "demand_adjustment"
    name: str
    parameters: dict[str, Any]  # Flexibelt JSON-objekt
    priority: int = 0


class PriceRuleResponse(BaseModel):
    id: int
    property_id: int
    rule_type: str
    name: str
    parameters: dict[str, Any]
    is_active: bool
    priority: int

    class Config:
        from_attributes = True

    @classmethod
    def from_orm_custom(cls, rule: PriceRule):
        return cls(
            id=rule.id,
            property_id=rule.property_id,
            rule_type=rule.rule_type,
            name=rule.name,
            parameters=json.loads(rule.parameters),
            is_active=rule.is_active,
            priority=rule.priority,
        )


@router.post("/", response_model=PriceRuleResponse, status_code=201)
def create_rule(data: PriceRuleCreate, db: Session = Depends(get_db)):
    """Skapar en ny prisregel för ett objekt."""
    prop = db.query(Property).filter(Property.crm_property_id == data.crm_property_id).first()
    if not prop:
        raise HTTPException(status_code=404, detail=f"Objekt '{data.crm_property_id}' hittades inte.")

    rule = PriceRule(
        property_id=prop.id,
        rule_type=data.rule_type,
        name=data.name,
        parameters=json.dumps(data.parameters),
        priority=data.priority,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return PriceRuleResponse.from_orm_custom(rule)


@router.get("/{crm_property_id}", response_model=list[PriceRuleResponse])
def list_rules(crm_property_id: str, db: Session = Depends(get_db)):
    """Listar alla prisregler för ett objekt."""
    prop = db.query(Property).filter(Property.crm_property_id == crm_property_id).first()
    if not prop:
        raise HTTPException(status_code=404, detail=f"Objekt '{crm_property_id}' hittades inte.")

    rules = db.query(PriceRule).filter(PriceRule.property_id == prop.id).all()
    return [PriceRuleResponse.from_orm_custom(r) for r in rules]


@router.delete("/{rule_id}", status_code=204)
def delete_rule(rule_id: int, db: Session = Depends(get_db)):
    """Tar bort en prisregel."""
    rule = db.query(PriceRule).filter(PriceRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail=f"Regel {rule_id} hittades inte.")
    db.delete(rule)
    db.commit()
