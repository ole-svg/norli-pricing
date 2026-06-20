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
    last_minute_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Antal dagar innan incheckningsdatum dar rabatten borjar
    last_minute_start_days: Mapped[int] = mapped_column(Integer, nullable=False, default=20)

    # Maximal rabatt i procent (t.ex. 0.20 = 20% rabatt sista dagen)
    last_minute_max_discount: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False, default=Decimal("0.20"))

    # Minimum pris efter last-minute-rabatt (skyddsracke)
    # Om None anvands ekonomikalkylatorn for att rakna ut minimum lonsamt pris
    last_minute_min_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)

    base_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    pricing_strategy: Mapped[str] = mapped_column(String(50), nullable=False, default="balanced")

    # Skyddsracken
    price_floor: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    price_ceiling: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    min_margin: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    min_owner_net: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)

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

