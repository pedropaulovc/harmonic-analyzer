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
# fit, and the graduation stations share one function: each names its mate
# once, in the note its dimensions and the station table link (rule 4). The
# table on sheet 2 links the sheet 1 note by sheet.
# Rule 4 (fitted pairs): a fit name alone is incomplete, so note 1 gives the
# acceptance by feel against the MHA-MS-02 rebate. The rebate keeps its own
# .330 x .134 +.010/0 (owner ruling 2026-11-21, ms_stop_spec
# WINDOW_SIZE_TOLERANCE_MM), so this note does not make it to the stick: one
# controlling value per feature (rule 7). No shake limit: the thumbscrew
# seats the stick on the roof, taking out the designed clearance.
REBATE_NOTE_NUMBER = 1
STATION_NOTE_NUMBER = 2
DRAWING_NOTES = (
    f"{REBATE_NOTE_NUMBER}. SLIDING FIT IN {_config.parts('ms-stop-block')['number']} STOP BLOCK REBATE: "
    "STICK SLIDES FULL LENGTH\n"
    f"{STATION_NOTE_NUMBER}. SETS {_config.parts('ch-amplitude-bar')['number']} AMPLITUDE BAR STATIONS\n"
    # The model's stroke shapes are representative; the shop's own
    # single-stroke sans font engraves the same V at the dimensioned height
    # and gaps.
    "3. NUMERALS: ANY SINGLE-STROKE SANS FONT"
)
REBATE_LINK = f"SEE NOTE {REBATE_NOTE_NUMBER}"
# Rule 4 (stock that is good enough stays stock): the thickness is the 1/8
# flat's as supplied (owner ruling 2026-11-20, #2441, option B), printed as a
# reference over the stock it is, as MHA-PN-02's "1/8 CF FLAT".
THICKNESS_STOCK = "1/8 FLAT AS SUPPLIED"
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
    "BodyThickness": f"{THICKNESS_STOCK}\n{REBATE_LINK}",
    # The station table locates the 10 tick with every other graduation;
    # sheet 1 shows its distance from the datum face as a reference.
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
# dimension name -> its prefix: detail A's pitches and the stock thickness
# open their reference parentheses; detail F's gaps carry a count (rule 10:
# one nX callout), since they hold for every numeral beside its tick: the
# tick-edge gap for 0-9 on the +X side (the 10 has its own detail), the
# tick-end gap for all eleven.
PREFIXES: dict[str, str] = {
    "BodyThickness": "(",
    "Tick10FromEnd": "(",
    "FullTickPitch": "(",
    "MinorTickPitch": "(",
    "NumeralXGap": f"{part.DIVISION_COUNT - 1}X ",
    "NumeralYGap": f"{part.DIVISION_COUNT}X ",
}
# Detail A's pitches and the 10 tick's land show as references (rule 10: the
# station table, not a chain from the 10 tick, locates every graduation from
# the end face); the thickness is the stock's (THICKNESS_STOCK).
SUFFIXES: dict[str, str] = {
    "BodyThickness": ")", "Tick10FromEnd": ")", "FullTickPitch": ")", "MinorTickPitch": ")",
}
# Each native text lane and the text the part authors in it.
LANES: tuple[tuple[int, dict[str, str]], ...] = (
    (CALLOUT_BELOW, CALLOUTS), (PREFIX, PREFIXES), (SUFFIX, SUFFIXES),
)

# Sheet 2's graduation station table (rules 10 and 26: a location is a table
# row, baseline from one datum). The datum is the end face nearest the 10,
# the face that bears on the bar (#2434). Graduation k (0 at scale zero) sits
# k minor pitches from zero, so the 10 tick's land plus (100 - k) pitches
# from that face; a row is a numeral's full tick, a column the minor ticks
# past it, so every cell is one station's printed distance.
STATION_TABLE_TITLE = (
    "GRADUATION STATIONS FROM END FACE NEAREST 10, EACH ±.002\n"
    "ROW = NUMERAL'S TICK; COLUMN = MINOR TICKS PAST IT\n"
    f"{STATION_LINK_FROM_SHEET_2}"
)
STATION_ROW_HEADING = "NUMERAL"
LAST_GRADUATION = (part.DIVISION_COUNT - 1) * part.MINOR_PER_DIVISION


def station_x_text(index: int) -> str:
    """Graduation ``index``'s printed distance from the end face nearest the
    10 (.XXX inch)."""
    return part.inch_text(
        part.SCALE_END_MARGIN + (LAST_GRADUATION - index) * part.MINOR_SPACING, 3)


def station_table_columns() -> tuple[str, ...]:
    """The table's columns, each one note: the numeral column, then one
    column per minor tick past the numeral's tick (only the 10 has none)."""
    numerals = range(part.DIVISION_COUNT)
    columns = ["\n".join([STATION_ROW_HEADING, *(str(numeral) for numeral in numerals)])]
    for minor in range(part.MINOR_PER_DIVISION):
        cells = [
            station_x_text(index)
            for numeral in numerals
            if (index := numeral * part.MINOR_PER_DIVISION + minor) <= LAST_GRADUATION
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
