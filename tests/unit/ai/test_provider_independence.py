"""Unit test: the analysis orchestrator depends only on the AIClient Protocol (T110)."""

from __future__ import annotations

import inspect

from workshop.analysis import service as analysis_service


def test_orchestrator_does_not_reference_concrete_providers() -> None:
    source = inspect.getsource(analysis_service)
    assert "openai" not in source.lower()
    assert "providers" not in source
    assert "for_provider" not in source


def test_orchestrator_imports_only_the_interface() -> None:
    assert hasattr(analysis_service, "AIClient")
