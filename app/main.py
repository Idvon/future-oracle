from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.api import events as events_api
from app.api import meta as meta_api
from app.config import settings
from app.database import get_db, init_db
from app.scheduler import shutdown_scheduler, start_scheduler
from app.storage import repository

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


def _prob_class(value: float) -> str:
    if value >= 0.6:
        return "high"
    if value <= 0.4:
        return "low"
    return "mid"


templates.env.filters["pct_class"] = _prob_class


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    if settings.enable_scheduler:
        start_scheduler()
    yield
    shutdown_scheduler()


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
app.include_router(events_api.router, prefix="/api")
app.include_router(meta_api.router, prefix="/api")


@app.get("/", response_class=HTMLResponse)
def index(request: Request, q: str = "", db: Session = Depends(get_db)):
    query = q.strip()
    if query:
        events = repository.search_events(db, query)
    else:
        events = repository.list_events(db, status="active")
    cards = [
        {"event": event, "prediction": repository.latest_prediction(db, event.id)}
        for event in events
    ]
    return templates.TemplateResponse(request, "index.html", {"cards": cards, "q": query})


@app.get("/events/{event_id}", response_class=HTMLResponse)
def event_page(request: Request, event_id: int, db: Session = Depends(get_db)):
    event = repository.get_event(db, event_id)
    if event is None:
        return HTMLResponse("<h1>Event not found</h1>", status_code=404)
    prediction = repository.latest_prediction(db, event_id)
    raw_records = repository.list_raw_records(db, event_id)
    return templates.TemplateResponse(
        request,
        "prediction.html",
        {
            "event": event,
            "prediction": prediction,
            "raws": raw_records,
        },
    )


@app.get("/accuracy", response_class=HTMLResponse)
def accuracy_page(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse(
        request, "accuracy.html", {"rows": repository.list_resolutions(db)}
    )


@app.get("/sources", response_class=HTMLResponse)
def sources_page(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse(
        request, "sources.html", {"sources": repository.list_sources(db)}
    )
