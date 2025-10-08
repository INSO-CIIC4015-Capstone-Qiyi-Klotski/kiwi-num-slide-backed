# app/routers/health_router.py
from fastapi import APIRouter

router = APIRouter(tags=["health"])

@router.get("/health", include_in_schema=False)
def health():
    # Respuesta súper rápida, sin DB
    return {"status": "ok"}

@router.get("/", include_in_schema=False)
def root():
    # Útil para probar rápido que el contenedor está vivo
    return {"ok": True}