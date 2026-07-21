r"""Pure-data manufacturing-note builders for made fasteners.

The title block owns units, material, finish, surface texture, and blanket
tolerances.  These helpers add only feature-specific controls which override
that blanket where the fastener's function needs a tighter, inspectable limit.
They deliberately have no SolidWorks imports so part builders and drawing
recipes can share the exact same product definition.
"""

from __future__ import annotations

import re
from typing import Literal


_TPI_RE = re.compile(r"-(?P<tpi>[1-9][0-9]*)$")


def _thread_pitch_mm(thread: str) -> float:
    match = _TPI_RE.search(thread)
    if match is None:
        raise ValueError(f"unrecognized Unified thread designation: {thread!r}")
    return 25.4 / int(match.group("tpi"))


def thread_control_notes(
    *, thread: str, thread_designation: str, underhead_length_mm: float
) -> tuple[str, ...]:
    """Return the common, measurable external-thread manufacturing contract."""
    pitch = _thread_pitch_mm(thread)
    min_full_form = underhead_length_mm - 4.0 * pitch
    if min_full_form <= 0.0:
        raise ValueError(
            f"{thread_designation} length {underhead_length_mm:g} leaves no "
            "full-form thread after two-pitch runout at each end"
        )
    lead_chamfer = min(0.50, max(0.25, pitch / 2.0))
    underhead_radius = min(0.25, max(0.10, pitch / 4.0))
    return (
        f"{thread_designation} PER ASME B1.1-2024.",
        "ACCEPT THREADS USING SYSTEM 21 PER ASME B1.3-2007 (R2022).",
        "THREAD EXTENT FROM UNDERHEAD FILLET TO DISTAL START CHAMFER.",
        f"{min_full_form:.2f} MIN FULL THREAD FORM; INCOMPLETE THREAD 2P MAX "
        "AT EACH END.",
        f"DISTAL START CHAMFER C{lead_chamfer:.2f} +/-0.05 X 45 DEG +/-1 DEG.",
        f"UNDERHEAD FILLET R{underhead_radius:.2f} MAX, TANGENT TO SHANK AND "
        "BEARING FACE.",
        "THREAD LIMITS APPLY AFTER FINISH.",
        "DISTAL END FACE SQUARE TO THREAD AXIS; CONTROL PER FCF.",
        "THREAD GEOMETRY OMITTED IN VIEWS; SHANK OUTLINE REFERENCE ONLY.",
    )


def slotted_round_head_notes(
    *,
    head_dia_mm: float,
    head_height_mm: float,
    slot_width_mm: float,
    slot_depth_mm: float,
    axis_control_style: Literal["notes", "native"] = "notes",
) -> tuple[str, ...]:
    """Return controls for a cylindrical head with a straight driver slot."""
    controls = ()
    if axis_control_style == "notes":
        controls = (
            "HEAD OD TOTAL RUNOUT 0.10 RELATIVE TO THREAD PITCH-DIAMETER AXIS.",
            "BEARING FACE PERPENDICULAR 0.10 TO THREAD PITCH-DIAMETER AXIS.",
        )
    return (
        f"HEAD DIA {head_dia_mm:.2f} +/-0.10 X {head_height_mm:.2f} +/-0.10 HIGH.",
        *controls,
        f"DRIVER SLOT {slot_width_mm:.2f} +/-0.10 WIDE X "
        f"{slot_depth_mm:.2f} +/-0.10 DEEP.",
        "SLOT FLAT BOTTOM; DEPTH FROM TOP; MIDPLANE OFFSET FROM HEAD OD AXIS "
        "0.00 +/-0.05.",
    )


def hex_head_notes(*, across_flats_mm: float, head_height_mm: float) -> tuple[str, ...]:
    """Return controls for a custom regular-hex head."""
    return (
        f"CUSTOM REGULAR HEX HEAD {across_flats_mm:.2f} +/-0.10 ACROSS FLATS X "
        f"{head_height_mm:.2f} +/-0.10 HIGH.",
        "B18 HEAD DIMENSIONS DO NOT APPLY.",
    )


def reeded_head_notes(
    *, head_name: str, head_dia_mm: float, head_length_mm: float, groove_count: int
) -> tuple[str, ...]:
    """Return direct, inspectable geometry for the modeled axial reeding."""
    groove_radius = 0.50
    root_dia = head_dia_mm - 2.0 * groove_radius
    return (
        f"{head_name} DIA {head_dia_mm:.2f} +/-0.10 X "
        f"{head_length_mm:.2f} +/-0.10 LONG.",
        f"{head_name} OD TOTAL RUNOUT 0.10 RELATIVE TO THREAD PITCH-DIAMETER AXIS.",
        "BEARING FACE PERPENDICULAR 0.10 TO THREAD PITCH-DIAMETER AXIS.",
        f"{groove_count}X R{groove_radius:.2f} +/-0.05 AXIAL GROOVES, EQUALLY SPACED.",
        f"GROOVE ROOT DIA {root_dia:.2f} +/-0.10; FULL {head_name} LENGTH.",
    )
