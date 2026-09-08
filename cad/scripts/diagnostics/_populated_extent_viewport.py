"""One retained tube input and viewport-only A/B/A observations, never fit approval."""

from copy import deepcopy
from enum import StrEnum
import hashlib
import json
import math
from pathlib import Path
import re

from _common import _early_bound
import _drawing_template_viewport as viewport
from solidworks_mcp.adapters.com_variant import double_array
from diagnostics import _baked_template_gaps as gaps
from diagnostics import _baked_template_layout as layout
from diagnostics import _material_template_sources as sources
from diagnostics import probe_prepared_viewport as prepared

RETAINED_REVISION = "2ce7e15e8855ff2aee982a6b51303895aea0a222"
DERIVED_SHA256 = "97a59b4f1d39994d522b7220fb89e0cb026b47d253031d5c54a2107872ff5c92"


class State(StrEnum):
    BLANK = "blank"
    POPULATED = "populated"


def _read(path, digest):
    if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise ValueError("retained viewport evidence requires lowercase SHA256")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != digest:
        raise RuntimeError(f"retained viewport evidence SHA256 differs: {path}")
    return json.loads(raw)


def read_inputs(template, template_sha, receipt, receipt_sha, owner_sha, blank_sha):
    """Validate historical copy proof without opening any old producer/token path."""
    from _drawing_sheet_setup import PROJECT_DRWDOT

    if hashlib.sha256(template.read_bytes()).hexdigest() != template_sha:
        raise RuntimeError("retained derived template SHA256 differs")
    receipt = Path(receipt).resolve(strict=True)
    owner_path, blank_path = (
        receipt.parent / "ownership.json",
        template.parent / "template-layout.json",
    )
    report = _read(receipt, receipt_sha)
    owner, blank = _read(owner_path, owner_sha), _read(blank_path, blank_sha)
    try:
        gaps.read_population_report(
            receipt,
            receipt_sha,
            hashlib.sha256(PROJECT_DRWDOT.read_bytes()).hexdigest(),
        )
        if (
            report["revision"] != RETAINED_REVISION
            or report["population"] != "material-finish"
            or report["status"] != "failed"
            or report["targets"] != list(sources.TARGETS)
            or len(report["trials"]) != 3
            or blank["status"] != "passed"
            or blank["revision"] != RETAINED_REVISION
            or blank["layout_policy"] != "material-finish"
            or Path(blank["derived_template"]).resolve() != template
            or blank["derived_sha256"] != template_sha
            or template_sha != DERIVED_SHA256
            or blank["inputs_before"] != blank["inputs_after"]
            or owner["cleanup_error"] is not None
            or owner["baseline_initial"] != []
            or owner["final_inventory"] != []
        ):
            raise RuntimeError(
                "retained tube requires exact terminal blank/population/ownership evidence"
            )
        if set(owner["source_hashes"]) != set(report["inputs_before"]):
            raise RuntimeError("retained ownership source inventory differs")
        for path, digest in report["inputs_before"].items():
            row = owner["source_hashes"][path]
            if row != {"before": digest, "after": digest, "unchanged": True}:
                raise RuntimeError("retained ownership source preservation differs")
        trials = {row["target"]: row for row in report["trials"]}
        if set(trials) != set(sources.TARGETS):
            raise RuntimeError("retained population target inventory differs")
        tube = trials["tube_frame"]
        source = Path(tube["source_copy"]).resolve(strict=True)
        digest = sources.TARGETS["tube_frame"].source_sha256
        if (
            not source.is_relative_to(receipt.parent)
            or source.suffix.lower() != ".sldprt"
            or tube["status"] != "observed"
            or tube["copy_hashes"] != {"initial": digest, "final": digest}
            or hashlib.sha256(source.read_bytes()).hexdigest() != digest
            or tube["explicit_source_manifest"]["sha256"] != digest
            or tube["view_scale"] != [1.0, 10.0]
            or tube["cold_delta"]["changed_leaf_count"] != 0
            or tube["cold_export_delta"]["changed_leaf_count"] != 0
            or tube["png_delta"]["changed_pixel_count"] != 0
            or tube["printed"]["classification"] != "unchanged"
            or tube["linked_fields"]["built"] != tube["linked_fields"]["cold"]
            or any(
                tube[key] != tube["source_before"]
                for key in ("source_after", "source_reopened", "source_after_cold_pdf")
            )
        ):
            raise RuntimeError("retained tube lacks exact copy/source/cold persistence")
        template_pins = {
            Path(p).resolve(): sha
            for p, sha in report["inputs_before"].items()
            if p.lower().endswith(".drwdot")
        }
        if template_pins.get(template) != template_sha:
            raise RuntimeError("retained population names a different derived template")
        return {
            "scope": "retained diagnostic tube copy, not a current production execution token",
            "source": str(source),
            "expected": {
                str(source): digest,
                str(receipt): receipt_sha,
                str(owner_path): owner_sha,
                str(blank_path): blank_sha,
            },
            "original_issues": tube["acceptance_issues"],
            "original_blank": report["setups"]["tube_frame"][
                "normalized_blank_defaults"
            ],
            "original_loaded": tube["linked_fields"]["built"],
        }
    except (KeyError, TypeError, ValueError) as error:
        raise RuntimeError(
            "retained tube copy-proof receipt is incomplete or malformed"
        ) from error


def snapshot(adapter, state):
    """Exact anchors/display data, plus raw GetExtent kept separately observable."""
    from diagnostics.probe_populated_template import preferences

    adapter.ownership.assert_current_owned()
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    groups = tuple(_early_bound(model, "IDrawingDoc").GetViews() or ())
    count = 1 if state is State.BLANK else 2
    if len(groups) != 1 or len(groups[0]) != count:
        raise RuntimeError(
            "viewport control has wrong exact blank/populated view count"
        )
    notes, handles, finishes = layout.note_inventory(adapter)
    _, geometry = layout.cells.template_lines(adapter)
    views = [_early_bound(raw, "IView") for raw in groups[0]]
    view_rows = []
    for view in views[1:]:
        scale = view.ScaleDecimal
        if type(scale) not in (int, float) or not math.isfinite(scale) or scale <= 0:
            raise RuntimeError("viewport control has invalid drawing view scale")
        view_rows.append(
            {
                "name": str(view.GetName2()),
                "position": layout.cells.finite(
                    view.Position, 2, "drawing view position"
                ),
                "scale": scale,
                "model_to_view_transform": layout.cells.finite(
                    view.ModelToViewTransform.ArrayData,
                    16,
                    "drawing model-to-view transform",
                ),
                "configuration": str(view.ReferencedConfiguration),
                "source": str(view.ReferencedDocument.GetPathName()),
            }
        )
    bank = {"sheet_view": views[0], "model": model}
    for name, pair in handles.items():
        bank[f"note:{name}"], bank[f"owner:{name}"] = pair
    for index, view in enumerate(views[1:]):
        bank[f"view:{index}"] = view
        bank[f"source:{index}"] = view.ReferencedDocument
    for raw in views[0].GetAnnotations() or ():
        annotation = _early_bound(raw, "IAnnotation")
        if int(annotation.GetType()) == 7:
            key = "surface_finish:" + str(annotation.GetName())
            if key in bank:
                raise RuntimeError(
                    "viewport control has ambiguous surface-finish identity"
                )
            bank[key] = annotation
    return layout.plain(
        {
            "notes": notes,
            "surface_finishes": finishes,
            "template_geometry": geometry,
            "preferences": preferences(adapter),
            "views": view_rows,
        }
    ), bank


def semantics(raw):
    result = deepcopy(raw)
    for row in result["notes"].values():
        del row["extent"]
    return result


def require_identity(app, before, after):
    if before.keys() != after.keys() or any(
        int(app.IsSame(before[key], after[key])) != 1 for key in before
    ):
        raise RuntimeError(
            "viewport control native drawing/view/note/source identity changed"
        )


def screen_basis(app, view):
    """Native documented model-to-view-pixel transform; no guessed matrix layout."""
    utility = _early_bound(app.GetMathUtility(), "IMathUtility")
    if utility is None:
        raise RuntimeError("native screen basis has no MathUtility")
    transform = view.Transform  # GET only: its setter is explicitly unimplemented.
    result = []
    for xyz in ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)):
        point = utility.CreatePoint(double_array(xyz))
        if point is None:
            raise RuntimeError("native screen basis CreatePoint returned null")
        mapped = _early_bound(point, "IMathPoint").MultiplyTransform(transform)
        if mapped is None:
            raise RuntimeError("native screen basis MultiplyTransform returned null")
        result.append(
            layout.cells.finite(
                _early_bound(mapped, "IMathPoint").ArrayData, 3, "screen basis"
            )
        )
    return layout.plain(result)


def observe(adapter, state, directory, record, checkpoint):
    """Bounded A/B/A; preserve primary errors and always attempt exact restoration."""
    if not isinstance(state, State):
        raise ValueError("viewport control requires an explicit blank/populated state")
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    adapter.ownership.assert_current_owned()
    initial = viewport.capture(model)
    view = _early_bound(model.ActiveView, "IModelView")

    def require_view():
        adapter.ownership.assert_current_owned()
        if (
            int(adapter.swApp.IsSame(model, adapter.currentModel)) != 1
            or int(adapter.swApp.IsSame(view, model.ActiveView)) != 1
        ):
            raise RuntimeError(
                "viewport control exact owned drawing/viewport handle changed"
            )

    require_view()
    original, bank = snapshot(adapter, state)
    record.update(
        state=state.value,
        initial_viewport=initial,
        initial=original,
        arms=[],
        restoration={},
        status="running",
    )
    errors = []
    try:
        checkpoint()
        for arm in prepared.Arm:
            row = {"arm": arm.value}
            record["arms"].append(row)
            require_view()
            if arm is prepared.Arm.ZOOM:
                target = initial["scale2"] * 2
                view.Scale2 = target
                row["after_scale"] = viewport.capture(model)
                if row["after_scale"]["scale2"] != target:
                    raise RuntimeError(
                        "native viewport scale assignment did not persist"
                    )
                if row["after_scale"]["orientation3"] != initial["orientation3"]:
                    raise RuntimeError("native Scale2 changed the viewport orientation")
                viewport.assign_translation(
                    adapter.swApp, view, initial["translation3"]
                )
            if arm is prepared.Arm.RESTORED:
                viewport.restore(
                    adapter.swApp, model, initial, row.setdefault("restore", {})
                )
            model.GraphicsRedraw2()
            row["viewport"] = viewport.capture(model)
            for key in (
                "orientation3",
                "translation3",
                "visible_box_pixels",
                "document_visibility",
            ):
                if row["viewport"][key] != initial[key]:
                    raise RuntimeError(f"viewport control changed {key}")
            target = initial["scale2"] * (2 if arm is prepared.Arm.ZOOM else 1)
            if row["viewport"]["scale2"] != target:
                raise RuntimeError("native viewport scale assignment did not persist")
            row["native"], current = snapshot(adapter, state)
            require_identity(adapter.swApp, bank, current)
            if semantics(row["native"]) != semantics(original):
                raise RuntimeError("viewport control changed non-extent drawing state")
            if arm is not prepared.Arm.ZOOM and row["native"] != original:
                raise RuntimeError("viewport control A/A native extents differ")
            row["screen_basis_pixels"] = screen_basis(adapter.swApp, view)
            checkpoint()
            arm_dir = directory / arm.value
            arm_dir.mkdir(parents=True)
            adapter.ownership.register_directory(arm_dir)
            row["printed"] = prepared.printed_snapshot(adapter, arm_dir)
            require_view()
            row["after_pdf"], current = snapshot(adapter, state)
            require_identity(adapter.swApp, bank, current)
            if (
                row["after_pdf"] != row["native"]
                or viewport.capture(model) != row["viewport"]
            ):
                raise RuntimeError("viewport control PDF export changed native state")
            if len(record["arms"]) > 1:
                first = record["arms"][0]["printed"]
                row["printed_delta"] = prepared.compare_appearance(
                    first, row["printed"]
                )
                prepared.compare_vectors(first, row["printed"])
            checkpoint()
        if record["arms"][-1]["viewport"] != initial:
            raise RuntimeError("viewport control A/A full viewport differs")
    except BaseException as error:
        errors.append(error)
    finally:
        try:
            require_view()
            viewport.restore(adapter.swApp, model, initial, record["restoration"])
            restored, current = snapshot(adapter, state)
            require_identity(adapter.swApp, bank, current)
            record["restored_native"] = restored
            if restored != original:
                raise RuntimeError(
                    "viewport control finally restored drawing state differs"
                )
        except BaseException as error:
            record["restoration"].update(status="failed", error=repr(error))
            if not any(error is previous for previous in errors):
                errors.append(error)
            else:
                error.add_note(
                    "same exception object recurred during viewport restoration"
                )
        record.update(
            status="failed" if errors else "observed",
            errors=[repr(error) for error in errors],
            scope="zoom-dependent GetExtent observation; no material-fit acceptance",
        )
        try:
            checkpoint()
        except BaseException as error:
            if not any(error is previous for previous in errors):
                errors.append(error)
            record.update(status="failed", errors=[repr(error) for error in errors])
    if len(errors) == 1:
        raise errors[0]
    if errors:
        raise BaseExceptionGroup(
            "viewport observation and restoration failures", errors
        )
