import logging
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, Query, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse

from app.db import RequestLog, add_request_log, init_db, recent_request_logs, request_log_stats

STATIC_DIR = Path(__file__).parent / "static"

logger = logging.getLogger("uvicorn.error")

LOGGED_PATHS = {"/datetime"}
# The landing page tags its once-a-second polls with this header so they aren't logged.
# Any client can send it, so this is a filter, not access control.
CLIENT_HEADER = "x-truview-client"
LANDING_PAGE_CLIENT = "lcd"


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="truview", lifespan=lifespan)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    from_landing_page = request.headers.get(CLIENT_HEADER) == LANDING_PAGE_CLIENT
    if request.url.path in LOGGED_PATHS and not from_landing_page:
        entry = RequestLog(
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            client_host=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            duration_ms=round((time.perf_counter() - start) * 1000, 2),
        )
        # SQLite calls block, so run them off the event loop. A logging failure
        # shouldn't break the response the caller is waiting for.
        try:
            await run_in_threadpool(add_request_log, entry)
        except Exception:
            logger.exception("Failed to write request log entry")
    return response


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/datetime")
def get_datetime():
    now = datetime.now(timezone.utc).astimezone()
    return {
        "datetime": now.isoformat(),
        "date": now.date().isoformat(),
        "time": now.strftime("%H:%M:%S"),
        "timezone": str(now.tzinfo),
    }


@app.get("/history", response_model=list[RequestLog])
def history(limit: int = Query(50, ge=1, le=1000)):
    return recent_request_logs(limit)


@app.get("/stats")
def stats():
    return request_log_stats()


@app.get("/healthz")
def healthz():
    return {"status": "ok"}
