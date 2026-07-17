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

# --- Nominal geometry (book ch. 22, pp. 54-55; see build_guide_lock.py for the
# bottom-station height derivation). These drive the part's named equation
# globals AND the drawing's coordinate math. ---
LOCK_WIDTH = 22.0  # along +X
LOCK_HEIGHT = 19.0  # along +Y; y = 0 is the guide-side edge
LOCK_THICK = 2.0  # extruded +Z

# Screw-hole layout on the guide-side band (matches the guide's hole pitch:
# the two stations sit x +-7 about the plate centre, 2.5 above the y=0 edge).
HOLE_XY = ((4.0, 2.5), (18.0, 2.5))
# Pinned #4-clearance CLOSE-fit drill (mm) -- the wizard-table value the part
# build cuts (``_holes.CLEARANCE_MM[("#4", "close")]``, re-pinned here so the
# drawing's view math stays COM-free; the lockstep test asserts equality).
HOLE_DIA_MM = 3.048

# --- Marked-dimension contract: feature -> the parametric dimension NAMES the
# print shows. ``build_guide_lock`` marks exactly these; ``draw_guide_lock``
# keeps exactly their union across its per-view ``keep`` maps. The wizard screw
# holes are deliberately NOT here: their size ships as a native hole callout
# and their locations as BASIC drawing dimensions tied to the datum edges. ---
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "LockProfile": {"Width", "Height"},
    "Lock": {"Depth"},
}

# True free-text instructions only. Geometry, datum structure, form, and
# roughness live in native dimensions / datum tags / FCFs / surface symbols.
# The part build stamps these strings into the SLDPRT; the drawing displays
# only $PRPSHEET links, so the print cannot silently diverge from its model.
DRAWING_NOTES = "\n".join(
    (
        "HOLE POSITION PER FCF.",
        "SCREW HOLES: #4 CLEARANCE DRILL THRU, CLOSE FIT,",
        "FOR #4 FILLISTER-HEAD SCREWS.",
        "MAKE FROM 2.0 COLD-ROLLED STRIP; 4 REQUIRED (2 PER GUIDE RAIL).",
        "BLACK OXIDE AFTER MACHINING.",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 2:1"
