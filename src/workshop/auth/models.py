"""Authenticated user context derived from the platform JWT."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from workshop.common.enums import ProjectRole


@dataclass(frozen=True)
class AuthenticatedUser:
    user_id: uuid.UUID
    tenant_id: uuid.UUID
    global_roles: frozenset[str] = field(default_factory=frozenset)

    def is_platform_admin(self) -> bool:
        return bool({"admin", "platform_admin", "super_admin"} & set(self.global_roles))

    def has_project_role(self, roles: tuple[ProjectRole, ...]) -> bool:
        if self.is_platform_admin():
            return True
        return any(role.value in self.global_roles for role in roles)
