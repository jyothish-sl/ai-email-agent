# app/api/agent.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.deps import get_db
from app.models.agent import Agent
from app.schemas.agent import AgentCreate, AgentUpdate, AgentResponse

agent_router = APIRouter()


@agent_router.get("", response_model=list[AgentResponse])
async def list_agents(
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Agent)
        .where(Agent.enabled.is_(True))
        .order_by(Agent.name)
    )
    return result.scalars().all()


@agent_router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(
    agent_id: str,  # or UUID if you prefer
    db: AsyncSession = Depends(get_db),
):
    agent = await db.get(Agent, agent_id)
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found",
        )
    return agent


@agent_router.post(
    "",
    response_model=AgentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_agent(
    payload: AgentCreate,
    db: AsyncSession = Depends(get_db),
):
    agent = Agent(**payload.model_dump())
    db.add(agent)
    await db.commit()
    await db.refresh(agent)
    return agent


@agent_router.put("/{agent_id}", response_model=AgentResponse)
async def update_agent(
    agent_id: str,
    payload: AgentUpdate,
    db: AsyncSession = Depends(get_db),
):
    agent = await db.get(Agent, agent_id)
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found",
        )

    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(agent, key, value)

    await db.commit()
    await db.refresh(agent)
    return agent


@agent_router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent(
    agent_id: str,
    db: AsyncSession = Depends(get_db),
):
    agent = await db.get(Agent, agent_id)
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found",
        )

    await db.delete(agent)
    await db.commit()
    return