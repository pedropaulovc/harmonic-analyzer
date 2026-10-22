"""Disposable fixed SM-positive / S1 source-definition investigation; NEVER MERGE.

SM opens independent readonly copies and retains clean-only cleanup. S1 opens
only a unique same-basename PART COPY writable and DRW COPY readonly. After
native ownership/reference proof and a zero baseline, at most one real cosmetic
definition is accessed and released without modification. No settings, saves,
reference replacement, rebuild experiment, or other intervention is reachable.
The existing diagnostic retains its single display-generation boundary.
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
S1 = {
    "case": "s1",
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
CONTRACT = {
    "schema": 3,
    "protocol": {
        "order": "SM readonly positive, then one S1 disposable-copy access/read/release",
        "selected_edge": "Only a unique real CosmeticThread definition; Wizard alone is UNAVAILABLE",
        "cleanup": "SM clean-only; S1 known-dirty copies only, complete owned inventory and UserControl=True before each close",
        "limitations": "No historical in-memory part hash, flank identity, global telemetry, or hard-crash cleanup guarantee",
    },
    "cases": [SM_POSITIVE, S1],
}
MISSING = object()


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


def source_intervention(part, intended_name, bind, same, failure, before_access):
    """The only S1 intervention. Native references always remain in this PART context."""
    result = {"state": "UNAVAILABLE", "reads": {}, "errors": [], "phases": {},
              "access_calls": 0, "release_calls": 0, "causal_conclusion": "NOT_ESTABLISHED"}
    body_references = {}

    def read(label, reader, *, opaque=False):
        try:
            value = reader()
            result["reads"][label] = {"present": value is not None} if opaque else value
            return value
        except BaseException as error:
            row = failure(f"s1.{label}", error)
            result["errors"].append(row)
            return MISSING

    def typed(raw, interface):
        require(raw is not None and raw is not MISSING, f"{interface} unavailable")
        value = bind(raw, interface)
        require(value is not None, f"{interface} null")
        return value

    def scalar(value, expected):
        require(type(value) is expected or (expected is float and type(value) is int),
                "native scalar has unexpected type")
        require(expected is not float or math.isfinite(value), "native scalar is not finite")
        return value

    extension = read("part.extension", lambda: typed(part.Extension, "IModelDocExtension"), opaque=True)
    if extension is MISSING:
        return result

    def resolve(reference, label):
        pair = extension.GetObjectByPersistReference3(reference)
        require(isinstance(pair, tuple) and len(pair) == 2, "persistent resolution OUT status missing")
        entity, status = pair
        result["reads"][f"{label}.status"] = status
        require(type(status) is int and status == 0 and entity is not None,
                "persistent object unresolved in owned part context")
        return entity

    def persistent(entity, label):
        def collect():
            reference = extension.GetPersistReference3(entity)
            require(reference is not None, "persistent reference is null")
            values = list(reference)
            require(values and all(type(item) is int and 0 <= item <= 255 for item in values),
                    "persistent reference is not a nonempty byte array")
            result["reads"][f"{label}.bytes"] = values
            resolved = resolve(reference, label)
            require(same(resolved, entity, f"s1.{label}.resolved_identity"), "persistent identity differs")
            return reference
        return read(label, collect, opaque=True)

    wizard_properties = {
        "CosmeticThreadType": int, "ThreadEndCondition": int, "ThreadClass": str,
        "Type": int, "FastenerSize": str, "EndCondition": int, "HoleDepth": float,
        "ThreadDepth": float, "TapDrillDepth": float, "ThruTapDrillDepth": float,
        "ThreadDiameter": float, "TapDrillDiameter": float, "ThruTapDrillDiameter": float,
    }
    cosmetic_properties = {
        "ApplyThread": int, "BlindDepth": float, "Diameter": float,
        "DiameterType": int, "EndCondition": int,
    }

    def geometry(edge, label):
        values = {}
        curve = read(f"{label}.curve", lambda: typed(edge.GetCurve(), "ICurve"), opaque=True)
        if curve is not MISSING:
            for key, reader in (
                ("circle", lambda: scalar(curve.IsCircle(), bool)),
                ("circle_parameters", lambda: finite_values(curve.CircleParams, 7)),
                ("curve_domain", lambda: curve.GetEndParams()),
            ):
                # CircleParams is defined only for an underlying circle.
                if key == "circle_parameters" and values.get("circle") is not True:
                    continue
                value = read(f"{label}.{key}", reader)
                if value is not MISSING:
                    values[key] = value
            params = read(f"{label}.trim", lambda: typed(edge.GetCurveParams3(), "ICurveParamData"), opaque=True)
            if params is not MISSING:
                for key, expected in (("UMinValue", float), ("UMaxValue", float), ("Sense", bool)):
                    value = read(f"{label}.{key}", lambda key=key, expected=expected: scalar(getattr(params, key), expected))
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
        return {"reads": values, "trimmed_circle": trimmed_circle_summary(values)}

    def capture(phase):
        error_start = len(result["errors"])
        snapshot = {"features": [], "edges": [], "complete": False}
        result["phases"][phase] = snapshot
        features, edges = [], []

        def walk(raw, parent=None, depth=0, ancestors=()):
            chain = []
            while raw is not None and raw is not MISSING:
                require(depth < 32 and len(features) < 512, "bounded feature inventory exhausted")
                feature = typed(raw, "IFeature")
                require(not any(same(feature, previous, f"s1.{phase}.cursor_cycle") for previous in chain),
                        "cyclic feature cursor")
                require(not any(same(feature, ancestor, f"s1.{phase}.ancestor_cycle") for ancestor in ancestors),
                        "cyclic subfeature ancestry")
                chain.append(feature)
                duplicates = [item for item in features if same(feature, item["native"], f"s1.{phase}.deduplicate")]
                if not duplicates:
                    index = len(features)
                    label = f"{phase}.feature[{index}]"
                    row = {"index": index, "parent_inventory_index": parent, "definition_state": "UNAVAILABLE",
                           "scalars": {}, "face_state": "UNAVAILABLE"}
                    snapshot["features"].append(row)
                    item = {"native": feature, "row": row, "definition": MISSING, "reference": MISSING,
                            "faces": [], "owner": MISSING}
                    features.append(item)
                    for key, reader in (
                        ("name", lambda: scalar(feature.Name, str)),
                        ("type", lambda: scalar(feature.GetTypeName2(), str)),
                        ("rolled_back", lambda: scalar(feature.IsRolledBack(), bool)),
                    ):
                        value = read(f"{label}.{key}", reader)
                        if value is not MISSING:
                            row[key] = value
                    item["reference"] = persistent(feature, f"{label}.reference")
                    item["owner"] = read(f"{label}.owner", lambda: feature.GetOwnerFeature(), opaque=True)
                    row["owner_state"] = "UNAVAILABLE" if item["owner"] is MISSING else "NULL" if item["owner"] is None else "PRESENT"
                    raw_definition = read(f"{label}.definition", lambda: feature.GetDefinition(), opaque=True)
                    row["definition_state"] = "UNAVAILABLE" if raw_definition is MISSING else "NULL_UNSUPPORTED" if raw_definition is None else "PRESENT"
                    interface = {"HoleWzd": "IWizardHoleFeatureData2",
                                 "CosmeticThread": "ICosmeticThreadFeatureData"}.get(row.get("type"))
                    if interface and raw_definition is not None and raw_definition is not MISSING:
                        definition = read(f"{label}.typed_definition", lambda: typed(raw_definition, interface), opaque=True)
                        item["definition"] = definition
                        row["definition_interface"] = interface
                        if definition is not MISSING:
                            properties = wizard_properties if interface == "IWizardHoleFeatureData2" else cosmetic_properties
                            for name, expected in properties.items():
                                value = read(f"{label}.{name}", lambda name=name, expected=expected: scalar(getattr(definition, name), expected))
                                if value is not MISSING:
                                    row["scalars"][name] = value
                    child = read(f"{label}.first_subfeature", lambda: feature.GetFirstSubFeature(), opaque=True)
                    walk(child, index, depth + 1, ancestors + (feature,))
                raw = read(f"{phase}.next[{len(chain)}].depth[{depth}]",
                           lambda: feature.GetNextFeature() if parent is None else feature.GetNextSubFeature(), opaque=True)

        read(f"{phase}.traversal", lambda: walk(part.FirstFeature()))
        # Preserve owner identities and every independent physical feature-face
        # membership. GetFeature gives oldest owner, not exclusive ownership.
        for item in features:
            row, feature = item["row"], item["native"]
            label = f"{phase}.feature[{row['index']}]"
            owner = item["owner"]
            if owner is not MISSING and owner is not None:
                row["owner_inventory_matches"] = []
                for other in features:
                    value = read(f"{label}.owner_vs[{other['row']['index']}]",
                                 lambda other=other: same(owner, other["native"], f"s1.{label}.owner"))
                    if value is True:
                        row["owner_inventory_matches"].append(other["row"]["index"])
                read(f"{label}.owner_inventory_complete",
                     lambda: require(len(row["owner_inventory_matches"]) == 1,
                                     "nonnull feature owner not uniquely in source inventory"))
            faces = read(f"{label}.faces", lambda: feature.GetFaces(), opaque=True)
            if faces is not MISSING:
                row["face_state"] = "NULL" if faces is None else "PRESENT"
                if faces is not None:
                    def collect_faces():
                        require(isinstance(faces, (tuple, list)), "feature faces not an array")
                        item["faces"] = [typed(face, "IFace2") for face in faces]
                    read(f"{label}.face_array", collect_faces)
            for face_index, face in enumerate(item["faces"]):
                raw_edges = read(f"{label}.face[{face_index}].edges", lambda face=face: face.GetEdges(), opaque=True)
                if raw_edges is MISSING or raw_edges is None:
                    continue
                def collect_edges():
                    require(isinstance(raw_edges, (tuple, list)), "face edges not an array")
                    for raw_edge in raw_edges:
                        edge = typed(raw_edge, "IEdge")
                        if not any(same(edge, existing["native"], f"s1.{phase}.edge_deduplicate") for existing in edges):
                            edge_label = f"{phase}.edge[{len(edges)}]"
                            edge_row = {"index": len(edges)}
                            snapshot["edges"].append(edge_row)
                            edges.append({"native": edge, "row": edge_row,
                                          "reference": persistent(edge, f"{edge_label}.reference")})
                read(f"{label}.face[{face_index}].edge_array", collect_edges)
        bodies = read(f"{phase}.bodies", lambda: typed(part, "IPartDoc").GetBodies2(-1, False), opaque=True)
        if bodies is not MISSING:
            read(f"{phase}.body_array", lambda: require(isinstance(bodies, (tuple, list)) and len(bodies) > 0,
                                                       "owned part body inventory unavailable"))
        for item in edges:
            item["row"].update(edge_evidence(item["native"], f"{phase}.edge[{item['row']['index']}]", features, bodies))
        snapshot["complete"] = len(result["errors"]) == error_start and bool(features)
        snapshot["all_features_rolled_forward"] = snapshot["complete"] and all(
            item["row"].get("rolled_back") is False for item in features)
        return {"features": features, "edges": edges, "bodies": bodies, "snapshot": snapshot}

    def edge_evidence(edge, label, features, bodies):
        evidence = geometry(edge, label)
        body = read(f"{label}.body", lambda: edge.GetBody(), opaque=True)
        evidence["body_source_matches"] = []
        if body is not MISSING and body is not None and isinstance(bodies, (tuple, list)):
            for index, source_body in enumerate(bodies):
                value = read(f"{label}.body_vs[{index}]", lambda source_body=source_body: same(body, source_body, f"s1.{label}.body"))
                if value is True:
                    evidence["body_source_matches"].append(index)
        evidence["owned_body_proven"] = len(evidence["body_source_matches"]) == 1
        if body is not MISSING and body is not None:
            body_references[label] = persistent(body, f"{label}.body_reference")
        faces = read(f"{label}.adjacent_faces", lambda: edge.GetTwoAdjacentFaces2(), opaque=True)
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
                                     lambda feature=feature: same(oldest, feature["native"], f"s1.{label}.oldest"))
                        if value is True:
                            face_row["oldest_owner_matches"].append(feature_index)
                    for owned_face in feature["faces"]:
                        value = read(f"{label}.adjacent[{index}].member[{feature_index},{len(face_row['feature_memberships'])}]",
                                     lambda owned_face=owned_face: same(face, owned_face, f"s1.{label}.face_membership"))
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
    result["selected_feature_inventory_index"] = candidate["row"]["index"]
    result["intended_wizard_inventory_index"] = wizard["row"]["index"]
    if read("safety_before_access", before_access) is MISSING:
        return result
    selected_reference = MISSING
    accessed = None
    confirmed = False
    try:
        result["access_calls"] = 1
        success = read("AccessSelections", lambda: candidate["definition"].AccessSelections(part, None))
        confirmed = success is True
        if confirmed:
            accessed = capture("accessed")
            edge = read("accessed.selected_edge", lambda: typed(candidate["definition"].Edge, "IEdge"), opaque=True)
            if edge is not MISSING:
                selected_reference = persistent(edge, "accessed.selected_edge.reference")
                result["selected_edge"] = edge_evidence(edge, "accessed.selected_edge", accessed["features"], accessed["bodies"])
                result["selected_edge"]["before_inventory_matches"] = []
                for item in before["edges"]:
                    if item["reference"] is MISSING:
                        continue
                    value = read(f"accessed.selected_edge.before[{item['row']['index']}]",
                                 lambda item=item: same(resolve(item["reference"], "accessed.before_edge"), edge, "s1.selected_before"))
                    if value is True:
                        result["selected_edge"]["before_inventory_matches"].append(item["row"]["index"])
                # Resolve the intended Wizard in the accessed inventory rather
                # than assuming an index/name survives rollback unchanged.
                live_wizard = read("accessed.wizard.resolve",
                                   lambda: resolve(wizard["reference"], "accessed.wizard"), opaque=True)
                wizard_indices = []
                if live_wizard is not MISSING:
                    for item in accessed["features"]:
                        if read(f"accessed.wizard.member[{item['row']['index']}]",
                                lambda item=item: same(live_wizard, item["native"], "s1.accessed.wizard")) is True:
                            wizard_indices.append(item["row"]["index"])
                result["selected_edge"]["wizard_inventory_matches"] = wizard_indices
                result["selected_edge"]["wizard_face_association"] = (
                    len(wizard_indices) == 1 and any(
                        wizard_indices[0] in row["feature_memberships"]
                        for row in result["selected_edge"]["adjacent_faces"]
                    )
                )
                diameter = result["selected_edge"]["trimmed_circle"].get("diameter_m")
                result["selected_edge"]["wizard_diameter_differences_m"] = {
                    name: diameter - value for name, value in wizard["row"]["scalars"].items()
                    if name in ("ThreadDiameter", "TapDrillDiameter", "ThruTapDrillDiameter")
                    and diameter is not None
                }
        else:
            result["reason"] = "AccessSelections not confirmed True; no release, retry, or repair."
    finally:
        if confirmed:
            result["release_calls"] = 1
            release = read("ReleaseSelectionAccess", lambda: candidate["definition"].ReleaseSelectionAccess())
            result["release_returned"] = release is None
            if release is not MISSING and release is not None:
                read("ReleaseSelectionAccess.contract",
                     lambda: require(False, "VOID release returned a non-null value; no retry"))
    # Fresh feature/definition reads, never reuse a pre-rollback definition to
    # claim roll-forward. Even a release/reader error retains after evidence.
    after = capture("after")
    result["feature_identity_after"] = []
    for item in before["features"]:
        if item["reference"] is MISSING:
            continue
        def match_feature(item=item):
            restored = resolve(item["reference"], f"after.feature[{item['row']['index']}]")
            matches = [other for other in after["features"]
                       if same(restored, other["native"], "s1.after.feature_inventory")]
            require(len(matches) == 1, "feature absent/ambiguous after rollback")
            other = matches[0]
            owner_unchanged = item["owner"] is None and other["owner"] is None
            owner_indices = item["row"].get("owner_inventory_matches", [])
            if len(owner_indices) == 1 and other["owner"] is not None and other["owner"] is not MISSING:
                original_owner = before["features"][owner_indices[0]]
                owner_unchanged = same(resolve(original_owner["reference"], "after.feature_owner"),
                                       other["owner"], "s1.after.feature_owner")
            result["feature_identity_after"].append({
                "before": item["row"]["index"], "after": other["row"]["index"],
                "scalars_unchanged": item["row"]["scalars"] == other["row"]["scalars"],
                "name_type_unchanged": all(item["row"].get(key) == other["row"].get(key) for key in ("name", "type")),
                "owner_unchanged": owner_unchanged,
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
                       if same(restored_edge, other["native"], "s1.after.physical_edge")]
            require(len(matches) == 1, "physical edge absent/ambiguous after rollback")
            other = matches[0]
            old_body = body_references.get(f"before.edge[{item['row']['index']}]", MISSING)
            new_body = body_references.get(f"after.edge[{other['row']['index']}]", MISSING)
            require(old_body is not MISSING and new_body is not MISSING, "edge body persistence unavailable")
            body_same = same(resolve(old_body, "after.old_body"), resolve(new_body, "after.new_body"),
                             "s1.after.body_identity")
            old_memberships = sorted(sorted(feature_indices.get(index, -1) for index in face["feature_memberships"])
                                     for face in item["row"]["adjacent_faces"])
            new_memberships = sorted(sorted(face["feature_memberships"]) for face in other["row"]["adjacent_faces"])
            result["geometry_identity_after"].append({
                "before": item["row"]["index"], "after": other["row"]["index"],
                "geometry_unchanged": item["row"]["reads"] == other["row"]["reads"],
                "body_same": body_same, "face_feature_memberships_unchanged": old_memberships == new_memberships,
            })
        read(f"after.physical_edge[{item['row']['index']}].comparison", match_edge)
    if selected_reference is not MISSING:
        edge = read("after.selected_edge.resolve", lambda: typed(resolve(selected_reference, "after.selected_edge"), "IEdge"), opaque=True)
        if edge is not MISSING:
            result["selected_edge_after"] = edge_evidence(edge, "after.selected_edge", after["features"], after["bodies"])
            matches = []
            for item in after["edges"]:
                value = read(f"after.selected_edge.member[{item['row']['index']}]",
                             lambda item=item: same(edge, item["native"], "s1.after.selected_edge"))
                if value is True:
                    matches.append(item["row"]["index"])
            result["selected_edge_after"]["inventory_matches"] = matches
    # Native availability is not causal proof. This state only says the
    # bounded access/read/release occurred and its entire evidence is retained.
    result["state"] = "ACCESS_READ_RELEASE_OBSERVED" if confirmed and result.get("release_returned") else "UNAVAILABLE"
    result["roll_forward_witness"] = after["snapshot"]["all_features_rolled_forward"]
    selected = result.get("selected_edge", {})
    restored = result.get("selected_edge_after", {})
    before_matches = selected.get("before_inventory_matches", [])
    before_geometry = before["edges"][before_matches[0]]["row"] if len(before_matches) == 1 else {}
    result["selected_geometry_unchanged"] = (
        bool(before_geometry)
        and before_geometry.get("reads") == selected.get("reads") == restored.get("reads")
    )
    result["clean_comparison"] = (
        confirmed and result.get("release_returned") is True and not result["errors"]
        and after["snapshot"]["all_features_rolled_forward"]
        and len(before["features"]) == len(after["features"]) == len(result["feature_identity_after"])
        and all(row["scalars_unchanged"] and row["name_type_unchanged"]
                and row["owner_unchanged"] and row["definition_state_unchanged"]
                for row in result["feature_identity_after"])
        and len(before["edges"]) == len(after["edges"]) == len(result["geometry_identity_after"])
        and all(row["geometry_unchanged"] and row["body_same"] and row["face_feature_memberships_unchanged"]
                for row in result["geometry_identity_after"])
        and accessed is not None and accessed["snapshot"]["complete"]
        and selected.get("owned_body_proven") is True and restored.get("owned_body_proven") is True
        and selected.get("wizard_face_association") is True
        and len(before_matches) == 1 and len(restored.get("inventory_matches", [])) == 1
        and selected.get("trimmed_circle", {}).get("state") == "FULL_TRIMMED_CIRCLE"
        and restored.get("trimmed_circle", {}).get("state") == "FULL_TRIMMED_CIRCLE"
        and result["selected_geometry_unchanged"]
    )
    return result


def main():
    primary_exception = None
    primary_traceback = None
    report = {
        "kind": "mg-saved-thread-control-s1",
        "status": "running",
        "native_ship": "NOT_EVALUATED",
        "mode": "disposable_copy_access_read_release_no_save",
        "contract": CONTRACT,
        "cases": [],
        "session": {
            "scope": "Exactly two sequential pairs in one attached adapter callback; no reattach between pairs.",
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
            "native_ship": "NOT_EVALUATED",
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
        require(contract == CONTRACT, "committed two-case contract differs from the immutable probe contract")
        report["reads"]["probe_identity"] = file_identity(Path(__file__))
        report["reads"]["contract_identity"] = file_identity(CONTRACT_PATH)
        sys.path[:0] = [str(ROOT), str(ROOT / "cad/scripts")]
        from diagnostics import _script_paths  # noqa: F401
        from diagnostics._owned_native_session import run_owned_diagnostic
        from _com import _early_bound
        import _artifact_cache as cache
        from draw_mg_magnifying_bracket import _mouth_thread_diagnostic

        async def run_pair(adapter, control):
            app = adapter.swApp
            owned = []
            originals = {kind: ROOT / control[kind]["path"] for kind in ("part", "drawing")}
            targets = {}
            copy_root = ROOT / "cad/out/diagnostic-copies/mg-saved-thread-control" / uuid4().hex
            report["copy_root"] = str(copy_root)

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
                    all(key in row["data"] for key in ("path", "title", "type", "dirty"))
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
                    require(Path(data["path"]).resolve().is_relative_to(copy_root.resolve()),
                            f"{label}: owned path escaped unique copy directory")
                    index = candidates[0]
                    require(index not in matched, f"{label}: duplicate live owner")
                    require(same(row["native"], owned[index]["native"], f"{label}.live_vs_owned[{index}]"),
                            f"{label}: live document differs from retained direct OpenDoc6 result")
                    require(data["title"] == owned[index]["data"]["title"],
                            f"{label}: owned document title changed")
                    if clean:
                        require(data["dirty"] is False, f"{label}: dirty owned document is stranded; refusing CloseDoc")
                    matched.add(index)
                return rows

            def open_native(kind, doc_type):
                path = targets[kind]
                readonly = not (control["case"] == "s1" and kind == "part")
                options = 3 if readonly else 1
                row = {"kind": kind, "requested_path": str(path), "options": options}
                report["opens"].append(row)
                # swOpenDocOptions_Silent=1 | swOpenDocOptions_ReadOnly=2.
                result = app.OpenDoc6(str(path), doc_type, options, "", 0, 0)
                require(isinstance(result, tuple) and len(result) == 3,
                        "early-bound OpenDoc6 did not return document/errors/warnings")
                raw, errors, warnings = result
                row["returned_document"] = raw is not None
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
                    owned.append({"native": doc, "data": {key: row[key] for key in ("path", "title", "type")}})
                    row["retained_owned"] = True
                    report["owned_documents"] = [dict(owner["data"]) for owner in owned]
                require(row.get("retained_owned") is True, f"OpenDoc6 did not certify the exact {kind} owner")
                require(type(errors) is int and type(warnings) is int, "OpenDoc6 status codes unavailable")
                row.update(errors=errors, warnings=warnings)
                require(errors == 0, f"OpenDoc6 reported {kind} load errors")
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
                # Refuse redirected cache/SAS configuration; keep canonical
                # archive restore semantics and never mint execution tokens.
                require(not os.environ.get("HARMONIC_CACHE_SAS"), "SAS is forbidden")
                for name, expected in (("HARMONIC_CACHE_ACCOUNT", "stswbuildcache07aba2"),
                                       ("HARMONIC_CACHE_CONTAINER", "buildcache")):
                    require(os.environ.get(name) in (None, "", expected), f"{name} redirects pinned cache")
                for kind in ("drawing", "part"):
                    spec = control[kind]
                    if control["case"] == "s1" and kind == "drawing":
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
                copy_root.mkdir(parents=True, exist_ok=False)
                for kind in ("part", "drawing"):
                    target = copy_root / originals[kind].name
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
                        if control["case"] == "s1":
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

                # These actual native reads enclose the ENTIRE existing call,
                # including its fixed generation boundary, not just generation.
                observe_active_sketch("before_diagnostic_including_generation")
                try:
                    report["diagnostic"] = _mouth_thread_diagnostic(
                        adapter, section, feature_name=control["feature_name"]
                    )
                except BaseException as error:
                    failure("collect", error)
                    raise
                finally:
                    observe_active_sketch("after_diagnostic_including_generation")
                report["thread_ink"] = thread_ink_summary(report["diagnostic"])
                if control["case"] == "s1":
                    if report["thread_ink"]["positive_count_fields"]:
                        report["s1"] = {"state": "STOP_BASELINE_PRIMITIVES",
                                        "reason": "Writable-copy reopening already has primitives; no access performed."}
                    elif report["thread_ink"]["state"] != "OBSERVED_ZERO" or report["errors"]:
                        report["s1"] = {"state": "UNAVAILABLE", "reason": "Baseline or native safety witnesses incomplete."}
                    else:
                        def before_access():
                            live = require_owned_inventory(inventory("before_access"), "before_access")
                            require(len(live) == 2, "both exact owned copies must be live before access")
                            require(all(row.get("warnings") == 0 and type(row.get("warnings")) is int
                                        for row in report["opens"]), "open warnings prevent source intervention")
                            part_mode = observe("before_access.part.IsOpenedReadOnly", lambda: part.IsOpenedReadOnly())
                            drawing_mode = observe("before_access.drawing.IsOpenedReadOnly", lambda: drawing_model.IsOpenedReadOnly())
                            require(part_mode is False and drawing_mode is True, "copy open modes changed before access")
                            live_source = _early_bound(base.ReferencedDocument, "IModelDoc2")
                            require(live_source is not None and same(live_source, part, "before_access.reference")
                                    and canonical(live_source.GetPathName()) == canonical(targets["part"]),
                                    "loaded reference changed before access")
                            require(not report["errors"], "native safety collection failed before access")
                            activate(part, str(targets["part"]), "activate_source_access")

                        report["s1"] = source_intervention(
                            part, control["feature_name"], _early_bound, same, failure, before_access,
                        )
                        if report["s1"]["access_calls"]:
                            activate(drawing_model, str(targets["drawing"]), "activate_after_access")
                            report["after_access_diagnostic"] = _mouth_thread_diagnostic(
                                adapter, section, feature_name=control["feature_name"],
                            )
                            report["after_access_thread_ink"] = thread_ink_summary(report["after_access_diagnostic"])
                            report["s1"]["display_comparison_complete"] = report["after_access_thread_ink"]["complete"]
                            if not report["after_access_thread_ink"]["complete"]:
                                report["s1"]["clean_comparison"] = False
                            if report["after_access_thread_ink"]["positive_count_fields"]:
                                report["s1"]["stop"] = "Inspect actual primitives; positive counts do not establish recovered flanks."
                else:
                    require(report["thread_ink"]["state"] == "PRESENT",
                            "SM positive control did not reproduce observed native primitives")
                report["collection_completed"] = True
            except BaseException as error:
                failure("collect", error)
            finally:
                # CloseDoc may also close hidden docs: EVERY live document must
                # be an exact owned copy with a known Boolean save flag. Only
                # S1 permits known dirty copies; SM still requires all clean.
                for index, owned_row in enumerate(sorted(owned, key=lambda row: row["data"]["type"] != 3)):
                    data = owned_row["data"]
                    closure = {"path": data["path"], "title": data["title"], "status": "stranded_owned"}
                    report["closures"].append(closure)

                    def close_owned():
                        now = require_owned_inventory(inventory(f"before_close_{index}"),
                                                      f"before_close_{index}", clean=control["case"] != "s1")
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
                for control, case in zip((SM_POSITIVE, S1), summary["cases"], strict=True):
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
                                   for key in ("diagnostic", "after_access_diagnostic")) else "observed"
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
                   for key in ("diagnostic", "after_access_diagnostic"))
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
