from pydantic import BaseModel, Field


class ErrorOut(BaseModel):
    """Єдиний формат помилки. Додаткові поля залежать від коду (див. docs/api.md)."""

    error: str = Field(examples=["DENIED_403_RBAC"])
    message: str
    request_id: str | None = None
    audit_entry_id: int | None = Field(
        default=None, description="Номер запису в журналі аудиту (для відмов 401/403)"
    )

    model_config = {"extra": "allow"}


UNAUTHORIZED = {401: {"model": ErrorOut, "description": "Немає або недійсний токен"}}
FORBIDDEN = {403: {"model": ErrorOut, "description": "Роль не має прав або немає згоди"}}
NOT_FOUND = {404: {"model": ErrorOut, "description": "Не знайдено"}}
