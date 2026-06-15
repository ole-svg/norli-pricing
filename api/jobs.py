"""
Endpoints for att trigga schemalagda jobb manuellt.
"""

from fastapi import APIRouter, BackgroundTasks
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
