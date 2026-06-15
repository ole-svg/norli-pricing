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
