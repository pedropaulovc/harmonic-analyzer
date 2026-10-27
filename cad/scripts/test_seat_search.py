"""Offline contract for the native seat SEARCH behind spring recalibration, and
for the driver: its refusals before native work (a partial --write, a report
onto the written table), its import against the stale counter record it
replaces, and its --worker and counter-only modes.

The search may use ``ClosestDistance`` only to choose where the next trial
lands. A distance the modeller over-reports, under-reports, or returns as zero
must still end in a bracket that the NATIVE evaluations closed to 1e-6 mm, with
the clear endpoint never inside the interfering region.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

import _config
from diagnostics import _seat_search as search

_CONTACT_OFFSET_MM = 0.0731234567


class _FakeContact:
    """A pair whose contact sits at ``contact``; distance is scaled by ``gain``."""

    contact = _CONTACT_OFFSET_MM
    gain = 1.0

    def __init__(self, adapter, moving, fixed, direction, maximum, label) -> None:
        self.trials = 0
        self.offsets: list[float] = []
        self.seconds: dict[str, float] = {}

    def evaluate(self, offset_mm: float):
        self.trials += 1
        self.offsets.append(offset_mm)
        if offset_mm < self.contact:
            return "interfering", None
        return "clear", (offset_mm - self.contact) * self.gain


@pytest.fixture
def fake(monkeypatch):
    monkeypatch.setattr(search, "_ActualContact", _FakeContact)
    return _FakeContact


def _solve(label: str = "fake") -> search.ContactSolution:
    return search.solve_component_contact(
        object(), "spring", "hook", (0.0, 1.0, 0.0), 0.3175, label=label
    )


@pytest.mark.parametrize("gain", [1.0, 1.7, 0.4, 0.0])
def test_bracket_closes_on_the_native_contact_for_any_distance_gain(fake, gain) -> None:
    fake.gain = gain
    solution = _solve()

    assert solution.certificate == "bracketed_native_contact"
    assert solution.interfering_offset_mm is not None
    assert (
        solution.interfering_offset_mm < _CONTACT_OFFSET_MM <= solution.clear_offset_mm
    )
    assert solution.clear_offset_mm - solution.interfering_offset_mm <= 1e-6
    assert solution.offset_mm == solution.clear_offset_mm


class _WireOnWire(_FakeContact):
    """Two round wires closing 30 degrees off the contact normal.

    The minimum distance is convex in the offset (centre distance
    sqrt(D0^2 + 2 D0 g cos + g^2) minus D0), the shape a spring eye riding a
    hook wire shows the search.
    """

    def evaluate(self, offset_mm: float):
        state, _distance = super().evaluate(offset_mm)
        if state == "interfering":
            return state, None
        gap = offset_mm - self.contact
        centre = 1.5
        return "clear", self.gain * (
            (centre * centre + 2.0 * centre * gap * 0.866 + gap * gap) ** 0.5 - centre
        )


@pytest.mark.parametrize("gain", [1.0, 0.7, 0.4])
@pytest.mark.parametrize(
    "contact",
    [
        _CONTACT_OFFSET_MM,
        _CONTACT_OFFSET_MM + 1e-16,
        _CONTACT_OFFSET_MM - 1e-16,
        2e-5,
        5e-7,
        0.01,
        0.3,
    ],
)
def test_true_distance_converges_in_a_few_trials_not_a_bisection(
    fake, gain, contact
) -> None:
    """Bisecting this bracket to 1e-6 mm costs ~20 native evaluations (pinned by
    the zero-distance test); steering must stay far below that wherever the
    contact sits, including offsets that make a secant probe overshoot."""
    fake.gain = gain
    fake.contact = contact
    try:
        linear = _solve()
    finally:
        fake.gain = 1.0
        fake.contact = _CONTACT_OFFSET_MM

    assert linear.iterations <= 10
    assert linear.interfering_offset_mm < contact <= linear.clear_offset_mm
    assert linear.clear_offset_mm - linear.interfering_offset_mm <= 1e-6


@pytest.mark.parametrize("gain", [1.0, 0.7, 0.4])
def test_wire_on_wire_distance_converges_in_a_few_trials(monkeypatch, gain) -> None:
    monkeypatch.setattr(search, "_ActualContact", _WireOnWire)
    _WireOnWire.gain = gain
    solution = _solve()

    assert solution.iterations <= 8
    assert (
        solution.interfering_offset_mm < _CONTACT_OFFSET_MM <= solution.clear_offset_mm
    )
    assert solution.clear_offset_mm - solution.interfering_offset_mm <= 1e-6


def test_zero_distance_falls_back_to_bisection_and_still_converges(fake) -> None:
    fake.gain = 0.0
    solution = _solve()

    assert 19 <= solution.iterations <= 22
    assert solution.clear_offset_mm - solution.interfering_offset_mm <= 1e-6


def test_seated_pose_within_guard_is_certified_without_a_move(fake) -> None:
    fake.gain = 1.0
    fake.contact = -0.5e-5
    try:
        solution = _solve()
    finally:
        fake.contact = _CONTACT_OFFSET_MM

    assert solution.certificate == "already_seated"
    assert solution.witness == "native_distance"
    assert solution.offset_mm == 0.0


class _GuardShortDistance(_FakeContact):
    """ClosestDistance reading up to its 1e-5 mm guard short, so it reads zero
    on poses that are still clear -- the gooseneck screw against the counter
    eye (farm 2026-09-23: 23 native trials, 17 of them bisection)."""

    def evaluate(self, offset_mm: float):
        state, distance = super().evaluate(offset_mm)
        if state == "interfering":
            return state, None
        return state, max(0.0, distance - search.NATIVE_CONTACT_DISTANCE_TOLERANCE_MM)


def test_distance_short_by_its_guard_closes_at_the_guard_scale(monkeypatch) -> None:
    """A clear closing probe means the boundary is within the distance guard of
    the clear endpoint; the search must close there, not bisect from -max."""
    monkeypatch.setattr(search, "_ActualContact", _GuardShortDistance)
    solution = _solve()

    assert solution.iterations <= 10
    assert solution.interfering_offset_mm < _CONTACT_OFFSET_MM <= solution.clear_offset_mm
    assert solution.clear_offset_mm - solution.interfering_offset_mm <= 1e-6


@pytest.mark.parametrize("gain", [1.0, 0.0])
@pytest.mark.parametrize("error", [0.0, 3e-10, -9e-7, 2.5e-6, -2.5e-6])
def test_hint_near_the_boundary_closes_in_a_few_trials(fake, gain, error) -> None:
    """A re-seat of the same pair (the clamp tilt search re-seats both eyes
    ~20 times, drifting < 2.5e-6 mm) must not pay a fresh bracket search,
    whatever the distance reads."""
    fake.gain = gain
    try:
        solution = search.solve_component_contact(
            object(), "spring", "hook", (0.0, 1.0, 0.0), 0.3175, label="fake",
            hint_offset_mm=_CONTACT_OFFSET_MM + error,
        )
    finally:
        fake.gain = 1.0

    assert solution.iterations <= 6
    assert solution.interfering_offset_mm < _CONTACT_OFFSET_MM <= solution.clear_offset_mm
    assert solution.clear_offset_mm - solution.interfering_offset_mm <= 1e-6


@pytest.mark.parametrize("gain", [1.0, 0.0])
@pytest.mark.parametrize("hint", [0.0731, 0.2, -0.3, 0.3175, -0.3175, 5.0])
def test_wrong_hint_still_ends_in_a_native_bracket(fake, gain, hint) -> None:
    """A hint far off, on either side, at an endpoint or outside the bracket
    only costs trials; the verdict is still the native 1e-6 mm bracket."""
    fake.gain = gain
    try:
        solution = search.solve_component_contact(
            object(), "spring", "hook", (0.0, 1.0, 0.0), 0.3175, label="fake",
            hint_offset_mm=hint,
        )
    finally:
        fake.gain = 1.0

    assert solution.iterations <= 30
    assert solution.interfering_offset_mm < _CONTACT_OFFSET_MM <= solution.clear_offset_mm
    assert solution.clear_offset_mm - solution.interfering_offset_mm <= 1e-6


@pytest.mark.parametrize("mode", ["ALL", "COUNTER"])
def test_write_refuses_presets_that_leave_any_counter_unmeasured(
    tmp_path, mode
) -> None:
    """A partial --write keeps the omitted presets' counter records, which
    counter_seat() rejects as stale at build; in ALL mode it would also DELETE
    the channel-seat rows only they need (channel_seat() matches exactly). The
    driver must refuse before native work -- with no adapter, reaching a build
    is the bug -- and leave no report behind."""
    import asyncio

    from diagnostics import calibrate_spring_seats as driver

    table = _config.machine("springs", "presets")
    assert len(table) > 1, "fixture needs more than one configured preset"
    report = tmp_path / "report.json"
    for partial in sorted(table):
        with pytest.raises(ValueError, match="re-measure every configured preset"):
            asyncio.run(
                driver.calibrate(
                    None,
                    [partial],
                    report,
                    write=tmp_path / "springs.yaml",
                    source="test",
                    mode=driver.CalibrationMode[mode],
                )
            )
    assert not report.exists()


def test_partial_write_is_refused_before_the_com_seat(tmp_path, monkeypatch) -> None:
    from diagnostics import calibrate_spring_seats as driver

    def forbidden(*_args, **_kwargs):
        raise AssertionError("a refused run reached the COM seat")

    monkeypatch.setattr(driver.dodo, "_com_seat", forbidden)
    monkeypatch.setattr(driver, "run_build", forbidden)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "calibrate_spring_seats.py",
            "--presets",
            sorted(_config.machine("springs", "presets"))[-1],
            "--counter-only",
            "--write",
            str(tmp_path / "springs.yaml"),
        ],
    )
    with pytest.raises(ValueError, match="re-measure every configured preset"):
        driver.main()


def _aliased_report_and_table(tmp_path: Path, alias: str) -> tuple[Path, Path]:
    table = tmp_path / "springs.yaml"
    if alias == "same path":
        return table, table
    (tmp_path / "sub").mkdir()
    if alias == "dot-dot spelling":
        return tmp_path / "sub" / ".." / "springs.yaml", table
    table.write_text("springs: {}\n", encoding="utf-8")
    link = tmp_path / "sub" / "hardlink.yaml"
    os.link(table, link)  # resolves elsewhere; only samefile sees the alias
    assert link.resolve() != table.resolve()
    return link, table


@pytest.mark.parametrize("alias", ["same path", "dot-dot spelling", "hard link"])
def test_output_onto_the_written_table_is_refused(tmp_path, monkeypatch, alias) -> None:
    """The report is written last, even on failure: aimed at the --write PATH
    (by any alias) it would replace the merged table with JSON. Both entry
    points refuse before native work."""
    import asyncio

    from diagnostics import calibrate_spring_seats as driver

    def forbidden(*_args, **_kwargs):
        raise AssertionError("a refused run reached native work")

    monkeypatch.setattr(driver.dodo, "_com_seat", forbidden)
    monkeypatch.setattr(driver, "run_build", forbidden)
    presets = sorted(_config.machine("springs", "presets"))
    output, write = _aliased_report_and_table(tmp_path, alias)
    with pytest.raises(ValueError, match="report would overwrite it"):
        asyncio.run(driver.calibrate(None, presets, output, write=write, source="test"))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "calibrate_spring_seats.py",
            "--presets",
            *presets,
            "--output",
            str(output),
            "--write",
            str(write),
        ],
    )
    with pytest.raises(ValueError, match="report would overwrite it"):
        driver.main()


def test_the_real_source_table_is_never_a_report_target() -> None:
    from diagnostics import calibrate_spring_seats as driver

    presets = sorted(_config.machine("springs", "presets"))
    with pytest.raises(ValueError, match="source seat table"):
        driver._refuse_unsafe_run(presets, driver.SPRINGS_YAML, None)


@pytest.mark.parametrize("write", ["none", "elsewhere", "default"])
@pytest.mark.parametrize("alias", ["same path", "dot-dot spelling", "hard link"])
def test_output_onto_the_source_table_is_refused(
    tmp_path, monkeypatch, write, alias
) -> None:
    """With no --write, or a --write elsewhere, the report would still replace
    springs.yaml with JSON (written last, even on failure). Both entry points
    refuse before native work and leave the table untouched."""
    import asyncio

    from diagnostics import calibrate_spring_seats as driver

    def forbidden(*_args, **_kwargs):
        raise AssertionError("a refused run reached native work")

    monkeypatch.setattr(driver.dodo, "_com_seat", forbidden)
    monkeypatch.setattr(driver, "run_build", forbidden)
    output, springs = _aliased_report_and_table(tmp_path, alias)
    springs.write_bytes(driver.SPRINGS_YAML.read_bytes())
    table_bytes = springs.read_bytes()
    monkeypatch.setattr(driver, "SPRINGS_YAML", springs)
    presets = sorted(_config.machine("springs", "presets"))
    target = {
        "none": None,
        "elsewhere": tmp_path / "out" / "x.yaml",
        "default": springs,
    }
    with pytest.raises(ValueError, match="source seat table"):
        asyncio.run(
            driver.calibrate(None, presets, output, write=target[write], source="test")
        )
    argv = ["calibrate_spring_seats.py", "--presets", *presets, "--output", str(output)]
    if write == "elsewhere":
        argv += ["--write", str(target[write])]
    elif write == "default":
        argv += ["--write"]
    monkeypatch.setattr(sys, "argv", argv)
    with pytest.raises(ValueError, match="source seat table"):
        driver.main()
    assert springs.read_bytes() == table_bytes


def test_calibrating_every_preset_passes_the_coverage_guard(
    tmp_path, monkeypatch
) -> None:
    """The complete set must NOT be refused; it is how the table is regenerated."""
    import asyncio

    from diagnostics import calibrate_spring_seats as driver

    # COUNTER mode goes straight to the counter, whose doit-ledger freshness
    # check is covered below; past it, the missing adapter is the proof.
    monkeypatch.setattr(driver, "_require_current_support_parts", lambda: None)
    presets = sorted(_config.machine("springs", "presets"))
    for mode in driver.CalibrationMode:
        with pytest.raises(AttributeError):  # reached the build: no adapter to drive
            asyncio.run(
                driver.calibrate(
                    None,
                    presets,
                    tmp_path / "report.json",
                    write=tmp_path / "springs.yaml",
                    source="test",
                    mode=mode,
                )
            )


def test_counter_support_certificate_refuses_stale_or_unproven_parts(
    tmp_path, monkeypatch
) -> None:
    """upper_support labels the CURRENT recipe, so the driver refuses to measure
    support parts doit would rebuild, and refuses when it cannot tell."""
    import verify
    from diagnostics import calibrate_spring_seats as driver

    ledger = tmp_path / ".doit.db"
    monkeypatch.setitem(driver.dodo.DOIT_CONFIG, "dep_file", str(ledger))
    seen: list[list[str]] = []

    def fake_stale(db, producers):
        seen.append([task for task, _, _ in producers])
        return db.get("stale", [])

    monkeypatch.setattr(verify, "_stale_in_db", fake_stale)
    with pytest.raises(RuntimeError, match="cannot prove the counter support"):
        driver._require_current_support_parts()

    ledger.write_text('{"stale": ["part:sm_gooseneck_spring_screw: x changed"]}')
    with pytest.raises(RuntimeError, match="refusing to certify .* stale"):
        driver._require_current_support_parts()

    ledger.write_text("{}")
    driver._require_current_support_parts()
    assert seen[-1] == ["part:sm_gooseneck", "part:sm_gooseneck_spring_screw"]


def test_driver_imports_against_the_stale_counter_record_it_replaces() -> None:
    """The calibrator must load in the stale state it exists to fix, with no
    bypass: none of its imports may read counter_seat(), so neither the summing
    builder nor the summing spec (which reads it at import) may load. A fresh
    interpreter keeps the injected stale table out of this process."""
    scripts = Path(__file__).resolve().parent
    probe = textwrap.dedent(
        f"""
        import copy
        import sys

        sys.path[:0] = [{str(scripts)!r}, {str(scripts.parents[1])!r}]
        import _config

        machine = _config.machine

        def stale_machine(*keys):
            value = machine(*keys)
            if keys == ("springs", "presets"):
                value = copy.deepcopy(value)
                for preset in value.values():
                    preset["counter"]["upper_support"] = {{"thread": "#6-32 UNC"}}
            return value

        _config.machine = stale_machine
        import settled_spring_seats

        try:
            settled_spring_seats.counter_seat()
        except ValueError as error:
            assert "Stale counter native calibration" in str(error), error
        else:
            raise SystemExit("the injected counter record is not stale")
        from diagnostics import calibrate_spring_seats

        loaded = {{"build_sm_summing_assembly", "sm_summing_assembly_spec"}}
        assert not loaded & set(sys.modules), loaded & set(sys.modules)
        print("imported", calibrate_spring_seats.__name__)
        """
    )
    result = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=scripts,
        capture_output=True,
        text=True,
        timeout=240,
    )
    assert result.returncode == 0, result.stderr
    assert "imported diagnostics.calibrate_spring_seats" in result.stdout


def test_worker_runs_only_under_the_callers_com_seat(monkeypatch) -> None:
    """A ``_cached_com_action`` leaf already holds the seat: ``--worker`` must not
    take ``dodo._com_seat`` again (it would deadlock), and must refuse to run at
    all when no caller holds it."""
    from diagnostics import calibrate_spring_seats as driver

    def forbidden(*_args, **_kwargs):
        raise AssertionError("--worker took the COM seat lock")

    builds: list[object] = []
    monkeypatch.setattr(driver.dodo, "_com_seat", forbidden)
    monkeypatch.setattr(driver, "run_build", lambda build: builds.append(build) or 0)
    monkeypatch.setattr(sys, "argv", ["calibrate_spring_seats.py", "--worker"])

    monkeypatch.delenv("HARMONIC_COM_SEAT", raising=False)
    with pytest.raises(RuntimeError, match="HARMONIC_COM_SEAT unset"):
        driver.main()
    assert builds == []

    monkeypatch.setenv("HARMONIC_COM_SEAT", "calibrate-spring-seats leaf")
    assert driver.main() == 0
    assert len(builds) == 1


def test_counter_mode_measures_no_channel_seat_and_reports_it(
    tmp_path, monkeypatch
) -> None:
    import asyncio

    from diagnostics import calibrate_spring_seats as driver

    async def no_channel(*_args):
        raise AssertionError("counter mode calibrated a channel seat")

    monkeypatch.setattr(driver, "_calibrate_channel", no_channel)
    monkeypatch.setattr(driver, "_require_current_support_parts", lambda: None)
    report = tmp_path / "report.json"
    with pytest.raises(AttributeError):  # reached the counter build: no adapter
        asyncio.run(
            driver.calibrate(
                None,
                sorted(_config.machine("springs", "presets")),
                report,
                write=tmp_path / "springs.yaml",
                source="test",
                mode=driver.CalibrationMode.COUNTER,
            )
        )
    recorded = json.loads(report.read_text(encoding="utf-8"))
    assert recorded["mode"] == "counter"
    assert recorded["status"] == "failed"
    assert recorded["channel"] == []
    assert "channel_seats" not in recorded


def test_counter_only_merge_keeps_channel_seats_and_writes_the_given_path(
    tmp_path, monkeypatch
) -> None:
    import yaml

    from diagnostics import calibrate_spring_seats as driver

    springs = tmp_path / "springs.yaml"
    springs.write_bytes(driver.SPRINGS_YAML.read_bytes())
    monkeypatch.setattr(driver, "SPRINGS_YAML", springs)
    before = springs.read_text(encoding="utf-8")
    original = yaml.safe_load(before)["springs"]
    counters = {name: {"marker": name} for name in original["presets"]}
    target = tmp_path / "out" / "springs.calibrated.yaml"

    driver._merge_yaml(None, counters, "test source", target)

    assert springs.read_text(encoding="utf-8") == before
    after = target.read_text(encoding="utf-8")

    def channel_block(text: str) -> str:
        return text[text.index("\n  channel_seats:\n") : text.index("\n  presets:\n")]

    assert channel_block(after) == channel_block(before)
    merged = yaml.safe_load(after)["springs"]
    assert merged["channel_seats"] == original["channel_seats"]
    # The retained channel seats keep their own attribution; only the refreshed
    # counters are credited to this run.
    assert merged["source"] == original["source"] != "test source"
    assert merged["counter_source"] == "test source"
    assert list(merged).index("counter_source") == list(merged).index("source") + 1
    for name, counter in counters.items():
        assert merged["presets"][name]["counter"] == counter
        assert (
            merged["presets"][name]["amplitudes_mm"]
            == original["presets"][name]["amplitudes_mm"]
        )
    header = [line for line in before.splitlines() if line.startswith("#")]
    assert after.splitlines()[: len(header)] == header


def test_unchanged_merge_reproduces_the_committed_table_byte_for_byte(
    tmp_path, monkeypatch
) -> None:
    """Merging the table's own counters and source back must emit its exact LF
    bytes, so a farm leaf's output can be copied into cad/config verbatim. (The
    checkout may carry CRLF; git stores and _merge_yaml writes LF.)"""
    import yaml

    from diagnostics import calibrate_spring_seats as driver

    springs = tmp_path / "springs.yaml"
    springs.write_bytes(driver.SPRINGS_YAML.read_bytes())
    monkeypatch.setattr(driver, "SPRINGS_YAML", springs)
    text = springs.read_text(encoding="utf-8")
    original = yaml.safe_load(text)["springs"]
    counters = {name: preset["counter"] for name, preset in original["presets"].items()}
    target = tmp_path / "out" / "springs.yaml"

    driver._merge_yaml(None, counters, original["source"], target)

    assert b"\r" not in target.read_bytes()
    assert target.read_bytes() == text.encode("utf-8")


def test_full_merge_credits_both_tables_to_the_run(tmp_path, monkeypatch) -> None:
    import yaml

    from diagnostics import calibrate_spring_seats as driver

    springs = tmp_path / "springs.yaml"
    document = yaml.safe_load(driver.SPRINGS_YAML.read_text(encoding="utf-8"))
    document["springs"]["counter_source"] = "an earlier counter-only run"
    springs.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
    monkeypatch.setattr(driver, "SPRINGS_YAML", springs)
    original = document["springs"]
    counters = {name: {"marker": name} for name in original["presets"]}
    target = tmp_path / "out" / "springs.yaml"

    driver._merge_yaml([{"row": 0}], counters, "run B", target)

    merged = yaml.safe_load(target.read_text(encoding="utf-8"))["springs"]
    assert merged["source"] == "run B"
    assert "counter_source" not in merged
    assert merged["channel_seats"] == [{"row": 0}]


def _tear_writes(monkeypatch) -> None:
    """Make the next binary write stop half way through with a disk error."""
    real = os.fdopen

    class _Torn:
        def __init__(self, stream) -> None:
            self.stream = stream

        def __enter__(self):
            return self

        def __exit__(self, *_exc) -> bool:
            self.stream.close()
            return False

        def write(self, data: bytes) -> int:
            self.stream.write(data[: len(data) // 2])
            self.stream.flush()
            raise OSError("disk full")

    monkeypatch.setattr(os, "fdopen", lambda handle, mode: _Torn(real(handle, mode)))


def test_a_torn_table_write_leaves_the_previous_table_intact(
    tmp_path, monkeypatch
) -> None:
    from diagnostics import calibrate_spring_seats as driver

    springs = tmp_path / "springs.yaml"
    springs.write_bytes(driver.SPRINGS_YAML.read_bytes())
    monkeypatch.setattr(driver, "SPRINGS_YAML", springs)
    target = tmp_path / "out" / "springs.calibrated.yaml"
    target.parent.mkdir()
    target.write_bytes(b"previous table\n")
    _tear_writes(monkeypatch)

    with pytest.raises(OSError, match="disk full"):
        driver._merge_yaml(None, {}, "test source", target)

    assert target.read_bytes() == b"previous table\n"
    assert sorted(target.parent.iterdir()) == [target]


def test_a_torn_report_write_leaves_the_previous_report_intact(
    tmp_path, monkeypatch
) -> None:
    import asyncio

    from diagnostics import calibrate_spring_seats as driver

    report = tmp_path / "report.json"
    report.write_bytes(b'{"status": "previous"}\n')
    _tear_writes(monkeypatch)

    with pytest.raises(OSError, match="disk full"):  # the failed run's report
        asyncio.run(
            driver.calibrate(
                None,
                sorted(_config.machine("springs", "presets")),
                report,
                write=None,
                source="test",
            )
        )

    assert report.read_bytes() == b'{"status": "previous"}\n'
    assert sorted(tmp_path.iterdir()) == [report]


class _ParallelFaceDistance(_FakeContact):
    """ClosestDistance held by a separation the motion does not close.

    Native 2026-10-10 neutral counter upper run: the made screw moves along -Y
    into the counter spring's upper eye while its head face stays clamped
    2.2e-6 mm off the eye's side face (SPRING_EYE_GAP is the eye's occupied
    width), parallel to the motion. Every steered probe read the same 2.2e-6
    mm, crept that far, and the search exhausted 64 iterations.
    """

    creep = 0.0

    def evaluate(self, offset_mm: float):
        state, _distance = super().evaluate(offset_mm)
        if state == "interfering":
            return state, None
        return state, 2.2e-6 + self.creep * (offset_mm - self.contact)


@pytest.mark.parametrize("creep", [0.0, 1e-3])
@pytest.mark.parametrize("contact", [-0.0312345678, 0.0731234567, -0.124])
def test_distance_the_motion_does_not_close_falls_back_to_bisection(
    monkeypatch, creep, contact
) -> None:
    monkeypatch.setattr(search, "_ActualContact", _ParallelFaceDistance)
    monkeypatch.setattr(_ParallelFaceDistance, "creep", creep)
    monkeypatch.setattr(_ParallelFaceDistance, "contact", contact)
    solution = search.solve_component_contact(
        object(),
        "screw",
        "counter",
        (0.0, -1.0, 0.0),
        0.125,
        label="fake counter upper",
        locate_only=True,
    )

    assert solution.certificate == "bracketed_native_contact"
    # One stalled steer, then bisection of the 0.25 mm bracket to 1e-6 mm.
    assert solution.iterations <= 22
    assert solution.interfering_offset_mm < contact <= solution.clear_offset_mm
    assert solution.clear_offset_mm - solution.interfering_offset_mm <= 1e-6
