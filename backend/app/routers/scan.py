from fastapi import APIRouter, Depends

from app.middleware.auth import get_current_user
from app.models import User

router = APIRouter(dependencies=[Depends(get_current_user)])


@router.get("/ping")
def ping(current_user: User = Depends(get_current_user)):
    """Smoke-test endpoint — verifies auth dependency is wired correctly."""
    return {"user_id": current_user.id}
