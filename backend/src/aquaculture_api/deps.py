from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Header, Request
from sqlalchemy.orm import Session

from aquaculture_api.config import Settings
from aquaculture_api.models import Alert, Pond, User
from aquaculture_api.security import validated_subject
from aquaculture_api.store import Store


class ApiError(Exception):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message


_store: Store | None = None
_settings: Settings | None = None


def configure(store: Store, settings: Settings) -> None:
    global _store, _settings
    _store = store
    _settings = settings


def session_dependency() -> Iterator[Session]:
    assert _store is not None
    with _store.sessions() as session:
        yield session


def current_user(
    session: Annotated[Session, Depends(session_dependency)],
    authorization: Annotated[str | None, Header()] = None,
) -> User:
    assert _settings is not None
    if authorization is None or not authorization.startswith("Bearer "):
        raise ApiError(401, "unauthorized", "Authentication is required")
    subject = validated_subject(authorization.removeprefix("Bearer "), _settings)
    user = session.get(User, subject) if subject is not None else None
    if user is None or not user.active:
        raise ApiError(401, "unauthorized", "Authentication is invalid")
    return user


def scoped_pond(session: Session, user: User, pond_id: str) -> Pond:
    pond = session.get(Pond, pond_id)
    if pond is None or pond.id not in user.pond_scope.split(","):
        raise ApiError(403, "forbidden", "Pond is outside the authorized scope")
    return pond


def role_required(user: User, allowed: set[str]) -> None:
    if user.role not in allowed:
        raise ApiError(403, "forbidden", "Role is not authorized for this operation")


def get_settings() -> Settings:
    assert _settings is not None
    return _settings


def trace_id(request: Request) -> str:
    tid = request.state.trace_id
    if not isinstance(tid, str):
        raise RuntimeError("Trace id middleware was not applied")
    return tid


def scoped_alert(session: Session, user: User, alert_id: str) -> Alert:
    alert = session.get(Alert, alert_id)
    if alert is None or alert.pond_id not in user.pond_scope.split(","):
        raise ApiError(404, "not_found", "Alert was not found")
    return alert


def require_state(current: str, allowed: set[str], resource: str) -> None:
    if current not in allowed:
        raise ApiError(409, "invalid_state", f"{resource} is not in an actionable state")


def get_entity_or_404[T](session: Session, model: type[T], entity_id: str, resource_name: str) -> T:
    entity = session.get(model, entity_id)
    if entity is None:
        raise ApiError(404, "not_found", f"{resource_name} was not found")
    return entity
