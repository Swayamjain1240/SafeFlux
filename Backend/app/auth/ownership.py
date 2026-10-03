"""Object-level authorization helpers for user-owned resources.

Every owned model (Plant, AnalysisRun, Scenario, Report, …) will carry an
`owner_id` FK to User.id. Access checks always compare the *verified*
session user against the stored owner — never a user_id supplied by the
client (SAFEFLUX_MASTER.md §12 / ARCHITECTURE §10).

Returns 404 (not 403) for cross-user access so object existence is not
leaked to unauthorized callers.
"""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import User


def get_owned_or_404(db: Session, model: type, resource_id: str, user: User):  # noqa: ANN201
    """Load one resource enforcing ownership; 404 if missing OR not owned."""
    resource = db.get(model, resource_id)
    if resource is None or getattr(resource, "owner_id", None) != user.id:
        raise HTTPException(status_code=404, detail="The requested resource was not found.")
    return resource


def ensure_owner(resource: object, user: User) -> None:
    """Assert an already-loaded resource belongs to the session user."""
    if getattr(resource, "owner_id", None) != user.id:
        raise HTTPException(status_code=404, detail="The requested resource was not found.")
