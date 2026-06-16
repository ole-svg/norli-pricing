"""
Eventkalender Stockholm 2026-2027.
Kalls manuellt: python scripts/seed_events_2026_2027.py
Baseras pa ChatGPT-analys av Visit Stockholm, SBR, Strawberry Arena, Stockholmsmassan.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from decimal import Decimal
from datetime import date
from db.session import SessionLocal
from db.models import Base, CalendarEvent, LocalEvent
from db.session import engine

Base.metadata.create_all(bind=engine)

# Konfidensnivaer: confirmed | recurring_estimate | watchlist
CALENDAR_EVENTS = [
    # Helgdagar och lov
    ("Midsommar 2026", "public_holiday", date(2026,6,19), date(2026,6,21), Decimal("1.10"), 20),
    ("Höstlov Stockholm 2026", "school_break", date(2026,10,26), date(2026,11,1), Decimal("1.20"), 10),
    ("Jul 2026", "public_holiday", date(2026,12,23), date(2026,12,26), Decimal("1.50"), 25),
    ("Nyar 2026-2027", "public_holiday", date(2026,12,27), date(2027,1,2), Decimal("1.65"), 30),
    ("Sportlov Stockholm 2027", "school_break", date(2027,3,1), date(2027,3,7), Decimal("1.25"), 10),
    ("Pask 2027", "public_holiday", date(2027,3,26), date(2027,4,2), Decimal("1.30"), 20),
    ("Kristi himmelsfard 2027", "public_holiday", date(2027,5,13), date(2027,5,16), Decimal("1.20"), 15),
    ("Midsommar 2027", "public_holiday", date(2027,6,18), date(2027,6,20), Decimal("1.10"), 20),
]

LOCAL_EVENTS_DATA = [
    # JUNI 2026
    ("PUMA HYROX World Championships", "sport", "Stockholm", "Strawberry Arena",
     date(2026,6,18), date(2026,6,21), Decimal("1.20"), Decimal("10")),
    ("System of a Down", "concert", "Stockholm", "Strawberry Arena",
     date(2026,6,29), date(2026,6,29), Decimal("1.35"), Decimal("5")),

    # JULI 2026
    ("Jehovahs Witnesses International Convention", "congress", "Stockholm", "Tele2 Arena",
     date(2026,7,3), date(2026,7,5), Decimal("1.28"), Decimal("15")),
    ("Bad Bunny", "concert", "Stockholm", "Strawberry Arena",
     date(2026,7,10), date(2026,7,11), Decimal("1.65"), Decimal("5")),
    ("Lenny Kravitz", "concert", "Stockholm", "Avicii Arena",
     date(2026,7,24), date(2026,7,24), Decimal("1.18"), Decimal("5")),

    # JULI-AUGUSTI 2026 - PRIDE
    ("Stockholm Pride", "festival", "Stockholm", "Stockholmsomradet",
     date(2026,7,27), date(2026,8,1), Decimal("1.55"), Decimal("10")),
    ("Pride Parade + Man Utd vs Atletico", "sport", "Stockholm", "Stockholmsomradet",
     date(2026,8,1), date(2026,8,1), Decimal("1.70"), Decimal("5")),

    # AUGUSTI 2026
    ("The Weeknd", "concert", "Stockholm", "Strawberry Arena",
     date(2026,8,8), date(2026,8,10), Decimal("1.75"), Decimal("5")),
    ("Stockholm Culture Festival", "festival", "Stockholm", "Stadshuset/city",
     date(2026,8,12), date(2026,8,16), Decimal("1.25"), Decimal("10")),
    ("Midnattsloppet", "sport", "Stockholm", "Östermalm",
     date(2026,8,15), date(2026,8,15), Decimal("1.35"), Decimal("8")),
    ("World Water Week", "congress", "Stockholm", "Stockholmsmassan",
     date(2026,8,23), date(2026,8,27), Decimal("1.32"), Decimal("10")),
    ("Formex", "fair", "Stockholm", "Stockholmsmassan",
     date(2026,8,25), date(2026,8,27), Decimal("1.28"), Decimal("10")),
    ("Stockholm Half Marathon", "sport", "Stockholm", "Gamla Stan",
     date(2026,8,29), date(2026,8,29), Decimal("1.30"), Decimal("8")),

    # SEPTEMBER 2026
    ("European Dog Show", "fair", "Stockholm", "Stockholmsmassan",
     date(2026,9,4), date(2026,9,6), Decimal("1.23"), Decimal("15")),
    ("Tjejmilen", "sport", "Stockholm", "Djurgarden",
     date(2026,9,5), date(2026,9,5), Decimal("1.28"), Decimal("8")),
    ("European Congress of Pathology", "congress", "Stockholm", "Stockholmsmassan",
     date(2026,9,12), date(2026,9,16), Decimal("1.38"), Decimal("15")),
    ("A$AP Rocky", "concert", "Stockholm", "Avicii Arena",
     date(2026,9,21), date(2026,9,21), Decimal("1.22"), Decimal("5")),
    ("World Congress of Psychiatry", "congress", "Stockholm", "Stockholmsmassan",
     date(2026,9,23), date(2026,9,26), Decimal("1.40"), Decimal("15")),
    ("Lidingoloppet + Sverige vs Rumänien", "sport", "Stockholm", "Lidingo/Friends Arena",
     date(2026,9,25), date(2026,9,27), Decimal("1.55"), Decimal("10")),
    ("Sverige vs Polen Nations League", "sport", "Stockholm", "Friends Arena",
     date(2026,9,28), date(2026,9,28), Decimal("1.23"), Decimal("5")),

    # OKTOBER 2026
    ("Hem & Villa + eCarExpo", "fair", "Stockholm", "Stockholmsmassan",
     date(2026,10,9), date(2026,10,11), Decimal("1.15"), Decimal("15")),
    ("Robyn", "concert", "Stockholm", "Tele2 Arena",
     date(2026,10,17), date(2026,10,17), Decimal("1.32"), Decimal("5")),
    ("SKYDD Totalförsvarsmässan", "fair", "Stockholm", "Stockholmsmassan",
     date(2026,10,20), date(2026,10,22), Decimal("1.18"), Decimal("10")),
    ("Deep Purple", "concert", "Stockholm", "Avicii Arena",
     date(2026,10,26), date(2026,10,26), Decimal("1.15"), Decimal("5")),

    # NOVEMBER 2026
    ("Stockholm Nordic Open Tennis", "sport", "Stockholm", "Avicii Arena",
     date(2026,11,7), date(2026,11,14), Decimal("1.20"), Decimal("10")),
    ("Stockholm International Film Festival", "festival", "Stockholm", "Cityomradet",
     date(2026,11,11), date(2026,11,22), Decimal("1.18"), Decimal("10")),
    ("J Cole", "concert", "Stockholm", "Avicii Arena",
     date(2026,11,11), date(2026,11,11), Decimal("1.23"), Decimal("5")),
    ("Benjamin Ingrosso", "concert", "Stockholm", "Avicii Arena",
     date(2026,11,13), date(2026,11,14), Decimal("1.30"), Decimal("5")),
    ("DreamHack Stockholm", "fair", "Stockholm", "Stockholmsmassan",
     date(2026,11,27), date(2026,11,29), Decimal("1.48"), Decimal("15")),

    # DECEMBER 2026
    ("Sweden International Horse Show", "sport", "Stockholm", "Strawberry Arena",
     date(2026,12,3), date(2026,12,6), Decimal("1.48"), Decimal("10")),
    ("Nobel Day", "congress", "Stockholm", "Konserthuset/Stadshuset",
     date(2026,12,10), date(2026,12,10), Decimal("1.20"), Decimal("10")),
    ("Phoebe Bridgers", "concert", "Stockholm", "Avicii Arena",
     date(2026,12,12), date(2026,12,12), Decimal("1.18"), Decimal("5")),

    # JANUARI 2027
    ("Formex Januari", "fair", "Stockholm", "Stockholmsmassan",
     date(2027,1,19), date(2027,1,21), Decimal("1.23"), Decimal("10")),
    ("aespa", "concert", "Stockholm", "Avicii Arena",
     date(2027,1,22), date(2027,1,22), Decimal("1.23"), Decimal("5")),

    # FEBRUARI 2027
    ("Stockholm Design Week + Furniture Fair", "fair", "Stockholm", "Stockholmsmassan",
     date(2027,2,8), date(2027,2,14), Decimal("1.38"), Decimal("10")),

    # MARS-APRIL 2027
    ("Olivia Rodrigo", "concert", "Stockholm", "Avicii Arena",
     date(2027,3,19), date(2027,3,20), Decimal("1.48"), Decimal("5")),

    # MAJ 2027
    ("Tough Viking Stockholm", "sport", "Stockholm", "Stadion",
     date(2027,5,15), date(2027,5,15), Decimal("1.18"), Decimal("8")),
    ("Gracie Abrams", "concert", "Stockholm", "Avicii Arena",
     date(2027,5,18), date(2027,5,19), Decimal("1.28"), Decimal("5")),
    ("Stockholm Marathon 2027", "sport", "Stockholm", "Stadion",
     date(2027,5,29), date(2027,5,29), Decimal("1.38"), Decimal("10")),

    # JUNI 2027
    ("CIRED Kongress", "congress", "Stockholm", "Stockholmsmassan",
     date(2027,6,14), date(2027,6,17), Decimal("1.23"), Decimal("10")),
    ("Womens EuroBasket 2027", "sport", "Stockholm", "Avicii Arena",
     date(2027,6,16), date(2027,6,27), Decimal("1.30"), Decimal("10")),
]

def seed_events():
    db = SessionLocal()
    try:
        cal_count = 0
        for name, etype, start, end, mult, prio in CALENDAR_EVENTS:
            existing = db.query(CalendarEvent).filter_by(name=name, start_date=start).first()
            if not existing:
                db.add(CalendarEvent(name=name, event_type=etype, start_date=start,
                                     end_date=end, multiplier=mult, priority=prio))
                cal_count += 1

        local_count = 0
        for name, etype, loc, venue, start, end, mult, radius in LOCAL_EVENTS_DATA:
            existing = db.query(LocalEvent).filter_by(name=name, start_date=start).first()
            if not existing:
                db.add(LocalEvent(name=name, event_type=etype, location=loc, venue=venue,
                                  start_date=start, end_date=end, multiplier=mult, radius_km=radius))
                local_count += 1

        db.commit()
        print(f"✓ {cal_count} kalenderhandelser skapade")
        print(f"✓ {local_count} lokala evenemang skapade")
        print("\nKor nu omrakning:")
        print("  curl -X POST http://localhost:8000/prices/enskede-79/recalculate")

    except Exception as e:
        db.rollback()
        print(f"Fel: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    print("=== Eventkalender Stockholm 2026-2027 ===\n")
    seed_events()
