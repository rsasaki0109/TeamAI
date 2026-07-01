from __future__ import annotations

import ast
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CORE_ROOT = REPO_ROOT / "src" / "teamai" / "core"


def check_import_rules(core_root: Path = CORE_ROOT) -> list[str]:
    errors: list[str] = []
    for path in sorted(core_root.glob("*.py")):
        errors.extend(_check_core_module(path))
    return errors


def main() -> int:
    errors = check_import_rules()
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print("import rules are valid")
    return 0


def _check_core_module(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    errors: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if _is_forbidden_teamai_import(module):
                errors.append(_format_error(path, node.lineno, module))
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if _is_forbidden_teamai_import(alias.name):
                    errors.append(_format_error(path, node.lineno, alias.name))
    return errors


def _is_forbidden_teamai_import(module: str) -> bool:
    return module.startswith("teamai.") and not module.startswith("teamai.core")


def _format_error(path: Path, line: int, module: str) -> str:
    relative_path = path.relative_to(REPO_ROOT).as_posix()
    return f"{relative_path}:{line}: core must not import {module}"


if __name__ == "__main__":
    raise SystemExit(main())
