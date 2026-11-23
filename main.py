import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from bgs_client import BgsClient
from config import settings
from database import latest_num_qa
from sync import SyncService

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

service = SyncService(BgsClient(), latest_num_qa)


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler = None
    if settings.sync_enabled:
        scheduler = BackgroundScheduler(timezone="UTC")
        # max_instances=1 + coalesce: wolny Eclipse nie zdubluje odpytań, zaległe uruchomienia nie nadrabiają się seriami.
        # Pierwsze odpytanie od razu po starcie, potem co SYNC_INTERVAL_SECONDS.
        scheduler.add_job(service.run_once, "interval", seconds=settings.sync_interval_seconds, id="eclipse_num_qa",
                          max_instances=1, coalesce=True, next_run_time=datetime.now(timezone.utc))
        scheduler.start()
    yield
    if scheduler:
        scheduler.shutdown(wait=False)
    service.bgs.close()


app = FastAPI(title="BGS UR Eclipse Sync", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    """Stan ostatniego odpytania. status: ok | error | starting."""
    state = service.state
    if state.runs == 0:
        status = "starting"
    elif state.last_error:
        status = "error"
    else:
        status = "ok"
    return {"status": status, "interval_seconds": settings.sync_interval_seconds,
            "scheduler_enabled": settings.sync_enabled, **state.as_dict()}


@app.post("/sync/run")
def run_now():
    """Odpytanie natychmiast (np. po dodaniu kanału w panelu) – bez czekania na harmonogram."""
    return service.run_once().as_dict()
