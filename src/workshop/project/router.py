"""Project, membership, overview, reopen, and audit endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from workshop.audit import service as audit
from workshop.auth.dependencies import get_current_user, get_db, require_project_role
from workshop.auth.models import AuthenticatedUser
from workshop.common.enums import (
    PROJECT_CONFIG_ROLES,
    REOPEN_ROLES,
    VIEW_ROLES,
    ProjectStatus,
)
from workshop.common.errors import ForbiddenError
from workshop.project import member_service, overview_service, reopen_service, service
from workshop.project.models import WorkshopProject
from workshop.project.schemas import (
    AuditEvent,
    AuditEventPage,
    MemberCreate,
    Project,
    ProjectCreate,
    ProjectMember,
    ProjectOverview,
    ProjectPage,
    ProjectUpdate,
    ReopenRequest,
    TransitionRequest,
)

router = APIRouter(tags=["Projects"])


def _require_creator(user: AuthenticatedUser) -> None:
    if user.is_platform_admin():
        return
    if not ({"consultant", "implementation_consultant", "admin"} & set(user.global_roles)):
        raise ForbiddenError("You are not permitted to create projects")


@router.post("/projects", response_model=Project, status_code=status.HTTP_201_CREATED)
def create_project(
    data: ProjectCreate,
    session: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(get_current_user),
) -> WorkshopProject:
    _require_creator(user)
    project = service.create_project(session, user, data)
    session.commit()
    return project


@router.get("/projects", response_model=ProjectPage)
def list_projects(
    status_filter: ProjectStatus | None = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100, alias="pageSize"),
    session: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(get_current_user),
) -> ProjectPage:
    items, total = service.list_projects(
        session,
        user,
        status=status_filter.value if status_filter else None,
        page=page,
        page_size=page_size,
    )
    return ProjectPage(
        items=[Project.model_validate(i) for i in items],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get("/projects/{project_id}", response_model=Project)
def get_project(
    project: WorkshopProject = Depends(require_project_role(*VIEW_ROLES)),
) -> WorkshopProject:
    return project


@router.patch("/projects/{project_id}", response_model=Project)
def update_project(
    data: ProjectUpdate,
    project: WorkshopProject = Depends(require_project_role(*PROJECT_CONFIG_ROLES)),
    session: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(get_current_user),
) -> WorkshopProject:
    service.update_project(session, user, project, data)
    session.commit()
    return project


@router.get("/projects/{project_id}/overview", response_model=ProjectOverview)
def get_project_overview(
    project: WorkshopProject = Depends(require_project_role(*VIEW_ROLES)),
    session: Session = Depends(get_db),
) -> ProjectOverview:
    return overview_service.build_overview(session, project)


@router.post("/projects/{project_id}/transition", response_model=Project)
def transition_project(
    data: TransitionRequest,
    project: WorkshopProject = Depends(require_project_role(*PROJECT_CONFIG_ROLES)),
    session: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(get_current_user),
) -> WorkshopProject:
    service.transition(session, user, project, data.target_status.value, data.comment)
    session.commit()
    return project


@router.post("/projects/{project_id}/reopen", response_model=Project)
def reopen_project(
    data: ReopenRequest,
    project: WorkshopProject = Depends(require_project_role(*REOPEN_ROLES)),
    session: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(get_current_user),
) -> WorkshopProject:
    reopen_service.reopen_project(session, user, project, data.reason)
    session.commit()
    return project


@router.get("/projects/{project_id}/members", response_model=list[ProjectMember])
def list_members(
    project: WorkshopProject = Depends(require_project_role(*VIEW_ROLES)),
    session: Session = Depends(get_db),
) -> list[ProjectMember]:
    return [ProjectMember.model_validate(m) for m in member_service.list_members(session, project.id)]


@router.post(
    "/projects/{project_id}/members",
    response_model=ProjectMember,
    status_code=status.HTTP_201_CREATED,
)
def add_member(
    data: MemberCreate,
    project: WorkshopProject = Depends(require_project_role(*PROJECT_CONFIG_ROLES)),
    session: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(get_current_user),
) -> ProjectMember:
    member = member_service.add_member(session, user, project.id, data)
    session.commit()
    return ProjectMember.model_validate(member)


@router.delete("/projects/{project_id}/members/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member(
    member_id: uuid.UUID,
    project: WorkshopProject = Depends(require_project_role(*PROJECT_CONFIG_ROLES)),
    session: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(get_current_user),
) -> Response:
    member_service.remove_member(session, user, project.id, member_id)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/projects/{project_id}/audit-events", response_model=AuditEventPage)
def list_audit_events(
    action: str | None = None,
    from_time: datetime | None = Query(default=None, alias="from"),
    to_time: datetime | None = Query(default=None, alias="to"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100, alias="pageSize"),
    project: WorkshopProject = Depends(require_project_role(*VIEW_ROLES)),
    user: AuthenticatedUser = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> AuditEventPage:
    events, total = audit.list_events(
        session,
        tenant_id=user.tenant_id,
        project_id=project.id,
        action=action,
        from_time=from_time,
        to_time=to_time,
        page=page,
        page_size=page_size,
    )
    return AuditEventPage(
        items=[AuditEvent.model_validate(e) for e in events],
        page=page,
        page_size=page_size,
        total=total,
    )
