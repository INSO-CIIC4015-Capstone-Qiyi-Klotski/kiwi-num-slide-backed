from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import auth_router, health_router, users_router, puzzles_router

app = FastAPI(title="three-tier BE")

origins = [
    "http://localhost:3000",
    "https://janieljoelnunezquintana.com",
    "https://www.janieljoelnunezquintana.com",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Registrar rutas
app.include_router(health_router)  # primero, para el health check
app.include_router(auth_router)
app.include_router(users_router.router)
app.include_router(puzzles_router.router)