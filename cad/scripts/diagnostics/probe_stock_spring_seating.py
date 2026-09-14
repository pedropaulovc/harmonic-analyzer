"""Certify four native stock-spring seats using independent grounded fixtures.

    uv run python cad/scripts/diagnostics/probe_stock_spring_seating.py

Reads existing saved parts only: never builds spring variants or saves models.
Each case starts at the production analytical seed in a fresh two-part assembly.
The public solver proposes/certifies contact; independent assembly interference
and ClosestDistance measurements check the applied and rebuilt actual placement.
Standard run_build performs its normal initial document cleanup; save user work
before running. This diagnostic closes only its owned fixtures and input docs.
"""
from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
import math
from pathlib import Path
import sys
import traceback

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import dodo
import _telemetry
import build_channel_assembly as channel
import build_summing_assembly as summing
import channel_kinematics
import spring_mount_geom as mounts
from _assembly import place_component
from _common import _early_bound, _read_member, check, run_build
from _cwm import put_component_pose
from _native_spring_contact import (
    NATIVE_CONTACT_DISTANCE_TOLERANCE_MM,
    solve_component_contact,
)
from _transforms import IDENTITY, ROT_Y_180, compose_rows, euler_from_rows

ROOT = Path(__file__).resolve().parents[3]
OUTPUT = ROOT / "cad/out/reports/stock-spring-seating.json"
PARTS = (
    "boss-hook", "counter-spring", "gooseneck", "channel-lever",
    "channel-spring-installed", "spring-hook",
)
CASES = ("counter lower", "counter upper", "channel upper", "channel lower")


def hashes():
    values = {}
    for stem in PARTS:
        path = ROOT / "cad/out/sldprt" / f"{stem}.SLDPRT"
        with path.open("rb") as stream:
            values[str(path)] = hashlib.file_digest(stream, "sha256").hexdigest()
    return values


def component(adapter, name):
    asm = _early_bound(adapter.currentModel, "IAssemblyDoc")
    raw = asm.GetComponentByName(name)
    if raw is None:
        raise RuntimeError("missing fixture component " + name)
    return _early_bound(raw, "IComponent2")


def transform(adapter, name):
    comp = component(adapter, name)
    native = _early_bound(_read_member(comp, "Transform2"), "IMathTransform")
    values = [float(value) for value in _read_member(native, "ArrayData")]
    if len(values) != 16 or not all(math.isfinite(value) for value in values):
        raise RuntimeError("invalid typed transform readback: " + name)
    return values


def assert_transforms(adapter, expected):
    actual = {name: transform(adapter, name) for name in expected}
    for name, target in expected.items():
        if max(abs(a - b) for a, b in zip(actual[name], target, strict=True)) > 1e-12:
            raise RuntimeError(f"{name}: actual fixture transform changed unexpectedly")
    return actual


def put(adapter, name, target):
    if not component(adapter, name).IsFixed():
        raise RuntimeError("only grounded fixture components may move: " + name)
    put_component_pose(adapter, name, target)
    return assert_transforms(adapter, {name: target})[name]


def shifted(seed, direction, offset):
    target = list(seed)
    for axis, value in enumerate(direction):
        target[9 + axis] += value * offset / 1000
    return target


def rebuild_placement(model):
    # Match production contact trials: update assembly mates, not part features.
    extension = _early_bound(_read_member(model, "Extension"), "IModelDocExtension")
    if not extension.Rebuild(4):
        raise RuntimeError("native fixture mate update failed")


def actual_contact(adapter, moving, fixed):
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    asm = _early_bound(model, "IAssemblyDoc")
    expected = {name: transform(adapter, name) for name in (moving, fixed)}
    result = model.ClosestDistance(component(adapter, moving), component(adapter, fixed))
    if not isinstance(result, tuple) or len(result) != 3:
        raise RuntimeError(f"unexpected native ClosestDistance result: {result}")
    distance, point1, point2 = result
    distance = float(distance) * 1000
    if not math.isfinite(distance) or distance < 0:
        raise RuntimeError("native ClosestDistance has no solution")
    evidence = {
        "distance_mm": distance, "distance_mm_17g": format(distance, ".17g"),
        "point1_assembly_mm": None if point1 is None else [float(value) * 1000 for value in point1],
        "point2_assembly_mm": None if point2 is None else [float(value) * 1000 for value in point2],
        "assembly_interferences": [],
    }
    model.ClearSelection2(True)
    adapter._attempt(lambda: asm.ToolsCheckInterference(), default=None)
    manager = _early_bound(_read_member(asm, "InterferenceDetectionManager"), "IInterferenceDetectionMgr")
    primary = None
    try:
        for key, value in {
            "TreatCoincidenceAsInterference": False,
            "TreatSubAssembliesAsComponents": True,
            "IncludeMultibodyPartInterferences": True,
            "MakeInterferingPartsTransparent": False,
            "CreateFastenersFolder": False,
            "UseTransform": False,
        }.items():
            setattr(manager, key, value)
        # Each fixture contains exactly this pair. Any returned interference is
        # a failure; no volume threshold silently tolerates a small overlap.
        for raw in manager.GetInterferences() or []:
            hit = _early_bound(raw, "IInterference")
            evidence["assembly_interferences"].append({
                "components": [str(_read_member(comp, "Name2")) for comp in _read_member(hit, "Components") or []],
                "volume_mm3": float(_read_member(hit, "Volume")) * 1e9,
            })
        evidence["transforms_after_query"] = assert_transforms(adapter, expected)
    except BaseException as exc:
        primary = exc
        raise
    finally:
        try:
            manager.Done()
        except Exception as cleanup:
            if primary is None:
                raise
            primary.add_note(f"interference cleanup failed: {cleanup}")
    assert_transforms(adapter, expected)
    evidence["native_distance_certified"] = (
        not evidence["assembly_interferences"]
        and distance <= NATIVE_CONTACT_DISTANCE_TOLERANCE_MM
    )
    return evidence


def require_solution(solution):
    if solution.offset_mm != solution.clear_offset_mm:
        raise RuntimeError("solution offset differs from its certified clear endpoint")
    if solution.certificate == "already_seated":
        if solution.offset_mm != 0 or solution.iterations != 0:
            raise RuntimeError("already-seated solution proposes another displacement")
    elif solution.certificate != "bracketed_native_contact":
        raise RuntimeError("unknown native contact certificate")
    if solution.witness == "native_distance":
        if solution.certificate != "already_seated" or solution.interfering_offset_mm is not None:
            raise RuntimeError("native-distance witness has an unexpected bracket")
    elif solution.witness == "native_collision_bracket":
        if solution.interfering_offset_mm is None:
            raise RuntimeError("native collision witness has no interfering endpoint")
        if not 0 < solution.clear_offset_mm - solution.interfering_offset_mm <= 1e-6:
            raise RuntimeError("native collision bracket did not converge to 1e-6 mm")
    else:
        raise RuntimeError("unknown native contact witness")


def apply_from_seed(adapter, moving, seed, direction, offset, maximum):
    target = shifted(seed, direction, offset)
    endpoints = [shifted(seed, direction, value) for value in (-maximum, maximum)]
    waypoint = max(endpoints, key=lambda value: math.dist(value[9:12], target[9:12]))
    put(adapter, moving, waypoint)
    put(adapter, moving, target)
    return target


def verify_witness(adapter, moving, fixed, direction, maximum, base, solution, evidence, label):
    """Independently query real endpoint placements, then restore the entry pose."""
    require_solution(solution)
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    original = {name: transform(adapter, name) for name in (moving, fixed)}
    primary = None
    try:
        clear = apply_from_seed(
            adapter, moving, base[moving], direction, solution.clear_offset_mm, maximum
        )
        rebuild_placement(model)
        assert_transforms(adapter, {**base, moving: clear})
        evidence["clear"] = actual_contact(adapter, moving, fixed)
        if evidence["clear"]["assembly_interferences"]:
            raise RuntimeError(label + ": claimed clear endpoint actually interferes")
        if solution.witness == "native_distance":
            if not evidence["clear"]["native_distance_certified"]:
                raise RuntimeError(label + ": independent native distance exceeds 10 nm")
        else:
            inside = apply_from_seed(
                adapter, moving, base[moving], direction,
                solution.interfering_offset_mm, maximum,
            )
            rebuild_placement(model)
            assert_transforms(adapter, {**base, moving: inside})
            evidence["interfering"] = actual_contact(adapter, moving, fixed)
            if not evidence["interfering"]["assembly_interferences"]:
                raise RuntimeError(label + ": claimed inside endpoint is actually clear")
            evidence["bracket_width_mm"] = (
                solution.clear_offset_mm - solution.interfering_offset_mm
            )
            if not evidence["clear"]["native_distance_certified"]:
                message = (
                    f"{label}: native collision transition is within 1 nm, but "
                    f"ClosestDistance is {evidence['clear']['distance_mm']:.17g} mm; "
                    "no overlap allowance or distance margin was added"
                )
                evidence["distance_disagreement_warning"] = message
                _telemetry.warn(message)
        evidence["verified_witness"] = solution.witness
    except BaseException as exc:
        primary = exc
        raise
    finally:
        try:
            apply_from_seed(adapter, moving, original[moving], direction, 0.0, maximum)
            rebuild_placement(model)
            evidence["restored_transforms"] = assert_transforms(adapter, original)
        except Exception as cleanup:
            if primary is None:
                raise
            primary.add_note(f"restoring independent endpoint probe failed: {cleanup}")


async def add(adapter, stem, position, rows):
    return await place_component(
        adapter, stem, list(position), euler_from_rows(rows), rows, ground=True
    )


@_telemetry.traced("diagnostic.stock_spring_seating", label_param="label")
async def fixture(adapter, label, row):
    initially_open = {str(_early_bound(doc, "IModelDoc2").GetTitle())
                      for doc in adapter.swApp.GetDocuments() or []}
    fixture_title = None
    input_paths = {str((ROOT / "cad/out/sldprt" / f"{stem}.SLDPRT").resolve()).casefold() for stem in PARTS}
    primary = None
    try:
        check("create " + label + " fixture", await adapter.create_assembly())
        model = _early_bound(adapter.currentModel, "IModelDoc2")
        fixture_title = str(model.GetTitle())
        if label.startswith("counter"):
            pose = mounts.COUNTER_REFERENCE_POSE
            spring = await add(adapter, "counter-spring", summing.SPRING_SEED_POS, pose.rotation_rows)
            if label == "counter lower":
                fixed = await add(adapter, "boss-hook", summing.BOSS_HOOK_POS, IDENTITY)
                moving = spring
                direction = (-pose.axis_xy[0], -pose.axis_xy[1], 0.0)
            else:
                moving = await add(adapter, "gooseneck", summing.GOOSENECK_SEED_POS, ROT_Y_180)
                fixed = spring
                direction = (0.0, -1.0, 0.0)
        else:
            pose = mounts.channel_pose(0.0)
            z = 0.0  # Match the production native channel seating fixture.
            moving = await add(adapter, "channel-spring-installed", (*pose.centre_xy, z), pose.rotation_rows)
            if label == "channel upper":
                state = channel_kinematics.solve_state(0.0)
                rows = compose_rows(channel.rot_z_rows(state["lever_tilt"]), ROT_Y_180)
                fixed = await add(adapter, "channel-lever", (*channel.FULCRUM, z), rows)
                direction = (*pose.axis_xy, 0.0)
            else:
                fixed = await add(adapter, "spring-hook", (*mounts.CHANNEL_ANCHOR_XY, z), IDENTITY)
                direction = (-pose.axis_xy[0], -pose.axis_xy[1], 0.0)
        for name in (moving, fixed):
            if not component(adapter, name).IsFixed():
                raise RuntimeError("fixture component is not grounded: " + name)
        rebuild_placement(model)
        seed = {name: transform(adapter, name) for name in (moving, fixed)}
        maximum = mounts.MIN_CLEARANCE_MM / 2
        row.update({"moving": moving, "fixed": fixed, "direction_xyz": direction,
                    "max_translation_mm": maximum, "seed_transforms": seed,
                    "seed_actual_contact": actual_contact(adapter, moving, fixed)})
        solution = solve_component_contact(adapter, moving, fixed, direction, maximum, label=label + " seed")
        row["solution"] = asdict(solution)
        require_solution(solution)
        row["restored_seed_transforms"] = assert_transforms(adapter, seed)
        row["initial_witness_check"] = {}
        verify_witness(
            adapter, moving, fixed, direction, maximum, seed, solution,
            row["initial_witness_check"], label + " initial witness",
        )
        target = apply_from_seed(
            adapter, moving, seed[moving], direction, solution.offset_mm, maximum
        )
        row["target_transform"] = target
        row["applied_transform"] = transform(adapter, moving)
        rebuild_placement(model)
        expected = {**seed, moving: target}
        row["rebuilt_transforms"] = assert_transforms(adapter, expected)
        row["rebuilt_actual_contact"] = actual_contact(adapter, moving, fixed)
        if row["rebuilt_actual_contact"]["assembly_interferences"]:
            raise RuntimeError(label + ": rebuilt actual assembly interferes")
        repeated = solve_component_contact(adapter, moving, fixed, direction, maximum, label=label + " re-solve")
        row["repeated_solution"] = asdict(repeated)
        require_solution(repeated)
        if repeated.certificate != "already_seated":
            raise RuntimeError(label + ": applied seat requires another displacement")
        row["final_transforms"] = assert_transforms(adapter, expected)
        row["final_actual_contact"] = actual_contact(adapter, moving, fixed)
        if row["final_actual_contact"]["assembly_interferences"]:
            raise RuntimeError(label + ": re-solve changed the clear native seat")
        row["repeated_witness_check"] = {}
        verify_witness(
            adapter, moving, fixed, direction, maximum, expected, repeated,
            row["repeated_witness_check"], label + " repeated witness",
        )
        row["post_witness_actual_contact"] = actual_contact(adapter, moving, fixed)
        if row["post_witness_actual_contact"]["assembly_interferences"]:
            raise RuntimeError(label + ": endpoint verification did not restore the clear seat")
        if repeated.witness == "native_distance" and not row["post_witness_actual_contact"]["native_distance_certified"]:
            raise RuntimeError(label + ": restored distance witness exceeds 10 nm")
        row["status"] = "passed"
    except BaseException as exc:
        primary = exc
        row["status"] = "failed"
        row["error"] = traceback.format_exc()
        raise
    finally:
        owned = [fixture_title] if fixture_title is not None else []
        for raw in adapter.swApp.GetDocuments() or []:
            doc = _early_bound(raw, "IModelDoc2")
            title = str(doc.GetTitle())
            if title not in initially_open and str(doc.GetPathName()).casefold() in input_paths:
                owned.append(title)
        for title in dict.fromkeys(owned):
            try:
                adapter.swApp.CloseDoc(title)
            except Exception as cleanup:
                if primary is None:
                    raise
                primary.add_note(f"closing owned document {title} failed: {cleanup}")
        adapter.currentModel = None


async def probe(adapter):
    report = {"status": "started", "cases": [], "input_sha256_before": hashes(),
              "native_contact_distance_tolerance_mm": NATIVE_CONTACT_DISTANCE_TOLERANCE_MM,
              "position_convergence_mm": 1e-6}
    try:
        for label in CASES:
            row = {"label": label, "status": "started"}
            report["cases"].append(row)
            await fixture(adapter, label, row)
            OUTPUT.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        report["status"] = "passed"
        return {"report": str(OUTPUT)}
    except BaseException:
        report["status"] = "failed"
        report["error"] = traceback.format_exc()
        raise
    finally:
        report["input_sha256_after"] = hashes()
        changed = report["input_sha256_after"] != report["input_sha256_before"]
        if changed:
            report["status"] = "failed"
            report["input_integrity_error"] = "saved fixture part bytes changed"
        OUTPUT.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        if changed:
            raise RuntimeError(report["input_integrity_error"])


def main():
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with dodo._com_seat("probe-stock-spring-seating"):
        return run_build(probe)


if __name__ == "__main__":
    raise SystemExit(main())
