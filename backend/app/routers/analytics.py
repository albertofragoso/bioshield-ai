"""Analytics event ingestion — fire-and-forget (Fase 2).

Records user interactions with the alternatives feature.
Errors are swallowed to never block the UI.
"""

import logging
from uuid import uuid4

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.middleware.auth import get_current_user
from app.middleware.rate_limit import limiter
from app.models import AnalyticsEvent, User
from app.models.base import get_db
from app.schemas.models import AnalyticsEventIn

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analytics", dependencies=[Depends(get_current_user)])


@router.post("/event", status_code=status.HTTP_202_ACCEPTED)
@limiter.limit("30/minute")
def record_event(
    request: Request,
    body: AnalyticsEventIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        db.add(
            AnalyticsEvent(
                id=str(uuid4()),
                user_id=str(current_user.id),
                event_type=body.event_type,
                payload=body.payload,
            )
        )
        db.commit()
    except Exception as exc:
        logger.warning("Analytics event failed silently: %s", exc)
    return JSONResponse(status_code=202, content={"status": "accepted"})
