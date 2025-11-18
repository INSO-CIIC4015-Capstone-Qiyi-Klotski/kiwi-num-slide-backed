import os
from contextlib import asynccontextmanager
from zoneinfo import ZoneInfo

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.routers import auth_router, health_router, users_router, puzzles_router
from app.services import puzzle_service

def daily_puzzle_job():
    info = puzzle_service.ensure_daily_puzzle_for_today(auto_generate_fallback=True)
    print(f"🧩 Daily publish: {info}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    disable = os.getenv("DISABLE_SCHEDULER") == "1" or os.getenv("TESTING") == "1"
    scheduler = None

    if not disable:
        tz = ZoneInfo(os.getenv("DAILY_TZ", "UTC"))
        scheduler = BackgroundScheduler(timezone=tz)
        scheduler.add_job(
            daily_puzzle_job,
            CronTrigger(hour=6, minute=0, timezone=tz),  # ajusta la hora que quieras
            id="daily_publisher",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
            misfire_grace_time=3600,
            jitter=60,
        )
        scheduler.start()
        next_run = scheduler.get_job("daily_publisher").next_run_time
        print(f"🕛 Daily publisher programado: {next_run.astimezone(tz)} [{tz.key}]")

    app.state.scheduler = scheduler
    try:
        yield
    finally:
        sched = getattr(app.state, "scheduler", None)
        if sched:
            sched.shutdown(wait=False)


app = FastAPI(title="three-tier BE", lifespan=lifespan)

# CORS, etc.
origins = [
    "http://localhost:3000",
    "https://janieljoelnunezquintana.com",
    "https://www.janieljoelnunezquintana.com",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex=r"https://.*\.trycloudflare\.com",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(health_router)
app.include_router(auth_router)
app.include_router(users_router.router)
app.include_router(puzzles_router.router)
