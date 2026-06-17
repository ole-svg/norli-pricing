import os
from fastapi import FastAPI

app = FastAPI()

@app.get("/health")
def health():
    return {"status": "ok", "db_url_set": "DATABASE_URL" in os.environ}

@app.get("/env")
def env():
    return {k: v for k, v in os.environ.items() if "RAILWAY" in k or "DATABASE" in k or "PORT" in k}
