"""Validate JWT identity, then resolve current permissions from database membership.

Token role and platform-operator claims never grant authority.
"""

from __future__ import annotations

import uuid
from dataclasses import replace

import jwt
import sqlalchemy as sa

from .tenancy import TenantContext

DEFAULT_ISSUER = "traluat"
DEFAULT_AUDIENCE = "traluat-api"
_INSECURE_SECRETS = {"dev-secret-change-me-0123456789abcd"}


def validate_secret(secret: str) -> None:
    if not isinstance(secret, str) or len(secret.encode()) < 32 or secret in _INSECURE_SECRETS:
        raise ValueError("JWT_SECRET must be a private key of at least 32 bytes")


def decode_context(
    token: str, secret: str, *, algorithms=("HS256",),
    issuer: str = DEFAULT_ISSUER, audience: str = DEFAULT_AUDIENCE,
) -> TenantContext:
    validate_secret(secret)
    try:
        claims = jwt.decode(
            token, secret, algorithms=list(algorithms), issuer=issuer, audience=audience,
            options={"require": ["exp", "iat", "sub", "iss", "aud", "tenant_id"]},
        )
    except (ValueError, TypeError, OverflowError) as exc:
        raise jwt.InvalidTokenError("invalid token envelope") from exc
    try:
        tenant_id = str(uuid.UUID(claims["tenant_id"]))
        subject = claims["sub"]
        if not isinstance(subject, str) or not subject.strip():
            raise ValueError("empty subject")
        if (isinstance(claims["exp"], bool) or isinstance(claims["iat"], bool)
                or not isinstance(claims["exp"], (int, float))
                or not isinstance(claims["iat"], (int, float))
                or not 0 < claims["exp"] - claims["iat"] <= 3600):
            raise ValueError("token lifetime must be between 0 and 3600 seconds")
        # Role/retention/residency/operator claims do not grant authority. Current
        # membership is resolved below so role changes and tenant suspension revoke access.
        return TenantContext(tenant_id=tenant_id, subject=subject)
    except (ValueError, TypeError, AttributeError) as exc:
        raise jwt.InvalidTokenError("invalid identity claims") from exc


def verify_database_identity(session, ctx: TenantContext) -> TenantContext:
    from .models import PlatformOperator, Tenant, TenantUser
    from .rls import set_identity

    set_identity(session, ctx.tenant_id, ctx.subject)
    tenant = session.scalars(sa.select(Tenant).where(
        Tenant.id == uuid.UUID(ctx.tenant_id), Tenant.status == "active")).first()
    member = session.scalars(sa.select(TenantUser).where(
        TenantUser.tenant_id == uuid.UUID(ctx.tenant_id),
        TenantUser.auth_subject == ctx.subject)).first()
    if tenant is None or member is None:
        raise jwt.InvalidTokenError("inactive tenant or revoked membership")
    operator = session.scalar(sa.select(PlatformOperator.auth_subject).where(
        PlatformOperator.auth_subject == ctx.subject, PlatformOperator.enabled.is_(True)))
    try:
        return replace(
            ctx, role=member.role, residency_region=tenant.residency_region,
            retention_mode=tenant.retention_mode, platform_operator=operator is not None,
        )
    except ValueError as exc:
        raise jwt.InvalidTokenError("invalid membership role") from exc
