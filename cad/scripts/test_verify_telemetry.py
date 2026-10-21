r"""Telemetry-shape tests for the verify gates, driven by a MOCK SolidWorks.

The real COM seat is replaced with a fake adapter + fake model/component/IDM
objects whose every COM call ``time.sleep``s for a duration *calibrated from the
v0.10.0 release logs* (``harmonic-analyzer-v0.10.0-logs.zip`` ->
``verify-soundness.log``). Everything ABOVE that seam is the production code:
``verify._verify_static_one`` opens the doc, activates the pose, and runs the
real gates through the real ``_telemetry`` spine. Component state and channel
native readbacks are headless synthetic data, NOT a CAD correctness proof;
the wall-clock is scaled (``HARMONIC_MOCK_SCALE``, default 0.01).

This pins the two span-shape fixes this module exists to prove:

  * **De-noised** -- the per-component ``dof.check`` span and the per-target
    ``health.whats_wrong`` span (the "multiple whats_wrong calls in sequence"
    flood: 335 + 343 near-instant leaf spans across one soundness pass) are gone;
    each collapses into its parent gate span carrying aggregate attributes.
  * **Detailed** -- the three gates that used to be a single opaque 80-90 s span
    (``no-over-constrained`` / ``gear-ratios`` / ``component-count``) plus the
    per-assembly open/activate now open child spans, so no gate hides a large
    unspanned gap.

    python cad/scripts/test_verify_telemetry.py            # pytest
    python cad/scripts/test_verify_telemetry.py --demo     # print the real
                                                           # console span tree
    HARMONIC_MOCK_SCALE=1.0 ... --demo                     # real wall-clock
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import sys
import time
import types
from pathlib import Path
from typing import Any

import pytest

# Export nowhere (no Aspire probe / OTLP retries) BEFORE the spine configures.
os.environ.setdefault("OTEL_EXPORTER_OTLP_ENDPOINT", "")

sys.path.insert(0, str(Path(__file__).resolve().parent))


# --------------------------------------------------------------------------- #
# SolidWorks isolation. This module used to install bare `types.ModuleType`    #
# stand-ins for `solidworks_mcp`, `.adapters`, `.adapters.solidworks` and      #
# `.adapters.solidworks.assembly`, plus hand-written fakes for the few symbols #
# the verify import graph reached. A bare ModuleType has no `__path__`, so     #
# every submodule the enumeration did NOT fake died on import with            #
# "solidworks_mcp.adapters is not a package" -- and the graph kept growing     #
# past the list (`_part_pmi` -> `...pywin32_adapter.null_callout`,             #
# `_native_spring_contact` -> `...com_variant.dispatch_array`), which is how   #
# collection of this file broke. Faking submodules one at a time is a race     #
# against the import graph, so the fakes are GONE: the REAL package is         #
# imported instead. It is import-safe and seat-free -- importing it binds      #
# pywin32 but never dispatches SolidWorks (no `sw.connect`, ~0.6 s), and the   #
# COM behaviour under test still comes from the mock adapter below, which      #
# `_verify_static_one` is handed explicitly. `_gear_mate_links` is             #
# monkeypatched per-test, so the real one is never called either.              #
#                                                                             #
# What the fakes DID carry that the real package cannot is one behavioural     #
# neutralization, kept below.                                                  #
# --------------------------------------------------------------------------- #
@contextlib.contextmanager
def _com_method_flagging_neutralized():
    """Keep `sw_type_info.flag_methods` a no-op against the mock, and PUT IT BACK.

    Flagging exists so pywin32 dispatches zero-arg SolidWorks methods as
    methods rather than properties; the mock objects are plain Python with no
    `_oleobj_`, so there is nothing to flag. On the real module the call would
    import the vendored makepy wrapper (6 MB of generated classes) just to
    attempt `_FlagAsMethod` on objects that have none.

    Measured today the gate never reaches it (0 calls across the 14 tests):
    `_com._early_bound` passes a test double straight through before it
    touches `sw_type_info`, and `_com._flag` -- the caller the removed stub
    was written for -- no longer has call sites. This stays as the standing
    isolation invariant the stub module used to provide, so a gate that starts
    flagging methods cannot pull real COM type info into a seatless gate.

    Scoped, not assigned at import: `check:recipe` runs every offline test
    file in ONE pytest process, so a module-level assignment would leak into
    a later test that legitimately reaches `_com._flag` and silently skip
    real COM method flagging there (CodeRabbit, PR #771).
    """
    from solidworks_mcp.adapters import sw_type_info

    original = sw_type_info.flag_methods
    sw_type_info.flag_methods = lambda obj, *interfaces: 0  # type: ignore[assignment]
    try:
        yield
    finally:
        sw_type_info.flag_methods = original


@pytest.fixture(autouse=True, scope="module")
def _neutralize_com_method_flagging():
    with _com_method_flagging_neutralized():
        yield

import _assembly  # noqa: E402
import _telemetry  # noqa: E402
import verify  # noqa: E402
import rocker_bank_layout  # noqa: E402
from test_native_spring_contact import (  # noqa: E402
    _IDENTITY,
    _IntersectionBody,
    _NativeBody,
)

# --------------------------------------------------------------------------- #
# Timing model -- base seconds per COM call, lifted from verify-soundness.log   #
# (v0.10.0), scaled by HARMONIC_MOCK_SCALE so a full pass runs in seconds while #
# preserving the REAL relative shape (rebuild dominates; per-component ~0.6 s;  #
# the gear-mate walk ~80 s; open ~8 s; activate ~17 s).                         #
# --------------------------------------------------------------------------- #
SCALE = float(os.environ.get("HARMONIC_MOCK_SCALE", "0.01"))

T_OPEN = 8.0
T_LIST_CONFIGS = 0.1
T_ACTIVATE = 17.0
T_REBUILD_PER_COMP = 0.30      # ForceRebuild3 scales with the component count
T_GETCOMPONENTS_PER_COMP = 0.04
T_NAME2 = 0.18
T_IS_FIXED = 0.10
T_IS_PATTERN = 0.06
T_CONSTRAINED_STATUS = 0.28    # ~0.62 s/comp total, matching the +0.6 s log step
T_GET_MODELDOC2 = 0.04
T_GEAR_LINKS_OWNER = 80.0      # the MateGroup walk, drive-train only
T_GEAR_LINKS_OTHER = 0.15
T_TOOLS_INTERFERENCE = 0.3
T_GET_INTERFERENCES = 0.7
T_WHATS_WRONG = 0.03           # per target, the leaf that used to flood the trace
T_LIST_MATES = 0.2             # MateGroup walk (list_mates)


def _sleep(seconds: float) -> None:
    if SCALE > 0:
        time.sleep(seconds * SCALE)


# Preserve the frame/drive-train timing populations from the historical reference
# bands. Channel occurrences are built from configured rows below, never padded
# to a count-band midpoint.
COMPONENT_COUNTS = {
    name: sum(verify._COMPONENT_BAND[name]) // 2
    for name in ("fr-frame", "dt-drive-train")
}
_DEFAULT_ASSEMBLIES = ("fr-frame", "dt-drive-train", "ch-channel")


# --------------------------------------------------------------------------- #
# Mock COM objects. Each method sleeps its calibrated duration, then returns    #
# explicit component/native-port data for the unchanged production consumers.  #
# --------------------------------------------------------------------------- #
class _Result:
    """Mirrors the adapter result protocol check() reads (is_success/.data)."""

    def __init__(self, data: Any = None, *, ok: bool = True, error: str = "") -> None:
        self.is_success = ok
        self.data = data
        self.error = error


class MockComponent:
    def __init__(
        self,
        name: str,
        model: "MockModel",
        *,
        source_stem: str,
        fixed: bool = False,
        pattern: bool = False,
        status: int = _assembly.FULLY_CONSTRAINED,
        station_z_mm: float = 0.0,
    ) -> None:
        self._name = name
        self._model = model
        self.source_stem = source_stem
        self.fixed = fixed
        self.pattern = pattern
        self.status = status
        transform = list(_IDENTITY)
        transform[11] = station_z_mm / 1000.0
        self.Transform2 = types.SimpleNamespace(ArrayData=transform)

    # _read_member calls these (callable -> invoked); the per-comp cost lives here.
    def Name2(self) -> str:
        _sleep(T_NAME2)
        return self._name

    def IsFixed(self) -> bool:
        _sleep(T_IS_FIXED)
        return self.fixed

    def IsPatternInstance(self) -> bool:
        _sleep(T_IS_PATTERN)
        return self.pattern

    def GetConstrainedStatus(self) -> int:
        _sleep(T_CONSTRAINED_STATUS)
        return self.status

    def GetPathName(self) -> str:
        return f"C:/cad/out/sldprt/{self.source_stem}.SLDPRT" if self.source_stem else ""

    def GetBodies3(self, body_type: int):
        assert body_type == 0  # swSolidBody, as in test_native_spring_contact.
        return (_NativeBody(self._model, self, self._name),), (0,)

    def GetModelDoc2(self) -> "MockModel":
        # A distinct per-component sub-document, so assert_model_healthy's deep
        # sweep builds N+1 What's Wrong targets -- the pre-fix flood source.
        _sleep(T_GET_MODELDOC2)
        return MockModel(f"{self._name}#doc", 0)


class MockIDM:
    """InterferenceDetectionManager: accepts the config setters, returns clean."""

    TreatCoincidenceAsInterference = False
    TreatSubAssembliesAsComponents = False
    IncludeMultibodyPartInterferences = False
    MakeInterferingPartsTransparent = False
    CreateFastenersFolder = False
    UseTransform = False

    def GetInterferences(self) -> list:
        _sleep(T_GET_INTERFERENCES)
        return []

    def Done(self) -> None:
        pass


class MockModel:
    def __init__(self, name: str, n_components: int = 0) -> None:
        self._name = name
        self._comps: list[MockComponent] = []
        self.distances_mm: dict[tuple[str, str], float] = {}
        self.overlaps_mm3: dict[tuple[str, str], float] = {}
        if name == "ch-channel":
            self._populate_channel()
        elif n_components:
            # Retain the old timing population and contract-family coverage for
            # frame/drive-train, with actual structural seeds and explicit state.
            seed, structure = {
                "fr-frame": ("fr-harmonic-base", "fr-tube-frame"),
                "dt-drive-train": ("dt-cylinder-gear-shaft", "dt-arbor-pedestal"),
            }[name]
            required = verify._required_free_stems(name)
            allowed = verify.allowed_free_stems(name) or required
            stems = (*required, *(stem for stem in allowed if stem not in required))
            free = bool(verify._expected_free_dof(name))
            for index in range(n_components):
                stem = seed if index == 0 else (
                    stems[(index - 1) % len(stems)] if stems else structure
                )
                self._comps.append(MockComponent(
                    f"{stem}-{index + 1}",
                    self,
                    source_stem=stem,
                    fixed=index == 0,
                    status=(
                        _assembly.UNDER_CONSTRAINED
                        if index > 0 and free and stem in allowed
                        else _assembly.FULLY_CONSTRAINED
                    ),
                ))
        self.InterferenceDetectionManager = MockIDM()
        self.Extension = types.SimpleNamespace(NeedsRebuild2=0)
        # Count ForceRebuild3 calls so a test can prove the soundness suite shares
        # ONE re-solve across the dof/over/health gates instead of rebuilding 3x.
        self.rebuild_calls = 0

    def _populate_channel(self) -> None:
        """Model the configured moving bank and grounded spring-seat occurrences."""
        config = verify._config
        rows = config.active_channels()
        assert len(rows) == config.active_count()
        allowed = verify.allowed_free_stems("ch-channel")
        free = bool(verify._expected_free_dof("ch-channel"))
        # Real builder seeds/structure, not an assembly masquerading as a part.
        self._comps.extend((
            MockComponent("ch-pivot-shaft-1", self, source_stem="ch-pivot-shaft", fixed=True),
            MockComponent("ch-fulcrum-shaft-1", self, source_stem="ch-fulcrum-shaft"),
        ))
        # The builder assigns stretch indices in full-preset first-occurrence
        # order, even when only an active prefix is installed.
        variants = {
            amplitude: index
            for index, amplitude in enumerate(dict.fromkeys(config.amplitudes()))
        }
        records = {
            float(record["amplitude_mm"]): record
            for record in config.machine("springs", "channel_seats")
        }
        spring_occurrences: dict[str, int] = {}
        for station, row in enumerate(rows):
            station_z_mm = rocker_bank_layout.hub_mid_z(station)
            for stem in verify._MOVING_CHANNEL_STEMS:
                self._comps.append(MockComponent(
                    f"{stem}-{station + 1}",
                    self,
                    source_stem=stem,
                    status=(
                        _assembly.UNDER_CONSTRAINED
                        if free and stem in allowed
                        else _assembly.FULLY_CONSTRAINED
                    ),
                    station_z_mm=station_z_mm,
                ))
            amplitude = float(row["amplitude_mm"])
            spring_stem = (
                f"ch-vn-channel-spring-installed-stretch{variants[amplitude]:02d}"
            )
            spring_occurrences[spring_stem] = spring_occurrences.get(spring_stem, 0) + 1
            spring_name = f"{spring_stem}-{spring_occurrences[spring_stem]}"
            hook_name = f"ch-vn-spring-hook-{station + 1}"
            for name, stem in (
                (spring_name, spring_stem),
                (hook_name, "ch-vn-spring-hook"),
                (f"ch-anchor-jam-nut-{station + 1}", "ch-anchor-jam-nut"),
            ):
                self._comps.append(MockComponent(
                    name, self, source_stem=stem, fixed=True, station_z_mm=station_z_mm
                ))
            # Native DATA only: measured settled readbacks, NOT acceptance
            # maxima from channel_seat() or distances manufactured from bounds.
            measured = records[amplitude]["final_distance_mm"]
            self.distances_mm[(spring_name, hook_name)] = float(measured["lower"])
            self.distances_mm[(spring_name, f"ch-channel-lever-{station + 1}")] = float(
                measured["upper"]
            )

    def GetComponentByName(self, name: str) -> MockComponent | None:
        return next((component for component in self._comps if component._name == name), None)

    def ClosestDistance(self, first: MockComponent, second: MockComponent):
        measured_mm = self.distances_mm[(first._name, second._name)]
        return measured_mm / 1000.0, (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)

    def intersection(self, target: str, tool: str):
        # Reuse the native-contact test's temporary-body/copy/transform ports.
        # No result bodies is a measured zero-volume intersection, not a
        # replacement for native_component_overlap_mm3 or any gate.
        measured_mm3 = self.overlaps_mm3.get((target, tool))
        if measured_mm3 is None:
            return None, 0
        return (_IntersectionBody(measured_mm3),), 0

    def ForceRebuild3(self, _quiet: bool) -> bool:
        self.rebuild_calls += 1
        _sleep(T_REBUILD_PER_COMP * len(self._comps))
        return True

    def GetComponents(self, _top_level_only: bool) -> list:
        _sleep(T_GETCOMPONENTS_PER_COMP * len(self._comps))
        return list(self._comps)

    def ToolsCheckInterference(self) -> int:
        _sleep(T_TOOLS_INTERFERENCE)
        return 0


class MockAdapter:
    """The seam verify.py talks to: open/activate + _attempt + currentModel."""

    def __init__(self) -> None:
        self._current: MockModel | None = None
        self.swApp = types.SimpleNamespace(CloseAllDocuments=lambda _: None)

    @property
    def currentModel(self) -> MockModel:
        assert self._current is not None
        return self._current

    def _attempt(self, fn, default: Any = None) -> Any:
        try:
            return fn()
        except Exception:
            return default

    async def open_model(self, path: str) -> _Result:
        _sleep(T_OPEN)
        stem = Path(path).stem
        self._current = MockModel(stem, COMPONENT_COUNTS.get(stem, 0))
        return _Result(True)

    async def list_configurations(self) -> _Result:
        _sleep(T_LIST_CONFIGS)
        return _Result([verify.REST])

    async def set_active_configuration(self, _cfg: str) -> _Result:
        _sleep(T_ACTIVATE)
        return _Result(True)

    async def list_mates(self) -> _Result:
        # No driver mates exist for the freed DOF in the saved models.
        _sleep(T_LIST_MATES)
        return _Result([])


def _fake_gear_links(owner: str):
    """A _gear_mate_links stand-in: the slow MateGroup walk for the gear owner,
    returning the canonical crank + active-channel meshes so the gate passes."""

    def inner(_adapter: Any) -> list[dict]:
        # name comes from the currently-open model; only the owner carries mates.
        model_name = _adapter.currentModel._name
        if model_name != owner:
            _sleep(T_GEAR_LINKS_OTHER)
            return []
        _sleep(T_GEAR_LINKS_OWNER)
        crank_num, crank_den = (int(v) for v in verify._config.machine("gear_train", "crank_drive_ratio"))
        cyl = int(verify._config.machine("gear_train", "fundamental_cone_teeth"))
        links = [{
            "numerator": crank_num, "denominator": crank_den,
            "sides": [{"component": "dt-crank-pinion-1"}, {"component": "dt-crank-drive-gear-1"}],
        }]
        for ch in verify._config.active_channels():
            links.append({
                "numerator": ch["cone_teeth"], "denominator": cyl,
                "sides": [{"component": "cone-gear-x"}, {"component": "cylinder-gear-x"}],
            })
        return links

    return inner


def _patch_com_seam(monkeypatch, gear_owner: str = "dt-drive-train") -> None:
    """Replace the win32-only COM seam (GetWhatsWrong / MateGroup walk) with the
    sleepy fakes; everything else stays production code."""
    # whats_wrong() calls the early-bound GetWhatsWrong and consumes its return
    # tuple (win32 only; it does NOT pass byref VARIANTs -- that idiom belongs to
    # late-bound probes, see test_out_param_binding). Patch the reader, NOT
    # assert_model_healthy -- the health.whats_wrong span we are testing lives in
    # the (real) assert_model_healthy loop.
    def clean_whats_wrong(_adapter: Any, _model: Any) -> list:
        _sleep(T_WHATS_WRONG)
        return []

    monkeypatch.setattr(_assembly, "whats_wrong", clean_whats_wrong)
    monkeypatch.setattr(verify, "_gear_mate_links", _fake_gear_links(gear_owner))


# --------------------------------------------------------------------------- #
# Capture helpers                                                              #
# --------------------------------------------------------------------------- #
def _attach_capture():
    from opentelemetry.sdk.trace import TracerProvider as SdkTracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
        InMemorySpanExporter,
    )
    from typing import cast

    _telemetry.configure()
    spans = InMemorySpanExporter()
    cast(SdkTracerProvider, _telemetry.trace.get_tracer_provider()).add_span_processor(
        SimpleSpanProcessor(spans)
    )
    return spans


def _run_soundness(names: list[str], monkeypatch, tmp_path: Path):
    """Drive the REAL verify._verify_static_one over `names` against the mock,
    inside a root task span (mimicking the doit `verify:soundness` task span).
    Returns the captured finished spans."""
    _patch_com_seam(monkeypatch)
    # _verify_static_one checks `sldasm.exists()`; point OUT_SLDASM at a tmp dir
    # of empty .SLDASM files so the real existence check passes.
    monkeypatch.setattr(verify, "OUT_SLDASM", tmp_path)
    monkeypatch.setattr(_telemetry, "_telemetry_dir", lambda: tmp_path)
    for name in names:
        (tmp_path / f"{name}.SLDASM").write_bytes(b"")

    spans = _attach_capture()
    adapter = MockAdapter()
    report = verify.Report()

    async def drive() -> None:
        with _telemetry.run_pipeline_span("verify:soundness"):
            for name in names:
                await verify._verify_static_one(adapter, name, report)

    asyncio.run(drive())
    # Expose the adapter so a test can inspect the last-opened model's rebuild count.
    global _LAST_RUN_ADAPTER
    _LAST_RUN_ADAPTER = adapter
    return spans.get_finished_spans(), report


_LAST_RUN_ADAPTER: "MockAdapter | None" = None


def _by_name(spans, name: str) -> list:
    return [s for s in spans if s.name == name]


def _dur(span) -> float:
    return (span.end_time - span.start_time) / 1e9 if span.end_time and span.start_time else 0.0


# --------------------------------------------------------------------------- #
# Tests                                                                        #
# --------------------------------------------------------------------------- #
def test_default_soundness_fixture_passes_real_gates_and_native_contacts(
    monkeypatch, tmp_path
):
    """All three demo assemblies pass real consumers, including every channel seat."""
    monkeypatch.setattr(sys.modules[__name__], "SCALE", 0.0)
    spans, report = _run_soundness(list(_DEFAULT_ASSEMBLIES), monkeypatch, tmp_path)
    assert report.failed == [], report.failed
    assert {label for label in report.passed if label.startswith("ch-channel:")} == {
        f"ch-channel:{suffix}"
        for suffix in (
            "saved-rebuild-clean",
            "dof-free-necessity",
            "no-over-constrained",
            "model-healthy",
            "interference-free",
            "spring-native-contacts",
            "channel-independence",
        )
    }
    assert not any(span.status.status_code.name == "ERROR" for span in spans)
    count = verify._config.active_count()
    contacts = _by_name(spans, "spring.native_contact")
    assert len(contacts) == 2 * count
    assert all(
        span.status.status_code.name == "OK"
        and span.attributes["certificate"] == "zero_overlap_bounded_distance"
        and span.attributes["overlap_volume_mm3"] == 0.0
        for span in contacts
    )
    # Inspect consumer-visible identities/transforms as well as certificates:
    # source variants and distances must follow preset amplitudes, not bounds.
    assert _LAST_RUN_ADAPTER is not None
    model = _LAST_RUN_ADAPTER.currentModel
    variants = list(dict.fromkeys(verify._config.amplitudes()))
    records = verify._config.machine("springs", "channel_seats")
    for station, row in enumerate(verify._config.active_channels()):
        amplitude = float(row["amplitude_mm"])
        record = next(record for record in records if record["amplitude_mm"] == amplitude)
        lower, upper = contacts[2 * station:2 * station + 2]
        assert lower.attributes["label"] == f"channel {station:02d} lower native seat"
        assert upper.attributes["label"] == f"channel {station:02d} upper native seat"
        assert lower.attributes["distance_mm"] == pytest.approx(
            record["final_distance_mm"]["lower"]
        )
        assert upper.attributes["distance_mm"] == pytest.approx(
            record["final_distance_mm"]["upper"]
        )
        spring_name = lower.attributes["first_component"]
        assert upper.attributes["first_component"] == spring_name
        spring = model.GetComponentByName(spring_name)
        assert spring is not None
        assert Path(spring.GetPathName()).stem == (
            f"ch-vn-channel-spring-installed-stretch{variants.index(amplitude):02d}"
        )
        assert spring.fixed and not spring.pattern
        for name in (
            spring_name,
            lower.attributes["second_component"],
            upper.attributes["second_component"],
            f"ch-anchor-jam-nut-{station + 1}",
        ):
            component = model.GetComponentByName(name)
            assert component is not None
            assert component.Transform2.ArrayData[11] == pytest.approx(
                rocker_bank_layout.hub_mid_z(station) / 1000.0
            )
    for stem in ("ch-vn-spring-hook", "ch-anchor-jam-nut"):
        installed = [component for component in model._comps if component.source_stem == stem]
        assert len(installed) == count
        assert all(component.fixed and not component.pattern for component in installed)


_CHANNEL_CORRUPTIONS = {
    "frozen-motion": ("dof-free-necessity", "expected >="),
    "missing-source": ("spring-native-contacts", "component identity unavailable"),
    "wrong-moving-count": ("channel-independence", "independent instances"),
    "positive-overlap": ("spring-native-contacts", "components intersect"),
    "excessive-distance": ("spring-native-contacts", "exceeds calibrated maximum"),
}


def _corrupt_channel_data(monkeypatch, corruption: str) -> None:
    """Change adapter data after open; leave every production gate and Report real."""
    original_open = MockAdapter.open_model

    async def open_model(adapter, path):
        result = await original_open(adapter, path)
        model = adapter.currentModel
        if model._name != "ch-channel":
            return result
        if corruption == "frozen-motion":
            for component in model._comps:
                if component.source_stem in verify._MOVING_CHANNEL_STEMS:
                    component.status = _assembly.FULLY_CONSTRAINED
        elif corruption == "missing-source":
            spring_name, _ = next(iter(model.distances_mm))
            spring = model.GetComponentByName(spring_name)
            assert spring is not None
            spring.source_stem = ""
        elif corruption == "wrong-moving-count":
            model._comps.remove(next(
                component for component in model._comps
                if component.source_stem == "ch-connecting-rod"
            ))
        elif corruption == "positive-overlap":
            model.overlaps_mm3[next(iter(model.distances_mm))] = 1e-9
        elif corruption == "excessive-distance":
            model.distances_mm[next(iter(model.distances_mm))] = 1.0
        else:
            raise AssertionError(f"unknown channel-data corruption: {corruption}")
        return result

    monkeypatch.setattr(MockAdapter, "open_model", open_model)


@pytest.mark.parametrize("corruption", _CHANNEL_CORRUPTIONS)
def test_channel_corrupt_data_fails_real_soundness_gates(
    monkeypatch, tmp_path, corruption
):
    monkeypatch.setattr(sys.modules[__name__], "SCALE", 0.0)
    _corrupt_channel_data(monkeypatch, corruption)
    spans, report = _run_soundness(list(_DEFAULT_ASSEMBLIES), monkeypatch, tmp_path)
    suffix, evidence = _CHANNEL_CORRUPTIONS[corruption]
    label = f"ch-channel:{suffix}"
    assert [failed_label for failed_label, _ in report.failed] == [label], report.failed
    assert evidence in report.failed[0][1]
    (gate,) = [
        span for span in _by_name(spans, "gate") if span.attributes["label"] == label
    ]
    assert gate.status.status_code.name == "ERROR"
    assert any(
        event.name == "exception" and evidence in event.attributes["exception.message"]
        for event in gate.events
    )
    assert label not in report.passed


@pytest.mark.parametrize("corruption", (None, *_CHANNEL_CORRUPTIONS))
def test_demo_status_reflects_real_gate_results(monkeypatch, tmp_path, capsys, corruption):
    # Only the behavioral regression drops synthetic sleeps; --demo itself keeps
    # the configured timing scale and runs the same real soundness consumer.
    monkeypatch.setattr(sys.modules[__name__], "SCALE", 0.0)
    monkeypatch.setattr(_telemetry, "_telemetry_dir", lambda: tmp_path)
    if corruption is not None:
        _corrupt_channel_data(monkeypatch, corruption)
    capture = _attach_capture()
    status = _demo()
    spans = capture.get_finished_spans()
    assert {span.attributes["name"] for span in _by_name(spans, "verify.open")} == set(
        _DEFAULT_ASSEMBLIES
    )
    if corruption is None:
        assert status == 0
        assert not any(span.status.status_code.name == "ERROR" for span in spans)
        assert len(_by_name(spans, "spring.native_contact")) == 2 * verify._config.active_count()
    else:
        assert status == 1
        suffix, evidence = _CHANNEL_CORRUPTIONS[corruption]
        (gate,) = [
            span for span in _by_name(spans, "gate")
            if span.attributes["label"] == f"ch-channel:{suffix}"
        ]
        assert gate.status.status_code.name == "ERROR"
        assert evidence in gate.status.description
    assert f"Gates failed: {int(corruption is not None)}" in capsys.readouterr().err


def test_no_per_component_dof_check_spans(monkeypatch, tmp_path):
    """The dof gate no longer emits one span per component (the de-noise)."""
    spans, report = _run_soundness(["fr-frame", "dt-drive-train"], monkeypatch, tmp_path)
    assert report.failed == [], report.failed
    assert _by_name(spans, "dof.check") == []  # the flood is gone
    # frame is fully defined (strict 0-DOF), so its gate is the aggregate gate.dof.
    dof_gates = _by_name(spans, "gate.dof")
    assert len(dof_gates) == 1
    frame_gate = dof_gates[0]
    assert frame_gate.attributes["not_fully_defined"] == 0
    assert frame_gate.status.status_code.name == "OK"
    # drive-train keeps its operational DOF free (no driver mates), so its DOF
    # gate is the NECESSITY gate -- one span carrying the free-DOF aggregate,
    # still no per-component flood.
    nec = _by_name(spans, "gate.dof_free_necessity")
    assert len(nec) == 1
    # crank spin + cone-platform swing + pinion swing + lift-rod/cam spin (PR8)
    assert nec[0].attributes["expected_free_dof"] == 4
    assert nec[0].attributes["free_under_constrained"] >= 4
    assert nec[0].status.status_code.name == "OK"


def test_whats_wrong_collapses_to_one_span_per_health_gate(monkeypatch, tmp_path):
    """The per-target What's Wrong flood collapses to ONE span carrying the count
    -- the literal "multiple whats_wrong calls in sequence" the task flags."""
    spans, _ = _run_soundness(["fr-frame", "dt-drive-train"], monkeypatch, tmp_path)
    ww = _by_name(spans, "health.whats_wrong")
    # one per health gate (frame + drive-train), NOT one per target (each target
    # = the top doc + one per top-level component, which is what used to flood).
    assert len(ww) == 2, [s.attributes for s in ww]
    dt = max(ww, key=lambda s: s.attributes.get("targets", 0))
    assert dt.attributes["targets"] == COMPONENT_COUNTS["dt-drive-train"] + 1  # comps + top doc
    assert dt.attributes["errors"] == 0


def test_soundness_rebuild_spans_name_only_real_rebuilds(monkeypatch, tmp_path):
    """Soundness passes a shared rebuild result into every gate, so its trace must
    not claim that DOF, over-constrained, or health rebuilt the model again."""
    spans, report = _run_soundness(["fr-frame"], monkeypatch, tmp_path)
    assert report.failed == [], report.failed
    assert len(_by_name(spans, "verify.rebuild")) == 1
    assert _by_name(spans, "dof.rebuild") == []
    assert _by_name(spans, "dof.resolve") == []  # retired ambiguous name
    assert _by_name(spans, "over.rebuild") == []
    assert _by_name(spans, "health.rebuild") == []

    collect = _by_name(spans, "health.collect_targets")
    assert len(collect) == 1
    assert collect[0].attributes["targets"] == COMPONENT_COUNTS["fr-frame"] + 1


def _health_target_case(monkeypatch, child_errors=()):
    """Small, non-sleeping seam; keep the production health collector and spans."""
    root = types.SimpleNamespace()
    child = object()
    calls = types.SimpleNamespace(enumerations=[], children=[], targets=[], rebuilds=[])

    def component(name, document):
        def get_model():
            calls.children.append(name)
            return document

        return types.SimpleNamespace(Name2=name, GetModelDoc2=get_model)

    components = [
        component("shared-2", child),
        component("unloaded-1", None),
        component("shared-1", child),
        component("self-1", root),
        # Deliberately supply a slash-qualified row even to the top-only call:
        # preserve the collector's existing name filter independently of the API.
        component("sub-1/nested-1", object()),
    ]

    def get_components(top_level_only):
        calls.enumerations.append(top_level_only)
        return components

    def rebuild(top_only):
        calls.rebuilds.append(top_only)
        return True

    def whats_wrong(_adapter, document):
        calls.targets.append(document)
        return list(child_errors) if document is child else []

    root.GetComponents = get_components
    root.ForceRebuild3 = rebuild
    adapter = MockAdapter()
    adapter._current = root
    monkeypatch.setattr(_assembly, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(_assembly, "whats_wrong", whats_wrong)
    return adapter, root, child, calls


@pytest.mark.parametrize("model_source", ["active", "explicit"])
def test_health_top_level_collection_preserves_instance_targets(monkeypatch, model_source):
    adapter, root, child, calls = _health_target_case(monkeypatch)
    kwargs = {}
    if model_source == "explicit":
        adapter._current = object()  # self-exclusion belongs to model, not ActiveDoc.
        kwargs["model"] = root
    capture = _attach_capture()

    _assembly.assert_model_healthy(adapter, label="assembly", rebuilt=True, **kwargs)

    assert calls.enumerations == [True]
    assert calls.children == ["shared-2", "unloaded-1", "shared-1", "self-1"]
    assert calls.targets == [root, child, child]  # same document, two instance checks
    assert calls.rebuilds == []
    spans = capture.get_finished_spans()
    assert _by_name(spans, "health.collect_targets")[0].attributes["targets"] == 3
    assert _by_name(spans, "health.whats_wrong")[0].attributes["targets"] == 3
    assert _by_name(spans, "health.rebuild") == []


def test_health_shallow_does_not_enumerate_children(monkeypatch):
    adapter, root, _, calls = _health_target_case(monkeypatch)

    _assembly.assert_model_healthy(adapter, label="assembly", deep=False, rebuilt=True)

    assert calls.enumerations == []
    assert calls.children == []
    assert calls.targets == [root]
    assert calls.rebuilds == []


def test_health_child_error_keeps_each_instance_name(monkeypatch):
    adapter, root, child, calls = _health_target_case(
        monkeypatch, child_errors=[("BrokenMate", 48, False)]
    )
    capture = _attach_capture()

    with pytest.raises(RuntimeError, match="model unhealthy") as failure:
        _assembly.assert_model_healthy(adapter, label="assembly", rebuilt=True)

    assert calls.enumerations == [True]
    assert calls.targets == [root, child, child]
    assert "shared-1:BrokenMate" in str(failure.value)
    assert "shared-2:BrokenMate" in str(failure.value)
    gate = _by_name(capture.get_finished_spans(), "gate.health")[0]
    assert gate.status.status_code.name == "ERROR"
    assert gate.attributes["errors"] == 2


@pytest.mark.parametrize("rebuild_source", ["shared_clean", "shared_failed", "gate_owned"])
def test_health_preserves_shared_rebuild_result(monkeypatch, rebuild_source):
    adapter, _, _, calls = _health_target_case(monkeypatch)
    kwargs = {}
    if rebuild_source != "gate_owned":
        kwargs["rebuilt"] = rebuild_source == "shared_clean"
    capture = _attach_capture()

    if rebuild_source == "shared_failed":
        with pytest.raises(RuntimeError, match="ForceRebuild3 returned False"):
            _assembly.assert_model_healthy(adapter, label="assembly", **kwargs)
    if rebuild_source != "shared_failed":
        _assembly.assert_model_healthy(adapter, label="assembly", **kwargs)

    expected_rebuilds = [False] if rebuild_source == "gate_owned" else []
    assert calls.rebuilds == expected_rebuilds
    assert calls.enumerations == [True]
    assert len(_by_name(capture.get_finished_spans(), "health.rebuild")) == len(expected_rebuilds)


# NOTE: test_slow_gates_have_child_spans_no_unspanned_gap was removed. It asserted
# each slow gate's child spans cover >=85% of the gate's wall-clock -- a wall-clock
# ratio that is inherently jitter-sensitive (a one-off scheduler/GC pause in the
# smallest gate's thin unspanned sliver could tip it under threshold). The slow-gate
# span structure (named child spans, no large unspanned gap) is evaluated from real
# runtime traces (cad/out/reports/telemetry/) instead of a CI timing assertion.
def test_open_and_activate_are_spanned(monkeypatch, tmp_path):
    """The per-assembly open+activate (8-27 s real) is no longer an unspanned gap
    between gates."""
    spans, _ = _run_soundness(["fr-frame", "dt-drive-train"], monkeypatch, tmp_path)
    opens = _by_name(spans, "verify.open")
    assert {s.attributes.get("name") for s in opens} == {"fr-frame", "dt-drive-train"}
    assert all(_dur(s) > 0 for s in opens)


def test_trace_is_one_tree_with_far_fewer_spans(monkeypatch, tmp_path):
    """Everything hangs off the one root trace, and a 51-component assembly now
    emits a modest span count instead of the ~110 per-item leaves it used to."""
    spans, _ = _run_soundness(["dt-drive-train"], monkeypatch, tmp_path)
    assert len({s.context.trace_id for s in spans}) == 1  # no gaps
    # Pre-fix: ~51 dof.check + ~52 health.whats_wrong + the gate/op spans = 110+.
    # Post-fix the per-item leaves are gone; the whole drive-train pass is small
    # (~27 spans). The bound guards against the 110+ regression, not exact
    # count, so keep generous headroom above the real total.
    assert len(spans) < 45, f"{len(spans)} spans -- per-item flood not removed?"
    assert len(_by_name(spans, "dof.check")) == 0
    assert len(_by_name(spans, "health.whats_wrong")) == 1


def test_free_dof_gate_is_single_necessity_span_not_park_phases(monkeypatch, tmp_path):
    """The drive-train soundness DOF gate is the lightweight NECESSITY gate -- a
    single ``gate.dof_free_necessity`` span with no per-item flood. The retired
    park machinery's spans (``gate.dof_expected_free`` with ``park.*`` phase
    children, the release ``gate.park_closure``) must not appear anywhere --
    this pins the park-driver removal."""
    spans, report = _run_soundness(["dt-drive-train"], monkeypatch, tmp_path)
    assert report.failed == [], report.failed
    (gate,) = _by_name(spans, "gate.dof_free_necessity")
    assert gate.status.status_code.name == "OK"
    # crank spin + cone-platform swing + pinion swing + lift-rod/cam spin (PR8)
    assert gate.attributes["expected_free_dof"] == 4
    assert gate.attributes["free_under_constrained"] >= 4
    # the park machinery is gone -- none of its spans may reappear.
    assert _by_name(spans, "gate.dof_expected_free") == []
    assert _by_name(spans, "gate.park_closure") == []
    for phase in ("park.discover", "park.necessity", "park.engage", "park.restore"):
        assert _by_name(spans, phase) == [], f"{phase} is retired park machinery"
    # drive-train being free, there is no nested strict 0-DOF gate.
    assert _by_name(spans, "gate.dof") == []


def test_soundness_shares_one_rebuild_across_dof_over_health(monkeypatch, tmp_path):
    """The dof / over-constrained / model-healthy gates share ONE ForceRebuild3 (the
    perf fix): a fully-defined assembly's model is re-solved exactly once -- the
    single ``verify.rebuild`` -- not three times (was ~50 s x3 on the top assembly).
    """
    spans, report = _run_soundness(["fr-frame"], monkeypatch, tmp_path)  # frame => fully-defined
    assert report.failed == [], report.failed
    # The single shared re-solve span is emitted once for the one assembly.
    assert len(_by_name(spans, "verify.rebuild")) == 1
    # ... and the model itself saw exactly ONE ForceRebuild3 (dof + over + health
    # used to each re-solve it => 3). This is the assertion that pins the fix.
    assert _LAST_RUN_ADAPTER is not None
    assert _LAST_RUN_ADAPTER.currentModel.rebuild_calls == 1, (
        f"{_LAST_RUN_ADAPTER.currentModel.rebuild_calls} rebuilds -- "
        "the gates are still re-solving redundantly"
    )
    # gear-ratios is DEMOTED to the release preflight, so it must NOT run in soundness.
    assert _by_name(spans, "gate.gear_ratios") == []
    assert _by_name(spans, "gear.read_links") == []


def _phase_case(
    monkeypatch, tmp_path, *, manifest=True, parameter=True, manifest_copies=1
):
    """Use the existing inert result/model/attempt ports without sleeps or COM."""
    monkeypatch.setattr(verify, "OUT_SLDASM", tmp_path)
    monkeypatch.setattr(verify, "_assert_fresh", lambda *_: True)
    for name in (verify.MOTION_OWNER, "mg-magnifier", "pd-paper-drive"):
        (tmp_path / f"{name}.SLDASM").touch()
    param = types.SimpleNamespace(Value=1.0, SystemValue=0.0)
    model = MockModel("phase-model", 0)
    model.Parameter = lambda _: param if parameter else None
    model.EditRebuild3 = lambda: True
    model.GetTitle = lambda: "phase-model"
    adapter = types.SimpleNamespace(
        currentModel=model,
        swApp=types.SimpleNamespace(
            CloseAllDocuments=lambda _: None, CloseDoc=lambda _: None
        ),
    )
    adapter._attempt = types.MethodType(MockAdapter._attempt, adapter)

    async def open_model(_):
        return _Result(True)

    async def author(*_):
        return ["phase-drive"]

    async def install(*_):
        return {"links": 20, "scale_mm_per_unit": 1.0, "rest_deg": 0.0}

    async def set_crank(_, theta):
        param.SystemValue = theta

    adapter.open_model = open_model
    monkeypatch.setattr(
        verify, "load_dof_manifest",
        lambda _: [
            {"key": key, "params": {"distance": 1.0}}
            for key in ("pen_travel", "lever_rock", "slide")
        ] * manifest_copies if manifest else [],
    )
    monkeypatch.setattr(verify, "author_dof_drives", author)
    monkeypatch.setattr(verify.pen_driver, "install", install)
    monkeypatch.setattr(verify.pen_driver, "set_crank_deg", set_crank)
    monkeypatch.setattr(verify.pen_driver, "rest_crank_deg", lambda: 0.0)
    monkeypatch.setattr(verify.pen_driver, "stroke_half_mm", lambda: 1.0)
    monkeypatch.setattr(verify.pen_driver, "expected_tip_disp_mm", lambda _: 0.0)
    monkeypatch.setattr(verify, "_pen_marker_name", lambda _: "marker")
    monkeypatch.setattr(verify, "_tip_y_mm", lambda *_: 0.0)
    monkeypatch.setattr(verify, "check_no_interference", lambda *_, **__: None)
    monkeypatch.setattr(verify, "assert_components_fully_defined", lambda _: None)
    monkeypatch.setattr(verify, "discard_open_documents", lambda _: None)
    monkeypatch.setattr(
        verify, "component_transform",
        lambda *_: [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0],
    )
    return adapter


def _run_phase(capture, operation):
    async def drive():
        with _telemetry.run_pipeline_span("verify:phase-contract"):
            await operation()

    asyncio.run(drive())
    return capture.get_finished_spans()


def _assert_phase_tree(spans, phases):
    (root,) = _by_name(spans, "pipeline.verify:phase-contract")
    assert len({s.context.trace_id for s in spans}) == 1
    assert len(spans) < 45
    for name in phases:
        (phase,) = _by_name(spans, name)
        assert phase.parent.span_id == root.context.span_id
        assert phase.status.status_code.name == "OK"


@pytest.mark.parametrize("kind", ["motion", "chain"])
def test_whole_kinematic_sweeps_have_bounded_phase_spans(monkeypatch, tmp_path, kind):
    adapter = _phase_case(monkeypatch, tmp_path)
    capture = _attach_capture()
    report = verify.Report()
    operation = getattr(verify, f"_verify_{'live_chain' if kind == 'chain' else 'motion'}_one")
    spans = _run_phase(capture, lambda: operation(adapter, report))
    phases = ["prepare", "sweep", "restore"]
    if kind == "motion":
        phases += ["rest", "extremes"]
    _assert_phase_tree(
        spans, [f"verify.{kind}.{phase}" for phase in phases] + ["verify.cleanup"]
    )


@pytest.mark.parametrize("kind", ["motion", "chain"])
@pytest.mark.parametrize("missing", ["manifest", "ambiguous", "parameter"])
def test_kinematic_early_return_omits_unexecuted_phases(
    monkeypatch, tmp_path, kind, missing
):
    adapter = _phase_case(
        monkeypatch, tmp_path,
        manifest=missing != "manifest", parameter=missing != "parameter",
        manifest_copies=2 if missing == "ambiguous" else 1,
    )
    capture = _attach_capture()
    report = verify.Report()
    operation = getattr(verify, f"_verify_{'live_chain' if kind == 'chain' else 'motion'}_one")
    spans = _run_phase(capture, lambda: operation(adapter, report))
    assert report.failed
    for phase in ("rest", "sweep", "extremes", "restore"):
        assert not _by_name(spans, f"verify.{kind}.{phase}")
    prepared = kind == "motion" or missing == "parameter"
    assert len(_by_name(spans, f"verify.{kind}.prepare")) == int(prepared)
    assert len(_by_name(spans, "verify.cleanup")) == int(kind == "motion")
    (root,) = _by_name(spans, "pipeline.verify:phase-contract")
    assert len({s.context.trace_id for s in spans}) == 1
    if prepared:
        (prepare,) = _by_name(spans, f"verify.{kind}.prepare")
        assert prepare.status.status_code.name == "ERROR"
        assert prepare.status.description == report.failed[0][1]
        assert prepare.parent.span_id == root.context.span_id
    if kind == "motion":
        _assert_phase_tree(spans, ["verify.cleanup"])


@pytest.mark.parametrize("kind", ["motion", "chain"])
@pytest.mark.parametrize("failure_phase", ["prepare", "sweep", "cleanup"])
def test_kinematic_phase_errors_keep_propagation_and_cleanup(
    monkeypatch, tmp_path, kind, failure_phase
):
    adapter = _phase_case(monkeypatch, tmp_path)
    failure = RuntimeError("phase failure")

    def fail(*_, **__):
        raise failure

    async def afail(*_, **__):
        raise failure

    if failure_phase == "prepare":
        monkeypatch.setattr(verify, "author_dof_drives", afail)
    elif failure_phase == "sweep":
        if kind == "motion":
            original = verify.pen_driver.set_crank_deg

            async def drive_or_fail(adapter, theta):
                if theta != verify.pen_driver.rest_crank_deg():
                    raise failure
                await original(adapter, theta)

            monkeypatch.setattr(verify.pen_driver, "set_crank_deg", drive_or_fail)
        else:
            original = verify.component_transform

            def read_or_fail(*args):
                if adapter.currentModel.Parameter("").SystemValue != 0.0:
                    raise failure
                return original(*args)

            monkeypatch.setattr(verify, "component_transform", read_or_fail)
    elif kind == "motion":
        monkeypatch.setattr(verify, "discard_open_documents", fail)
    else:
        # _read_member tolerates a callable accessor's failure, but a property
        # read fails before its callable fallback and must still propagate.
        monkeypatch.setattr(
            type(adapter.currentModel), "GetTitle", property(fail), raising=False
        )
    capture = _attach_capture()
    report = verify.Report()
    operation = getattr(verify, f"_verify_{'live_chain' if kind == 'chain' else 'motion'}_one")
    with pytest.raises(RuntimeError) as caught:
        _run_phase(capture, lambda: operation(adapter, report))
    assert caught.value is failure
    spans = capture.get_finished_spans()
    name = "verify.cleanup" if failure_phase == "cleanup" else f"verify.{kind}.{failure_phase}"
    (phase,) = _by_name(spans, name)
    assert phase.status.status_code.name == "ERROR"
    assert len(_by_name(spans, "verify.cleanup")) == int(
        kind == "motion" or failure_phase == "cleanup"
    )
    if failure_phase != "cleanup":
        assert not _by_name(spans, f"verify.{kind}.restore")


@pytest.mark.parametrize(
    "case",
    [
        "normal", "missing", "manifest", "ambiguous", "parameter", "raised",
        "offstation", "interference",
    ],
)
def test_pass_walk_phase_parentage_and_failed_gate_conversion(monkeypatch, tmp_path, case):
    import json

    adapter = _phase_case(
        monkeypatch, tmp_path, parameter=case != "parameter",
        manifest=case != "manifest", manifest_copies=2 if case == "ambiguous" else 1,
    )
    name = verify.SWEEP_OWNER
    if case != "missing":
        verify._sweep_sidecar_path(name).write_text(
            json.dumps({
                "drive_key": "slide", "pose_tolerance_mm": 0.01,
                "passes": [{
                    "pass": "inner", "remate": None,
                    "poses": [
                        {"drive_mm": i, "theta_rad": 0.0, "carriages": {"carriage": [0, 0, 0]},
                         "check": i % 2 == 0}
                        for i in range(10)
                    ],
                }],
            }), encoding="utf-8",
        )
    if case == "raised":
        def fail(*_):
            raise RuntimeError("readback failed")

        monkeypatch.setattr(verify, "component_transform", fail)
    elif case == "offstation":
        original = verify.component_transform

        def offstation(*args):
            transform = original(*args)
            transform[9] = 1.0
            return transform

        monkeypatch.setattr(verify, "component_transform", offstation)
    elif case == "interference":
        def interference(*_, **__):
            raise RuntimeError("interference found")

        monkeypatch.setattr(verify, "check_no_interference", interference)
    capture = _attach_capture()
    report = verify.Report()
    spans = _run_phase(capture, lambda: verify._verify_pass_sweep(adapter, name, report))
    (walk,) = _by_name(spans, "verify.pass_sweep.walk")
    (prepare,) = _by_name(spans, "verify.pass_sweep.prepare")
    assert prepare.parent.span_id == walk.context.span_id
    _assert_phase_tree(spans, ["verify.cleanup"])
    (root,) = _by_name(spans, "pipeline.verify:phase-contract")
    assert walk.parent.span_id == root.context.span_id
    assert walk.status.status_code.name == ("OK" if case == "normal" else "ERROR")
    preparation_failed = case in ("missing", "manifest", "ambiguous", "parameter")
    assert prepare.status.status_code.name == ("ERROR" if preparation_failed else "OK")
    if preparation_failed:
        assert prepare.status.description == walk.status.description
    (gate,) = _by_name(spans, "gate")
    assert gate.status.status_code.name == ("OK" if case == "normal" else "ERROR")
    assert gate.parent.span_id == root.context.span_id
    assert bool(report.failed) == (case != "normal")
    if case == "raised":
        assert "sweep walk raised: readback failed" in report.failed[0][1]


@pytest.mark.parametrize("failed", [False, True])
def test_paper_feed_cleanup_remains_visible_after_gate_conversion(monkeypatch, tmp_path, failed):
    import build_kinematic_probe

    adapter = _phase_case(monkeypatch, tmp_path)

    async def feed(_):
        if failed:
            raise RuntimeError("feed failed")

    monkeypatch.setattr(build_kinematic_probe, "_drive_and_measure", feed)
    capture = _attach_capture()
    report = verify.Report()
    spans = _run_phase(capture, lambda: verify._verify_paper_feed_one(adapter, report))
    _assert_phase_tree(spans, ["verify.cleanup"])
    (gate,) = _by_name(spans, "gate")
    assert gate.status.status_code.name == ("ERROR" if failed else "OK")
    assert bool(report.failed) == failed


@pytest.mark.parametrize(
    "case",
    [
        "normal", "missing", "manifest", "parameter", "offstation",
        "write_error", "write_cancel", "read_error", "read_cancel",
        "force_swallowed", "force_cancel", "edit_swallowed", "edit_cancel",
        "remate_cancel", "prepare_cancel",
    ],
)
def test_jig_aggregate_envelopes_publish_actual_partial_work(
    monkeypatch, tmp_path, case
):
    """Four distinct fake native costs prove disjoint, reached-operation totals."""
    import json

    adapter = _phase_case(
        monkeypatch, tmp_path, manifest=case != "manifest",
        parameter=case != "parameter",
    )
    now = [0]
    events = []
    clocks = []
    publications = []

    def clock():
        clocks.append(now[0])
        return now[0]

    monkeypatch.setattr(verify, "time", types.SimpleNamespace(perf_counter_ns=clock))

    def port(name, cost, error=None):
        events.append(name)
        now[0] += cost
        if error is not None:
            raise error

    class Parameter:
        @property
        def SystemValue(self):
            return 0.0

        @SystemValue.setter
        def SystemValue(self, value):
            error = None
            if case == "write_error":
                error = RuntimeError("write failed")
            elif case == "write_cancel":
                error = asyncio.CancelledError("write cancelled")
            port("write", 3, error)

    model = adapter.currentModel
    if case != "parameter":
        model.Parameter = lambda _: Parameter()

    def force(_):
        error = None
        if case == "force_swallowed":
            error = RuntimeError("force failed")
        elif case == "force_cancel":
            error = asyncio.CancelledError("force cancelled")
        port("force", 5, error)

    model.ForceRebuild3 = force

    def edit():
        error = None
        if case == "edit_swallowed":
            error = RuntimeError("edit failed")
        elif case == "edit_cancel":
            error = asyncio.CancelledError("edit cancelled")
        port("edit", 7, error)

    model.EditRebuild3 = edit

    def transform(*_):
        error = None
        if case == "read_error":
            error = RuntimeError("read failed")
        elif case == "read_cancel":
            error = asyncio.CancelledError("read cancelled")
        port("read", 11, error)
        return [1., 0., 0., 0., 1., 0., 0., 0., 1.,
                1. if case == "offstation" else 0., 0., 0.]

    async def author(*_):
        port(
            "prepare", 29,
            asyncio.CancelledError("prepare cancelled") if case == "prepare_cancel" else None,
        )
        return ["phase-drive"]

    async def suppress(_):
        port(
            "suppress", 13,
            asyncio.CancelledError("remate cancelled") if case == "remate_cancel" else None,
        )
        return _Result(True)

    async def mate(*_, **__):
        port("mate", 17)

    original_annotate = _telemetry.annotate

    def annotate(**attributes):
        publications.append((
            _telemetry.trace.get_current_span().get_span_context().span_id,
            dict(attributes),
        ))
        original_annotate(**attributes)

    monkeypatch.setattr(verify, "component_transform", transform)
    monkeypatch.setattr(verify, "author_dof_drives", author)
    monkeypatch.setattr(verify, "named_ref", lambda name, kind: (name, kind))
    monkeypatch.setattr(verify, "coincident_mate", mate)
    monkeypatch.setattr(verify, "check_no_interference", lambda *_, **__: port("check", 19))
    monkeypatch.setattr(verify, "log", lambda *_: port("log", 23))
    monkeypatch.setattr(_telemetry, "annotate", annotate)
    adapter.suppress_mate = suppress

    def pose(i):
        return {
            "drive_mm": i, "theta_rad": 0., "carriages": {"carriage": [0, 0, 0]},
            "check": i == 0,
        }

    if case != "missing":
        verify._sweep_sidecar_path(verify.SWEEP_OWNER).write_text(json.dumps({
            "drive_key": "slide", "pose_tolerance_mm": .01,
            "passes": [
                {"pass": "inner", "remate": None, "poses": [pose(0), pose(1)]},
                {
                    "pass": "outer",
                    "remate": {
                        "suppress": ["old"],
                        "coaxial": [{"hole": "hole", "pin": "pin", "label": "pair"}],
                    },
                    "poses": [pose(2)],
                },
            ],
        }), encoding="utf-8")
    capture = _attach_capture()
    report = verify.Report()

    def operation():
        return verify._verify_pass_sweep(adapter, verify.SWEEP_OWNER, report)

    if case.endswith("cancel"):
        with pytest.raises(asyncio.CancelledError):
            _run_phase(capture, operation)
    else:
        _run_phase(capture, operation)
    spans = capture.get_finished_spans()
    (walk,) = _by_name(spans, "verify.pass_sweep.walk")
    (prepare,) = _by_name(spans, "verify.pass_sweep.prepare")
    assert len(publications) == 1
    span_id, attributes = publications[0]
    assert span_id == walk.context.span_id
    assert prepare.parent.span_id == span_id
    keys = ("drive_write", "force_rebuild", "edit_rebuild", "transform_readback")
    costs = (3, 5, 7, 11)
    if case in ("missing", "manifest", "parameter", "prepare_cancel"):
        counts = (0, 0, 0, 0)
    elif case in ("write_error", "write_cancel"):
        counts = (1, 0, 0, 0)
    elif case == "force_cancel":
        counts = (1, 1, 0, 0)
    elif case == "edit_cancel":
        counts = (1, 1, 1, 0)
    elif case in ("offstation", "read_error", "read_cancel"):
        counts = (1, 1, 1, 1)
    elif case == "remate_cancel":
        counts = (3, 3, 3, 2)
    else:
        counts = (4, 5, 5, 3)
    expected = {}
    for key, count, cost in zip(keys, counts, costs):
        expected[f"jig.{key}_attempts"] = count
        expected[f"jig.{key}_elapsed_ns"] = count * cost
    assert attributes == expected
    assert {k: v for k, v in walk.attributes.items() if k.startswith("jig.")} == expected
    assert not any(k.startswith("jig.") for k in prepare.attributes)
    assert all(type(value) is int for value in attributes.values())
    # Each start/end pair encloses exactly one operation, never a rebuild inside
    # a write or any preparation/remate/log/interference work.
    assert len(clocks) == 2 * sum(counts)
    deltas = [end - start for start, end in zip(clocks[::2], clocks[1::2])]
    assert sum(deltas) == sum(count * cost for count, cost in zip(counts, costs))
    for previous_end, next_start in zip(clocks[1::2], clocks[2::2]):
        assert previous_end <= next_start
    if case in ("normal", "force_swallowed", "edit_swallowed"):
        assert events == [
            "log", "prepare",
            "write", "force", "edit", "read", "log", "check",
            "write", "force", "edit", "read", "log",
            "write", "force", "edit", "suppress", "mate", "force", "edit",
            "write", "force", "edit", "read", "log",
        ]
        assert report.failed == []
    elif not case.endswith("cancel"):
        assert report.failed
    assert len(_by_name(spans, "verify.cleanup")) == 1
    assert len(spans) < 45


def test_non_jig_rebuild_has_no_clock_reads_and_keeps_two_native_attempts(monkeypatch):
    events = []

    def unexpected_clock():
        pytest.fail("non-jig rebuild must not read the clock")

    monkeypatch.setattr(
        verify, "time", types.SimpleNamespace(perf_counter_ns=unexpected_clock)
    )
    model = types.SimpleNamespace(
        ForceRebuild3=lambda quiet: events.append(("force", quiet)),
        EditRebuild3=lambda: events.append(("edit",)),
    )
    adapter = types.SimpleNamespace(currentModel=model)
    adapter._attempt = types.MethodType(MockAdapter._attempt, adapter)
    verify._rebuild(adapter)
    assert events == [("force", False), ("edit",)]


# --------------------------------------------------------------------------- #
# Standalone demo: print the REAL console span tree for a realistic pass.       #
# --------------------------------------------------------------------------- #
def _demo() -> int:
    class _Patch:
        """Minimal monkeypatch shim so _run_soundness works outside pytest."""

        def __init__(self) -> None:
            self._undo: list = []

        def setattr(self, obj, attr, value) -> None:
            self._undo.append((obj, attr, getattr(obj, attr)))
            setattr(obj, attr, value)

        def restore(self) -> None:
            for obj, attr, old in reversed(self._undo):
                setattr(obj, attr, old)

    names = list(_DEFAULT_ASSEMBLIES)
    print(
        f"\n=== mock verify:soundness over {names}  "
        f"(HARMONIC_MOCK_SCALE={SCALE}) ===\n"
        "Console below is the REAL _telemetry output; '⟩' lines are spans.\n",
        file=sys.stderr,
    )
    mp = _Patch()
    tmp = Path(_telemetry._telemetry_dir() or ".") / "mock_sldasm"
    tmp.mkdir(parents=True, exist_ok=True)
    # The autouse fixture covers the pytest path; --demo runs outside pytest.
    try:
        with _com_method_flagging_neutralized():
            spans, report = _run_soundness(names, mp, tmp)
    finally:
        mp.restore()

    leaf_counts: dict[str, int] = {}
    for s in spans:
        leaf_counts[s.name] = leaf_counts.get(s.name, 0) + 1
    print("\n=== span-name histogram (post-fix) ===", file=sys.stderr)
    for nm, c in sorted(leaf_counts.items(), key=lambda kv: -kv[1]):
        print(f"  {c:4d}  {nm}", file=sys.stderr)
    n_comp = sum(
        int(span.attributes["targets"]) - 1
        for span in _by_name(spans, "health.collect_targets")
    )
    pre = n_comp + (n_comp + len(names))  # dof.check + per-target whats_wrong
    print(
        f"\nTotal spans: {len(spans)}.  Pre-fix this pass would have emitted "
        f"~{pre} extra per-item leaf spans\n(one dof.check per component + one "
        f"health.whats_wrong per target) that are now collapsed.\n"
        f"Gates failed: {len(report.failed)}",
        file=sys.stderr,
    )
    return 1 if report.failed else 0


if __name__ == "__main__":
    if "--demo" in sys.argv:
        sys.exit(_demo())
    else:
        import pytest

        sys.exit(pytest.main([__file__, "-v"]))
