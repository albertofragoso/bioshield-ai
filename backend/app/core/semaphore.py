from app.schemas.models import SemaphoreColor


def semaphore_from_score(score: int) -> SemaphoreColor:
    if score == 0:
        return SemaphoreColor.BLUE
    if score <= 2:
        return SemaphoreColor.YELLOW
    if score <= 4:
        return SemaphoreColor.ORANGE
    return SemaphoreColor.RED
