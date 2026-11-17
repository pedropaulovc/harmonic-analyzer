"""Drawing-only text of the cone-gear indexing kit (MHA-DT-03-TL-00).

The plate's fitting steps and checks the release's ASSEMBLY.md prints
(ha_assembly_package, #2889), and the note sheet 1 prints in their place.
Only draw_dt_cone_gear_tl_indexing_assembly, ha_assembly_package (and their
tests) import this module. No SolidWorks.
"""

from __future__ import annotations

# Item 2 has no fitting here: the drive train's bonding step engages it. It
# shows under item 1 in the plate's face and edge views at its kit pose,
# ballooned there (rule 22); the sheet says where it is fitted.
COMB_FITTING_LINE = "ITEM 2 IS FITTED BY MHA-DT-00 STEP 1, NOT ON THE HEAD."

# Steps 1 and 4 reuse the head's own plate screws without a lock: owner
# ruling RV-01 (the kit's machinist_exceptions) accepts that joint. The head
# and its screws are shop equipment, named as such and not parts-list rows
# (RV-02). A step does one thing (rule 22).
HEAD = "PM BS-0 DIVIDING HEAD (SHOP EQUIPMENT)"
STEP_SECTIONS = (
    (
        f"FITTING ON THE {HEAD}",
        (
            "1. REMOVE THE HEAD'S STOCK INDEX PLATE; KEEP ITS THREE #8 FLAT HEAD "
            "SCREWS.",
            "2. SLIDE ITEM 1 ONTO THE HEAD'S PLATE HUB, COUNTERSUNK FACE OUT "
            "(SHEET 2).",
            "3. TURN ITEM 1 UNTIL ITS THREE COUNTERSINKS LINE UP WITH THE "
            "HEAD'S PLATE-SCREW TAPS.",
            "4. FIT THE SCREWS FROM STEP 1 AND TIGHTEN THEM EVENLY.",
            "5. SET THE CRANK PIN ON THE CIRCLE THE INDEXING TABLE (SHEET 1) NAMES.",
            "6. SET THE SECTOR ARMS TO SPAN THE PIN'S HOLE PLUS THE TABLE'S "
            "HOLE SPACES PER TOOTH (10 SPACES = 11 HOLES).",
        ),
    ),
)
ASSEMBLY_CHECKS = (
    "1. ITEM 1 SITS FLAT ON THE HEAD; NO SCREW HEAD STANDS PROUD.",
    "2. THE INDEX PIN DROPS INTO EVERY HOLE OF THE CHOSEN CIRCLE.",
    "3. INDEXING EVERY TOOTH OF ONE BLANK TURN BRINGS THE PIN BACK TO ITS "
    "STARTING HOLE.",
)
# Sheet 1's note where the steps stood; the indexing table under it keeps
# every setting (circle, spaces per tooth) on the sheet.
FITTING_NOTE = "\n".join(("FITTING STEPS AND CHECKS: ASSEMBLY.MD.", COMB_FITTING_LINE))
