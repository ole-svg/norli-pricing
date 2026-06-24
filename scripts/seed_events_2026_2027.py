"""
Eventkalender Stockholm 2026-2027.
Kallas via POST /setup/seed-events
Rensar gamla events och seedar om med korrekta datum.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from decimal import Decimal
from datetime import date
from db.session import SessionLocal
from db.models import Base, CalendarEvent, LocalEvent
from db.session import engine

Base.metadata.create_all(bind=engine)

CALENDAR_EVENTS = [
    # 2026
    ("Midsommar 2026",           "public_holiday", date(2026,6,19),  date(2026,6,21),  Decimal("1.10"), 20),
    ("Höstlov Stockholm 2026",   "school_break",   date(2026,10,26), date(2026,11,1),  Decimal("1.20"), 10),
    ("Jul 2026",                 "public_holiday", date(2026,12,23), date(2026,12,26), Decimal("1.50"), 25),
    ("Nyår 2026-2027",           "public_holiday", date(2026,12,27), date(2027,1,2),   Decimal("1.65"), 30),
    # 2027
    ("Sportlov Stockholm 2027",  "school_break",   date(2027,2,22),  date(2027,3,1),   Decimal("1.25"), 10),
    ("Påsk 2027",                "public_holiday", date(2027,3,26),  date(2027,4,2),   Decimal("1.30"), 20),
    ("Kristi himmelsfärd 2027",  "public_holiday", date(2027,5,13),  date(2027,5,16),  Decimal("1.20"), 15),
    ("Midsommar 2027",           "public_holiday", date(2027,6,18),  date(2027,6,20),  Decimal("1.10"), 20),
]

LOCAL_EVENTS_DATA = [
    # JUNI 2026
    ("Stockholm Marathon 2026",              "sports",     "Stockholm", "Stadion",             date(2026,6,6),  date(2026,6,7),  Decimal("1.25")),
    ("PUMA HYROX World Championships",       "sports",     "Stockholm", "Strawberry Arena",    date(2026,6,18), date(2026,6,21), Decimal("1.20")),
    ("System of a Down",                     "concert",    "Stockholm", "Strawberry Arena",    date(2026,6,29), date(2026,6,29), Decimal("1.35")),
    # JULI 2026
    ("Jehovah's Witnesses Convention",       "conference", "Stockholm", "Tele2 Arena",         date(2026,7,3),  date(2026,7,5),  Decimal("1.28")),
    ("Bad Bunny",                            "concert",    "Stockholm", "Strawberry Arena",    date(2026,7,10), date(2026,7,11), Decimal("1.65")),
    ("Lenny Kravitz",                        "concert",    "Stockholm", "Avicii Arena",        date(2026,7,24), date(2026,7,24), Decimal("1.18")),
    # JULI-AUGUSTI 2026
    ("Stockholm Pride 2026",                 "concert",    "Stockholm", "Stockholmsområdet",   date(2026,7,27), date(2026,8,1),  Decimal("1.55")),
    ("Pride Parade + Man Utd vs Atletico",   "sports",     "Stockholm", "Stockholmsområdet",   date(2026,8,1),  date(2026,8,1),  Decimal("1.70")),
    # AUGUSTI 2026
    ("The Weeknd",                           "concert",    "Stockholm", "Strawberry Arena",    date(2026,8,8),  date(2026,8,10), Decimal("1.75")),
    ("Stockholm Culture Festival",           "concert",    "Stockholm", "Stadshuset",          date(2026,8,12), date(2026,8,16), Decimal("1.25")),
    ("Midnattsloppet",                       "sports",     "Stockholm", "Östermalm",           date(2026,8,15), date(2026,8,15), Decimal("1.35")),
    ("World Water Week",                     "conference", "Stockholm", "Stockholmsmässan",    date(2026,8,23), date(2026,8,27), Decimal("1.32")),
    ("Stockholm Half Marathon",              "sports",     "Stockholm", "Gamla Stan",          date(2026,8,29), date(2026,8,29), Decimal("1.30")),
    # SEPTEMBER 2026
    ("European Dog Show",                    "conference", "Stockholm", "Stockholmsmässan",    date(2026,9,4),  date(2026,9,6),  Decimal("1.23")),
    ("Tjejmilen",                            "sports",     "Stockholm", "Djurgården",          date(2026,9,5),  date(2026,9,5),  Decimal("1.28")),
    ("European Congress of Pathology",       "conference", "Stockholm", "Stockholmsmässan",    date(2026,9,12), date(2026,9,16), Decimal("1.38")),
    ("A$AP Rocky",                           "concert",    "Stockholm", "Avicii Arena",        date(2026,9,21), date(2026,9,21), Decimal("1.22")),
    ("World Congress of Psychiatry",         "conference", "Stockholm", "Stockholmsmässan",    date(2026,9,23), date(2026,9,26), Decimal("1.40")),
    ("Lidingöloppet",                        "sports",     "Stockholm", "Lidingö",             date(2026,9,26), date(2026,9,27), Decimal("1.35")),
    ("Sverige vs Polen Nations League",      "sports",     "Stockholm", "Friends Arena",       date(2026,9,28), date(2026,9,28), Decimal("1.23")),
    # OKTOBER 2026
    ("Hem & Villa + eCarExpo",               "conference", "Stockholm", "Stockholmsmässan",    date(2026,10,9), date(2026,10,11),Decimal("1.15")),
    ("Robyn",                                "concert",    "Stockholm", "Tele2 Arena",         date(2026,10,17),date(2026,10,17),Decimal("1.32")),
    ("Deep Purple",                          "concert",    "Stockholm", "Avicii Arena",        date(2026,10,26),date(2026,10,26),Decimal("1.15")),
    # NOVEMBER 2026
    ("Stockholm Nordic Open Tennis",         "sports",     "Stockholm", "Avicii Arena",        date(2026,11,7), date(2026,11,14),Decimal("1.20")),
    ("Stockholm International Film Festival","concert",    "Stockholm", "Cityområdet",         date(2026,11,11),date(2026,11,22),Decimal("1.18")),
    ("J Cole",                               "concert",    "Stockholm", "Avicii Arena",        date(2026,11,11),date(2026,11,11),Decimal("1.23")),
    ("Benjamin Ingrosso",                    "concert",    "Stockholm", "Avicii Arena",        date(2026,11,13),date(2026,11,14),Decimal("1.30")),
    ("DreamHack Stockholm",                  "conference", "Stockholm", "Stockholmsmässan",    date(2026,11,27),date(2026,11,29),Decimal("1.48")),
    # DECEMBER 2026
    ("Sweden International Horse Show",      "sports",     "Stockholm", "Strawberry Arena",    date(2026,12,3), date(2026,12,6), Decimal("1.48")),
    ("Nobel Day",                            "conference", "Stockholm", "Konserthuset",        date(2026,12,10),date(2026,12,10),Decimal("1.20")),
    ("Phoebe Bridgers",                      "concert",    "Stockholm", "Avicii Arena",        date(2026,12,12),date(2026,12,12),Decimal("1.18")),
    # JANUARI 2027
    ("Formex Januari 2027",                  "conference", "Stockholm", "Stockholmsmässan",    date(2027,1,19), date(2027,1,21), Decimal("1.23")),
    ("aespa",                                "concert",    "Stockholm", "Avicii Arena",        date(2027,1,22), date(2027,1,22), Decimal("1.23")),
    # FEBRUARI 2027
    ("Stockholm Design Week + Furniture Fair","conference","Stockholm", "Stockholmsmässan",    date(2027,2,8),  date(2027,2,14), Decimal("1.38")),
    # MARS 2027
    ("Olivia Rodrigo",                       "concert",    "Stockholm", "Avicii Arena",        date(2027,3,19), date(2027,3,20), Decimal("1.48")),
    # MAJ 2027
    ("Gracie Abrams",                        "concert",    "Stockholm", "Avicii Arena",        date(2027,5,18), date(2027,5,19), Decimal("1.28")),
    ("Stockholm Marathon 2027",              "sports",     "Stockholm", "Stadion",             date(2027,5,29), date(2027,5,29), Decimal("1.38")),
    # JUNI 2027
    ("Women's EuroBasket 2027",              "sports",     "Stockholm", "Avicii Arena",        date(2027,6,16), date(2027,6,27), Decimal("1.30")),
]


def seed_events():
    db = SessionLocal()
    try:
        # Rensa gamla events (äldre än 2026-01-01)
        from datetime import date as d_
        old_cal = db.query(CalendarEvent).filter(CalendarEvent.start_date < d_(2026,1,1)).all()
        old_local = db.query(LocalEvent).filter(LocalEvent.start_date < d_(2026,1,1)).all()
        deleted_cal = len(old_cal)
        deleted_local = len(old_local)
        for e in old_cal: db.delete(e)
        for e in old_local: db.delete(e)
        db.commit()
        print(f"  Raderade {deleted_cal} gamla calendar-events, {deleted_local} gamla local-events")

        cal_count = 0
        for name, etype, start, end, mult, prio in CALENDAR_EVENTS:
            existing = db.query(CalendarEvent).filter_by(name=name, start_date=start).first()
            if not existing:
                db.add(CalendarEvent(name=name, event_type=etype, start_date=start,
                                     end_date=end, multiplier=mult, priority=prio))
                cal_count += 1

        local_count = 0
        for name, etype, loc, venue, start, end, mult in LOCAL_EVENTS_DATA:
            existing = db.query(LocalEvent).filter_by(name=name, start_date=start).first()
            if not existing:
                db.add(LocalEvent(name=name, event_type=etype, location=loc, venue=venue,
                                  start_date=start, end_date=end, multiplier=mult))
                local_count += 1

        db.commit()
        print(f"✓ {cal_count} kalenderevents skapade")
        print(f"✓ {local_count} lokala evenemang skapade")

    except Exception as e:
        db.rollback()
        print(f"Fel: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    print("=== Eventkalender Stockholm 2026-2027 ===\n")
    seed_events()
