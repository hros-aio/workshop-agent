"""Project membership operations."""

from __future__ import annotations

import uuid

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from workshop.audit import service as audit
from workshop.auth.models import AuthenticatedUser
from workshop.common.enums import AuditAction
from workshop.common.errors import ConflictError, NotFoundError
from workshop.project.models import WorkshopProjectMember
from workshop.project.schemas import MemberCreate


def add_member(
    session: Session,
    user: AuthenticatedUser,
    project_id: uuid.UUID,
    data: MemberCreate,
) -> WorkshopProjectMember:
    existing = (
        session.execute(
            select(WorkshopProjectMember).where(
                WorkshopProjectMember.project_id == project_id,
                WorkshopProjectMember.user_id == data.user_id,
                WorkshopProjectMember.role == data.role.value,
            )
        )
        .scalars()
        .first()
    )
    if existing is not None:
        raise ConflictError("Member already holds this role on the project")

    member = WorkshopProjectMember(
        project_id=project_id,
        user_id=data.user_id,
        role=data.role.value,
        added_by=user.user_id,
    )
    session.add(member)
    session.flush()
    audit.record(
        session,
        tenant_id=user.tenant_id,
        action=AuditAction.MEMBER_ADDED,
        project_id=project_id,
        actor_id=user.user_id,
        entity_type="ProjectMember",
        entity_id=member.id,
        payload={"userId": str(data.user_id), "role": data.role.value},
    )
    return member


def list_members(session: Session, project_id: uuid.UUID) -> list[WorkshopProjectMember]:
    return list(
        session.execute(
            select(WorkshopProjectMember)
            .where(WorkshopProjectMember.project_id == project_id)
            .order_by(WorkshopProjectMember.added_at)
        )
        .scalars()
        .all()
    )


def remove_member(session: Session, user: AuthenticatedUser, project_id: uuid.UUID, member_id: uuid.UUID) -> None:
    member = session.get(WorkshopProjectMember, member_id)
    if member is None or member.project_id != project_id:
        raise NotFoundError("Member not found")
    session.execute(delete(WorkshopProjectMember).where(WorkshopProjectMember.id == member_id))
    audit.record(
        session,
        tenant_id=user.tenant_id,
        action=AuditAction.MEMBER_REMOVED,
        project_id=project_id,
        actor_id=user.user_id,
        entity_type="ProjectMember",
        entity_id=member_id,
        payload={"userId": str(member.user_id), "role": member.role},
    )


def has_any_member(session: Session, project_id: uuid.UUID) -> bool:
    return (
        session.scalar(select(WorkshopProjectMember.id).where(WorkshopProjectMember.project_id == project_id).limit(1))
        is not None
    )
