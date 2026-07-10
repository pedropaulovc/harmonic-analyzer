r"""Telemetry-shape tests for the verify gates, driven by a MOCK SolidWorks.

The real COM seat is replaced with a fake adapter + fake model/component/IDM
objects whose every COM call ``time.sleep``s for a duration *calibrated from the
v0.10.0 release logs* (``harmonic-analyzer-v0.10.0-logs.zip`` ->
``verify-soundness.log``). Everything ABOVE that seam is the production code:
``verify._verify_static_one`` opens the doc, activates the pose, and runs the six
real gates through the real ``_telemetry`` spine, so the spans/logs captured here
are exactly the ones a real ``verify:soundness`` run emits -- only the wall-clock
is scaled (``HARMONIC_MOCK_SCALE``, default 0.01 = 1/100th real time).

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
import os
import sys
import time
import types
from pathlib import Path
from typing import Any

# Export nowhere (no Aspire probe / OTLP retries) BEFORE the spine configures.
os.environ.setdefault("OTEL_EXPORTER_OTLP_ENDPOINT", "")

sys.path.insert(0, str(Path(__file__).resolve().parent))


# --------------------------------------------------------------------------- #
# Stub the one solidworks_mcp symbol verify.py imports at module load. The COM  #
# behaviour itself comes from the mock adapter below; _gear_mate_links is       #
# monkeypatched per-test, so this only needs to satisfy the import.             #
# --------------------------------------------------------------------------- #
def _install_solidworks_stub() -> None:
    for name in (
        "solidworks_mcp",
        "solidworks_mcp.adapters",
        "solidworks_mcp.adapters.solidworks",
        "solidworks_mcp.adapters.solidworks.assembly",
    ):
        if name not in sys.modules:
            sys.modules[name] = types.ModuleType(name)
    asm = sys.modules["solidworks_mcp.adapters.solidworks.assembly"]
    if not hasattr(asm, "_gear_mate_links"):
        asm._gear_mate_links = lambda adapter: []  # type: ignore[attr-defined]
    # _common._flag does `from solidworks_mcp.adapters import sw_type_info` then
    # sw_type_info.flag_methods(...). Provide a no-op so method-flagging is a
    # silent no-op on the mock (real seat flags COM dispatch; the mock needs none).
    sti_name = "solidworks_mcp.adapters.sw_type_info"
    if sti_name not in sys.modules:
        sti = types.ModuleType(sti_name)
        sti.flag_methods = lambda obj, iface: None  # type: ignore[attr-defined]
        sys.modules[sti_name] = sti
        sys.modules["solidworks_mcp.adapters"].sw_type_info = sti  # type: ignore[attr-defined]
    # Some helpers import parameter classes from solidworks_mcp.adapters.base at
    # runtime; a permissive kwargs holder is enough to satisfy those imports.
    base_name = "solidworks_mcp.adapters.base"
    if base_name not in sys.modules:
        base = types.ModuleType(base_name)

        class _Params:  # accepts any kwargs
            def __init__(self, **kw: Any) -> None:
                self.__dict__.update(kw)

        base.SuppressMateParameters = _Params  # type: ignore[attr-defined]
        base.MateEntityRef = _Params  # type: ignore[attr-defined]
        base.RenameFeatureParameters = _Params  # type: ignore[attr-defined]
        sys.modules[base_name] = base
        sys.modules["solidworks_mcp.adapters"].base = base  # type: ignore[attr-defined]


_install_solidworks_stub()

import _assembly  # noqa: E402
import _telemetry  # noqa: E402
import verify  # noqa: E402

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


# Top-level component count per (sub)assembly = the MIDPOINT of the live
# component-count band, so the mock stays self-consistent with whatever config is
# checked out (the v0.10.0 logs were a reduced active_count=3 build; the band
# moves with active_count) and every component-count gate passes. `channel` is the
# dramatic case: ~164 dof.check + ~165 whats_wrong leaf spans, pre-fix.
COMPONENT_COUNTS = {
    name: (lo + hi) // 2 for name, (lo, hi) in verify._COMPONENT_BAND.items()
}


# --------------------------------------------------------------------------- #
# Mock COM objects. Each method sleeps its calibrated duration, then returns    #
# canned-healthy data, so every gate takes its real-shaped path and PASSES.     #
# --------------------------------------------------------------------------- #
class _Result:
    """Mirrors the adapter result protocol check() reads (is_success/.data)."""

    def __init__(self, data: Any = None, *, ok: bool = True, error: str = "") -> None:
        self.is_success = ok
        self.data = data
        self.error = error


class MockComponent:
    def __init__(self, name: str, model: "MockModel") -> None:
        self._name = name
        self._model = model

    # _read_member calls these (callable -> invoked); the per-comp cost lives here.
    def Name2(self) -> str:
        _sleep(T_NAME2)
        return self._name

    def IsFixed(self) -> bool:
        _sleep(T_IS_FIXED)
        return self._name.endswith("-1")  # one grounded part per assembly

    def IsPatternInstance(self) -> bool:
        _sleep(T_IS_PATTERN)
        return False

    def GetConstrainedStatus(self) -> int:
        _sleep(T_CONSTRAINED_STATUS)
        # Faithful to a freed-DOF model: in the free pose the train reads
        # under-constrained; a fully-defined assembly reads fully constrained.
        # Fixed (-1) comps never reach here (IsFixed short-circuits).
        if getattr(self._model, "_free_pose", False):
            return _assembly.UNDER_CONSTRAINED  # 2 -> the free DOF is real
        return _assembly.FULLY_CONSTRAINED  # 3 -> fully defined, gate passes

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
    def __init__(self, name: str, n_components: int) -> None:
        self._name = name
        self._comps = [MockComponent(f"{name}-{i + 1}", self) for i in range(n_components)]
        # The real free-DOF gate names required families (necessity) AND
        # rejects any under-constrained component outside the allowed coupled
        # families (exact-set) -- both taken from the SAME maps verify passes,
        # so the mock can't drift. Rename every non-seed component into the
        # allowed set (cycling), which also covers the required stems (they
        # are a subset); index 0 stays the grounded "-1" seed (IsFixed).
        allowed = (verify._ALLOWED_FREE_STEMS.get(name)
                   or verify._REQUIRED_FREE_STEMS.get(name, ()))
        required = verify._REQUIRED_FREE_STEMS.get(name, ())
        stems = list(required) + [s for s in allowed if s not in required]
        for j in range(1, len(self._comps)):
            if stems:
                self._comps[j]._name = f"{stems[(j - 1) % len(stems)]}-{j + 1}"
        self.InterferenceDetectionManager = MockIDM()
        # Whether this model is in its freed-DOF pose (non-fixed components read
        # under-constrained). Set by open_model for the free drive-train.
        self._free_pose = False
        # Count ForceRebuild3 calls so a test can prove the soundness suite shares
        # ONE re-solve across the dof/over/health gates instead of rebuilding 3x.
        self.rebuild_calls = 0

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
        self._current = MockModel(stem, COMPONENT_COUNTS.get(stem, 8))
        # drive-train ships with its operational DOF genuinely free.
        self._current._free_pose = stem == "drive-train"
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
            "sides": [{"component": "crank-pinion-1"}, {"component": "crank-drive-gear-1"}],
        }]
        for ch in verify._config.active_channels():
            links.append({
                "numerator": ch["cone_teeth"], "denominator": cyl,
                "sides": [{"component": "cone-gear-x"}, {"component": "cylinder-gear-x"}],
            })
        return links

    return inner


def _patch_com_seam(monkeypatch, gear_owner: str = "drive-train") -> None:
    """Replace the win32-only COM seam (pythoncom byref / MateGroup walk) with the
    sleepy fakes; everything else stays production code."""
    # whats_wrong() reads GetWhatsWrong via a pythoncom VT_BYREF VARIANT (win32
    # only). Patch the reader, NOT assert_model_healthy -- the health.whats_wrong
    # span we are testing lives in the (real) assert_model_healthy loop.
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
def test_no_per_component_dof_check_spans(monkeypatch, tmp_path):
    """The dof gate no longer emits one span per component (the de-noise)."""
    spans, report = _run_soundness(["frame", "drive-train"], monkeypatch, tmp_path)
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
    spans, _ = _run_soundness(["frame", "drive-train"], monkeypatch, tmp_path)
    ww = _by_name(spans, "health.whats_wrong")
    # one per health gate (frame + drive-train), NOT one per target (each target
    # = the top doc + one per top-level component, which is what used to flood).
    assert len(ww) == 2, [s.attributes for s in ww]
    dt = max(ww, key=lambda s: s.attributes.get("targets", 0))
    assert dt.attributes["targets"] == COMPONENT_COUNTS["drive-train"] + 1  # comps + top doc
    assert dt.attributes["errors"] == 0


# NOTE: test_slow_gates_have_child_spans_no_unspanned_gap was removed. It asserted
# each slow gate's child spans cover >=85% of the gate's wall-clock -- a wall-clock
# ratio that is inherently jitter-sensitive (a one-off scheduler/GC pause in the
# smallest gate's thin unspanned sliver could tip it under threshold). The slow-gate
# span structure (named child spans, no large unspanned gap) is evaluated from real
# runtime traces (cad/out/reports/telemetry/) instead of a CI timing assertion.
def test_open_and_activate_are_spanned(monkeypatch, tmp_path):
    """The per-assembly open+activate (8-27 s real) is no longer an unspanned gap
    between gates."""
    spans, _ = _run_soundness(["frame", "drive-train"], monkeypatch, tmp_path)
    opens = _by_name(spans, "verify.open")
    assert {s.attributes.get("name") for s in opens} == {"frame", "drive-train"}
    assert all(_dur(s) > 0 for s in opens)


def test_trace_is_one_tree_with_far_fewer_spans(monkeypatch, tmp_path):
    """Everything hangs off the one root trace, and a 51-component assembly now
    emits a modest span count instead of the ~110 per-item leaves it used to."""
    spans, _ = _run_soundness(["drive-train"], monkeypatch, tmp_path)
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
    spans, report = _run_soundness(["drive-train"], monkeypatch, tmp_path)
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
    spans, report = _run_soundness(["frame"], monkeypatch, tmp_path)  # frame => fully-defined
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


# --------------------------------------------------------------------------- #
# Standalone demo: print the REAL console span tree for a realistic pass.       #
# --------------------------------------------------------------------------- #
def _demo() -> None:
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

    names = ["frame", "drive-train", "channel"]
    print(
        f"\n=== mock verify:soundness over {names}  "
        f"(HARMONIC_MOCK_SCALE={SCALE}) ===\n"
        "Console below is the REAL _telemetry output; '⟩' lines are spans.\n",
        file=sys.stderr,
    )
    mp = _Patch()
    tmp = Path(_telemetry._telemetry_dir() or ".") / "mock_sldasm"
    tmp.mkdir(parents=True, exist_ok=True)
    try:
        spans, report = _run_soundness(names, mp, tmp)
    finally:
        mp.restore()

    leaf_counts: dict[str, int] = {}
    for s in spans:
        leaf_counts[s.name] = leaf_counts.get(s.name, 0) + 1
    print("\n=== span-name histogram (post-fix) ===", file=sys.stderr)
    for nm, c in sorted(leaf_counts.items(), key=lambda kv: -kv[1]):
        print(f"  {c:4d}  {nm}", file=sys.stderr)
    n_comp = sum(COMPONENT_COUNTS[n] for n in names)
    pre = n_comp + (n_comp + len(names))  # dof.check + per-target whats_wrong
    print(
        f"\nTotal spans: {len(spans)}.  Pre-fix this pass would have emitted "
        f"~{pre} extra per-item leaf spans\n(one dof.check per component + one "
        f"health.whats_wrong per target) that are now collapsed.\n"
        f"Gates failed: {len(report.failed)}",
        file=sys.stderr,
    )


if __name__ == "__main__":
    if "--demo" in sys.argv:
        _demo()
    else:
        import pytest

        sys.exit(pytest.main([__file__, "-v"]))
