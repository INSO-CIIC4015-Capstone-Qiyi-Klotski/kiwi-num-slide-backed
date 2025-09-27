from fastapi import FastAPI
from .db import ping_db
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="three-tier BE")

# Orígenes permitidos (añade tu dominio del FE en producción)
origins = [
    "http://localhost:3000",
    "https://www.janieljoelnunezquintana.com/",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,         # para dev puedes usar ["*"] (sin credenciales)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {"message": "Hello from FastAPI on EB via ECR (port 80)! Commit para trigger los deploy action"}

@app.get("/health")
def health():
    return {"ok": True}

@app.get("/db-ping")
def db_ping():
    return {"db": "ok" if ping_db() else "down"}

