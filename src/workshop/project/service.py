"""Project service: creation, configuration, listing, and lifecycle transitions."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from workshop.audit import service as audit
from workshop.auth.models import AuthenticatedUser
from workshop.common.enums import AuditAction, ProjectRole, ProjectStatus
from workshop.common.errors import ConflictError
from workshop.events import producer
from workshop.project import lifecycle
from workshop.project.models import WorkshopProject, WorkshopProjectMember
from workshop.project.schemas import ProjectCreate, ProjectUpdate


def create_project(session: Session, user: AuthenticatedUser, data: ProjectCreate) -> WorkshopProject:
    project = WorkshopProject(
        tenant_id=user.tenant_id,
        customer_id=data.customer_id,
        name=data.name,
        status=ProjectStatus.SETUP.value,
        ai_provider=data.ai_provider.value,
        scoped_entity_types=[e.value for e in data.scoped_entity_types],
        context_notes=data.context_notes,
        created_by=user.user_id,
    )
    session.add(project)
    session.flush()

    session.add(
        WorkshopProjectMember(
            project_id=project.id,
            user_id=user.user_id,
            role=ProjectRole.CONSULTANT.value,
            added_by=user.user_id,
        )
    )
    audit.record(
        session,
        tenant_id=user.tenant_id,
        action=AuditAction.PROJECT_CREATED,
        project_id=project.id,
        actor_id=user.user_id,
        entity_type="Project",
        entity_id=project.id,
        payload={
            "name": project.name,
            "aiProvider": project.ai_provider,
            "scopedEntityTypes": project.scoped_entity_types,
        },
    )
    return project


def get_project(session: Session, project_id: uuid.UUID, tenant_id: uuid.UUID) -> WorkshopProject:
    from workshop.common.errors import NotFoundError

    project = session.get(WorkshopProject, project_id)
    if project is None or project.tenant_id != tenant_id:
        raise NotFoundError("Project not found")
    return project


def list_projects(
    session: Session,
    user: AuthenticatedUser,
    *,
    status: str | None = None,
    page: int = 1,
    page_size: int = 25,
) -> tuple[list[WorkshopProject], int]:
    member_project_ids = select(WorkshopProjectMember.project_id).where(WorkshopProjectMember.user_id == user.user_id)
    conditions = [WorkshopProject.tenant_id == user.tenant_id]
    if not user.is_platform_admin():
        conditions.append(WorkshopProject.id.in_(member_project_ids))
    if status:
        conditions.append(WorkshopProject.status == status)

    total = session.scalar(select(func.count()).select_from(WorkshopProject).where(*conditions)) or 0
    rows = (
        session.execute(
            select(WorkshopProject)
            .where(*conditions)
            .order_by(WorkshopProject.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        .scalars()
        .all()
    )
    return list(rows), total


def update_project(
    session: Session, user: AuthenticatedUser, project: WorkshopProject, data: ProjectUpdate
) -> WorkshopProject:
    if project.status != ProjectStatus.SETUP.value:
        raise ConflictError("Project configuration can only change while in Setup")
    changed: dict[str, object] = {}
    if data.name is not None:
        project.name = data.name
        changed["name"] = data.name
    if data.scoped_entity_types is not None:
        project.scoped_entity_types = [e.value for e in data.scoped_entity_types]
        changed["scopedEntityTypes"] = project.scoped_entity_types
    if data.ai_provider is not None:
        project.ai_provider = data.ai_provider.value
        changed["aiProvider"] = project.ai_provider
    if data.context_notes is not None:
        project.context_notes = data.context_notes
        changed["contextNotes"] = project.context_notes

    audit.record(
        session,
        tenant_id=user.tenant_id,
        action=AuditAction.PROJECT_UPDATED,
        project_id=project.id,
        actor_id=user.user_id,
        entity_type="Project",
        entity_id=project.id,
        payload=changed,
    )
    return project


def transition(
    session: Session,
    user: AuthenticatedUser,
    project: WorkshopProject,
    target_status: str,
    comment: str | None = None,
) -> WorkshopProject:
    lifecycle.guard_transition(session, project, target_status)
    previous = project.status
    project.status = target_status
    audit.record(
        session,
        tenant_id=user.tenant_id,
        action=AuditAction.STATUS_TRANSITION,
        project_id=project.id,
        actor_id=user.user_id,
        entity_type="Project",
        entity_id=project.id,
        payload={"from": previous, "to": target_status, "comment": comment},
    )
    if target_status == ProjectStatus.FINALIZED.value:
        audit.record(
            session,
            tenant_id=user.tenant_id,
            action=AuditAction.PROJECT_FINALIZED,
            project_id=project.id,
            actor_id=user.user_id,
            entity_type="Project",
            entity_id=project.id,
            payload={},
        )
        producer.emit_finalized(project_id=project.id, tenant_id=user.tenant_id)
    return project
