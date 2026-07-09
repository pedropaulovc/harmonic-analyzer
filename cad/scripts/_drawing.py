r"""Project shared drawing constructs for harmonic-analyzer engineering drawings.

The GENERIC drawing COM primitives (views, dims, callouts, the cone glyph, notes,
save/export) live in the vendored adapter
(``solidworks_mcp.adapters.solidworks.drawing``). THIS module holds the
harmonic-analyzer CONVENTIONS layered on them — the checked-in drawing template,
the standard ASME notes block, the title-block rows, and the third-angle
projection-symbol PLACEMENT — so every part drawing script references one shared
source instead of re-inlining them.

Import direction is ``build_drawing_<part>.py`` -> ``_drawing`` ->
``_common``/submodule, so (like the drawing adapter module itself) nothing in a
part or assembly build imports it — editing it rebuilds only the opt-in ``drawing``
task, never a part or assembly.
"""

from __future__ import annotations

from typing import Any

from _common import CAD_ROOT

from solidworks_mcp.adapters.solidworks import drawing as dwg

import _telemetry

STANDARD = "ASME Y14.5-2018"

# The project drawing template (ANSI A landscape, unused tables stripped), checked
# into the repo so the sheet/border/title block is reproducible across seats instead
# of depending on each seat's default ``.drwdot``. Built by
# ``make_drawing_template.py``; ``new_drawing`` falls back to the seat default (with
# a warning) until it exists.
TEMPLATE_DRWDOT = (CAD_ROOT / "templates" / "harmonic-analyzer.drwdot").resolve()

# Third-angle projection symbol: the ONE project placement (sheet meters, just above
# the title block) + size, referenced by every part drawing rather than re-specified.
_PROJECTION_XY = (0.186, 0.055)
_PROJECTION_SIZE = 0.005

# General-notes block (upper-left) and title-block (lower-right) anchor + line pitch,
# sheet meters (origin bottom-left). The 5 mm notes pitch keeps a 7-line block clear
# of the top view's upper dimension.
_NOTES_XY = (0.018, 0.205)
_NOTES_PITCH = 0.005
_TITLE_XY = (0.180, 0.032)
_TITLE_PITCH = 0.008


def standard_notes(
    *, material: str, general_tol_mm: float = 0.10, finish_um: float = 3.2
) -> list[str]:
    """The machinist-complete ASME general-notes block, material/tolerance filled in.

    Universal notes (units, governing standard, burrs) plus the part's material,
    general decimal tolerance and default machined finish — the shared baseline every
    harmonic-analyzer print carries. A part may append its own specific notes.
    """
    return [
        "NOTES:",
        "1. DIMENSIONS IN MILLIMETERS.",
        f"2. INTERPRET DRAWING PER {STANDARD}.",
        "3. REMOVE ALL BURRS AND SHARP EDGES.",
        f"4. MATERIAL: {material.upper()}.",
        f"5. UNLESS OTHERWISE SPECIFIED, GENERAL TOLERANCE .XX +/- {general_tol_mm:.2f} mm.",
        f"6. MACHINED SURFACE FINISH {finish_um:g} µm Ra UNLESS OTHERWISE NOTED.",
    ]


def title_rows(
    *, name: str, number: str, rev: str, material: str, scale_str: str
) -> list[str]:
    """The three standard title-block rows (top-to-bottom): identity / material+scale
    / projection+units+standard. The scale is filled from the view's ACTUAL
    (auto-fit) scale, not assumed."""
    return [
        f"{name}      {number}   REV {rev}",
        f"MATERIAL: {material.upper()}        SCALE {scale_str}",
        f"THIRD ANGLE   mm   {STANDARD}",
    ]


def new_drawing(adapter: Any) -> Any:
    """Create the project drawing document from the checked-in template.

    Prefers the repo ``.drwdot`` (reproducible across seats); the submodule helper
    falls back to the seat default if the template file is missing.
    """
    template = str(TEMPLATE_DRWDOT) if TEMPLATE_DRWDOT.is_file() else None
    if template is None:
        _telemetry.warn(
            f"project drawing template not found ({TEMPLATE_DRWDOT}); "
            "using the seat default template"
        )
    return dwg.new_drawing(adapter, template=template)


def add_projection_symbol(adapter: Any) -> None:
    """Draw the ASME third-angle projection symbol at the project standard spot.

    References the generic cone glyph (submodule) at the harmonic-analyzer standard
    placement/size. RAISES if the glyph could not be authored — the projection
    convention is a required deliverable, so a silent miss must fail the build.
    """
    ok = dwg.add_third_angle_symbol(
        adapter, _PROJECTION_XY[0], _PROJECTION_XY[1], size=_PROJECTION_SIZE
    )
    if not ok:
        raise RuntimeError("ASME third-angle projection symbol was not drawn")


def add_notes_block(adapter: Any, notes: list[str]) -> None:
    """Place the general-notes block in the upper-left at the standard line pitch.

    RAISES if any note fails to insert (``add_note`` returns ``None``) -- the
    machinist notes are a required deliverable, so a silent miss must fail the build.
    """
    x, y_top = _NOTES_XY
    for i, line in enumerate(notes):
        if dwg.add_note(adapter, line, x, y_top - i * _NOTES_PITCH) is None:
            raise RuntimeError(f"notes block: SolidWorks did not insert note {line!r}")


def add_title_block(adapter: Any, rows: list[str]) -> None:
    """Place the title-block rows in the lower-right at the standard line pitch.

    RAISES if any row fails to insert -- the part number / material / standard rows
    are make-critical, so a silent miss must fail rather than ship a blank title block.
    """
    x, y_top = _TITLE_XY
    for i, row in enumerate(rows):
        if dwg.add_note(adapter, row, x, y_top - i * _TITLE_PITCH) is None:
            raise RuntimeError(f"title block: SolidWorks did not insert row {row!r}")
