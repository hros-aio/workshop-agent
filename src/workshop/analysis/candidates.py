"""In-memory candidate proposal items used while building a round.

Nothing here is persisted; the orchestrator persists only after every step
succeeds so a failure never leaves a partial proposal.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from workshop.common.enums import Confidence, EntityType


@dataclass
class CandidateItem:
    entity_type: EntityType
    entity_key: str
    proposed_value: dict[str, Any]
    explanation: str
    confidence: Confidence
    is_assumption: bool = False
    source_refs: list[dict[str, Any]] = field(default_factory=list)
    has_conflict: bool = False
    conflict_alternatives: list[dict[str, Any]] | None = None
    likely_duplicate_of: str | None = None
    carried_from_item_id: uuid.UUID | None = None
