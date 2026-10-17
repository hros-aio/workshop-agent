"""Export endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from workshop.auth.dependencies import get_current_user, get_db, require_project_role
from workshop.auth.models import AuthenticatedUser
from workshop.common.enums import EXPORT_ROLES, VIEW_ROLES
from workshop.export import service
from workshop.export.schemas import DownloadUrl, ExportPackage
from workshop.project.models import WorkshopProject
from workshop.settings import get_settings

router = APIRouter(tags=["Export"])


@router.post(
    "/projects/{project_id}/exports",
    response_model=ExportPackage,
    status_code=status.HTTP_201_CREATED,
)
def create_export(
    project: WorkshopProject = Depends(require_project_role(*EXPORT_ROLES)),
    session: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(get_current_user),
) -> ExportPackage:
    package = service.create_export(session, user, project)
    session.commit()
    return ExportPackage.model_validate(package)


@router.get("/projects/{project_id}/exports", response_model=list[ExportPackage])
def list_exports(
    project: WorkshopProject = Depends(require_project_role(*VIEW_ROLES)),
    session: Session = Depends(get_db),
) -> list[ExportPackage]:
    return [ExportPackage.model_validate(p) for p in service.list_exports(session, project.id)]


@router.get(
    "/projects/{project_id}/exports/{version_number}",
    response_model=ExportPackage,
)
def get_export(
    version_number: int,
    project: WorkshopProject = Depends(require_project_role(*VIEW_ROLES)),
    session: Session = Depends(get_db),
) -> ExportPackage:
    return ExportPackage.model_validate(service.get_export(session, project.id, version_number))


@router.get(
    "/projects/{project_id}/exports/{version_number}/files/{file_name}/download-url",
    response_model=DownloadUrl,
)
def get_export_file_download_url(
    version_number: int,
    file_name: str,
    project: WorkshopProject = Depends(require_project_role(*VIEW_ROLES)),
    session: Session = Depends(get_db),
) -> DownloadUrl:
    package = service.get_export(session, project.id, version_number)
    url = service.file_download_url(package, file_name)
    return DownloadUrl(url=url, expires_in=get_settings().s3_presign_ttl_seconds)
