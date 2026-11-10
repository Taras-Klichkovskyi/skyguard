from fastapi import APIRouter, Request
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.api.deps import CurrentUser, DbSession, deny_unauthenticated
from app.core.errors import ApiError
from app.core.security import (
    ACCESS,
    REFRESH,
    TokenError,
    create_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models import Role, User
from app.models.enums import AuditOutcome, DataClassification, RoleCode
from app.schemas.auth import LoginIn, RefreshIn, RegisterIn, TokenOut, UserOut
from app.schemas.common import UNAUTHORIZED, ErrorOut
from app.services import audit

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


def _user_out(user: User) -> UserOut:
    return UserOut(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role.code,
        assigned_shelter_id=user.assigned_shelter_id,
    )


def _tokens(user: User) -> TokenOut:
    access, expires_in = create_token(user.id, user.role.code, ACCESS)
    refresh, _ = create_token(user.id, user.role.code, REFRESH)
    return TokenOut(
        access_token=access, refresh_token=refresh, expires_in=expires_in, role=user.role.code
    )


def _find_by_email(db: DbSession, email: str) -> User | None:
    return db.scalars(select(User).where(func.lower(User.email) == email.lower())).first()


@router.post(
    "/register",
    response_model=UserOut,
    status_code=201,
    responses={409: {"model": ErrorOut, "description": "Email уже зареєстровано"}},
)
def register(body: RegisterIn, request: Request, db: DbSession) -> UserOut:
    """Самореєстрація мешканця. Роль завжди CITIZEN: інші ролі призначає адміністрація."""
    conflict = ApiError(409, "EMAIL_TAKEN", "Користувач з таким email уже існує")
    if _find_by_email(db, body.email) is not None:
        raise conflict
    role_id = db.scalar(select(Role.id).where(Role.code == RoleCode.CITIZEN))
    user = User(
        role_id=role_id,
        email=body.email,
        full_name=body.full_name,
        password_hash=hash_password(body.password),
    )
    db.add(user)
    try:
        db.flush()
    except IntegrityError as exc:  # одночасна реєстрація того самого email
        db.rollback()
        raise conflict from exc
    audit.record(
        db,
        request,
        action="USER_REGISTERED",
        outcome=AuditOutcome.SUCCESS,
        http_status=201,
        actor=user,
        classification=DataClassification.CONFIDENTIAL,
        entity_type="user",
        entity_id=user.id,
    )
    db.commit()
    return _user_out(user)


@router.post("/login", response_model=TokenOut, responses=UNAUTHORIZED)
def login(body: LoginIn, request: Request, db: DbSession) -> TokenOut:
    """Повертає пару токенів. У access-токені — ідентифікатор і роль користувача."""
    user = _find_by_email(db, body.email)
    usable = user is not None and user.is_active and user.deleted_at is None
    if not verify_password(body.password, user.password_hash if usable else None):
        # Однакова відповідь для невідомого email і хибного пароля
        raise deny_unauthenticated(db, request, "bad_credentials")
    audit.record(
        db,
        request,
        action="LOGIN_SUCCESS",
        outcome=AuditOutcome.SUCCESS,
        http_status=200,
        actor=user,
        entity_type="user",
        entity_id=user.id,
    )
    user.last_login_at = func.now()
    db.commit()
    return _tokens(user)


@router.post("/refresh", response_model=TokenOut, responses=UNAUTHORIZED)
def refresh(body: RefreshIn, request: Request, db: DbSession) -> TokenOut:
    """Обмінює дійсний refresh-токен на нову пару токенів."""
    try:
        payload = decode_token(body.refresh_token, REFRESH)
    except TokenError as exc:
        raise deny_unauthenticated(db, request, str(exc)) from exc
    user = db.get(User, payload["sub"])
    if user is None or not user.is_active or user.deleted_at is not None:
        raise deny_unauthenticated(db, request, "user_inactive")
    return _tokens(user)


@router.get("/me", response_model=UserOut, responses=UNAUTHORIZED)
def me(user: CurrentUser) -> UserOut:
    return _user_out(user)
