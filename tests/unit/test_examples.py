from pathlib import Path

from teamai.config.examples import check_examples, check_teamfile


def test_examples_are_valid_and_small() -> None:
    assert check_examples(Path.cwd()) == []


def test_check_teamfile_rejects_large_example(tmp_path: Path) -> None:
    source = Path("examples/minimal/team.yaml").read_text(encoding="utf-8")
    teamfile = tmp_path / "team.yaml"
    filler = "\n".join("# filler" for _ in range(130))
    teamfile.write_text(f"{source}\n{filler}", encoding="utf-8")

    errors = check_teamfile(teamfile, repo_root=Path.cwd())

    assert len(errors) == 1
    assert "expected <= 120 lines" in errors[0]
