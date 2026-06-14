"""
Norli Pricing Engine — API

Exponerar prissättningsmotorn via HTTP.
Andra system (CRM, ägarportal, Airbnb-adapter) pratar med motorn härifrån.
De läser aldrig direkt från databasen — alltid via detta API.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api import properties, prices, rules, health, economy

app = FastAPI(
    title="Norli Pricing Engine",
    description="Dynamisk prissättningsmotor för Norli Stay AB",
    version="1.0.0",
)

# CORS — tillåter anrop från webbläsare (t.ex. ägarportal)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Begränsa i produktion
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Registrera routes (endpoints) från varje modul
app.include_router(health.router, tags=["Hälsokontroll"])
app.include_router(properties.router, prefix="/properties", tags=["Objekt"])
app.include_router(prices.router, prefix="/prices", tags=["Priser"])
app.include_router(rules.router, prefix="/rules", tags=["Prisregler"])
app.include_router(economy.router, prefix="/economy", tags=["Ekonomi"])
