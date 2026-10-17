"""Build and persist the immutable proposal round.

Locked (accepted/modified) items are carried forward unchanged; rejected and new
items become open proposal items. Persistence happens in one flush so a failure
earlier in the run leaves nothing behind.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from workshop.analysis.candidates import CandidateItem
from workshop.analysis.models import WorkshopAnalysisRun
from workshop.project.models import WorkshopProject
from workshop.proposal.models import WorkshopProposal, WorkshopProposalItem
from workshop.proposal.service import LockedItem


def build_proposal(
    session: Session,
    *,
    project: WorkshopProject,
    run: WorkshopAnalysisRun,
    candidates: list[CandidateItem],
    locked: list[LockedItem],
) -> WorkshopProposal:
    proposal = WorkshopProposal(
        project_id=project.id,
        analysis_run_id=run.id,
        round_number=run.round_number,
    )
    session.add(proposal)
    session.flush()

    locked_keys: set[str] = set()
    for item in locked:
        locked_keys.add(item.entity_key)
        session.add(
            WorkshopProposalItem(
                proposal_id=proposal.id,
                entity_type=item.entity_type,
                entity_key=item.entity_key,
                proposed_value=item.proposed_value,
                explanation=item.explanation,
                confidence=item.confidence,
                is_assumption=item.is_assumption,
                source_refs=item.source_refs,
                carried_from_item_id=item.item_id,
            )
        )

    for candidate in candidates:
        if candidate.entity_key in locked_keys:
            continue
        session.add(
            WorkshopProposalItem(
                proposal_id=proposal.id,
                entity_type=candidate.entity_type.value,
                entity_key=candidate.entity_key,
                proposed_value=candidate.proposed_value,
                explanation=candidate.explanation,
                confidence=candidate.confidence.value,
                is_assumption=candidate.is_assumption,
                has_conflict=candidate.has_conflict,
                conflict_alternatives=candidate.conflict_alternatives,
                source_refs=candidate.source_refs,
                likely_duplicate_of=candidate.likely_duplicate_of,
                carried_from_item_id=candidate.carried_from_item_id,
            )
        )

    session.flush()
    return proposal
