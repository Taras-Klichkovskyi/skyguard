from datetime import datetime

from pydantic import BaseModel

from app.models.enums import ConsentPurpose, ConsentStatus


class ConsentIn(BaseModel):
    purpose: ConsentPurpose


class ConsentOut(BaseModel):
    purpose: ConsentPurpose
    status: ConsentStatus
    policy_version: str | None = None
    granted_at: datetime | None = None
    revoked_at: datetime | None = None
    expires_at: datetime | None = None
