# Norli Pricing Engine

Dynamisk prissättningsmotor för Norli Stay AB. Hanterar korttidsuthyrning på Airbnb och Booking.com.

---

## Förstå projektet på 2 minuter

```
norli-pricing/
│
├── db/               ← Databas: tabeller och anslutning
│   ├── models.py     ← Alla tabeller (Property, Season, PriceSnapshot...)
│   └── session.py    ← Databasanslutning
│
├── engine/           ← HJÄRTAT: Den deterministiska regelmotorn
│   └── pricing.py    ← Räknar ut priser, steg för steg
│
├── api/              ← HTTP API — så andra system pratar med motorn
│   ├── main.py       ← API-servern
│   ├── properties.py ← Endpoints för objekt
│   ├── prices.py     ← Endpoints för priser
│   └── rules.py      ← Endpoints för prisregler
│
├── scripts/
│   └── seed.py       ← Skapar tabeller + lägger in testdata (Enskede)
│
├── tests/
│   └── test_engine.py ← Automatiska tester för regelmotorn
│
├── docker-compose.yml ← Startar PostgreSQL + API med ett kommando
└── requirements.txt   ← Python-paket som behövs
```

---

## Installera verktygen (gör en gång)

### 1. Git
```bash
# Mac
brew install git

# Windows: ladda ner från https://git-scm.com/download/win
```

### 2. Docker Desktop
Ladda ner från: https://www.docker.com/products/docker-desktop/

Starta Docker Desktop och vänta tills ikonen slutar snurra.

### 3. Python (behövs bara för tester lokalt)
```bash
# Mac
brew install python@3.12

# Windows: ladda ner från https://python.org
```

---

## Kom igång (gör varje ny session)

### Steg 1: Starta databasen och API:et
```bash
cd norli-pricing
docker-compose up --build
```

Du borde se något i stil med:
```
norli_api  | INFO: Uvicorn running on http://0.0.0.0:8000
```

### Steg 2: Initiera databasen (bara första gången)
Öppna ett nytt terminalfönster:
```bash
cd norli-pricing
docker-compose exec api python scripts/seed.py
```

Du borde se:
```
✓ Tabeller skapade
✓ Enskedevägen 79 skapad (id=1)
✓ 5 säsonger skapade
✓ 7 kalenderhändelser skapade
✓ 2 lokala evenemang skapade
✓ Allt klart! Databasen är redo.
```

### Steg 3: Testa att allt funkar

Öppna i webbläsaren: http://localhost:8000/health

Du bör se:
```json
{"status": "ok", "service": "norli-pricing-engine", "version": "1.0.0"}
```

### Steg 4: Räkna ut priser för Enskede
```bash
curl -X POST "http://localhost:8000/prices/enskede-79/recalculate"
```

### Steg 5: Se priserna
```bash
curl "http://localhost:8000/prices/enskede-79?start_date=2026-06-01&end_date=2026-06-07"
```

### Utforska API-dokumentationen
Öppna: http://localhost:8000/docs

Här kan du testa alla endpoints direkt i webbläsaren — inga kommandon behövs.

---

## Kör testerna
```bash
docker-compose exec api pytest tests/ -v
```

---

## Stoppa allt
```bash
docker-compose down
```

Vill du radera databasen helt och börja om:
```bash
docker-compose down -v
```

---

## Vanliga frågor

**Vad är Docker?**
Docker låter dig köra PostgreSQL och API:et i isolerade "containrar" utan att installera något på din dator. `docker-compose up` startar allt med ett kommando.

**Vad är ett API?**
API (Application Programming Interface) är ett sätt för program att prata med varandra. Vår motor exponerar sina funktioner via HTTP (samma protokoll som webbläsare använder). CRM, ägarportal och Airbnb-adaptern anropar API:et — de läser aldrig direkt från databasen.

**Vad är deterministisk?**
Det betyder att samma input alltid ger samma output. Om du räknar ut priset för 15 juni 2026 idag och imorgon, med samma regler, ska du alltid få exakt samma svar. Det gör systemet testbart och förklarbart.

**Hur ändrar jag grundpriset för Enskede?**
```bash
curl -X PATCH "http://localhost:8000/properties/enskede-79" \
  -H "Content-Type: application/json" \
  -d '{"base_price": 3000}'
```
Trigga sedan omräkning: `curl -X POST "http://localhost:8000/prices/enskede-79/recalculate"`
