from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from aquaculture_api import deps
from aquaculture_api.deps import ApiError, session_dependency, trace_id
from aquaculture_api.models import User
from aquaculture_api.schemas import LoginRequest, RefreshRequest
from aquaculture_api.security import (
    issue_access_token,
    issue_offline_grant,
    issue_refresh_token,
    validate_credential,
    validated_subject,
)
from aquaculture_api.services import audit


def router() -> APIRouter:
    r = APIRouter(tags=["auth"])

    @r.post("/api/v1/auth/login")
    def login(
        body: LoginRequest,
        request: Request,
        session: Annotated[Session, Depends(session_dependency)],
    ) -> dict[str, object]:
        settings = deps.get_settings()
        user = session.scalar(select(User).where(User.phone == body.phone))
        if (
            user is None
            or not user.active
            or not validate_credential(body.credential, user.credential_salt, user.credential_hash)
        ):
            audit(session, "anonymous", "auth.login_failed", "credentials", trace_id(request))
            session.commit()
            raise ApiError(401, "unauthorized", "Invalid credentials")
        audit(session, user.id, "auth.login_succeeded", user.id, trace_id(request))
        session.commit()
        return {
            "access_token": issue_access_token(user.id, settings),
            "refresh_token": issue_refresh_token(user.id, settings),
            "role": user.role,
        }

    @r.post("/api/v1/auth/refresh")
    def refresh_session(
        body: RefreshRequest,
        request: Request,
        session: Annotated[Session, Depends(session_dependency)],
    ) -> dict[str, str]:
        settings = deps.get_settings()
        subject = validated_subject(body.refresh_token, settings, "refresh")
        user = session.get(User, subject) if subject is not None else None
        if user is None or not user.active:
            audit(
                session,
                subject or "anonymous",
                "auth.token_refresh_failed",
                "refresh_token",
                trace_id(request),
            )
            session.commit()
            raise ApiError(401, "unauthorized", "Refresh token is invalid")
        audit(session, user.id, "auth.token_refreshed", user.id, trace_id(request))
        session.commit()
        return {"access_token": issue_access_token(user.id, settings)}

    @r.get("/api/v1/me")
    def me(user: Annotated[User, Depends(deps.current_user)]) -> dict[str, object]:
        return {
            "id": user.id,
            "role": user.role,
            "pond_scope": user.pond_scope.split(","),
        }

    @r.post("/api/v1/auth/offline-grants")
    def offline_grant(
        request: Request,
        user: Annotated[User, Depends(deps.current_user)],
        session: Annotated[Session, Depends(session_dependency)],
    ) -> dict[str, object]:
        settings = deps.get_settings()
        permissions = ["read_cached_dashboard", "draft_alert_resolution"]
        pond_scope = user.pond_scope.split(",")
        signed_grant, expiry = issue_offline_grant(user.id, permissions, pond_scope, settings)
        audit(session, user.id, "auth.offline_grant_issued", user.id, trace_id(request))
        session.commit()
        return {
            "max_days": 7,
            "permissions": permissions,
            "pond_scope": pond_scope,
            "source_mode": "simulation",
            "expires_at": datetime.fromtimestamp(expiry, UTC).isoformat(),
            "signed_grant": signed_grant,
        }

    return r
