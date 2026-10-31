"""Dimension text the two stop parts author on their own model dimensions.

The part builds write each row below (or the quantity prefix before) its
source dimension and read it back; the drawings import the dimensions with
that text and only read it back.  Setting text from a drawing writes through
to the imported source dimension and dirties the part (#1942;
``cad/docs/pipeline/evidence/vm2-datum-placement/source-hash-cause.md``), so
no stop sheet presents an imported dimension itself.  Kept out of
``ms_stop_spec``, which the measuring stick assembly imports, so a wording
edit never re-keys that recipe.
"""

from __future__ import annotations

import _config
import ms_stop_spec as spec

# swDimensionTextParts_e: the definition (with variables) a prefix is written
# over, the prefix itself, and the lane below the value.
PREFIX = 1  # swDimensionTextPrefix
CALLOUT_BELOW = 4  # swDimensionTextCalloutBelow
PREFIX_DEFINITION = 5  # swDimensionTextPrefixDefinition

STICK_FIT = f"SLIDING FIT ON\nMS-STICK {_config.parts('ms-stick')['number']}"
BLOCK_NUMBER = _config.parts("ms-stop-block")["number"]
HOLE_STATION_FIT = f"LOCATES MS-STOP-BLOCK\n{BLOCK_NUMBER} TAPS"

# Block: the rebate bands exist only for the stick that slides in it.
BLOCK_CALLOUTS: dict[str, str] = {
    "RoofChamferSize": "2 CORNERS",
    "WindowWidth": f"OPEN REBATE\n{STICK_FIT}",
    "WindowHeight": STICK_FIT,
}
# Cover: the master stations become the block's tapped-hole stations, its
# thickness sets the screws' reach into the blind taps, and the earlier pilot
# step is drilled through both parts clamped.
PLATE_CALLOUTS: dict[str, str] = {
    "PilotDrillDiameter": (
        "LAYOUT ON THIS PLATE; PILOT\n"
        f"THROUGH INTO MS-STOP-BLOCK {BLOCK_NUMBER}\n"
        f"CLAMPED, {spec.MATCH_DRILL_DATUM_ALIGNMENT}\n"
        f"{spec.MATCHED_PAIR_NOTE}"
    ),
    **{name: HOLE_STATION_FIT for name in spec.PLATE_LOCATION_DIMENSIONS},
    "PlateThickness": f"SETS SCREW REACH IN\nMS-STOP-BLOCK\n{BLOCK_NUMBER} TAPS",
}
# Quantity prefixes written before the model's own prefix definition (the
# pilot keeps its <MOD-DIAM>); the chamfer angle keeps its native text.
PLATE_PREFIXES: dict[str, str] = {
    "PilotDrillDiameter": "2X ",
    "RoofChamferSize": "2X ",
}


def owners(
    dimensions: dict[str, set[str]], names: set[str] | frozenset[str]
) -> dict[str, str]:
    """``{dimension: feature}`` for ``names``, each marked on exactly one feature."""
    found: dict[str, list[str]] = {}
    for feature, marked in dimensions.items():
        for name in marked & set(names):
            found.setdefault(name, []).append(feature)
    missing = sorted(set(names) - set(found))
    if missing:
        raise AssertionError(f"text names dimensions the part does not mark: {missing}")
    shared = {name: features for name, features in found.items() if len(features) != 1}
    if shared:
        raise AssertionError(
            f"text dimensions marked on more than one feature: {shared}"
        )
    return {name: features[0] for name, features in found.items()}


BLOCK_FEATURE_OF = owners(spec.BLOCK_DRAWING_DIMENSIONS, set(BLOCK_CALLOUTS))
PLATE_FEATURE_OF = owners(
    spec.PLATE_DRAWING_DIMENSIONS, set(PLATE_CALLOUTS) | set(PLATE_PREFIXES)
)


def callout_rows(text: str) -> tuple[str, ...]:
    """A callout's rows, independent of CRLF line endings."""
    return tuple(row.strip() for row in text.replace("\r", "").split("\n"))
