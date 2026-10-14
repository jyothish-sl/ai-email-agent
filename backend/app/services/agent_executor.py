# app/services/agent_executor.py
"""
Dispatches a schedule/manual "Run now" trigger to whatever the target
Agent actually does.

This function is called from two places:
    1. app/services/scheduler_service.py::_run_due_schedules
       (automatic runs, triggered by the poll loop)
    2. app/api/schedule.py::run_schedule
       (manual "Run now" button in the UI)

Both callers already hold an open AsyncSession and know which user the
schedule belongs to, so both are passed in here rather than opened fresh -
that keeps a scheduled run and a manual run sharing the exact same code
path (and same commit boundary) as an ordinary API request.
"""

import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import Agent

logger = logging.getLogger(__name__)


class AgentExecutionError(Exception):
    """Raised when an agent can't be run (missing, unsupported, or the
    underlying task itself failed)."""


async def execute_agent(
    agent_id: UUID,
    user_id: UUID,
    db: AsyncSession,
    schedule_id: UUID | None = None,
) -> None:
    logger.info("Executing agent %s (schedule_id=%s)", agent_id, schedule_id)

    agent = await db.get(Agent, agent_id)
    if not agent:
        raise AgentExecutionError(f"Agent {agent_id} not found")

    if not agent.enabled:
        raise AgentExecutionError(f"Agent {agent_id} ({agent.name}) is disabled")
    
    match agent.code:
        case "email_fetch":
             from app.api.mail_agents import fetch_and_store_emails
             result = await fetch_and_store_emails(user_id, db)
             logger.info(
                 "Agent %s fetched %s emails, stored %s new (schedule_id=%s)",
                 agent_id,
                 result.fetched,
                 result.stored,
                 schedule_id
             )
             return
        case "email_classification":
            from app.api.classify import classify_and_store_emails

            result = await classify_and_store_emails(user_id, db)

            logger.info(
                "Agent %s classified %s/%s emails, skipped %s, LLM calls %s (schedule_id=%s)",
                agent_id,
                result.classified,
                result.scanned,
                result.skipped,
                result.llm_calls,
                schedule_id,
            )
            return

        case _:
            raise AgentExecutionError(
                f"No runnable implementation for agent code '{agent.code}'"
            )
                                                
    raise AgentExecutionError(
        f"Agent {agent_id} ({agent.name}) has no runnable implementation "
        f"for code={agent.code!r} category={agent.category!r}"
    )