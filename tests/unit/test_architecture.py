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


# --- queries live only in the repositories (RT03) --------------------------------

QUERY_FUNCTIONS = {"select", "text"}
QUERY_METHODS = {"exec", "execute", "query", "scalar", "scalars"}

# Repositories hold the queries; ``db.py`` only configures connections.
MAY_QUERY = {APP_DIR / "db.py", *(APP_DIR / "repositories").glob("*.py")}
MUST_NOT_QUERY = [
    path for path in sorted(APP_DIR.rglob("*.py")) if path not in MAY_QUERY
]


def query_calls(module_path: Path) -> list[str]:
    """Return the data-access calls found in a module, e.g. ``select`` or ``exec``."""
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    found: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        function = node.func
        if isinstance(function, ast.Name) and function.id in QUERY_FUNCTIONS:
            found.append(function.id)
        elif isinstance(function, ast.Attribute) and function.attr in QUERY_METHODS:
            found.append(function.attr)
    return found


@pytest.mark.parametrize(
    "module_path",
    MUST_NOT_QUERY,
    ids=lambda path: str(path.relative_to(APP_DIR)),
)
def test_only_the_repositories_query_the_database(module_path: Path) -> None:
    assert query_calls(module_path) == []


def test_the_repositories_do_contain_queries() -> None:
    """Guards the check above against matching nothing at all."""
    repository_calls = [
        call
        for path in (APP_DIR / "repositories").glob("*.py")
        for call in query_calls(path)
    ]

    assert {"select", "exec"} <= set(repository_calls)


def test_the_query_check_detects_a_query_outside_the_repositories(
    tmp_path: Path,
) -> None:
    offender = tmp_path / "offender.py"
    offender.write_text(
        "def run(session):\n"
        "    session.exec(select(Task))\n"
        "    session.execute(text('SELECT 1'))\n",
        encoding="utf-8",
    )

    assert sorted(query_calls(offender)) == ["exec", "execute", "select", "text"]
