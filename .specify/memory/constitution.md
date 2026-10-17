<!--
Sync Impact Report (temporary; remove before commit)
Version change: (none) -> 1.0.0
Modified principles: none (initial adoption)
Added sections: Core Principles I-IX, Engineering Standards, Development Workflow, Governance
Removed sections: none
Deferred TODOs: none
-->

# Workshop Module Constitution

## Core Principles

### I. AI Proposes, Humans Decide
AI MUST NOT modify production HRMS data. AI output MUST be stored only as proposals. No value
MAY reach an export unless a human has explicitly accepted or modified it, and every such
decision MUST record the user and timestamp.
Rationale: the module's value is trusted discovery, which depends on human accountability.

### II. Every Fact Is Traceable
Every proposed value MUST reference its source document and location (file, page or sheet,
row or cell), or MUST be explicitly flagged as an Assumption. An inferred value MUST NOT be
presented as an extracted fact. Any exported cell MUST be answerable with "where did this
come from and who approved it".

### III. Conflicts Are Surfaced, Never Silently Resolved
When sources disagree, the system MUST show every alternative with its source and MUST NOT
choose a winner. A conflict is resolved only by a recorded human decision.

### IV. Correctness Over Speed
Performance and scalability MUST NOT drive design decisions. Where accuracy and speed
conflict, accuracy wins. Workshops run a few times per year per customer.

### V. YAGNI and Simplicity
A component MUST have a present, documented business reason. The project MUST NOT add
speculative features, configurability, a workflow engine, a multi-agent framework, a vector
database, event sourcing, CQRS, or any service beyond this single service. The lifecycle is
a fixed enum with guard functions.

### VI. Deterministic Code Before AI
Parsing, conflict detection, duplicate detection, validation, diffing, and export MUST be
deterministic code. AI MAY be used only for semantic reasoning: reading unstructured
documents, proposing mappings and normalization, and writing explanations.

### VII. Insert-Only History
Documents, proposal rounds, and decisions MUST be versioned. They MUST NOT be edited in
place or deleted; superseding and new versions are used instead. The current accepted
dataset MUST be derived from history, not stored as mutable state.

### VIII. Fail Loudly
Malformed or schema-invalid AI output MUST fail the Analysis Run. It MUST NOT be coerced,
repaired by guesswork, or persisted as a partial proposal. Export MUST be all-or-nothing.

### IX. Reuse Mature Libraries
Parsing, OCR, Excel reading and writing, and validation MUST use mature open-source
libraries. The project MUST NOT build its own parsers, OCR, or agent framework.

## Engineering Standards

- Python 3.12 with type hints on all code; mypy MUST pass.
- pydantic validation MUST be applied at every boundary (API input, AI response, file
  extraction output, export input).
- The workflow logic MUST depend only on the `AIClient` interface, never on a specific
  provider.
- Tests are REQUIRED for validation rules, lifecycle state transitions, and AI-response
  parsing.
- A small fixed set of sample documents MUST be maintained as AI regression tests, runnable
  against each supported provider.
- Exported files MUST match the HRMS standard import templates exactly.

## Development Workflow

- Every change MUST be traceable to a requirement in the spec.
- A fake `AIClient` MUST exist so the full flow is testable without a real model.
- Plans and tasks MUST be checked against this constitution; any violation MUST be
  justified in writing in the plan's complexity section.
- Merge requires passing lint (ruff), type checks, and the required tests.

## Governance

This constitution supersedes other practices. Amendments require a written proposal, an
updated Sync Impact Report, and a version bump. Versioning follows semantic rules: MAJOR for
removed or redefined principles, MINOR for new or materially expanded principles, PATCH for
clarifications. Compliance MUST be reviewed in every plan and pull request.

**Version**: 1.0.0 | **Ratified**: 2026-10-17 | **Last Amended**: 2026-10-17