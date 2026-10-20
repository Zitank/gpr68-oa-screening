from __future__ import annotations

from pathlib import Path

from tools.check_evidence import main, resolve_root

VAULT = Path(__file__).resolve().parents[3]


def _note(access: str, body: str = "") -> str:
    return f"---\nkey: demo2019paper\naccess: {access}\n---\n\n# demo\n\n{body}\n"


def _vault(
    tmp_path: Path,
    access: str = "oa-cc",
    source: str | None = "the binding affinity is 12 nm.",
) -> Path:
    (tmp_path / "lit").mkdir()
    if source is not None:
        sources = tmp_path / "sources"
        sources.mkdir()
        (sources / "demo2019paper.md").write_text(source, encoding="utf-8")
    (tmp_path / "lit" / "@demo2019paper.md").write_text(_note(access), encoding="utf-8")
    return tmp_path


def _write_note(root: Path, body: str) -> None:
    (root / "lit" / "@demo2019paper.md").write_text(_note("oa-cc", body), encoding="utf-8")


def test_default_root_is_the_project_folder(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.delenv("EVIDENCE_ROOT", raising=False)
    root = resolve_root(None)
    assert root == VAULT
    assert (root / "sources").is_dir()
    assert (root / "lit").is_dir()


def test_five_papers_have_no_verified_cards(capsys) -> None:  # type: ignore[no-untyped-def]
    code = main(["--root", str(VAULT), "--list"])
    out = capsys.readouterr().out
    assert code == 0
    assert "0 quote-verified" in out
    assert "0 human-read" in out
    assert "0 quote callouts" in out
    assert "0 FAIL" in out
    assert "0 bib keys" in out


def test_verbatim_callout_passes(tmp_path: Path, capsys) -> None:  # type: ignore[no-untyped-def]
    root = _vault(tmp_path)
    _write_note(root, "> [!quote] §1\n> the binding affinity is 12 nm.\n")
    assert main(["--root", str(root)]) == 0
    assert "1 quote callouts" in capsys.readouterr().out


def test_missing_quote_fails(tmp_path: Path, capsys) -> None:  # type: ignore[no-untyped-def]
    root = _vault(tmp_path)
    _write_note(root, "> [!quote] §1\n> this sentence is not in the extract.\n")
    assert main(["--root", str(root)]) == 1
    assert "quote not found verbatim" in capsys.readouterr().out


def test_illegal_access_fails(tmp_path: Path, capsys) -> None:  # type: ignore[no-untyped-def]
    root = _vault(tmp_path, access="public-pdf")
    assert main(["--root", str(root)]) == 1
    err = capsys.readouterr().out
    assert "not in" in err
    assert "oa-cc" in err


def test_no_ai_source_on_disk_fails(tmp_path: Path, capsys) -> None:  # type: ignore[no-untyped-def]
    root = _vault(tmp_path, access="ieee-no-ai")
    body = "> [!quote] p. 6\n> the binding affinity is 12 nm.\n"
    (root / "lit" / "@demo2019paper.md").write_text(_note("ieee-no-ai", body), encoding="utf-8")
    assert main(["--root", str(root)]) == 1
    assert "no-AI source" in capsys.readouterr().out


def test_missing_lit_fails(tmp_path: Path) -> None:
    assert main(["--root", str(tmp_path)]) == 1


def test_repo_references_bib_satisfies_the_key(tmp_path: Path, capsys) -> None:  # type: ignore[no-untyped-def]
    root = _vault(tmp_path)
    bib = root / "repo" / "governance"
    bib.mkdir(parents=True)
    (bib / "references.bib").write_text("@article{demo2019paper,\n  title = {x},\n}\n", encoding="utf-8")
    code = main(["--root", str(root)])
    out = capsys.readouterr().out
    assert code == 0
    assert "1 bib keys" in out
    assert "not in bib yet" not in out
