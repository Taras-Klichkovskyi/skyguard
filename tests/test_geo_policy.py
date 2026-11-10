import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.core.policy import ALL_POLICIES
from app.models.enums import RoleCode
from app.services.geo import haversine_m, walk_minutes


def test_haversine_known_distances():
    # 0,001° широти ≈ 111,2 м
    assert haversine_m(49.8397, 24.0297, 49.8407, 24.0297) == pytest.approx(111.2, abs=0.1)
    # Львів (пл. Ринок) — Київ (Майдан) ≈ 469 км
    assert haversine_m(49.8419, 24.0315, 50.4501, 30.5234) == pytest.approx(469_000, rel=0.01)
    assert haversine_m(49.8397, 24.0297, 49.8397, 24.0297) == 0


def test_walk_minutes():
    assert walk_minutes(10) == 1
    assert walk_minutes(800) == 10


def test_anonymous_role_is_never_granted_protected_access():
    for policy in ALL_POLICIES:
        assert RoleCode.ANONYMOUS not in policy.allowed_roles, policy.action
        assert policy.ownership_roles <= policy.allowed_roles


def test_default_jwt_secret_is_refused_outside_dev():
    with pytest.raises(ValidationError):
        Settings(app_env="prod", _env_file=None)
    assert Settings(app_env="prod", jwt_secret="x" * 40, _env_file=None).jwt_secret == "x" * 40
