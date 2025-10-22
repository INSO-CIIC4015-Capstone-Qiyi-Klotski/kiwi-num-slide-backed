import os
from sched import scheduler
from zoneinfo import ZoneInfo

from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import auth_router, health_router, users_router, puzzles_router
from app.services import puzzle_generation, puzzle_service

from apscheduler.schedulers.background import BackgroundScheduler

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


scheduler: BackgroundScheduler | None = None

def daily_puzzle_job():
    info = puzzle_service.ensure_daily_puzzle_for_today(auto_generate_fallback=True)
    print(f"🧩 Daily publish: {info}")


@app.on_event("startup")
def start_scheduler():
    global scheduler
    tz = ZoneInfo(os.getenv("DAILY_TZ", "UTC"))  # p.ej. America/Puerto_Rico
    scheduler = BackgroundScheduler(timezone=tz)

    # Corre cada día a las 00:05 (primeros minutos del día local)
    scheduler.add_job(
        daily_puzzle_job,
        CronTrigger(hour=6, minute=0, timezone=tz),
        id="daily_publisher",
        replace_existing=True,
        max_instances=1,        # evita solapes
        coalesce=True,          # si se salta una ejecución, combina en una sola
        misfire_grace_time=3600,# 1h de gracia si el proceso estuvo dormido
        jitter=60,              # aleatoriza ±60s para evitar thundering herd
    )

    scheduler.start()

    # Log útil para verificar próxima corrida
    next_run = scheduler.get_job("daily_publisher").next_run_time
    print(f"🕛 Daily publisher programado: {next_run.astimezone(tz)} [{tz.key}]")

@app.on_event("shutdown")
def stop_scheduler():
    if scheduler:
        scheduler.shutdown(wait=False)