"""Document endpoints."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from workshop.auth.dependencies import get_current_user, get_db, require_project_role
from workshop.auth.models import AuthenticatedUser
from workshop.common.enums import UPLOAD_ROLES, VIEW_ROLES, DocumentStatus
from workshop.document import service
from workshop.document.schemas import (
    Document,
    DocumentCreate,
    DocumentDetail,
    DocumentUploadTicket,
    DocumentVersion,
    DocumentVersionComplete,
    DocumentVersionCreate,
    DownloadUrl,
)
from workshop.project.models import WorkshopProject
from workshop.settings import get_settings

router = APIRouter(tags=["Documents"])


@router.post(
    "/projects/{project_id}/documents",
    response_model=DocumentUploadTicket,
    status_code=status.HTTP_201_CREATED,
)
def create_document(
    data: DocumentCreate,
    project: WorkshopProject = Depends(require_project_role(*UPLOAD_ROLES)),
    session: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(get_current_user),
) -> DocumentUploadTicket:
    _, ticket = service.create_document(session, user, project, data)
    session.commit()
    return ticket


@router.get("/projects/{project_id}/documents", response_model=list[Document])
def list_documents(
    status_filter: DocumentStatus | None = Query(default=None, alias="status"),
    project: WorkshopProject = Depends(require_project_role(*VIEW_ROLES)),
    session: Session = Depends(get_db),
) -> list[Document]:
    documents = service.list_documents(session, project.id, status=status_filter.value if status_filter else None)
    return [Document.model_validate(d) for d in documents]


@router.get("/projects/{project_id}/documents/{document_id}", response_model=DocumentDetail)
def get_document(
    document_id: uuid.UUID,
    project: WorkshopProject = Depends(require_project_role(*VIEW_ROLES)),
    session: Session = Depends(get_db),
) -> DocumentDetail:
    document = service.get_document(session, project.id, document_id)
    return DocumentDetail.model_validate(
        {
            "id": document.id,
            "project_id": document.project_id,
            "document_type": document.document_type,
            "status": document.status,
            "current_version_id": document.current_version_id,
            "notes": document.notes,
            "created_by": document.created_by,
            "created_at": document.created_at,
            "versions": [DocumentVersion.model_validate(v) for v in document.versions],
        }
    )


@router.post(
    "/projects/{project_id}/documents/{document_id}/versions",
    response_model=DocumentUploadTicket,
    status_code=status.HTTP_201_CREATED,
)
def create_document_version(
    document_id: uuid.UUID,
    data: DocumentVersionCreate,
    project: WorkshopProject = Depends(require_project_role(*UPLOAD_ROLES)),
    session: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(get_current_user),
) -> DocumentUploadTicket:
    document = service.get_document(session, project.id, document_id)
    ticket = service.add_version(session, user, project, document, data)
    session.commit()
    return ticket


@router.post(
    "/projects/{project_id}/documents/{document_id}/versions/{version_id}/complete",
    response_model=DocumentVersion,
)
def complete_document_version(
    document_id: uuid.UUID,
    version_id: uuid.UUID,
    data: DocumentVersionComplete,
    project: WorkshopProject = Depends(require_project_role(*UPLOAD_ROLES)),
    session: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(get_current_user),
) -> DocumentVersion:
    document = service.get_document(session, project.id, document_id)
    version = service.get_version(session, document, version_id)
    updated = service.complete_version(session, user, project.id, document, version, data.checksum_sha256)
    session.commit()
    return DocumentVersion.model_validate(updated)


@router.get(
    "/projects/{project_id}/documents/{document_id}/versions/{version_id}/download-url",
    response_model=DownloadUrl,
)
def get_document_version_download_url(
    document_id: uuid.UUID,
    version_id: uuid.UUID,
    project: WorkshopProject = Depends(require_project_role(*VIEW_ROLES)),
    session: Session = Depends(get_db),
) -> DownloadUrl:
    document = service.get_document(session, project.id, document_id)
    version = service.get_version(session, document, version_id)
    settings = get_settings()
    return DownloadUrl(
        url=service.version_download_url(version),
        expires_at=datetime.now(UTC) + timedelta(seconds=settings.s3_presign_ttl_seconds),
    )
