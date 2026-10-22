"""Fixed SM-positive / R1-angle / C1-cut-only disposable-copy investigation.

NEVER MERGE. Three independent original-byte pairs; every PART is readonly.
Only R1/C1 DRAWING COPIES are writable. R1 writes IView.Angle once; C1 writes
IDrSection.SetDisplayOnlySurfaceCut once. No source selection access, geometry,
settings, saves, reference replacement or cumulative intervention is reachable.
Raw native source, display and transform evidence never automatically means SHIP.
Hard termination and existing outer telemetry can defeat reporting/cleanup.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from datetime import UTC, datetime
from pathlib import Path
import sys
import shutil
import struct
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[3]
REPORT = ROOT / "cad/out/reports/diagnostics/mg-saved-thread-control.json"
CONTRACT_PATH = Path(__file__).with_suffix(".json")
SM_POSITIVE = {
    "case": "sm_positive",
    "read_only": {"part": True, "drawing": True},
    "sheet_number": 1,
    "sheet_name": "Lever Geometry",
    "section_label": "H",
    "feature_name": "BracketMountingTaps",
    "drawing": {
        "path": "cad/out/slddrw/sm-summing-lever.SLDDRW",
        "key": "0549c19080401aaeb43a3d9dc5c40e31c53d5743610994318174817cf9cb8363",
        "bytes": 480655,
        "sha256": "775c6edc4befe1c17f4f9dfca1a9d43d5943fc85e15c0ba5c0e411a5bcf6bcf1",
    },
    "part": {
        "path": "cad/out/sldprt/sm-summing-lever.SLDPRT",
        "key": "238dc7587b2a41b5ed7081a08f35f479039418c60291fd9497a265d1ec16457c",
        "bytes": 280124,
        "sha256": "ff952b3739770d218251ab4c8cb333cc3d10e7c34097dbad5762fb1bd771bfdf",
    },
    "historical_provenance": {
        "status": "VERIFIED_EXTERNAL_EVIDENCE",
        "packet": "pr1769-sm-thread-control-20261021",
        "source_report": "C:/farm-runs/com-perf-20261019/20261021T135951435Z-16ea74332725458cadf5ff30f4c0e661.out/reports/cache.jsonl",
        "evidence_files": {
            "historical-recipe-execution-proof.json": {
                "bytes": 16291,
                "sha256": "159e8b334be89c93acd356390b3a528b873a378cd47bed5f724c5221e47db1e8",
            },
            "cache-archives/inventory.json": {
                "bytes": 2823,
                "sha256": "7b6bfe45ae9902ec60311ec5150db2b06c82268811df78eea863e0be43043ce5",
            },
            "manifest.json": {
                "bytes": 4486,
                "sha256": "7cc81384ef133e1c07978e402de01df780f8f33abe8e66798fbb882e719c63c1",
            },
        },
        "epoch": "4",
        "salt": "sw2024-sp3",
        "salt_is_not_runtime_version_proof": True,
        "part_manifest_id": "14e77479a2c39bfcb2d5f215a44b89f73c94b5e10e53726f33831570f9092dd3",
        "drawing_manifest_id": "1482b721b32fc1036a5cad7c65ecfbea0ee6fb222b1cba0c5ba03ef7c703e2cb",
        "part_input_count": 53,
        "drawing_input_count": 56,
        "part_recipe_digest": "26177d5c641f86d7d18f250811d52806",
        "execution_token_canonical_md5": "c7a4f8894771527745ede767473c9f32",
        "linkage": "Historical 53-input recipe replay and preserved execution-token canonical MD5 match the drawing manifest; token value equals the pinned part SHA-256.",
        "historical_source_digests": {
            "cad/scripts/build_sm_summing_lever.py": "bd4ee26fe25279c93a4cfe747cb72307",
            "cad/scripts/draw_sm_summing_lever.py": "25b0af4513486fe1c82c09d6048c77bd",
            "cad/scripts/sm_summing_lever_notes.py": "e1fa8767ec5f9062ca716346830dee5d",
            "cad/scripts/sm_summing_lever_spec.py": "62e838d80e9a0a34bd1ff20d86e28e96",
        },
        "archives": {
            "drawing": {
                "sha256": "1d25552b200ec6c4f5b63b19021f25cbb8dbb322b8633332b86ceec2484c2352",
                "bytes": 1509610,
                "epoch": "4",
                "members": [
                    "cad/out/slddrw/sm-summing-lever.SLDDRW",
                    "cad/out/pdf/sm-summing-lever.pdf",
                    "cad/out/png/sm-summing-lever_drawing.png",
                    "cad/out/reports/layout-audit/sm-summing-lever.json",
                ],
                "contains_part": False,
                "contains_execution_token": False,
            },
            "part": {
                "sha256": "5002b730b4b41c547cdb39c9f3f6c15262c22fab9797543d1e07bdab91c895e1",
                "bytes": 563978,
                "epoch": "4",
                "members": [
                    "cad/out/sldprt/sm-summing-lever.SLDPRT",
                    "cad/out/stl/sm-summing-lever.STL",
                    "cad/out/png/sm-summing-lever",
                    "cad/out/png/sm-summing-lever/sm-summing-lever_isometric.png",
                ],
                "contains_execution_token": False,
            },
        },
        "scope": "Externally verified historical evidence, not worker-fetched proof files or live native reference resolution. The later archive inventory supersedes the proof JSON's pending archive-inventory note.",
    },
}
BRACKET_ORIGINAL = {
    "sheet_number": 1,
    "sheet_name": "Sheet1",
    "section_label": "A",
    "feature_name": "LeverTap",
    "drawing": {
        "path": "cad/out/slddrw/mg-magnifying-bracket-native-thread.SLDDRW",
        "account": "stswboot5qnlwu2vtr6gs",
        "container": "results",
        "blob": "leaf/drawing__mg_magnifying_bracket/e2ceb7e1acd2954697f722021cdb83804314010d31c90f14f0ebf7bc980fd619/20261021T204253Z-1-9e30b42f/failures/mg-magnifying-bracket-native-thread/20261021T204332Z/mg-magnifying-bracket-native-thread.SLDDRW",
        "bytes": 177427,
        "sha256": "35d764341f0c221559e0793e63656578fee6c7f72452155897a1f56d71ce415d",
    },
    "part": {
        "path": "cad/out/sldprt/mg-magnifying-bracket.SLDPRT",
        "key": "6976969e72d6cd4dfc8775bb4d71e7a69ccc1c9034d064f9c53486bffd5eedf2",
        "bytes": 114126,
        "sha256": "cd30821111672d4c0a4e52ed36992ccda2594bd7a735d260c5cceea31cc13932",
    },
    "historical_provenance": {
        "status": "EXECUTION_PINNED_SOURCE_WITH_CAPTURED_FAILED_DRAWING",
        "run": "20261021T185156246Z-b65986dc5548401aa7cd9b2d8999526e",
        "source_commit": "bd160ae0f2994f5018c187279d41cd00f1fe7ab9",
        "part_input_count": 40,
        "duplicate_release_yaml_retained": True,
        "part_recipe_digest": "2d56f0ac631eb3207e61b6a0ba437201",
        "execution_token_bytes": 66,
        "execution_token_canonical_md5": "8469206605bed8151524b843ada692f2",
        "capture_manifest": "C:/src/dt-logs/pr1769-r26-bracket-forensics/manifest.json",
        "capture_document_title": "Draw54 - Sheet1",
        "capture_section_label": "A-A",
        "scope": "Execution-pinned retained/canonical historical source plus captured failed drawing, NOT a successful drawing-cache entry. Capture contains no PRT or worker part hash; identical historical in-memory source state is NOT retrospectively proven. Source-parameter and edge-cause claims remain unproved. Sheet1 comes from the native capture title; section A comes from retained A-A capture context and the section constructor. Reopening must independently witness both.",
    },
}
R1 = {**BRACKET_ORIGINAL, "case": "r1", "read_only": {"part": True, "drawing": False},
      "changed_factor": "IView.Angle", "baseline_angle": math.pi / 2, "baseline_cut_only": True,
      "requested_angle": 0.0, "requested_cut_only": True}
C1 = {**BRACKET_ORIGINAL, "case": "c1", "read_only": {"part": True, "drawing": False},
      "changed_factor": "IDrSection.SetDisplayOnlySurfaceCut", "baseline_angle": math.pi / 2,
      "baseline_cut_only": True, "requested_angle": math.pi / 2, "requested_cut_only": False}
# Exact observed UI-node roles, not a universal SDK persistent-ID exemption.
DESCRIPTIVE_TREE_TYPES = frozenset({
    "HistoryFolder", "SelectionSetFolder", "SensorFolder",
    "EnvFolder", "InkMarkupFolder", "MaterialFolder",
})
CONTRACT = {
    "schema": 5,
    "protocol": {
        "order": "SM positive once; independent fresh-original R1 then C1; no S1/source access",
        "mutators": "R1 IView.Angle=0 only; C1 IDrSection.SetDisplayOnlySurfaceCut(False) only",
        "baseline": "Each fresh bracket pair independently requires Angle=pi/2, cutOnly=True and complete observed zero",
        "cleanup": "Only exact owned writable R1/C1 drawing copies may be dirty; every part stays readonly and clean; full inventory and actual UserControl=True before each close",
        "admission": "SM probe-local strict native collector requires complete typed witnesses/counts/every payload plus genuine finite positive geometry; first reader BaseException retained; exact zero open errors/warnings",
        "copy_paths": "Strict unaliased canonical same-basename copies under a unique per-case directory",
        "evidence": "Before/write-readback/pre-generation/post-generation independent channels, actual transforms, native physical circles and declared major diameter; geometry correspondence is not native ownership",
        "tree_metadata_types": sorted(DESCRIPTIVE_TREE_TYPES),
        "failure": "First BaseException retained; independent reader errors never become zero; no retry/repair",
        "display_frame": "XYZ coordinate-frame authority unavailable; native projection and angle-normalized radius deltas are candidates only",
        "images": "Extracted nondegenerate primitives request fresh per-case/stage desktop PNG via existing pixel-only helper; unaliased trusted output/report ancestry certified before capture/hash; no native/PDF save",
        "limitations": "No automatic SHIP, source/display identity invention, global telemetry or hard-crash cleanup guarantee",
    },
    "cases": [SM_POSITIVE, R1, C1],
}
MISSING = object()

WIZARD_PROPERTIES = {
    "CosmeticThreadType": int, "ThreadEndCondition": int, "ThreadClass": str,
    "Type": int, "FastenerSize": str, "EndCondition": int, "HoleDepth": float,
    "ThreadDepth": float, "TapDrillDepth": float, "ThruTapDrillDepth": float,
    "ThreadDiameter": float, "TapDrillDiameter": float, "ThruTapDrillDiameter": float,
}
COSMETIC_PROPERTIES = {
    "ApplyThread": int, "BlindDepth": float, "Diameter": float,
    "DiameterType": int, "EndCondition": int,
}
DEFINITION_INTERFACES = {"HoleWzd": "IWizardHoleFeatureData2", "CosmeticThread": "ICosmeticThreadFeatureData"}
THREAD_ENUM_NAMESPACES = {
    "ICosmeticThreadFeatureData": {
        "ApplyThread": "swCosmeticThreadType_e", "EndCondition": "swCosmeticEndConditions_e",
        "DiameterType": "swCosmeticThreadDiameterType_e",
    },
    "IWizardHoleFeatureData2": {
        "CosmeticThreadType": "swWzdHoleCosmeticThreadTypes_e",
        "ThreadEndCondition": "swWzdHoleThreadEndCondition_e", "EndCondition": "swEndConditions_e",
    },
}


def native_scalar(value, expected):
    require(type(value) is expected or (expected is float and type(value) is int),
            "native scalar has unexpected type")
    require(expected is not float or math.isfinite(value), "native scalar is not finite")
    return value


def definition_scalars(definition, interface, read, label):
    properties = WIZARD_PROPERTIES if interface == "IWizardHoleFeatureData2" else COSMETIC_PROPERTIES
    values = {}
    for name, expected in properties.items():
        value = read(f"{label}.{name}", lambda name=name, expected=expected:
                     native_scalar(getattr(definition, name), expected))
        if value is not MISSING:
            values[name] = value
    return values


def descriptive_tree_container(row):
    return (
        row.get("type") in DESCRIPTIVE_TREE_TYPES
        and type(row.get("name")) is str and bool(row["name"])
        and "parent_inventory_index" in row and row["parent_inventory_index"] is None
        and type(row.get("rolled_back")) is bool
        and row.get("non_root_occurrence", False) is False
        and row.get("definition_state") == "NULL_UNSUPPORTED"
        and row.get("face_state") == "NULL" and row.get("owner_state") == "NULL"
    )


def require_reference_identity(status, resolved_present, native_same, feature=None):
    """Only an eligible UI container has optional PID quality; core never does."""
    proven = type(status) is int and status == 0 and resolved_present is True and type(native_same) is int and native_same == 1
    if feature is None or not descriptive_tree_container(feature):
        require(proven, "persistent identity unavailable or differs")
    return proven


def feature_tree(part, bind, same, read, label):
    """Bounded native traversal shared by S1 and the scalar-only SM census."""
    items, occurrences = [], []
    def walk(raw, parent=None, ancestors=()):
        chain = []
        while raw is not None and raw is not MISSING:
            require(len(ancestors) < 32 and len(items) < 512 and len(occurrences) < 2048,
                    "bounded feature inventory exhausted")
            feature = bind(raw, "IFeature")
            require(feature is not None, "feature binding unavailable")
            require(not any(same(feature, previous, f"{label}.cursor_cycle") for previous in chain),
                    "cyclic feature cursor")
            require(not any(same(feature, ancestor, f"{label}.ancestor_cycle") for ancestor in ancestors),
                    "cyclic subfeature ancestry")
            chain.append(feature)
            matches = [index for index, item in enumerate(items)
                       if same(feature, item["native"], f"{label}.deduplicate")]
            require(len(matches) <= 1, "ambiguous feature inventory")
            index = matches[0] if matches else len(items)
            occurrences.append({"index": index, "parent_inventory_index": parent})
            if not matches:
                items.append({"native": feature, "parent_inventory_index": parent})
                child = read(f"{label}.feature[{index}].first_subfeature",
                             lambda: feature.GetFirstSubFeature(), opaque=True)
                walk(child, index, ancestors + (feature,))
            raw = read(f"{label}.next[{len(occurrences)}]",
                       lambda: feature.GetNextFeature() if parent is None else feature.GetNextSubFeature(), opaque=True)
    read(f"{label}.traversal", lambda: walk(part.FirstFeature()))
    return items, occurrences


def structural_tree(features, occurrences):
    """Descriptive structure, deliberately NOT native or persistent identity."""
    paths = []
    for index, row in enumerate(features):
        require(type(row.get("index")) is int and row["index"] == index, "feature inventory index unavailable")
        require(all(type(row.get(key)) is str and row[key] for key in ("name", "type")),
                "feature tree name/type unavailable")
        require("parent_inventory_index" in row, "feature tree parent unavailable")
        parent = row["parent_inventory_index"]
        require(parent is None or (type(parent) is int and 0 <= parent < index), "invalid feature tree parent")
        path = (() if parent is None else paths[parent]) + ((row["type"], row["name"]),)
        require(path not in paths, "ambiguous descriptive feature tree path")
        paths.append(path)
    links = []
    for occurrence in occurrences:
        index, parent = occurrence.get("index"), occurrence.get("parent_inventory_index", MISSING)
        require(type(index) is int and 0 <= index < len(paths), "tree occurrence feature unavailable")
        require(parent is None or (type(parent) is int and 0 <= parent < len(paths) and parent != index),
                "tree occurrence parent unavailable")
        links.append((paths[index], () if parent is None else paths[parent]))
    require({row["index"] for row in occurrences} == set(range(len(features))), "tree occurrence coverage incomplete")
    return {"paths": paths, "relationships": sorted(links), "identity_role": "DESCRIPTIVE_ONLY"}


def passive_sm_thread_metadata(part, intended_name, bind, same, failure):
    """Readonly scalar census only: no access/Edge/activation/physical inventory."""
    result = {"state": "UNAVAILABLE", "reads": {}, "errors": [], "features": [],
              "cosmetic_children": [], "causal_conclusion": "NOT_ESTABLISHED"}
    result["enum_namespaces"] = THREAD_ENUM_NAMESPACES
    def read(label, reader, *, opaque=False):
        try:
            value = reader()
            result["reads"][label] = {"present": value is not None} if opaque else value
            return value
        except BaseException as error:
            result["errors"].append(failure(f"sm_source.{label}", error))
            return MISSING
    items, occurrences = feature_tree(part, bind, same, read, "tree")
    for index, item in enumerate(items):
        feature = item["native"]
        row = {"index": index, "parent_inventory_index": item["parent_inventory_index"]}
        item["row"] = row
        result["features"].append(row)
        for key, reader in (("name", lambda: native_scalar(feature.Name, str)),
                            ("type", lambda: native_scalar(feature.GetTypeName2(), str))):
            value = read(f"feature[{index}].{key}", reader)
            if value is not MISSING:
                row[key] = value
    result["tree"] = read("tree.structure", lambda: structural_tree(result["features"], occurrences))
    if result["tree"] is MISSING:
        result["tree"] = None
    targets = [item for item in items if item["row"].get("name") == intended_name and item["row"].get("type") == "HoleWzd"]
    if read("wizard.unique", lambda: require(len(targets) == 1, "SM intended Wizard unavailable or ambiguous")) is MISSING:
        return result
    wizard = targets[0]
    extension = read("part.extension", lambda: bind(part.Extension, "IModelDocExtension"), opaque=True)
    def collect_definition(item):
        feature, row = item["native"], item["row"]
        label = f"feature[{row['index']}]"
        def identity():
            require(extension is not None and extension is not MISSING, "SM part extension unavailable")
            reference = extension.GetPersistReference3(feature)
            require(reference is not None, "SM feature reference null")
            values = list(reference)
            require(values and all(type(value) is int and 0 <= value <= 255 for value in values),
                    "SM feature reference unavailable")
            result["reads"][f"{label}.reference.bytes"] = values
            pair = extension.GetObjectByPersistReference3(reference)
            require(isinstance(pair, tuple) and len(pair) == 2, "SM resolution OUT status missing")
            resolved, status = pair
            result["reads"][f"{label}.reference.status"] = status
            result["reads"][f"{label}.reference.resolved_present"] = resolved is not None
            result["reads"][f"{label}.reference.resolved_type_state"] = "UNAVAILABLE_NOT_READ"
            require(type(status) is int and status == 0 and resolved is not None, "SM feature resolution unavailable")
            require(same(resolved, feature, f"sm_source.{label}.reference"), "SM feature persistent identity differs")
        read(f"{label}.identity", identity)
        raw = read(f"{label}.definition", lambda: feature.GetDefinition(), opaque=True)
        row["definition_state"] = "UNAVAILABLE" if raw is MISSING else "NULL_UNSUPPORTED" if raw is None else "PRESENT"
        interface = DEFINITION_INTERFACES[row["type"]]
        row["definition_interface"] = interface
        def typed_definition():
            require(raw is not None and raw is not MISSING, "SM typed definition unavailable")
            value = bind(raw, interface)
            require(value is not None, "SM typed definition null")
            return value
        definition = read(f"{label}.typed_definition", typed_definition, opaque=True)
        row["scalars"] = {} if definition is MISSING else definition_scalars(definition, interface, read, label)
        return row
    result["wizard"] = collect_definition(wizard)
    wizard_index = wizard["row"]["index"]
    descendants = {wizard_index}
    for _ in items:
        expanded = descendants | {link["index"] for link in occurrences if link["parent_inventory_index"] in descendants}
        if expanded == descendants:
            break
        descendants = expanded
    for item in items:
        row = item["row"]
        if row.get("type") != "CosmeticThread":
            continue
        owner = read(f"feature[{row['index']}].owner", lambda item=item: item["native"].GetOwnerFeature(), opaque=True)
        row["owner_state"] = "UNAVAILABLE" if owner is MISSING else "NULL" if owner is None else "PRESENT"
        associated = MISSING if owner is MISSING else read(
            f"feature[{row['index']}].wizard_owner",
            lambda: owner is not None and same(owner, wizard["native"], "sm_source.wizard_owner"))
        row["wizard_owner_state"] = "UNAVAILABLE" if associated is MISSING else "SAME" if associated else "DIFFERENT"
        if associated is False and row["index"] not in descendants:
            continue  # Observed unrelated cosmetic; no arbitrary pairing.
        read(f"feature[{row['index']}].owner_proof",
             lambda: require(associated is True, "SM cosmetic child/owner association incomplete"))
        result["cosmetic_children"].append(collect_definition(item))
    if not result["errors"]:
        result["state"] = "OBSERVED"
        result["cosmetic_child_count"] = len(result["cosmetic_children"])
    return result


def file_identity(path):
    with path.open("rb") as stream:
        size = os.fstat(stream.fileno()).st_size
        sha256 = hashlib.file_digest(stream, "sha256").hexdigest()
    return {"bytes": size, "sha256": sha256}


def canonical(path):
    return os.path.normcase(str(Path(path).resolve())) if path else ""


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def thread_ink_summary(diagnostic):
    """Classify actual recorded dictionaries, never coerce unknown counts to zero."""
    reads = diagnostic.get("reads", {}) if isinstance(diagnostic, dict) else {}
    errors = diagnostic.get("errors", MISSING) if isinstance(diagnostic, dict) else MISSING
    positive = [
        key for key, value in reads.items()
        if ".thread[" in key and any(f".{channel}." in key for channel in ("ICThread", "IAnnotation"))
        and key.endswith((".lines.count", ".polylines.count", ".arcs.count"))
        and type(value) is int and value > 0
    ]
    positive_payloads = []
    if isinstance(errors, dict):
        for count_key in positive:
            primitive_key = count_key.removesuffix(".count")
            for index in range(reads[count_key]):
                key = f"{primitive_key}[{index}]"
                payload = reads.get(key)
                if (key not in errors and isinstance(payload, (list, tuple)) and payload
                        and all(type(value) in (float, int) and math.isfinite(value) for value in payload)):
                    positive_payloads.append(key)
    missing = []
    for phase in ("before_generation", "after_generation"):
        witnesses = [f"{phase}.threads"]
        count = reads.get(f"{phase}.thread_count")
        if type(count) is not int or count <= 0:
            missing.append(f"{phase}.thread_count")
            continue
        for index in range(count):
            prefix = f"{phase}.thread[{index}]"
            witnesses.extend((prefix, f"{prefix}.annotation"))
            for channel in ("ICThread", "IAnnotation"):
                witnesses.append(f"{prefix}.{channel}.display")
                for primitive in ("lines", "polylines", "arcs"):
                    key = f"{prefix}.{channel}.{primitive}.count"
                    value = reads.get(key)
                    if type(value) is not int or value < 0:
                        missing.append(key)
        for key in witnesses:
            witness = reads.get(key)
            if not isinstance(witness, dict) or witness.get("present") is not True:
                missing.append(key)
    complete = not missing and isinstance(errors, dict) and not errors
    return {
        "state": "PRESENT" if positive else "OBSERVED_ZERO" if complete else "UNAVAILABLE",
        "complete": complete,
        "positive_count_fields": positive,
        "positive_payload_fields": positive_payloads,
        "missing_or_invalid_fields": missing,
        "reader_errors_present": not isinstance(errors, dict) or bool(errors),
        "recommendation": "STOP; inspect actual primitives; counts alone never establish recovered flank identity."
        if positive else "Complete observed zero primitives, not a causal diagnosis."
        if complete else "Missing witnesses or failed readers are unavailable, not zero.",
    }


def finite_values(value, size):
    require(isinstance(value, (tuple, list)) and len(value) == size, "unexpected native numeric array")
    require(all(type(item) in (float, int) and math.isfinite(item) for item in value),
            "nonfinite, Boolean, or unavailable native numeric value")
    return list(value)


def trimmed_circle_summary(reads):
    """Geometry classification only: never an entity-identity or ownership test."""
    needed = ("circle", "circle_parameters", "curve_domain", "UMinValue", "UMaxValue",
              "StartPoint", "EndPoint", "Sense", "evaluate_min", "evaluate_max")
    if any(key not in reads for key in needed):
        return {"state": "UNAVAILABLE"}
    try:
        circle = finite_values(reads["circle_parameters"], 7)
        domain = reads["curve_domain"]
        require(isinstance(domain, (list, tuple)) and len(domain) == 5, "curve domain OUT tuple missing")
        success, start, end, closed, periodic = domain
        require(success is True and type(closed) is bool and type(periodic) is bool,
                "curve domain success/flags unavailable")
        start, end, lo, hi = finite_values([start, end, reads["UMinValue"], reads["UMaxValue"]], 4)
        require(end > start and hi > lo and type(reads["Sense"]) is bool, "invalid parameter range or sense")
        native_start = finite_values(reads["StartPoint"], 3)
        native_end = finite_values(reads["EndPoint"], 3)
        evaluated = [finite_values(reads[key], 4) for key in ("evaluate_min", "evaluate_max")]
        status = [struct.unpack("<II", struct.pack("<d", row[3]))[0] for row in evaluated]
        require(status == [1, 1], "edge evaluation packed success status unavailable")
        require(reads["circle"] is True and circle[6] > 0, "not a positive-radius circle")
        period, span = end - start, hi - lo
        endpoint_gap = max(math.dist(native_start, native_end),
                           math.dist(evaluated[0][:3], evaluated[1][:3]))
        # Sense may reverse endpoint ordering. Require both possible pairings to
        # be considered, never manufacture endpoint agreement from one point.
        correspondence = min(
            max(math.dist(native_start, evaluated[0][:3]), math.dist(native_end, evaluated[1][:3])),
            max(math.dist(native_start, evaluated[1][:3]), math.dist(native_end, evaluated[0][:3])),
        )
        full = closed is True and periodic is True and math.isclose(span, period, rel_tol=1e-9, abs_tol=1e-9)
        full = full and endpoint_gap <= 1e-9 and correspondence <= 1e-9
        return {
            "state": "FULL_TRIMMED_CIRCLE" if full else "NOT_FULL_OR_CONTRADICTORY",
            "trim_span": span, "native_period": period, "span_minus_2pi": span - math.tau,
            "endpoint_gap_m": endpoint_gap, "endpoint_correspondence_m": correspondence,
            "evaluation_status": status, "diameter_m": 2 * circle[6],
        }
    except (RuntimeError, ValueError, TypeError, OverflowError, struct.error) as error:
        return {"state": "UNAVAILABLE", "reason": str(error)}


def primitive_points(kind, values):
    """Decode only documented IDisplayData layouts, retaining raw arrays too."""
    require(isinstance(values, (list, tuple)) and values, "primitive payload unavailable")
    values = finite_values(values, len(values))
    if kind == "lines":
        require(len(values) == 10, "GetLineAtIndex2 layout differs")
        points = [values[4:7], values[7:10]]
        require(math.dist(*points) > 0, "degenerate line is not positive geometry")
        return points
    if kind == "arcs":
        require(len(values) == 17, "GetArcAtIndex2 layout differs")
        require(math.dist(values[4:7], values[10:13]) > 0, "degenerate arc radius")
        return [values[4:7], values[7:10], values[10:13]]
    require(kind == "polylines" and len(values) >= 7, "polyline header unavailable")
    count = values[6]
    require(float(count).is_integer() and count >= 2, "polyline point count unavailable")
    require(values[0] in (0, 1) and values[1] >= 0, "polyline geometry header unavailable")
    require(len(values) == 7 + 3 * int(count), "polyline coordinate layout differs")
    points = [values[index:index + 3] for index in range(7, len(values), 3)]
    require(any(math.dist(points[0], point) > 0 for point in points[1:]), "degenerate polyline")
    return points


def normalized_point(point, position, angle, scale):
    """Sheet metres -> rotation-normalized view-relative model metres."""
    x, y = point[0] - position[0], point[1] - position[1]
    return [(math.cos(angle) * x + math.sin(angle) * y) / scale,
            (-math.sin(angle) * x + math.cos(angle) * y) / scale, point[2] / scale]


def representation_state(view, base, part, drawing, cut, bind, read):
    state = {}
    for key, reader in (
        ("angle", lambda: native_scalar(view.Angle, float)),
        ("cut_only", lambda: native_scalar(cut.GetDisplayOnlySurfaceCut(), bool)),
        ("type", lambda: native_scalar(view.Type, int)),
        ("name", lambda: native_scalar(view.Name, str)),
        ("configuration", lambda: native_scalar(view.ReferencedConfiguration, str)),
        ("base_configuration", lambda: native_scalar(base.ReferencedConfiguration, str)),
        ("scale", lambda: native_scalar(view.ScaleDecimal, float)),
        ("position", lambda: finite_values(view.Position, 2)),
        ("broken", lambda: native_scalar(view.IsBroken(), bool)),
        ("mode", lambda: native_scalar(view.GetDisplayMode2(), int)),
        ("thread_quality", lambda: native_scalar(view.GetCThreadQuality(), bool)),
        ("use_parent_mode", lambda: native_scalar(view.GetUseParentDisplayMode(), bool)),
        ("faceted", lambda: native_scalar(view.GetFacettedHlrDisplay(), bool)),
    ):
        value = read(key, reader)
        if value is not MISSING:
            state[key] = value
    for key, reader in (
        ("base_angle", lambda: native_scalar(base.Angle, float)),
        ("base_scale", lambda: native_scalar(base.ScaleDecimal, float)),
        ("base_mode", lambda: native_scalar(base.GetDisplayMode2(), int)),
        ("base_thread_quality", lambda: native_scalar(base.GetCThreadQuality(), bool)),
        ("base_use_parent_mode", lambda: native_scalar(base.GetUseParentDisplayMode(), bool)),
        ("base_faceted", lambda: native_scalar(base.GetFacettedHlrDisplay(), bool)),
    ):
        value = read(key, reader)
        if value is not MISSING:
            state[key] = value
    for label, document in (("source", part), ("drawing", drawing)):
        for name, preference in (("annotations", 31), ("cosmetics", 41), ("high_quality", 257)):
            value = read(f"{label}.{name}", lambda document=document, preference=preference:
                         native_scalar(bind(document.Extension, "IModelDocExtension").GetUserPreferenceToggle(preference, 0), bool))
            if value is not MISSING:
                state[f"{label}.{name}"] = value
    return state


def capture_thread_stage(view, part, stage, diagnostic, bind, same, failure):
    """Actual strict counts and independent channel rows, without generation."""
    def read(key, reader, *, opaque=False):
        label = f"{stage}.{key}"
        try:
            value = reader()
            diagnostic["reads"][label] = {"present": value is not None} if opaque else value
            return value
        except BaseException as error:
            diagnostic["errors"][label] = failure(label, error)
            return MISSING
    def typed(raw, interface):
        require(raw is not None and raw is not MISSING, f"{interface} unavailable")
        result = bind(raw, interface)
        require(result is not None, f"{interface} null")
        return result
    threads = read("threads", lambda: view.GetCThreads(), opaque=True)
    if threads is MISSING:
        return
    if read("thread_array", lambda: require(isinstance(threads, (tuple, list)), "native CThread array unavailable")) is MISSING:
        return
    diagnostic["reads"][f"{stage}.thread_count"] = len(threads)
    for index, raw in enumerate(threads):
        prefix = f"thread[{index}]"
        thread = read(prefix, lambda: typed(raw, "ICThread"), opaque=True)
        if thread is MISSING:
            continue
        annotation = read(f"{prefix}.annotation", lambda: typed(thread.GetAnnotation(), "IAnnotation"), opaque=True)
        if annotation is not MISSING:
            read(f"{prefix}.visible", lambda: native_scalar(annotation.Visible, int))
            read(f"{prefix}.dangling", lambda: native_scalar(annotation.IsDangling(), bool))
            read(f"{prefix}.layer", lambda: native_scalar(annotation.Layer, str))
            read(f"{prefix}.attachment_types", annotation.GetAttachedEntityTypes)
            attachments = read(f"{prefix}.attachments", lambda: annotation.GetAttachedEntities3(), opaque=True)
            if attachments is not MISSING and attachments is not None:
                if read(f"{prefix}.attachment_array", lambda: require(isinstance(attachments, (tuple, list)),
                                                                     "attachment array unavailable")) is not MISSING:
                    diagnostic["reads"][f"{stage}.{prefix}.attachment_count"] = len(attachments)
                    for number, attachment in enumerate(attachments):
                        label = f"{prefix}.attachment[{number}]"
                        extension = read(label + ".extension", lambda: typed(part.Extension, "IModelDocExtension"), opaque=True)
                        canonical_entity = (read(label + ".canonical", lambda: extension.GetCorrespondingEntity2(attachment), opaque=True)
                                            if extension is not MISSING else MISSING)
                        if canonical_entity is not MISSING and canonical_entity is not None:
                            def reference_proof():
                                reference = extension.GetPersistReference3(canonical_entity)
                                require(reference is not None, "canonical attachment reference null")
                                values = list(reference)
                                require(values and all(type(x) is int and 0 <= x <= 255 for x in values),
                                        "canonical attachment reference unavailable")
                                diagnostic["reads"][f"{stage}.{label}.reference"] = values
                                pair = extension.GetObjectByPersistReference3(reference)
                                require(isinstance(pair, tuple) and len(pair) == 2, "attachment resolution OUT missing")
                                resolved, status = pair
                                diagnostic["reads"][f"{stage}.{label}.status"] = status
                                require(type(status) is int and status == 0 and resolved is not None,
                                        "attachment not resolved in this PART")
                                require(same(resolved, canonical_entity, f"{stage}.{label}.identity"), "attachment identity differs")
                            read(label + ".source_context_proof", reference_proof)
                        # NULL correspondence is an actual unavailable native
                        # source bridge, never a fabricated selected-edge ID.
        for channel, owner in (("ICThread", thread), ("IAnnotation", annotation)):
            if owner is MISSING:
                continue
            label = f"{prefix}.{channel}"
            display = read(label + ".display", lambda: typed(owner.GetDisplayData(), "IDisplayData"), opaque=True)
            if display is MISSING:
                continue
            for kind, count_reader, row_reader in (
                ("lines", display.GetLineCount, display.GetLineAtIndex2),
                ("polylines", display.GetPolyLineCount, display.GetPolylineAtIndex2),
                ("arcs", display.GetArcCount, display.GetArcAtIndex2),
            ):
                count = read(f"{label}.{kind}.count", count_reader)
                if read(f"{label}.{kind}.count_contract",
                        lambda: require(type(count) is int and 0 <= count <= 100000, "primitive count unavailable/invalid")) is MISSING:
                    continue
                for number in range(count):
                    key = f"{label}.{kind}[{number}]"
                    def payload():
                        value = row_reader(number)
                        require(isinstance(value, (list, tuple)) and value, "primitive payload unavailable")
                        return finite_values(value, len(value))
                    raw_values = read(key, payload)
                    if raw_values is not MISSING:
                        read(key + ".points", lambda: primitive_points(kind, raw_values))


def project_thread_geometry(app, view, state, source_snapshot, wizard, cosmetic, diagnostic, bind, double_array):
    """Native projection plus explicitly non-authoritative geometric candidates."""
    require(state["broken"] is False and state["scale"] > 0, "broken/nonpositive view projection unavailable")
    transform = bind(view.ModelToViewTransform, "IMathTransform")
    require(transform is not None, "model-to-view transform unavailable")
    matrix = finite_values(transform.ArrayData, 16)
    utility = bind(app.GetMathUtility(), "IMathUtility")
    require(utility is not None, "native math utility unavailable")
    def project(point):
        model = bind(utility.CreatePoint(double_array(point)), "IMathPoint")
        require(model is not None, "native point unavailable")
        created = finite_values(model.ArrayData, 3)
        require(math.dist(created, point) <= 1e-12, "native double-array marshaling changed point")
        projected = bind(model.MultiplyTransform(transform), "IMathPoint")
        require(projected is not None, "native point transform unavailable")
        sheet = finite_values(projected.ArrayData, 3)
        return {"model": list(point), "sheet": sheet,
                "normalized": normalized_point(sheet, state["position"], state["angle"], state["scale"])}
    output = {"transform": matrix, "angle": state["angle"], "position": state["position"], "scale": state["scale"],
              "circles": [], "primitives": [], "source_display_native_identity": "UNAVAILABLE_NO_INVENTED_BRIDGE",
              "coordinate_frame_authority": "UNAVAILABLE_IDisplayData_DOCS_SPECIFY_XYZ_NOT_FRAME",
              "normalization_assumption": "Display XYZ provisionally treated in same drawing-view frame as native projection; not certified",
              "role": "GEOMETRY_CORRESPONDENCE_ONLY_NOT_FLANK_IDENTITY_OR_SHIP"}
    major = native_scalar(cosmetic["scalars"]["Diameter"], float)
    require(cosmetic["scalars"]["DiameterType"] == 2 and major > 0, "native major diameter unavailable")
    for edge in source_snapshot["edges"]:
        if edge["trimmed_circle"]["state"] != "FULL_TRIMMED_CIRCLE":
            continue
        if not any(wizard["index"] in face["feature_memberships"] for face in edge["adjacent_faces"]):
            continue
        params = finite_values(edge["reads"]["circle_parameters"], 7)
        center, axis, radius = params[:3], params[3:6], params[6]
        length = math.sqrt(sum(x*x for x in axis))
        require(length > 0, "circle axis unavailable")
        axis = [x/length for x in axis]
        basis = min(([1.,0.,0.], [0.,1.,0.], [0.,0.,1.]), key=lambda v: abs(sum(a*b for a,b in zip(axis,v))))
        u = [axis[1]*basis[2]-axis[2]*basis[1], axis[2]*basis[0]-axis[0]*basis[2], axis[0]*basis[1]-axis[1]*basis[0]]
        length = math.sqrt(sum(x*x for x in u)); u = [x/length for x in u]
        v = [axis[1]*u[2]-axis[2]*u[1], axis[2]*u[0]-axis[0]*u[2], axis[0]*u[1]-axis[1]*u[0]]
        row = {"edge_index": edge["index"], "body_source_matches": edge["body_source_matches"],
               "adjacent_faces": edge["adjacent_faces"], "native_circle": params,
               "trimmed_circle": edge["trimmed_circle"], "center": project(center),
               "axis_point": project([center[i]+axis[i] for i in range(3)]),
               "major_diameter_m": major, "major_role": "NATIVE_DEFINITION_NOT_PHYSICAL_EDGE",
               "drill_diameter_m": 2*radius, "drill_samples": [], "major_samples": []}
        for name, r in (("drill_samples", radius), ("major_samples", major/2)):
            row[name] = [project([center[j]+r*(math.cos(t)*u[j]+math.sin(t)*v[j]) for j in range(3)])
                         for t in (0., math.pi/2, math.pi, 3*math.pi/2)]
        output["circles"].append(row)
    require(output["circles"], "no native full-circle Wizard-owned physical evidence")
    for key, points in diagnostic["reads"].items():
        if not key.endswith(".points"):
            continue
        normalized = [normalized_point(p, state["position"], state["angle"], state["scale"]) for p in points]
        row = {"payload": key.removesuffix(".points"), "sheet_points": points, "normalized_points": normalized,
               "circle_correspondence": []}
        # Compare axis-normal offsets, not axis-aligned screen distances:
        # rotation cannot make an unrelated line appear at the major radius.
        for circle in output["circles"]:
            c = circle["center"]["normalized"]; a = circle["axis_point"]["normalized"]
            dx,dy = a[0]-c[0], a[1]-c[1]; norm = math.hypot(dx,dy)
            if norm <= 1e-9:
                row["circle_correspondence"].append({"edge_index":circle["edge_index"], "state":"AXIS_PROJECTION_DEGENERATE"})
                continue
            distances = [abs((p[0]-c[0])*(-dy/norm)+(p[1]-c[1])*(dx/norm)) for p in normalized]
            row["circle_correspondence"].append({
                "edge_index":circle["edge_index"], "axis_normal_distances_m":distances,
                "major_radius_deltas_m":[d-circle["major_diameter_m"]/2 for d in distances],
                "drill_radius_deltas_m":[d-circle["drill_diameter_m"]/2 for d in distances],
                "state":"MEASURED_NOT_NATIVE_ASSOCIATION"})
        output["primitives"].append(row)
    return output


def source_observations(part, intended_name, bind, same, failure, observe_representation):
    """Readonly physical evidence around one drawing-only intervention."""
    result = {"state": "UNAVAILABLE", "reads": {}, "errors": [], "phases": {},
              "clean_comparison": False, "causal_conclusion": "NOT_ESTABLISHED",
              "reference_observations": {}}
    body_references = {}
    result["enum_namespaces"] = THREAD_ENUM_NAMESPACES

    def read(label, reader, *, opaque=False):
        try:
            value = reader()
            result["reads"][label] = {"present": value is not None} if opaque else value
            return value
        except BaseException as error:
            row = failure(f"source.{label}", error)
            result["errors"].append(row)
            return MISSING

    def typed(raw, interface):
        require(raw is not None and raw is not MISSING, f"{interface} unavailable")
        value = bind(raw, interface)
        require(value is not None, f"{interface} null")
        return value


    extension = read("part.extension", lambda: typed(part.Extension, "IModelDocExtension"), opaque=True)
    if extension is MISSING:
        return result

    def resolve(reference, label):
        pair = extension.GetObjectByPersistReference3(reference)
        require(isinstance(pair, tuple) and len(pair) == 2, "persistent resolution OUT status missing")
        entity, status = pair
        result["reads"][f"{label}.status"] = status
        result["reads"][f"{label}.resolved_present"] = entity is not None
        require(type(status) is int and status == 0 and entity is not None,
                "persistent object unresolved in owned part context")
        return entity

    def persistent(entity, label, feature=None):
        descriptive = feature is not None and descriptive_tree_container(feature)
        observation = {"required": not descriptive, "state": "UNAVAILABLE",
                       "native_identity_claim": False, "resolved_type_state": "UNAVAILABLE_NOT_READ",
                       "role": "DESCRIPTIVE_TREE" if descriptive else "STRICT"}
        result["reference_observations"][label] = observation
        def collect():
            reference = extension.GetPersistReference3(entity)
            require(reference is not None, "persistent reference is null")
            values = list(reference)
            require(values and all(type(item) is int and 0 <= item <= 255 for item in values),
                    "persistent reference is not a nonempty byte array")
            result["reads"][f"{label}.bytes"] = values
            observation["bytes"] = values
            try:
                resolved = resolve(reference, label)
            finally:
                for key in ("status", "resolved_present"):
                    if f"{label}.{key}" in result["reads"]:
                        observation[key] = result["reads"][f"{label}.{key}"]
            equal = same(resolved, entity, f"source.{label}.resolved_identity")
            observation["native_same"] = 1 if equal else 0
            result["reads"][f"{label}.native_same"] = observation["native_same"]
            observation["state"] = "SAME" if equal else "DIFFERENT"
            proven = require_reference_identity(observation["status"], True, observation["native_same"], feature)
            observation["native_identity_claim"] = proven and not descriptive
            return reference
        if not descriptive:
            return read(label, collect, opaque=True)
        try:
            collect()
        except Exception as error:
            try:
                message = str(error)
            except BaseException:
                message = "<exception text unavailable>"
            observation["error"] = {"type": type(error).__name__, "message": message,
                                    "traceback_available": error.__traceback__ is not None}
            frames, tb = [], error.__traceback__
            while tb is not None:
                frames.append({"file": tb.tb_frame.f_code.co_filename,
                               "function": tb.tb_frame.f_code.co_name, "line": tb.tb_lineno})
                tb = tb.tb_next
            observation["error"]["traceback_frames"] = frames
        return MISSING  # Never reuse a descriptive node's token as authority.

    def geometry(edge, label):
        error_start = len(result["errors"])
        values = {}
        curve = read(f"{label}.curve", lambda: typed(edge.GetCurve(), "ICurve"), opaque=True)
        if curve is not MISSING:
            for key, reader in (
                ("circle", lambda: native_scalar(curve.IsCircle(), bool)),
                ("circle_parameters", lambda: finite_values(curve.CircleParams, 7)),
                ("curve_domain", lambda: curve.GetEndParams()),
            ):
                # CircleParams is defined only for an underlying circle.
                if key == "circle_parameters" and values.get("circle") is not True:
                    continue
                value = read(f"{label}.{key}", reader)
                if value is not MISSING:
                    values[key] = value
            if "curve_domain" in values:
                def validate_domain():
                    domain = values["curve_domain"]
                    require(isinstance(domain, (tuple, list)) and len(domain) == 5,
                            "curve domain OUT tuple missing")
                    success, start, end, closed, periodic = domain
                    require(success is True and type(closed) is bool and type(periodic) is bool,
                            "curve domain operation failed or flags unavailable")
                    finite_values([start, end], 2)
                read(f"{label}.curve_domain.operation", validate_domain)
            params = read(f"{label}.trim", lambda: typed(edge.GetCurveParams3(), "ICurveParamData"), opaque=True)
            if params is not MISSING:
                for key, expected in (("UMinValue", float), ("UMaxValue", float), ("Sense", bool)):
                    value = read(f"{label}.{key}", lambda key=key, expected=expected: native_scalar(getattr(params, key), expected))
                    if value is not MISSING:
                        values[key] = value
                for key in ("StartPoint", "EndPoint"):
                    value = read(f"{label}.{key}", lambda key=key: finite_values(getattr(params, key), 3))
                    if value is not MISSING:
                        values[key] = value
                for key, parameter in (("evaluate_min", "UMinValue"), ("evaluate_max", "UMaxValue")):
                    if parameter in values:
                        value = read(f"{label}.{key}", lambda parameter=parameter: finite_values(edge.Evaluate2(values[parameter], 0), 4))
                        if value is not MISSING:
                            values[key] = value
                            read(f"{label}.{key}.operation", lambda value=value: require(
                                struct.unpack("<II", struct.pack("<d", value[3]))[0] == 1,
                                "edge evaluation packed success status unavailable",
                            ))
        return {"reads": values, "operations_complete": len(result["errors"]) == error_start,
                "trimmed_circle": trimmed_circle_summary(values)}

    def capture(phase):
        error_start = len(result["errors"])
        snapshot = {"features": [], "edges": [], "complete": False, "tree_complete": False,
                    "core_identity_complete": False, "all_pid_identity_claim": False}
        result["phases"][phase] = snapshot
        tree_errors = []
        def tree_read(label, reader, *, opaque=False):
            value = read(label, reader, opaque=opaque)
            if value is MISSING:
                tree_errors.append(label)
            return value
        features, occurrences = feature_tree(part, bind, same, tree_read, phase)
        snapshot["tree_occurrences"] = occurrences
        edges = []
        for index, item in enumerate(features):
            feature = item["native"]
            label = f"{phase}.feature[{index}]"
            row = {"index": index, "parent_inventory_index": item["parent_inventory_index"],
                   "definition_state": "UNAVAILABLE", "scalars": {}, "face_state": "UNAVAILABLE"}
            row["non_root_occurrence"] = any(link["index"] == index and link["parent_inventory_index"] is not None
                                             for link in occurrences)
            snapshot["features"].append(row)
            item.update(row=row, definition=MISSING, reference=MISSING, faces=[], owner=MISSING)
            for key, reader in (
                ("name", lambda: native_scalar(feature.Name, str)),
                ("type", lambda: native_scalar(feature.GetTypeName2(), str)),
                ("rolled_back", lambda: native_scalar(feature.IsRolledBack(), bool)),
            ):
                value = tree_read(f"{label}.{key}", reader)
                if value is not MISSING:
                    row[key] = value
            item["owner"] = tree_read(f"{label}.owner", lambda: feature.GetOwnerFeature(), opaque=True)
            row["owner_state"] = "UNAVAILABLE" if item["owner"] is MISSING else "NULL" if item["owner"] is None else "PRESENT"
            raw_definition = tree_read(f"{label}.definition", lambda: feature.GetDefinition(), opaque=True)
            row["definition_state"] = "UNAVAILABLE" if raw_definition is MISSING else "NULL_UNSUPPORTED" if raw_definition is None else "PRESENT"
            interface = DEFINITION_INTERFACES.get(row.get("type"))
            if interface and raw_definition is not None and raw_definition is not MISSING:
                definition = tree_read(f"{label}.typed_definition", lambda: typed(raw_definition, interface), opaque=True)
                item["definition"] = definition
                row["definition_interface"] = interface
                if definition is not MISSING:
                    row["scalars"] = definition_scalars(definition, interface, tree_read, label)
        structure = tree_read(f"{phase}.tree.structure", lambda: structural_tree(snapshot["features"], occurrences))
        snapshot["tree_structure"] = None if structure is MISSING else structure
        # Preserve owner identities and every independent physical feature-face
        # membership. GetFeature gives oldest owner, not exclusive ownership.
        for item in features:
            row, feature = item["row"], item["native"]
            label = f"{phase}.feature[{row['index']}]"
            owner = item["owner"]
            if owner is not MISSING and owner is not None:
                row["owner_inventory_matches"] = []
                for other in features:
                    value = tree_read(f"{label}.owner_vs[{other['row']['index']}]",
                                 lambda other=other: same(owner, other["native"], f"source.{label}.owner"))
                    if value is True:
                        row["owner_inventory_matches"].append(other["row"]["index"])
                tree_read(f"{label}.owner_inventory_complete",
                     lambda: require(len(row["owner_inventory_matches"]) == 1,
                                     "nonnull feature owner not uniquely in source inventory"))
            faces = tree_read(f"{label}.faces", lambda: feature.GetFaces(), opaque=True)
            if faces is not MISSING:
                row["face_state"] = "NULL" if faces is None else "PRESENT"
                if faces is not None:
                    def collect_faces():
                        require(isinstance(faces, (tuple, list)), "feature faces not an array")
                        item["faces"] = [typed(face, "IFace2") for face in faces]
                    tree_read(f"{label}.face_array", collect_faces)
            row["identity_role"] = "DESCRIPTIVE_TREE" if descriptive_tree_container(row) else "STRICT"
            item["reference"] = persistent(feature, f"{label}.reference", row)
            for face_index, face in enumerate(item["faces"]):
                raw_edges = read(f"{label}.face[{face_index}].edges", lambda face=face: face.GetEdges(), opaque=True)
                if raw_edges is MISSING or raw_edges is None:
                    continue
                def collect_edges():
                    require(isinstance(raw_edges, (tuple, list)), "face edges not an array")
                    for raw_edge in raw_edges:
                        edge = typed(raw_edge, "IEdge")
                        if not any(same(edge, existing["native"], f"source.{phase}.edge_deduplicate") for existing in edges):
                            edge_label = f"{phase}.edge[{len(edges)}]"
                            edge_row = {"index": len(edges)}
                            snapshot["edges"].append(edge_row)
                            edges.append({"native": edge, "row": edge_row,
                                          "reference": persistent(edge, f"{edge_label}.reference")})
                read(f"{label}.face[{face_index}].edge_array", collect_edges)
        for item in features:
            owners = item["row"].get("owner_inventory_matches", [])
            if len(owners) == 1 and features[owners[0]]["row"]["identity_role"] == "DESCRIPTIVE_TREE":
                tree_read(f"{phase}.feature[{item['row']['index']}].core_owner",
                          lambda item=item: require(item["row"].get("type") in ("AmbientLight", "DirectionLight"),
                                                    "modeling feature owner cannot use descriptive-only identity"))
        bodies = read(f"{phase}.bodies", lambda: typed(part, "IPartDoc").GetBodies2(-1, False), opaque=True)
        if bodies is not MISSING:
            read(f"{phase}.body_array", lambda: require(isinstance(bodies, (tuple, list)) and len(bodies) > 0,
                                                       "owned part body inventory unavailable"))
        for item in edges:
            item["row"].update(edge_evidence(item["native"], f"{phase}.edge[{item['row']['index']}]", features, bodies))
        snapshot["tree_complete"] = not tree_errors and structure is not MISSING and bool(features)
        snapshot["core_feature_count"] = sum(item["row"]["identity_role"] == "STRICT" for item in features)
        observations = [value for key, value in result["reference_observations"].items() if key.startswith(f"{phase}.")]
        required = [value for value in observations if value["required"]]
        snapshot["core_identity_complete"] = bool(required) and all(value["state"] == "SAME" for value in required)
        aliases = {}
        for item in features:
            values = result["reads"].get(f"{phase}.feature[{item['row']['index']}].reference.bytes")
            if values:
                aliases.setdefault(tuple(values), []).append(item["row"]["index"])
        snapshot["reference_aliases"] = [
            {"bytes": list(values), "feature_indices": indices, "role": "BYTE_ALIAS_NOT_IDENTITY"}
            for values, indices in aliases.items() if len(indices) > 1
        ]
        snapshot["complete"] = snapshot["tree_complete"] and snapshot["core_identity_complete"] and len(result["errors"]) == error_start
        snapshot["all_features_rolled_forward"] = snapshot["complete"] and all(
            item["row"].get("rolled_back") is False for item in features)
        return {"features": features, "edges": edges, "bodies": bodies, "snapshot": snapshot}

    def edge_evidence(edge, label, features, bodies):
        evidence = geometry(edge, label)
        body = read(f"{label}.body", lambda: edge.GetBody(), opaque=True)
        evidence["body_source_matches"] = []
        if body is not MISSING and body is not None and isinstance(bodies, (tuple, list)):
            for index, source_body in enumerate(bodies):
                value = read(f"{label}.body_vs[{index}]", lambda source_body=source_body: same(body, source_body, f"source.{label}.body"))
                if value is True:
                    evidence["body_source_matches"].append(index)
        evidence["owned_body_proven"] = len(evidence["body_source_matches"]) == 1
        read(f"{label}.owned_body", lambda: require(evidence["owned_body_proven"], "physical edge body not uniquely owned"))
        if body is not MISSING and body is not None:
            body_references[label] = persistent(body, f"{label}.body_reference")
        faces = read(f"{label}.adjacent_faces", lambda: edge.GetTwoAdjacentFaces2(), opaque=True)
        read(f"{label}.adjacent_array", lambda: require(isinstance(faces, (tuple, list)) and len(faces) == 2,
                                                       "native adjacent-face pair unavailable"))
        evidence["adjacent_faces"] = []
        if isinstance(faces, (tuple, list)):
            for index, raw_face in enumerate(faces):
                face_row = {"state": "NULL" if raw_face is None else "PRESENT", "feature_memberships": []}
                evidence["adjacent_faces"].append(face_row)
                if raw_face is None:
                    continue
                face = read(f"{label}.adjacent[{index}].bind", lambda: typed(raw_face, "IFace2"), opaque=True)
                if face is MISSING:
                    continue
                persistent(face, f"{label}.adjacent[{index}].reference")
                oldest = read(f"{label}.adjacent[{index}].oldest_owner", lambda: face.GetFeature(), opaque=True)
                face_row["oldest_owner_matches"] = []
                for feature in features:
                    feature_index = feature["row"]["index"]
                    if oldest is not MISSING and oldest is not None:
                        value = read(f"{label}.adjacent[{index}].oldest_vs[{feature_index}]",
                                     lambda feature=feature: same(oldest, feature["native"], f"source.{label}.oldest"))
                        if value is True:
                            face_row["oldest_owner_matches"].append(feature_index)
                            read(f"{label}.adjacent[{index}].oldest_core",
                                 lambda feature=feature: require(feature["row"].get("identity_role") != "DESCRIPTIVE_TREE",
                                                                 "physical face owner is a descriptive tree node"))
                    for owned_face in feature["faces"]:
                        value = read(f"{label}.adjacent[{index}].member[{feature_index},{len(face_row['feature_memberships'])}]",
                                     lambda owned_face=owned_face: same(face, owned_face, f"source.{label}.face_membership"))
                        if value is True:
                            face_row["feature_memberships"].append(feature_index)
                            break
        return evidence

    before = capture("before")
    if not before["snapshot"]["complete"] or not before["snapshot"]["all_features_rolled_forward"]:
        result["reason"] = "Incomplete source inventory or pre-existing rollback; no unique candidate established."
        return result
    cosmetics = [item for item in before["features"] if item["row"].get("type") == "CosmeticThread"]
    wizards = [item for item in before["features"] if item["row"].get("type") == "HoleWzd"
               and item["row"].get("name") == intended_name]
    result["cosmetic_candidate_count"] = len(cosmetics)
    result["intended_wizard_count"] = len(wizards)
    if len(cosmetics) != 1 or len(wizards) != 1 or any(
            item["definition"] is MISSING for item in cosmetics + wizards):
        result["reason"] = "Unique real cosmetic definition and intended native Wizard required; Wizard-only route unavailable."
        return result
    candidate, wizard = cosmetics[0], wizards[0]
    result["cosmetic_feature_inventory_index"] = candidate["row"]["index"]
    result["intended_wizard_inventory_index"] = wizard["row"]["index"]
    read("cosmetic.owner", lambda: require(candidate["row"].get("owner_inventory_matches") == [wizard["row"]["index"]],
                                           "cosmetic definition not natively owned by intended Wizard"))
    if not result["errors"]:
        read("drawing_intervention", lambda: observe_representation(before["snapshot"], wizard["row"], candidate["row"]))
    # Fresh source reads and same-PART persistent resolution even if a drawing
    # writer/reader failed. Never alter source or repair representation.
    after = capture("after")
    result["tree_structure_unchanged"] = (
        before["snapshot"]["tree_complete"] and after["snapshot"]["tree_complete"]
        and before["snapshot"]["tree_structure"] == after["snapshot"]["tree_structure"]
    )
    read("after.tree.stability", lambda: require(result["tree_structure_unchanged"],
                                                "complete descriptive tree structure changed or unavailable"))
    result["feature_identity_after"] = []
    for item in before["features"]:
        if item["reference"] is MISSING:
            continue
        def match_feature(item=item):
            restored = resolve(item["reference"], f"after.feature[{item['row']['index']}]")
            matches = [other for other in after["features"]
                       if same(restored, other["native"], "source.after.feature_inventory")]
            require(len(matches) == 1, "feature absent/ambiguous after drawing intervention")
            other = matches[0]
            owner_unchanged = item["owner"] is None and other["owner"] is None
            owner_role = "NATIVE"
            owner_relation_unchanged = owner_unchanged
            owner_indices = item["row"].get("owner_inventory_matches", [])
            if len(owner_indices) == 1 and other["owner"] is not None and other["owner"] is not MISSING:
                original_owner = before["features"][owner_indices[0]]
                if original_owner["row"]["identity_role"] == "DESCRIPTIVE_TREE":
                    owner_role = "DESCRIPTIVE_TREE"
                    require(item["row"].get("type") in ("AmbientLight", "DirectionLight"),
                            "modeling feature owner cannot use descriptive-only identity")
                    current_indices = other["row"].get("owner_inventory_matches", [])
                    require(len(current_indices) == 1, "live descriptive parent association unavailable")
                    current_owner = after["features"][current_indices[0]]
                    owner_unchanged = None
                    owner_relation_unchanged = (
                        result["tree_structure_unchanged"]
                        and current_owner["row"]["identity_role"] == "DESCRIPTIVE_TREE"
                        and before["snapshot"]["tree_structure"]["paths"][original_owner["row"]["index"]]
                        == after["snapshot"]["tree_structure"]["paths"][current_owner["row"]["index"]]
                    )
                else:
                    owner_unchanged = same(resolve(original_owner["reference"], "after.feature_owner"),
                                           other["owner"], "source.after.feature_owner")
                    owner_relation_unchanged = owner_unchanged
            result["feature_identity_after"].append({
                "before": item["row"]["index"], "after": other["row"]["index"],
                "scalars_unchanged": item["row"]["scalars"] == other["row"]["scalars"],
                "name_type_unchanged": all(item["row"].get(key) == other["row"].get(key) for key in ("name", "type")),
                "owner_unchanged": owner_unchanged,
                "owner_identity_role": owner_role, "owner_relation_unchanged": owner_relation_unchanged,
                "definition_state_unchanged": item["row"]["definition_state"] == other["row"]["definition_state"],
            })
        read(f"after.feature[{item['row']['index']}].identity", match_feature)
    result["geometry_identity_after"] = []
    feature_indices = {row["before"]: row["after"] for row in result["feature_identity_after"]}
    for item in before["edges"]:
        def match_edge(item=item):
            require(item["reference"] is not MISSING, "before edge identity unavailable")
            restored_edge = resolve(item["reference"], f"after.physical_edge[{item['row']['index']}]")
            matches = [other for other in after["edges"]
                       if same(restored_edge, other["native"], "source.after.physical_edge")]
            require(len(matches) == 1, "physical edge absent/ambiguous after drawing intervention")
            other = matches[0]
            old_body = body_references.get(f"before.edge[{item['row']['index']}]", MISSING)
            new_body = body_references.get(f"after.edge[{other['row']['index']}]", MISSING)
            require(old_body is not MISSING and new_body is not MISSING, "edge body persistence unavailable")
            body_same = same(resolve(old_body, "after.old_body"), resolve(new_body, "after.new_body"),
                             "source.after.body_identity")
            old_memberships = sorted(sorted(feature_indices.get(index, -1) for index in face["feature_memberships"])
                                     for face in item["row"]["adjacent_faces"])
            new_memberships = sorted(sorted(face["feature_memberships"]) for face in other["row"]["adjacent_faces"])
            result["geometry_identity_after"].append({
                "before": item["row"]["index"], "after": other["row"]["index"],
                "geometry_unchanged": item["row"]["reads"] == other["row"]["reads"],
                "body_same": body_same, "face_feature_memberships_unchanged": old_memberships == new_memberships,
            })
        read(f"after.physical_edge[{item['row']['index']}].comparison", match_edge)
    result["all_features_rolled_forward_after"] = after["snapshot"]["all_features_rolled_forward"]
    result["clean_comparison"] = (
        not result["errors"] and after["snapshot"]["complete"]
        and after["snapshot"]["all_features_rolled_forward"]
        and result["tree_structure_unchanged"]
        and before["snapshot"]["core_feature_count"] == after["snapshot"]["core_feature_count"] == len(result["feature_identity_after"])
        and all(row["scalars_unchanged"] and row["name_type_unchanged"]
                and row["owner_relation_unchanged"] and row["definition_state_unchanged"]
                for row in result["feature_identity_after"])
        and len(before["edges"]) == len(after["edges"]) == len(result["geometry_identity_after"])
        and all(row["geometry_unchanged"] and row["body_same"] and row["face_feature_memberships_unchanged"]
                for row in result["geometry_identity_after"])
    )
    result["state"] = "READONLY_SOURCE_UNCHANGED" if result["clean_comparison"] else "UNAVAILABLE"
    return result


def main():
    primary_exception = None
    primary_traceback = None
    report = {
        "kind": "mg-saved-thread-representation-r1-c1",
        "status": "running",
        "native_ship": "NOT_SHIP",
        "mode": "independent_drawing_copy_one_factor_no_save",
        "contract": CONTRACT,
        "cases": [],
        "session": {
            "scope": "Exactly three independent pairs in one attached callback; no reattach or cumulative copies.",
            "native_pid_evidence": "Existing owned runner attach witness; no additional native process calls.",
        },
        "reads": {},
        "errors": [],
        "primary_failure": None,
        "collection_completed": False,
        "limitations": [
            "Python finally/report/cleanup is not guaranteed after watchdog os._exit, native crash, process kill, or machine loss.",
            "Native reads are not atomic against external UI/add-ins; exclusive worker-seat ownership is required.",
            "Existing outer telemetry may obscure failure delivery; no global end-to-end guarantee is made.",
        ],
    }
    summary = report

    def case_report(control):
        return {
            "case": control["case"], "contract": control, "status": "not_started",
            "native_ship": "NOT_SHIP",
            "reads": {}, "errors": [], "primary_failure": None,
            "inventories": {}, "restores": [], "opens": [], "closures": [],
            "views": [], "identity_comparisons": [], "active_sketch": {},
            "diagnostic": None, "isolation_gate": "not_entered",
            "collection_completed": False,
        }

    summary["cases"] = [case_report(control) for control in CONTRACT["cases"]]

    def failure(label, error, original_tb=MISSING):
        nonlocal primary_exception, primary_traceback
        if primary_exception is None:
            # Retain the actual exception and original traceback before any
            # formatting, cleanup, or aggregate failure can obscure them.
            primary_exception = error
            primary_traceback = error.__traceback__ if original_tb is MISSING else original_tb
        # Error rendering must not interrupt an optional reader or cleanup.
        # Never fall back to repr(error), which can fail for the same reason.
        try:
            message = str(error)
        except BaseException:
            message = "<exception text unavailable>"
        row = {"operation": label, "type": type(error).__name__, "message": message}
        tb = error.__traceback__ if original_tb is MISSING else original_tb
        row["traceback_available"] = tb is not None
        row["traceback_frames"] = []
        while tb is not None:
            row["traceback_frames"].append({
                "file": tb.tb_frame.f_code.co_filename,
                "function": tb.tb_frame.f_code.co_name,
                "line": tb.tb_lineno,
            })
            tb = tb.tb_next
        report["errors"].append(row)
        if report["primary_failure"] is None:
            report["primary_failure"] = row
        if report is not summary:
            summary["errors"].append(dict(row, case=report["case"]))
            if summary["primary_failure"] is None:
                summary["primary_failure"] = summary["errors"][-1]
        return row

    def attempt(label, reader):
        try:
            return reader()
        except BaseException as error:
            failure(label, error)
            return MISSING

    def observe(label, reader):
        value = attempt(label, reader)
        if value is not MISSING:
            report["reads"][label] = value
        return value

    def checkpoint():
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        # No default=str: unexpected native objects must not be rendered as COM repr.
        REPORT.write_text(json.dumps(summary, indent=2, allow_nan=False) + "\n", encoding="utf-8")

    def pinned_identity(control, kind, phase):
        value = file_identity(ROOT / control[kind]["path"])
        report["reads"][f"{phase}.{kind}"] = value
        require(value == {key: control[kind][key] for key in ("bytes", "sha256")},
                f"{phase}: {kind} is not the pinned saved native")
        if kind == "part":
            # Match the preserved generation token's canonical text in memory;
            # never mint/write a production .execution token for this probe.
            token_md5 = hashlib.md5((value["sha256"] + "\n").encode("utf-8"), usedforsecurity=False).hexdigest()
            report["reads"][f"{phase}.part.execution_token_canonical_md5"] = token_md5
            require(token_md5 == control["historical_provenance"]["execution_token_canonical_md5"],
                    f"{phase}: part SHA does not derive the historical generation-token digest")
        return value

    def download_capture(spec, target):
        # Same ContainerClient/get_blob_client/download_blob/readall convention
        # as _artifact_cache; worker auth is restricted to its managed identity.
        # No CLI/login, SAS, permission change, upload, or alternate source.
        from azure.identity import ManagedIdentityCredential
        from azure.storage.blob import ContainerClient

        credential = None
        client = None
        try:
            target = cache._restore_path(target)
            report["reads"]["captured_blob.auth"] = "system_assigned_ManagedIdentityCredential_only"
            credential = ManagedIdentityCredential()
            client = ContainerClient(
                f"https://{spec['account']}.blob.core.windows.net",
                spec["container"], credential=credential,
            )
            payload = client.get_blob_client(spec["blob"]).download_blob().readall()
            identity = {"bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest()}
            report["reads"]["captured_blob.download_identity"] = identity
            require(identity == {key: spec[key] for key in ("bytes", "sha256")},
                    "captured drawing download differs from pinned bytes")
            target.parent.mkdir(parents=True, exist_ok=True)
            cache._restore_path(target).write_bytes(payload)
        except BaseException as error:
            failure("captured_blob.download", error)
            raise
        finally:
            if client is not None:
                attempt("captured_blob.client.close", client.close)
            if credential is not None:
                attempt("captured_blob.credential.close", credential.close)

    try:
        checkpoint()
        parser = argparse.ArgumentParser(description=__doc__)
        parser.add_argument("--disposable-source-tree", action="store_true")
        args = parser.parse_args()
        require(args.disposable_source_tree, "explicit disposable source-tree acknowledgement required")
        require(os.environ.get("HARMONIC_COM_SEAT"), "the admitted task must hold the coordinated COM seat")
        require(os.environ.get("HARMONIC_SW_AUTOSTART") == "0", "attach-only worker seat required")
        contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        require(contract == CONTRACT, "committed three-case contract differs from immutable probe contract")
        report["reads"]["probe_identity"] = file_identity(Path(__file__))
        report["reads"]["contract_identity"] = file_identity(CONTRACT_PATH)
        sys.path[:0] = [str(ROOT), str(ROOT / "cad/scripts")]
        from diagnostics import _script_paths  # noqa: F401
        from diagnostics._owned_native_session import run_owned_diagnostic
        from _com import _early_bound, double_array
        import _artifact_cache as cache

        async def run_pair(adapter, control):
            app = adapter.swApp
            owned = []
            originals = {kind: ROOT / control[kind]["path"] for kind in ("part", "drawing")}
            targets = {}
            copy_root = ROOT / "cad/out/diagnostic-copies/mg-saved-thread-control" / uuid4().hex
            report["copy_root"] = str(copy_root)

            def certified_copy_path(path):
                # Reuse the repository's strict unaliased output policy, not a
                # containment check against an already-redirected resolved root.
                target = cache._restore_path(Path(path))
                base = ROOT / "cad/out/diagnostic-copies/mg-saved-thread-control"
                require(target != base and target.is_relative_to(base),
                        "copy is outside the trusted diagnostic output tree")
                require(target == copy_root or target.parent == copy_root,
                        "copy is outside this unique disposable directory")
                return target

            def inventory(label):
                rows = []
                error_start = len(report["errors"])
                snapshot = {
                    "method": "GetFirstDocument/GetNext",
                    "enumerated": False,
                    "documents": [],
                    "visited_count": 0,
                    "cursor_terminated": False,
                }
                report["inventories"][label] = snapshot
                count = attempt(f"{label}.GetDocumentCount.before", lambda: app.GetDocumentCount())
                raw = attempt(f"{label}.GetFirstDocument", lambda: app.GetFirstDocument())
                snapshot["first_document_state"] = (
                    "UNAVAILABLE" if raw is MISSING else "NULL" if raw is None else "PRESENT"
                )
                count_valid = type(count) is int and count >= 0
                if count_valid:
                    snapshot["native_count_before"] = count
                elif count is not MISSING:
                    failure(f"{label}.GetDocumentCount.before",
                            RuntimeError("native document count is not a nonnegative integer"))
                # The count bounds traversal, but never substitutes for a
                # successful native null cursor. Visit one excess entry only
                # to retain its metadata/identity evidence before refusing.
                while count_valid and raw is not MISSING and raw is not None:
                    index = len(rows)
                    tag = f"{label}[{index}]"
                    data = {"handle_token": tag}
                    snapshot["documents"].append(data)
                    doc = attempt(f"{tag}.bind", lambda: _early_bound(raw, "IModelDoc2"))
                    if doc is MISSING or doc is None:
                        if doc is None:
                            failure(f"{tag}.bind", RuntimeError("null document in cursor inventory"))
                        break
                    self_same = attempt(f"{tag}.identity.self", lambda: same(doc, doc, f"{tag}.identity.self"))
                    identity_valid = self_same is True
                    if self_same is False:
                        failure(f"{tag}.identity.self", RuntimeError("document is not natively identical to itself"))
                    for previous_index, previous in enumerate(rows):
                        identity_label = f"{tag}.identity.previous[{previous_index}]"
                        duplicate = attempt(identity_label, lambda: same(doc, previous["native"], identity_label))
                        if duplicate is True:
                            failure(identity_label, RuntimeError("duplicate/cyclic native document cursor"))
                        if duplicate is not False:
                            identity_valid = False
                    rows.append({"native": doc, "data": data})
                    snapshot["visited_count"] = len(rows)
                    # Each metadata reader is independent, including during cleanup.
                    for key, reader, expected_type in (
                        ("path", lambda: doc.GetPathName(), str),
                        ("title", lambda: doc.GetTitle(), str),
                        ("type", lambda: doc.GetType(), int),
                        ("dirty", lambda: doc.GetSaveFlag(), bool),
                        ("read_only", lambda: doc.IsOpenedReadOnly(), bool),
                    ):
                        value = attempt(f"{tag}.{key}", reader)
                        if value is not MISSING:
                            if type(value) is expected_type:
                                data[key] = value
                            else:
                                failure(f"{tag}.{key}", RuntimeError("native metadata result has an unavailable or unexpected type"))
                    if index >= count:
                        failure(f"{label}.cursor.cardinality", RuntimeError("native cursor exceeded the initial document count"))
                        break
                    if not identity_valid:
                        break
                    raw = attempt(f"{tag}.GetNext", lambda: doc.GetNext())
                snapshot["cursor_terminated"] = raw is None
                after = attempt(f"{label}.GetDocumentCount.after", lambda: app.GetDocumentCount())
                after_valid = type(after) is int and after >= 0
                if after_valid:
                    snapshot["native_count_after"] = after
                elif after is not MISSING:
                    failure(f"{label}.GetDocumentCount.after",
                            RuntimeError("native document count is not a nonnegative integer"))
                if count_valid and after_valid and not count == after == len(rows):
                    failure(f"{label}.cursor.cardinality",
                            RuntimeError("document count changed or differs from the visited cursor length"))
                snapshot["enumerated"] = (
                    count_valid and after_valid and count == after == len(rows)
                    and snapshot["cursor_terminated"] and len(report["errors"]) == error_start
                )
                return rows if snapshot["enumerated"] else None

            def complete(rows):
                return rows is not None and all(
                    all(key in row["data"] for key in ("path", "title", "type", "dirty", "read_only"))
                    for row in rows
                )

            def same(left, right, label):
                evidence = {"operation": label, "status": "unavailable"}
                report["identity_comparisons"].append(evidence)
                result = app.IsSame(left, right)
                # Official IsSame example: 0=different, 1=same, -1=unable
                # to determine. Unknown/unsupported is never ownership proof.
                if type(result) is int:
                    evidence["raw"] = result
                    evidence["status"] = {0: "different", 1: "same", -1: "unsupported"}.get(result, "unknown_code")
                else:
                    evidence["status"] = "unexpected_type"
                require(type(result) is int and result in (0, 1),
                        f"{label}: IsSame did not establish same/different identity")
                return result == 1

            def user_control(label):
                value = attempt(f"{label}.UserControl", lambda: app.UserControl)
                if type(value) is bool:
                    report["reads"][f"{label}.UserControl"] = value
                    return value
                report["reads"][f"{label}.UserControl_state"] = "UNAVAILABLE"
                if value is not MISSING:
                    failure(f"{label}.UserControl", RuntimeError("UserControl did not return an actual Boolean"))
                return MISSING

            def require_owned_inventory(rows, label, *, clean=False):
                require(complete(rows), f"{label}: complete live inventory required")
                require(len(rows) <= len(owned) <= 2, f"{label}: unknown or excess live documents")
                matched = set()
                for row in rows:
                    data = row["data"]
                    candidates = [
                        index for index, owner in enumerate(owned)
                        if canonical(data["path"]) == canonical(owner["data"]["path"])
                        and data["type"] == owner["data"]["type"]
                    ]
                    require(len(candidates) == 1, f"{label}: live document has no unique exact-path/type owner")
                    require(canonical(data["path"]) in {canonical(path) for path in targets.values()},
                            f"{label}: owner is not a certified disposable copy")
                    require(certified_copy_path(data["path"]).parent == certified_copy_path(copy_root),
                            f"{label}: owned path escaped unaliased unique copy directory")
                    index = candidates[0]
                    require(index not in matched, f"{label}: duplicate live owner")
                    require(same(row["native"], owned[index]["native"], f"{label}.live_vs_owned[{index}]"),
                            f"{label}: live document differs from retained direct OpenDoc6 result")
                    require(data["title"] == owned[index]["data"]["title"],
                            f"{label}: owned document title changed")
                    expected_mode = control["read_only"]["part" if data["type"] == 1 else "drawing"]
                    require(data["read_only"] is expected_mode, f"{label}: owned copy read-only state changed")
                    if data["dirty"] is True:
                        require(control["case"] in ("r1", "c1") and data["type"] == 3
                                and data["read_only"] is False
                                and canonical(data["path"]) == canonical(targets["drawing"]),
                                f"{label}: dirty document is not this case's writable drawing copy")
                    if clean:
                        require(data["dirty"] is False, f"{label}: dirty owned document is stranded; refusing CloseDoc")
                    matched.add(index)
                return rows

            def open_native(kind, doc_type):
                path = certified_copy_path(targets[kind])
                readonly = control["read_only"][kind]
                options = 3 if readonly else 1
                row = {"kind": kind, "requested_path": str(path), "options": options}
                report["opens"].append(row)
                # swOpenDocOptions_Silent=1 | swOpenDocOptions_ReadOnly=2.
                result = app.OpenDoc6(str(path), doc_type, options, "", 0, 0)
                require(isinstance(result, tuple) and len(result) == 3,
                        "early-bound OpenDoc6 did not return document/errors/warnings")
                raw, errors, warnings = result
                row.update(errors=errors, warnings=warnings)
                row["returned_document"] = raw is not None
                row["ownership_state"] = "UNAVAILABLE_STRANDED" if raw is not None else "NULL"
                require(raw is not None, f"OpenDoc6 returned no {kind}")
                doc = _early_bound(raw, "IModelDoc2")
                for key, reader, expected_type in (
                    ("path", lambda: doc.GetPathName(), str),
                    ("title", lambda: doc.GetTitle(), str),
                    ("type", lambda: doc.GetType(), int),
                    ("read_only", lambda: doc.IsOpenedReadOnly(), bool),
                ):
                    value = attempt(f"open.{kind}.{key}", reader)
                    if value is not MISSING:
                        if type(value) is expected_type:
                            row[key] = value
                        else:
                            failure(f"open.{kind}.{key}", RuntimeError("native open readback has an unavailable or unexpected type"))
                # Retain ONLY the direct result with certified path/type/title.
                # Never adopt auto-loaded references or arbitrary inventory deltas.
                if (type(row.get("path")) is str and canonical(row["path"]) == canonical(path)
                        and row.get("type") == doc_type and type(row.get("title")) is str and row["title"]):
                    certified_copy_path(row["path"])
                    owned.append({"native": doc, "data": {key: row[key] for key in ("path", "title", "type")}})
                    row["retained_owned"] = True
                    row["ownership_state"] = "CERTIFIED_COPY"
                    report["owned_documents"] = [dict(owner["data"]) for owner in owned]
                require(row.get("retained_owned") is True, f"OpenDoc6 did not certify the exact {kind} owner")
                require(type(errors) is int and type(warnings) is int, "OpenDoc6 status codes unavailable")
                require(errors == 0 and warnings == 0, f"OpenDoc6 reported {kind} load errors/warnings")
                require(row.get("read_only") is readonly, f"OpenDoc6 {kind} read-only state differs from fixed protocol")
                require_owned_inventory(inventory(f"after_open_{kind}"), f"after_open_{kind}")
                require(not report["errors"], "open readback/ownership collection failed")
                return doc

            def activate(doc, name, label):
                result = app.ActivateDoc3(name, False, 1, 0)  # swDontRebuildActiveDoc
                require(isinstance(result, tuple) and len(result) == 2,
                        "early-bound ActivateDoc3 did not return document/errors")
                raw, errors = result
                report["reads"][f"{label}.return"] = {"document_present": raw is not None, "errors": errors}
                # The helper/return pointer alone is never an activation witness.
                active = app.ActiveDoc
                witnessed = active is not None and same(active, doc, f"{label}.ActiveDoc")
                report["reads"][f"{label}.ActiveDoc_IsSame"] = witnessed
                require(type(errors) is int and errors == 0 and witnessed,
                        f"{label}: exact active document not witnessed or activation warning/error")

            # FIRST native boundary of EACH pair: read-only refusal gate.
            # This is deliberately OUTSIDE the mutation/cleanup try/finally.
            # Refusal must never activate/close a foreign or background session.
            report["isolation_gate"] = "refused"
            initial = inventory("initial")
            initial_active = attempt("initial.ActiveDoc", lambda: app.ActiveDoc)
            initial_current = attempt("initial.currentModel", lambda: adapter.currentModel)
            initial_control = user_control("initial")
            for label, handle in (("currentModel", initial_current), ("ActiveDoc", initial_active)):
                report["reads"][f"initial.{label}_state"] = (
                    "UNAVAILABLE" if handle is MISSING else "NULL" if handle is None else "PRESENT"
                )
            require(complete(initial) and initial == [] and not report["errors"],
                    "control requires stable zero native counts AND a complete null-terminated document cursor")
            require(initial_active is None and initial_current is None,
                    "control requires measured-null initial ActiveDoc and currentModel")
            require(initial_control is True, "control requires actual UserControl=True; no setter/repair permitted")
            report["isolation_gate"] = "accepted"
            try:
                certified_copy_path(copy_root)
                for kind in ("part", "drawing"):
                    certified_copy_path(copy_root / originals[kind].name)
                # Refuse redirected cache/SAS configuration; keep canonical
                # archive restore semantics and never mint execution tokens.
                require(not os.environ.get("HARMONIC_CACHE_SAS"), "SAS is forbidden")
                for name, expected in (("HARMONIC_CACHE_ACCOUNT", "stswbuildcache07aba2"),
                                       ("HARMONIC_CACHE_CONTAINER", "buildcache")):
                    require(os.environ.get(name) in (None, "", expected), f"{name} redirects pinned cache")
                for kind in ("drawing", "part"):
                    spec = control[kind]
                    if control["case"] in ("r1", "c1") and kind == "drawing":
                        row = {"kind": kind, "source": "private_failure_blob", "complete": False}
                        report["restores"].append(row)
                        download_capture(spec, originals[kind])
                        row["complete"] = True
                    else:
                        row = {"kind": kind, "key": spec["key"], "hit": None}
                        report["restores"].append(row)
                        row["hit"] = cache.restore(spec["key"], [originals[kind]], f"diagnostic:{control['case']}-{kind}")
                        require(row["hit"] is True, f"historical {kind} cache restore missed; regeneration forbidden")
                # Both hashes are checked after all staging, before any open.
                for kind in ("drawing", "part"):
                    attempt(f"staged.{kind}.identity", lambda kind=kind: pinned_identity(control, kind, "staged"))
                require(not report["errors"], "staged native identity verification failed")
                certified_copy_path(copy_root).mkdir(parents=True, exist_ok=False)
                for kind in ("part", "drawing"):
                    target = certified_copy_path(copy_root / originals[kind].name)
                    require(canonical(target) != canonical(originals[kind]), "copy aliases pinned original")
                    with originals[kind].open("rb") as source_stream, target.open("xb") as destination:
                        shutil.copyfileobj(source_stream, destination)
                    identity = file_identity(target)
                    report["reads"][f"copy_before.{kind}"] = identity
                    require(identity == report["reads"][f"staged.{kind}"], "disposable copy hash differs")
                    targets[kind] = target
                part = open_native("part", 1)
                drawing_model = open_native("drawing", 3)
                require(not report["errors"], "open ownership collection failed")
                activate(drawing_model, str(targets["drawing"]), "activate_control")
                adapter.currentModel = drawing_model
                drawing = _early_bound(drawing_model, "IDrawingDoc")
                names = tuple(str(name) for name in drawing.GetSheetNames() or ())
                report["reads"]["sheet_names"] = names
                require(names and names[0] == control["sheet_name"], "intended native sheet 1 differs from pinned case")
                rows = drawing.GetViews()
                require(rows is not None, "saved drawing returned no per-sheet views")
                candidates = []
                found_sheets = []
                for row_index, raw_row in enumerate(rows):
                    entries = list(raw_row or ())
                    require(entries, "empty native sheet view row")
                    sheet_view = _early_bound(entries[0], "IView")
                    name = str(sheet_view.Name)
                    sheet = _early_bound(drawing.Sheet(name), "ISheet")
                    require(sheet is not None, "sheet view does not resolve to ISheet")
                    sheet_name = str(sheet.GetName())
                    found_sheets.append(sheet_name)
                    report["views"].append({"row": row_index, "sheet": sheet_name,
                                            "sheet_view_name": name, "role": "sheet"})
                    for view_index, raw in enumerate(entries[1:], 1):
                        view = _early_bound(raw, "IView")
                        item = {"row": row_index, "index": view_index, "sheet": sheet_name}
                        report["views"].append(item)
                        view_name = attempt(f"view[{row_index},{view_index}].name", lambda: str(view.Name))
                        if view_name is not MISSING:
                            item["name"] = view_name
                        section = attempt(f"view[{row_index},{view_index}].section",
                                          lambda: _early_bound(view.GetSection(), "IDrSection"))
                        if section is MISSING:
                            continue
                        item["section_present"] = section is not None
                        if section is not None:
                            label = attempt(f"view[{row_index},{view_index}].label", lambda: str(section.GetLabel()))
                            if label is not MISSING:
                                item["section_label"] = label
                                if sheet_name == control["sheet_name"] and label == control["section_label"]:
                                    candidates.append(view)
                        if control["case"] in ("r1", "c1"):
                            def view_reference():
                                # SDK section views have no own reference;
                                # inspect their native parent, never substitute
                                # a filename or an auto-loaded inventory delta.
                                reference_view = _early_bound(view.GetBaseView(), "IView") if section is not None else view
                                require(reference_view is not None, "drawing view has no native reference owner")
                                reference = _early_bound(reference_view.ReferencedDocument, "IModelDoc2")
                                require(reference is not None, "drawing reference unavailable")
                                path = reference.GetPathName()
                                require(type(path) is str and canonical(path) == canonical(targets["part"]),
                                        "drawing view references another path")
                                require(same(reference, part, f"view[{row_index},{view_index}].reference"),
                                        "drawing view references another native source")
                                item["reference_path"] = path
                                item["reference_IsSame_owned_part"] = True
                            attempt(f"view[{row_index},{view_index}].reference", view_reference)
                report["reads"]["section_candidates_on_intended_sheet"] = len(candidates)
                require(sorted(found_sheets) == sorted(names), "per-sheet view inventory differs from native sheet names")
                require(not report["errors"] and len(candidates) == 1, "exactly one native case section on intended sheet required")
                section = candidates[0]
                base = _early_bound(section.GetBaseView(), "IView")
                require(base is not None, "case section has no native base view")
                source = _early_bound(base.ReferencedDocument, "IModelDoc2")
                require(source is not None, "base view has no resolved ReferencedDocument")
                reference_path = observe("base.reference_path", lambda: str(source.GetPathName()))
                reference_same = observe("base.reference_IsSame_opened_part", lambda: same(source, part, "base.reference_vs_opened_part"))
                require(reference_path is not MISSING and canonical(reference_path) == canonical(targets["part"])
                        and reference_same is True, "base reference is not the exact staged/opened part")
                # GetViews order is not sheet order. Activate the pinned native
                # sheet by name, then independently witness its current identity.
                activated = drawing.ActivateSheet(control["sheet_name"])
                report["reads"]["activate_sheet.return"] = bool(activated)
                current_sheet = _early_bound(drawing.GetCurrentSheet(), "ISheet")
                require(activated is True and current_sheet is not None
                        and str(current_sheet.GetName()) == control["sheet_name"], "intended sheet activation failed")

                def observe_active_sketch(phase):
                    observations = {}
                    report["active_sketch"][phase] = observations
                    for name, document in (("source", source), ("drawing", drawing_model)):
                        row = {"state": "UNAVAILABLE", "errors": []}
                        observations[name] = row
                        start = len(report["errors"])

                        def read_sketch():
                            manager = _early_bound(document.SketchManager, "ISketchManager")
                            require(manager is not None, "SketchManager returned null")
                            return manager.ActiveSketch

                        sketch = attempt(f"{phase}.{name}.ActiveSketch", read_sketch)
                        row["errors"] = report["errors"][start:]
                        if sketch is not MISSING:
                            row["state"] = "NULL" if sketch is None else "PRESENT"

                if control["case"] == "sm_positive":
                    observe_active_sketch("before_diagnostic_including_generation")
                    report["diagnostic"] = {"reads": {}, "errors": {}, "feature": control["feature_name"]}
                    report["optional_evidence"] = {
                        "display_coordinate_frame": "UNAVAILABLE_NO_PRIMARY_FRAME_AUTHORITY",
                        "source_display_bridge": "Only actual native correspondence is recorded; NULL remains unavailable",
                    }
                    cut = attempt("sm.section", lambda: _early_bound(section.GetSection(), "IDrSection"))
                    report["control_states"] = {}
                    for phase in ("before_generation", "after_generation"):
                        if phase == "after_generation":
                            observe("sm.generation.ViewZoomtofit2", drawing_model.ViewZoomtofit2)
                            observe("sm.generation.UpdateViewDisplayGeometry", section.UpdateViewDisplayGeometry)
                        report["control_states"][phase] = representation_state(
                            section, base, part, drawing_model, cut, _early_bound,
                            lambda key, reader: observe(f"sm.{phase}.{key}", reader))
                        capture_thread_stage(section, part, phase, report["diagnostic"], _early_bound, same, failure)
                    observe_active_sketch("after_diagnostic_including_generation")
                    report["thread_ink"] = thread_ink_summary(report["diagnostic"])
                    require(report["thread_ink"]["complete"] and not report["errors"]
                            and bool(report["thread_ink"]["positive_payload_fields"]),
                            "SM requires complete native control readers and genuine finite positive primitive geometry")
                    report["source_metadata"] = passive_sm_thread_metadata(part, control["feature_name"], _early_bound, same, failure)
                    require(report["source_metadata"]["state"] == "OBSERVED", "SM scalar census unavailable")
                else:
                    intervention = {"state": "UNAVAILABLE", "changed_factor": control["changed_factor"],
                                    "attempted": False, "confirmed": False, "mutator_calls": 0,
                                    "stages": {}, "causal_conclusion": "NOT_ESTABLISHED", "native_ship": "NOT_SHIP"}
                    report["representation"] = intervention
                    cut = _early_bound(section.GetSection(), "IDrSection")
                    require(cut is not None, "target native section object unavailable")

                    def target_guard(label, *, clean):
                        live = require_owned_inventory(inventory(label), label, clean=clean)
                        require(len(live) == 2, "both exact owned copies must remain live")
                        require(part.IsOpenedReadOnly() is True and drawing_model.IsOpenedReadOnly() is False,
                                "representation case requires readonly PART and writable DRAWING")
                        found = 0
                        fresh_rows = drawing.GetViews()
                        require(isinstance(fresh_rows, (list, tuple)), "live target view inventory unavailable")
                        for raw_row in fresh_rows:
                            require(isinstance(raw_row, (list, tuple)) and raw_row, "live sheet row unavailable")
                            for raw_view in raw_row[1:]:
                                current = _early_bound(raw_view, "IView")
                                require(current is not None, "live view unavailable")
                                current_cut = _early_bound(current.GetSection(), "IDrSection")
                                parent = _early_bound(current.GetBaseView(), "IView") if current_cut is not None else current
                                require(parent is not None, "live reference owner unavailable")
                                reference = _early_bound(parent.ReferencedDocument, "IModelDoc2")
                                require(reference is not None and canonical(reference.GetPathName()) == canonical(targets["part"])
                                        and same(reference, part, f"{label}.reference"), "live drawing reference changed")
                                if same(current, section, f"{label}.target_view"):
                                    found += 1
                                    require(current.Type == 2 and same(parent, base, f"{label}.base")
                                            and current_cut is not None and same(current_cut, cut, f"{label}.section"),
                                            "target native view/parent/section identity changed")
                        require(found == 1, "target view absent or ambiguous")
                        if label == "before_intervention":
                            for kind in ("part", "drawing"):
                                original_hash = observe(f"{label}.original.{kind}", lambda kind=kind: file_identity(originals[kind]))
                                copy_hash = observe(f"{label}.copy.{kind}", lambda kind=kind: file_identity(targets[kind]))
                                require(original_hash == report["reads"][f"staged.{kind}"]
                                        and copy_hash == report["reads"][f"copy_before.{kind}"],
                                        "original or disposable copy bytes drifted before write")
                        require(user_control(label) is True, "UserControl not proven before representation operation")
                        require(not report["errors"], "representation ownership/state reader failed")

                    def run_representation(snapshot, wizard, cosmetic):
                        report["diagnostic"] = {"reads": {}, "errors": {}, "feature": control["feature_name"]}
                        report["after_intervention_diagnostic"] = {"reads": {}, "errors": {}, "feature": control["feature_name"]}
                        def stage(label, channel_phase, diagnostic):
                            entry = {"state": {}, "geometry": None, "visual": {"state": "NOT_REQUESTED_ZERO_OR_UNAVAILABLE"}}
                            intervention["stages"][label] = entry
                            def state_read(key, reader):
                                return observe(f"{label}.{key}", reader)
                            entry["state"] = representation_state(section, base, part, drawing_model, cut, _early_bound, state_read)
                            observe_active_sketch(label)
                            capture_thread_stage(section, part, channel_phase, diagnostic, _early_bound, same, failure)
                            entry["annotation_controls"] = {
                                key.removeprefix(channel_phase + "."): value
                                for key, value in diagnostic["reads"].items()
                                if key.startswith(channel_phase + ".") and key.endswith((".visible", ".dangling", ".layer", ".attachment_types"))
                            }
                            if any(key.startswith(channel_phase + ".") and key.endswith(".points") and value
                                   for key, value in diagnostic["reads"].items()):
                                def capture_image():
                                    # Existing pixel-only helper: no native save,
                                    # viewport mutation, window lookup or COM call.
                                    from _seat_forensics import _grab_screen
                                    expected_parent = ROOT / "cad/out/reports/diagnostics/representation-images" / copy_root.name
                                    expected_name = f"{control['case']}-{label}.png"
                                    def certify_image_path():
                                        target = cache._restore_path(REPORT.parent / "representation-images" / copy_root.name / expected_name)
                                        require(REPORT.parent == ROOT / "cad/out/reports/diagnostics"
                                                and target.parent == expected_parent and target.name == expected_name,
                                                "image path is outside trusted unique report subtree")
                                        return target
                                    path = certify_image_path()
                                    require(not path.exists(), "image path not fresh")
                                    _grab_screen(path)
                                    identity = file_identity(certify_image_path())
                                    require(identity["bytes"] > 0, "image capture produced no bytes")
                                    return {"state": "CAPTURED_DESKTOP", "path": str(path), **identity,
                                            "limitation": "Session desktop pixels; no claim of unobscured target view or native flank identity"}
                                image = attempt(f"{label}.image", capture_image)
                                entry["visual"] = ({"state": "GAP", "reason": "Pixel-only capture failed; see original local error"}
                                                   if image is MISSING else image)
                            geometry_diagnostic = {"reads": {key:value for key,value in diagnostic["reads"].items()
                                                            if key.startswith(channel_phase + ".")}}
                            geometry = attempt(f"{label}.geometry", lambda: project_thread_geometry(
                                app, section, entry["state"], snapshot, wizard, cosmetic,
                                geometry_diagnostic, _early_bound, double_array))
                            if geometry is not MISSING:
                                entry["geometry"] = geometry
                            return entry["state"]
                        def expected_state(state, angle, cut_only):
                            require(type(state.get("angle")) in (float,int) and math.isclose(state["angle"], angle, rel_tol=0, abs_tol=1e-10)
                                    and state.get("cut_only") is cut_only, "fresh baseline/factor readback differs")
                            require(type(state.get("type")) is int and state["type"] == 2
                                    and state.get("broken") is False, "target is not an unbroken section view")
                            require(type(state.get("configuration")) is str and bool(state["configuration"])
                                    and state.get("configuration") == state.get("base_configuration"),
                                    "native section/base configuration unavailable or different")
                        def generation(label):
                            observe(label + ".ViewZoomtofit2", drawing_model.ViewZoomtofit2)
                            observe(label + ".UpdateViewDisplayGeometry", section.UpdateViewDisplayGeometry)
                        target_guard("before_baseline", clean=True)
                        baseline = stage("baseline_before_generation", "before_generation", report["diagnostic"])
                        expected_state(baseline, control["baseline_angle"], True)
                        require(not report["errors"], "baseline readers unavailable")
                        generation("baseline_generation")
                        baseline_after = stage("baseline_after_generation", "after_generation", report["diagnostic"])
                        expected_state(baseline_after, control["baseline_angle"], True)
                        require(baseline_after == baseline, "baseline generation changed a controlled factor")
                        report["thread_ink"] = thread_ink_summary(report["diagnostic"])
                        require(report["thread_ink"]["state"] == "OBSERVED_ZERO" and report["thread_ink"]["complete"],
                                "fresh baseline is not complete observed zero; intervention refused")
                        require(not report["errors"], "baseline safety/evidence unavailable")
                        target_guard("before_intervention", clean=False)
                        # Last baseline readback after ownership census; only
                        # the explicitly selected drawing mutator follows.
                        last = representation_state(section, base, part, drawing_model, cut, _early_bound,
                                                    lambda key,reader: observe("before_write."+key,reader))
                        expected_state(last, control["baseline_angle"], True)
                        require(last == baseline, "controlled state drifted immediately before write")
                        require(user_control("immediate_prewrite") is True, "UserControl changed before write")
                        require(not report["errors"], "last prewrite evidence unavailable")
                        intervention["attempted"] = True
                        intervention["mutator_calls"] = 1
                        try:
                            if control["case"] == "r1":
                                section.Angle = 0.0  # IView PUT DISPID200, radians.
                            else:
                                value = cut.SetDisplayOnlySurfaceCut(False)  # IDrSection VT_VOID, never BOOL.
                                report["reads"]["intervention.setter_return"] = value
                                require(value is None, "VOID cut-only setter returned unexpected value")
                        except BaseException as error:
                            failure("intervention.write", error, error.__traceback__)
                        finally:
                            post = stage("post_write_before_generation", "before_generation", report["after_intervention_diagnostic"])
                        expected_state(post, control["requested_angle"], control["requested_cut_only"])
                        allowed = ("angle", "cut_only", "position") if control["case"] == "r1" else ("angle", "cut_only")
                        unchanged = [key for key in baseline if key not in allowed]
                        require(all(post.get(key) == baseline[key] for key in unchanged),
                                "intervention changed another controlled factor")
                        # Position is observed separately: rotation may move
                        # a view's geometric centre, never write it to repair.
                        intervention["position_changed"] = post.get("position") != baseline.get("position")
                        require(not report["errors"], "write/readback failed; no generation or retry")
                        intervention["confirmed"] = True
                        target_guard("after_intervention", clean=False)
                        generation("post_write_generation")
                        final_state = stage("post_write_after_generation", "after_generation", report["after_intervention_diagnostic"])
                        expected_state(final_state, control["requested_angle"], control["requested_cut_only"])
                        require(all(final_state.get(key) == baseline[key] for key in unchanged),
                                "post-generation controlled factors changed")
                        controls = [entry["annotation_controls"] for entry in intervention["stages"].values()]
                        require(all(value == controls[0] for value in controls), "annotation visibility/layer/attachment type controls changed")
                        target_guard("after_generation", clean=False)
                        report["after_intervention_thread_ink"] = thread_ink_summary(report["after_intervention_diagnostic"])
                        ink = report["after_intervention_thread_ink"]
                        require(ink["complete"] and not report["errors"], "post-intervention evidence unavailable")
                        intervention["state"] = ("OBSERVED_POSITIVE" if ink["positive_payload_fields"]
                                                 else "OBSERVED_ZERO" if ink["state"] == "OBSERVED_ZERO" else "UNAVAILABLE")
                        require(intervention["state"] != "UNAVAILABLE", "positive counts without extracted geometry")
                    report["source_observations"] = source_observations(
                        part, control["feature_name"], _early_bound, same, failure, run_representation)
                    require(report["source_observations"]["clean_comparison"] is True
                            and intervention["confirmed"] is True and not report["errors"],
                            "readonly source stability or drawing intervention incomplete")
                report["collection_completed"] = True
            except BaseException as error:
                failure("collect", error)
            finally:
                # CloseDoc also closes hidden documents: certify every live
                # copy and readonly mode; only this R1/C1 drawing may be dirty.
                for index, owned_row in enumerate(sorted(owned, key=lambda row: row["data"]["type"] != 3)):
                    data = owned_row["data"]
                    closure = {"path": data["path"], "title": data["title"], "status": "stranded_owned"}
                    report["closures"].append(closure)

                    def close_owned():
                        now = require_owned_inventory(inventory(f"before_close_{index}"),
                                                      f"before_close_{index}", clean=control["case"] == "sm_positive")
                        matches = [row for row in now if canonical(row["data"]["path"]) == canonical(data["path"])]
                        if not matches:
                            closure["status"] = "already_unloaded"
                            return
                        require(len(matches) == 1, "ambiguous owned path before CloseDoc")
                        title = matches[0]["data"]["title"]
                        require(title and sum(row["data"]["title"] == title for row in now) == 1,
                                "ambiguous/empty CloseDoc title")
                        # Last native read before CloseDoc. Never set this flag:
                        # closing the last doc with False may terminate the seat.
                        require(user_control(f"before_close_{index}") is True,
                                "UserControl not proven True; owned documents stranded")
                        app.CloseDoc(title)  # VT_VOID; may also unload the owned part.
                        closure["status"] = "close_requested_without_save"

                    attempt(f"close[{index}]", close_owned)
                # Initial state was proven empty/null. Only restore this Python
                # reference; never activate anything or force native emptiness.
                attempt("final.restore_currentModel", lambda: setattr(adapter, "currentModel", initial_current))
                final = inventory("final")
                final_active = attempt("final.ActiveDoc", lambda: app.ActiveDoc)
                report["reads"]["final.ActiveDoc_state"] = (
                    "UNAVAILABLE" if final_active is MISSING else "NULL" if final_active is None else "PRESENT"
                )
                observe("final.inventory_empty", lambda: (
                    require(complete(final) and final == [], "native documents remain or final inventory unavailable") or True
                ))
                observe("final.active_identity_restored", lambda: (
                    require(final_active is None, "initial null ActiveDoc was not restored") or True
                ))
                observe("final.currentModel_identity_restored", lambda: (
                    require(adapter.currentModel is None, "initial null currentModel was not restored") or True
                ))
                for kind in ("drawing", "part"):
                    attempt(f"final.{kind}.identity", lambda kind=kind: pinned_identity(control, kind, "final"))
                    if kind in targets:
                        def copy_identity(kind=kind):
                            identity = file_identity(targets[kind])
                            report["reads"][f"copy_after.{kind}"] = identity
                            require(identity == report["reads"][f"copy_before.{kind}"],
                                    f"copy {kind} disk bytes changed; no native artifact is adopted")
                        attempt(f"copy_after.{kind}.identity", copy_identity)
                attempt("callback.checkpoint", checkpoint)
            if primary_exception is not None:
                raise primary_exception.with_traceback(primary_traceback)

        async def probe(adapter):
            nonlocal report
            application = adapter.swApp
            summary["session"]["python_handles"] = {
                "adapter": id(adapter), "application_wrapper": id(application),
                "scope": "Python object identity only; native PID/revision are the existing runner's attach telemetry.",
            }
            try:
                # Explicit order; one adapter/native session, no case matrix.
                for control, case in zip((SM_POSITIVE, R1, C1), summary["cases"], strict=True):
                    report = case
                    report["status"] = "running"
                    try:
                        report["session_python_handles"] = {
                            "adapter": id(adapter), "application_wrapper": id(adapter.swApp),
                        }
                        require(adapter.swApp is application, "attached application wrapper changed between pairs")
                        await run_pair(adapter, control)
                    except BaseException as error:
                        failure("pair", error)
                        raise primary_exception.with_traceback(primary_traceback)
                    finally:
                        report["status"] = "failed" if report["errors"] else (
                            "observed_with_diagnostic_read_errors"
                            if any((report.get(key) or {}).get("errors")
                                   for key in ("diagnostic", "after_intervention_diagnostic")) else "observed"
                        )
                    # run_pair returns only after owned-copy close, full empty/
                    # null proof, and unchanged original/copy hashes without errors.
                summary["collection_completed"] = True
                return {"report": str(REPORT), "collection_completed": True}
            finally:
                report = summary

        runner_failures = []
        report["runner_exit_code"] = run_owned_diagnostic(probe, failures=runner_failures)
        for phase, error, original_tb in runner_failures:
            failure(f"runner.{phase}", error, original_tb)
    except BaseException as error:
        failure("driver", error)
    finally:
        report = summary
        report["status"] = "failed" if report["errors"] else (
            "observed_with_diagnostic_read_errors"
            if any((case.get(key) or {}).get("errors") for case in report["cases"]
                   for key in ("diagnostic", "after_intervention_diagnostic"))
            else "observed"
        )
        try:
            checkpoint()
        except BaseException as error:
            # A filesystem failure cannot be represented in an unwritable file.
            row = failure("report_write", error)
            try:
                print(f"control report write failed: {row['type']}: {row['message']}", file=sys.stderr)
            except BaseException:
                # Preserve the already-recorded primary failure if stderr fails too.
                pass
        if primary_exception is not None:
            # The pool publishes fresh regular files under this recognized
            # failure root even for nonzero leaves; it does not fetch our normal
            # diagnostic target on failure. Export only AFTER all native cleanup.
            report["status"] = "failed"
            try:
                frames = []
                tb = primary_traceback
                while tb is not None:
                    frames.append({
                        "file": tb.tb_frame.f_code.co_filename,
                        "function": tb.tb_frame.f_code.co_name,
                        "line": tb.tb_lineno,
                    })
                    tb = tb.tb_next
                report["primary_traceback"] = {
                    "available": primary_traceback is not None,
                    "frames": frames,
                    "locals_captured": False,
                }
                failure_path = (
                    ROOT / "cad/out/reports/failures/mg-saved-thread-control"
                    / datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ") / "capture.json"
                )
                report["failure_artifact"] = {
                    "workspace_path": failure_path.relative_to(ROOT).as_posix(),
                    "transport": "pool failures/ prefix beside this execution's task.log",
                    "publication": "pending_worker_upload",
                }
                failure_path.parent.mkdir(parents=True, exist_ok=False)
                failure_path.write_text(
                    json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8"
                )
            except BaseException as error:
                row = failure("failure_artifact_write", error)
                try:
                    print(f"control failure artifact write failed: {row['type']}: {row['message']}", file=sys.stderr)
                except BaseException:
                    pass
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
