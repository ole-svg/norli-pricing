"""
Endpoints for publicering till plattformar.
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db.session import get_db
from adapters.publisher import Publisher

router = APIRouter()


@router.post("/enable-push/{crm_property_id}")
def enable_push(crm_property_id: str, db=None):
    """Aktiverar push_enabled i PriceLabs för ett objekt."""
    from adapters.pricelabs import PricelabsAdapter
    adapter = PricelabsAdapter()
    listing_id = adapter.get_listing_id(crm_property_id)
    if not listing_id:
        return {"success": False, "error": f"Inget listing-ID hittat för {crm_property_id}"}
    ok = adapter.enable_push(listing_id)
    return {
        "success": ok,
        "property_id": crm_property_id,
        "listing_id": listing_id,
        "message": "push_enabled aktiverat" if ok else "Kunde inte aktivera push_enabled",
    }


class PublishResult(BaseModel):
    success: bool
    property_id: str
    dates_updated: int
    errors: list[str]
    message: str


@router.post("/{crm_property_id}", response_model=PublishResult)
def publish_property(
    crm_property_id: str,
    days_ahead: int = 365,
    db: Session = Depends(get_db),
):
    """
    Publicerar priser for ett objekt till Airbnb.

    Om Airbnb-credentials saknas kors i simuleringsläge
    och loggar vad som skulle publicerats.
    """
    publisher = Publisher(db)
    result = publisher.publish_property(crm_property_id, days_ahead)
    return PublishResult(
        success=result.success,
        property_id=result.property_id,
        dates_updated=result.dates_updated,
        errors=result.errors,
        message=result.message,
    )


@router.post("/", response_model=list[PublishResult])
def publish_all(days_ahead: int = 365, db: Session = Depends(get_db)):
    """Publicerar alla aktiva objekt till Airbnb."""
    publisher = Publisher(db)
    results = publisher.publish_all(days_ahead)
    return [
        PublishResult(
            success=r.success,
            property_id=r.property_id,
            dates_updated=r.dates_updated,
            errors=r.errors,
            message=r.message,
        )
        for r in results
    ]
