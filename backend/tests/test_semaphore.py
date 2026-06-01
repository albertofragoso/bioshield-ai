import pytest

from app.core.semaphore import semaphore_from_score
from app.schemas.models import SemaphoreColor


@pytest.mark.parametrize(
    "score,expected",
    [
        (0, SemaphoreColor.BLUE),
        (1, SemaphoreColor.YELLOW),
        (2, SemaphoreColor.YELLOW),
        (3, SemaphoreColor.ORANGE),
        (4, SemaphoreColor.ORANGE),
        (5, SemaphoreColor.RED),
        (99, SemaphoreColor.RED),
    ],
)
def test_semaphore_from_score(score, expected):
    assert semaphore_from_score(score) == expected
