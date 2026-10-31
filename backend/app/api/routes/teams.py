import uuid
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import crud, models
from app.db.session import get_session

router = APIRouter(prefix="/teams", tags=["teams"])


class CreateTeamRequest(BaseModel):
    name: str


class AddMemberRequest(BaseModel):
    user_id: uuid.UUID
    role: str = "agent"


class UpdateRoleRequest(BaseModel):
    role: str


@router.post("")
async def create_team(
    body: CreateTeamRequest,
    db: AsyncSession = Depends(get_session),
):
    # For now, use the first user as owner - in real app, get from auth
    from app.api.routes.users import router as users_router
    result = await db.execute(select(models.User).limit(1))
    owner = result.scalar_one_or_none()
    if not owner:
        raise HTTPException(status_code=400, detail="No users exist")
    
    team = await crud.create_team(db, owner.id, body.name)
    await db.commit()
    return {"id": str(team.id), "name": team.name, "owner_id": str(team.owner_id)}


@router.get("")
async def list_teams(
    db: AsyncSession = Depends(get_session),
):
    # For now, use the first user - in real app, get from auth
    result = await db.execute(select(models.User).limit(1))
    user = result.scalar_one_or_none()
    if not user:
        return {"teams": []}
    
    teams = await crud.get_user_teams(db, user.id)
    return {
        "teams": [
            {
                "id": str(t.id),
                "name": t.name,
                "owner_id": str(t.owner_id),
                "is_owner": t.owner_id == user.id,
            }
            for t in teams
        ]
    }


@router.get("/{team_id}")
async def get_team(
    team_id: uuid.UUID,
    db: AsyncSession = Depends(get_session),
):
    team = await crud.get_team(db, team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    
    members = await crud.get_team_members(db, team_id)
    return {
        "id": str(team.id),
        "name": team.name,
        "owner_id": str(team.owner_id),
        "members": [
            {
                "id": str(m.id),
                "user_id": str(m.user_id),
                "email": m.user.email,
                "name": m.user.name,
                "role": m.role.value,
                "joined_at": m.joined_at.isoformat() if m.joined_at else None,
            }
            for m in members
        ],
    }


@router.post("/{team_id}/members")
async def add_member(
    team_id: uuid.UUID,
    body: AddMemberRequest,
    db: AsyncSession = Depends(get_session),
):
    team = await crud.get_team(db, team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    
    # Check if user exists
    user = await crud.get_user(db, str(body.user_id))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    role = models.TeamRole(body.role)
    member = await crud.add_team_member(db, team_id, body.user_id, role)
    await db.commit()
    return {"id": str(member.id), "user_id": str(member.user_id), "role": member.role.value}


@router.delete("/{team_id}/members/{user_id}")
async def remove_member(
    team_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_session),
):
    success = await crud.remove_team_member(db, team_id, user_id)
    if not success:
        raise HTTPException(status_code=404, detail="Member not found")
    await db.commit()
    return {"success": True}


@router.patch("/{team_id}/members/{user_id}")
async def update_role(
    team_id: uuid.UUID,
    user_id: uuid.UUID,
    body: UpdateRoleRequest,
    db: AsyncSession = Depends(get_session),
):
    role = models.TeamRole(body.role)
    member = await crud.update_member_role(db, team_id, user_id, role)
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    await db.commit()
    return {"id": str(member.id), "user_id": str(member.user_id), "role": member.role.value}