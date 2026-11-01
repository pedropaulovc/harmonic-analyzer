"""Pure-data manufacturing contract for the platen guide.

Issue #290: the sheet prints decimal inch (``drawing_unit: in``); bands and
limits stay physical millimetres, each the exact decimal of its inch value.
"""

import _config
from _gtol_planar import PlanarFace
from _hole_spec import HoleSpec
from _package_units import drawing_unit
from _surface_finish import MACHINED_UM, SurfaceFinishControl

UNIT = drawing_unit("parts/pd-platen-guide", _config.parts("pd-platen-guide"))

# R9-64: the guide screws' front receivers are #4-40 tapped THROUGH the rail,
# as R9-48 made the rear row. A blind tap cannot hold full thread to the
# screw's 5.42 reach and keep a bottoming tap's lead above the drill bottom
# without the drill point breaking through a faced lock seat, so the hole has
# no thread or drill depth to stack. The tips stop inside the rail
# (build_pd_platen_guide asserts the reach).
TAPPED_HOLE_SPEC = HoleSpec("tapped", "#4-40")

# The guide-lock screws' rear receivers (R9-48): #4-40 tapped THROUGH the
# rail, so the full depth carries thread and no depth band can starve
# the 3/8 in MHA-PD-VN-60 screws (pd_vn_guide_lock_screw_spec.ENGAGEMENT_WORST). The
# tips stop inside the rail (build_pd_platen_guide asserts the reach).
LOCK_TAP_SPEC = HoleSpec("tapped", "#4-40")

# Owner ruling 2026-11-01 (option B2): the rail is .29 tall and both tap rows
# stand .140 above datum B (local y 0, the bottom face), so each #4-40 major
# with its Ø.008 position keeps .080 to datum B and to the top face at the
# height's .XX minimum (build_pd_platen_guide asserts both walls). The bottom
# rail's datum B stays on the frame's GUIDE_Y over the rack backer, so both
# rails grow into the support bar's channel (pd_support_bar_spec.BAR_HEIGHT).
GUIDE_HEIGHT = 7.366  # .29
TAP_Y = 3.556  # .140

# The rail's depth (``build_pd_platen_guide.GUIDE_DEPTH``) sets how far behind the
# bar's back face the lock plates ride and how close their slotted pan heads
# come to the hanger arm and its plate. Both sit inside the paper-drive
# lock-station sweep, so the depth carries an explicit one-sided band, native
# on Depth@Guide: never deeper than the .40 nominal (the heads keep their
# room to the arm plate), and on the shallow side no shallower than the
# deepest bar plus the fitted lock gap's max (R9-47: so the seat facing
# always cuts; build_pd_platen_guide asserts it). It prints .XX.
GUIDE_DEPTH_BAND = (0.0, -0.254)  # (upper, lower): +.00/-.01
GUIDE_DEPTH_PLACES = 2
# The one-sided band's function, printed at the depth (rule 4): a deeper rail
# stands the lock-screw heads closer to the hanger's arm plate.
GUIDE_DEPTH_CALLOUT = (
    f"LOCK-SCREW HEADS\nCLEAR {_config.parts('pd-transgear-arm-plate')['number']}"
)

# The print's dimensions, by owning feature (the build marks exactly these and
# the sheet imports only these), and the places each carries, authored on the
# model (drawing-simplicity-policy.md `How the repository implements the guidelines`). The height prints at the depth's places (the
# lock-station sweep reads it so). The length prints .XX: the rail ends meet
# the platen's edges, which the platen sheet prints at .XX; the holes locate
# from the left end at basic stations, so no stack reads its band.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "GuideProfile": {"Length", "Height"},
    "Guide": {"Depth"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "GuideProfile": {"Length": 2, "Height": GUIDE_DEPTH_PLACES},
    "Guide": {"Depth": GUIDE_DEPTH_PLACES},
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}
if {f: set(d) for f, d in DRAWING_PRECISION.items()} != DRAWING_DIMENSIONS:
    raise AssertionError("every marked platen-guide dimension needs native precision")

# R9-47 (Main-approved fit-up): the lock gap, lock-plate front face to the
# bar's back face, as fitted by facing the rail backs under the lock plates
# (the lock seats; pd_paper_drive_assembly_steps "lock-seats-faced"). It is the
# platen's float: (min, max), on .002 and .009 feelers. Its max bounds how far
# the platen can come forward toward the 120T disc. The as-made gap is never
# under the max (build_pd_platen_guide asserts it), so the facing always cuts.
LOCK_GAP_FIT = (0.0508, 0.2286)  # .002, .009
# Printed on the paper-drive assembly sheet (still millimetres), so it names
# its unit: the feelers are inch.
LOCK_GAP_FIT_TEXT = (
    "-".join(f"{gap / 25.4:.3f}".lstrip("0") for gap in LOCK_GAP_FIT) + " IN"
)


# Manufacturing GD&T limits consumed by the part's drawing projection: the
# printed inch zone, and its exact millimetres for the stacks.
GEOMETRIC_TOLERANCES_IN: dict[str, str] = {
    "guide hole-pattern position": ".008",
}
GEOMETRIC_TOLERANCES_MM: dict[str, float] = {
    key: float(value) * 25.4 for key, value in GEOMETRIC_TOLERANCES_IN.items()
}

# The one running surface (drawing-guidelines.md rule 6 (roughness symbols only where a surface runs, slides or locates)): the platen HANGS by the top rail's
# bottom face (local y 0, datum B) on the support bar's top edge and slides
# along it across the feed. Both rails are this part, so the face is cut on
# both. Every other face is cast/machined per the title block. The symbol
# names the bar it slides on.
SURFACE_FINISHES = (
    SurfaceFinishControl(
        "bar_slide",
        MACHINED_UM,
        PlanarFace((0, -1, 0), 0.0),
        production_method=f"SLIDES ON {_config.parts('pd-support-bar')['number']}",
        display_unit=UNIT,
    ),
)
