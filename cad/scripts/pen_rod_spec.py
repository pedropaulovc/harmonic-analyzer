r"""Pure-data dimensional contract shared by the pen rod and drawing."""

from __future__ import annotations

from _gtol_spec import GeometricControl, PartDatum, PlanarFace


ROD_SECTION = 5.0  # DIMENSIONS.md ch24: square section (low)
ROD_LENGTH = 120.0  # DIMENSIONS.md ch24: p.64 inset (low)
WIRE_HOLE_Y = 115.0  # wire tie-off near the top (build_pen_assembly imports this)
WIRE_HOLE_DRILL = "#47"  # number drill (see _holes.NUMBER_DRILL_MM)
WIRE_HOLE_DIA = 1.994

# Geometric controls, authored on the MODEL as DimXpert PMI by the part build
# (_part_pmi.author_part_pmi) and IMPORTED onto the sheet — the sheet types no
# tolerance strings. The rod is a square bar (zero cylinders): datum A is the
# -X slide face, its opposite +X face rides parallel to it in the v-block, and
# the bottom end (-Y at y=0) is squared to the slide face.
PART_DATUMS = (
    # The v-block slide face the other functional faces are measured against.
    PartDatum("A", PlanarFace((-1, 0, 0), ROD_SECTION / 2.0)),
)
GEOMETRIC_CONTROLS = (
    GeometricControl(
        "opposite_slide_face_parallelism",
        "parallelism",
        "0.03",
        PlanarFace((1, 0, 0), ROD_SECTION / 2.0),
        datums=("A",),
    ),
    GeometricControl(
        "bottom_end_squareness",
        "perpendicularity",
        "0.05",
        PlanarFace((0, -1, 0), 0.0),
        datums=("A",),
    ),
)

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "RodProfile": {"Section", "Length"},
    "Rod": {"Depth"},
}

DRAWING_NOTES = "\n".join(
    (
        "USE DRAWN SQUARE BRASS BAR; KEEP FACES STRAIGHT AND SMOOTH - THE "
        "ROD SLIDES IN THE V-BLOCK GUIDE.",
        "DRILL WIRE HOLE #47 THRU; DEBURR BOTH FACES.",
    )
)
TOP_VIEW_NOTE = "TOP VIEW SCALE 4:1"
