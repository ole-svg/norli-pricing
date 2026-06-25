"""
engine/geo.py
Geografisk filtrering av lokala evenemang.

Varje LocalEvent har venue_lat/venue_lng och radius_km.
Varje Property har latitude/longitude.
Motorn applicerar bara events som är inom radien från objektet.

Standardradier:
  Stockholm city events (Avicii Arena, Strawberry Arena, Tele2):  50 km
  → Täcker Enskede, Älta, Älvsjö men INTE Trosa (65 km) eller Ronneby (400 km)

  Nationella events (Pride, Eurovision etc): 200 km
  → Påverkar hela Sverige om relevant

  Lokala/regionala events: 20-30 km
  → Bara närmaste objekt
"""

import math
from decimal import Decimal
from typing import Optional


# Koordinater för Stockholms evenemangsarenor (venues)
STOCKHOLM_VENUES: dict[str, tuple[float, float]] = {
    "Avicii Arena":       (59.2981, 18.0029),
    "Strawberry Arena":   (59.3724, 17.9986),
    "Tele2 Arena":        (59.2944, 18.0834),
    "Friends Arena":      (59.3728, 17.9980),
    "Stockholmsmässan":   (59.2766, 17.9398),
    "Stadion":            (59.3426, 18.0752),
    "Konserthuset":       (59.3348, 18.0638),
    "Stadshuset":         (59.3275, 18.0544),
    "Gamla Stan":         (59.3251, 18.0711),
    "Djurgården":         (59.3299, 18.1076),
    "Östermalm":          (59.3371, 18.0855),
    "Lidingö":            (59.3628, 18.1563),
    "Cityområdet":        (59.3326, 18.0649),
    "Stockholmsområdet":  (59.3293, 18.0686),
    "Stockholms centrum": (59.3326, 18.0649),
}

# Objektkoordinater (Norlis objekt)
PROPERTY_COORDS: dict[str, tuple[float, float]] = {
    "enskede-79":        (59.2743, 18.0808),   # Enskede — 8 km från city
    "alta-beach-villa":  (59.2563, 18.1621),   # Älta — 13 km från city
    "alvsjö-tradgard":   (59.2775, 17.9860),   # Älvsjö Trädgård — 9 km från city
    "alvsjö-strandvilla":(59.2775, 17.9860),   # Älvsjö Strandvilla — samma område
    "trosa-havsdrom":    (58.8945, 17.5478),   # Trosa — 65 km från city
    "ronneby-fritidshus":(56.2107, 15.2758),   # Ronneby — 400 km från city
}

# Standardradius om inget annat anges
DEFAULT_RADIUS_KM = 50.0  # Stockholm city-events


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Beräknar avstånd i km mellan två koordinater (Haversine-formeln)."""
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dphi/2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlng/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def get_property_coords(crm_property_id: str, prop_lat=None, prop_lng=None) -> Optional[tuple[float, float]]:
    """Hämtar koordinater för ett objekt — DB först, fallback till hårdkodad karta."""
    if prop_lat is not None and prop_lng is not None:
        return (float(prop_lat), float(prop_lng))
    return PROPERTY_COORDS.get(crm_property_id)


def get_venue_coords(venue_name: str, event_lat=None, event_lng=None) -> Optional[tuple[float, float]]:
    """Hämtar koordinater för en venue — DB först, fallback till hårdkodad karta."""
    if event_lat is not None and event_lng is not None:
        return (float(event_lat), float(event_lng))
    return STOCKHOLM_VENUES.get(venue_name)


def event_affects_property(
    event,
    crm_property_id: str,
    prop_lat=None,
    prop_lng=None,
) -> bool:
    """
    Avgör om ett lokalt evenemang påverkar ett givet objekt.

    Returnerar True om objektet är inom eventets radius, annars False.
    Om koordinater saknas på eventet antas det vara ett Stockholmsevent
    med DEFAULT_RADIUS_KM.
    """
    prop_coords = get_property_coords(crm_property_id, prop_lat, prop_lng)
    if prop_coords is None:
        # Okänt objekt — applicera event (safe default)
        return True

    # Hämta venue-koordinater
    venue_coords = get_venue_coords(
        getattr(event, 'venue', '') or '',
        getattr(event, 'venue_lat', None),
        getattr(event, 'venue_lng', None),
    )

    if venue_coords is None:
        # Okänd venue — använd Stockholm city som fallback
        venue_coords = (59.3326, 18.0649)

    radius = float(getattr(event, 'radius_km', None) or DEFAULT_RADIUS_KM)
    distance = haversine_km(prop_coords[0], prop_coords[1], venue_coords[0], venue_coords[1])

    return distance <= radius
