"""The single FastAPI dependency for authentication and project-scoped roles.

Every router uses `require_project_role(...)`; no endpoint implements its own
permission logic. The dependency verifies the platform JWT, loads the
project-membership row, checks the requested role, and enforces tenant match.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Iterator

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from workshop.auth.jwt import decode_token
from workshop.auth.models import AuthenticatedUser
from workshop.common.enums import ProjectRole
from workshop.common.errors import ForbiddenError, NotFoundError
from workshop.db import get_session_factory
from workshop.project.models import WorkshopProject, WorkshopProjectMember


def get_db() -> Iterator[Session]:
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_current_user(request: Request) -> AuthenticatedUser:
    header = request.headers.get("Authorization", "")
    if not header.lower().startswith("bearer "):
        raise ForbiddenError("Missing bearer token")
    return decode_token(header[len("bearer ") :].strip())


def load_project(session: Session, project_id: uuid.UUID, tenant_id: uuid.UUID) -> WorkshopProject:
    project = session.get(WorkshopProject, project_id)
    if project is None or project.tenant_id != tenant_id:
        raise NotFoundError("Project not found")
    return project


def require_project_role(*allowed_roles: ProjectRole) -> Callable[..., WorkshopProject]:
    """Dependency factory enforcing project membership + role."""

    def dependency(
        project_id: uuid.UUID,
        session: Session = Depends(get_db),
        user: AuthenticatedUser = Depends(get_current_user),
    ) -> WorkshopProject:
        project = load_project(session, project_id, user.tenant_id)
        if user.is_platform_admin():
            return project
        member = (
            session.execute(
                select(WorkshopProjectMember).where(
                    WorkshopProjectMember.project_id == project_id,
                    WorkshopProjectMember.user_id == user.user_id,
                )
            )
            .scalars()
            .first()
        )
        if member is None:
            raise ForbiddenError("You are not a member of this project")
        member_roles = {
            m.role
            for m in session.execute(
                select(WorkshopProjectMember).where(
                    WorkshopProjectMember.project_id == project_id,
                    WorkshopProjectMember.user_id == user.user_id,
                )
            ).scalars()
        }
        if allowed_roles and not (member_roles & {r.value for r in allowed_roles}):
            raise ForbiddenError("Your project role does not permit this action")
        return project

    return dependency
