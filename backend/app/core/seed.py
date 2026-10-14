
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import Agent

logger = logging.getLogger("email_agent.seed")

# code must match the dispatch in app/services/agent_executor.py.
# endpoint/method are descriptive only (shown in the UI) - the executor
# calls the Python functions directly, it does not make an HTTP request.
BUILTIN_AGENTS = [
    {
        "name": "Fetch Emails",
        "code": "email_fetch",
        "description": "Pulls new messages from the user's connected mailbox and stores them as queued emails.",
        "category": "email",
        "endpoint": "/mail-agents/getEmails",
        "method": "POST",
    },
    {
        "name": "Classify Emails",
        "code": "email_classification",
        "description": "Runs the LLM classification agent over the user's queued emails using their configured categories and LLM credential.",
        "category": "email",
        "endpoint": "/classifyEmails",
        "method": "POST",
    },
]


async def seed_builtin_agents(db: AsyncSession) -> None:
    for spec in BUILTIN_AGENTS:
        existing = (
            await db.execute(select(Agent).where(Agent.code == spec["code"]))
        ).scalar_one_or_none()

        if existing is None:
            db.add(Agent(**spec, enabled=True))
            logger.info("Seeded agent %s", spec["code"])
        else:
            # Keep display metadata in sync; never touch `enabled`, so an
            # operator's choice to disable an agent survives restarts.
            existing.name = spec["name"]
            existing.description = spec["description"]
            existing.category = spec["category"]
            existing.endpoint = spec["endpoint"]
            existing.method = spec["method"]

    await db.commit()
