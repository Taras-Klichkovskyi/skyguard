"""Єдиний формат помилок API.

Кожна помилка — JSON з полями `error` (машинний код), `message` (текст для
людини українською) і `request_id`. Відмови доступу додатково несуть
`audit_entry_id` — номер запису в журналі аудиту, за яким інцидент знаходить
аудитор, а 403 за роллю — ще й `required_roles`.
"""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

# Коди збігаються з типами подій у журналі аудиту (розділ 4.1 звіту)
DENIED_401_AUTH = "DENIED_401_AUTH"
DENIED_403_RBAC = "DENIED_403_RBAC"
DENIED_403_CONSENT = "DENIED_403_CONSENT"


class ApiError(Exception):
    def __init__(
        self,
        status_code: int,
        error: str,
        message: str,
        *,
        headers: dict[str, str] | None = None,
        **extra,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.error = error
        self.message = message
        self.headers = headers
        self.extra = extra


def _body(request: Request, error: str, message: str, **extra) -> dict:
    body = {"error": error, "message": message, **extra}
    body["request_id"] = getattr(request.state, "request_id", None)
    return body


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def api_error(request: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(
            _body(request, exc.error, exc.message, **exc.extra),
            status_code=exc.status_code,
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        details = [
            {"field": ".".join(str(p) for p in e["loc"][1:]) or e["loc"][0], "problem": e["msg"]}
            for e in exc.errors()
        ]
        return JSONResponse(
            _body(request, "VALIDATION_ERROR", "Запит не пройшов перевірку", details=details),
            status_code=422,
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        codes = {404: "NOT_FOUND", 405: "METHOD_NOT_ALLOWED"}
        return JSONResponse(
            _body(request, codes.get(exc.status_code, f"HTTP_{exc.status_code}"), str(exc.detail)),
            status_code=exc.status_code,
            headers=getattr(exc, "headers", None),
        )
