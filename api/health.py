"""Hälsokontroll — enkel endpoint för att verifiera att API:et är uppe."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
def health_check():
    """Returnerar 200 OK om API:et är igång."""
    return {"status": "ok", "service": "norli-pricing-engine", "version": "1.0.0"}
