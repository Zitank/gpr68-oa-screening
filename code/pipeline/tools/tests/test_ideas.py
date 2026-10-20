from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.ideas import main


def _fill_falsify(card: Path, text: str) -> None:
    raw = card.read_text(encoding="utf-8")
    marker = "## What would falsify it"
    start = raw.index(marker)
    header = raw[start : raw.index("\n", start)]
    next_heading = raw.index("\n## ", start + 1)
    card.write_text(raw[:start] + header + "\n\n" + text + "\n" + raw[next_heading + 1 :], encoding="utf-8")


def _events(root: Path) -> bytes:
    return (root / "ideas" / "events.jsonl").read_bytes()


def test_add_assigns_ids_and_writes_cards(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--root", str(tmp_path), "add", "alpha"]) == 0
    assert capsys.readouterr().out.strip() == "T-001"
    card = tmp_path / "ideas" / "cards" / "T-001.md"
    text = card.read_text(encoding="utf-8")
    assert "id: T-001" in text
    assert "type: SPECULATION" in text
    assert "status: untested" in text
    assert main(["--root", str(tmp_path), "add", "beta"]) == 0
    assert capsys.readouterr().out.strip() == "T-002"
    assert (tmp_path / "ideas" / "cards" / "T-002.md").is_file()


def test_status_queued_needs_falsify_then_ingest(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--root", str(tmp_path), "add", "first idea"]) == 0
    capsys.readouterr()
    before = _events(tmp_path)
    assert main(["--root", str(tmp_path), "status", "T-001", "queued"]) == 1
    err = capsys.readouterr().err
    assert "What would falsify it" in err
    assert _events(tmp_path) == before
    card = tmp_path / "ideas" / "cards" / "T-001.md"
    _fill_falsify(card, "accuracy does not change when the penalty is removed")
    assert main(["--root", str(tmp_path), "ingest", "T-001"]) == 0
    assert main(["--root", str(tmp_path), "status", "T-001", "queued"]) == 0
    assert "status: queued" in card.read_text(encoding="utf-8")
    edited = json.loads(_events(tmp_path).decode().splitlines()[1])
    assert edited["event"] == "edited"
    assert "falsify" in edited["data"]


def test_scout_cannot_set_evidence_above_mechanism(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = main(
        ["--root", str(tmp_path), "add", "too strong", "--by", "scout", "--evidence", "literature-supported"]
    )
    assert code == 1
    assert "mechanism-argued" in capsys.readouterr().err
    assert not (tmp_path / "ideas" / "events.jsonl").exists()
    assert main(["--root", str(tmp_path), "add", "needs a cite", "--evidence", "literature-supported"]) == 1
    assert main(["--root", str(tmp_path), "add", "needs a run", "--evidence", "pilot-supported"]) == 1
    capsys.readouterr()
    assert (
        main(["--root", str(tmp_path), "add", "argued", "--by", "scout", "--evidence", "mechanism-argued"])
        == 0
    )
    card = (tmp_path / "ideas" / "cards" / "T-001.md").read_text(encoding="utf-8")
    assert "evidence: mechanism-argued" in card
    assert "agent-proposed, unreviewed" in card


def test_promote_question_keeps_evidence(tmp_path: Path) -> None:
    questions = tmp_path / "governance" / "questions"
    questions.mkdir(parents=True)
    (questions / "Q-001.md").write_text("keep\n", encoding="utf-8")
    assert main(["--root", str(tmp_path), "add", "the effect may be real"]) == 0
    before = _events(tmp_path)
    assert main(["--root", str(tmp_path), "promote", "T-001", "--as", "question"]) == 0
    after = _events(tmp_path)
    assert after.startswith(before)
    assert (questions / "Q-001.md").read_text(encoding="utf-8") == "keep\n"
    stub = (questions / "Q-002.md").read_text(encoding="utf-8")
    assert "id: Q-002" in stub
    assert "state: SEED" in stub
    assert "TBD (human)" in stub
    card = (tmp_path / "ideas" / "cards" / "T-001.md").read_text(encoding="utf-8")
    assert "evidence: speculative" in card
    promoted = json.loads(after.decode().splitlines()[-1])
    assert promoted["event"] == "promoted"
    assert "evidence" not in promoted["data"]


def test_promote_study_stub(tmp_path: Path) -> None:
    existing = tmp_path / "studies" / "S01-existing"
    existing.mkdir(parents=True)
    (existing / "STUDY.md").write_text("keep\n", encoding="utf-8")
    assert main(["--root", str(tmp_path), "add", "a later study"]) == 0
    assert main(["--root", str(tmp_path), "promote", "T-001", "--as", "study"]) == 0
    assert (existing / "STUDY.md").read_text(encoding="utf-8") == "keep\n"
    stubs = list((tmp_path / "studies").glob("S02-*/STUDY.md"))
    assert len(stubs) == 1
    text = stubs[0].read_text(encoding="utf-8")
    assert "state: PLANNED" in text
    assert 'standalone_claim: "TBD (human)"' in text
    card = (tmp_path / "ideas" / "cards" / "T-001.md").read_text(encoding="utf-8")
    assert "evidence: speculative" in card


def test_events_stay_append_only(tmp_path: Path) -> None:
    assert main(["--root", str(tmp_path), "add", "one"]) == 0
    first = _events(tmp_path)
    assert main(["--root", str(tmp_path), "add", "two"]) == 0
    second = _events(tmp_path)
    assert second.startswith(first)
    card = tmp_path / "ideas" / "cards" / "T-001.md"
    _fill_falsify(card, "a null result on the cheapest test")
    assert main(["--root", str(tmp_path), "ingest", "T-001"]) == 0
    third = _events(tmp_path)
    assert third.startswith(second)
    assert main(["--root", str(tmp_path), "status", "T-001", "queued"]) == 0
    fourth = _events(tmp_path)
    assert fourth.startswith(third)
    assert main(["--root", str(tmp_path), "link", "T-001", "--grounding", "doe2020example"]) == 0
    fifth = _events(tmp_path)
    assert fifth.startswith(fourth)
    assert main(["--root", str(tmp_path), "promote", "T-001", "--as", "question"]) == 0
    sixth = _events(tmp_path)
    assert sixth.startswith(fifth)
    assert len(sixth) > len(first)


def test_triage_digest_map_and_speculate(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    rule = tmp_path / ".cursor" / "rules"
    rule.mkdir(parents=True)
    (rule / "60-scout.mdc").write_text("---\ndescription: x\n---\nYou are the SCOUT.\n", encoding="utf-8")
    assert main(["--root", str(tmp_path), "add", "maybe local", "--by", "scout", "--study", "S01"]) == 0
    assert main(["--root", str(tmp_path), "add", "drop me", "--by", "scout"]) == 0
    capsys.readouterr()
    code = main(["--root", str(tmp_path), "triage", "--decisions", "T-001=keep,T-002=retire"])
    assert code == 0
    retired = (tmp_path / "ideas" / "cards" / "T-002.md").read_text(encoding="utf-8")
    assert "status: retired" in retired
    assert main(["--root", str(tmp_path), "digest", "S01"]) == 0
    digest = capsys.readouterr().out
    assert "Further work and untested ideas" in digest
    assert "**untested**" in digest
    assert main(["--root", str(tmp_path), "future-map"]) == 0
    graph = (tmp_path / "programme" / "future_map.mmd").read_text(encoding="utf-8")
    assert "T-001" in graph
    assert "S01" in graph
    assert main(["--root", str(tmp_path), "speculate", "example topic"]) == 0
    prompt = capsys.readouterr().out
    assert "Topic: example topic" in prompt
    assert "--by scout" in prompt
    assert "does not call an LLM" in prompt
