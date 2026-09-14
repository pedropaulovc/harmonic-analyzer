"""Certify native stock-spring seats and diagnose saved summing collisions.

    uv run python cad/scripts/diagnostics/probe_stock_spring_seating.py
    uv run python cad/scripts/diagnostics/probe_stock_spring_seating.py \
        --saved-summing-detector-comparison

The default mode preserves the four independent two-part fixtures.  The saved
mode reads summing.SLDASM, compares the ordinary all-component interference
manager with native assembly-instance body intersections, restores every trial
pose, and closes every owned model without saving.  Standard run_build performs
its normal initial document cleanup; save user work before running.
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
from _assembly import configured_interference_manager, place_component
from _common import _early_bound, _read_member, check, run_build
from _cwm import put_component_pose
from _native_spring_contact import (
    NATIVE_CONTACT_DISTANCE_TOLERANCE_MM,
    native_component_overlap_mm3,
    solve_component_contact,
)
from _transforms import IDENTITY, ROT_Y_180, compose_rows, euler_from_rows

ROOT = Path(__file__).resolve().parents[3]
OUTPUT = ROOT / "cad/out/reports/stock-spring-seating.json"
PARTS = (
    "boss-hook",
    "counter-spring",
    "gooseneck",
    "channel-lever",
    "channel-spring-installed",
    "spring-hook",
)
CASES = ("counter lower", "counter upper", "channel upper", "channel lower")
SAVED_SUMMING_MODE = "--saved-summing-detector-comparison"
SUMMING_ASSEMBLY = ROOT / "cad/out/sldasm" / f"{summing.ASM_NAME}.SLDASM"
MANAGER_SETTINGS = (
    "TreatCoincidenceAsInterference",
    "TreatSubAssembliesAsComponents",
    "IncludeMultibodyPartInterferences",
    "MakeInterferingPartsTransparent",
    "CreateFastenersFolder",
    "UseTransform",
)


def requested_mode():
    if not sys.argv[1:]:
        return "fixtures"
    if sys.argv[1:] == [SAVED_SUMMING_MODE]:
        return "saved_summing_detector_comparison"
    raise SystemExit(f"usage: {Path(sys.argv[0]).name} [{SAVED_SUMMING_MODE}]")


def hash_paths(paths):
    values = {}
    for path in sorted({Path(path).resolve() for path in paths}):
        with path.open("rb") as stream:
            values[str(path)] = hashlib.file_digest(stream, "sha256").hexdigest()
    return values


def hashes():
    return hash_paths(ROOT / "cad/out/sldprt" / f"{stem}.SLDPRT" for stem in PARTS)


def component(adapter, name):
    asm = _early_bound(adapter.currentModel, "IAssemblyDoc")
    raw = asm.GetComponentByName(name)
    if raw is None:
        raise RuntimeError("missing fixture component " + name)
    return _early_bound(raw, "IComponent2")


def component_names(adapter):
    asm = _early_bound(adapter.currentModel, "IAssemblyDoc")
    names = [
        str(_read_member(_early_bound(raw, "IComponent2"), "Name2"))
        for raw in asm.GetComponents(True) or []
    ]
    if len(names) != len(set(names)):
        raise RuntimeError("saved assembly has duplicate top-level component names")
    return sorted(names)


def component_for_stem(adapter, stem):
    matches = []
    for name in component_names(adapter):
        source = str(component(adapter, name).GetPathName() or "")
        if source and Path(source).stem.casefold() == stem.casefold():
            matches.append(name)
    if len(matches) != 1:
        raise RuntimeError(f"expected one top-level {stem} component, found {matches}")
    return matches[0]


def assembly_transforms(adapter):
    return {name: transform(adapter, name) for name in component_names(adapter)}


def assembly_source_paths(adapter):
    paths = {SUMMING_ASSEMBLY.resolve()}
    for name in component_names(adapter):
        source = str(component(adapter, name).GetPathName() or "")
        if not source:
            raise RuntimeError(f"component source path unavailable: {name}")
        path = Path(source).resolve()
        if not path.is_file():
            raise RuntimeError(f"component source does not exist: {path}")
        paths.add(path)
    return sorted(paths)


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


def closest_distance(adapter, moving, fixed):
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    result = model.ClosestDistance(
        component(adapter, moving), component(adapter, fixed)
    )
    if not isinstance(result, tuple) or len(result) != 3:
        raise RuntimeError(f"unexpected native ClosestDistance result: {result}")
    distance, point1, point2 = result
    distance_mm = float(distance) * 1000
    if not math.isfinite(distance_mm) or distance_mm < 0:
        raise RuntimeError("native ClosestDistance has no solution")

    def point_mm(point, label):
        if point is None:
            return None
        values = [float(value) * 1000 for value in point]
        if len(values) != 3 or not all(math.isfinite(value) for value in values):
            raise RuntimeError(f"native ClosestDistance {label} is malformed")
        return values

    return {
        "distance_mm": distance_mm,
        "distance_mm_17g": format(distance_mm, ".17g"),
        "point1_assembly_mm": point_mm(point1, "point1"),
        "point2_assembly_mm": point_mm(point2, "point2"),
    }


def actual_contact(adapter, moving, fixed):
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    asm = _early_bound(model, "IAssemblyDoc")
    expected = {name: transform(adapter, name) for name in (moving, fixed)}
    evidence = {
        **closest_distance(adapter, moving, fixed),
        "assembly_interferences": [],
    }
    model.ClearSelection2(True)
    adapter._attempt(lambda: asm.ToolsCheckInterference(), default=None)
    manager = configured_interference_manager(adapter)
    primary = None
    try:
        # Each fixture contains exactly this pair. Any returned interference is
        # a failure; no volume threshold silently tolerates a small overlap.
        for raw in manager.GetInterferences() or []:
            hit = _early_bound(raw, "IInterference")
            evidence["assembly_interferences"].append(
                {
                    "components": [
                        str(_read_member(comp, "Name2"))
                        for comp in _read_member(hit, "Components") or []
                    ],
                    "volume_mm3": float(_read_member(hit, "Volume")) * 1e9,
                }
            )
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
        and evidence["distance_mm"] <= NATIVE_CONTACT_DISTANCE_TOLERANCE_MM
    )
    return evidence


def configured_manager_comparison(adapter, expected, monitored_pair, control_pair):
    """Run the ordinary unscoped manager and retain both diagnostic pairs."""
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    asm = _early_bound(model, "IAssemblyDoc")
    model.ClearSelection2(True)
    adapter._attempt(lambda: asm.ToolsCheckInterference(), default=None)
    manager = configured_interference_manager(adapter)
    evidence = {
        "scope": "all_top_level_components",
        "settings": {
            name: bool(_read_member(manager, name)) for name in MANAGER_SETTINGS
        },
        "interferences": [],
    }
    primary = None
    try:
        for raw in manager.GetInterferences() or []:
            hit = _early_bound(raw, "IInterference")
            names = [
                str(_read_member(comp, "Name2"))
                for comp in _read_member(hit, "Components") or []
            ]
            volume_mm3 = float(_read_member(hit, "Volume")) * 1e9
            if not math.isfinite(volume_mm3) or volume_mm3 < 0:
                raise RuntimeError(
                    f"ordinary manager returned invalid volume: {volume_mm3!r}"
                )
            evidence["interferences"].append(
                {
                    "components": names,
                    "volume_mm3": volume_mm3,
                    "volume_mm3_17g": format(volume_mm3, ".17g"),
                }
            )
        evidence["poses_before_done"] = assert_transforms(adapter, expected)
    except BaseException as exc:
        primary = exc
        raise
    finally:
        try:
            manager.Done()
        except BaseException as cleanup:
            if primary is None:
                raise
            primary.add_note(f"saved summing interference Done failed: {cleanup}")
    evidence["poses_after_done"] = assert_transforms(adapter, expected)

    def pair_result(pair):
        pair_names = set(pair)
        hits = [
            row
            for row in evidence["interferences"]
            if len(row["components"]) == 2 and set(row["components"]) == pair_names
        ]
        volume_mm3 = sum(row["volume_mm3"] for row in hits)
        return {
            "components": list(pair),
            "state": "interfering" if hits else "clear",
            "volume_mm3": volume_mm3,
            "volume_mm3_17g": format(volume_mm3, ".17g"),
            "hits": hits,
        }

    evidence["monitored_pair"] = pair_result(monitored_pair)
    evidence["positive_control"] = pair_result(control_pair)
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
        if (
            solution.certificate != "already_seated"
            or solution.interfering_offset_mm is not None
        ):
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


def verify_witness(
    adapter, moving, fixed, direction, maximum, base, solution, evidence, label
):
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
                raise RuntimeError(
                    label + ": independent native distance exceeds 10 nm"
                )
        else:
            inside = apply_from_seed(
                adapter,
                moving,
                base[moving],
                direction,
                solution.interfering_offset_mm,
                maximum,
            )
            rebuild_placement(model)
            assert_transforms(adapter, {**base, moving: inside})
            evidence["interfering"] = actual_contact(adapter, moving, fixed)
            if not evidence["interfering"]["assembly_interferences"]:
                raise RuntimeError(
                    label + ": claimed inside endpoint is actually clear"
                )
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
    initially_open = {
        str(_early_bound(doc, "IModelDoc2").GetTitle())
        for doc in adapter.swApp.GetDocuments() or []
    }
    fixture_title = None
    input_paths = {
        str((ROOT / "cad/out/sldprt" / f"{stem}.SLDPRT").resolve()).casefold()
        for stem in PARTS
    }
    primary = None
    try:
        check("create " + label + " fixture", await adapter.create_assembly())
        model = _early_bound(adapter.currentModel, "IModelDoc2")
        fixture_title = str(model.GetTitle())
        if label.startswith("counter"):
            pose = mounts.COUNTER_REFERENCE_POSE
            spring = await add(
                adapter, "counter-spring", summing.SPRING_SEED_POS, pose.rotation_rows
            )
            if label == "counter lower":
                fixed = await add(adapter, "boss-hook", summing.BOSS_HOOK_POS, IDENTITY)
                moving = spring
                direction = (-pose.axis_xy[0], -pose.axis_xy[1], 0.0)
            else:
                moving = await add(
                    adapter, "gooseneck", summing.GOOSENECK_SEED_POS, ROT_Y_180
                )
                fixed = spring
                direction = (0.0, -1.0, 0.0)
        else:
            pose = mounts.channel_pose(0.0)
            z = 0.0  # Match the production native channel seating fixture.
            moving = await add(
                adapter,
                "channel-spring-installed",
                (*pose.centre_xy, z),
                pose.rotation_rows,
            )
            if label == "channel upper":
                state = channel_kinematics.solve_state(0.0)
                rows = compose_rows(channel.rot_z_rows(state["lever_tilt"]), ROT_Y_180)
                fixed = await add(adapter, "channel-lever", (*channel.FULCRUM, z), rows)
                direction = (*pose.axis_xy, 0.0)
            else:
                fixed = await add(
                    adapter, "spring-hook", (*mounts.CHANNEL_ANCHOR_XY, z), IDENTITY
                )
                direction = (-pose.axis_xy[0], -pose.axis_xy[1], 0.0)
        for name in (moving, fixed):
            if not component(adapter, name).IsFixed():
                raise RuntimeError("fixture component is not grounded: " + name)
        rebuild_placement(model)
        seed = {name: transform(adapter, name) for name in (moving, fixed)}
        maximum = mounts.MIN_CLEARANCE_MM / 2
        row.update(
            {
                "moving": moving,
                "fixed": fixed,
                "direction_xyz": direction,
                "max_translation_mm": maximum,
                "seed_transforms": seed,
                "seed_actual_contact": actual_contact(adapter, moving, fixed),
            }
        )
        solution = solve_component_contact(
            adapter, moving, fixed, direction, maximum, label=label + " seed"
        )
        row["solution"] = asdict(solution)
        require_solution(solution)
        row["restored_seed_transforms"] = assert_transforms(adapter, seed)
        row["initial_witness_check"] = {}
        verify_witness(
            adapter,
            moving,
            fixed,
            direction,
            maximum,
            seed,
            solution,
            row["initial_witness_check"],
            label + " initial witness",
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
        repeated = solve_component_contact(
            adapter, moving, fixed, direction, maximum, label=label + " re-solve"
        )
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
            adapter,
            moving,
            fixed,
            direction,
            maximum,
            expected,
            repeated,
            row["repeated_witness_check"],
            label + " repeated witness",
        )
        row["post_witness_actual_contact"] = actual_contact(adapter, moving, fixed)
        if row["post_witness_actual_contact"]["assembly_interferences"]:
            raise RuntimeError(
                label + ": endpoint verification did not restore the clear seat"
            )
        if (
            repeated.witness == "native_distance"
            and not row["post_witness_actual_contact"]["native_distance_certified"]
        ):
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
            if (
                title not in initially_open
                and str(doc.GetPathName()).casefold() in input_paths
            ):
                owned.append(title)
        for title in dict.fromkeys(owned):
            try:
                adapter.swApp.CloseDoc(title)
            except Exception as cleanup:
                if primary is None:
                    raise
                primary.add_note(f"closing owned document {title} failed: {cleanup}")
        adapter.currentModel = None


def document_inventory(adapter):
    rows = []
    for raw in adapter.swApp.GetDocuments() or []:
        doc = _early_bound(raw, "IModelDoc2")
        native_path = str(doc.GetPathName() or "")
        rows.append(
            {
                "path": str(Path(native_path).resolve()) if native_path else "",
                "title": str(doc.GetTitle()),
                "type": int(doc.GetType()),
                "state": "dirty" if doc.GetSaveFlag() else "clean",
            }
        )
    return sorted(
        rows, key=lambda row: (row["path"].casefold(), row["title"].casefold())
    )


def close_owned_documents(adapter, initial, source_paths):
    initial_pairs = {(row["path"], row["title"]) for row in initial}
    source_keys = {str(path).casefold() for path in source_paths}
    owned = [
        row
        for row in document_inventory(adapter)
        if (row["path"], row["title"]) not in initial_pairs
        and row["path"].casefold() in source_keys
    ]
    titles = [row["title"].casefold() for row in owned]
    if any(not row["title"] for row in owned) or len(titles) != len(set(titles)):
        raise RuntimeError(
            "cannot close saved summing sources by unique document title"
        )
    closed = []
    for target in sorted(
        owned,
        key=lambda row: (
            row["path"].casefold() != str(SUMMING_ASSEMBLY.resolve()).casefold()
        ),
    ):
        present = {(row["path"], row["title"]) for row in document_inventory(adapter)}
        pair = (target["path"], target["title"])
        if pair not in present:
            closed.append({**target, "closure": "already_unloaded"})
            continue
        adapter.swApp.CloseDoc(target["title"])
        remaining = {(row["path"], row["title"]) for row in document_inventory(adapter)}
        if pair in remaining:
            raise RuntimeError(
                f"CloseDoc did not unload {target['path']} without saving"
            )
        closed.append({**target, "closure": "closed_without_save"})
    if document_inventory(adapter) != initial:
        raise RuntimeError(
            "saved summing comparison did not restore document inventory"
        )
    return closed


def saved_summing_trial(
    adapter,
    seed,
    moving,
    fixed,
    control,
    direction,
    bracket,
    label,
    offset_mm,
    row,
):
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    entry = assert_transforms(adapter, seed)
    row.update(
        {
            "label": label,
            "offset_mm": offset_mm,
            "offset_mm_17g": format(offset_mm, ".17g"),
            "pose_readbacks": {"entry": entry},
        }
    )
    primary = None
    try:
        target = apply_from_seed(
            adapter, moving, seed[moving], direction, offset_mm, bracket
        )
        row["target_transform"] = target
        rebuild_placement(model)
        expected = {**seed, moving: target}
        row["pose_readbacks"]["placed"] = assert_transforms(adapter, expected)
        row["closest_distance"] = closest_distance(adapter, moving, fixed)
        row["pose_readbacks"]["after_closest_distance"] = assert_transforms(
            adapter, expected
        )
        row["ordinary_manager"] = configured_manager_comparison(
            adapter, expected, (moving, fixed), control
        )
        row["pose_readbacks"]["after_ordinary_manager"] = assert_transforms(
            adapter, expected
        )
        overlap_mm3 = native_component_overlap_mm3(
            adapter,
            moving,
            fixed,
            label=f"saved summing {label} lower counter/boss",
        )
        row["pose_readbacks"]["after_native_monitored_pair"] = assert_transforms(
            adapter, expected
        )
        control_mm3 = native_component_overlap_mm3(
            adapter,
            control[0],
            control[1],
            label=f"saved summing {label} boss-hook/summing-lever control",
        )
        row["pose_readbacks"]["after_native_positive_control"] = assert_transforms(
            adapter, expected
        )
        manager_control = row["ordinary_manager"]["positive_control"]
        row["native_bodies"] = {
            "monitored_pair": {
                "components": [moving, fixed],
                "state": "interfering" if overlap_mm3 > 0.0 else "clear",
                "volume_mm3": overlap_mm3,
                "volume_mm3_17g": format(overlap_mm3, ".17g"),
            },
            "positive_control": {
                "components": list(control),
                "state": "interfering" if control_mm3 > 0.0 else "clear",
                "volume_mm3": control_mm3,
                "volume_mm3_17g": format(control_mm3, ".17g"),
            },
        }
        if (
            manager_control["state"] != "interfering"
            or manager_control["volume_mm3"] <= 0.0
        ):
            raise RuntimeError(
                f"{label}: ordinary manager lost boss-hook/summing-lever positive control"
            )
        if control_mm3 <= 0.0:
            raise RuntimeError(
                f"{label}: native bodies lost boss-hook/summing-lever positive control"
            )
        if label == "inward" and overlap_mm3 <= 0.0:
            raise RuntimeError("inward saved summing control is not overlapping")
        if label == "outward" and overlap_mm3 != 0.0:
            raise RuntimeError("outward saved summing control is not clear")
        row["status"] = "passed"
    except BaseException as exc:
        primary = exc
        row["status"] = "failed"
        row["error"] = traceback.format_exc()
        raise
    finally:
        try:
            apply_from_seed(adapter, moving, entry[moving], direction, 0.0, bracket)
            rebuild_placement(model)
            row["pose_readbacks"]["restored"] = assert_transforms(adapter, entry)
        except BaseException as cleanup:
            row["status"] = "failed"
            row["restoration_error"] = traceback.format_exc()
            if primary is None:
                raise
            primary.add_note(f"restoring saved summing {label} trial failed: {cleanup}")


@_telemetry.traced("diagnostic.stock_spring_saved_comparison")
async def saved_summing_comparison(adapter, report):
    initial_documents = document_inventory(adapter)
    source_paths = [SUMMING_ASSEMBLY.resolve()]
    report.update(
        {
            "assembly": str(SUMMING_ASSEMBLY.resolve()),
            "source_paths": [str(path) for path in source_paths],
            "documents_before_open": initial_documents,
        }
    )
    primary = None
    try:
        if not SUMMING_ASSEMBLY.is_file():
            raise RuntimeError(
                f"saved summing assembly does not exist: {SUMMING_ASSEMBLY}"
            )
        report["source_sha256_before"] = hash_paths(source_paths)
        check(
            "open saved summing detector comparison",
            await adapter.open_model(str(SUMMING_ASSEMBLY.resolve())),
        )
        model = _early_bound(adapter.currentModel, "IModelDoc2")
        if Path(str(model.GetPathName())).resolve() != SUMMING_ASSEMBLY.resolve():
            raise RuntimeError("SolidWorks opened a different summing assembly")
        source_paths = assembly_source_paths(adapter)
        source_sha256 = hash_paths(source_paths)
        moving = component_for_stem(adapter, "counter-spring")
        fixed = component_for_stem(adapter, "boss-hook")
        lever = component_for_stem(adapter, "summing-lever")
        if not component(adapter, moving).IsFixed():
            raise RuntimeError(
                "saved summing lower comparison requires grounded counter-spring"
            )
        ux, uy = mounts.COUNTER_REFERENCE_POSE.axis_xy
        direction = (-ux, -uy, 0.0)
        bracket = mounts.MIN_CLEARANCE_MM / 2.0
        seed = assembly_transforms(adapter)
        report["opened_pose_readback"] = seed
        with _telemetry.span("diagnostic.saved_summing.rebuild"):
            if not model.ForceRebuild3(False):
                raise RuntimeError("saved summing full rebuild failed")
        seed = assembly_transforms(adapter)
        report.update(
            {
                "source_paths": [str(path) for path in source_paths],
                "source_sha256_before": source_sha256,
                "documents_after_open": document_inventory(adapter),
                "moving": moving,
                "fixed": fixed,
                "positive_control": [fixed, lever],
                "direction_xyz": direction,
                "bracket_mm": bracket,
                "offsets_mm": {
                    "seed": 0.0,
                    "inward": -bracket,
                    "outward": bracket,
                    "seed_repeat": 0.0,
                },
                "seed_pose_readback": seed,
                "trials": [],
            }
        )
        for label, offset in (
            ("seed", 0.0),
            ("inward", -bracket),
            ("outward", bracket),
            ("seed_repeat", 0.0),
        ):
            row = {"status": "started"}
            report["trials"].append(row)
            saved_summing_trial(
                adapter,
                seed,
                moving,
                fixed,
                (fixed, lever),
                direction,
                bracket,
                label,
                offset,
                row,
            )
            OUTPUT.write_text(
                json.dumps(report, indent=2, allow_nan=False) + "\n",
                encoding="utf-8",
            )
        first, repeated = report["trials"][0], report["trials"][-1]
        if (
            first["native_bodies"]["monitored_pair"]["state"]
            != repeated["native_bodies"]["monitored_pair"]["state"]
        ):
            raise RuntimeError("saved summing native-body seed state is not repeatable")
        report["ordinary_manager_seed_repeatability"] = (
            "stable"
            if first["ordinary_manager"]["monitored_pair"]["state"]
            == repeated["ordinary_manager"]["monitored_pair"]["state"]
            else "changed"
        )
        report["seed_native_state"] = first["native_bodies"]["monitored_pair"]["state"]
        report["ordinary_manager_omission_trials"] = [
            row["label"]
            for row in report["trials"]
            if row["native_bodies"]["monitored_pair"]["state"] == "interfering"
            and row["ordinary_manager"]["monitored_pair"]["state"] == "clear"
        ]
        report["final_pose_readback"] = assert_transforms(adapter, seed)
        report["status"] = "passed"
        _telemetry.success(
            "saved summing detector comparison passed",
            manager_omission_trials=report["ordinary_manager_omission_trials"],
            seed_native_state=report["seed_native_state"],
        )
    except BaseException as exc:
        primary = exc
        report["status"] = "failed"
        report["error"] = traceback.format_exc()
        raise
    finally:
        try:
            report["documents_before_close"] = document_inventory(adapter)
            report["closed_without_save"] = close_owned_documents(
                adapter, initial_documents, source_paths
            )
            report["documents_after_close"] = document_inventory(adapter)
            report["source_sha256_after"] = hash_paths(source_paths)
            changed = (
                report.get("source_sha256_before") != report["source_sha256_after"]
            )
            report["source_integrity"] = "changed" if changed else "unchanged"
            if changed:
                raise RuntimeError("saved summing source bytes changed")
        except BaseException as cleanup:
            report["cleanup_error"] = traceback.format_exc()
            if primary is None:
                raise
            primary.add_note(f"saved summing cleanup failed: {cleanup}")
        finally:
            adapter.currentModel = None


async def probe(adapter):
    mode = requested_mode()
    if mode == "saved_summing_detector_comparison":
        report = {
            "mode": mode,
            "status": "started",
            "native_overlap_threshold_mm3": 0.0,
            "manager_scope": "all_top_level_components",
        }
        try:
            await saved_summing_comparison(adapter, report)
            return {"report": str(OUTPUT)}
        except BaseException:
            report["status"] = "failed"
            report["error"] = traceback.format_exc()
            raise
        finally:
            OUTPUT.write_text(
                json.dumps(report, indent=2, allow_nan=False) + "\n",
                encoding="utf-8",
            )

    report = {
        "mode": mode,
        "status": "started",
        "cases": [],
        "input_sha256_before": hashes(),
        "native_contact_distance_tolerance_mm": NATIVE_CONTACT_DISTANCE_TOLERANCE_MM,
        "position_convergence_mm": 1e-6,
    }
    try:
        for label in CASES:
            row = {"label": label, "status": "started"}
            report["cases"].append(row)
            await fixture(adapter, label, row)
            OUTPUT.write_text(
                json.dumps(report, indent=2, allow_nan=False) + "\n",
                encoding="utf-8",
            )
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
        OUTPUT.write_text(
            json.dumps(report, indent=2, allow_nan=False) + "\n",
            encoding="utf-8",
        )
        if changed:
            raise RuntimeError(report["input_integrity_error"])


def main():
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with dodo._com_seat("probe-stock-spring-seating"):
        return run_build(probe)


if __name__ == "__main__":
    raise SystemExit(main())
