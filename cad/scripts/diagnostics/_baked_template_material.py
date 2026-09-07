"""Opt-in blank MATERIAL-value centering; no production template is replaced.

INote's documented middle vertical alignment is a candidate, not evidence that
resolved multiline text fits. Preserve every other note field and drawing
property; populated native/PDF containment remains a separate strict gate.
"""

from copy import deepcopy
import math

from diagnostics import _baked_template_layout as layout

MATERIAL_LINK = '$PRPSHEET:"Material"'
MIDDLE = 1  # swTextAlignmentVertical_e.swTextAlignmentMiddle


def material_plan(notes, lines):
    """Keep the inherited X/Z and font; derive Y only from native cell rules."""
    name = layout.unique_note(notes, link=MATERIAL_LINK)
    row = notes[name]
    if (
        row["kind"] != 6
        or row["lock"] != "unlocked"
        or row["horizontal"] != 1
        or row["vertical"] != 0
    ):
        raise RuntimeError(
            "material centering requires the inherited unlocked left/top note"
        )
    position = row["position"]
    height = row["font"]["CharHeight"]
    if (
        len(position) != 3
        or not all(math.isfinite(value) for value in position)
        or not math.isfinite(height)
        or height <= 0
    ):
        raise RuntimeError(
            "material centering requires finite native position and font height"
        )
    cell = layout.cells.enclosing_cell(lines, position)
    return layout.plain(
        {
            name: {
                "role": "material",
                "position": [position[0], (cell[1] + cell[3]) / 2, position[2]],
                "cell": cell,
                "horizontal": 1,
                "vertical": MIDDLE,
                "height_m": height,
            }
        }
    )


def require_transition(before, after, plan, lines):
    """Add exactly one vertical transition to the existing exhaustive allowlist."""
    if plan != material_plan(before["notes"], lines):
        raise RuntimeError(
            "material plan differs from the sole measured native-cell target"
        )
    name = next(iter(plan))
    if after["notes"][name]["vertical"] != MIDDLE:
        raise RuntimeError("material middle-justification setter was rejected")
    expected = deepcopy(before)
    expected["notes"][name]["vertical"] = MIDDLE
    layout.require_transition(expected, after, plan)


def apply_layout(adapter, handles, plan, receipt, checkpoint):
    """Two documented setters on the exact owned material note; no font changes."""
    if len(plan) != 1:
        raise RuntimeError("material centering requires exactly one target")
    name, target = next(iter(plan.items()))
    if target["role"] != "material" or target["vertical"] != MIDDLE:
        raise RuntimeError("material centering received an unsupported target")
    adapter.ownership.assert_current_owned()
    model = adapter.currentModel
    if int(adapter.swApp.IsSame(adapter.swApp.ActiveDoc, model)) != 1:
        raise RuntimeError("material centering lost its exact active owned drawing")
    annotation, owner = handles[name]
    actual_owner = annotation.Owner
    if (owner is None) != (actual_owner is None) or (
        owner is not None and int(adapter.swApp.IsSame(owner, actual_owner)) != 1
    ):
        raise RuntimeError("material centering note owner changed")
    note = layout.cells.required(annotation.GetSpecificAnnotation(), "INote")
    if (
        note.LockPosition
        or str(note.PropertyLinkedText) != MATERIAL_LINK
        or int(note.GetTextJustification()) != 1
        or int(note.GetTextVerticalJustification()) != 0
    ):
        raise RuntimeError(
            "material centering native note no longer matches its starting contract"
        )
    operation = {"name": name, "role": "material", "target": target, "calls": []}
    receipt.append(operation)
    checkpoint()
    operation["calls"].append("SetTextVerticalJustification")
    note.SetTextVerticalJustification(MIDDLE)
    operation["vertical_after"] = int(note.GetTextVerticalJustification())
    checkpoint()
    if operation["vertical_after"] != MIDDLE:
        raise RuntimeError("material middle-justification setter was rejected")
    operation["calls"].append("SetPosition2")
    returned = annotation.SetPosition2(*target["position"])
    operation["position_return"] = repr(returned)
    operation["position_after"] = list(annotation.GetPosition())
    checkpoint()
    if returned is not True or operation["position_after"] != target["position"]:
        raise RuntimeError("material position setter was rejected or clamped")
    model.GraphicsRedraw2()


def static_label_plan(notes, lines, changes):
    """Blank formula ink cannot prove the fit of resolved manufacturing text."""
    name = layout.unique_note(notes, text="MATERIAL")
    if notes[name]["link"] != "MATERIAL":
        raise RuntimeError("material static label no longer has exact literal content")
    return {
        name: {
            "role": "material_label",
            "cell": layout.cells.enclosing_cell(lines, notes[name]["position"]),
        }
    }


def phase_scope(notes):
    scope = layout.blank_phase_scope(notes)
    scope.update(
        phase="blank_material_middle_persistence",
        geometric_acceptance="unchanged_static_MATERIAL_label_only",
        material_finish_crowding="fresh_three_source_native_and_PDF_fit_pending",
    )
    return scope
