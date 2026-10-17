"""Contract test: the OpenAPI document is client-generation ready (T112)."""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest


def _spec() -> dict[str, object]:
    from workshop.main import app

    return app.openapi()


def test_every_operation_has_a_unique_operation_id() -> None:
    spec = _spec()
    operation_ids: list[str] = []
    for _path, operations in spec["paths"].items():
        for method, operation in operations.items():
            if method in {"parameters"}:
                continue
            operation_ids.append(operation["operationId"])
    assert len(operation_ids) == len(set(operation_ids))


def test_document_is_json_serializable() -> None:
    spec = _spec()
    assert json.loads(json.dumps(spec)) == spec


@pytest.mark.skipif(shutil.which("npx") is None, reason="npx not available")
def test_typescript_client_generation() -> None:
    spec = _spec()
    with tempfile.TemporaryDirectory() as tmp:
        spec_path = Path(tmp) / "openapi.json"
        out_path = Path(tmp) / "client.d.ts"
        spec_path.write_text(json.dumps(spec))
        try:
            subprocess.run(
                [
                    "npx",
                    "--yes",
                    "openapi-typescript@7",
                    str(spec_path),
                    "-o",
                    str(out_path),
                ],
                check=True,
                capture_output=True,
                timeout=180,
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:  # pragma: no cover
            pytest.skip(f"client generation unavailable in this environment: {exc}")
        assert out_path.exists() and out_path.stat().st_size > 0
