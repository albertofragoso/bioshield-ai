from fastapi import APIRouter, Depends

from app.middleware.auth import get_current_user

router = APIRouter(dependencies=[Depends(get_current_user)])
