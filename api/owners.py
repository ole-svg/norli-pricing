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

@router.post("/extract-contract")
async def extract_contract(file: UploadFile = File(...)):
    """
    Ta emot en PDF, skicka till Claude API och returnera extraherad data.
    Frontend visar resultatet för bekräftelse innan något sparas.
    """
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Endast PDF-filer stöds")

    pdf_bytes = await file.read()
    pdf_b64 = base64.b64encode(pdf_bytes).decode()

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY saknas i miljövariabler")

    extraction_prompt = """Du är ett system som extraherar strukturerad data från svenska hyres- och driftavtal för korttidsuthyrning.

Avtalet har typiskt ett huvuddokument och bilagor. Bilaga 1 (Objektsbilaga) innehåller den viktigaste strukturerade informationen.

Extrahera följande fält och returnera ENBART ett JSON-objekt, inga förklaringar eller markdown:

{
  "owner_name": "ägarens fullständiga namn",
  "personal_id": "personnummer eller organisationsnummer (utan bindestreck om möjligt)",
  "phone": "telefonnummer",
  "email": "e-postadress",
  "property_address": "objektets adress inklusive postnummer och ort",
  "property_type": "objektstyp (villa, lägenhet, fritidshus etc)",
  "max_guests": antal gäster som heltal eller null,
  "bedrooms": antal sovrum som heltal eller null,
  "owner_share_pct": ägarens andel som decimal 0-1 (ex 0.80 för 80%) eller null,
  "norli_share_pct": Norlis andel som decimal 0-1 (ex 0.20 för 20%) eller null,
  "bank_name": "bankens namn",
  "bank_account": "clearing- och kontonummer som en sträng",
  "cost_mandate_sek": beloppsgräns utan förhandsgodkännande som tal eller null,
  "insurance_company": "försäkringsbolag",
  "pets_allowed": true/false/null,
  "access_type": "accesslösning (nyckelbox, kodlås etc)",
  "start_date": "YYYY-MM-DD eller null",
  "notes": "övriga viktiga noteringar från avtalet"
}

Om ett fält inte finns i avtalet, sätt det till null. Returnera alltid giltig JSON."""

    payload = {
        "model": "claude-sonnet-4-6",
        "max_tokens": 1000,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "document",
                        "source": {
                            "type": "base64",
                            "media_type": "application/pdf",
                            "data": pdf_b64
                        }
                    },
                    {
                        "type": "text",
                        "text": extraction_prompt
                    }
                ]
            }
        ]
    }

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=json.dumps(payload).encode(),
        method="POST",
        headers={
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        }
    )

    try:
        with urllib.request.urlopen(req) as r:
            response = json.loads(r.read())
        raw_text = response["content"][0]["text"].strip()
        # Rensa eventuella markdown-backticks
        if raw_text.startswith("```"):
            raw_text = raw_text.split("\n", 1)[1]
            raw_text = raw_text.rsplit("```", 1)[0]
        extracted = json.loads(raw_text)
        return {
            "success": True,
            "filename": file.filename,
            "extracted": extracted,
            "raw_response": raw_text
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Extraktion misslyckades: {str(e)}")


@router.post("/confirm-extraction")
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
