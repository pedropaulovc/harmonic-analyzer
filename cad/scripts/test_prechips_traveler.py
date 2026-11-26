"""Wrapper contracts for the prechips travelers, without SolidWorks, network or
a browser: every ``uv tool run`` and browser call is stubbed at ``subprocess.run``."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

import prechips_traveler as wrapper
import _process_plans as plans

_UV = "uv-under-test"
_VERSION = "9.9.9"


@pytest.fixture
def process(tmp_path, monkeypatch):
    monkeypatch.setattr(plans, "PROCESS_ROOT", tmp_path / "process")
    monkeypatch.setenv("UV", _UV)
    printer = tmp_path / "browser-under-test.exe"
    printer.write_bytes(b"")
    monkeypatch.setenv(wrapper.BROWSER_ENV, str(printer))

    def author(stem: str) -> None:
        plans.plan_path(stem).parent.mkdir(parents=True)
        plans.plan_path(stem).write_text('title = "Smoke plate"\n', encoding="utf-8")

    return tmp_path / "out", author


def _uv_stub(monkeypatch, *, probe=None, traveler=None, standing=None, printed=True):
    """Route stubbed ``uv tool run`` calls: the ``@latest`` version probe, then
    each pinned ``prechips traveler`` run (writes its ``--out`` unless refused)
    or ``prechips standing`` run. ``traveler(profile)`` and ``standing(cmd)``
    return an exit code or ``(code, stderr)``. A browser call writes a PDF
    naming the sheet it printed, unless ``printed`` is False."""
    calls = []

    def run(cmd, **kwargs):
        calls.append(cmd)
        if cmd[0] != _UV:
            if printed:
                pdf = next(arg for arg in cmd if arg.startswith("--print-to-pdf="))
                Path(pdf.split("=", 1)[1]).write_bytes(b"%PDF-1.4 " + cmd[-1].encode())
            return subprocess.CompletedProcess(cmd, 0, "", "")
        if f"{wrapper.PACKAGE}@latest" in cmd:
            return probe(cmd) if probe else subprocess.CompletedProcess(cmd, 0, f"{_VERSION}\n", "")
        if "--profile" in cmd:
            written = cmd[cmd.index("--profile") + 1]
            outcome = traveler(written) if traveler else 0
        else:
            written = "standing"
            outcome = standing(cmd) if standing else 0
        code, stderr = outcome if isinstance(outcome, tuple) else (outcome, "")
        if code == 0:
            Path(cmd[cmd.index("--out") + 1]).write_text(written, encoding="utf-8")
        return subprocess.CompletedProcess(cmd, code, None, stderr)

    monkeypatch.setattr(wrapper.subprocess, "run", run)
    return calls


def test_latest_release_renders_pro_then_hobby_then_prints_hobby_pdf(process, monkeypatch):
    out, author = process
    author("smoke_part")
    calls = _uv_stub(monkeypatch)
    assert wrapper.main(["smoke_part", "--out", str(out)]) == 0
    probe, *runs, printing = calls
    assert probe[:5] == [_UV, "tool", "run", "--from", "prechips@latest"]
    pro, hobby = plans.traveler_paths("smoke_part", out)
    head = [_UV, "tool", "run", "--from", f"prechips=={_VERSION}", "prechips", "traveler",
            str(plans.plan_path("smoke_part"))]
    assert runs == [
        [*head, "--profile", "pro", "--out", str(pro)],
        [*head, "--profile", "hobby", "--out", str(hobby)],
    ]
    assert pro.read_text(encoding="utf-8") == "pro"
    assert hobby.read_text(encoding="utf-8") == "hobby"
    pdf = plans.traveler_pdf_path("smoke_part", out)
    assert pdf == hobby.parent / "smoke-part-traveler.pdf"
    assert printing[-1] == hobby.resolve().as_uri()
    assert pdf.read_bytes() == b"%PDF-1.4 " + hobby.resolve().as_uri().encode()


_FAMILY = '''title = "Smoke pair"
[[parts]]
id = "left"
file = "../../out/features/smoke_left/features.toml"
[[parts]]
id = "right"
file = "../../out/features/smoke_right/features.toml"
'''


def test_family_plan_adds_a_placeholder_pdf_per_part_pointing_to_the_shared_one(
    process, monkeypatch
):
    # Owner ruling 2026-11-24: a release ships "a placeholder pdf per part
    # that points to shared one".
    out, author = process
    author("smoke_pair")
    plans.plan_path("smoke_pair").write_text(_FAMILY, encoding="utf-8")
    assert plans.family_parts("smoke_pair") == {"left": "smoke_left", "right": "smoke_right"}
    assert plans.part_stems("smoke_pair") == ("smoke_left", "smoke_right")
    calls = _uv_stub(monkeypatch)
    assert wrapper.main(["smoke_pair", "--out", str(out)]) == 0
    _probe, pro, hobby, left, right, *printing = calls
    directory = plans.traveler_dir("smoke_pair", out)
    shared = "smoke-pair-traveler.pdf"
    for part_id, slug, cmd in (("left", "smoke-left", left), ("right", "smoke-right", right)):
        # The same plan and checks as the shipped sheet, then the pointer page.
        assert cmd[: len(hobby) - 1] == hobby[:-1]
        assert cmd[len(hobby) - 1 :] == [
            str(directory / f"{slug}-traveler.html"),
            "--placeholder", part_id, "--shared-file", shared,
        ]
    assert [Path(cmd[-1].removeprefix("file:///")).name for cmd in printing] == [
        "traveler-hobby.html", "smoke-left-traveler.html", "smoke-right-traveler.html",
    ]
    pdfs = plans.traveler_pdf_paths("smoke_pair", out)
    assert [pdf.name for pdf in pdfs] == [
        shared, "smoke-left-traveler.pdf", "smoke-right-traveler.pdf",
    ]
    assert all(pdf.read_bytes().startswith(b"%PDF-1.4 ") for pdf in pdfs)
    assert set(plans.traveler_outputs("smoke_pair", out)) == {
        *plans.traveler_paths("smoke_pair", out), *pdfs,
        directory / "smoke-left-traveler.html", directory / "smoke-right-traveler.html",
    }
    # A print that fails on any of them leaves no sheet at all.
    _uv_stub(monkeypatch, printed=False)
    assert wrapper.main(["smoke_pair", "--out", str(out)]) == 1
    assert not any(path.exists() for path in plans.traveler_outputs("smoke_pair", out))


def test_latest_version_reads_the_probe_output(monkeypatch):
    def run(cmd, **kwargs):
        assert cmd[:7] == [_UV, "tool", "run", "--from", "prechips@latest", "python", "-c"]
        return subprocess.CompletedProcess(cmd, 0, "0.9.0\r\n", "")

    monkeypatch.setattr(wrapper.subprocess, "run", run)
    assert wrapper.latest_version(_UV) == "0.9.0"


def test_refusal_propagates_and_removes_previous_travelers(process, monkeypatch):
    out, author = process
    author("refused_part")
    paths = plans.traveler_outputs("refused_part", out)
    paths[0].parent.mkdir(parents=True)
    for path in paths:
        path.write_text("previous success", encoding="utf-8")
    calls = _uv_stub(
        monkeypatch, traveler=lambda profile: (2, "prechips: stock_fit: blank too short\n"),
    )
    assert wrapper.main(["refused_part", "--out", str(out)]) == 2
    assert not any(path.exists() for path in paths)
    assert len(calls) == 2  # the probe, then the refused pro run only


def test_hobby_refusal_removes_the_pro_traveler(process, monkeypatch):
    out, author = process
    author("smoke_part")
    _uv_stub(monkeypatch, traveler=lambda profile: 0 if profile == "pro" else 2)
    assert wrapper.main(["smoke_part", "--out", str(out)]) == 2
    assert not any(path.exists() for path in plans.traveler_outputs("smoke_part", out))


def test_failed_print_removes_every_traveler(process, monkeypatch):
    out, author = process
    author("smoke_part")
    _uv_stub(monkeypatch, printed=False)
    assert wrapper.main(["smoke_part", "--out", str(out)]) == 1
    assert not any(path.exists() for path in plans.traveler_outputs("smoke_part", out))


def test_missing_browser_fails_before_any_sheet(process, monkeypatch, tmp_path):
    out, author = process
    author("smoke_part")
    monkeypatch.delenv(wrapper.BROWSER_ENV)
    monkeypatch.setattr(wrapper.shutil, "which", lambda _name: None)
    for variable in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA"):
        monkeypatch.setenv(variable, str(tmp_path / "no-browser"))
    calls = _uv_stub(monkeypatch)
    assert wrapper.main(["smoke_part", "--out", str(out)]) == 1
    assert calls == []
    with pytest.raises(RuntimeError, match="no Edge or Chrome found"):
        wrapper.browser()


# uv's own diagnostics, as uv 0.9.8 printed them when provoked on this host:
# an unreachable index exits 2 with ``error:``; an unresolvable pin exits 1 with ``×``.
@pytest.mark.parametrize(("code", "stderr"), [
    (2, "error: Failed to fetch: `https://pypi.org/simple/prechips/`\n"
        "  Caused by: Request failed after 3 retries\n"),
    (1, "  × No solution found when resolving tool dependencies:\n"
        "  ╰─▶ Because there is no version of prechips==9.9.9 and you require\n"),
])
def test_uv_failure_during_render_is_not_a_refusal(process, monkeypatch, code, stderr):
    out, author = process
    author("smoke_part")
    _uv_stub(monkeypatch, traveler=lambda profile: 0 if profile == "pro" else (code, stderr))
    assert wrapper.main(["smoke_part", "--out", str(out)]) == 1
    assert not any(path.exists() for path in plans.traveler_outputs("smoke_part", out))
    assert wrapper.uv_error(stderr) is not None
    assert wrapper.uv_error("usage: prechips ...\nprechips: error: bad plan\n") is None


def test_missing_plan_fails_without_running_uv(process, monkeypatch):
    out, _author = process
    monkeypatch.setattr(
        wrapper.subprocess, "run",
        lambda *args, **kwargs: pytest.fail("uv ran without a plan"),
    )
    assert wrapper.main(["unplanned_part", "--out", str(out)]) == 2
    assert not any(path.exists() for path in plans.traveler_outputs("unplanned_part", out))


def test_unreachable_pypi_fails_before_any_sheet(process, monkeypatch):
    out, author = process
    author("smoke_part")
    paths = plans.traveler_paths("smoke_part", out)
    paths[0].parent.mkdir(parents=True)
    paths[0].write_text("previous success", encoding="utf-8")
    calls = _uv_stub(
        monkeypatch,
        probe=lambda cmd: subprocess.CompletedProcess(cmd, 2, "", "error: Failed to fetch"),
    )
    assert wrapper.main(["smoke_part", "--out", str(out)]) == 1
    assert len(calls) == 1
    assert not any(path.exists() for path in paths)
    with pytest.raises(RuntimeError, match="network access to PyPI is required"):
        wrapper.latest_version(_UV)


def test_missing_uv_fails_clearly(process, monkeypatch):
    out, author = process
    author("smoke_part")
    monkeypatch.delenv("UV")
    monkeypatch.setattr(wrapper.shutil, "which", lambda _name: None)
    monkeypatch.setattr(
        wrapper.subprocess, "run",
        lambda *args, **kwargs: pytest.fail("ran without uv"),
    )
    assert wrapper.main(["smoke_part", "--out", str(out)]) == 1
    with pytest.raises(RuntimeError, match="uv was not found"):
        wrapper._uv()


@pytest.fixture
def shop(tmp_path, monkeypatch):
    directory = tmp_path / "process" / "shop"
    directory.mkdir(parents=True)
    (directory / "common.toml").write_text("[standing]\n", encoding="utf-8")
    monkeypatch.setattr(plans, "SHOP_DIR", directory)
    return directory


def test_standing_renders_the_shop_page_and_prints_it_beside(process, shop, monkeypatch):
    out, _author = process
    calls = _uv_stub(monkeypatch)
    assert wrapper.main(["--standing", "--out", str(out)]) == 0
    probe, render, printing = calls
    assert probe[:5] == [_UV, "tool", "run", "--from", "prechips@latest"]
    html, pdf = wrapper.standing_paths(out)
    directory = out / "travelers" / "shop-standing-instructions"
    assert (html, pdf) == (
        directory / "shop-standing-instructions.html", directory / "shop-standing-instructions.pdf",
    )
    assert render == [
        _UV, "tool", "run", "--from", f"prechips=={_VERSION}", "prechips", "standing",
        str(shop), "--out", str(html),
    ]
    assert html.read_text(encoding="utf-8") == "standing"
    assert printing[-1] == html.resolve().as_uri()
    assert pdf.read_bytes() == b"%PDF-1.4 " + html.resolve().as_uri().encode()


def _previous_standing(out: Path) -> tuple[Path, Path]:
    paths = wrapper.standing_paths(out)
    paths[0].parent.mkdir(parents=True)
    for path in paths:
        path.write_text("previous success", encoding="utf-8")
    return paths


def test_standing_on_a_prechips_without_the_command_names_the_release_it_needs(
    process, shop, monkeypatch,
):
    out, _author = process
    paths = _previous_standing(out)
    errors = []
    monkeypatch.setattr(wrapper._telemetry, "error", lambda message, **_: errors.append(message))
    # argparse's refusal of an unknown subcommand, as an older prechips prints it.
    stderr = (
        "usage: prechips [-h] {traveler} ...\n"
        "prechips: error: argument command: invalid choice: 'standing' (choose from traveler)\n"
    )
    calls = _uv_stub(monkeypatch, standing=lambda _cmd: (2, stderr))
    assert wrapper.main(["--standing", "--out", str(out)]) == 1
    assert len(calls) == 2  # the probe, then the refused render; no print
    assert not any(path.exists() for path in paths)
    assert errors == [
        f"standing: prechips {_VERSION} has no `standing` command; the shop standing page "
        f"needs the first prechips release that adds `prechips standing` (newer than {_VERSION})"
    ]


@pytest.mark.parametrize(("outcome", "code"), [
    ((2, "prechips: shop: [notes.burrs] has no text\n"), 2),
    ((2, "error: Failed to fetch: `https://pypi.org/simple/prechips/`\n"), 1),
])
def test_standing_refusal_or_uv_failure_removes_the_page(process, shop, monkeypatch, outcome, code):
    out, _author = process
    paths = _previous_standing(out)
    _uv_stub(monkeypatch, standing=lambda _cmd: outcome)
    assert wrapper.main(["--standing", "--out", str(out)]) == code
    assert not any(path.exists() for path in paths)


def test_standing_failed_print_removes_the_page(process, shop, monkeypatch):
    out, _author = process
    _uv_stub(monkeypatch, printed=False)
    assert wrapper.main(["--standing", "--out", str(out)]) == 1
    assert not any(path.exists() for path in wrapper.standing_paths(out))


def test_standing_without_shop_files_fails_without_running_uv(process, tmp_path, monkeypatch):
    out, _author = process
    monkeypatch.setattr(plans, "SHOP_DIR", tmp_path / "empty-shop")
    monkeypatch.setattr(
        wrapper.subprocess, "run",
        lambda *args, **kwargs: pytest.fail("uv ran without a shop"),
    )
    assert wrapper.main(["--standing", "--out", str(out)]) == 2


@pytest.mark.parametrize("argv", [[], ["smoke_part", "--standing"]])
def test_a_stem_or_standing_but_not_both(argv):
    with pytest.raises(SystemExit) as raised:
        wrapper.main(argv)
    assert raised.value.code == 2


def test_enrolment_is_every_plan_that_is_not_a_placeholder(tmp_path):
    import _cam_programs

    for stem, revision in (
        ("b_part", "{{cad.revision}}"),
        ("a_part", "A"),
        ("c_part", "placeholder"),
    ):
        (tmp_path / stem).mkdir()
        (tmp_path / stem / "plan.toml").write_text(
            f'revision = "{revision}"\n', encoding="utf-8"
        )
    (tmp_path / "b_part" / "cam.py").write_text("", encoding="utf-8")
    assert plans.enrolled_stems(tmp_path) == ("a_part", "b_part")
    assert _cam_programs.cam_stems(tmp_path) == ("b_part",)


def test_an_unreadable_plan_fails_enrolment_naming_it(tmp_path):
    (tmp_path / "part").mkdir()
    (tmp_path / "part" / "plan.toml").write_text("revision = \n", encoding="utf-8")
    with pytest.raises(ValueError, match="unreadable process plan .*part"):
        plans.enrolled_stems(tmp_path)


def test_shop_files_are_the_directory_tomls_prechips_reads(tmp_path):
    for name in ("pd.toml", "common.toml", ".draft.toml", "notes.txt"):
        (tmp_path / name).write_text("", encoding="utf-8")
    (tmp_path / "nested").mkdir()
    (tmp_path / "nested" / "x.toml").write_text("", encoding="utf-8")
    assert [path.name for path in plans.shop_files(tmp_path)] == [
        "common.toml",
        "pd.toml",
    ]
