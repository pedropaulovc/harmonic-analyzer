"""Offline contract for COM failure forensics (_common.capture_com_failure).

No SolidWorks: the adapter, the seat and the document are test doubles, so the
assertions read the real OTel records and the real artefact files the capture
would produce on a worker.

What is pinned here is what makes forensics safe to put on a build path -- and
the reason the 2026-09-17 ``logo ring extrude failed`` leaf could only be called
"transient":

* the capture NEVER changes the failure: same exception type, same message,
  even when every single capture step blows up (a diagnostic that can mask or
  replace a geometry failure moves the diagnosis further away, so this is the
  one property worth a test more than the captures themselves);
* the evidence reaches telemetry, not just the disposable worker's disk: one
  ERROR log carrying the whole capture, and one span event per capture STEP
  (bounded -- never one per sketch point);
* the inference fingerprint is readable off the artefact: a profile whose
  coincident endpoints did not merge shows ``contour_count == 0`` with
  ``coincident_point_pairs > 0``, which is the difference between "the geometry
  is wrong" and "this seat authors sketches differently";
* seat preferences that cannot be resolved or read are reported as
  ``unresolved``/``unreadable`` and never as ``False`` (``GetUserPreference*``
  answers an unknown id with a plausible ``False``);
* seat provenance says WHICH sldworks.exe ran the leaf and whether this build
  started it.

    python -m pytest cad/scripts/test_failure_forensics.py
"""

from __future__ import annotations

import contextlib
import json
import ctypes
import io
import logging
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast
from unittest import mock

import pytest
from opentelemetry._logs import get_logger_provider
from opentelemetry.sdk._logs import LoggerProvider as SdkLoggerProvider
from opentelemetry.sdk._logs.export import (
    InMemoryLogRecordExporter,
    SimpleLogRecordProcessor,
)
from opentelemetry.sdk.trace import TracerProvider as SdkTracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _common  # noqa: E402
import _telemetry  # noqa: E402
import _watchdog  # noqa: E402

# --- Test doubles ----------------------------------------------------------
# Deliberately NOT Mock(): a Mock answers every attribute with a truthy child,
# which is exactly the failure mode these captures guard against (a plausible
# value where the seat actually said nothing). Each double answers only what the
# real interface answers, and raises for the rest.


class _Sketch:
    """An ``ISketch`` whose census is whatever the test dictates."""

    def __init__(self, *, contours: int, points: list[tuple[float, float, float]]):
        self._contours = contours
        self._points = points
        self.Name = "LogoProfile"

    def GetSketchContourCount(self) -> int:
        return self._contours

    def GetSketchRegionCount(self) -> int:
        return self._contours

    def GetSketchSegments(self) -> list[object]:
        return [object()] * len(self._points)

    def GetLineCount(self) -> int:
        return len(self._points)

    def GetArcCount(self) -> int:
        return 0

    def GetAutomaticSolve(self) -> bool:
        return True

    def GetConstrainedStatus(self) -> int:
        return 2  # swUnderConstrained

    def GetSketchPoints2(self) -> list[object]:
        return [
            type("_P", (), {"X": x, "Y": y, "Z": z})()
            for x, y, z in self._points
        ]


class _Model:
    """An ``IModelDoc2`` that can save a copy and a BMP, like a real seat."""

    def __init__(self, tmp_path: Path):
        self._root = tmp_path
        self.saved: list[tuple[str, int, int]] = []
        self.ActiveView = _View()
        self.Extension = None

    def GetTitle(self) -> str:
        return "91247A720"

    def GetPathName(self) -> str:
        return str(self._root / "91247A720.SLDPRT")

    def GetType(self) -> int:
        return 1

    def GetFeatureCount(self) -> int:
        return 7

    def GetSaveFlag(self) -> bool:
        return True

    def GetActiveSketch2(self) -> None:
        return None

    def SaveAs3(self, path: str, version: int, options: int) -> int:
        self.saved.append((path, version, options))
        Path(path).write_bytes(b"SLDPRT")
        return 0

    def SaveBMP(self, path: str, width: int, height: int) -> bool:
        Path(path).write_bytes(b"BM")
        return True


class _View:
    """An ``IModelView``: a zoom scale, a visible box and screen projection.

    ``ProjectModelPoint`` is what makes px/mm MEASURED rather than inferred from
    ``Scale2``; this double projects 1 mm to 20 px along x and y.
    """

    def __init__(self, *, px_per_mm: float = 20.0):
        self._px = px_per_mm
        self.Scale2 = 3.5

    def GetVisibleBox(self) -> list[float]:
        # Metres: a 100 mm x 80 mm visible region centred on the origin.
        return [-0.05, -0.04, -0.01, 0.05, 0.04, 0.01]

    def ProjectModelPoint(self, x: float, y: float, z: float) -> tuple[int, float, float, float]:
        # [out] params ride the return tuple under early binding.
        return 0, x * 1000.0 * self._px, y * 1000.0 * self._px, 0.0


class _SketchManager:
    """``ISketchManager``'s sticky per-session bag."""

    def __init__(self, *, add_to_db: bool = False):
        self.AddToDB = add_to_db
        self.AutoInference = True
        self.AutoSolve = True
        self.DisplayWhenAdded = True


class _Frame:
    def GetHWnd(self) -> int:
        return 0x1234


class _Seat:
    """An ``ISldWorks``: a pid, a revision and readable user preferences."""

    def __init__(self, *, pid: int = 4242, toggles: dict[int, Any] | None = None):
        self._pid = pid
        self._toggles = toggles or {}
        self.Frame = _Frame()

    def GetProcessID(self) -> int:
        return self._pid

    def RevisionNumber(self) -> str:
        return "34.3.0"

    def GetUserPreferenceToggle(self, pref: int) -> Any:
        if pref in self._toggles:
            return self._toggles[pref]
        raise OSError("seat refused the read")

    def GetUserPreferenceIntegerValue(self, pref: int) -> int:
        return 9

    def GetUserPreferenceStringValue(self, pref: int) -> str:
        return r"C:\templates\harmonic-part.prtdot"


class _Adapter:
    """The slice of ``PyWin32Adapter`` the forensics touch."""

    def __init__(
        self,
        *,
        sw: Any = None,
        model: Any = None,
        sketch_manager: Any = None,
        constants=None,
    ):
        self.swApp = sw
        self.currentModel = model
        self.currentSketchManager = sketch_manager
        self.constants = constants or dict(_SW_CONSTANTS)

    def _attempt(self, fn, default=None):
        try:
            return fn()
        except Exception:
            return default


@pytest.fixture(autouse=True)
def offline_seat(monkeypatch, tmp_path):
    """Keep the capture offline and out of the repo's cad/out tree.

    The preference ids resolve through the real name->id path, seeded with the
    verified swconst R2026x ids for the two toggles that decide whether bare
    CreateLine endpoints merge; ``sldworks.exe`` scans are stubbed so the test
    never depends on what runs on the machine.
    """
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "")
    monkeypatch.setattr(_common, "OUT_FAILURES", tmp_path / "failures")
    monkeypatch.setattr(_common, "_sldworks_pids", lambda: {4242})
    monkeypatch.setattr(_common, "_seat_pids_at_start", frozenset({4242}))
    monkeypatch.setattr(_common, "_seat_identity", {})
    monkeypatch.setattr(_common, "_process_started_at", lambda pid: 1_700_000_000.0)
    monkeypatch.setattr(_common, "_process_memory", lambda pid: (1 << 30, 1 << 29))
    monkeypatch.setattr(_common, "_process_session_id", lambda pid: 1)
    yield


@pytest.fixture
def capture_telemetry():
    """Attach in-memory OTel exporters to the spine's live providers."""
    _telemetry.configure()
    spans = InMemorySpanExporter()
    processor = SimpleSpanProcessor(spans)
    cast(SdkTracerProvider, _telemetry.trace.get_tracer_provider()).add_span_processor(
        processor
    )
    _telemetry._span_processors.append(processor)
    _telemetry._aux_providers.clear()
    logs = InMemoryLogRecordExporter()
    cast(SdkLoggerProvider, get_logger_provider()).add_log_record_processor(
        SimpleLogRecordProcessor(logs)
    )
    yield spans, logs
    _telemetry._span_processors.remove(processor)
    _telemetry._aux_providers.clear()


# swconst R2026x ids, verified against this install's type library. Offline
# there is no swconst gencache to resolve member NAMES through, so the doubles
# expose the same name->id table the adapter carries -- which also exercises
# _preference_id's adapter.constants fallback.
_SW_SKETCH_INFERENCE = 249
_SW_SKETCH_AUTOMATIC_RELATIONS = 9
_SW_CONSTANTS = {
    "swSketchInference": _SW_SKETCH_INFERENCE,
    "swSketchAutomaticRelations": _SW_SKETCH_AUTOMATIC_RELATIONS,
    "swSketchInferFromModel": 95,
    "swSketchSnapsGrid": 278,
    "swSketch_Auto_Solve_Threshold": 564,
    "swDefaultTemplatePart": 8,
    "swSketchAddConstToRectEntity": 584,
}


def _unmerged_profile(tmp_path: Path) -> _Adapter:
    """A seat with inference OFF whose 4-line profile never closed: 8 points in
    4 coincident pairs, no contour -- the shape of the 91247A720 failure."""
    seat = _Seat(
        toggles={_SW_SKETCH_INFERENCE: False, _SW_SKETCH_AUTOMATIC_RELATIONS: False}
    )
    return _Adapter(
        sw=seat, model=_Model(tmp_path), sketch_manager=_SketchManager(add_to_db=True)
    )


def _failure_dir(tmp_path: Path, label: str = "logo-ring-extrude") -> Path:
    """The single timestamped capture directory written under ``<label>/``."""
    (captured,) = sorted((tmp_path / "failures" / label).iterdir())
    return captured


def test_capture_raises_the_callers_failure_unchanged(tmp_path):
    """Guarantee 1: the caller's exception type and message survive verbatim."""
    adapter = _unmerged_profile(tmp_path)
    with pytest.raises(RuntimeError, match=r"^logo ring extrude failed$"):
        _common.capture_com_failure(
            adapter,
            "logo-ring-extrude",
            "logo ring extrude failed",
            api="IFeatureManager.FeatureExtrusion3",
            sketch=_Sketch(contours=0, points=[]),
        )


def test_capture_raises_even_when_every_step_fails(tmp_path, monkeypatch):
    """Forensics may never convert a geometry failure into an unrelated crash.

    Every capture step is broken here -- including the artefact writer and the
    telemetry span itself -- and the caller still sees its own failure.
    """
    for name in (
        "seat_provenance",
        "sketch_authoring_preferences",
        "_seat_error_state",
        "_document_state",
        "_sketch_state",
        "_save_failure_document",
        "_save_seat_image",
        "_write_failure_report",
    ):
        monkeypatch.setattr(
            _common,
            name,
            lambda *a, **k: (_ for _ in ()).throw(OSError(f"{name} exploded")),
        )
    monkeypatch.setattr(
        _telemetry,
        "span",
        lambda *a, **k: (_ for _ in ()).throw(OSError("span exploded")),
    )
    with pytest.raises(ValueError, match=r"^rib cut failed$"):
        _common.capture_com_failure(
            _Adapter(), "rib-cut", "rib cut failed", exc_type=ValueError
        )


def test_one_step_failing_does_not_stop_the_others(tmp_path, monkeypatch):
    """A seat that refuses ONE read must still yield the other evidence."""
    monkeypatch.setattr(
        _common,
        "_sketch_state",
        lambda *a, **k: (_ for _ in ()).throw(OSError("sketch gone")),
    )
    adapter = _unmerged_profile(tmp_path)
    with pytest.raises(RuntimeError):
        _common.capture_com_failure(adapter, "logo-ring-extrude", "boom")

    report = json.loads((_failure_dir(tmp_path) / "capture.json").read_text())
    assert report["sketch"]["capture_error"].startswith("OSError:")
    assert report["seat"]["seat_pid"] == 4242
    assert report["document"]["title"] == "91247A720"


def test_artefacts_land_beside_the_report(tmp_path):
    """The document copy, the seat image and capture.json are the evidence a
    disposable worker must leave behind."""
    adapter = _unmerged_profile(tmp_path)
    with pytest.raises(RuntimeError):
        _common.capture_com_failure(
            adapter,
            "logo-ring-extrude",
            "logo ring extrude failed",
            sketch=_Sketch(contours=0, points=[]),
        )

    out = _failure_dir(tmp_path)
    assert (out / "capture.json").is_file()
    assert (out / "logo-ring-extrude.SLDPRT").is_file()
    assert (out / "logo-ring-extrude.bmp").is_file()
    # Saved SILENT and as a COPY, so the live document keeps its own path and a
    # headless leaf can never block on a save dialog.
    (_path, version, options) = adapter.currentModel.saved[0]
    assert (version, options) == (
        _common._SAVE_AS_CURRENT_VERSION,
        _common._SAVE_AS_SILENT_COPY,
    )


def test_unmerged_endpoints_are_visible_in_the_capture(tmp_path):
    """The inference fingerprint: no contour, and points in coincident pairs."""
    adapter = _unmerged_profile(tmp_path)
    corners = [(0.0, 0.0, 0.0), (0.01, 0.0, 0.0), (0.01, 0.01, 0.0), (0.0, 0.01, 0.0)]
    with pytest.raises(RuntimeError):
        _common.capture_com_failure(
            adapter,
            "logo-ring-extrude",
            "logo ring extrude failed",
            # Each corner twice: the endpoints of adjacent segments never merged.
            sketch=_Sketch(contours=0, points=corners * 2),
        )

    sketch = json.loads((_failure_dir(tmp_path) / "capture.json").read_text())["sketch"]
    assert sketch["contour_count"] == 0
    assert sketch["point_count"] == 8
    assert sketch["distinct_point_positions"] == 4
    assert sketch["coincident_point_pairs"] == 4
    assert sketch["constrained"] == "under-constrained"


def test_merged_profile_reports_no_coincident_pairs(tmp_path):
    """The control: the same profile with merged endpoints closes into a contour
    and shows zero coincident pairs -- so the fingerprint discriminates."""
    corners = [(0.0, 0.0, 0.0), (0.01, 0.0, 0.0), (0.01, 0.01, 0.0), (0.0, 0.01, 0.0)]
    adapter = _unmerged_profile(tmp_path)
    with pytest.raises(RuntimeError):
        _common.capture_com_failure(
            adapter, "logo-ring-extrude", "boom", sketch=_Sketch(contours=1, points=corners)
        )

    sketch = json.loads((_failure_dir(tmp_path) / "capture.json").read_text())["sketch"]
    assert sketch["contour_count"] == 1
    assert sketch["coincident_point_pairs"] == 0


def test_unreadable_preference_is_never_reported_as_false(tmp_path):
    """``GetUserPreferenceToggle`` answers an unknown id with a plausible
    ``False``; a silent one of those sends the next investigation the wrong way.
    """
    adapter = _unmerged_profile(tmp_path)
    prefs = _common.sketch_authoring_preferences(adapter)

    assert prefs["swSketchInference"] is False  # genuinely read as off
    assert prefs["swSketchAutomaticRelations"] is False
    # Every other toggle either did not resolve or the seat refused it.
    assert set(prefs) >= set(_common.SKETCH_AUTHORING_TOGGLE_NAMES)
    for name in _common.SKETCH_AUTHORING_TOGGLE_NAMES:
        if name not in ("swSketchInference", "swSketchAutomaticRelations"):
            assert prefs[name] in ("unresolved", "unreadable"), name
    # The id each name resolved to is recorded, so an id can be CONFIRMED
    # against the type library instead of assumed.
    assert prefs["preference_ids"]["swSketchInference"] == _SW_SKETCH_INFERENCE


def test_capture_emits_one_error_log_and_bounded_span_events(
    tmp_path, capture_telemetry
):
    """Guarantee 2: the evidence reaches telemetry -- once per capture STEP, plus
    exactly one ERROR record carrying the whole capture as JSON."""
    spans, logs = capture_telemetry
    adapter = _unmerged_profile(tmp_path)
    with pytest.raises(RuntimeError):
        _common.capture_com_failure(
            adapter,
            "logo-ring-extrude",
            "logo ring extrude failed",
            api="IFeatureManager.FeatureExtrusion3",
            # 40 sketch points must NOT become 40 span events.
            sketch=_Sketch(contours=0, points=[(0.001 * n, 0.0, 0.0) for n in range(40)]),
        )

    (sp,) = [s for s in spans.get_finished_spans() if s.name.startswith("com.failure ")]
    assert sp.attributes["api"] == "IFeatureManager.FeatureExtrusion3"
    events = [e.name for e in sp.events]
    assert events == [
        "com.failure.seat",
        "com.failure.preferences",
        "com.failure.sketch_manager",
        "com.failure.display",
        "com.failure.error_state",
        "com.failure.document",
        "com.failure.sketch",
        "com.failure.document_copy",
        "com.failure.seat_image",
        "com.failure.artefacts",
    ]

    errors = [
        r.log_record
        for r in logs.get_finished_logs()
        if r.log_record.severity_text == "ERROR"
    ]
    (record,) = errors
    assert "logo ring extrude failed" in record.body
    captured = json.loads(record.attributes["capture"])
    assert captured["sketch"]["point_count"] == 40
    assert captured["seat"]["seat_pid"] == 4242


def test_context_kwargs_ride_the_span_and_the_log(tmp_path, capture_telemetry):
    """Call-site context (which feature, which config) is what makes a capture
    searchable across leaves."""
    spans, logs = capture_telemetry
    with pytest.raises(RuntimeError):
        _common.capture_com_failure(
            _unmerged_profile(tmp_path),
            "logo-ring-extrude",
            "boom",
            depth_mm=1.2,
            feature="LogoRing",
        )

    (sp,) = [s for s in spans.get_finished_spans() if s.name.startswith("com.failure ")]
    assert sp.attributes["feature"] == "LogoRing"
    assert sp.attributes["depth_mm"] == 1.2
    report = json.loads((_failure_dir(tmp_path) / "capture.json").read_text())
    assert report["context"] == {"depth_mm": 1.2, "feature": "LogoRing"}


def test_seat_provenance_names_the_seat_and_its_origin(capture_telemetry):
    """Which sldworks.exe, how old, which Windows session, and whether THIS
    build started it -- the attribution a "failed once, passed on retry" leaf
    needs."""
    spans, logs = capture_telemetry
    adapter = _Adapter(sw=_Seat())

    prov = _common.record_seat_provenance(adapter)

    assert prov["seat_pid"] == 4242
    assert prov["seat_pid_source"] == "GetProcessID"
    assert prov["seat_origin"] == "attached"  # it was running before connect
    assert prov["seat_session_id"] == 1
    assert prov["seat_revision"] == "34.3.0"
    assert prov["seat_uptime_s"] > 0
    assert prov["seat_commit_bytes"] == 1 << 30
    # Published on the log channel too: the diagnostics/ probes build without a
    # phase span, so logs.jsonl is the only place their seat is attributable.
    bodies = [r.log_record.body for r in logs.get_finished_logs()]
    assert any("pid=4242" in str(body) for body in bodies)


def test_seat_origin_distinguishes_a_seat_this_build_started(monkeypatch):
    """A seat on its first document of the process is the leading suspect in any
    first-run-only failure, so "who started it" must not be guessed."""
    monkeypatch.setattr(_common, "_seat_identity", {})
    monkeypatch.setattr(_common, "_seat_pids_at_start", frozenset())
    assert _common.seat_provenance(_Adapter(sw=_Seat()))["seat_origin"] == (
        "started-by-build"
    )

    monkeypatch.setattr(_common, "_seat_identity", {})
    monkeypatch.setattr(_common, "_seat_pids_at_start", None)  # sample never ran
    assert _common.seat_provenance(_Adapter(sw=_Seat()))["seat_origin"] == "unknown"


def test_pre_connect_scan_failure_leaves_origin_unknown(monkeypatch):
    """The scan is best-effort: if it cannot run, the origin is ``unknown``
    rather than a wrong answer."""
    monkeypatch.setattr(
        _common,
        "_sldworks_pids",
        lambda: (_ for _ in ()).throw(OSError("wmi unavailable")),
    )
    _common.note_seats_before_connect()
    assert _common._seat_pids_at_start is None


def test_unresolvable_seat_pid_is_not_invented(monkeypatch):
    """Several seats running and no ``GetProcessID`` answer: no pid at all beats
    the wrong pid."""
    monkeypatch.setattr(_common, "_seat_identity", {})
    monkeypatch.setattr(_common, "_sldworks_pids", lambda: {11780, 13436})
    prov = _common.seat_provenance(_Adapter(sw=object()))

    assert prov["seat_pid_source"] == "unresolved"
    assert "seat_pid" not in prov


def test_watchdog_abort_names_the_seat_it_killed(capture_telemetry):
    """A watchdog kill is the one failure with no build-side record: the process
    is gone before any handler runs, so the abort itself must carry the seat."""
    spans, logs = capture_telemetry
    _watchdog.set_seat_provenance(
        {"seat_pid": 13436, "seat_uptime_s": 900.0, "ignored": "not a seat field"}
    )
    try:
        _watchdog._abort("crash", "SolidWorks crashed", _watchdog.EXIT_CRASH, idle_s=3)
    finally:
        _watchdog.set_seat_provenance({})

    (sp,) = [s for s in spans.get_finished_spans() if s.name == "watchdog.abort"]
    assert sp.attributes["seat_pid"] == 13436
    assert "ignored" not in sp.attributes
    record = next(
        r.log_record
        for r in logs.get_finished_logs()
        if r.log_record.severity_text == "ERROR"
    )
    assert record.attributes["seat_pid"] == 13436


def test_px_per_mm_is_measured_and_yields_a_snap_floor(tmp_path, monkeypatch):
    """The number that decides an inference-dependent profile.

    A sketch-inference snap is a SCREEN-SPACE hit test, so what governs whether
    two nearby points stay distinct is pixels-per-millimetre at authoring time --
    measured by projecting model points to the screen, not inferred from
    ``Scale2`` (which is uninterpretable without the client rect, and vice
    versa). At the 20 px/mm this seat reports, the 8 px snap tolerance covers
    0.4 mm: exactly the 91247A720 logo profile's nearest non-coincident
    competitor, i.e. the crossover this capture exists to make visible.
    """
    monkeypatch.setattr(
        _common,
        "_frame_geometry",
        lambda adapter: {
            "frame_hwnd": 0x1234,
            "frame_left": 0,
            "frame_top": 0,
            "frame_width_px": 2000,
            "frame_height_px": 1200,
            "frame_area_px": 2_400_000,
            "frame_client_width_px": 2000,
            "frame_client_height_px": 1200,
            "frame_state": "normal",
        },
    )
    geometry = _common.display_geometry(_unmerged_profile(tmp_path))

    assert geometry["px_per_mm"] == 20.0
    assert geometry["px_per_mm_x"] == 20.0
    assert geometry["snap_floor_mm"] == 0.4
    assert geometry["snap_tolerance_px"] == 8
    # The raw inputs behind it are kept: neither is interpretable alone.
    assert geometry["view_scale2"] == 3.5
    assert geometry["visible_width_mm"] == 100.0
    assert geometry["px_per_mm_from_box"] == 20.0


def test_the_main_window_rect_is_recorded_as_comparable_integers(tmp_path):
    """The MEASURED root cause: the failing seat's window was 1024x640 against
    1278x750 and 1296x816 on the two seats that passed -- 0.620 of the area,
    monotonic with the outcome, and recorded nowhere. A "1024x640" label would
    not answer "smaller than the seat that passed?"; integers and an area do.
    """
    rects = {
        "GetWindowRect": (12, 34, 12 + 1024, 34 + 640),
        "GetClientRect": (0, 0, 1008, 600),
    }

    class _User32:
        def __getattr__(self, name):
            if name in rects:
                def fill(hwnd, pointer, _name=name):
                    rect = ctypes.cast(pointer, ctypes.POINTER(_common._Rect))[0]
                    rect.left, rect.top, rect.right, rect.bottom = rects[_name]
                    return 1

                return fill
            return lambda *args: 0  # IsIconic / IsZoomed: a normal window

    with mock.patch.object(_common.ctypes, "windll", mock.Mock(user32=_User32())):
        geometry = _common._frame_geometry(_unmerged_profile(tmp_path))

    assert geometry["frame_width_px"] == 1024
    assert geometry["frame_height_px"] == 640
    assert geometry["frame_area_px"] == 1024 * 640
    assert (geometry["frame_left"], geometry["frame_top"]) == (12, 34)
    assert geometry["frame_client_width_px"] == 1008
    assert geometry["frame_state"] == "normal"
    # The comparison the investigation had to do by hand, now arithmetic:
    assert round(geometry["frame_area_px"] / (1296 * 816), 3) == 0.620


def test_display_geometry_flags_a_session_without_a_display(tmp_path, monkeypatch):
    """A disconnected RDP session reports a degenerate desktop; that is the
    documented "frame froze after someone RDP'd in" shape, and it makes every
    view measurement meaningless -- so it is recorded, not silently reported as
    a healthy 0x0 screen."""
    monkeypatch.setattr(
        _common.ctypes.windll.user32, "GetSystemMetrics", lambda index: 0
    )
    geometry = _common.display_geometry(_unmerged_profile(tmp_path))

    assert geometry["screen_px"] == "0x0"
    assert geometry["session_has_display"] is False


def test_sketch_manager_state_is_captured_separately_from_preferences(tmp_path):
    """The blind spot that made tonight's log read clean.

    ``AddToDB``/``AutoInference``/``AutoSolve`` are sticky per-SESSION state that
    ``GetUserPreferenceToggle`` cannot see, and ``AddToDB=True`` bypasses
    inference relations at creation time whatever ``swSketchInference`` says. A
    capture that read only user preferences would report a healthy seat.
    """
    adapter = _unmerged_profile(tmp_path)
    with pytest.raises(RuntimeError):
        _common.capture_com_failure(adapter, "logo-ring-extrude", "boom")

    report = json.loads((_failure_dir(tmp_path) / "capture.json").read_text())
    assert report["sketch_manager"]["AddToDB"] is True
    assert report["sketch_manager"]["scope"] == "session"
    # ... and the preference snapshot, on the same seat, says inference is a
    # preference-level False: two different bags, both recorded.
    assert report["preferences"]["swSketchInference"] is False


def test_expected_points_turns_the_census_into_a_verdict(tmp_path):
    """An author that declares how many points a MERGED profile keeps lets the
    artefact state the verdict instead of leaving it to be counted.

    The fingerprint is the point COUNT, not the distinct positions: two
    exactly-coincident endpoints sit at the same place whether or not they
    merged, so an unmerged 9-segment ring reports 18 points across 9 distinct
    places -- nine coincident pairs, nine merges that did not happen.
    """
    places = [(0.001 * n, 0.0, 0.0) for n in range(9)]
    with pytest.raises(RuntimeError):
        _common.capture_com_failure(
            _unmerged_profile(tmp_path),
            "logo-ring-extrude",
            "logo ring extrude failed",
            sketch=_Sketch(contours=0, points=places + places),
            expected_points=9,
        )

    sketch = json.loads((_failure_dir(tmp_path) / "capture.json").read_text())["sketch"]
    assert sketch["expected_distinct_points"] == 9
    assert sketch["point_count"] == 18
    assert sketch["distinct_point_positions"] == 9
    assert sketch["coincident_point_pairs"] == 9
    assert sketch["unmerged_points"] == 9


def test_a_merged_profile_reports_no_unmerged_points(tmp_path):
    """The control: the same declaration against a profile whose endpoints DID
    merge must read zero, or the verdict means nothing."""
    places = [(0.001 * n, 0.0, 0.0) for n in range(9)]
    with pytest.raises(RuntimeError):
        _common.capture_com_failure(
            _unmerged_profile(tmp_path),
            "logo-ring-extrude",
            "logo ring extrude failed",
            sketch=_Sketch(contours=1, points=places),
            expected_points=9,
        )

    sketch = json.loads((_failure_dir(tmp_path) / "capture.json").read_text())["sketch"]
    assert sketch["coincident_point_pairs"] == 0
    assert sketch["unmerged_points"] == 0


def test_a_census_that_cannot_be_read_says_so(tmp_path):
    """A census that raised must leave a stated error, not an absent key: the
    reader must never mistake "could not count" for "nothing coincident"."""

    class _Unreadable(_Sketch):
        def GetSketchPoints2(self):
            raise OSError("RPC_E_DISCONNECTED")

    with pytest.raises(RuntimeError):
        _common.capture_com_failure(
            _unmerged_profile(tmp_path),
            "logo-ring-extrude",
            "logo ring extrude failed",
            sketch=_Unreadable(contours=0, points=[]),
            expected_points=9,
        )

    sketch = json.loads((_failure_dir(tmp_path) / "capture.json").read_text())["sketch"]
    assert "RPC_E_DISCONNECTED" in sketch["point_census_error"]
    assert "point_count" not in sketch


def test_retry_capture_does_not_erase_the_first_failure(tmp_path):
    """A retried failure must not overwrite the evidence of the failure it is
    retrying -- the exact way tonight's failing leaf log was lost."""
    for _ in range(2):
        with pytest.raises(RuntimeError):
            _common.capture_com_failure(
                _unmerged_profile(tmp_path), "logo-ring-extrude", "boom"
            )
        # The directory is stamped to the second; a same-second retry would
        # otherwise land in the same place.
        time.sleep(1.1)

    captures = sorted((tmp_path / "failures" / "logo-ring-extrude").iterdir())
    assert len(captures) == 2
    assert all((capture / "capture.json").is_file() for capture in captures)


def test_authoring_context_is_recorded_on_the_success_path(tmp_path, capture_telemetry):
    """A failure-only capture cannot answer "what was different about the run
    that worked?", so the same state bags are recorded per part build."""
    spans, logs = capture_telemetry
    context = _common.record_authoring_context(_unmerged_profile(tmp_path), "logo_ring")

    assert context["display"]["px_per_mm"] > 0
    assert context["sketch_manager"]["AddToDB"] is True
    events = [
        event
        for span in spans.get_finished_spans()
        for event in span.events
        if event.name == "seat.authoring_context"
    ]
    # Recorded even with no enclosing span: the log record is the channel the
    # diagnostics/ probes (which build no phase span) are attributable through.
    bodies = [str(r.log_record.body) for r in logs.get_finished_logs()]
    assert any("authoring logo_ring: px/mm=" in body for body in bodies)
    assert len(events) <= 1


def test_add_to_db_left_on_by_a_dead_leaf_is_reported(capture_telemetry):
    """``AddToDB`` is session state on a seat that outlives the leaf: finding it
    already ON means an earlier leaf died between its True and its False."""
    spans, logs = capture_telemetry
    adapter = _Adapter(sw=_Seat(), sketch_manager=_SketchManager(add_to_db=True))

    _common.set_sketch_direct_db(adapter, True)

    warnings = [
        str(r.log_record.body)
        for r in logs.get_finished_logs()
        if r.log_record.severity_text == "WARN"
    ]
    assert any("AddToDB was already True" in body for body in warnings)


def test_a_healthy_add_to_db_transition_does_not_warn(capture_telemetry):
    """The control: the normal OFF -> ON transition is recorded, not warned
    about (a warning on every build is a warning nobody reads)."""
    spans, logs = capture_telemetry
    adapter = _Adapter(sw=_Seat(), sketch_manager=_SketchManager(add_to_db=False))

    _common.set_sketch_direct_db(adapter, True)

    assert adapter.currentSketchManager.AddToDB is True
    assert not [
        r for r in logs.get_finished_logs() if r.log_record.severity_text == "WARN"
    ]


class _PreferenceSeat:
    """An ``ISldWorks`` whose preference values are readable and writable."""

    def __init__(self, values: dict[int, Any], *, refuse: set[int] | None = None):
        self.values = dict(values)
        self._refuse = refuse or set()
        self.writes: list[tuple[int, Any]] = []

    def GetUserPreferenceToggle(self, pref: int) -> Any:
        return self.values[pref]

    def SetUserPreferenceToggle(self, pref: int, value: Any) -> None:
        self.writes.append((pref, value))
        if pref not in self._refuse:  # a refused write reads back unchanged
            self.values[pref] = value


_INFERENCE_SPEC = _common.PreferenceSpec(
    label="test-sketch-inference",
    toggles={"swSketchInference": False},
    baseline_toggles={"swSketchInference": True},
)


def _preference_adapter(values: dict[int, Any], **kwargs) -> _Adapter:
    return _Adapter(sw=_PreferenceSeat(values, **kwargs))


def test_enforce_writes_the_declaration_and_reports_the_drift(capture_telemetry):
    """A seat carrying a stranded value is CORRECTED and the drift reported --
    never inherited as "the original", which is how the old observed-value
    latches perpetuated a mutated seat forever."""
    spans, logs = capture_telemetry
    seat = _PreferenceSeat({_SW_SKETCH_INFERENCE: False})
    adapter = _Adapter(sw=seat)

    drift = _common.enforce_preferences(
        adapter,
        _common.PreferenceSpec(
            label="test-enforce", toggles={"swSketchInference": True}
        ),
    )

    assert seat.values[_SW_SKETCH_INFERENCE] is True
    assert drift == {"swSketchInference": False}
    warnings = [
        str(r.log_record.body)
        for r in logs.get_finished_logs()
        if r.log_record.severity_text == "WARN"
    ]
    assert any("differed from the declared baseline" in body for body in warnings)


def test_enforce_on_a_clean_seat_is_silent(capture_telemetry):
    """The control: no drift, no warning (an every-build warning is noise)."""
    spans, logs = capture_telemetry
    adapter = _preference_adapter({_SW_SKETCH_INFERENCE: True})

    assert _common.enforce_preferences(
        adapter,
        _common.PreferenceSpec(label="test-clean", toggles={"swSketchInference": True}),
    ) == {}
    assert not [
        r for r in logs.get_finished_logs() if r.log_record.severity_text == "WARN"
    ]


def test_override_restores_the_declared_baseline_not_the_observed_value():
    """The defect this replaces: a seat that came in POISONED (inference off)
    must come out at the declared baseline (on), not back at the poisoned value
    it was observed to hold."""
    seat = _PreferenceSeat({_SW_SKETCH_INFERENCE: False})
    with _common.preference_override(_Adapter(sw=seat), _INFERENCE_SPEC):
        assert seat.values[_SW_SKETCH_INFERENCE] is False
    assert seat.values[_SW_SKETCH_INFERENCE] is True


def test_nested_override_does_not_restore_mid_flight():
    """Depth counting: restoring a declared baseline from a NESTED exit would be
    worse than the old latch, because the outer block is still relying on the
    override."""
    seat = _PreferenceSeat({_SW_SKETCH_INFERENCE: True})
    adapter = _Adapter(sw=seat)
    with _common.preference_override(adapter, _INFERENCE_SPEC):
        with _common.preference_override(adapter, _INFERENCE_SPEC):
            assert seat.values[_SW_SKETCH_INFERENCE] is False
        # Inner exit restored nothing: the outer block still needs it off.
        assert seat.values[_SW_SKETCH_INFERENCE] is False
    assert seat.values[_SW_SKETCH_INFERENCE] is True


def test_override_depth_unwinds_even_when_the_restore_write_throws():
    """A restore that raises must not pin the depth above zero: that would make
    every later block on this long-lived adapter silently apply nothing and
    restore nothing -- the latch again, one level up."""
    seat = _PreferenceSeat({_SW_SKETCH_INFERENCE: True})

    class _ExplodingSeat(_PreferenceSeat):
        def SetUserPreferenceToggle(self, pref: int, value: Any) -> None:
            if value is True:  # the restore direction
                raise OSError("seat refused the restore")
            super().SetUserPreferenceToggle(pref, value)

    exploding = _ExplodingSeat({_SW_SKETCH_INFERENCE: True})
    with contextlib.suppress(OSError):
        with _common.preference_override(_Adapter(sw=exploding), _INFERENCE_SPEC):
            pass
    assert _common._override_depth[_INFERENCE_SPEC.label] == 0

    # Proof it is not latched: the next block still applies and restores.
    with _common.preference_override(_Adapter(sw=seat), _INFERENCE_SPEC):
        assert seat.values[_SW_SKETCH_INFERENCE] is False
    assert seat.values[_SW_SKETCH_INFERENCE] is True


def test_a_refused_preference_write_warns_instead_of_failing_the_build(
    capture_telemetry,
):
    """Some preferences are write-ignored by design (a per-document one read
    through the system accessor). Raising would turn seat hygiene into an
    outage, so a refused write is reported at WARN and the block still runs."""
    spans, logs = capture_telemetry
    seat = _PreferenceSeat({_SW_SKETCH_INFERENCE: True}, refuse={_SW_SKETCH_INFERENCE})

    with _common.preference_override(_Adapter(sw=seat), _INFERENCE_SPEC):
        pass

    warnings = [
        str(r.log_record.body)
        for r in logs.get_finished_logs()
        if r.log_record.severity_text == "WARN"
    ]
    assert any("refused" in body for body in warnings)


def test_a_declared_spec_cannot_be_mutated_in_place():
    """The baseline is a DECLARED constant: a recipe must not be able to
    accumulate into the fleet's declaration."""
    with pytest.raises(TypeError):
        _INFERENCE_SPEC.toggles["swSketchInference"] = True


def test_an_open_sketch_is_reported_at_exit_not_at_the_extrude(capture_telemetry):
    """The gap that cost the 2026-09-17 investigation: exit_sketch returned OK
    and the extrude failed 1.9 s later with nothing recorded in between. A
    sketch the seat ACCEPTED with no closed contour must say so at closure."""
    spans, logs = capture_telemetry
    places = [(0.001 * n, 0.0, 0.0) for n in range(9)]
    adapter = _Adapter(sw=_Seat(), sketch_manager=_SketchManager())

    verdict = _common.record_sketch_closure(
        adapter,
        "logo",
        _Sketch(contours=0, points=places + places),
        expected_points=9,
    )

    assert verdict["closure"] == "open"
    assert verdict["contour_count"] == 0
    assert verdict["unmerged_points"] == 9
    warnings = [
        str(r.log_record.body)
        for r in logs.get_finished_logs()
        if r.log_record.severity_text == "WARN"
    ]
    assert any("no usable contour" in body for body in warnings)


def test_a_closed_sketch_records_its_verdict_without_warning(capture_telemetry):
    """The control, and the reason this runs on the success path too: a good
    sketch logs the counts a later failure has to be compared against, and does
    not cry wolf on every build."""
    spans, logs = capture_telemetry
    places = [(0.001 * n, 0.0, 0.0) for n in range(9)]
    adapter = _Adapter(sw=_Seat(), sketch_manager=_SketchManager())

    verdict = _common.record_sketch_closure(
        adapter, "logo", _Sketch(contours=2, points=places), expected_points=9
    )

    assert verdict["closure"] == "closed"
    assert verdict["unmerged_points"] == 0
    assert not [
        r for r in logs.get_finished_logs() if r.log_record.severity_text == "WARN"
    ]


def test_a_closure_verdict_that_cannot_be_read_never_raises(capture_telemetry):
    """A sketch that would have built must not fail on the way to being
    described: the verdict degrades to "unknown" and the caller decides."""
    spans, logs = capture_telemetry

    class _Hostile:
        def __getattr__(self, name):
            raise OSError("RPC_E_DISCONNECTED")

    verdict = _common.record_sketch_closure(
        _Adapter(sw=_Seat()), "logo", _Hostile()
    )

    assert verdict["closure"] == "unknown"


def test_authored_profile_geometry_is_logged_for_every_profile(capture_telemetry):
    """Per-entity logs were inconsistent -- shank/hex/cutter logged every line,
    logo logged nothing -- so one uniform line states the AUTHOR's intent:
    endpoints emitted, distinct places, coincidences the seat must merge."""
    spans, logs = capture_telemetry
    places = [(0.001 * n, 0.0, 0.0) for n in range(9)]

    intent = _common.log_profile_geometry("logo", places + places)

    assert intent == {
        "profile": "logo",
        "authored_points": 18,
        "distinct_places": 9,
        "expected_merges": 9,
    }
    assert any(
        "9 coincidences to merge" in str(r.log_record.body)
        for r in logs.get_finished_logs()
    )


def test_warn_and_error_lines_carry_an_absolute_utc_stamp():
    """The leaf log's stamps are elapsed seconds, and the only absolute stamp in
    it on 2026-09-17 was LOCAL (21:58:42) against blob metadata in UTC
    (04:59:59Z) -- the same event reading as two runs seven hours apart."""
    when = datetime(2026, 9, 18, 4, 59, 59, tzinfo=timezone.utc)
    record = logging.LogRecord(
        "harmonic", logging.WARNING, __file__, 1, "seat drifted", None, None
    )
    record.created = when.timestamp()

    line = _telemetry._FriendlyFormatter().format(record)

    assert line.endswith("@2026-09-18T04:59:59.000Z")
    info = logging.LogRecord(
        "harmonic", logging.INFO, __file__, 1, "create_sketch logo", None, None
    )
    # INFO stays compact: a 600-line build log must remain readable.
    assert "@" not in _telemetry._FriendlyFormatter().format(info)


def test_the_log_states_what_t_zero_was_in_utc(capture_telemetry, monkeypatch):
    """Elapsed-seconds stamps are only correlatable if something says what t=0
    was; nothing did, so the reader depended on whichever library happened to
    print a timestamp.

    The banner must survive the terse mode a farm leaf runs in: at warning-only
    console verbosity an INFO record is dropped, which is precisely when the log
    is hardest to place in time.
    """
    spans, logs = capture_telemetry
    terse = logging.StreamHandler(stream=io.StringIO())
    terse.setLevel(logging.WARNING)
    monkeypatch.setattr(_telemetry, "_anchor_printed", False)

    _telemetry._log_utc_anchor(_telemetry.get_logger(), terse)

    banner = terse.stream.getvalue()
    assert "log anchor" in banner
    assert re.search(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z", banner)
    # ... and the structured sinks get it as a real record too.
    anchors = [
        str(r.log_record.body)
        for r in logs.get_finished_logs()
        if "log anchor" in str(r.log_record.body)
    ]
    assert anchors and anchors[-1].endswith("carries its own @UTC")


def test_the_anchor_banner_is_printed_once_per_process(monkeypatch):
    """A reconfigure (dodo relabels the service mid-process) must not restate
    the anchor: a header repeated at random depths reads like a new run."""
    stream = logging.StreamHandler(stream=io.StringIO())
    monkeypatch.setattr(_telemetry, "_anchor_printed", False)

    for _ in range(3):
        _telemetry._log_utc_anchor(_telemetry.get_logger(), stream)

    assert stream.stream.getvalue().count("log anchor") == 1


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
