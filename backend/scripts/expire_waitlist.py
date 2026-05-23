"""CLI: eliminar registros de waitlist vencidos sin contactar.

LFPDPPP data minimization: filas con expires_at < NOW() y sin contacted_at
se borran. Las filas con contacted_at (usuario invitado al beta) se conservan.

Uso:
    cd backend && python -m scripts.expire_waitlist
"""

import sys
from datetime import UTC, datetime

from sqlalchemy import text

from app.models.base import SessionLocal


def expire_waitlist(db) -> int:
    """Elimina filas vencidas no contactadas. Devuelve el número de filas borradas."""
    result = db.execute(
        text("DELETE FROM waitlist_signups WHERE expires_at < :now AND contacted_at IS NULL"),
        {"now": datetime.now(UTC)},
    )
    db.commit()
    return result.rowcount


def main() -> int:
    db = SessionLocal()
    try:
        removed = expire_waitlist(db)
        print(f"Eliminados {removed} registro(s) de waitlist vencidos.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
