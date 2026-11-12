"""Authentication rejects forged/underspecified/stale token envelopes."""
import datetime as dt
import uuid

import jwt
import pytest

from traluat.w5.auth import decode_context, validate_secret

SECRET = "test-private-signing-key-at-least-32-bytes"


def _claims():
    now = int(dt.datetime.now(dt.UTC).timestamp())
    return {"tenant_id": str(uuid.uuid4()), "sub": "issuer-user-123", "iss": "traluat",
            "aud": "traluat-api", "iat": now, "exp": now + 600}


@pytest.mark.parametrize("field", ["exp", "iat", "sub", "iss", "aud", "tenant_id"])
def test_required_claims(field):
    claims = _claims()
    del claims[field]
    with pytest.raises(jwt.PyJWTError):
        decode_context(jwt.encode(claims, SECRET, algorithm="HS256"), SECRET)


@pytest.mark.parametrize("overrides", [
    {"iss": "other"}, {"aud": "other"}, {"tenant_id": "t1"}, {"sub": ""},
    {"exp": 1}, {"exp": True}, {"iat": 0}, {"exp": float("nan")},
    {"iat": float("inf")}, {"tenant_id": []}, {"exp": []},
])
def test_invalid_claims(overrides):
    claims = {**_claims(), **overrides}
    with pytest.raises(jwt.PyJWTError):
        decode_context(jwt.encode(claims, SECRET, algorithm="HS256"), SECRET)


def test_claims_do_not_grant_tenant_or_platform_permissions():
    claims = {**_claims(), "role": "owner", "platform_operator": True,
              "retention_mode": "zero", "residency_region": "foreign"}
    ctx = decode_context(jwt.encode(claims, SECRET, algorithm="HS256"), SECRET)
    assert ctx.role == "viewer" and not ctx.platform_operator
    assert ctx.retention_mode == "standard" and ctx.residency_region == "vn"


@pytest.mark.parametrize("secret", ["", "short", "dev-secret-change-me-0123456789abcd"])
def test_no_default_or_weak_secret(secret):
    with pytest.raises(ValueError):
        validate_secret(secret)
