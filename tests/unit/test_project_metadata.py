from pathlib import Path


def test_required_oss_metadata_files_exist() -> None:
    required_files = [
        "README.md",
        "LICENSE",
        "CHANGELOG.md",
        "SECURITY.md",
        "CONTRIBUTING.md",
        "CODE_OF_CONDUCT.md",
        "GOVERNANCE.md",
        ".github/pull_request_template.md",
        ".github/ISSUE_TEMPLATE/bug_report.md",
        ".github/ISSUE_TEMPLATE/feature_request.md",
        ".github/ISSUE_TEMPLATE/config.yml",
        "pyproject.toml",
    ]

    for path in required_files:
        assert Path(path).is_file()


def test_license_matches_project_metadata() -> None:
    pyproject = Path("pyproject.toml").read_text(encoding="utf-8")
    license_text = Path("LICENSE").read_text(encoding="utf-8")

    assert 'license = { text = "MIT" }' in pyproject
    assert license_text.startswith("MIT License")


def test_pull_request_template_keeps_runtime_safety_checks() -> None:
    template = Path(".github/pull_request_template.md").read_text(encoding="utf-8")

    assert "No unbounded loops or retries were added." in template
    assert "Side effects still require explicit approval." in template
    assert "Workspace boundaries and redaction rules are preserved." in template
