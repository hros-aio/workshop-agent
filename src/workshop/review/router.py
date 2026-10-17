"""Review endpoints: record and list decisions on proposal items."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from workshop.auth.dependencies import get_current_user, get_db, require_project_role
from workshop.auth.models import AuthenticatedUser
from workshop.common.enums import REVIEW_ROLES, VIEW_ROLES
from workshop.project.models import WorkshopProject
from workshop.review import service
from workshop.review.schemas import Decision, DecisionCreate

router = APIRouter(tags=["Review"])


@router.post(
    "/projects/{project_id}/proposal-items/{item_id}/decisions",
    response_model=Decision,
    status_code=status.HTTP_201_CREATED,
)
def record_decision(
    item_id: uuid.UUID,
    data: DecisionCreate,
    project: WorkshopProject = Depends(require_project_role(*REVIEW_ROLES)),
    session: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(get_current_user),
) -> Decision:
    item = service.get_item_for_project(session, project.id, item_id)
    decision = service.record_decision(session, user, project, item, data)
    session.commit()
    return Decision.model_validate(decision)


@router.get(
    "/projects/{project_id}/proposal-items/{item_id}/decisions",
    response_model=list[Decision],
)
def list_decisions(
    item_id: uuid.UUID,
    project: WorkshopProject = Depends(require_project_role(*VIEW_ROLES)),
    session: Session = Depends(get_db),
) -> list[Decision]:
    service.get_item_for_project(session, project.id, item_id)
    return [Decision.model_validate(d) for d in service.list_decisions(session, item_id)]
