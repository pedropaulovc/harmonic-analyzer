"""Copy-only cosmetic-thread source-feature A/B/A and native view-data probe.

Run through uv with DRAWING PART --feature NAME. The parent takes the COM seat.
Use --mode definition for a read-only copied-source feature-definition capture.
Use --mode metadata for view-owned annotation width/layer/position metadata only,
without a rebuild, configuration change, suppression, or save.
Use --mode corrected with explicit standard/type/size/minor-diameter inputs to
modify only the copied cosmetic definition, run A/B/A, and verify saved/reopened
definition values. This does not repair an undersized solid thread envelope.
Only a uniquely copied drawing and its uniquely copied part are modified. The
closed drawing is relinked before opening; every view must resolve the copied
part and one configuration. The source feature must be CosmeticThread and initially
unsuppressed; the suppression comparison additionally rejects patterned threads.
No document-display filter is used as a no-ink proof.

GetDisplayData4 covers visible model items; GetPolylines7 covers visible model
edges/silhouettes, not documented cosmetic-thread ownership. Capture both with
native mode/quality/context before, during and after source-feature suppression,
plus PDF vectors/raster. Repeatable changed ink is a positive source-feature
control; unchanged ink remains inconclusive. Changed native data is a candidate
coverage witness, not automatic proof that every changed PDF stroke was captured.
Face boxes are recorded as approximate associated geometry, not thread-ink bounds.
The body metric/topology guard is not a complete B-rep equivalence proof.
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import sys
import tempfile

from _common import CAD_ROOT, _early_bound, check, run_build
from _drawing_common import render_pdf_png
from probe_drawing_primitive_annotations import display_counts
from probe_drawing_thread_ink import ink_difference, vector_witness
from solidworks_mcp.adapters.com_variant import null_variant
import _telemetry


def _numbers(raw):
    values = tuple(float(value) for value in raw or ())
    if not all(math.isfinite(value) for value in values):
        raise ValueError("native view data contains non-finite coordinates")
    return values


def parse_polylines(raw):
    """Decode the documented GetPolylines7 buffer without dropping any record."""
    values = _numbers(raw)
    records, offset = [], 0
    while offset < len(values):
        if len(values) - offset < 2:
            raise ValueError("truncated native polyline header")
        kind, size = values[offset : offset + 2]
        if kind not in (0, 1) or size != (0 if kind == 0 else 12):
            raise ValueError(f"unsupported native polyline geometry: {(kind, size)}")
        offset += 2
        size = int(size)
        if len(values) - offset < size + 7:
            raise ValueError("truncated native polyline geometry/style")
        geometry = values[offset : offset + size]
        offset += size
        style = values[offset : offset + 6]
        count = values[offset + 6]
        offset += 7
        if count < 0 or count != int(count) or len(values) - offset < 3 * count:
            raise ValueError("invalid native polyline point count")
        stop = offset + 3 * int(count)
        records.append(
            {
                "kind": int(kind),
                "geometry": geometry,
                "style": style,
                "points": tuple(values[i : i + 3] for i in range(offset, stop, 3)),
            }
        )
        offset = stop
    return records


def capture_display(data):
    """Retain all ten native primitive inventories, without nominal bounds."""
    data = _early_bound(data, "IDisplayData")
    counts = display_counts(data)
    if any(count < 0 for count in counts.values()):
        raise RuntimeError("native display-data count is negative")
    result = {
        "counts": counts,
        "text": [str(data.GetTextAtIndex(i)) for i in range(counts["text"])],
    }
    for kind, getter in (
        ("lines", "GetLineAtIndex3"),
        ("arcs", "GetArcAtIndex2"),
        ("polylines", "GetPolylineAtIndex2"),
        ("triangles", "GetTriangleAtIndex"),
        ("arrowheads", "GetArrowHeadAtIndex2"),
        ("polygons", "GetPolygonAtIndex"),
        ("ellipses", "GetEllipseAtIndex2"),
        ("parabolas", "GetParabolaAtIndex"),
        ("points", "GetPointAtIndex"),
    ):
        result[kind] = [_numbers(getattr(data, getter)(i)) for i in range(counts[kind])]
    return result


def observe(operation):
    """Capture a diagnostic call-shape failure, never substitute fabricated data."""
    try:
        return operation()
    except Exception as error:
        return {"error": repr(error)}


def capture_polylines(view):
    raw = view.GetPolylines7(1)  # exclude crosshatching; generated return + out tuple
    if not isinstance(raw, tuple) or len(raw) != 2:
        raise RuntimeError(
            f"unexpected GetPolylines7 return shape: {type(raw).__name__}"
        )
    edges, values = raw
    records = parse_polylines(values)
    edge_slots = tuple(edges or ())
    return {
        "records": records,
        "edge_slot_count": len(edge_slots),
        "null_edge_slots": [i for i, edge in enumerate(edge_slots) if edge is None],
    }


def thread_visual_metadata(annotation):
    """Observe native width/layer defaults without interpreting undefined flags.

    GetVisualProperties is color/style/width/layerID/layerOverride. The last
    field is undefined on no-layer annotations; preserve it, do not use it as
    a default-width certificate. GetPosition does not document cosmetic-thread
    support, so an empty native position is evidence, not a guessed anchor.
    """
    properties = tuple(annotation.GetVisualProperties() or ())
    if len(properties) != 5:
        raise RuntimeError("thread visual properties must contain five integers")
    return {
        "layer": str(annotation.Layer),
        "width": int(annotation.Width),
        "visual_properties": properties,
        "position": _numbers(annotation.GetPosition()),
    }


def capture_thread_metadata(adapter, views):
    """Read actual annotation context without mutating or saving any document."""
    result = {}
    for name, view in views.items():
        rows = []
        for raw in view.GetAnnotationsByType(1) or ():
            annotation = _early_bound(raw, "IAnnotation")
            specific = _early_bound(annotation.GetSpecificAnnotation(), "ICThread")
            if (
                int(annotation.OwnerType) != 0
                or int(adapter.swApp.IsSame(annotation.Owner, view)) != 1
                or int(adapter.swApp.IsSame(specific.GetAnnotation(), annotation)) != 1
            ):
                raise RuntimeError(
                    "cosmetic-thread metadata native owner/identity differs"
                )
            rows.append(
                {
                    "name": str(annotation.GetName()),
                    "visible": int(annotation.Visible),
                    "dangling": bool(annotation.IsDangling()),
                    **thread_visual_metadata(annotation),
                    "native_display_counts": display_counts(
                        _early_bound(annotation.GetDisplayData(), "IDisplayData")
                    ),
                }
            )
        result[name] = rows
    if not any(result.values()):
        raise RuntimeError("copied drawing contains no cosmetic-thread annotations")
    return result


def capture_view(adapter, view):
    threads = []
    for raw in view.GetAnnotationsByType(1) or ():
        annotation = _early_bound(raw, "IAnnotation")
        specific = _early_bound(annotation.GetSpecificAnnotation(), "ICThread")
        if (
            int(annotation.OwnerType) != 0
            or int(adapter.swApp.IsSame(annotation.Owner, view)) != 1
        ):
            raise RuntimeError("cosmetic thread has a foreign native view owner")
        if int(adapter.swApp.IsSame(specific.GetAnnotation(), annotation)) != 1:
            raise RuntimeError(
                "cosmetic thread specific interface has a foreign annotation"
            )
        entities = tuple(annotation.GetAttachedEntities3() or ())
        types = tuple(annotation.GetAttachedEntityTypes() or ())
        if (
            len(entities) != len(types)
            or len(types) != annotation.GetAttachedEntityCount3()
        ):
            raise RuntimeError("cosmetic thread attachment inventory is incomplete")
        callout = specific.ThreadCallout
        threads.append(
            {
                "name": str(annotation.GetName()),
                "visible": int(annotation.Visible),
                "dangling": bool(annotation.IsDangling()),
                "attachment_types": types,
                "null_entity_slots": [
                    i for i, entity in enumerate(entities) if entity is None
                ],
                "associated_face_boxes_approximate": [
                    _numbers(_early_bound(entity, "IFace2").GetBox())
                    for kind, entity in zip(types, entities)
                    if kind == 2 and entity is not None
                ],
                "pattern_count": int(specific.GetPatternedTransformsCount()),
                "callout": None
                if callout is None
                else {
                    "text": str(_early_bound(callout, "INote").GetText()),
                    "extent": _numbers(_early_bound(callout, "INote").GetExtent()),
                },
                "generic_display": observe(
                    lambda: capture_display(annotation.GetDisplayData())
                ),
                "specific_display": observe(
                    lambda: capture_display(specific.GetDisplayData())
                ),
            }
        )
    return {
        "position": _numbers(view.Position),
        "outline": _numbers(view.GetOutline()),
        "scale": _numbers(view.ScaleRatio),
        "angle": float(view.Angle),
        "reference": str(view.GetReferencedModelName()),
        "configuration": str(view.ReferencedConfiguration),
        "model_to_view": _numbers(
            _early_bound(view.ModelToViewTransform, "IMathTransform").ArrayData
        ),
        "display_mode": int(view.GetDisplayMode2()),
        "faceted": bool(view.GetFacettedHlrDisplay()),
        "thread_high_quality": bool(view.GetCThreadQuality()),
        "threads": threads,
        "model_display": observe(lambda: capture_display(view.GetDisplayData4())),
        "model_polylines": observe(lambda: capture_polylines(view)),
    }


def _activate_copy(adapter, path):
    raw, errors = adapter.swApp.ActivateDoc3(path.name, False, 2, 0)
    if raw is None or int(errors) != 0:
        raise RuntimeError(f"copy activation failed: {path}, errors={errors}")
    model = _early_bound(raw, "IModelDoc2")
    if Path(model.GetPathName()).resolve() != path:
        raise RuntimeError(
            "SolidWorks activated a document other than the intended copy"
        )
    adapter.currentModel = model
    return model


def body_metric_guard(model):
    bodies = tuple(_early_bound(model, "IPartDoc").GetBodies2(0, False) or ())
    if not bodies:
        raise RuntimeError("source-feature control requires at least one solid body")
    values = []
    for raw in bodies:
        body = _early_bound(raw, "IBody2")
        mass = _numbers(body.GetMassProperties(1.0))
        if len(mass) != 12 or mass[3] <= 0:
            raise RuntimeError("source-feature control body mass metrics are invalid")
        values.append((int(body.GetFaceCount()), int(body.GetEdgeCount()), mass))
    return values, bodies


def compare_body_metrics(before, after):
    """Numerical guard, not bitwise equality of recomputed native moments.

    The no-change control thread-view-5i1j861l retained volume/area exactly but
    differed by 1-2 ULP in nonzero moments and ~1e-28 in near-zero products.
    Centre tolerance is 1nm (the repository's geometric checks); volume/area/mass
    use relative 1e-12 with NO absolute floor. Products of inertia use the largest
    diagonal inertia component's scale, so numerical zero is not a singular case.
    """
    if len(before) != len(after):
        raise RuntimeError("copied part solid-body count changed")
    differences = []
    for original, observed in zip(before, after, strict=True):
        if original[:2] != observed[:2]:
            raise RuntimeError("copied part face/edge topology counts changed")
        old, new = original[2], observed[2]
        scale = max(abs(value) for value in old[6:9])
        tolerances = (
            [1e-9] * 3
            + [abs(value) * 1e-12 for value in old[3:6]]
            + [scale * 1e-12] * 6
        )
        deltas = [b - a for a, b in zip(old, new, strict=True)]
        if any(
            abs(delta) > limit for delta, limit in zip(deltas, tolerances, strict=True)
        ):
            raise RuntimeError(
                f"copied part mass metrics changed beyond numeric guard: deltas={deltas}, limits={tolerances}"
            )
        differences.append({"deltas": deltas, "absolute_limits": tolerances})
    return differences


def match_body_identities(adapter, originals, observed):
    indices = []
    for original in originals:
        matches = [
            i
            for i, body in enumerate(observed)
            if int(adapter.swApp.IsSame(original, body)) == 1
        ]
        if len(matches) != 1:
            raise RuntimeError(
                "copied part native body identity was replaced or ambiguous"
            )
        indices.extend(matches)
    if len(set(indices)) != len(observed):
        raise RuntimeError("copied part native body inventory changed")
    return indices


def check_body_observation(adapter, baseline, observed, identity_mode=None):
    """Calibrate identity on a healthy rebuild in the same open copied part.

    An identity exclusion is available only when that control regenerates its
    sole body. Multiple regenerated bodies have no proven correspondence here.
    Later identity loss after a stable control stops the experiment, without
    asserting that it proves a material geometry change.
    """
    before_metrics, before_bodies = baseline
    after_metrics, after_bodies = observed
    if identity_mode == "healthy_rebuild_regenerates_single_body":
        return identity_mode, compare_body_metrics(before_metrics, after_metrics)
    try:
        indices = match_body_identities(adapter, before_bodies, after_bodies)
    except RuntimeError:
        if (
            identity_mode is not None
            or len(before_bodies) != 1
            or len(after_bodies) != 1
        ):
            raise RuntimeError(
                "native body identity witness unavailable; geometry change not inferred"
            )
        checks = compare_body_metrics(before_metrics, after_metrics)
        return "healthy_rebuild_regenerates_single_body", checks
    checks = compare_body_metrics(before_metrics, [after_metrics[i] for i in indices])
    return "stable_in_healthy_rebuild", checks


def set_thread_state(model, feature_name, state):
    if state not in (0, 1):
        raise ValueError("thread source-feature state must suppress or unsuppress")
    feature = _early_bound(
        _early_bound(model, "IPartDoc").FeatureByName(feature_name), "IFeature"
    )
    if feature.GetTypeName2() != "CosmeticThread":
        raise RuntimeError("source-feature control target is not CosmeticThread")
    # swSuppressFeature=0, swUnSuppressFeature=1; swThisConfiguration=1.
    if not feature.SetSuppression2(state, 1, null_variant()):
        raise RuntimeError("native cosmetic-thread suppression change was rejected")
    if not model.EditRebuild3():
        raise RuntimeError("copied part rebuild failed")
    actual = tuple(feature.IsSuppressed2(1, null_variant()) or ())
    if actual != (state == 0,):
        raise RuntimeError(f"cosmetic-thread suppression readback differs: {actual}")


def prepare_phase(model, feature_name, phase):
    if phase == "present":
        # Activation alone is not a healthy rebuild control if already active.
        if not model.EditRebuild3():
            raise RuntimeError("copied part healthy-control rebuild failed")
        return
    set_thread_state(model, feature_name, {"suppressed": 0, "present_again": 1}[phase])


def feature_definition(feature):
    """Read documented scalar values without AccessSelections/rollback/mutation."""
    data = _early_bound(feature.GetDefinition(), "ICosmeticThreadFeatureData")
    return {
        "diameter_m": float(data.Diameter),
        "diameter_type": int(data.DiameterType),
        "blind_depth_m": float(data.BlindDepth),
        "apply_thread": int(data.ApplyThread),
        "standard": int(data.Standard),
        "standard_type": str(data.StandardType),
        "size": str(data.Size),
    }


def correction_request(args, original):
    if (
        args.standard is None
        or not args.standard_type
        or not args.thread_size
        or args.minor_diameter_mm is None
        or not math.isfinite(args.minor_diameter_mm)
        or args.minor_diameter_mm <= 0
    ):
        raise ValueError(
            "corrected mode requires explicit standard/type/size and positive minor diameter"
        )
    if original["diameter_type"] != 3:
        raise ValueError(
            "minor-diameter control requires the native Boss/MinorDiameter type"
        )
    return {
        **original,
        "standard": args.standard,
        "standard_type": args.standard_type,
        "size": args.thread_size,
        "diameter_m": args.minor_diameter_mm / 1000.0,
    }


def assert_definition(actual, requested):
    for key, expected in requested.items():
        observed = actual[key]
        if key in ("diameter_m", "blind_depth_m"):
            if math.isfinite(observed) and abs(observed - expected) <= 1e-12:
                continue
            raise RuntimeError(
                f"native thread definition differs at {key}: {observed} != {expected}"
            )
        if observed != expected:
            raise RuntimeError(
                f"native thread definition differs at {key}: {observed!r} != {expected!r}"
            )


def correct_definition(model, feature, requested, record):
    """Modify the copied native feature, recording actual returns before gating."""
    data = _early_bound(feature.GetDefinition(), "ICosmeticThreadFeatureData")
    if not data.AccessSelections(model, None):
        raise RuntimeError("native thread definition selection access rejected")
    access_state = "held"
    try:
        data.Standard = requested["standard"]
        data.StandardType = requested["standard_type"]
        data.Size = requested["size"]
        data.Diameter = requested["diameter_m"]
        data.ApplyThread = requested["apply_thread"]
        data.BlindDepth = requested["blind_depth_m"]
        # ModifyDefinition consumes the access/rollback transaction, including
        # its documented failure state; discard the copy on any failed gate.
        access_state = "submitted"
        record["modify_result"] = bool(feature.ModifyDefinition(data, model, None))
    finally:
        if access_state == "held":
            data.ReleaseSelectionAccess()
    if not record["modify_result"]:
        raise RuntimeError("native thread ModifyDefinition rejected correction")
    record["rebuild_result"] = bool(model.EditRebuild3())
    record["feature_error"] = tuple(feature.GetErrorCode2())
    record["readback"] = feature_definition(feature)
    if not record["rebuild_result"] or record["feature_error"][0] != 0:
        raise RuntimeError("corrected cosmetic thread has a native rebuild error")
    assert_definition(record["readback"], requested)


def save_native_copy(model, path):
    if Path(model.GetPathName()).resolve() != path:
        raise RuntimeError("refusing to save a model outside the verified copy path")
    saved, errors, warnings = model.Save3(1, 0, 0)
    if not saved or errors:
        raise RuntimeError(
            f"copied native document Save3 failed: {(saved, errors, warnings)}"
        )
    return {"save_warnings": warnings}


async def close_copies(adapter, documents):
    """Close only verified copy handles, regardless of which copy was active."""
    for model, path in documents:
        if model is None:
            continue
        if Path(model.GetPathName()).resolve() != path:
            raise RuntimeError(
                "refusing to close a model outside the verified copy paths"
            )
        adapter.currentModel = model
        check("close thread source-feature copy", await adapter.close_model(save=False))


def save_phase(model, drawing_path, pdf_path):
    """Save the open copy in place; each phase exports to a never-used PDF path."""
    if Path(model.GetPathName()).resolve() != drawing_path:
        raise RuntimeError("refusing to save a model outside the verified copy path")
    if pdf_path.exists():
        raise RuntimeError("source-feature phase PDF target already exists")
    # Save3 is the documented in-place save; deleting an open native file fails.
    saved, errors, warnings = model.Save3(1, 0, 0)  # swSaveAsOptions_Silent
    if not saved or errors:
        raise RuntimeError(f"copied drawing Save3 failed: {(saved, errors, warnings)}")
    pdf_result = model.SaveAs3(str(pdf_path), 0, 0)
    if not pdf_path.is_file() or pdf_path.stat().st_size == 0:
        raise RuntimeError(f"PDF export produced no nonempty file: {pdf_result}")
    return {"save_warnings": warnings, "pdf_save_result": pdf_result}


def _multiset(value):
    return Counter(json.dumps(item, sort_keys=True) for item in value)


def data_difference(first, second):
    """Compare every captured primitive; native errors remain explicitly inconclusive."""
    if "error" in first or "error" in second:
        return {"outcome": "capture_error", "first": first, "second": second}
    labels = set(first) | set(second)
    changes = {}
    for label in sorted(labels - {"counts", "edge_slot_count", "null_edge_slots"}):
        before, after = (
            _multiset(first.get(label, ())),
            _multiset(second.get(label, ())),
        )
        removed, added = (
            list((before - after).elements()),
            list((after - before).elements()),
        )
        if removed or added:
            changes[label] = {
                "removed": [json.loads(item) for item in removed],
                "added": [json.loads(item) for item in added],
            }
    return {"outcome": "changed" if changes else "unchanged", "changes": changes}


def ink_outcome(phases, repeat_ink, suppression_ink):
    first = phases["present"]["pdf_vectors"]["sha256"]
    if (
        repeat_ink["difference_box_pixels"] is not None
        or first != phases["present_again"]["pdf_vectors"]["sha256"]
    ):
        return "inconclusive_repeat_ink_change"
    if (
        suppression_ink["difference_box_pixels"] is not None
        or first != phases["suppressed"]["pdf_vectors"]["sha256"]
    ):
        return "repeatable_source_feature_ink_change"
    return "inconclusive_no_source_feature_ink_change"


def view_context_differences(first, second):
    """Report native context drift separately from thread-owned display ink."""
    if set(first) != set(second):
        raise RuntimeError("thread control changed the native view inventory")
    fields = (
        "position",
        "outline",
        "scale",
        "angle",
        "reference",
        "configuration",
        "display_mode",
        "faceted",
        "thread_high_quality",
    )
    return {
        name: {
            field: {"before": row[field], "after": second[name][field]}
            for field in fields
            if row[field] != second[name][field]
        }
        for name, row in first.items()
        if any(row[field] != second[name][field] for field in fields)
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("drawing", type=Path)
    parser.add_argument("part", type=Path)
    parser.add_argument("--feature", required=True)
    parser.add_argument(
        "--mode",
        choices=("suppression", "definition", "corrected", "metadata"),
        default="suppression",
    )
    parser.add_argument("--standard", type=int)
    parser.add_argument("--standard-type")
    parser.add_argument("--thread-size")
    parser.add_argument("--minor-diameter-mm", type=float)
    parser.add_argument("--worker", action="store_true")
    args = parser.parse_args()
    source, source_part = (
        args.drawing.resolve(strict=True),
        args.part.resolve(strict=True),
    )
    if source.suffix.upper() != ".SLDDRW" or source_part.suffix.upper() != ".SLDPRT":
        raise ValueError("thread-view probe requires a native drawing and native part")
    if not args.worker:
        sys.path.insert(0, str(CAD_ROOT.parent))
        import dodo

        command = [
            sys.executable,
            str(Path(__file__).resolve()),
            str(source),
            str(source_part),
            "--feature",
            args.feature,
            "--mode",
            args.mode,
            "--worker",
        ]
        for flag, value in (
            ("--standard", args.standard),
            ("--standard-type", args.standard_type),
            ("--thread-size", args.thread_size),
            ("--minor-diameter-mm", args.minor_diameter_mm),
        ):
            if value is not None:
                command.extend((flag, str(value)))
        dodo._run(
            command,
            "thread native-view source-feature control",
            log_stem="thread-view-coverage",
            com=True,
        )
        return 0
    if not os.environ.get("HARMONIC_COM_SEAT"):
        raise RuntimeError("--worker requires the machine-global COM seat")

    async def probe(adapter):
        root = CAD_ROOT / "out/reports"
        root.mkdir(parents=True, exist_ok=True)
        folder = Path(tempfile.mkdtemp(prefix="thread-view-", dir=root)).resolve()
        copy, part_copy = (
            folder / f"{folder.name}-{path.name}" for path in (source, source_part)
        )
        hashes = {
            path: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (source, source_part)
        }
        report = {
            "source": str(source),
            "source_part": str(source_part),
            "copy": str(copy),
            "part_copy": str(part_copy),
            "feature": args.feature,
            "phases": {},
        }
        part_model = drawing_model = None
        try:
            shutil.copy2(source_part, part_copy)
            shutil.copy2(source, copy)
            if not adapter.swApp.ReplaceReferencedDocument(
                str(copy), str(source_part), str(part_copy)
            ):
                raise RuntimeError("closed copied drawing reference replacement failed")
            check(
                "open isolated thread drawing copy", await adapter.open_model(str(copy))
            )
            if Path(adapter.currentModel.GetPathName()).resolve() != copy:
                raise RuntimeError("opened drawing is not the intended isolated copy")
            drawing_model = adapter.currentModel
            drawing = _early_bound(adapter.currentModel, "IDrawingDoc")
            sheets = tuple(drawing.GetViews() or ())
            if len(sheets) != 1:
                raise RuntimeError(
                    "source-feature control requires exactly one drawing sheet"
                )
            views = {}
            for raw in sheets[0][1:]:
                view = _early_bound(raw, "IView")
                model = _early_bound(view.ReferencedDocument, "IModelDoc2")
                if Path(model.GetPathName()).resolve() != part_copy:
                    raise RuntimeError(
                        "copied drawing still references an unisolated source model"
                    )
                name = str(view.GetName2())
                if name in views:
                    raise RuntimeError("copied drawing repeats a native view name")
                views[name] = view
                part_model = model
            if not views:
                raise RuntimeError("copied drawing contains no model views")
            configurations = {
                str(view.ReferencedConfiguration) for view in views.values()
            }
            if len(configurations) != 1 or not all(configurations):
                raise RuntimeError(
                    "source-feature control requires one explicit part configuration"
                )
            if args.mode == "metadata":
                report["annotation_metadata"] = capture_thread_metadata(adapter, views)
                report["outcome"] = "native_thread_annotation_metadata_captured"
                return {"report": str(folder / "coverage.json")}
            part_model = _activate_copy(adapter, part_copy)
            expected_configuration = next(iter(configurations))
            manager = _early_bound(
                part_model.ConfigurationManager, "IConfigurationManager"
            )
            active_configuration = str(
                _early_bound(manager.ActiveConfiguration, "IConfiguration").Name
            )
            report["configuration_activation"] = {
                "expected": expected_configuration,
                "before": active_configuration,
                "active_document_path": str(
                    _early_bound(adapter.swApp.ActiveDoc, "IModelDoc2").GetPathName()
                ),
                "active_document_same": int(
                    adapter.swApp.IsSame(adapter.swApp.ActiveDoc, part_model)
                ),
            }
            if active_configuration != expected_configuration:
                shown = bool(part_model.ShowConfiguration2(expected_configuration))
                report["configuration_activation"]["show_result"] = shown
                if not shown:
                    raise RuntimeError(
                        "copied part ShowConfiguration2 rejected configuration"
                    )
            actual_configuration = str(
                _early_bound(manager.ActiveConfiguration, "IConfiguration").Name
            )
            if actual_configuration != expected_configuration:
                raise RuntimeError("copied part active configuration readback differs")
            rebuilt = bool(part_model.EditRebuild3())
            report["configuration_activation"]["rebuild_result"] = rebuilt
            if not rebuilt:
                raise RuntimeError("copied part initial EditRebuild3 rejected rebuild")
            feature = _early_bound(
                _early_bound(part_model, "IPartDoc").FeatureByName(args.feature),
                "IFeature",
            )
            if feature.GetTypeName2() != "CosmeticThread" or tuple(
                feature.IsSuppressed2(1, null_variant()) or ()
            ) != (False,):
                raise RuntimeError(
                    "control requires an initially unsuppressed CosmeticThread feature"
                )
            baseline_metrics, baseline_bodies = body_metric_guard(part_model)
            report["body_metric_guard"] = baseline_metrics
            report["source_feature_definition"] = feature_definition(feature)
            if args.mode == "definition":
                report["outcome"] = "source_feature_definition_captured"
                return {"report": str(folder / "coverage.json")}
            if args.mode == "corrected":
                requested = correction_request(
                    args, report["source_feature_definition"]
                )
                report["correction"] = {"requested": requested}
                correct_definition(part_model, feature, requested, report["correction"])
                corrected_metrics, baseline_bodies = body_metric_guard(part_model)
                report["correction"]["body_metric_checks"] = compare_body_metrics(
                    baseline_metrics, corrected_metrics
                )
                baseline_metrics = corrected_metrics
                report["body_identity_scope"] = (
                    "healthy rebuild and suppression after cosmetic definition edit; no identity claim across reopen"
                )
            for phase, state in (
                ("present", 1),
                ("suppressed", 0),
                ("present_again", 1),
            ):
                part_model = _activate_copy(adapter, part_copy)
                prepare_phase(part_model, args.feature, phase)
                observed_metrics, observed_bodies = body_metric_guard(part_model)
                report.setdefault("body_metric_observations", {})[phase] = (
                    observed_metrics
                )
                identity_mode, checks = check_body_observation(
                    adapter,
                    (baseline_metrics, baseline_bodies),
                    (observed_metrics, observed_bodies),
                    report.get("body_identity_mode"),
                )
                report["body_identity_mode"] = identity_mode
                report.setdefault("body_metric_checks", {})[phase] = checks
                model = _activate_copy(adapter, copy)
                if not model.EditRebuild3():
                    raise RuntimeError("copied drawing rebuild failed")
                model.ViewZoomtofit2()  # documented GetPolylines7 full-data precondition
                model.GraphicsRedraw2()
                row = {
                    "suppressed": state == 0,
                    "views": {
                        key: capture_view(adapter, view) for key, view in views.items()
                    },
                }
                report["phases"][phase] = row
                if phase == "present":
                    matched = [
                        thread
                        for value in row["views"].values()
                        for thread in value["threads"]
                        if thread["name"] == args.feature
                    ]
                    if not matched or any(
                        thread["pattern_count"]
                        or thread["dangling"]
                        or thread["visible"] != 1
                        for thread in matched
                    ):
                        raise RuntimeError(
                            "control requires visible seed-feature annotation inventory without patterns"
                        )
                pdf = folder / f"{phase}.pdf"
                row["save"] = save_phase(model, copy, pdf)
                render_pdf_png(pdf, folder / f"{phase}.png")
                row["pdf_vectors"] = vector_witness(pdf)
            if args.mode == "corrected":
                part_model = _activate_copy(adapter, part_copy)
                report["correction"]["save"] = save_native_copy(part_model, part_copy)
                await close_copies(
                    adapter, ((drawing_model, copy), (part_model, part_copy))
                )
                drawing_model = part_model = None
                check(
                    "reopen corrected part copy",
                    await adapter.open_model(str(part_copy)),
                )
                part_model = _early_bound(adapter.currentModel, "IModelDoc2")
                if Path(part_model.GetPathName()).resolve() != part_copy:
                    raise RuntimeError(
                        "reopened corrected part is not the intended copy"
                    )
                reopened_feature = _early_bound(
                    _early_bound(part_model, "IPartDoc").FeatureByName(args.feature),
                    "IFeature",
                )
                report["correction"]["reopened_definition"] = feature_definition(
                    reopened_feature
                )
                assert_definition(
                    report["correction"]["reopened_definition"], requested
                )
                reopened_metrics, _reopened_bodies = body_metric_guard(part_model)
                report["correction"]["reopened_body_metric_checks"] = (
                    compare_body_metrics(baseline_metrics, reopened_metrics)
                )
            phases = report["phases"]
            report["repeat_ink"] = ink_difference(
                folder / "present.png", folder / "present_again.png"
            )
            report["suppression_ink"] = ink_difference(
                folder / "present.png", folder / "suppressed.png"
            )
            report["native_differences"] = {
                key: {
                    kind: {
                        "suppressed": data_difference(
                            phases["present"]["views"][key][kind],
                            phases["suppressed"]["views"][key][kind],
                        ),
                        "repeat": data_difference(
                            phases["present"]["views"][key][kind],
                            phases["present_again"]["views"][key][kind],
                        ),
                    }
                    for kind in ("model_display", "model_polylines")
                }
                for key in views
            }
            report["view_context_differences"] = {
                phase: view_context_differences(
                    phases["present"]["views"], phases[phase]["views"]
                )
                for phase in ("suppressed", "present_again")
            }
            if any(report["view_context_differences"].values()):
                report["outcome"] = "inconclusive_view_context_change"
                raise RuntimeError(
                    "source-feature view context changed; A/B cannot isolate thread ink"
                )
            report["outcome"] = ink_outcome(
                phases, report["repeat_ink"], report["suppression_ink"]
            )
            if report["outcome"] == "inconclusive_repeat_ink_change":
                raise RuntimeError(
                    "source-feature A/A repeat differs; A/B cannot isolate thread ink"
                )
        except Exception as error:
            report["error"] = repr(error)
            raise
        finally:
            try:
                await close_copies(
                    adapter, ((drawing_model, copy), (part_model, part_copy))
                )
            finally:
                report["source_unchanged"] = {
                    str(path): hashlib.sha256(path.read_bytes()).hexdigest() == digest
                    for path, digest in hashes.items()
                }
                (folder / "coverage.json").write_text(
                    json.dumps(report, indent=2), encoding="utf-8"
                )
                _telemetry.info(f"thread view coverage observations: {folder}")
                if not all(report["source_unchanged"].values()):
                    raise RuntimeError("source-feature probe changed source bytes")
        return {"report": str(folder / "coverage.json")}

    _telemetry.set_service("drawing-thread-view-probe")
    return run_build(probe)


if __name__ == "__main__":
    raise SystemExit(main())
