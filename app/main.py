from fastapi import FastAPI
from .db import ping_db

app = FastAPI(title="three-tier BE")

@app.get("/")
def root():
    return {"message": "Hello from FastAPI on EB via ECR (port 80)! Commit para trigger los deploy action"}

@app.get("/health")
def health():
    return {"ok": True}

@app.get("/db-ping")
def db_ping():
    return {"db": "ok" if ping_db() else "down"}

