# app/core/scheduler_lifespan.py
"""
Wire this into your FastAPI app's lifespan so the poll loop actually
starts. Example, in app/main.py:

    from contextlib import asynccontextmanager
    from fastapi import FastAPI
    from app.core.scheduler_lifespan import scheduler_lifespan

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        async with scheduler_lifespan():
            yield

    app = FastAPI(lifespan=lifespan)

If you already have a lifespan function with other startup/shutdown
logic, just call `scheduler_service.start()` / `scheduler_service.shutdown()`
at the right points inside it instead of nesting this context manager.

NOTE ON MULTIPLE WORKERS: if you run this app with multiple
uvicorn/gunicorn worker processes, each one will start its own poll
loop. That's actually fine here (unlike the old Redis/APScheduler
version) because `SELECT ... FOR UPDATE SKIP LOCKED` in
scheduler_service.py ensures they won't double-run the same due
schedule - each worker just picks up whatever's still unlocked.
"""

from contextlib import asynccontextmanager

from app.services import scheduler_service


@asynccontextmanager
async def scheduler_lifespan():
    scheduler_service.start()
    try:
        yield
    finally:
        scheduler_service.shutdown()