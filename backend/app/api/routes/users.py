from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import models
from app.db.session import get_session

router = APIRouter(prefix="/users", tags=["users"])


@router.get("")
async def list_users(db: AsyncSession = Depends(get_session)):
    result = await db.execute(select(models.User).order_by(models.User.created_at))
    return {
        "users": [
            {
                "id": str(u.id),
                "name": u.name,
                "email": u.email,
                "role": u.role.value,
                "created_at": u.created_at.isoformat() if u.created_at else None,
            }
            for u in result.scalars().all()
        ]
    }