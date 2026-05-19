from pydantic import BaseModel


class ErrorResponse(BaseModel):
    error: str
    message: str
    detail: dict | None = None
