from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    _ensure_src_on_path(REPO_ROOT)
    from teamai.config.examples import check_examples

    errors = check_examples(REPO_ROOT)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print("example Teamfiles are valid")
    return 0


def _ensure_src_on_path(repo_root: Path) -> None:
    src_root = repo_root / "src"
    src_root_text = str(src_root)
    if src_root_text not in sys.path:
        sys.path.insert(0, src_root_text)


if __name__ == "__main__":
    raise SystemExit(main())
