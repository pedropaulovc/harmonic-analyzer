r"""Guide-lock dimensional contract -- the single source of truth shared by the
part build (``build_guide_lock.py``) and its manufacturing drawing
(``draw_guide_lock.py``).

PURE DATA, no SolidWorks/COM imports: the nominal geometry (the "editable
knobs"), the hole layout the drawing needs for its view math, and the
marked-dimension -> kept-dimension NAME map. Keeping this in ONE module means a
rename or a nominal change is a single edit that reaches both scripts, so the
part-side ``mark_dimensions_for_drawing`` set and the drawing-side ``keep``
maps cannot silently drift apart (see ``crank_arm_spec.py`` for the pattern's
build-graph rationale).

The offline lockstep test (``test_guide_lock_drawing.py``) asserts the part
marks and the drawing keeps EXACTLY ``DRAWING_DIMENSIONS`` -- the drift alarm,
run without SolidWorks in ~1 s.
"""

from __future__ import annotations

from _hole_spec import HoleSpec

# --- Nominal geometry (book ch. 22, pp. 54-55; see build_guide_lock.py for the
# bottom-station height derivation). These drive the part's named equation
# globals AND the drawing's coordinate math. ---
LOCK_WIDTH = 22.0  # along +X
LOCK_HEIGHT = 15.0  # along +Y; y = 0 is the guide-side edge (2026-09-02
# user re-read of ch22 p.54: a LOW lock -- 5 rail + 7 channel + 3 bar overlap)
LOCK_THICK = 2.0  # extruded +Z

# Screw-hole layout on the guide-side band (matches the guide's hole pitch:
# the two stations sit x +-7 about the plate centre, 2.5 above the y=0 edge).
# R9-49: 1/8 DRILL (Ø3.175) over the #4-40 majors carries this plate's Ø0.10
# and the rail taps' Ø0.20 position (guide_lock_screw_spec.LOCK_SET_OFFSET);
# the #4 close Ø3.048 left 0.20 of the 0.30 needed.
HOLE_XY = ((4.0, 2.5), (18.0, 2.5))
HOLE_SPEC = HoleSpec("drilled_fractional", "1/8")

# --- Marked-dimension contract: feature -> the parametric dimension NAMES the
# print shows. ``build_guide_lock`` marks exactly these; ``draw_guide_lock``
# keeps exactly their union across its per-view ``keep`` maps. The wizard screw
# holes are deliberately NOT here: their size ships as a native hole callout
# and their locations as BASIC drawing dimensions tied to the datum edges. ---
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "LockProfile": {"Width", "Height"},
    "Lock": {"Depth"},
}

# Places and explicit bands the print carries on those dimensions, the ones the
# paper-drive lock-station sweep judges the plate at (policy rule 12). The
# bottom-station plate's far edge passes 0.135 from the pivot spacer and 0.47
# from the latch-hook bracket, and its back face carries the button heads past
# the hanger arm. So the height never runs over 15 (+0/-0.25), and the
# thickness of the cold-rolled strip prints .XXX (±0.13). The width stays at
# the .XX row.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "LockProfile": {"Width": 2, "Height": 2},
    "Lock": {"Depth": 3},
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}
if DRAWING_PRECISION.keys() != DRAWING_DIMENSIONS.keys() or any(
    set(DRAWING_PRECISION[feature]) != names
    for feature, names in DRAWING_DIMENSIONS.items()
):
    raise AssertionError("every marked guide-lock dimension needs authored places")
LOCK_HEIGHT_BAND = (0.0, -0.25)  # (upper, lower), native on Height

# True free-text instructions only. Geometry, datum structure, form, and
# roughness live in native dimensions / datum tags / FCFs / surface symbols.
# The part build stamps these strings into the SLDPRT; the drawing displays
# only $PRPSHEET links, so the print cannot silently diverge from its model.
DRAWING_NOTES = "\n".join(
    (
        "HOLE POSITION PER FCF.",
        "SCREW HOLES PASS #4-40 BUTTON-HEAD SOCKET CAP SCREWS.",
        "MAKE FROM 2.0 COLD-ROLLED STRIP; 4 REQUIRED (2 PER GUIDE RAIL).",
        "BLACK OXIDE AFTER MACHINING.",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 2:1"


# Manufacturing GD&T limits consumed by the part's drawing projection.
GEOMETRIC_TOLERANCES_MM: dict[str, str] = {
    "screw-hole position": "0.10",
    "rail-mating face flatness": "0.10",
}
