"""
api/cleaning_state.py
Persistens för städportalen: städuppdragens tillstånd.

Städjobben härleds deterministiskt i frontend från bokningar och ägarperioder.
Denna router lagrar det som inte kan härledas (bekräftelse, tilldelning, planerat
slot, gästklar-status, flaggor, estimat, ändringsbegäran) och en audit-logg.

Nyckeln är job_key, en stabil sträng som frontend bygger.
"""

import json
from datetime import date, datetime, timezone
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from db.session import get_db
from db.models import CleaningJobState, CleaningAuditLog, Property

# ── Mejlsändare (Resend, env-gatad) ─────────────────────────────────────────

import os
import urllib.request as _urllib_req

def _send_event_email(subject: str, html: str) -> None:
    """Skickar notifieringsmejl via Resend. No-opar om RESEND_API_KEY saknas."""
    api_key = os.environ.get("RESEND_API_KEY", "")
    if not api_key:
        return
    try:
        body = json.dumps({
            "from": "Norli System <notiser@norli.se>",
            "to": ["ole@horn.se"],  # TODO vid go-live: byt till rätt mottagare per notistyp
            "subject": subject,
            "html": html,
        }).encode()
        req = _urllib_req.Request(
            "https://api.resend.com/emails",
            data=body,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        with _urllib_req.urlopen(req, timeout=5) as r:
            r.read()
    except Exception as e:
        print(f"⚠ Resend-fel (icke-kritiskt): {e}")


router = APIRouter()


# ── Serialisering ────────────────────────────────────────────────────────────

def _flags_to_list(raw: Optional[str]) -> List[str]:
    if not raw:
        return []
    try:
        val = json.loads(raw)
        return val if isinstance(val, list) else []
    except Exception:
        return []


def _state_dict(s: CleaningJobState) -> dict:
    return {
        "job_key": s.job_key,
        "crm_property_id": s.crm_property_id,
        "property_id": s.property_id,
        "job_type": s.job_type,
        "incoming_ical_uid": s.incoming_ical_uid,
        "outgoing_ical_uid": s.outgoing_ical_uid,
        "window_start": s.window_start.isoformat() if s.window_start else None,
        "window_end": s.window_end.isoformat() if s.window_end else None,
        "status": s.status,
        "assigned_company": s.assigned_company,
        "assigned_to": s.assigned_to,
        "confirmed_date": str(s.confirmed_date) if s.confirmed_date else None,
        "confirmed_start": s.confirmed_start,
        "confirmed_end": s.confirmed_end,
        "latest_ready": s.latest_ready.isoformat() if s.latest_ready else None,
        "readiness_status": s.readiness_status,
        "flags": _flags_to_list(s.flags),
        "estimated_hours": float(s.estimated_hours) if s.estimated_hours is not None else None,
        "estimated_hours_source": s.estimated_hours_source,
        "estimated_hours_overridden_by": s.estimated_hours_overridden_by,
        "estimated_hours_overridden_at": s.estimated_hours_overridden_at.isoformat() if s.estimated_hours_overridden_at else None,
        "estimated_hours_original": float(s.estimated_hours_original) if s.estimated_hours_original is not None else None,
        "actual_minutes": s.actual_minutes,
        "bedding_mode": s.bedding_mode,
        "bedding_for_guests": s.bedding_for_guests,
        "outgoing_guests": s.outgoing_guests,
        "notes": s.notes,
        "change_status": s.change_status,
        "change_requested_date": str(s.change_requested_date) if s.change_requested_date else None,
        "change_requested_start": s.change_requested_start,
        "change_requested_assignee": s.change_requested_assignee,
        "change_is_urgent": s.change_is_urgent,
        "change_note": s.change_note,
        "started_at": s.started_at.isoformat() if s.started_at else None,
        "completed_at": s.completed_at.isoformat() if s.completed_at else None,
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "updated_at": s.updated_at.isoformat() if s.updated_at else None,
    }


def _audit_dict(a: CleaningAuditLog) -> dict:
    detail = None
    if a.detail:
        try:
            detail = json.loads(a.detail)
        except Exception:
            detail = a.detail
    return {
        "id": a.id,
        "job_key": a.job_key,
        "event": a.event,
        "actor": a.actor,
        "actor_role": a.actor_role,
        "detail": detail,
        "created_at": a.created_at.isoformat() if a.created_at else None,
    }


def _log(db: Session, job_key: str, event: str, actor: Optional[str] = None,
         actor_role: Optional[str] = None, detail: Optional[dict] = None) -> None:
    """Lägg till en audit-post. Anroparen ansvarar för commit."""
    db.add(CleaningAuditLog(
        job_key=job_key,
        event=event,
        actor=actor,
        actor_role=actor_role,
        detail=json.dumps(detail, ensure_ascii=False) if detail is not None else None,
    ))


def _get_or_404(db: Session, job_key: str) -> CleaningJobState:
    s = db.query(CleaningJobState).filter(CleaningJobState.job_key == job_key).first()
    if not s:
        raise HTTPException(404, f"Städuppdrag {job_key} finns ej")
    return s


def _resolve_property_id(db: Session, crm_property_id: Optional[str]) -> Optional[int]:
    if not crm_property_id:
        return None
    prop = db.query(Property).filter(Property.crm_property_id == crm_property_id).first()
    return prop.id if prop else None


# ── Scheman ──────────────────────────────────────────────────────────────────

class CleaningStateUpsert(BaseModel):
    # Kontext (crm_property_id eller property_id krävs vid skapande)
    crm_property_id: Optional[str] = None
    property_id: Optional[int] = None
    job_type: Optional[str] = None
    incoming_ical_uid: Optional[str] = None
    outgoing_ical_uid: Optional[str] = None
    window_start: Optional[datetime] = None
    window_end: Optional[datetime] = None
    # Tillstånd
    status: Optional[str] = None
    assigned_company: Optional[str] = None
    assigned_to: Optional[str] = None
    confirmed_date: Optional[date] = None
    confirmed_start: Optional[str] = None
    confirmed_end: Optional[str] = None
    latest_ready: Optional[datetime] = None
    readiness_status: Optional[str] = None
    flags: Optional[List[str]] = None
    estimated_hours: Optional[float] = None
    estimated_hours_source: Optional[str] = None
    bedding_mode: Optional[str] = None
    bedding_for_guests: Optional[int] = None
    outgoing_guests: Optional[int] = None
    notes: Optional[str] = None
    actor: Optional[str] = None
    actor_role: Optional[str] = None


class ConfirmBody(BaseModel):
    confirmed_date: date
    confirmed_start: Optional[str] = "09:00"
    confirmed_end: Optional[str] = None
    latest_ready: Optional[datetime] = None
    assigned_to: Optional[str] = None
    actor: Optional[str] = None
    actor_role: Optional[str] = "cleaning_admin"


class AssignBody(BaseModel):
    assigned_to: Optional[str] = None
    assigned_company: Optional[str] = None
    actor: Optional[str] = None
    actor_role: Optional[str] = "cleaning_admin"


class StartCompleteBody(BaseModel):
    actual_minutes: Optional[int] = None
    has_deviation: Optional[bool] = False
    actor: Optional[str] = None
    actor_role: Optional[str] = "cleaner"


class EstimateBody(BaseModel):
    estimated_hours: float
    overridden_by: str
    actor_role: Optional[str] = "norli_admin"


class ChangeRequestBody(BaseModel):
    confirmed_date: Optional[date] = None
    confirmed_start: Optional[str] = None
    assignee: Optional[str] = None
    urgent: Optional[bool] = False
    note: Optional[str] = None
    actor: Optional[str] = None
    actor_role: Optional[str] = "cleaning_admin"


class ChangeResolveBody(BaseModel):
    approve: bool
    actor: Optional[str] = None
    actor_role: Optional[str] = "norli_admin"


class ReadinessBody(BaseModel):
    readiness_status: str
    actor: Optional[str] = None
    actor_role: Optional[str] = "norli_admin"


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.get("/cleaning-state")
def list_states(
    crm_property_id: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    db: Session = Depends(get_db),
):
    """Hämta lagrade tillstånd, ev. filtrerade per objekt och fönsterperiod."""
    q = db.query(CleaningJobState)
    if crm_property_id:
        q = q.filter(CleaningJobState.crm_property_id == crm_property_id)
    if date_from:
        q = q.filter(CleaningJobState.window_end >= datetime(date_from.year, date_from.month, date_from.day, tzinfo=timezone.utc))
    if date_to:
        q = q.filter(CleaningJobState.window_start <= datetime(date_to.year, date_to.month, date_to.day, 23, 59, tzinfo=timezone.utc))
    return [_state_dict(s) for s in q.all()]


@router.get("/cleaning-state/{job_key}")
def get_state(job_key: str, db: Session = Depends(get_db)):
    return _state_dict(_get_or_404(db, job_key))


@router.put("/cleaning-state/{job_key}")
def upsert_state(job_key: str, data: CleaningStateUpsert, db: Session = Depends(get_db)):
    """Skapa eller uppdatera ett tillstånd. Accepterar valfri delmängd av fält."""
    s = db.query(CleaningJobState).filter(CleaningJobState.job_key == job_key).first()
    payload = data.model_dump(exclude_unset=True)
    actor = payload.pop("actor", None)
    actor_role = payload.pop("actor_role", None)
    prev_confirmed = s.confirmed_date if s else None
    created = False

    if not s:
        crm = payload.get("crm_property_id")
        pid = payload.get("property_id")
        if not crm and pid is not None:
            prop = db.get(Property, pid)
            if prop:
                crm = prop.crm_property_id
        if not crm:
            raise HTTPException(422, "crm_property_id eller property_id krävs när tillståndet skapas")
        s = CleaningJobState(
            job_key=job_key,
            crm_property_id=crm,
            property_id=pid if pid is not None else _resolve_property_id(db, crm),
        )
        db.add(s)
        created = True

    for field, value in payload.items():
        if field == "flags":
            s.flags = json.dumps(value, ensure_ascii=False)
        elif field == "crm_property_id":
            s.crm_property_id = value
            s.property_id = _resolve_property_id(db, value)
        else:
            setattr(s, field, value)

    _log(db, job_key, "created" if created else "updated", actor=actor, actor_role=actor_role,
         detail={k: (str(v) if isinstance(v, (date, datetime)) else v) for k, v in payload.items()})

    new_confirmed = payload.get("confirmed_date")
    property_name = payload.pop("property_name", None)  # skickas från frontend, lagras ej

    # Detektera reset: confirmed_date skickas explicit som None och fanns tidigare
    is_reset = (not created) and ("confirmed_date" in payload) and new_confirmed is None and prev_confirmed is not None
    # Detektera dag-byte
    is_day_change = (not created) and new_confirmed is not None and prev_confirmed is not None and str(prev_confirmed) != str(new_confirmed)

    if is_reset:
        _log(db, job_key, "reset", actor=actor, actor_role=actor_role,
             detail={"from": str(prev_confirmed),
                     "crm_property_id": s.crm_property_id, "job_type": s.job_type,
                     "property_name": property_name})
        _send_event_email(
            subject=f"Städning återställd: {property_name or s.crm_property_id}",
            html=f"<p>Städning för <strong>{property_name or s.crm_property_id}</strong> har återställts till <em>obekräftad</em>.</p>"
                 f"<p>Tidigare bekräftad dag: {prev_confirmed}<br>Aktör: {actor or 'okänd'}</p>"
        )
    elif is_day_change:
        _log(db, job_key, "day_changed", actor=actor, actor_role=actor_role,
             detail={"from": str(prev_confirmed), "to": str(new_confirmed),
                     "crm_property_id": s.crm_property_id, "job_type": s.job_type,
                     "property_name": property_name})
        _send_event_email(
            subject=f"Städdag ändrad: {property_name or s.crm_property_id}",
            html=f"<p>Städdag för <strong>{property_name or s.crm_property_id}</strong> har ändrats.</p>"
                 f"<p>Från: {prev_confirmed}<br>Till: {new_confirmed}<br>Aktör: {actor or 'okänd'}</p>"
        )

    db.commit()
    db.refresh(s)
    return _state_dict(s)


def _ensure(db: Session, job_key: str, crm_property_id: Optional[str] = None) -> CleaningJobState:
    """Hämta tillstånd, eller skapa ett tomt om det inte finns (för action-anrop)."""
    s = db.query(CleaningJobState).filter(CleaningJobState.job_key == job_key).first()
    if not s:
        if not crm_property_id:
            raise HTTPException(404, f"Städuppdrag {job_key} finns ej (ange crm_property_id för att skapa)")
        s = CleaningJobState(job_key=job_key, crm_property_id=crm_property_id,
                             property_id=_resolve_property_id(db, crm_property_id))
        db.add(s)
    return s


@router.post("/cleaning-state/{job_key}/assign")
def assign(job_key: str, body: AssignBody, db: Session = Depends(get_db)):
    s = _get_or_404(db, job_key)
    if body.assigned_to is not None:
        s.assigned_to = body.assigned_to
    if body.assigned_company is not None:
        s.assigned_company = body.assigned_company
    if s.status in ("unassigned",) and s.assigned_to:
        s.status = "assigned"
    _log(db, job_key, "assigned", body.actor, body.actor_role,
         {"assigned_to": body.assigned_to, "assigned_company": body.assigned_company})
    db.commit(); db.refresh(s)
    return _state_dict(s)


@router.post("/cleaning-state/{job_key}/confirm")
def confirm(job_key: str, body: ConfirmBody, db: Session = Depends(get_db)):
    s = _get_or_404(db, job_key)
    s.confirmed_date = body.confirmed_date
    s.confirmed_start = body.confirmed_start
    s.confirmed_end = body.confirmed_end
    if body.latest_ready is not None:
        s.latest_ready = body.latest_ready
    if body.assigned_to is not None:
        s.assigned_to = body.assigned_to
    s.status = "confirmed"
    if s.readiness_status in ("not_checked", "cleaning_needed", "cleaning_planned"):
        s.readiness_status = "cleaning_confirmed"
    _log(db, job_key, "confirmed", body.actor, body.actor_role,
         {"date": str(body.confirmed_date), "start": body.confirmed_start,
          "end": body.confirmed_end, "assigned_to": body.assigned_to})
    db.commit(); db.refresh(s)
    return _state_dict(s)


@router.post("/cleaning-state/{job_key}/start")
def start(job_key: str, body: StartCompleteBody, db: Session = Depends(get_db)):
    s = _get_or_404(db, job_key)
    s.status = "in_progress"
    s.readiness_status = "in_progress"
    s.started_at = datetime.now(timezone.utc)
    _log(db, job_key, "started", body.actor, body.actor_role)
    db.commit(); db.refresh(s)
    return _state_dict(s)


@router.post("/cleaning-state/{job_key}/complete")
def complete(job_key: str, body: StartCompleteBody, db: Session = Depends(get_db)):
    s = _get_or_404(db, job_key)
    s.status = "done"
    s.completed_at = datetime.now(timezone.utc)
    if body.actual_minutes is not None:
        s.actual_minutes = body.actual_minutes
    s.readiness_status = "done_with_deviation" if body.has_deviation else "cleaning_done"
    _log(db, job_key, "completed", body.actor, body.actor_role,
         {"actual_minutes": body.actual_minutes, "has_deviation": body.has_deviation})
    db.commit(); db.refresh(s)
    return _state_dict(s)


@router.post("/cleaning-state/{job_key}/estimate")
def set_estimate(job_key: str, body: EstimateBody, db: Session = Depends(get_db)):
    """Manuell ändring av uppskattad städtid med signatur. Originalvärdet behålls."""
    s = _get_or_404(db, job_key)
    if s.estimated_hours_original is None and s.estimated_hours is not None:
        s.estimated_hours_original = s.estimated_hours
    s.estimated_hours = body.estimated_hours
    s.estimated_hours_source = "manual"
    s.estimated_hours_overridden_by = body.overridden_by
    s.estimated_hours_overridden_at = datetime.now(timezone.utc)
    _log(db, job_key, "estimate_changed", body.overridden_by, body.actor_role,
         {"estimated_hours": body.estimated_hours, "original": float(s.estimated_hours_original) if s.estimated_hours_original is not None else None})
    db.commit(); db.refresh(s)
    return _state_dict(s)


@router.post("/cleaning-state/{job_key}/change-request")
def change_request(job_key: str, body: ChangeRequestBody, db: Session = Depends(get_db)):
    """Begär ändring efter bekräftelse. Gammalt läge gäller tills Norli godkänt."""
    s = _get_or_404(db, job_key)
    s.change_status = "pending"
    s.change_requested_date = body.confirmed_date
    s.change_requested_start = body.confirmed_start
    s.change_requested_assignee = body.assignee
    s.change_is_urgent = bool(body.urgent)
    s.change_note = body.note
    flags = _flags_to_list(s.flags)
    flag = "urgent_change" if body.urgent else "change_requested"
    if flag not in flags:
        flags.append(flag)
        s.flags = json.dumps(flags, ensure_ascii=False)
    _log(db, job_key, "change_requested", body.actor, body.actor_role,
         {"date": str(body.confirmed_date) if body.confirmed_date else None,
          "start": body.confirmed_start, "assignee": body.assignee, "urgent": body.urgent})
    db.commit(); db.refresh(s)
    return _state_dict(s)


@router.post("/cleaning-state/{job_key}/change-resolve")
def change_resolve(job_key: str, body: ChangeResolveBody, db: Session = Depends(get_db)):
    """Norli godkänner eller avböjer en ändringsbegäran."""
    s = _get_or_404(db, job_key)
    if s.change_status != "pending":
        raise HTTPException(409, "Ingen ändringsbegäran att hantera")
    if body.approve:
        if s.change_requested_date is not None:
            s.confirmed_date = s.change_requested_date
        if s.change_requested_start is not None:
            s.confirmed_start = s.change_requested_start
        if s.change_requested_assignee is not None:
            s.assigned_to = s.change_requested_assignee
        s.change_status = "approved"
    else:
        s.change_status = "rejected"
    # Rensa ändringsflaggor
    flags = [f for f in _flags_to_list(s.flags) if f not in ("change_requested", "urgent_change")]
    s.flags = json.dumps(flags, ensure_ascii=False)
    s.change_requested_date = None
    s.change_requested_start = None
    s.change_requested_assignee = None
    s.change_is_urgent = False
    _log(db, job_key, "change_approved" if body.approve else "change_rejected",
         body.actor, body.actor_role)
    db.commit(); db.refresh(s)
    return _state_dict(s)


@router.post("/cleaning-state/{job_key}/readiness")
def set_readiness(job_key: str, body: ReadinessBody, db: Session = Depends(get_db)):
    """Sätt gästklar-status manuellt (t.ex. blockerad eller gästklar)."""
    s = _get_or_404(db, job_key)
    s.readiness_status = body.readiness_status
    _log(db, job_key, "readiness_changed", body.actor, body.actor_role,
         {"readiness_status": body.readiness_status})
    db.commit(); db.refresh(s)
    return _state_dict(s)


@router.get("/cleaning-audit/{job_key}")
def get_audit(job_key: str, db: Session = Depends(get_db)):
    rows = db.query(CleaningAuditLog).filter(
        CleaningAuditLog.job_key == job_key
    ).order_by(CleaningAuditLog.created_at.desc()).all()
    return [_audit_dict(a) for a in rows]


@router.get("/cleaning-events")
def list_events(limit: int = 50, db: Session = Depends(get_db)):
    """Senaste händelser för Norli-dashboarden (i v1: ändrade städdagar)."""
    rows = db.query(CleaningAuditLog).filter(
        CleaningAuditLog.event.in_(["day_changed", "reset"])
    ).order_by(CleaningAuditLog.created_at.desc()).limit(min(limit, 200)).all()
    return [_audit_dict(a) for a in rows]
