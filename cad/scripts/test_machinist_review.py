"""Offline contracts for the blind machinist review runner."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import machinist_review as mr


def test_prompts_exist_and_are_calibrated_to_the_policy() -> None:
    part = mr.load_prompt("part")
    assembly = mr.load_prompt("assembly")
    # The recalibration that separates this prompt from the gap-hunting ones:
    # the title block is the general spec, and over-specification is a defect.
    for text in (part, assembly):
        assert "TITLE BLOCK FIRST" in text
        assert "do not run commands" in text  # keeps the review blind
        assert "over_specification" in text
        assert "Never pad a category" in text
    assert "loaded gun" in part
    assert "Decimal places" in part
    assert "Hidden lines" in part
    assert "DRILL or REAM" in part
    assert "granite surface plate" in part and "No CMM" in part
    assert "never call a geometric control uninspectable" in part
    assert "datum feature symbols on real, reachable surfaces" in part
    # Assembly packages are judged as real assembly drawings: exploded view,
    # parts list, balloons, ordered steps -- the current three-view sheets are
    # expected to FAIL this until they are built out.
    for item in ("exploded view", "parts list (BOM)", "Assembly steps in order"):
        assert item in assembly, item
    assembly_text = " ".join(assembly.split())
    for item in (
        "return one verdict for the package as a whole",
        "every balloon against its BOM row",
        "setup and assembly steps across sheet boundaries",
        "SHIP requires those cross-sheet checks",
    ):
        assert item in assembly_text, item


def test_schema_is_strict_structured_output() -> None:
    schema = mr.load_schema()
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == set(schema["properties"])
    assert set(mr.FINDING_KEYS) <= set(schema["properties"])
    finding = schema["$defs"]["findings"]["items"]
    assert finding["additionalProperties"] is False
    assert set(finding["required"]) == {"where", "issue", "fix"}
    assert schema["properties"]["verdict"]["enum"] == ["SHIP", "FIX"]
    assert schema["properties"]["summary"]["minLength"] == 1
    for key in ("where", "issue", "fix"):
        assert finding["properties"][key]["minLength"] == 1


def test_command_references_only_the_neutral_workdir(tmp_path: Path) -> None:
    images = [tmp_path / "sheet-1.png", tmp_path / "sheet-2.png"]
    cmd = mr.build_command(
        workdir=tmp_path,
        images=images,
        schema=tmp_path / "schema.json",
        output=tmp_path / "verdict.json",
        model="gpt-test",
        effort="high",
    )
    joined = " ".join(cmd)
    repo = mr.CAD_ROOT.parent.as_posix()
    assert repo not in joined.replace("\\", "/")
    assert cmd[-1] == "-"  # prompt on stdin, never inline
    assert [cmd[index + 1] for index, value in enumerate(cmd) if value == "-i"] == [
        str(image) for image in images
    ]
    for flag in ("--ignore-user-config", "--ignore-rules", "--ephemeral", "--json"):
        assert flag in cmd
    assert cmd[cmd.index("--sandbox") + 1] == "read-only"
    assert cmd[cmd.index("-m") + 1] == "gpt-test"
    assert "model_reasoning_effort=high" in cmd


def test_pass_requires_ship_with_no_gating_findings() -> None:
    clean = {
        "verdict": "SHIP",
        "summary": "ready",
        "blockers": [],
        "over_specification": [],
        "clarity": [],
        "minor": [{"where": "x", "issue": "y", "fix": "z"}],
    }
    assert mr.is_pass(clean)
    assert not mr.is_pass({**clean, "verdict": "FIX"})
    for key in mr.GATING_KEYS:
        assert not mr.is_pass(
            {**clean, key: [{"where": "x", "issue": "y", "fix": "z"}]}
        )
    assert not mr.is_pass(None)


def test_verdict_validation_rejects_every_schema_violation() -> None:
    clean = {
        "verdict": "SHIP",
        "summary": "ready",
        "blockers": [],
        "over_specification": [],
        "clarity": [],
        "minor": [{"where": "x", "issue": "y", "fix": "z"}],
    }
    assert mr.validate_verdict(clean) is clean

    invalid = [
        {key: value for key, value in clean.items() if key != "summary"},
        {**clean, "unexpected": True},
        {**clean, "verdict": "MAYBE"},
        {**clean, "verdict": 1},
        {**clean, "summary": ""},
        {**clean, "summary": 1},
        {**clean, "blockers": {}},
        {**clean, "minor": ["not an object"]},
        {**clean, "minor": [{"where": "x", "issue": "y"}]},
        {
            **clean,
            "minor": [{"where": "x", "issue": "y", "fix": "z", "unexpected": True}],
        },
        {**clean, "minor": [{"where": "", "issue": "y", "fix": "z"}]},
        {**clean, "minor": [{"where": "x", "issue": "", "fix": "z"}]},
        {**clean, "minor": [{"where": "x", "issue": "y", "fix": ""}]},
        {**clean, "minor": [{"where": "x", "issue": 1, "fix": "z"}]},
    ]
    for value in invalid:
        with pytest.raises(ValueError):
            mr.validate_verdict(value)
        assert not mr.is_pass(value)


def test_extract_verdict_validates_file_and_event_fallback(tmp_path: Path) -> None:
    invalid = {
        "verdict": "SHIP",
        "summary": "ready",
        "blockers": [],
        "over_specification": [],
        "clarity": [],
        "minor": [],
        "unexpected": True,
    }
    output = tmp_path / "verdict.json"
    output.write_text(json.dumps(invalid), encoding="utf-8")
    with pytest.raises(ValueError, match="keys must be exact"):
        mr._extract_verdict(output, [])

    output.unlink()
    events = [{"type": "agent_message", "text": json.dumps(invalid)}]
    with pytest.raises(ValueError, match="keys must be exact"):
        mr._extract_verdict(output, events)


def test_tool_events_are_detected_at_any_depth() -> None:
    assert mr.count_tool_events([{"type": "agent_message", "text": "{}"}]) == 0
    assert (
        mr.count_tool_events(
            [
                {
                    "type": "item.completed",
                    "item": {"type": "command_execution", "command": "ls"},
                }
            ]
        )
        == 1
    )
    assert (
        mr.count_tool_events([{"type": "turn.started"}, {"type": "mcp_tool_call"}]) == 1
    )


def test_retry_persists_all_attempts_and_cannot_hide_tool_use(
    tmp_path: Path, monkeypatch
) -> None:
    import subprocess

    png = tmp_path / "source.png"
    png.write_bytes(b"image")
    verdict = {
        "verdict": "SHIP",
        "summary": "ready",
        "blockers": [],
        "over_specification": [],
        "clarity": [],
        "minor": [],
    }
    calls = 0

    def fake_run(command, **_kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            event = {
                "type": "item.completed",
                "item": {
                    "type": "command_execution",
                    "command": "read something",
                },
            }
            return subprocess.CompletedProcess(
                command, 1, stdout=json.dumps(event), stderr="failed"
            )
        output = Path(command[command.index("-o") + 1])
        output.write_text(json.dumps(verdict), encoding="utf-8")
        event = {"type": "agent_message", "text": json.dumps(verdict)}
        return subprocess.CompletedProcess(
            command, 0, stdout=json.dumps(event), stderr=""
        )

    monkeypatch.setattr(subprocess, "run", fake_run)
    report_dir = tmp_path / "reports"
    review = mr.review_package(
        mr.ReviewPackage("part", "part", (png,)),
        report_dir=report_dir,
        retries=1,
        codex="codex",
    )

    assert review.attempts == 2
    assert review.tool_events == 1
    assert not review.blind
    assert not review.passed
    records = [
        json.loads(line)
        for line in (report_dir / "part.events.jsonl").read_text().splitlines()
    ]
    assert [record["attempt"] for record in records] == [1, 2]
    assert records[0]["event"]["item"]["type"] == "command_execution"
    assert records[1]["event"]["type"] == "agent_message"


def test_arbitrary_png_reports_with_same_basename_do_not_collide(
    tmp_path: Path, monkeypatch
) -> None:
    import subprocess
    from concurrent.futures import ThreadPoolExecutor

    verdict = {
        "verdict": "SHIP",
        "summary": "ready",
        "blockers": [],
        "over_specification": [],
        "clarity": [],
        "minor": [],
    }

    def fake_run(command, **_kwargs):
        output = Path(command[command.index("-o") + 1])
        output.write_text(json.dumps(verdict), encoding="utf-8")
        return subprocess.CompletedProcess(
            command, 0, stdout=json.dumps({"type": "turn.completed"}), stderr=""
        )

    monkeypatch.setattr(subprocess, "run", fake_run)
    inputs = [tmp_path / "left" / "part.png", tmp_path / "right" / "part.png"]
    for index, image in enumerate(inputs):
        image.parent.mkdir()
        image.write_bytes(f"png-{index}".encode())
    packages = [mr._package_for_pngs([image], "part") for image in inputs]
    assert packages[0].name != packages[1].name

    report_dir = tmp_path / "reports"
    with ThreadPoolExecutor(max_workers=2) as pool:
        reviews = list(
            pool.map(
                lambda package: mr.review_package(
                    package, report_dir=report_dir, retries=0, codex="codex-test"
                ),
                packages,
            )
        )

    names = {review.name for review in reviews}
    assert len(names) == 2
    assert {path.stem for path in report_dir.glob("*.json")} == names
    assert {path.stem for path in report_dir.glob("*.md")} == names
    assert {Path(review.events_file or "").name for review in reviews} == {
        f"{name}.events.jsonl" for name in names
    }
    index = mr.write_index(report_dir).read_text(encoding="utf-8")
    assert all(f"]({name}.md)" in index for name in names)


def test_pdfium_operations_share_one_module_lock(tmp_path: Path, monkeypatch) -> None:
    import sys
    import threading
    import types
    from concurrent.futures import ThreadPoolExecutor

    class ObservedLock:
        def __init__(self) -> None:
            self._lock = threading.Lock()
            self._state_lock = threading.Lock()
            self.owner: int | None = None
            self.active = 0
            self.max_active = 0
            self.acquisitions = 0

        def __enter__(self):
            self._lock.acquire()
            with self._state_lock:
                self.owner = threading.get_ident()
                self.active += 1
                self.max_active = max(self.max_active, self.active)
                self.acquisitions += 1
            return self

        def __exit__(self, *_args) -> None:
            with self._state_lock:
                self.active -= 1
                self.owner = None
            self._lock.release()

        def assert_held(self, operation: str) -> None:
            assert self.owner == threading.get_ident(), (
                f"PDFium operation escaped the shared lock: {operation}"
            )

    observed_lock = ObservedLock()

    class FakeImage:
        def save(self, path: Path, **_kwargs) -> None:
            path.write_bytes(b"png")

    class FakeBitmap:
        def to_pil(self) -> FakeImage:
            observed_lock.assert_held("bitmap.to_pil")
            return FakeImage()

    class FakePage:
        def render(self, **_kwargs) -> FakeBitmap:
            observed_lock.assert_held("page.render")
            return FakeBitmap()

        def close(self) -> None:
            observed_lock.assert_held("page.close")

    class FakeDocument:
        def __init__(self, _path: str) -> None:
            observed_lock.assert_held("PdfDocument")

        def __len__(self) -> int:
            observed_lock.assert_held("document length")
            return 2

        def __getitem__(self, _index: int) -> FakePage:
            observed_lock.assert_held("document page")
            return FakePage()

        def close(self) -> None:
            observed_lock.assert_held("document.close")

    monkeypatch.setattr(mr, "_PDFIUM_LOCK", observed_lock)
    monkeypatch.setitem(
        sys.modules, "pypdfium2", types.SimpleNamespace(PdfDocument=FakeDocument)
    )
    barrier = threading.Barrier(2)
    source = tmp_path / "assembly.pdf"
    package = mr.ReviewPackage("assembly", "assembly", (source,))
    workdir = tmp_path / "images"
    workdir.mkdir()

    def page_count() -> int:
        barrier.wait()
        return mr._pdf_page_count(source)

    def materialize() -> list[Path]:
        barrier.wait()
        return mr._materialize_images(package, workdir)

    with ThreadPoolExecutor(max_workers=2) as pool:
        page_count_future = pool.submit(page_count)
        materialize_future = pool.submit(materialize)
        assert page_count_future.result() == 2
        assert len(materialize_future.result()) == 2

    assert observed_lock.acquisitions == 2
    assert observed_lock.max_active == 1


def test_multi_sheet_assembly_is_one_cross_sheet_review(
    tmp_path: Path, monkeypatch
) -> None:
    import subprocess

    from pypdf import PdfWriter

    source = tmp_path / "assembly.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    writer.add_blank_page(width=72, height=72)
    with source.open("wb") as stream:
        writer.write(stream)
    verdict = {
        "verdict": "SHIP",
        "summary": "BOM conflict remains",
        "blockers": [],
        "over_specification": [],
        "clarity": [
            {
                "where": "sheets 1 and 2",
                "issue": "balloon 4 maps to conflicting BOM rows",
                "fix": "make item 4 consistent across the package",
            }
        ],
        "minor": [],
    }
    captured: list[tuple[list[Path], str, list[bytes]]] = []

    def fake_run(command, **kwargs):
        attachments = [
            Path(command[index + 1])
            for index, value in enumerate(command)
            if value == "-i"
        ]
        prompt = kwargs["input"]
        signatures = [path.read_bytes()[:4] for path in attachments]
        captured.append((attachments, prompt, signatures))
        output = Path(command[command.index("-o") + 1])
        output.write_text(json.dumps(verdict), encoding="utf-8")
        return subprocess.CompletedProcess(
            command, 0, stdout=json.dumps({"type": "turn.completed"}), stderr=""
        )

    monkeypatch.setattr(subprocess, "run", fake_run)
    package = mr.ReviewPackage("gearbox", "assembly", (source,))
    review = mr.review_package(
        package,
        report_dir=tmp_path / "reports",
        retries=0,
        codex="codex-test",
    )

    assert review.error is None
    assert review.verdict == verdict
    assert len(captured) == 1
    attachments, prompt, signatures = captured[0]
    assert len(attachments) == 2
    assert len(signatures) == 2
    assert all(signature == b"\x89PNG" for signature in signatures)
    prompt_text = " ".join(prompt.split())
    assert "Compare every sheet against every other sheet" in prompt_text
    assert "every balloon against its BOM row" in prompt_text
    assert review.sheet_count == 2
    assert review.sources == [str(source)]
    assert len(review.source_sha256) == 1
    assert not review.passed

    part_sheets = (tmp_path / "part-a.png", tmp_path / "part-b.png")
    for sheet in part_sheets:
        sheet.write_bytes(b"part")
    with pytest.raises(ValueError, match="part review requires exactly one"):
        mr._validate_package(mr.ReviewPackage("part", "part", part_sheets))


def test_write_index_creates_missing_report_directory(tmp_path: Path) -> None:
    report_dir = tmp_path / "missing" / "nested"

    index = mr.write_index(report_dir)

    assert index == report_dir / "index.md"
    assert index.is_file()
    assert "0/0 packages pass" in index.read_text(encoding="utf-8")


def test_review_serialises_and_indexes(tmp_path: Path) -> None:
    verdict = {
        "verdict": "FIX",
        "summary": "over-toleranced",
        "blockers": [],
        "over_specification": [
            {"where": "front view", "issue": "datum B", "fix": "drop"}
        ],
        "clarity": [],
        "minor": [],
    }
    review = mr.Review(
        name="crank_arm",
        kind="part",
        sources=["x.png"],
        source_sha256=["b" * 64],
        verdict=verdict,
        passed=mr.is_pass(verdict),
        blind=True,
        tool_events=0,
        model="m",
        effort="high",
        prompt_sha256="a" * 64,
        sheet_count=1,
        duration_s=1.0,
        reviewed_at="now",
    )
    mr.write_review(review, tmp_path)
    loaded = mr.load_reviews(tmp_path)
    assert loaded[0].verdict == verdict and not loaded[0].passed
    index = mr.render_index(loaded)
    expected = (
        "| [crank_arm](crank_arm.md) | part | 1 | FAIL | FIX | 0 | 1 | 0 | 0 | yes |"
    )
    assert expected in index
    data = json.loads((tmp_path / "crank_arm.json").read_text())
    assert data["name"] == "crank_arm"
    assert data["sources"] == ["x.png"]


def test_every_registered_drawing_has_a_prompt_kind_and_package_source() -> None:
    for package in mr.all_packages():
        assert package.kind in mr.PROMPT_FILES
        assert len(package.sources) == 1
        expected_suffix = ".pdf" if package.kind == "assembly" else ".png"
        assert package.sources[0].suffix.casefold() == expected_suffix
        if package.kind == "part":
            assert package.sources[0].name.endswith("_drawing.png")
        else:
            assert package.sources[0].parent.name == "pdf"
