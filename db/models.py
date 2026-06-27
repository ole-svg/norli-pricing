"""
Databasmodeller for Norli Pricing Engine.

Varje klass har motsvarar en tabell i PostgreSQL.
SQLAlchemy oversatter Python-klasserna till SQL automatiskt.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Boolean, Date, DateTime, ForeignKey, Integer, Numeric,
    String, Text, UniqueConstraint, func
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Property(Base):
    """
    Ett uthyrningsobjekt.
    Speglar bara de attribut prissattningsmotor behover.
    CRM pushar andringar hit via API.
    """
    __tablename__ = "properties"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    crm_property_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    airbnb_listing_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Adress
    address: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    postal_code: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    # Geografiska koordinater — används för att filtrera lokala events
    latitude: Mapped[Optional[Decimal]] = mapped_column(Numeric(9, 6), nullable=True)
    longitude: Mapped[Optional[Decimal]] = mapped_column(Numeric(9, 6), nullable=True)

    # Grundinfo
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    bedrooms: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    bathrooms: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    linen_included: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Grundpris
    # Prissattningskategori - styr sasongsmonster (manuellt tilldelad av Norli)
    pricing_category_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, default="STOCKHOLM_URBAN_EVENT")

    # Stadsprofil (refererar till CleaningProfile.code)
    cleaning_profile_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, default="default_villa")

    # ── Objektspecifikationer ────────────────────────────────────────────────
    # Maxgaster (absolut tak, fran Airbnb-listingen)
    max_guests: Mapped[int] = mapped_column(Integer, nullable=False, default=12)

    # Avrundningsregel for publicerade priser
    # "nearest_50" | "nearest_100" | "nearest_200" | "tiered" (var standard)
    rounding_rule: Mapped[str] = mapped_column(String(20), nullable=False, default="nearest_10")

    # Eventkansliget: hur starkt paverkas objektet av Stockholmsevent?
    # "high" | "medium" | "low"
    event_sensitivity: Mapped[str] = mapped_column(String(10), nullable=False, default="high")

    # ── Objektkostnader ─────────────────────────────────────────────────────
    # Fast kostnad per bokning (forbrukningsvaror, administration)
    object_cost_per_booking: Mapped[Decimal] = mapped_column(Numeric(10,2), nullable=False, default=Decimal("200"))

    # Rorlig kostnad per natt (slitage, energi)
    object_cost_per_night: Mapped[Optional[Decimal]] = mapped_column(Numeric(10,2), nullable=True)

    # Rorlig kostnad per gast
    object_cost_per_guest: Mapped[Optional[Decimal]] = mapped_column(Numeric(10,2), nullable=True)

    # ── Stadsmodell v2 — universell trappa ────────────────────────────────
    # Basgaster (utgangspunkt for gastjustering, t.ex. 8 for Enskede)
    cleaning_base_guests: Mapped[int] = mapped_column(Integer, nullable=False, default=8)

    # Minimum stadstid per vistelse (golv, oavsett natter/gaster)
    cleaning_min_hours: Mapped[Decimal] = mapped_column(Numeric(4,2), nullable=False, default=Decimal("3.0"))

    # Gastjustering per 2-personsintervall OVER basgaster (t.ex. 0.5h)
    cleaning_hours_per_2_guests_above: Mapped[Decimal] = mapped_column(Numeric(4,2), nullable=False, default=Decimal("0.5"))

    # Gastjustering per 2-personsintervall UNDER basgaster (t.ex. 0.25h)
    cleaning_hours_per_2_guests_below: Mapped[Decimal] = mapped_column(Numeric(4,2), nullable=False, default=Decimal("0.25"))

    # ── Last-minute prissattning ─────────────────────────────────────────────
    # Aktivera/avaktivera last-minute-rabatt for detta objekt
    last_minute_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Antal dagar innan incheckningsdatum dar rabatten borjar
    last_minute_start_days: Mapped[int] = mapped_column(Integer, nullable=False, default=20)

    # Maximal rabatt i procent (t.ex. 0.20 = 20% rabatt sista dagen)
    last_minute_max_discount: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False, default=Decimal("0.20"))

    # Minimum pris efter last-minute-rabatt (skyddsracke)
    # Om None anvands ekonomikalkylatorn for att rakna ut minimum lonsamt pris
    last_minute_min_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)

    base_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    pricing_strategy: Mapped[str] = mapped_column(String(50), nullable=False, default="balanced")

    # LOS-profil: styr min-stay och LOS-trappa
    # "urban_hotel"  = Enskede, Älta, Älvsjö Trädgård — 1-natts premium, tydlig trappa
    # "destination"  = Trosa, Ronneby — säsongsstyrd, min 2-3 nätter
    pricing_profile: Mapped[str] = mapped_column(String(30), nullable=False, default="urban_hotel")

    # Weekly/monthly discount i procent (0-100), sätts per objekt
    weekly_discount_pct: Mapped[Optional[Decimal]] = mapped_column(Numeric(5,2), nullable=True)
    monthly_discount_pct: Mapped[Optional[Decimal]] = mapped_column(Numeric(5,2), nullable=True)

    # Skyddsracken
    price_floor: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    price_ceiling: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    min_margin: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    min_owner_net: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)

    # ── Lönsamhetsmål per natt (ägarens netto) ───────────────────────────────
    # Absolut golv — bokning under detta är destruktiv, accepteras bara som gap night
    owner_net_floor: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True, default=Decimal("900"))
    # Normalmål — standardgolv för vanliga datum
    owner_net_target: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True, default=Decimal("1600"))
    # Starkt mål — helger, event, hög säsong
    owner_net_strong: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True, default=Decimal("2300"))
    # Event-mål — Pride, stora konserter, peak
    owner_net_event: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True, default=Decimal("3000"))

    # Minimumnetto per bokning (totalt, oavsett antal nätter)
    # En bokning som inte når detta är inte värd att ta emot
    # Systemet tar max(per-natt-golv × nätter, min_booking_net)
    min_booking_net: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True, default=Decimal("3000"))

    # ── Minimum stay ─────────────────────────────────────────────────────────
    min_stay_default: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    min_stay_weekend: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    min_stay_highseason: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    min_stay_event: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    allow_one_night: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # ── Airbnb avgiftsmodell ─────────────────────────────────────────────────
    # "split_fee" = 3% värd + ~14% gäst (standard)
    # "host_only" = 15.5% värd
    airbnb_fee_model: Mapped[str] = mapped_column(String(20), nullable=False, default="split_fee")
    airbnb_host_fee_pct: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False, default=Decimal("0.03"))

    # Ekonomimodell
    # "commission" | "management_fee"
    revenue_model: Mapped[str] = mapped_column(String(50), nullable=False, default="commission")
    # "company_vat_registered" | "company_not_vat_registered" | "private_person"
    owner_type: Mapped[str] = mapped_column(String(50), nullable=False, default="company_vat_registered")
    platform_fee_rate: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False, default=Decimal("0.03"))
    vat_rate: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False, default=Decimal("0.12"))
    owner_share_pct: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False, default=Decimal("0.82"))
    norli_share_pct: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False, default=Decimal("0.18"))

    # Stadmodell
    cleaning_hourly_rate: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=Decimal("500"))
    cleaning_base_hours: Mapped[Decimal] = mapped_column(Numeric(4, 2), nullable=False, default=Decimal("2.0"))
    cleaning_hours_per_bedroom: Mapped[Decimal] = mapped_column(Numeric(4, 2), nullable=False, default=Decimal("0.5"))
    cleaning_hours_per_bathroom: Mapped[Decimal] = mapped_column(Numeric(4, 2), nullable=False, default=Decimal("0.5"))
    cleaning_hours_per_guest: Mapped[Decimal] = mapped_column(Numeric(4, 2), nullable=False, default=Decimal("0.25"))
    cleaning_extra_hours_per_night: Mapped[Decimal] = mapped_column(Numeric(4, 2), nullable=False, default=Decimal("0.2"))
    cleaning_night_threshold: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    cleaning_max_hours: Mapped[Decimal] = mapped_column(Numeric(4, 2), nullable=False, default=Decimal("8.0"))
    # "norli" | "owner_private" | "owner_company"
    cleaning_invoice_recipient: Mapped[str] = mapped_column(String(50), nullable=False, default="owner_company")
    cleaning_rut_applicable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Objektkostnader per bokning (forbrukningsmaterial, toapapper, tval etc)
    object_costs_per_booking: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)

    # ── Airbnb-avgifter (speglar Airbnbs avgiftsstruktur) ────────────────────
    # Städavgift per vistelse (standard, 3+ nätter)
    cleaning_fee_per_stay: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)

    # Städavgift för kortare vistelser (1-2 nätter) - lägre belopp
    cleaning_fee_short_stay: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    cleaning_fee_short_stay_max_nights: Mapped[int] = mapped_column(Integer, nullable=False, default=2)

    # Husdjursavgift per vistelse
    pet_fee_per_stay: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)

    # Avgift for extra gast (per natt, over ett visst antal gaster)
    extra_guest_fee_per_night: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    extra_guest_fee_trigger: Mapped[int] = mapped_column(Integer, nullable=False, default=8)

    # Administrationsavgift per vistelse
    admin_fee_per_stay: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)

    # Lokal avgift per vistelse (kommunal/regional avgift)
    local_fee_per_stay: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)

    # Avgift for sangklader per vistelse
    linen_fee_per_stay: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)

    # Hotelavgift per vistelse (turistskatt etc)
    hotel_fee_per_stay: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)

    # Investeringar / uppstartskostnader
    # Totalt utestående saldo som ska kvittas mot agarens utbetalningar
    investment_balance: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=Decimal("0"))
    # "auto_full" | "auto_with_cap" | "manual"
    investment_recoupment_mode: Mapped[str] = mapped_column(String(50), nullable=False, default="auto_full")
    # Fast tak per avrakning i kr (NULL = inget tak)
    investment_recoupment_cap: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    # Tak som procent av agarandel (t.ex. 0.50 = max 50%)
    investment_recoupment_cap_pct: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 4), nullable=True)

    # Metadata
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    price_rules: Mapped[list["PriceRule"]] = relationship("PriceRule", back_populates="property")
    price_snapshots: Mapped[list["PriceSnapshot"]] = relationship("PriceSnapshot", back_populates="property")

    def __repr__(self) -> str:
        return f"<Property id={self.id} name={self.name!r}>"


class Season(Base):
    """Sasongsdefinitioner. Galler globalt for alla objekt."""
    __tablename__ = "seasons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    multiplier: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self) -> str:
        return f"<Season id={self.id} name={self.name!r}>"


class CalendarEvent(Base):
    """Kalenderhandelser: roda dagar, skollov etc."""
    __tablename__ = "calendar_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    # "public_holiday" | "school_break"
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    multiplier: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self) -> str:
        return f"<CalendarEvent id={self.id} name={self.name!r}>"


class LocalEvent(Base):
    """Lokala evenemang: konserter, massor, kongresser, sport."""
    __tablename__ = "local_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    # "concert" | "fair" | "congress" | "sport"
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    location: Mapped[str] = mapped_column(String(200), nullable=False)
    venue: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    multiplier: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    # Koordinater för evenemangsplatsen (venue)
    venue_lat: Mapped[Optional[Decimal]] = mapped_column(Numeric(9, 6), nullable=True)
    venue_lng: Mapped[Optional[Decimal]] = mapped_column(Numeric(9, 6), nullable=True)
    # Max avstånd från venue för att eventet ska påverka ett objekt (default 50 km = hela Stockholmsregionen)
    radius_km: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 2), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self) -> str:
        return f"<LocalEvent id={self.id} name={self.name!r}>"


class PriceRule(Base):
    """Objektspecifika prisregler."""
    __tablename__ = "price_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    property_id: Mapped[int] = mapped_column(Integer, ForeignKey("properties.id"), nullable=False)
    # "weekday_adjustment" | "length_of_stay" | "demand_adjustment"
    rule_type: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    parameters: Mapped[str] = mapped_column(Text, nullable=False)  # JSON
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    property: Mapped["Property"] = relationship("Property", back_populates="price_rules")

    def __repr__(self) -> str:
        return f"<PriceRule id={self.id} type={self.rule_type!r}>"


class PriceSnapshot(Base):
    """
    Beraknat pris per objekt och dag.

    Sparar bade rekommenderat pris (motorns utrakning)
    och publicerat pris (vad Norli faktiskt la upp).
    Prisforklaringen ar audit trail for varje pris.
    """
    __tablename__ = "price_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    property_id: Mapped[int] = mapped_column(Integer, ForeignKey("properties.id"), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    recommended_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    min_stay: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    published_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    is_clamped_floor: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_clamped_ceiling: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    engine_version: Mapped[str] = mapped_column(String(20), nullable=False, default="1.0.0")
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    property: Mapped["Property"] = relationship("Property", back_populates="price_snapshots")

    __table_args__ = (
        UniqueConstraint("property_id", "date", name="uq_snapshot_property_date"),
    )

    def __repr__(self) -> str:
        return f"<PriceSnapshot property_id={self.property_id} date={self.date} price={self.recommended_price}>"



class CleaningProfile(Base):
    """
    Stadsprofilmall — definerar natttrappa och gastjustering.
    
    Hierarki: Global default → Kategori-default → Objekt-override
    I v1 anvands en global default for alla objekt.
    """
    __tablename__ = "cleaning_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Gastinstallningar
    base_guests: Mapped[int] = mapped_column(Integer, nullable=False, default=8)
    min_hours: Mapped[Decimal] = mapped_column(Numeric(4,2), nullable=False, default=Decimal("3.0"))
    max_hours: Mapped[Decimal] = mapped_column(Numeric(4,2), nullable=False, default=Decimal("8.0"))
    guest_interval: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    under_base_adjustment: Mapped[Decimal] = mapped_column(Numeric(4,2), nullable=False, default=Decimal("0.25"))
    over_base_adjustment: Mapped[Decimal] = mapped_column(Numeric(4,2), nullable=False, default=Decimal("0.50"))

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Natttrappa: sparas som JSON-dict {1: 3.0, 2: 3.5, ...}
    los_hours_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    @property
    def los_hours(self) -> dict:
        import json
        if self.los_hours_json:
            return json.loads(self.los_hours_json)
        # Default: vår universella trappa
        return {"1":3.0,"2":3.5,"3":4.0,"4":4.5,"5":5.0,"6":5.5,"7":6.0,"8":7.0}

    def get_hours_for_nights(self, nights: int) -> Decimal:
        table = self.los_hours
        key = str(min(nights, 8))
        return Decimal(str(table.get(key, 7.0)))

    def __repr__(self) -> str:
        return f"<CleaningProfile code={self.code!r}>"

class PricingCategory(Base):
    """
    Prissattningskategori — styr sasongsmonster per objekt.

    Kategori = sasongsmonster (manad for manad).
    Event-lagret styr datumpikar ovanpa.
    Varje objekt tilldelas manuellt en kategori av Norli.
    """
    __tablename__ = "pricing_categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    monthly_multipliers: Mapped[list["PricingCategoryMultiplier"]] = relationship(
        "PricingCategoryMultiplier", back_populates="category", order_by="PricingCategoryMultiplier.month"
    )

    def __repr__(self) -> str:
        return f"<PricingCategory code={self.code!r} active={self.is_active}>"


class PricingCategoryMultiplier(Base):
    """
    Manadvis sasongsm ultiplikator per kategori.
    12 rader per kategori (en per manad, 1=jan ... 12=dec).
    """
    __tablename__ = "pricing_category_multipliers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    category_id: Mapped[int] = mapped_column(Integer, ForeignKey("pricing_categories.id"), nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)  # 1=jan, 12=dec
    multiplier: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)

    category: Mapped["PricingCategory"] = relationship("PricingCategory", back_populates="monthly_multipliers")

    __table_args__ = (
        UniqueConstraint("category_id", "month", name="uq_category_month"),
    )

    def __repr__(self) -> str:
        return f"<PricingCategoryMultiplier category_id={self.category_id} month={self.month} mult={self.multiplier}>"


class Booking(Base):
    """
    Bokning hämtad via iCal-synk från Airbnb/Booking.com/VRBO.
    
    Status:
      active    — visas i systemet
      ignored   — importerad men dold (t.ex. Cohoast-blockeringar, Airbnb-blocks)
      private   — visas bara för admin, ej i rapporter
    """
    __tablename__ = "bookings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    property_id: Mapped[int] = mapped_column(Integer, ForeignKey("properties.id"), nullable=False)

    # iCal-identitet (unik per bokning från källan)
    ical_uid: Mapped[str] = mapped_column(String(500), unique=True, nullable=False)

    # Datum
    check_in: Mapped[date] = mapped_column(Date, nullable=False)
    check_out: Mapped[date] = mapped_column(Date, nullable=False)

    # Gästinfo (kan vara tomt för blocks)
    guest_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    guest_email: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    num_guests: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    num_adults: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    num_children: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    num_infants: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    confirmation_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)

    # Källa och status
    source: Mapped[str] = mapped_column(String(50), nullable=False, default="airbnb")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    manually_overridden: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Ekonomi (fylls i manuellt eller från rapporter)
    gross_revenue: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    norli_cut: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)

    # Metadata
    synced_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def __repr__(self) -> str:
        return f"<Booking id={self.id} check_in={self.check_in} guest={self.guest_name!r}>"

class OwnerPeriod(Base):
    """
    Manuellt inmatat förvaltningsfönster — period då ägaren disponerar objektet.
    
    Används av serviceteam-sidan för att:
    1. Skjuta upp städfönstrets start till period_end (ägaren lämnar)
    2. Flagga gapet med rätt label ("Ägarperiod") i stället för tomt fönster
    3. Trigga AI-fråga om städning behövs och när
    
    En period kan sträcka sig över flera bokningar och säsonger.
    label: fritext, t.ex. "Ägarna hemma jul/nyår", "Peters sommarvistelse"
    cleaning_needed: om Norli ska städa när perioden slutar (default True)
    cleaning_from: om satt, styr när städfönstret öppnar (annars period_end)
    """
    __tablename__ = "owner_periods"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    property_id: Mapped[int] = mapped_column(Integer, ForeignKey("properties.id"), nullable=False)
    
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    
    label: Mapped[str] = mapped_column(String(200), nullable=False, default="Ägarperiod")
    cleaning_needed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # Om satt: städfönstret öppnar denna dag (override av period_end)
    cleaning_from: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    
    __table_args__ = (
        UniqueConstraint("property_id", "period_start", name="uq_owner_period_prop_start"),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Städuppdragens tillstånd (persistens för städportalen)
#
# Själva städjobben härleds deterministiskt i frontend från bokningar och
# ägarperioder. Denna tabell lagrar det som INTE kan härledas och som tidigare
# bara levde i React-state (och försvann vid reload): bekräftelse, tilldelning,
# planerat slot, gästklar-status, flaggor, estimat, ändringsbegäran och historik.
#
# Nyckeln är job_key: en stabil sträng som frontend bygger. Rekommendation är att
# binda den till inkommande bokningens ical_uid när sådan finns ("gör klart inför
# DENNA gäst"), så att tillståndet överlever att andra bokningar ändras.
# ─────────────────────────────────────────────────────────────────────────────



class Owner(Base):
    """
    Fastighetsägare. Skapas manuellt eller via AI-extraktion av PDF-avtal.
    En ägare kan ha flera objekt (Property).
    """
    __tablename__ = "owners"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Personuppgifter
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    personal_id: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)   # personnr eller orgnr
    phone: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    address: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)

    # Ekonomi
    bank_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    bank_account: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)   # clearing + konto
    bank_iban: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Försäkring
    insurance_company: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    insurance_valid_until: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    # Anteckningar
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    contracts: Mapped[list["Contract"]] = relationship("Contract", back_populates="owner")

    def __repr__(self) -> str:
        return f"<Owner id={self.id} name={self.name!r}>"


class Contract(Base):
    """
    Avtal mellan Norli och en fastighetsägare, kopplat till ett objekt.
    Skapas via PDF-uppladdning med AI-extraktion eller manuellt.
    """
    __tablename__ = "contracts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_id: Mapped[int] = mapped_column(Integer, ForeignKey("owners.id"), nullable=False)
    crm_property_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # koppling till Property

    # Ekonomiska villkor (extraherade ur avtalet)
    owner_share_pct: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 4), nullable=True)   # ex 0.80
    norli_share_pct: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 4), nullable=True)    # ex 0.20
    cost_mandate_sek: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)  # utan förhandsgodkännande

    # Avtalstid
    start_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)       # None = tillsvidare
    notice_months: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    # Status
    # draft|active|terminated
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")

    # Dokumentreferens (filnamn eller URL till sparad PDF)
    document_filename: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    document_uploaded_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # AI-extraktion
    extracted_by_ai: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    extraction_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    extraction_raw_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # rådata från Claude

    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    owner: Mapped["Owner"] = relationship("Owner", back_populates="contracts")

    def __repr__(self) -> str:
        return f"<Contract id={self.id} owner_id={self.owner_id} status={self.status!r}>"

class CleaningJobState(Base):
    """Persistent tillstånd för ett härlett städuppdrag."""
    __tablename__ = "cleaning_job_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_key: Mapped[str] = mapped_column(String(200), unique=True, nullable=False, index=True)

    # Kontext (denormaliserat för spårbarhet och orphan-detektion)
    crm_property_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    property_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("properties.id"), nullable=True)
    job_type: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)  # turnover|prep|final|no_bedding
    incoming_ical_uid: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    outgoing_ical_uid: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    window_start: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    window_end: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Huvudstatus (städuppdragets status) — skild från flaggor och gästklar-status
    # unassigned|assigned|confirmed|in_progress|done|aborted|replaced
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="unassigned")

    # Tilldelning
    assigned_company: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    assigned_to: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Planerat städslot (start, slut, senast gästklar)
    confirmed_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    confirmed_start: Mapped[Optional[str]] = mapped_column(String(5), nullable=True)  # "HH:MM"
    confirmed_end: Mapped[Optional[str]] = mapped_column(String(5), nullable=True)    # "HH:MM"
    latest_ready: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Gästklar-status — objektets operativa sanning, skild från uppdragsstatus
    # not_checked|cleaning_needed|cleaning_planned|cleaning_confirmed|in_progress|
    # cleaning_done|done_with_deviation|blocked|guest_ready|guest_checked_in
    readiness_status: Mapped[str] = mapped_column(String(30), nullable=False, default="not_checked")

    # Flaggor (JSON-lista av flaggkoder, t.ex. ["urgent","blocking_deviation"])
    flags: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Uppskattad städtid (estimat i timmar, skilt från planerat klockslag)
    estimated_hours: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2), nullable=True)
    # default|actual|manual
    estimated_hours_source: Mapped[str] = mapped_column(String(20), nullable=False, default="default")
    estimated_hours_overridden_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    estimated_hours_overridden_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    estimated_hours_original: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2), nullable=True)
    actual_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Bäddning (max kontra faktisk grupp)
    bedding_mode: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # max|actual
    bedding_for_guests: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    outgoing_guests: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # Manuellt: antal som checkade ut (auto-fylls av Airbnb-API framöver)

    # Anteckningar
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Ändringsbegäran efter bekräftelse (kräver Norli-godkännande, akutväg finns)
    # none|pending|approved|rejected
    change_status: Mapped[str] = mapped_column(String(20), nullable=False, default="none")
    change_requested_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    change_requested_start: Mapped[Optional[str]] = mapped_column(String(5), nullable=True)
    change_requested_assignee: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    change_is_urgent: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    change_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Tidsstämplar
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def __repr__(self) -> str:
        return f"<CleaningJobState job_key={self.job_key!r} status={self.status!r}>"


class CleaningAuditLog(Base):
    """Spårbarhetslogg för städuppdrag. Varje väsentlig händelse loggas."""
    __tablename__ = "cleaning_audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_key: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    event: Mapped[str] = mapped_column(String(50), nullable=False)
    actor: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    actor_role: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    detail: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self) -> str:
        return f"<CleaningAuditLog job_key={self.job_key!r} event={self.event!r}>"
