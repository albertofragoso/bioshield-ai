"""Per-user daily token budget enforcement.

Enforcement uses a single atomic SQL UPDATE — no read-modify-write race.
The WHERE clause prevents the UPDATE from succeeding if the budget would
be exceeded. rowcount == 0 → 429.

IMPORTANT: Add Depends(token_budget(ENDPOINT_TOKEN_COST["<key>"])) to every
endpoint that calls gemini.py. See backend/CLAUDE.md for the rule.
"""

from datetime import UTC, date, datetime, time, timedelta

from fastapi import Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.middleware.auth import get_current_user
from app.models import User
from app.models.base import get_db

# Per-endpoint estimated token costs.
# UPDATE THIS when the Gemini model changes pricing or you add a new LLM endpoint.
ENDPOINT_TOKEN_COST: dict[str, int] = {
    "scan_photo": 2_000,
    "scan_barcode": 1_000,
    "biosync_extract": 4_000,
}


def _seconds_until_midnight_utc() -> int:
    now = datetime.now(UTC)
    midnight = datetime.combine(now.date() + timedelta(days=1), time.min, tzinfo=UTC)
    return max(1, int((midnight - now).total_seconds()))


def token_budget(estimated_tokens: int):
    """Factory: returns a FastAPI dependency that atomically reserves `estimated_tokens`.

    Uses a single SQL UPDATE with a WHERE guard — prevents read-modify-write races.
    Daily reset is handled inside the same UPDATE when tokens_budget_date < today.
    """
    assert estimated_tokens > 0, "estimated_tokens must be positive"

    async def _dep(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
        settings: Settings = Depends(get_settings),
    ) -> User:
        today = date.today()

        result = db.execute(
            text("""
                UPDATE users
                SET
                    tokens_used_today = CASE
                        WHEN tokens_budget_date < :today THEN :estimated
                        ELSE tokens_used_today + :estimated
                    END,
                    tokens_budget_date = :today
                WHERE id = :user_id
                  AND (
                      CASE
                          WHEN tokens_budget_date < :today THEN :estimated
                          ELSE tokens_used_today + :estimated
                      END
                  ) <= :budget
            """),
            {
                "today": today.isoformat(),
                "estimated": estimated_tokens,
                "user_id": current_user.id,
                "budget": settings.daily_token_budget,
            },
        )
        db.commit()

        if result.rowcount == 0:  # type: ignore[union-attr]
            retry_after = _seconds_until_midnight_utc()
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                headers={"Retry-After": str(retry_after)},
                detail={
                    "error": "token_budget_exceeded",
                    "message": "Daily AI token limit reached",
                    "resets_at": (today + timedelta(days=1)).isoformat() + "T00:00:00Z",
                },
            )

        return current_user

    return _dep
