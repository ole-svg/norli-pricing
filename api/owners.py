"""
API-endpoints för Owner och Contract.
Inkluderar PDF-uppladdning med AI-extraktion via Claude API.
"""

import base64
import json
import os
import urllib.request
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from db.session import get_db
from db.models import Owner, Contract

router = APIRouter(prefix="/owners", tags=["owners"])


# ─── Pydantic-scheman ────────────────────────────────────────────────────────

class OwnerCreate(BaseModel):
    name: str
    personal_id: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    bank_name: Optional[str] = None
    bank_account: Optional[str] = None
    bank_iban: Optional[str] = None
    insurance_company: Optional[str] = None
    insurance_valid_until: Optional[date] = None
    notes: Optional[str] = None

class OwnerUpdate(BaseModel):
    name: Optional[str] = None
    personal_id: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    bank_name: Optional[str] = None
    bank_account: Optional[str] = None
    bank_iban: Optional[str] = None
    insurance_company: Optional[str] = None
    insurance_valid_until: Optional[date] = None
    notes: Optional[str] = None

class ContractCreate(BaseModel):
    owner_id: int
    crm_property_id: Optional[str] = None
    owner_share_pct: Optional[float] = None
    norli_share_pct: Optional[float] = None
    cost_mandate_sek: Optional[float] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    notice_months: int = 1
    status: str = "active"
    notes: Optional[str] = None

class ExtractionConfirm(BaseModel):
    """Skickas från frontend när användaren bekräftar AI-extraktionen."""
    owner_data: OwnerCreate
    contract_data: ContractCreate
    document_filename: str


# ─── Owner-endpoints ─────────────────────────────────────────────────────────

@router.get("")
def list_owners(db: Session = Depends(get_db)):
    owners = db.query(Owner).filter(Owner.is_active == True).order_by(Owner.name).all()
    return [_owner_to_dict(o) for o in owners]


@router.get("/{owner_id}")
def get_owner(owner_id: int, db: Session = Depends(get_db)):
    owner = db.query(Owner).filter(Owner.id == owner_id).first()
    if not owner:
        raise HTTPException(status_code=404, detail="Owner not found")
    result = _owner_to_dict(owner)
    result["contracts"] = [_contract_to_dict(c) for c in owner.contracts]
    return result


@router.post("")
def create_owner(data: OwnerCreate, db: Session = Depends(get_db)):
    owner = Owner(**data.model_dump())
    db.add(owner)
    db.commit()
    db.refresh(owner)
    return _owner_to_dict(owner)


@router.patch("/{owner_id}")
def update_owner(owner_id: int, data: OwnerUpdate, db: Session = Depends(get_db)):
    owner = db.query(Owner).filter(Owner.id == owner_id).first()
    if not owner:
        raise HTTPException(status_code=404, detail="Owner not found")
    for k, v in data.model_dump(exclude_none=True).items():
        setattr(owner, k, v)
    db.commit()
    db.refresh(owner)
    return _owner_to_dict(owner)


# ─── Contract-endpoints ───────────────────────────────────────────────────────

@router.get("/{owner_id}/contracts")
def list_contracts(owner_id: int, db: Session = Depends(get_db)):
    contracts = db.query(Contract).filter(Contract.owner_id == owner_id).all()
    return [_contract_to_dict(c) for c in contracts]


@router.post("/{owner_id}/contracts")
def create_contract(owner_id: int, data: ContractCreate, db: Session = Depends(get_db)):
    contract = Contract(**data.model_dump())
    contract.owner_id = owner_id
    db.add(contract)
    db.commit()
    db.refresh(contract)
    return _contract_to_dict(contract)


# ─── PDF-extraktion med Claude API ───────────────────────────────────────────

@router.post("/contract/extract")
async def extract_contract(file: UploadFile = File(...)):
    """
    Extraherar ägardata ur Norlis standardavtal (Bilaga 1) via regelbaserad parsning.
    Ingen AI-API krävs.
    """
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Endast PDF-filer stöds")

    pdf_bytes = await file.read()

    try:
        import io
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(pdf_bytes))
        pdf_text = "\n".join(page.extract_text() or "" for page in reader.pages)
        pdf_text = pdf_text.encode("utf-8", errors="ignore").decode("utf-8")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Kunde inte läsa PDF: {str(e)}")

    if not pdf_text.strip():
        raise HTTPException(status_code=400, detail="PDF:en verkar vara tom eller skannad utan OCR")

    import re as rx

    def f(pattern, text, g=1):
        m = rx.search(pattern, text, rx.IGNORECASE | rx.MULTILINE)
        try:
            return m.group(g).strip() if m else None
        except Exception:
            return None

    t = pdf_text

    # Hitta Bilaga 1-sektionen specifikt
    bilaga1_idx = t.find("Bilaga 1")
    bilaga1 = t[bilaga1_idx:] if bilaga1_idx >= 0 else t

    # NAMN: "Fastighetsägarens namn [Förnamn Efternamn]" — stoppa före "Personnr"
    owner_name = f(r"Fastighets.?garens namn\s+([A-ZÅÄÖ][a-zåäö]+(?:\s[A-ZÅÄÖ][a-zåäö]+)+)\s+Personnr", bilaga1)
    if not owner_name:
        owner_name = f(r"Fastighets.?garens namn\s+([A-ZÅÄÖ][a-zåäö]+(?: [A-ZÅÄÖ][a-zåäö]+)+)", bilaga1)

    # PERSONNR: 6 siffror + bindestreck + 4 siffror, men INTE Norlis 559553-5120
    personal_id = f(r"Personnr/org\.nr\s+(\d{6}[-–]\d{4})", bilaga1)

    # TELEFON: stoppa före "E-post"
    phone_raw = f(r"Telefon\s+((?:\+46|0)\d[\d\s]{6,13}?)\s+E-post", bilaga1)
    if not phone_raw:
        phone_raw = f(r"Telefon\s+((?:\+46|0)[\d\s]{8,14})", bilaga1)
    phone = phone_raw.strip() if phone_raw else None

    # E-POST: ägaren, inte kontakt@norli.se — ta den som INTE är norli.se
    emails = rx.findall(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", bilaga1)
    email = next((e for e in emails if "norli.se" not in e), None)

    # ADRESS: leta i Bilaga 1 direkt efter "Adress" men inte "anges i Bilaga"
    property_address = f(r"Adress\s+([A-ZÅÄÖ][a-zåäö].{5,50}\d{3}\s*\d{2}\s*\S+)", bilaga1)

    # OBJEKTSTYP: stoppa vid "Max antal"
    property_type = f(r"Objektstyp\s+(Villa(?:\s+med\s+\S+)?|Lägenhet|Fritidshus|Stuga|Radhus)\s+Max", bilaga1)
    if not property_type:
        property_type = f(r"Objektstyp\s+(Villa|Lägenhet|Fritidshus|Stuga|Radhus)", bilaga1)

    # MAX GÄSTER
    max_guests_raw = f(r"Max antal g.?ster\s+(\d+)", bilaga1)
    max_guests = int(max_guests_raw) if max_guests_raw else None

    # SOVRUM
    bedrooms_raw = f(r"Antal sovrum\s+(\d+)", bilaga1)
    bedrooms = int(bedrooms_raw) if bedrooms_raw else None

    # ÄGARANDEL: ta första % i Bilaga 1
    pcts = rx.findall(r"(\d+)%", bilaga1)
    owner_share_pct = float(pcts[0]) / 100 if pcts else None
    norli_share_pct = float(pcts[1]) / 100 if len(pcts) > 1 else None

    # BANK: ta bara banknamnet, inte ", Sverige"
    bank_raw = f(r"Bank och land\s+(\S+)", bilaga1)
    bank_name = bank_raw.rstrip(",") if bank_raw else None

    # KONTONUMMER: siffror efter "kontonummer"
    bank_account = f(r"kontonummer\s+(\d{6,15})", bilaga1)

    # KOSTNADSMANDAT
    mandate_raw = f(r"Upp till\s+([\d\s]+)\s*SEK", bilaga1)
    cost_mandate = None
    if mandate_raw:
        try:
            cost_mandate = float(rx.sub(r"\s", "", mandate_raw))
        except Exception:
            pass

    # FÖRSÄKRINGSBOLAG: bara namnet
    insurance = f(r"Fastighets.?garens\s+f.?rs.?kringsbolag\s+(L.?nsf.?rs.?kringar|Folksam|If\b|Trygg-Hansa|Moderna|Gjensidige|Ålands)", bilaga1)
    if not insurance:
        insurance = f(r"(L.?nsf.?rs.?kringar|Folksam|Trygg-Hansa|Moderna|Gjensidige)", bilaga1)

    # HUSDJUR
    pets_raw = f(r"Husdjur tillåtet\s+(Ja|Nej)", bilaga1)
    pets_allowed = True if pets_raw and pets_raw.lower() == "ja" else (False if pets_raw else None)

    # ACCESS
    access_type = f(r"Prim.?r accessl.?sning[^\n]*?\s+(Nyckelbox|Kodlås|Kodbricka|Smart lock)", bilaga1)
    if not access_type:
        access_type = f(r"(Nyckelbox|Kodlås)", bilaga1)

    return {
        "success": True,
        "filename": file.filename,
        "extracted": {
            "owner_name": owner_name,
            "personal_id": personal_id,
            "phone": phone,
            "email": email,
            "property_address": property_address,
            "property_type": property_type,
            "max_guests": max_guests,
            "bedrooms": bedrooms,
            "owner_share_pct": owner_share_pct,
            "norli_share_pct": norli_share_pct,
            "bank_name": bank_name,
            "bank_account": bank_account,
            "cost_mandate_sek": cost_mandate,
            "insurance_company": insurance,
            "pets_allowed": pets_allowed,
            "access_type": access_type,
            "start_date": None,
            "notes": None,
        },
        "raw_response": pdf_text
    }

@router.post("/contract/confirm")
def confirm_extraction(data: ExtractionConfirm, db: Session = Depends(get_db)):
    """
    Sparar bekräftad extraktion till databasen.
    Skapar Owner + Contract i en transaktion.
    """
    # Skapa ägaren
    owner = Owner(
        name=data.owner_data.name,
        personal_id=data.owner_data.personal_id,
        phone=data.owner_data.phone,
        email=data.owner_data.email,
        address=data.owner_data.address,
        bank_name=data.owner_data.bank_name,
        bank_account=data.owner_data.bank_account,
        bank_iban=data.owner_data.bank_iban,
        insurance_company=data.owner_data.insurance_company,
        insurance_valid_until=data.owner_data.insurance_valid_until,
        notes=data.owner_data.notes,
    )
    db.add(owner)
    db.flush()  # Få owner.id utan att commita

    # Skapa avtalet
    contract = Contract(
        owner_id=owner.id,
        crm_property_id=data.contract_data.crm_property_id,
        owner_share_pct=data.contract_data.owner_share_pct,
        norli_share_pct=data.contract_data.norli_share_pct,
        cost_mandate_sek=data.contract_data.cost_mandate_sek,
        start_date=data.contract_data.start_date,
        end_date=data.contract_data.end_date,
        notice_months=data.contract_data.notice_months,
        status=data.contract_data.status,
        notes=data.contract_data.notes,
        document_filename=data.document_filename,
        document_uploaded_at=datetime.utcnow(),
        extracted_by_ai=True,
        extraction_confirmed=True,
    )
    db.add(contract)
    db.commit()
    db.refresh(owner)

    return {
        "success": True,
        "owner_id": owner.id,
        "contract_id": contract.id,
        "owner": _owner_to_dict(owner)
    }


# ─── Setup: skapa tabeller ────────────────────────────────────────────────────

@router.post("/setup/migrate")
def migrate_owners(db: Session = Depends(get_db)):
    """Kör CREATE TABLE IF NOT EXISTS för owners och contracts."""
    db.execute(text("""
        CREATE TABLE IF NOT EXISTS owners (
            id SERIAL PRIMARY KEY,
            name VARCHAR(200) NOT NULL,
            personal_id VARCHAR(20),
            phone VARCHAR(30),
            email VARCHAR(200),
            address VARCHAR(300),
            bank_name VARCHAR(100),
            bank_account VARCHAR(50),
            bank_iban VARCHAR(50),
            insurance_company VARCHAR(100),
            insurance_valid_until DATE,
            notes TEXT,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
    """))
    db.execute(text("""
        CREATE TABLE IF NOT EXISTS contracts (
            id SERIAL PRIMARY KEY,
            owner_id INTEGER NOT NULL REFERENCES owners(id),
            crm_property_id VARCHAR(100),
            owner_share_pct NUMERIC(5,4),
            norli_share_pct NUMERIC(5,4),
            cost_mandate_sek NUMERIC(10,2),
            start_date DATE,
            end_date DATE,
            notice_months INTEGER NOT NULL DEFAULT 1,
            status VARCHAR(20) NOT NULL DEFAULT 'active',
            document_filename VARCHAR(300),
            document_uploaded_at TIMESTAMPTZ,
            extracted_by_ai BOOLEAN NOT NULL DEFAULT FALSE,
            extraction_confirmed BOOLEAN NOT NULL DEFAULT FALSE,
            extraction_raw_json TEXT,
            notes TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
    """))
    db.commit()
    return {"success": True, "message": "Tabellerna owners och contracts skapade"}


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _owner_to_dict(o: Owner) -> dict:
    return {
        "id": o.id,
        "name": o.name,
        "personal_id": o.personal_id,
        "phone": o.phone,
        "email": o.email,
        "address": o.address,
        "bank_name": o.bank_name,
        "bank_account": o.bank_account,
        "bank_iban": o.bank_iban,
        "insurance_company": o.insurance_company,
        "insurance_valid_until": o.insurance_valid_until.isoformat() if o.insurance_valid_until else None,
        "notes": o.notes,
        "is_active": o.is_active,
        "created_at": o.created_at.isoformat() if o.created_at else None,
    }

def _contract_to_dict(c: Contract) -> dict:
    return {
        "id": c.id,
        "owner_id": c.owner_id,
        "crm_property_id": c.crm_property_id,
        "owner_share_pct": float(c.owner_share_pct) if c.owner_share_pct else None,
        "norli_share_pct": float(c.norli_share_pct) if c.norli_share_pct else None,
        "cost_mandate_sek": float(c.cost_mandate_sek) if c.cost_mandate_sek else None,
        "start_date": c.start_date.isoformat() if c.start_date else None,
        "end_date": c.end_date.isoformat() if c.end_date else None,
        "notice_months": c.notice_months,
        "status": c.status,
        "document_filename": c.document_filename,
        "document_uploaded_at": c.document_uploaded_at.isoformat() if c.document_uploaded_at else None,
        "extracted_by_ai": c.extracted_by_ai,
        "extraction_confirmed": c.extraction_confirmed,
        "notes": c.notes,
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }
