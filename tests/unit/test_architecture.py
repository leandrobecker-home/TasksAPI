"""Architecture tests: the inner layers must not depend on the web framework (RT02)."""

import ast
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parents[2] / "app"
WEB_FRAMEWORKS = {"fastapi", "starlette", "uvicorn"}

# Layers that hold business rules or data access: no HTTP concerns allowed.
FRAMEWORK_FREE = [
    *sorted((APP_DIR / "services").glob("*.py")),
    *sorted((APP_DIR / "repositories").glob("*.py")),
    *sorted((APP_DIR / "models").glob("*.py")),
    APP_DIR / "errors.py",
]


def imported_top_level_packages(module_path: Path) -> set[str]:
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    packages: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            packages.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            packages.add(node.module.split(".")[0])
    return packages


@pytest.mark.parametrize(
    "module_path",
    FRAMEWORK_FREE,
    ids=lambda path: str(path.relative_to(APP_DIR)),
)
def test_inner_layers_do_not_import_the_web_framework(module_path: Path) -> None:
    assert imported_top_level_packages(module_path).isdisjoint(WEB_FRAMEWORKS)


def test_the_architecture_check_detects_a_web_framework_import(
    tmp_path: Path,
) -> None:
    offender = tmp_path / "offender.py"
    offender.write_text("from fastapi import APIRouter\n", encoding="utf-8")

    assert imported_top_level_packages(offender) & WEB_FRAMEWORKS == {"fastapi"}
