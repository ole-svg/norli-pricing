from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os
"""
Norli Pricing Engine — API

Exponerar prissättningsmotorn via HTTP.
Andra system (CRM, ägarportal, Airbnb-adapter) pratar med motorn härifrån.
De läser aldrig direkt från databasen — alltid via detta API.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api import properties, prices, rules, health, economy, publish, jobs, categories, ai_events, events_api

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
app.include_router(publish.router, prefix="/publish", tags=["Publicering"])
app.include_router(jobs.router, prefix="/jobs", tags=["Jobb"])
app.include_router(categories.router, prefix="/categories", tags=["Kategorier"])
app.include_router(ai_events.router, prefix="/ai/events", tags=["AI Evenemang"])
app.include_router(events_api.router, tags=["Evenemang"])

# Setup-endpoints (maste ligga fore static files mount)
@app.post("/setup/seed")
def run_seed():
    import subprocess
    result = subprocess.run(["python", "scripts/seed.py"], capture_output=True, text=True, cwd="/app")
    return {"stdout": result.stdout, "stderr": result.stderr, "returncode": result.returncode}

@app.post("/setup/seed-events")
def run_seed_events():
    import subprocess
    result = subprocess.run(["python", "scripts/seed_events_2026_2027.py"], capture_output=True, text=True, cwd="/app")
    return {"stdout": result.stdout, "stderr": result.stderr, "returncode": result.returncode}

# Admin-panel (maste ligga sist)
admin_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "admin")
if os.path.exists(admin_dir):
    app.mount("/admin", StaticFiles(directory=admin_dir, html=True), name="admin")
