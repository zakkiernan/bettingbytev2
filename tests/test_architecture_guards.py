from __future__ import annotations

import ast
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MODEL_MODULE_NAMES = {
    "opportunity_model.py",
    "pregame_model.py",
    "assists_model.py",
    "rebounds_model.py",
    "threes_model.py",
}


def _load_tree(path: Path) -> ast.AST:
    return ast.parse(path.read_text(encoding="utf-8", errors="ignore"))


def _imports_for_path(path: Path) -> list[tuple[int, str]]:
    imports: list[tuple[int, str]] = []
    for node in ast.walk(_load_tree(path)):
        if isinstance(node, ast.Import):
            imports.extend((node.lineno, alias.name) for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append((node.lineno, node.module))
    return imports


def _format_offenders(offenders: list[tuple[Path, int, str]]) -> str:
    return "\n".join(
        f"{path.relative_to(REPO_ROOT)}:{lineno} imports {module}"
        for path, lineno, module in offenders
    )


def test_analytics_does_not_import_api() -> None:
    offenders: list[tuple[Path, int, str]] = []
    for path in (REPO_ROOT / "analytics").rglob("*.py"):
        for lineno, module in _imports_for_path(path):
            if module.split(".")[0] == "api":
                offenders.append((path, lineno, module))

    assert not offenders, _format_offenders(offenders)


def test_ingestion_does_not_import_api() -> None:
    offenders: list[tuple[Path, int, str]] = []
    for path in (REPO_ROOT / "ingestion").rglob("*.py"):
        for lineno, module in _imports_for_path(path):
            if module.split(".")[0] == "api":
                offenders.append((path, lineno, module))

    assert not offenders, _format_offenders(offenders)


def test_model_modules_do_not_import_ingestion() -> None:
    offenders: list[tuple[Path, int, str]] = []
    for path in (REPO_ROOT / "analytics").rglob("*.py"):
        if path.name not in MODEL_MODULE_NAMES:
            continue
        for lineno, module in _imports_for_path(path):
            if module.split(".")[0] == "ingestion":
                offenders.append((path, lineno, module))

    assert not offenders, _format_offenders(offenders)
