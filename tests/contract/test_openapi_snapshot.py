"""Contract test: the generated OpenAPI document matches the committed contract (T111).

The committed contract uses camelCase path parameters (`{projectId}`) while the
FastAPI implementation uses snake_case (`{project_id}`); path parameters are
normalized before comparison so the structural shape is still asserted.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

_CONTRACT = Path(__file__).resolve().parents[2] / "specs/001-workshop-discovery/contracts/openapi.yaml"
_PARAM = re.compile(r"\{([A-Za-z]+)\}")


def _snake(name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def _normalize_path(path: str) -> str:
    return _PARAM.sub(lambda m: "{" + _snake(m.group(1)) + "}", path)


def _generated_spec() -> dict[str, object]:
    from workshop.main import app

    return app.openapi()


def test_service_paths_cover_the_contract() -> None:
    contract = yaml.safe_load(_CONTRACT.read_text())
    generated = _generated_spec()

    contract_paths = {_normalize_path(p) for p in contract["paths"] if p.startswith("/projects")}
    generated_paths = {p for p in generated["paths"] if p.startswith("/projects")}

    assert contract_paths == generated_paths


def test_contract_methods_are_implemented() -> None:
    contract = yaml.safe_load(_CONTRACT.read_text())
    generated = _generated_spec()

    for path, operations in contract["paths"].items():
        if not path.startswith("/projects"):
            continue
        normalized = _normalize_path(path)
        for method in operations:
            if method in {"parameters", "summary", "description"}:
                continue
            assert method in generated["paths"][normalized], f"{method.upper()} {path} missing"


def test_health_endpoint_present() -> None:
    assert "/health" in _generated_spec()["paths"]
