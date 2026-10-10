"""Pure native-hole contracts shared by part builds and drawings.

This module owns standard-table dimensions and declarative :class:`HoleSpec`
values. SolidWorks execution stays in ``_holes``; drawing placement stays in
``_drawing_common``. Part specification modules can therefore own one hole
identity without importing COM or duplicating its diameter and process text.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Cut diameters (mm) from this seat's wizard database and live feature probes.
# HoleDiameter commonly reads 0.0; a plain through hole's usable value is in
# ThruHoleDiameter (live #4 normal = 0.0032639 m). Scripts take analytic volume
# expectations from these pinned values; diag_hole_wizard.py re-proves the
# representative cases by measured volume.
TAP_DRILL_MM = {  # taps cut the tap-drill diameter (TAP_DRILL column)
    "#0-80": 1.191,  # 3/64 drill; not yet re-proved by a live wizard probe
    "#2-56": 1.778,
    "#3-48": 1.994,
    "#4-40": 2.261,
    "#6-32": 2.705,
    "#8-32": 3.454,
    "#10-24": 3.797,
    "#10-32": 4.0386,
    "1/4-20": 5.105,
    "5/16-18": 6.528,
    "3/8-16": 7.938,  # 5/16 drill
    "1/2-13": 10.716,
    "9/16-12": 12.304,
}
THREAD_MAJOR_MM = {  # basic external-thread major diameters (ASME B1.1)
    "#0-80": 1.524,
    "#2-56": 2.184,
    "#3-48": 2.515,
    "#4-40": 2.845,
    "#6-32": 3.505,
    "#8-32": 4.166,
    "#10-24": 4.826,
    "#10-32": 4.826,
    "1/4-20": 6.350,
    "5/16-18": 7.938,
    "3/8-16": 9.525,
    "1/2-13": 12.700,
    "9/16-12": 14.288,
}
CLEARANCE_MM = {  # (size, fit) -> hole diameter (CLOSE/NORMAL/LOOSE_FIT)
    ("#2", "close"): 2.388,
    ("#2", "normal"): 2.591,
    ("#2", "loose"): 2.946,
    ("#3", "close"): 2.692,
    ("#3", "normal"): 2.946,
    ("#3", "loose"): 3.251,
    ("#4", "close"): 3.048,
    ("#4", "normal"): 3.264,
    ("#4", "loose"): 3.658,
    ("#6", "close"): 3.912,
    ("#6", "normal"): 4.318,
    ("#6", "loose"): 4.699,
    ("#8", "close"): 4.572,
    ("#8", "normal"): 4.978,
    ("#8", "loose"): 5.410,
    ("1/4", "close"): 6.756,
    ("1/4", "normal"): 7.137,
    ("1/4", "loose"): 7.544,
    ("5/16", "close"): 8.331,
    ("5/16", "normal"): 8.738,
    ("5/16", "loose"): 9.119,
    ("1/2", "close"): 13.492,
    ("1/2", "normal"): 14.288,
    ("1/2", "loose"): 15.081,
    ("9/16", "close"): 14.684,
    ("9/16", "normal"): 15.080,
    ("9/16", "loose"): 15.479,
}
NUMBER_DRILL_MM = {  # number drills cut diameter exactly
    "#9": 4.978,
    "#19": 4.216,
    "#20": 4.089,
    "#21": 4.039,
    "#29": 3.454,
    "#14": 4.623,
    "#37": 2.642,
    "#43": 2.261,
    "#47": 1.994,
    "#54": 1.397,
    "#5": 5.220,  # 0.2055in: #10 screw clearance (pivot-bracket ledge)
}
FRACTIONAL_DRILL_MM = {
    "1/8": 3.175,
    "3/16": 4.763,
    "15/64": 5.953,
    "1/4": 6.350,  # reamed size (cone swing platform pivot bore, H7)
    "5/16": 7.938,
}
LETTER_DRILL_MM = {  # letter drills cut diameter exactly
    "F": 6.528,
    "V": 9.576,  # 0.377in (transgear stud seat)
    "X": 10.084,  # 0.397in: 3/8 free clearance
}

# 118-degree drill point: tip height = r * cot(59 deg). A blind wizard hole's
# depth runs to the flat shoulder; the point extends beyond it.
DRILL_POINT_H = 0.60086


@dataclass
class HoleSpec:
    """One native Hole Wizard definition shared by all feature instances."""

    kind: str
    size: str
    end: str = "through_all"
    depth_mm: float = 0.0
    thread_class: str = "2B"
    fit: str = "normal"
    overrides_mm: dict[str, float] = field(default_factory=dict)


def blind_cut_dia_mm(spec: HoleSpec) -> float:
    """Return the pinned cut diameter for a supported standard hole spec."""
    if spec.kind in ("tapped", "tapped_bottoming"):
        table, key = TAP_DRILL_MM, spec.size
    elif spec.kind == "clearance":
        table, key = CLEARANCE_MM, (spec.size, spec.fit)
    elif spec.kind == "drilled_number":
        table, key = NUMBER_DRILL_MM, spec.size
    elif spec.kind == "drilled_fractional":
        table, key = FRACTIONAL_DRILL_MM, spec.size
    elif spec.kind == "drilled_letter":
        table, key = LETTER_DRILL_MM, spec.size
    else:
        raise ValueError(f"diameter resolution is not supported for kind {spec.kind!r}")
    if key not in table:
        raise ValueError(
            f"size {key!r} not pinned for {spec.kind!r} -- add it to the "
            "table in _hole_spec.py (values from the wizard-database dump)"
        )
    return table[key]


def drill_process(spec: HoleSpec) -> str:
    """Render the drawing process prefix for a numbered/fractional/letter drill."""
    if spec.kind not in {"drilled_number", "drilled_fractional", "drilled_letter"}:
        raise ValueError(f"{spec.kind!r} is not a drill-size hole")
    return f"{spec.size} DRILL"
