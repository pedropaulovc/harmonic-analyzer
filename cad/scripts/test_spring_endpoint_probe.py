"""Read-only spring investigation exercises the real owned callback and getters."""

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

import _common
from diagnostics import _owned_native_documents as owned
from diagnostics import probe_spring_endpoints as probe
from test_owned_native_documents_drawing import Model, native  # noqa: F401


def fail(error):
    raise error


@pytest.fixture
def spring(native, monkeypatch, tmp_path):  # noqa: F811
    monkeypatch.setattr(probe, "_early_bound", lambda value, _: value)
    monkeypatch.setattr(_common, "_early_bound", lambda value, _: value)
    frozen = {"revision": "candidate", "adapter_revision": probe.ADAPTER_REVISION}
    monkeypatch.setattr(probe, "runtime", lambda: frozen.copy())
    source = tmp_path / "channel-spring-installed.SLDPRT"
    source.write_bytes(b"completed native spring")
    pin = probe.digest(source)
    monkeypatch.setattr(probe, "SOURCE_SHA256", pin)
    token = source.with_name(f".{source.stem}.execution")
    token.write_text(pin, encoding="utf-8")
    reports = tmp_path / "reports"
    reports.mkdir()
    calls = []
    circle = NS(Identity=lambda: 3002, IsCircle=lambda: True,
                CircleParams=(0.00275, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0005))
    inverse = NS(ArrayData=(1., 0., 0., 0., 1., 0., 0., 0., 1., .01, .02, .03, 1., 0., 0., 0.))
    transform = NS(ArrayData=(1., 0., 0., 0., 1., 0., 0., 0., 1., -.01, -.02, -.03, 1., 0., 0., 0.),
                   Inverse=lambda: inverse)

    def point(values):
        if hasattr(values, "varianttype"):
            assert values.varianttype == 0x2000 | 5  # VT_ARRAY | VT_R8.
            values = values.value
        calls.append(("CreatePoint", tuple(values)))
        def multiply(actual):
            assert actual is inverse
            calls.append(("MultiplyTransform",))
            return NS(ArrayData=(values[0] + .01, values[1] + .02, values[2] + .03))
        return NS(MultiplyTransform=multiply)

    native.app.GetMathUtility = lambda: NS(CreatePoint=point)
    segment = NS(GetCurve=lambda: circle)
    sketch = NS(ModelToSketchTransform=transform, GetSketchSegments=lambda: (segment,))
    definition = NS(DefinedBy=2, Height=.0677834, Pitch=.0677834 / 28, Revolution=28.,
                    StartingAngle=0., Clockwise=False, ReverseDirection=False,
                    VariablePitch=False, Taper=False, TaperAngle=0., TaperOutward=False)
    bodies = [NS(Name=name, GetType=lambda: 0, GetBodyBox=lambda: (0., 0., 0., .1, .1, .1))
              for name in ("coil/lower", "upper")]
    trim = NS(CurveType=3002, CurveTag=12, Sense=False, UMinValue=0., UMaxValue=6.28,
              StartPoint=(0.0, .066, .003), EndPoint=(0.0, .066, .003))

    def get_curve():
        calls.append(("GetCurve",))
        return circle

    def get_trim():
        assert calls[-1] == ("GetCurve",)
        calls.append(("GetCurveParams3",))
        return trim

    edge = NS(GetCurve=get_curve, GetCurveParams3=get_trim)
    face = NS(GetBody=lambda: bodies[0], GetSurface=lambda: NS(
        Identity=lambda: 4001, PlaneParams=(1., 0., 0., 0., .066, .003)), GetEdges=lambda: (edge,))
    features = [NS(Name=name, GetTypeName2=lambda kind=kind: kind,
                   GetDefinition=lambda: definition, GetSpecificFeature2=lambda: sketch,
                   GetFaces=lambda: (face,)) for name, kind in probe.FEATURES.items()]
    for index, feature in enumerate(features):
        feature.GetNextFeature = lambda index=index: features[index + 1] if index + 1 < len(features) else None

    def get_bodies(kind, visible):
        calls.append(("GetBodies2", kind, visible))
        return tuple(bodies)

    original_open = native.adapter.open_model
    async def open_model(path):
        result = await original_open(path)
        native.adapter.currentModel.FirstFeature = lambda: features[0]
        native.adapter.currentModel.GetBodies2 = get_bodies
        return result
    native.adapter.open_model = open_model
    return NS(native=native, source=source, token=token, pin=pin, reports=reports,
              features=features, bodies=bodies, face=face, edge=edge, trim=trim,
              circle=circle, sketch=sketch, transform=transform, definition=definition,
              calls=calls, frozen=frozen)


def execute(spring):
    return asyncio.run(owned.owned_callback(spring.native.adapter, lambda adapter:
        probe.probe(adapter, spring.source, "candidate", spring.reports)))


def receipt(spring):
    return json.loads(next(spring.reports.glob("*/endpoints.json")).read_text(encoding="utf-8"))


def test_actual_owned_callback_retains_native_banks_without_requiring_one_solid(spring):
    user = Model(None, title="Unrelated unsaved work", dirty=True)
    spring.native.app.documents.append(user)
    spring.native.app.ActiveDoc = user
    result = execute(spring)
    report = receipt(spring)
    assert result["report"].endswith("endpoints.json")
    assert report["status"] == "captured" and not report["errors"]
    assert spring.calls.count(("GetBodies2", 0, False)) == 1
    assert len(report["groups"]["solid_bodies"]["bodies"]) == 2
    assert report["groups"]["wire_profile"]["circle_center_model_space"] == [.00275 + .01, .02, .03]
    assert report["groups"]["coil_faces"]["faces"][0]["edges"][0]["Sense"] is False
    assert spring.calls.count(("GetCurve",)) == spring.calls.count(("GetCurveParams3",)) == 1
    assert spring.native.app.documents == [user] and user.dirty
    assert len(spring.native.adapter.opens) == len(spring.native.app.closes) == 1
    copied = Path(report["copy"])
    assert spring.native.adapter.opens == [str(copied)]
    assert copied.name != spring.source.name
    for phase in ("before_open", "before_close", "after_close"):
        assert report["hashes"][phase] == {
            str(spring.source): spring.pin, str(copied): spring.pin, "execution_token": spring.pin}
    ownership = json.loads((copied.parent / "ownership.json").read_text(encoding="utf-8"))
    assert ownership["baseline_preservation"]["status"] == "preserved"
    assert ownership["cleanup_error"] is None


def test_partial_curve_identity_survives_later_getter_error(spring, monkeypatch):
    error = RuntimeError("circle predicate getter")
    monkeypatch.setattr(spring.circle, "IsCircle", lambda: fail(error))
    with pytest.raises(RuntimeError) as raised:
        execute(spring)
    assert raised.value is error
    report = receipt(spring)
    assert report["groups"]["base_profile"]["identity"] == 3002
    assert report["groups"]["coil_faces"]["faces"][0]["edges"][0]["identity"] == 3002
    assert report["hashes"]["after_close"][str(spring.source)] == spring.pin
    assert spring.native.app.documents == []


def test_interrupt_supersedes_prior_read_error_and_still_closes_owned_copy(spring, monkeypatch):
    earlier = RuntimeError("unsupported helix definition")
    interrupt = KeyboardInterrupt("operator stop")
    monkeypatch.setattr(spring.features[0], "GetDefinition", lambda: fail(earlier))
    monkeypatch.setattr(spring.sketch, "GetSketchSegments", lambda: fail(interrupt))
    with pytest.raises(KeyboardInterrupt) as raised:
        execute(spring)
    assert raised.value is interrupt
    assert any("unsupported helix" in note for note in interrupt.__notes__)
    report = receipt(spring)
    assert report["status"] == "failed"
    assert "after_close" in report["hashes"] and "runtime_final" in report
    assert spring.native.app.documents == []


def test_checkpoint_error_does_not_replace_native_failure(spring, monkeypatch):
    error = RuntimeError("original native getter")
    monkeypatch.setattr(spring.features[0], "GetDefinition", lambda: fail(error))
    write = Path.write_text
    failed = []
    def checkpoint(path, text, *args, **kwargs):
        if path.name == "endpoints.json" and "original native getter" in text and not failed:
            failed.append(True)
            raise OSError("one failed checkpoint")
        return write(path, text, *args, **kwargs)
    monkeypatch.setattr(Path, "write_text", checkpoint)
    with pytest.raises(RuntimeError) as raised:
        execute(spring)
    assert raised.value is error
    assert failed and any("checkpoint" in note for note in error.__notes__)
    assert receipt(spring)["status"] == "failed"


def test_all_final_hashes_attempted_after_original_hash_changes(spring, monkeypatch):
    original = RuntimeError("getter failed")
    def corrupt():
        spring.source.write_bytes(b"changed original")
        spring.token.write_text("changed token", encoding="utf-8")
        fail(original)
    monkeypatch.setattr(spring.features[0], "GetDefinition", corrupt)
    with pytest.raises(ExceptionGroup):
        execute(spring)
    report = receipt(spring)
    final = report["hashes"]["after_close"]
    assert final[str(spring.source)] != spring.pin
    assert final[report["copy"]] == spring.pin
    assert final["execution_token"] == "changed token"
    assert "getter failed" in report["errors"][0]


@pytest.mark.parametrize("mode,match", [
    ("missing", "missing exact"), ("duplicate", "ambiguous"), ("wrong_type", "wrong-type"),
    ("body_kind", "solid body type"), ("duplicate_body", "duplicate native bodies"),
    ("foreign_face", "one enumerated solid"), ("null_edges", "array shape"),
    ("too_many_segments", "array shape"), ("wrong_curve", "profile circle identity"),
    ("nan_transform", "non-finite"), ("invalid_sense", "unsupported boolean"),
    ("invalid_trim", "not increasing"), ("dirty", "dirty"),
])
def test_native_measurement_refusals_retain_receipt_and_no_save(spring, monkeypatch, mode, match):
    if mode == "missing":
        spring.features[-1].Name = "OtherCoil"
    if mode == "duplicate":
        spring.features[-1].Name = "WireProfile"
    if mode == "wrong_type":
        spring.features[0].GetTypeName2 = lambda: "RefCurve"
    if mode == "body_kind":
        spring.bodies[0].GetType = lambda: 1
    if mode == "duplicate_body":
        spring.bodies[1] = spring.bodies[0]
    if mode == "foreign_face":
        spring.face.GetBody = object
    if mode == "null_edges":
        spring.face.GetEdges = lambda: None
    if mode == "too_many_segments":
        spring.sketch.GetSketchSegments = lambda: (object(), object())
    if mode == "wrong_curve":
        spring.circle.Identity = lambda: 3001
    if mode == "nan_transform":
        spring.transform.ArrayData = (float("nan"),) * 16
    if mode == "invalid_sense":
        spring.trim.Sense = 1
    if mode == "invalid_trim":
        spring.trim.UMaxValue = 0.
    if mode == "dirty":
        def definition():
            spring.native.adapter.currentModel.dirty = True
            return spring.definition
        spring.features[0].GetDefinition = definition
    with pytest.raises((RuntimeError, ExceptionGroup), match=match if mode != "dirty" else None):
        execute(spring)
    report = receipt(spring)
    assert report["status"] == "failed"
    assert report["hashes"]["after_close"][str(spring.source)] == spring.pin
    assert spring.native.app.documents == []


@pytest.mark.parametrize("key,value", [("DefinedBy", True), ("Clockwise", 1), ("Height", float("inf"))])
def test_helix_native_types_and_partial_raw_values_are_not_coerced(spring, key, value):
    setattr(spring.definition, key, value)
    with pytest.raises(RuntimeError, match="unsupported|non-finite"):
        execute(spring)
    row = receipt(spring)["groups"]["helix"]
    assert row[key] == value
    assert row["status"] == "failed" and spring.native.app.documents == []


def test_cleanup_error_keeps_original_interruption_and_attempts_all_final_guards(spring, monkeypatch):
    interrupt = KeyboardInterrupt("stop reading")
    spring.features[0].GetDefinition = lambda: fail(interrupt)
    close = owned.DiagnosticAdapter.close_owned_documents
    async def close_then_error(adapter):
        await close(adapter)
        raise RuntimeError("after-close diagnostic error")
    monkeypatch.setattr(owned.DiagnosticAdapter, "close_owned_documents", close_then_error)
    with pytest.raises(KeyboardInterrupt) as raised:
        execute(spring)
    assert raised.value is interrupt
    assert any("after-close" in note for note in interrupt.__notes__)
    report = receipt(spring)
    assert report["runtime_final"] == spring.frozen
    assert "after_close" in report["hashes"] and "cleanup_error" in report
    assert spring.native.app.documents == []


@pytest.mark.parametrize("mode,match", [
    ("autostart", "AUTOSTART"), ("pid", "PID"), ("cache", "cache off"),
    ("candidate", "candidate"), ("source", "named, pinned"), ("token", "execution token"),
])
def test_invalid_preflight_never_enters_com_parent(spring, monkeypatch, mode, match):
    import dodo
    monkeypatch.setenv("HARMONIC_SW_AUTOSTART", "0")
    monkeypatch.setenv("HARMONIC_DIAGNOSTIC_SW_PID", "1234")
    monkeypatch.setenv("HARMONIC_REMOTE_CACHE_MODE", "off")
    monkeypatch.setattr(probe.pilot.benchmark, "revision", lambda _: "candidate")
    monkeypatch.setattr(dodo, "_run", lambda *a, **k: pytest.fail("must reject before seat runner"))
    if mode == "autostart":
        monkeypatch.setenv("HARMONIC_SW_AUTOSTART", "1")
    if mode == "pid":
        monkeypatch.delenv("HARMONIC_DIAGNOSTIC_SW_PID")
    if mode == "cache":
        monkeypatch.setenv("HARMONIC_REMOTE_CACHE_MODE", "ro")
    if mode == "candidate":
        monkeypatch.setattr(probe.pilot.benchmark, "revision", lambda _: "foreign")
    if mode == "source":
        spring.source.write_bytes(b"wrong source")
    if mode == "token":
        spring.token.write_text("wrong", encoding="utf-8")
    with pytest.raises(RuntimeError, match=match):
        probe.main(["--source", str(spring.source), "--report-root", str(spring.reports)])
    assert not spring.native.adapter.opens


def test_parent_forwards_exact_candidate_source_and_seat_contract(spring, monkeypatch):
    import dodo
    monkeypatch.setenv("HARMONIC_SW_AUTOSTART", "0")
    monkeypatch.setenv("HARMONIC_DIAGNOSTIC_SW_PID", "1234")
    monkeypatch.setenv("HARMONIC_REMOTE_CACHE_MODE", "off")
    monkeypatch.setattr(probe.pilot.benchmark, "revision", lambda _: "candidate")
    calls = []
    monkeypatch.setattr(dodo, "_run", lambda *a, **k: calls.append((a, k)))
    assert probe.main(["--source", str(spring.source), "--report-root", str(spring.reports)]) == 0
    (args, kwargs), = calls
    assert args[0] == [probe.sys.executable, str(Path(probe.__file__).resolve()), "--worker",
                       "--source", str(spring.source), "--candidate", "candidate",
                       "--report-root", str(spring.reports)]
    assert kwargs == {"com": True, "log_stem": "spring-endpoints"}
    assert not spring.native.adapter.opens


@pytest.mark.parametrize("mode", ["foreign_package", "wrong_adapter", "dirty_checkout"])
def test_runtime_provenance_rejects_foreign_import_or_unfrozen_source(monkeypatch, mode):
    package = probe.ROOT / "SolidworksMCP-python/src/solidworks_mcp"
    monkeypatch.setattr(probe.pilot, "adapter_fingerprints", lambda: {
        "package_path": str(package if mode != "foreign_package" else package.parent)})
    def git(command, **kwargs):
        if command[1] == "rev-parse":
            return NS(stdout="wrong" if mode == "wrong_adapter" else probe.ADAPTER_REVISION)
        return NS(stdout=" M source.py" if mode == "dirty_checkout" else "")
    monkeypatch.setattr(probe.subprocess, "run", git)
    with pytest.raises(RuntimeError, match="outside|revision|frozen"):
        probe.runtime()


def test_both_spring_tests_are_enrolled_exactly_once_with_runtime_dependencies():
    import dodo
    recipe = next(task for task in dodo.task_check() if task["name"] == "recipe")
    command = [Path(value).name for value in recipe["actions"][0][1][0]]
    deps = {Path(value).name for value in recipe["file_dep"]}
    for name in ("test_spring_mesh_gap.py", "test_spring_endpoint_probe.py"):
        assert command.count(name) == 1
        assert name in deps
    assert {"probe_spring_endpoints.py", "probe_spring_mesh_gap.py"} <= deps
