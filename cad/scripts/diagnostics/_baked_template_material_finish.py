"""Two linked-note Y targets derived from three preserved native/PDF samples.

This opt-in diagnostic predicts translations; fresh populated native/cold/print
checks must prove the actual result. It never edits text, font, frames or labels.
"""

from copy import deepcopy
from itertools import combinations
import math

from diagnostics import _baked_template_gaps as gaps
from diagnostics import _baked_template_layout as layout
from diagnostics import _baked_template_material as material
from diagnostics import _material_template_sources as sources
from diagnostics import _populated_template_fields as fields

FINISH_LINK = '$PRPSHEET:"Finish"'
LINKS = {"material": material.MATERIAL_LINK, "finish": FINISH_LINK}
BOXES = ("native_box_m", "pdf_box_m")


def read_population(path, sha256, template_sha256):
    """The old receipt/hash guard is shared; the three-source mode is explicit."""
    try:
        report = gaps.read_population_report(path, sha256, template_sha256)
        if report["population"] != "material-center" or report["status"] != "failed":
            raise RuntimeError(
                "material-finish requires terminal material-center evidence"
            )
        targets = {}
        for trial in report["trials"]:
            target = trial["target"]
            if target not in sources.TARGETS or target in targets:
                raise RuntimeError("material-finish has a duplicate or foreign target")
            if (
                trial["status"] != "observed"
                or trial["cold_delta"]["changed_leaf_count"] != 0
                or trial["png_delta"]["changed_pixel_count"] != 0
                or trial["printed"]["classification"] != "unchanged"
                or trial["copy_hashes"]["initial"]
                != sources.TARGETS[target].source_sha256
                or trial["copy_hashes"]["final"]
                != sources.TARGETS[target].source_sha256
            ):
                raise RuntimeError("material-finish source/cold persistence differs")
            built, cold = (trial["linked_fields"][phase] for phase in ("built", "cold"))
            for key in ("notes", "template_geometry", "expected_link_values"):
                if built[key] != cold[key]:
                    raise RuntimeError("material-finish raw cold evidence differs")
            if built["fit"]["fields"] != cold["fit"]["fields"]:
                raise RuntimeError(
                    "material-finish native/PDF field evidence changed cold"
                )
            name = layout.unique_note(built["notes"], link=material.MATERIAL_LINK)
            sources.require_material_value(
                built["notes"][name],
                built["expected_link_values"][material.MATERIAL_LINK],
                expected_vertical=material.MIDDLE,
            )
            targets[target] = {
                "notes": built["notes"],
                "fields": built["fit"]["fields"],
                "lines": [
                    row["sheet_points"]
                    for row in built["template_geometry"]["segments"]
                    if "sheet_points" in row
                ],
            }
        if set(targets) != set(sources.TARGETS):
            raise RuntimeError(
                "material-finish requires exactly rocker, lever and tube"
            )
        return {
            "receipt": str(path),
            "sha256": sha256,
            "targets": targets,
            "original_issues": {
                row["target"]: row["acceptance_issues"] for row in report["trials"]
            },
        }
    except (KeyError, TypeError, ValueError) as error:
        raise RuntimeError(
            "material-finish receipt is incomplete or malformed"
        ) from error


def _box(values, label):
    result = layout.cells.finite(values, 4, f"material-finish {label}")
    if not (result[0] < result[2] and result[1] < result[3]):
        raise RuntimeError("material-finish requires positive-area measured ink")
    return result


def _shift(box, dy):
    return [value + dy if index in (1, 3) else value for index, value in enumerate(box)]


def _gap(first, second):
    return max(
        second[0] - first[2],
        first[0] - second[2],
        second[1] - first[3],
        first[1] - second[3],
    )


def _samples(notes, lines, targets, centered):
    if set(targets) != set(sources.TARGETS):
        raise RuntimeError(
            "material-finish requires exactly the three measured sources"
        )
    material_name = next(iter(centered))
    for target, sample in targets.items():
        if (
            layout.plain(lines) != sample["lines"]
            or notes.keys() != sample["notes"].keys()
        ):
            raise RuntimeError("material-finish blank geometry/note inventory differs")
        for name, row in sample["notes"].items():
            current = notes[name]
            expected_link, expected_text = current["link"], current["text"]
            if (
                expected_link
                == expected_text
                == layout.sheet_setup._OLD_EDGE_BREAK_NOTE
            ):
                # Normal new_project_drawing already performs this exact metric
                # conversion. Blank authoring must still preserve the old note.
                expected_link = expected_text = (
                    layout.sheet_setup._METRIC_EDGE_BREAK_NOTE
                )
            expected_position = (
                centered[name]["position"]
                if name == material_name
                else current["position"]
            )
            expected_vertical = (
                material.MIDDLE if name == material_name else current["vertical"]
            )
            if (
                any(
                    row[key] != current[key]
                    for key in (
                        "font",
                        "horizontal",
                        "lock",
                        "kind",
                        "visible",
                        "owner_type",
                    )
                )
                or row["link"] != expected_link
                or row["position"] != list(expected_position)
                or row["vertical"] != expected_vertical
                or ("$PRP" not in row["link"] and row["text"] != expected_text)
            ):
                raise RuntimeError(
                    f"material-finish {target}/{name}: blank style/content/anchor differs"
                )
        expected_fields = {
            name
            for name, row in sample["notes"].items()
            if row["visible"] == 1
            and ("$PRP" in row["link"] or row["text"] in fields.LABEL_VALUE)
        }
        if expected_fields != sample["fields"].keys():
            raise RuntimeError("material-finish complete field inventory differs")
        for name, field in sample["fields"].items():
            row = sample["notes"][name]
            if field["link"] != row["link"] or field["native_text"] != row["text"]:
                raise RuntimeError(
                    "material-finish field text/link differs from raw note"
                )
            if not row["text"]:
                if (
                    row["extent_scope"] != "observed_zero_ink"
                    or field["status"] != "proven_zero_ink"
                ):
                    raise RuntimeError(
                        "material-finish empty field lacks a zero-ink witness"
                    )
                continue
            if "$PRP" in row["text"]:
                raise RuntimeError("material-finish populated field remains unresolved")
            _box(field["region_m"], "field region")
            for key in BOXES:
                _box(field[key], key)
            if list(field["native_box_m"]) != [
                row["extent"][index] for index in (0, 1, 3, 4)
            ]:
                raise RuntimeError("material-finish native box differs from raw extent")
            _box(field["pdf"]["ink_box_pt"], "raw PDF ink")
        _require_derived_fields(sample)


def _require_derived_fields(sample):
    """Reuse the field auditor to derive regions and boxes from raw observations."""

    def pdf_for_text(text):
        matches = [
            row["pdf"]
            for row in sample["fields"].values()
            if row["native_text"] == text
        ]
        if len(matches) != 1:
            raise RuntimeError("material-finish raw PDF text is ambiguous")
        return matches[0]

    def pdf_for_note(note):
        names = [name for name, row in sample["notes"].items() if row is note]
        if len(names) != 1:
            raise RuntimeError("material-finish raw note is ambiguous")
        return sample["fields"][names[0]]["pdf"]

    replay = fields.field_audit(
        sample["notes"],
        sample["lines"],
        pdf_reader=pdf_for_text,
        symbol_reader=pdf_for_note,
    )
    for name, original in sample["fields"].items():
        if not original["native_text"]:
            continue
        derived = replay["fields"][name]
        for key in ("region_m", *BOXES):
            if list(original[key]) != list(derived[key]):
                raise RuntimeError(
                    f"material-finish {name}/{key} differs from raw observations"
                )


def measured_plan(notes, lines, targets):
    """Intersect all retained box constraints without reducing any acceptance gap."""
    try:
        return _measured_plan(notes, lines, targets)
    except (KeyError, TypeError, ValueError) as error:
        raise RuntimeError(
            "material-finish sample is incomplete or malformed"
        ) from error


def _measured_plan(notes, lines, targets):
    centered = material.material_plan(notes, lines)
    names = {role: layout.unique_note(notes, link=link) for role, link in LINKS.items()}
    _samples(notes, lines, targets, centered)
    for name in names.values():
        if (
            notes[name]["lock"] != "unlocked"
            or notes[name]["horizontal"] != 1
            or notes[name]["vertical"] != 0
        ):
            raise RuntimeError(
                "material-finish requires inherited unlocked left/top notes"
            )
    samples = list(targets.values())
    material_name, finish_name = names["material"], names["finish"]
    material_cell = centered[material_name]["cell"]
    material_boxes = [
        sample["fields"][material_name]["native_box_m"] for sample in samples
    ]
    material_shift = (
        material_cell[1]
        + material_cell[3]
        - min(box[1] for box in material_boxes)
        - max(box[3] for box in material_boxes)
    ) / 2
    lo, hi = -math.inf, math.inf
    constraints = []
    gap = layout.FIELD_GAP_M
    for target, sample in targets.items():
        finish = sample["fields"][finish_name]
        for key in BOXES:
            box, cell = finish[key], finish["region_m"]
            low, high = cell[1] - box[1], cell[3] - box[3]
            constraints.append(
                {
                    "target": target,
                    "kind": key,
                    "field": finish_name,
                    "interval_m": [low, high],
                    "reason": "cell",
                }
            )
            lo, hi = max(lo, low), min(hi, high)
            for other, field in sample["fields"].items():
                if other == finish_name or key not in field:
                    continue
                fixed = _shift(
                    field[key], material_shift if other == material_name else 0
                )
                if max(fixed[0] - box[2], box[0] - fixed[2]) >= gap:
                    continue
                # Keep the recorded vertical order; do not jump past another note.
                if box[1] >= fixed[3]:
                    low = fixed[3] + gap - box[1]
                    lo = max(lo, low)
                    constraints.append(
                        {
                            "target": target,
                            "kind": key,
                            "field": other,
                            "minimum_m": low,
                            "reason": "neighbor_below",
                        }
                    )
                elif fixed[1] >= box[3]:
                    high = fixed[1] - gap - box[3]
                    hi = min(hi, high)
                    constraints.append(
                        {
                            "target": target,
                            "kind": key,
                            "field": other,
                            "maximum_m": high,
                            "reason": "neighbor_above",
                        }
                    )
                else:
                    raise RuntimeError(
                        "material-finish has overlapping vertical order; no bounded interval"
                    )
    if not math.isfinite(lo) or not math.isfinite(hi) or lo >= hi:
        raise RuntimeError(f"material-finish has no feasible interval: {lo!r}..{hi!r}")
    finish_shift = (lo + hi) / 2
    plan = {}
    for role, name in names.items():
        initial = (
            centered[name]["position"]
            if role == "material"
            else notes[name]["position"]
        )
        dy = material_shift if role == "material" else finish_shift
        position = [initial[0], initial[1] + dy, initial[2]]
        cell = layout.cells.enclosing_cell(lines, initial)
        if not cell[1] < position[1] < cell[3]:
            raise RuntimeError(
                "material-finish planned anchor leaves its measured cell"
            )
        plan[name] = {
            "role": role,
            "position": position,
            "cell": cell,
            "horizontal": 1,
            "vertical": material.MIDDLE if role == "material" else 0,
            "height_m": notes[name]["font"]["CharHeight"],
        }
    witness = {
        "material_shift_m": material_shift,
        "finish_interval_m": [lo, hi],
        "finish_shift_m": finish_shift,
        "constraints": constraints,
        "validated_gap_m": gap,
        "targets": {},
    }
    for target, sample in targets.items():
        predicted = deepcopy(sample["fields"])
        for name, field in predicted.items():
            dy = (
                material_shift
                if name == material_name
                else finish_shift
                if name == finish_name
                else 0
            )
            for key in BOXES:
                if key in field:
                    field[key] = _shift(field[key], dy)
                    layout.cells.require_box(
                        field["region_m"],
                        field[key],
                        f"material-finish predicted {target}/{name}/{key}",
                    )
        for key in BOXES:
            for (name, first), (other, second) in combinations(predicted.items(), 2):
                if (
                    key in first
                    and key in second
                    and _gap(first[key], second[key]) < gap
                ):
                    raise RuntimeError(
                        f"material-finish predicted {target}/{name}/{other}/{key} violates clearance"
                    )
        witness["targets"][target] = {"predicted_fields": predicted, "issues": []}
    return layout.plain(plan), layout.plain(witness)


def require_transition(before, after, plan, lines, targets):
    expected_plan, _ = measured_plan(before["notes"], lines, targets)
    if plan != expected_plan:
        raise RuntimeError("material-finish plan differs from measured targets")
    expected = deepcopy(before)
    name = layout.unique_note(before["notes"], link=material.MATERIAL_LINK)
    if after["notes"][name]["vertical"] != material.MIDDLE:
        raise RuntimeError("material-finish vertical setter was rejected")
    expected["notes"][name]["vertical"] = material.MIDDLE
    layout.require_transition(expected, after, plan)


def apply_layout(adapter, handles, plan, receipt, checkpoint):
    """Three setters, immediate native readback, no font or horizontal writes."""
    if len(plan) != 2 or [row["role"] for row in plan.values()] != list(LINKS):
        raise RuntimeError("material-finish requires exactly its two ordered targets")
    model = material.require_visible_owned_drawing(adapter)
    for name, target in plan.items():
        material.require_visible_owned_drawing(adapter, model)
        role = target["role"]
        if target["vertical"] != (material.MIDDLE if role == "material" else 0):
            raise RuntimeError("material-finish unsupported vertical target")
        annotation, owner = handles[name]
        actual_owner = annotation.Owner
        if (owner is None) != (actual_owner is None) or (
            owner is not None and int(adapter.swApp.IsSame(owner, actual_owner)) != 1
        ):
            raise RuntimeError("material-finish annotation owner changed")
        note = layout.cells.required(annotation.GetSpecificAnnotation(), "INote")
        if (
            note.LockPosition
            or str(note.PropertyLinkedText) != LINKS[role]
            or int(note.GetTextJustification()) != 1
            or int(note.GetTextVerticalJustification()) != 0
        ):
            raise RuntimeError("material-finish native starting note differs")
        operation = {"name": name, "role": role, "target": target, "calls": []}
        receipt.append(operation)
        checkpoint()
        if role == "material":
            material.require_visible_owned_drawing(adapter, model)
            operation["calls"].append("SetTextVerticalJustification")
            note.SetTextVerticalJustification(material.MIDDLE)
            operation["vertical_after"] = int(note.GetTextVerticalJustification())
            checkpoint()
            if operation["vertical_after"] != material.MIDDLE:
                raise RuntimeError("material-finish vertical setter was rejected")
        material.require_visible_owned_drawing(adapter, model)
        operation["calls"].append("SetPosition2")
        returned = annotation.SetPosition2(*target["position"])
        operation["position_return"] = repr(returned)
        operation["position_after"] = list(annotation.GetPosition())
        checkpoint()
        if returned is not True or operation["position_after"] != target["position"]:
            raise RuntimeError(
                "material-finish position setter was rejected or clamped"
            )
        material.require_visible_owned_drawing(adapter, model)
    model.GraphicsRedraw2()


def static_label_plan(notes, lines, plan):
    result = material.static_label_plan(notes, lines, plan)
    name = layout.unique_note(notes, text="FINISH")
    if notes[name]["link"] != "FINISH":
        raise RuntimeError("material-finish static FINISH label became linked")
    result[name] = {
        "role": "finish_label",
        "cell": layout.cells.enclosing_cell(lines, notes[name]["position"]),
    }
    return result


def phase_scope(notes):
    scope = layout.blank_phase_scope(notes)
    scope.update(
        phase="blank_material_finish_persistence",
        geometric_acceptance="unchanged_static_MATERIAL_FINISH_labels_only",
        material_finish_crowding="predicted_from_three_native_PDF_samples_fresh_population_required",
    )
    return scope
