# Norli Pricing — Backend

## Projekt
FastAPI-backend för Norli Stay AB:s CRM och prissättningssystem.

## Stack
- FastAPI + SQLAlchemy + PostgreSQL
- Deploy: Railway (norli-pricing-production.up.railway.app)
- Repo: ole-svg/norli-pricing

## Kritiska lärdomar
- Railway redeploy: uppdatera requirements.txt med "# cache-bust: {timestamp}" om auto-deploy inte triggar
- FastAPI route-ordning: specifika routes (/contract/extract) FÖRE parametriska (/{owner_id})
- SQLAlchemy schema-cache: använd raw SQL för kolumner tillagda efter deploy
- CORS-fel maskerar 500-fel: kolla Railway runtime-loggar för Python-traceback
- Miljövariabler: wrappa token-läsningar i funktion, inte på modulnivå

## Viktiga endpoints
- GET /properties/ — lista alla aktiva objekt (raw SQL)
- GET /properties/{crm_property_id} — hämta objekt (raw SQL)
- PATCH /properties/{crm_property_id} — uppdatera objekt (raw SQL)
- POST /onboarding — skapa nytt objekt
- GET /onboarding/cleaning-companies — städbolag
- GET /onboarding/pricing-profiles — prisprofiler
- GET /onboarding/owners-list — befintliga ägare
- POST /owners/contract/extract — extrahera PDF-avtal med pypdf + regex
- POST /owners/contract/confirm — spara som Owner + Contract
- POST /setup/fix-schema — kör databasmigration

## Databasmodeller
- Property — objekt med prissättning, städkonfiguration, ekonomimodell
- Owner — fastighetsägare med kontaktinfo och bankuppgifter
- Contract — avtal kopplat till Owner + Property
- CleaningJobState — städjobb med status

## Ekonomimodell
Brutto -> -Airbnb 3% -> -Logimoms 12/112 -> Avräkningsbas
x Ägare 80% / Norli 20% (varierar per avtal)
- Städ 500 kr/h, objektkostnad 200 kr/bokning
= Ägarens netto (avrundning närmaste 10 SEK)

## Städbolag
- Hustrend Sverige AB — Stockholm + Trosa
- Plus55 — Ronneby
- Buskhaga Städ — Klassbol
- Sam Kiander — Oxelösund

## Avtalsextraktion (PDF)
Regex-baserad, ingen Anthropic API. Extraherar ur Norlis standardavtal Bilaga 1:
- Namn, personnr, telefon, e-post, adress, objektstyp
- Max gäster, sovrum, ägarandel, Norlis andel
- Bank, kontonummer, kostnadsmandat, försäkringsbolag
- Husdjur, accesslösning, uppsägningstid

## Git
git add -A && git commit -m "beskrivning" && git push origin main
Railway deploar automatiskt — om inte, cache-bust i requirements.txt.
