from fastapi import APIRouter, Depends

from app.core.security import require_user
from app.db import models

router = APIRouter(prefix="/users", tags=["users"])


@router.get("")
async def current_user_profile(user: models.User = Depends(require_user)):
    return {
        "users": [
            {
                "id": str(user.id),
                "name": user.name,
                "email": user.email,
                "role": user.role.value,
                "created_at": user.created_at.isoformat() if user.created_at else None,
            }
        ]
    }
