r"""Create the one-sheet purchase drawing for shared McMaster 9666K56 wire.

Replacement needs the supplier wire diameter and the purchase identity, not
the installed members' straight rest runs: the formed ends, wraps and cut
lengths are set at assembly. The sheet shows the supplier circle from the
zero-body SUPPLIER_REFERENCE state with its native diameter, one
property-linked note naming the SKU, a flagged pointer to the assembly steps
that cut and form each member, and an undimensioned reference isometric
(rule 8); the title block carries the material.
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import add_note, place_view

import _telemetry
import mg_magnifier_assembly_steps as magnifier_steps
from _purchased_fastener_drawing import (
    _open_supplier_source_read_only,
    _source_file_sha256,
)
from _com import _early_bound
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    rebuild_drawing,
    set_high_quality_shaded_with_edges,
    stamp_drawing_summary,
)
from _drawing_notes import add_property_linked_note
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_view_display import set_hidden_lines_removed
from _paths import CAD_ROOT
from _part_properties import part_drawing_unit
from _session import run_build
from _supplier_spring_drawing import _preserve_reference_source_file
from _supplier_wire_stock_drawing import STOCK_FIELD, STOCK_SCALE, add_wire_section
from sh_vn_music_wire_pen_geom import CONFIGURATION as ISO_CONFIGURATION
from _machinist_review_mode import MachinistReviewMode

MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["sh_vn_music_wire"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(**SPEC.outputs)
SLDDRW = OUTPUTS.slddrw
PDF = OUTPUTS.pdf
PNG = OUTPUTS.png

_BORDER = (0.0127, 0.0127, 0.4191, 0.2667)
_TITLE_BLOCK = (0.2159, 0.0127, 0.4191, 0.0651)
_POSITION_TOLERANCE = 1e-6
NOTES_XY = (0.020, 0.075)

# Where each member is cut and formed: the assembly drawing sheet that PRINTS
# each step. Both packages continue their sequence on a second sheet, so the
# citation is (sheet, step) per printed group (test-pinned to where the
# assembly drawings place their sequence blocks).
MAGNIFIER_WIRE_SHEET = 5
PEN_DRAWING_NUMBER = "MHA-PN-00"
PEN_WIRE_CITATIONS = ((3, 2), (4, 8))
ASSEMBLY_NOTE = "\n".join(
    (
        "CUT TO LENGTH AND FORM AT ASSEMBLY:",
        f"LEVER WIRE: {magnifier_steps.DRAWING_NUMBER} SHEET {MAGNIFIER_WIRE_SHEET}, "
        f"STEPS {magnifier_steps.step_number(magnifier_steps.WIRE_HOOKED_KEY)}-"
        f"{magnifier_steps.step_number(magnifier_steps.WIRE_TIED_KEY)}",
        f"PEN WIRE: {PEN_DRAWING_NUMBER} "
        + "; ".join(
            f"SHEET {sheet}, STEP {step}" for sheet, step in PEN_WIRE_CITATIONS
        ),
    )
)
ASSEMBLY_NOTE_XY = (0.020, 0.105)

# Rule 8's pictorial: one member's straight run, undimensioned, in the empty
# upper-right field; its label says it is not a length.
ISO_SCALE = (2, 1)
ISO_CENTER = (0.300, 0.170)
ISO_FIELD = (0.262, 0.085, 0.410, 0.255)
ISO_LABEL = (
    f"ISOMETRIC SCALE {ISO_SCALE[0]}:{ISO_SCALE[1]}\n"
    "PEN WIRE MEMBER SHOWN\nREFERENCE ONLY, NOT TO LENGTH"
)
ISO_LABEL_XY = (0.268, 0.108)


def _overlaps(box: tuple[float, ...], other: tuple[float, ...]) -> bool:
    return (
        box[0] < other[2]
        and other[0] < box[2]
        and box[1] < other[3]
        and other[1] < box[3]
    )


def _inside(box: tuple[float, ...], field: tuple[float, ...]) -> bool:
    return (
        field[0] <= box[0]
        and field[1] <= box[1]
        and box[2] <= field[2]
        and box[3] <= field[3]
    )


def _note_box(note: Any, expected: str, label: str) -> tuple[float, ...]:
    text = str(_early_bound(note, "INote").GetText() or "").replace("\r\n", "\n")
    if text != expected.replace("\r\n", "\n"):
        raise RuntimeError(f"{label} resolved to {text!r}, expected {expected!r}")
    extent = tuple(
        float(value) for value in (_early_bound(note, "INote").GetExtent() or ())
    )
    if (
        len(extent) != 6
        or not all(map(math.isfinite, extent))
        or (extent[3] <= extent[0] or extent[4] <= extent[1])
    ):
        raise RuntimeError(f"{label} has no resolved native extent: {extent!r}")
    box = (extent[0], extent[1], extent[3], extent[4])
    if not _inside(box, _BORDER) or _overlaps(box, _TITLE_BLOCK):
        raise RuntimeError(f"{label} leaves its printable field: {box!r}")
    return box


def _outline(view: Any) -> tuple[float, ...]:
    box = tuple(float(value) for value in (view.GetOutline() or ()))
    if (
        len(box) != 4
        or not all(map(math.isfinite, box))
        or box[2] <= box[0]
        or box[3] <= box[1]
    ):
        raise RuntimeError(f"wire isometric: invalid view outline {box!r}")
    return box


def _assert_iso_state(view: Any) -> None:
    source = str(view.GetReferencedModelName()).replace("\\", "/").casefold()
    ratio = tuple(float(value) for value in (view.ScaleRatio or ()))
    if (
        str(view.ReferencedConfiguration) != ISO_CONFIGURATION
        or source != str(SOURCE).replace("\\", "/").casefold()
        or str(view.GetOrientationName()) != "*Isometric"
        or ratio != tuple(float(value) for value in ISO_SCALE)
        or int(view.UseSheetScale) != 0
    ):
        raise RuntimeError(
            f"wire isometric: native source/configuration/scale changed: {ratio!r}"
        )
    mode, edges = view.GetDisplayMode2(), view.GetDisplayEdgesInShadedMode()
    if mode is None or int(mode) not in (3, 7) or not bool(edges):
        raise RuntimeError("wire isometric is not Shaded With Edges")


def _add_isometric(adapter: Any) -> Any:
    """Configured member run, primed through HLR before shading, centred."""
    view = _early_bound(
        place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE),
        "IView",
    )
    view.ReferencedConfiguration = ISO_CONFIGURATION
    view.UseSheetScale = 0
    view.ScaleRatio = double_array(ISO_SCALE)
    # An already-shaded no-op can retain low-quality display: HLR first.
    set_hidden_lines_removed(adapter, view)
    set_high_quality_shaded_with_edges(adapter, view, label="wire isometric")
    rebuild_drawing(adapter, label="wire isometric configuration")
    _assert_iso_state(view)
    # The end-origin member moves on reconfiguration: centre its real outline.
    box = _outline(view)
    position = tuple(float(value) for value in (view.Position or ()))
    if len(position) != 2 or not all(map(math.isfinite, position)):
        raise RuntimeError(f"wire isometric: invalid native view position {position!r}")
    target = tuple(
        position[index] + ISO_CENTER[index] - (box[index] + box[index + 2]) / 2.0
        for index in range(2)
    )
    if not view.SetViewPosition(double_array(target), False):
        raise RuntimeError("wire isometric: cannot recenter native view")
    rebuild_drawing(adapter, label="wire isometric recentered")
    return view


def _assert_iso_field(view: Any) -> tuple[float, ...]:
    box = _outline(view)
    centre = ((box[0] + box[2]) / 2.0, (box[1] + box[3]) / 2.0)
    if math.dist(centre, ISO_CENTER) > _POSITION_TOLERANCE or not _inside(
        box, ISO_FIELD
    ):
        raise RuntimeError(f"wire isometric leaves its field: {box!r}")
    return box


def _literal_note(adapter: Any, text: str, xy: tuple[float, float], label: str) -> Any:
    note = add_note(adapter, text, *xy)
    if note is None:
        raise RuntimeError(f"cannot create {label}")
    return note


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")
    # As _supplier_spring_drawing: the native Ø presentation writes (SetText on
    # the imported model dimension) may dirty the part in memory, so the shared
    # part is opened read-only and its bytes are proven unchanged through export.
    source_sha256 = _source_file_sha256(SOURCE)
    model = _open_supplier_source_read_only(adapter, SOURCE, label=PART_STEM)
    if model.GetSaveFlag() is not False:
        raise RuntimeError(f"{PART_STEM}: supplier source must be clean before drawing")
    properties = read_required_properties(
        model,
        (
            "Number",
            "Revision",
            "Title",
            "Material Specification",
            "Finish",
            "Manufacturing Notes",
        ),
        required=("Number", "Material Specification", "Finish", "Manufacturing Notes"),
    )
    drawing_model, _ = new_project_drawing(
        adapter,
        property_view=PART_STEM,
        scale=STOCK_SCALE,
        layout=SPEC.layout,
        unit=part_drawing_unit(PART_STEM),
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Shared Music Wire Purchase Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "music wire; McMaster-Carr 9666K56; supplier wire diameter",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    # The section stays the first view: the title block reads its properties.
    section = add_wire_section(adapter, SOURCE)
    iso = _add_isometric(adapter)
    drawing = _early_bound(adapter.currentModel, "IDrawingDoc")
    drawing.ActivateView("")
    if not drawing.GetEditSheet() or drawing.ActiveDrawingView is not None:
        raise RuntimeError("cannot restore sheet context for the wire notes")
    purchase = add_property_linked_note(adapter, "Manufacturing Notes", *NOTES_XY)
    assembly = _literal_note(
        adapter, ASSEMBLY_NOTE, ASSEMBLY_NOTE_XY, "assembly pointer note"
    )
    iso_label = _literal_note(adapter, ISO_LABEL, ISO_LABEL_XY, "isometric label")

    def settled() -> None:
        section()
        _assert_iso_state(iso)
        iso_box = _assert_iso_field(iso)
        notes = {
            "purchase note": _note_box(
                purchase,
                str(properties["Manufacturing Notes"]),
                "purchase note",
            ),
            "assembly pointer note": _note_box(
                assembly, ASSEMBLY_NOTE, "assembly pointer note"
            ),
            "isometric label": _note_box(iso_label, ISO_LABEL, "isometric label"),
        }
        if not _inside(notes["isometric label"], ISO_FIELD):
            raise RuntimeError(
                f"isometric label leaves its field: {notes['isometric label']!r}"
            )
        boxes = list(notes.items())
        for index, (label, box) in enumerate(boxes):
            if _overlaps(box, iso_box) or _overlaps(box, STOCK_FIELD):
                raise RuntimeError(f"{label} overlaps a native view: {box!r}")
            for other, other_box in boxes[index + 1 :]:
                if _overlaps(box, other_box):
                    raise RuntimeError(f"{label} overlaps {other}")

    with _preserve_reference_source_file(SOURCE, source_sha256, label=PART_STEM):
        return await finalize_drawing(
            adapter,
            OUTPUTS,
            pdf_title="Shared Music Wire Purchase Drawing",
            scale=STOCK_SCALE,
            layout=SPEC.layout,
            settled_checks=(settled,),
        )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
