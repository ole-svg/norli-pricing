"""
Endpoints for att trigga schemalagda jobb manuellt.
"""

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.orm import Session
from db.session import get_db
from api import ical_sync as ical
from pydantic import BaseModel
from datetime import datetime

router = APIRouter()


class JobResult(BaseModel):
    job: str
    triggered_at: str
    message: str


@router.post("/nightly", response_model=JobResult)
def trigger_nightly_job(background_tasks: BackgroundTasks):
    """
    Triggar nattjobbet manuellt.
    Kors i bakgrunden sa att API:et svarar direkt.
    """
    from scripts.nightly_job import run_nightly_job
    background_tasks.add_task(run_nightly_job)

    return JobResult(
        job="nightly",
        triggered_at=datetime.now().isoformat(),
        message="Nattjobbet ar igangsat i bakgrunden. Kolla Railway-loggarna for status.",
    )

@router.post("/sync-bookings", response_model=JobResult)
async def trigger_booking_sync(db: Session = Depends(get_db)):
    """
    Synkar alla iCal-bokningar manuellt.
    Körs också automatiskt var 15:e minut via nattjobbet.
    """
    from api.ical_sync import ICAL_URLS, sync_property
    results = []
    total_synced = 0
    for crm_id, url in ICAL_URLS.items():
        result = await sync_property(crm_id, url, db)
        results.append(result)
        total_synced += result.get("synced", 0)

    return JobResult(
        job="sync-bookings",
        triggered_at=datetime.now().isoformat(),
        message=f"Synkade {total_synced} bokningar från {len(results)} objekt.",
    )
