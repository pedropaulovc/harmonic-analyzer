"""The narrative alignment-pinion record in dimensions.yaml tracks the CAD.

``cad/config/dimensions.yaml`` is read by no part, so nothing rebuilds when
the rig moves, and its alignment-pinion layout summary drifted three geometry
revisions behind (Codex P2s on #814: a 2.0 gap and −18.626 axis, 5 mm straps,
the Ø10.32/e1.4 scalloped cam, a 34.0 spring foot).  Every number the summary
and the two rig rows print is re-derived here from the constant that owns it,
at the places the prose prints, so the record cannot drift silently again.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

import build_drive_train_assembly as dt
import pinion_bracket_geometry as strap
from pinion_arbor_spec import SHAFT_LEN as ARBOR_LEN
import pinion_spring_geometry as spring

DIMENSIONS = Path(__file__).resolve().parents[1] / "config" / "dimensions.yaml"


def _strings(node: object) -> list[str]:
    if isinstance(node, str):
        return [node]
    if isinstance(node, dict):
        return [s for key, value in node.items() for s in _strings(key) + _strings(value)]
    if isinstance(node, list):
        return [s for item in node for s in _strings(item)]
    return []


def _prose() -> str:
    """Every string in the PARSED record, whitespace runs collapsed.

    Parsing first means a row that breaks the YAML (an unquoted ``r7: +1.4``
    once did, and only check:config noticed) fails here too, and quoting or
    escaping a row can never hide or fake a fragment."""
    record = yaml.safe_load(DIMENSIONS.read_text(encoding="utf-8"))
    return re.sub(r"\s+", " ", " ".join(_strings(record)))


def _mm(value: float, places: int = 3) -> str:
    """Format a signed value the way the record prints it (Unicode minus)."""
    return f"{value:.{places}f}".replace("-", "−")


def _expected_fragments() -> list[str]:
    authority = (dt.FPIN_DIA + dt.CAM_OD) / 2.0 - dt._D_ENG
    follower_reserve = dt._FPIN_TIP_S - dt._S_CAM_ENG
    return [
        # Layout summary.
        f"U28 {dt.APINION_GAP} mm parked tip gap",
        f"machine ({_mm(dt.APINION_X)}, {dt.APINION_Y:g})",
        f"drum tip {dt.TIP_DRUM120:.3f} + pinion tip {dt.TIP_APINION:.3f} "
        f"+ {dt.APINION_GAP} disengaged gap",
        f"drum z {_mm(dt.APINION_Z_FRONT)}..+{dt.APINION_Z_BACK:.3f}",
        f"face {dt.APINION_Z_BACK - dt.APINION_Z_FRONT:.1f}",
        f"root z {_mm(dt.ARBOR_Z0)}..+{dt.ARBOR_Z0 + ARBOR_LEN:.3f}",
        f"head/crossrod axis z {_mm(dt.HANDLE_Z)}",
        f"crossrod at +{dt.HANDLE_TILT_DEG:g}°",
        f"Straps: {strap.WIDTH:g} wide × {strap.THICKNESS:g} thick with "
        f"R{strap.R_END:g} ends, plain (no cam relief)",
        f"pivot ({_mm(dt.PIVOT_X)}, {dt.PIVOT_Y:g})",
        f"c2c {dt.STRAP_C2C:.1f}",
        f"{dt.STRAP_LEAN_DEG:.3f}° lean",
        f"bores at ({_mm(dt.LIFT_X)}, {_mm(dt.LIFT_Y)})",
        f"The collar is Ø{dt.CAM_OD:g} with a {dt.CAM_ECC:.1f} eccentricity "
        f"and keeps a {dt.CAM_THIN_SIDE_WALL:.3f} thin-side wall",
        f"Parked surface gap is {dt._PARK_GAP:.3f}",
        f"{_mm(dt.CAM_ENGAGE_ROTATION_DEG)}° cam rotation gives "
        f"{authority:.3f} mm engaged authority and leaves "
        f"{follower_reserve:.3f} mm of follower pin",
        # Engage-lever row.
        f"the {_mm(dt.CAM_ENGAGE_ROTATION_DEG)}° eccentric-cam contact rotation "
        f"carries it through vertical to {_mm(dt.LEVER_ENGAGED_TILT_DEG)}°",
        f"ecc {dt.CAM_ECC:.1f}, {dt.CAM_THIN_SIDE_WALL:.3f} thin-side wall",
        f"solves {_mm(dt.CAM_ENGAGE_ROTATION_DEG)}° cam rotation and a "
        f"{_mm(dt.LEVER_ENGAGED_TILT_DEG)}° engaged lever",
        # Return-spring row: the numbers only.  The strip material is prose
        # the spring owner may change, not a dimension this record derives.
        f"{spring.THICK:g} × {spring.WIDTH:.1f} ",
        f"{spring.FOOT_LEN:.1f} foot",
    ]


def test_alignment_pinion_record_matches_the_cad_constants() -> None:
    prose = _prose()
    missing = [fragment for fragment in _expected_fragments() if fragment not in prose]
    assert not missing, "dimensions.yaml drifted from the CAD:\n" + "\n".join(missing)


def test_superseded_rig_values_are_gone() -> None:
    prose = _prose()
    for stale in (
        "−18.626",
        "15 wide × 5 thick",
        "Ø10.32",
        "cam eccentricity is 1.4",
        "R6.90 bracket scallops",
        # Only the retired follower-stud sentence: dt-crank's 64T crank-drive
        # gear row legitimately allows a silver-brazed shaft joint.
        "follower-stud mouth is silver-brazed",
        "34.0 foot",
        "−81.793",
        "2.115 thin-side",
        "retained 2 mm parked tip gap",
    ):
        assert stale not in prose, stale
