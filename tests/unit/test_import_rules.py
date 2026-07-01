import importlib.util
from pathlib import Path
from typing import Protocol, cast


class ImportRuleModule(Protocol):
    def check_import_rules(self) -> list[str]: ...


def test_core_import_rules_are_valid() -> None:
    module = _load_check_import_rules_module()

    assert module.check_import_rules() == []


def _load_check_import_rules_module() -> ImportRuleModule:
    path = Path("scripts/check_import_rules.py")
    spec = importlib.util.spec_from_file_location("check_import_rules", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return cast(ImportRuleModule, module)
