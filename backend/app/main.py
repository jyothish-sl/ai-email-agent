import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api.auth import auth_router, limiter
from app.api.credentials import credentials_router
from app.api.dashboard import dashboard_router
from app.api.mail_agents import mail_agents_router
from app.core.config import settings
from app.core.scheduler_lifespan import scheduler_lifespan  # ← ADD THIS
from app.core.seed import seed_builtin_agents
from app.database.db import AsyncSessionLocal, Base, engine
from app.api.classifications import classifications_router
from app.api.email import emails_router
from app.api.agent import agent_router
from app.api.schedule import schedule_router
from app.api.classify import classify_router

logging.basicConfig(
    level=settings.resolved_log_level,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

logger = logging.getLogger("email_agent")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # create_all() is a convenience for local dev only. In staging/production,
    # manage the schema with a real migration tool (e.g. Alembic) instead.
    # This MUST run before the scheduler poll loop starts, otherwise the
    # first poll can fire against tables that don't exist yet.
    if settings.environment != "production":
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    # Built-in agents (email_fetch, email_classification) must exist before
    # the scheduler starts polling, and before any user can create a
    # schedule - the "Select Agent" dropdown reads from this table.
    async with AsyncSessionLocal() as session:
        await seed_builtin_agents(session)

    # Start scheduler poll loop
    async with scheduler_lifespan():  # ← ADD THIS CONTEXT MANAGER
        logger.info("Startup complete (environment=%s)", settings.environment)
        yield
        await engine.dispose()
        logger.info("Shutdown complete")

app = FastAPI(title="Email Agent API", version="1.0.0", lifespan=lifespan)


app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list or ["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error on %s", request.url.path)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"},
    )


@app.get("/health")
async def health_check():
    return {"status": "ok"}


app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(credentials_router, prefix="/credentials", tags=["credentials"])
app.include_router(mail_agents_router, prefix="/mail-agents", tags=["mail-agents"])
app.include_router(dashboard_router, prefix="/dashboard", tags=["dashboard"])
app.include_router(classifications_router, prefix="/classifications",tags=["classifications"])
app.include_router(emails_router,tags=["emails"])
app.include_router(schedule_router,prefix="/schedules", tags=["schedules"])
app.include_router(agent_router,prefix="/agents", tags=["agents"])
app.include_router(classify_router)