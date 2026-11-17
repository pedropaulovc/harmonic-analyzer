"""Drawing-only text of the T006 fly cutter (MHA-DT-37-TL-00).

The fitting steps the release's ASSEMBLY.md prints (ha_assembly_package,
#2889) and the stick-out note sheet 1 prints in their place. Only
draw_dt_cone_tip_gear_tl_cutter_assembly, ha_assembly_package (and their
tests) import this module. No SolidWorks.
"""

from __future__ import annotations

import dt_cone_tip_gear_spec as tip
import dt_cone_tip_gear_tl_cutter_spec as fixture

WINDOW_TEXT = "-".join(tip.inch_text(value, 3) for value in fixture.STICK_OUT_WINDOW)

# Item 3's cup bears on item 2's plain round: the stick-out is an adjustable
# clamp setting (drawing-guidelines rule 23), so the steps set it, then prove
# the clamp holds it.  Ends and faces go by view names (rule 22): item 1's
# cutting end is its bottom end in the front view.
STEP_SECTIONS = (
    (
        "FITTING",
        (
            "1. SLIDE ITEM 2 INTO ITEM 1'S CROSS HOLE, FORM END RIGHT, FACE "
            "TOWARD THE VIEWER (FRONT VIEW).",
            f"2. SET THE STICK-OUT {WINDOW_TEXT} (CALIPER).",
            "3. TURN ITEM 2 UNTIL ITS FACE IS PARALLEL TO ITEM 1'S AXIS: A "
            "SQUARE ON ITEM 1'S BOTTOM END (FRONT VIEW) SHOWS NO LIGHT "
            "BETWEEN ITS BLADE AND THE FACE.",
            "4. TIGHTEN ITEM 3, CUP END FIRST, UP THROUGH ITEM 1'S BOTTOM END "
            "(FRONT VIEW) ONTO ITEM 2'S ROUND SHANK.",
            "5. CHECK: ITEM 2 DOES NOT TURN OR SLIDE BY HAND.",
            f"6. CHECK: THE STICK-OUT STILL READS {WINDOW_TEXT} (CALIPER).",
            "7. IF STEP 5 OR 6 FAILS, LOOSEN ITEM 3 AND REPEAT FROM STEP 2.",
        ),
    ),
)
ASSEMBLY_CHECKS: tuple[str, ...] = ()
# Sheet 1's note where the steps stood: the stick-out's window is a
# measurable setting and acceptance, so it stays on the sheet (rule 22).
STICK_OUT_NOTE = "\n".join(
    (
        "FITTING STEPS: ASSEMBLY.MD.",
        f"STICK-OUT {WINDOW_TEXT} (CALIPER), SET BEFORE ITEM 3 IS",
        "TIGHTENED AND READ AGAIN AFTER.",
    )
)
