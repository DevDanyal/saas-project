import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import require_user
from app.db import crud, models
from app.db.session import get_session

router = APIRouter(prefix="/teams", tags=["teams"])


class CreateTeamRequest(BaseModel):
    name: str


class AddMemberRequest(BaseModel):
    email: str | None = None
    user_id: uuid.UUID | None = None
    role: str = "agent"


class UpdateRoleRequest(BaseModel):
    role: str


def _parse_role(value: str) -> models.TeamRole:
    try:
        return models.TeamRole(value)
    except ValueError:
        raise HTTPException(status_code=400, detail="Role must be 'admin' or 'agent'")


async def _require_membership(
    db: AsyncSession, team_id: uuid.UUID, user: models.User, admin: bool = False
) -> tuple[models.Team, models.TeamMember]:
    team = await crud.get_team(db, team_id)
    if team is None:
        raise HTTPException(status_code=404, detail="Team not found")

    members = await crud.get_team_members(db, team_id)
    membership = next((m for m in members if m.user_id == user.id), None)
    if membership is None:
        raise HTTPException(status_code=403, detail="You are not a member of this team")
    if admin and membership.role != models.TeamRole.admin:
        raise HTTPException(status_code=403, detail="Admin role required")
    return team, membership


@router.post("")
async def create_team(
    body: CreateTeamRequest,
    user: models.User = Depends(require_user),
    db: AsyncSession = Depends(get_session),
):
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Team name is required")

    team = await crud.create_team(db, user.id, name)
    await db.commit()
    return {
        "id": str(team.id),
        "name": team.name,
        "owner_id": str(team.owner_id),
        "is_owner": True,
    }


@router.get("")
async def list_teams(
    user: models.User = Depends(require_user),
    db: AsyncSession = Depends(get_session),
):
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
    user: models.User = Depends(require_user),
    db: AsyncSession = Depends(get_session),
):
    team, _ = await _require_membership(db, team_id, user)
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
    user: models.User = Depends(require_user),
    db: AsyncSession = Depends(get_session),
):
    await _require_membership(db, team_id, user, admin=True)
    role = _parse_role(body.role)

    if body.email:
        target = await crud.get_user_by_email(db, body.email.strip().lower())
    elif body.user_id:
        target = await crud.get_user(db, str(body.user_id))
    else:
        raise HTTPException(status_code=400, detail="email or user_id is required")

    if target is None:
        raise HTTPException(
            status_code=404, detail="User not found. They must sign up first."
        )

    existing = await db.execute(
        select(models.TeamMember).where(
            models.TeamMember.team_id == team_id,
            models.TeamMember.user_id == target.id,
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=400, detail="User is already a team member")

    member = await crud.add_team_member(db, team_id, target.id, role)
    await db.commit()
    return {
        "id": str(member.id),
        "user_id": str(member.user_id),
        "role": member.role.value,
    }


@router.delete("/{team_id}/members/{user_id}")
async def remove_member(
    team_id: uuid.UUID,
    user_id: uuid.UUID,
    user: models.User = Depends(require_user),
    db: AsyncSession = Depends(get_session),
):
    team, _ = await _require_membership(db, team_id, user, admin=True)
    if user_id == team.owner_id:
        raise HTTPException(status_code=400, detail="Cannot remove the team owner")

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
    user: models.User = Depends(require_user),
    db: AsyncSession = Depends(get_session),
):
    team, _ = await _require_membership(db, team_id, user, admin=True)
    role = _parse_role(body.role)
    if user_id == team.owner_id and role != models.TeamRole.admin:
        raise HTTPException(status_code=400, detail="Owner must remain an admin")

    member = await crud.update_member_role(db, team_id, user_id, role)
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    await db.commit()
    return {
        "id": str(member.id),
        "user_id": str(member.user_id),
        "role": member.role.value,
    }
