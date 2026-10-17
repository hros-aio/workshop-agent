"""Analysis Run orchestrator (the "Workshop Agent").

Deterministic orchestration around narrow AI calls. Depends only on the AIClient
interface. On any failure it raises; the job marks the run Failed and nothing is
persisted, so no partial proposal is ever created.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from workshop.ai.client import AIClient
from workshop.analysis.candidates import CandidateItem
from workshop.analysis.models import WorkshopAnalysisRun
from workshop.analysis.steps.build_proposal import build_proposal
from workshop.analysis.steps.detect_conflicts import detect_conflicts
from workshop.analysis.steps.detect_duplicates import detect_duplicates
from workshop.analysis.steps.extract_facts import extract_facts
from workshop.analysis.steps.recommend_mapping import recommend_mapping
from workshop.common.enums import EntityType
from workshop.common.errors import DomainValidationError
from workshop.document.models import WorkshopDocumentVersion
from workshop.parsing.models import ExtractedFact
from workshop.parsing.service import parse_document_version
from workshop.project.models import WorkshopProject
from workshop.proposal.models import WorkshopProposal
from workshop.proposal.service import locked_items


def _load_versions(session: Session, version_ids: list[uuid.UUID]) -> list[WorkshopDocumentVersion]:
    if not version_ids:
        return []
    return list(
        session.execute(select(WorkshopDocumentVersion).where(WorkshopDocumentVersion.id.in_(version_ids)))
        .scalars()
        .all()
    )


def run_analysis(
    session: Session, *, project: WorkshopProject, run: WorkshopAnalysisRun, ai: AIClient
) -> WorkshopProposal:
    versions = _load_versions(session, run.document_version_ids)
    if not versions:
        raise DomainValidationError("There are no uploaded documents to analyze")

    facts: list[ExtractedFact] = []
    failures = 0
    for version in versions:
        parsed = parse_document_version(version)
        if parsed.parse_failed:
            failures += 1
            continue
        facts.extend(parsed.features)

    if not facts and failures == len(versions):
        raise DomainValidationError("None of the documents could be parsed")

    locked = locked_items(session, project.id)
    prior_accepted: list[dict[str, object]] = [
        {"entity_key": item.entity_key, "proposed_value": item.proposed_value} for item in locked
    ]

    candidates: list[CandidateItem] = []
    for entity_type_value in project.scoped_entity_types:
        entity_type = EntityType(entity_type_value)
        typed = extract_facts(
            ai,
            entity_type=entity_type,
            facts=facts,
            prior_accepted=prior_accepted,
        )
        for suggestion in recommend_mapping(ai, entity_type=entity_type, items=typed):
            for item in typed:
                if (
                    item.entity_key == suggestion.entity_key
                    and item.proposed_value.get(suggestion.field) == suggestion.from_value
                ):
                    item.proposed_value[suggestion.field] = suggestion.to_value
        candidates.extend(typed)

    candidates = detect_duplicates(candidates)
    candidates = detect_conflicts(candidates)

    proposal = build_proposal(session, project=project, run=run, candidates=candidates, locked=locked)
    project.current_round = run.round_number
    return proposal
