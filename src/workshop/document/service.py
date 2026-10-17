"""Document service: versioned uploads, supersession, downloads."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from workshop.audit import service as audit
from workshop.auth.models import AuthenticatedUser
from workshop.common.enums import AuditAction, DocumentStatus, UploadStatus
from workshop.common.errors import ConflictError, NotFoundError
from workshop.document import storage
from workshop.document.models import WorkshopDocument, WorkshopDocumentVersion
from workshop.document.schemas import (
    DocumentCreate,
    DocumentUploadTicket,
    DocumentVersionCreate,
)
from workshop.project.models import WorkshopProject
from workshop.settings import get_settings


def _ticket(*, document_id: uuid.UUID, version: WorkshopDocumentVersion, content_type: str) -> DocumentUploadTicket:
    settings = get_settings()
    url = storage.presigned_put_url(version.storage_key, content_type=content_type)
    return DocumentUploadTicket(
        document_id=document_id,
        version_id=version.id,
        upload_url=url,
        storage_key=version.storage_key,
        expires_at=datetime.now(UTC) + timedelta(seconds=settings.s3_presign_ttl_seconds),
    )


def create_document(
    session: Session,
    user: AuthenticatedUser,
    project: WorkshopProject,
    data: DocumentCreate,
) -> tuple[WorkshopDocument, DocumentUploadTicket]:
    document = WorkshopDocument(
        project_id=project.id,
        document_type=data.document_type,
        status=DocumentStatus.UPLOADED.value,
        notes=data.notes,
        created_by=user.user_id,
    )
    session.add(document)
    session.flush()

    version = _new_version(
        session,
        user=user,
        document=document,
        tenant_id=project.tenant_id,
        project_id=project.id,
        file_name=data.file_name,
        mime_type=data.mime_type,
        size_bytes=data.size_bytes,
        version_number=1,
    )
    document.current_version_id = version.id
    audit.record(
        session,
        tenant_id=user.tenant_id,
        action=AuditAction.DOCUMENT_UPLOADED,
        project_id=project.id,
        actor_id=user.user_id,
        entity_type="Document",
        entity_id=document.id,
        payload={
            "documentType": document.document_type,
            "fileName": data.file_name,
            "versionNumber": 1,
        },
    )
    session.flush()
    return document, _ticket(document_id=document.id, version=version, content_type=data.mime_type)


def add_version(
    session: Session,
    user: AuthenticatedUser,
    project: WorkshopProject,
    document: WorkshopDocument,
    data: DocumentVersionCreate,
) -> DocumentUploadTicket:
    if document.status == DocumentStatus.SUPERSEDED.value:
        raise ConflictError("Cannot add a version to a superseded document")

    next_number = (
        session.scalar(
            select(func.max(WorkshopDocumentVersion.version_number)).where(
                WorkshopDocumentVersion.document_id == document.id
            )
        )
        or 0
    ) + 1
    version = _new_version(
        session,
        user=user,
        document=document,
        tenant_id=project.tenant_id,
        project_id=project.id,
        file_name=data.file_name,
        mime_type=data.mime_type,
        size_bytes=data.size_bytes,
        version_number=next_number,
    )
    previous = (
        session.get(WorkshopDocumentVersion, document.current_version_id) if document.current_version_id else None
    )
    if previous is not None:
        previous.superseded_at = datetime.now(UTC)
    document.current_version_id = version.id
    document.status = DocumentStatus.UPLOADED.value
    if data.notes is not None:
        document.notes = data.notes

    audit.record(
        session,
        tenant_id=user.tenant_id,
        action=AuditAction.DOCUMENT_SUPERSEDED,
        project_id=project.id,
        actor_id=user.user_id,
        entity_type="Document",
        entity_id=document.id,
        payload={"previousVersionId": str(previous.id) if previous else None, "newVersionNumber": next_number},
    )
    session.flush()
    return _ticket(document_id=document.id, version=version, content_type=data.mime_type)


def _new_version(
    session: Session,
    *,
    user: AuthenticatedUser,
    document: WorkshopDocument,
    tenant_id: uuid.UUID,
    project_id: uuid.UUID,
    file_name: str,
    mime_type: str,
    size_bytes: int,
    version_number: int,
) -> WorkshopDocumentVersion:
    version_id = uuid.uuid4()
    key = storage.build_key(
        tenant_id=tenant_id,
        project_id=project_id,
        document_id=document.id,
        version_id=version_id,
        file_name=file_name,
    )
    version = WorkshopDocumentVersion(
        id=version_id,
        document_id=document.id,
        version_number=version_number,
        storage_key=key,
        file_name=file_name,
        mime_type=mime_type,
        size_bytes=size_bytes,
        upload_status=UploadStatus.PENDING.value,
        uploaded_by=user.user_id,
    )
    session.add(version)
    session.flush()
    return version


def complete_version(
    session: Session,
    user: AuthenticatedUser,
    project_id: uuid.UUID,
    document: WorkshopDocument,
    version: WorkshopDocumentVersion,
    checksum_sha256: str,
) -> WorkshopDocumentVersion:
    if not storage.object_exists(version.storage_key):
        raise ConflictError("Uploaded object was not found in storage")
    version.checksum_sha256 = checksum_sha256
    version.upload_status = UploadStatus.UPLOADED.value
    version.uploaded_at = datetime.now(UTC)
    document.status = DocumentStatus.UPLOADED.value
    session.flush()
    return version


def list_documents(session: Session, project_id: uuid.UUID, *, status: str | None = None) -> list[WorkshopDocument]:
    conditions = [WorkshopDocument.project_id == project_id]
    if status:
        conditions.append(WorkshopDocument.status == status)
    return list(
        session.execute(select(WorkshopDocument).where(*conditions).order_by(WorkshopDocument.created_at))
        .scalars()
        .all()
    )


def get_document(session: Session, project_id: uuid.UUID, document_id: uuid.UUID) -> WorkshopDocument:
    document = session.get(WorkshopDocument, document_id)
    if document is None or document.project_id != project_id:
        raise NotFoundError("Document not found")
    return document


def get_version(session: Session, document: WorkshopDocument, version_id: uuid.UUID) -> WorkshopDocumentVersion:
    version = session.get(WorkshopDocumentVersion, version_id)
    if version is None or version.document_id != document.id:
        raise NotFoundError("Document version not found")
    return version


def version_download_url(version: WorkshopDocumentVersion) -> str:
    return storage.presigned_get_url(version.storage_key)


def active_version_ids(session: Session, project_id: uuid.UUID) -> list[uuid.UUID]:
    """Version ids of documents whose current version was successfully uploaded."""
    documents = session.execute(
        select(WorkshopDocument).where(
            WorkshopDocument.project_id == project_id,
            WorkshopDocument.status != DocumentStatus.SUPERSEDED.value,
        )
    ).scalars()
    ids: list[uuid.UUID] = []
    for document in documents:
        if document.current_version_id is None:
            continue
        version = session.get(WorkshopDocumentVersion, document.current_version_id)
        if version is not None and version.upload_status == UploadStatus.UPLOADED.value:
            ids.append(version.id)
    return ids
