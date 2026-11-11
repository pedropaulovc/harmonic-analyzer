"""Drawing presentation the MHA-MS-01 stick part authors for its print.

The part builder writes each callout below its source dimension, each count
prefix ahead of it and each closing suffix after it, and reads them back; the
drawing imports the dimensions with that text and only reads it back.  Setting
text from the drawing writes through to the imported source dimension (#1942;
``cad/docs/pipeline/evidence/vm2-datum-placement/source-hash-cause.md``).
The builder also authors the sheet notes and view labels as part properties
the drawing links, and names the ruled-face isometric octant the drawing
places.  Kept out of ``ms_stick_spec``, which the measuring stick assembly
imports.
"""

from __future__ import annotations

import _config
import ms_stick_spec as part

CALLOUT_BELOW = 4  # swDimensionTextCalloutBelow
PREFIX = 1  # swDimensionTextPrefix
SUFFIX = 2  # swDimensionTextSuffix

# The engraving is on the z=0 face, seen from -Z. Built-in *Isometric looks
# from +X+Y+Z at the plain back face. Viewing from +X-Y-Z with the view turned
# 180 degrees on the sheet shows the ruled face as the front view does:
# scale zero left, graduations along the lower edge, numerals upright, with
# the plain y=0 edge as the top face.
RULED_FACE_ISOMETRIC_OCTANT = (1, -1, -1)

# Sheet 1's numbered notes (rule 7). The bar section's two sizes share one
# fit, and scale zero and the graduation stations share one function: each
# names its mate once, in the note its dimensions and the station table link
# (rule 4). The table on sheet 2 links the sheet 1 note by sheet.
REBATE_NOTE_NUMBER = 1
STATION_NOTE_NUMBER = 2
DRAWING_NOTES = (
    f"{REBATE_NOTE_NUMBER}. SLIDING FIT IN {_config.parts('ms-stop-block')['number']} STOP BLOCK REBATE\n"
    f"{STATION_NOTE_NUMBER}. SETS {_config.parts('ch-amplitude-bar')['number']} AMPLITUDE BAR STATIONS\n"
    # The model's stroke shapes are representative; the shop's own
    # single-stroke sans font engraves the same V at the dimensioned height
    # and gaps.
    "3. NUMERALS: ANY SINGLE-STROKE SANS FONT"
)
REBATE_LINK = f"SEE NOTE {REBATE_NOTE_NUMBER}"
STATION_LINK = f"SEE NOTE {STATION_NOTE_NUMBER}"
STATION_LINK_FROM_SHEET_2 = f"{STATION_LINK}, SHEET 1"

# View labels (rule 9). Each detail's parent on sheets 2-4 is a reduced copy
# of a sheet 1 view, so it carries that view's name and its own scale; the
# section G-G parent is the front view unturned, at the sheet's scale.
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:2"
PARENT_VIEW_NOTE = "FRONT VIEW SCALE 1:2"
BOTTOM_PARENT_VIEW_NOTE = "BOTTOM VIEW SCALE 1:2"
# Unturned so SolidWorks prints each G clear of its arrow (machinist review,
# run 20261031T082305583Z-d97607f2); the label says it is turned.
SECTION_PARENT_VIEW_NOTE = "FRONT VIEW ROTATED 180°"

# dimension name -> the rows printed below its value (rule 7: a location
# carries its value and band; a callout at most two lines of words).
CALLOUTS: dict[str, str] = {
    "BodyWidth": REBATE_LINK,
    "BodyThickness": REBATE_LINK,
    "ScaleStartX": STATION_LINK,
    "Tick0Width": f"ALL GRADUATIONS\n{part.GRADUATION_WIDTH_CALLOUT}",
    # Delegated ruling 2026-11-11 (#2433, pending owner confirmation, #2144):
    # the graduations' V angle prints from the spec as NumeralDepth's does,
    # following the 2026-10-23 owner ruling on the numeral V (one bit cuts
    # both); the model drafts each wall half of it.
    "TickDepth": (f"GRADUATIONS: {part.ENGRAVING_V_INCLUDED_ANGLE_DEG:g}° INCLUDED V\n"
                  f"{part.GRADUATION_FLOOR_CALLOUT}"),
    "FullTickLength": "FULL TICKS",
    "MinorTickLength": "MINOR TICKS",
    "HalfTickLength": "HALF-DIVISION TICK",
    "NumeralHeight": "NUMERAL HEIGHT",
    # Section G-G cuts the zero, so the callout names the numerals and their V
    # (rule 9), then the stock under it; the block fits between detail F and G-G.
    "NumeralDepth": (f"NUMERALS: {part.ENGRAVING_V_INCLUDED_ANGLE_DEG:g}° INCLUDED V\n"
                     f"{part.NUMERAL_FLOOR_CALLOUT}"),
}
# dimension name -> its prefix: detail A's pitches open their reference
# parentheses; detail F's gaps carry a count (rule 10: one nX callout), since
# they hold for every numeral beside its tick: the tick-edge gap for 0-9 on
# the +X side (the 10 has its own detail), the tick-end gap for all eleven.
PREFIXES: dict[str, str] = {
    "FullTickPitch": "(",
    "MinorTickPitch": "(",
    "NumeralXGap": f"{part.DIVISION_COUNT - 1}X ",
    "NumeralYGap": f"{part.DIVISION_COUNT}X ",
}
# Detail A's pitches show the pattern as references (rule 10: the station
# table, not a chain of pitches, locates every graduation from zero).
SUFFIXES: dict[str, str] = {"FullTickPitch": ")", "MinorTickPitch": ")"}
# Each native text lane and the text the part authors in it.
LANES: tuple[tuple[int, dict[str, str]], ...] = (
    (CALLOUT_BELOW, CALLOUTS), (PREFIX, PREFIXES), (SUFFIX, SUFFIXES),
)

# Sheet 2's graduation station table (rules 10 and 26: a location is a table
# row, baseline from the zero tick that 2.224 locates from the end face).
# Graduation k (0 at scale zero) sits k minor pitches from zero; a row is a
# numeral's full tick, a column the minor ticks past it, so every cell is
# one station's printed X.
STATION_TABLE_TITLE = (
    "GRADUATION STATIONS: X FROM ZERO TICK, EACH ±.002\n"
    "ROW = NUMERAL'S TICK; COLUMN = MINOR TICKS PAST IT\n"
    f"{STATION_LINK_FROM_SHEET_2}"
)
STATION_ROW_HEADING = "NUMERAL"


def station_x_text(index: int) -> str:
    """Graduation ``index``'s printed X from the zero tick (.XXX inch)."""
    return part.inch_text(index * part.MINOR_SPACING, 3)


def station_table_columns() -> tuple[str, ...]:
    """The table's columns, each one note: the numeral column, then one
    column per minor tick past the numeral's tick (only the 10 has none)."""
    numerals = range(part.DIVISION_COUNT)
    columns = ["\n".join([STATION_ROW_HEADING, *(str(numeral) for numeral in numerals)])]
    for minor in range(part.MINOR_PER_DIVISION):
        last = (part.DIVISION_COUNT - 1) * part.MINOR_PER_DIVISION
        cells = [
            station_x_text(index)
            for numeral in numerals
            if (index := numeral * part.MINOR_PER_DIVISION + minor) <= last
        ]
        columns.append("\n".join([f"+{minor}", *cells]))
    return tuple(columns)


def _owners() -> dict[str, str]:
    authored = {name for _lane, texts in LANES for name in texts}
    owners: dict[str, list[str]] = {}
    for feature, names in part.DRAWING_DIMENSIONS.items():
        for name in names:
            owners.setdefault(name, []).append(feature)
    missing = sorted(authored - set(owners))
    if missing:
        raise AssertionError(
            f"callouts name dimensions the part does not mark: {missing}"
        )
    shared = {
        name: features
        for name, features in owners.items()
        if name in authored and len(features) != 1
    }
    if shared:
        raise AssertionError(
            f"callout dimensions marked on more than one feature: {shared}"
        )
    return {name: owners[name][0] for name in sorted(authored)}


# dimension name -> the feature that owns it (the builder's lookup key), for
# every dimension with authored text in any lane.
FEATURE_OF: dict[str, str] = _owners()


def callout_rows(text: str) -> tuple[str, ...]:
    """A callout's rows, independent of CRLF line endings."""
    return tuple(row.strip() for row in text.replace("\r", "").split("\n"))
