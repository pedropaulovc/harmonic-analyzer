"""MHA-FR-00's printed settings and bench acceptances, as sheet text.

The values are the parts' and the frame's (fr_frame_attachment_spec,
fr_frame_setting_bands, the castings' far-wall stacks, fr_tube_frame_spec);
this drawing-only module composes what the fitter sheet prints from them, so
draw_fr_frame_assembly places the text and owns none of it (drawing
specification purity, test_drawing_specification_purity).
"""

from __future__ import annotations

import math

from _assembly_contract import assembly_contract
from _title_block_units import render_number
from fr_frame_attachment_spec import TOP_AXIS_HEIGHT_PLACES, TOP_SCREW_Y
from fr_frame_cross_screw import FAR_WALL_ENGAGEMENT_FLOOR_MM
from fr_frame_setting_bands import TOP_AXIS_HEIGHT_BAND_MM
from fr_harmonic_base_fasteners import base_cross_screw_far_wall_start_max_mm
from fr_top_frame_spec import TOP_CROSS_SCREW_FAR_WALL_START_MAX
from fr_tube_frame_spec import SUPPLY_LENGTH_MIN_IN as COLUMN_SUPPLY_LENGTH_MIN_IN
from fr_vn_frame_cross_screw_spec import SHANK_LEN as CROSS_SCREW_SHANK_LEN

# The fitter sheets print decimal inch (fr-frame.yaml ``drawing_unit``).
UNIT = assembly_contract("fr-frame").drawing_unit
# The top cross-bore axis height (fr_frame_attachment_spec TOP_AXIS_*) prints
# three places, 40.075, with its .XX-grade band (+/-.010). TOP_AXIS_SET_KEY
# sets all four corners' axes to this one absolute height from the base
# underside before the upper tube holes are match-drilled, so the frame's own
# .72 tap station off its rail top cannot carry it. MHA-FR-02's faced
# underside sits on the inch-grid plane (top_frame_plane, 39.358) the summing
# knife mounts clamp to, which puts its rail top (40.795) and this axis on the
# .001 grid. The setting step names the height and its band itself: the
# sheet-1 dimension carries its value and band and nothing else (rule 7).
TOP_AXIS_HEIGHT_TEXT = (
    f"{render_number(TOP_SCREW_Y / 25.4, UNIT, TOP_AXIS_HEIGHT_PLACES)} "
    f"±{render_number(TOP_AXIS_HEIGHT_BAND_MM / 25.4, UNIT, TOP_AXIS_HEIGHT_PLACES)}"
)
# The installed cross screw's far-wall engagement (rule 18), made checkable at
# the bench before the screw goes in (delegated ruling, machinist review
# 20261107T081227004Z): each MHA-FR-VN-53's full thread must reach from under
# its head past the print-worst start of full far-wall thread in either
# casting by the 1.5D floor. The base governs (its front pad chain); the
# limit rounds UP to the printed .001, so a screw that passes it engages at
# least 1.5D however its tip is chamfered.
CROSS_SCREW_FAR_WALL_START_MAX_MM = max(
    TOP_CROSS_SCREW_FAR_WALL_START_MAX,
    *(base_cross_screw_far_wall_start_max_mm(front=front) for front in (True, False)),
)
CROSS_SCREW_FULL_THREAD_MIN_IN = (
    math.ceil(
        (CROSS_SCREW_FAR_WALL_START_MAX_MM + FAR_WALL_ENGAGEMENT_FLOOR_MM) / 25.4 * 1000.0
        - 1e-9
    )
    / 1000.0
)
CROSS_SCREW_FULL_THREAD_MIN_TEXT = render_number(CROSS_SCREW_FULL_THREAD_MIN_IN, UNIT, 3)
CROSS_SCREW_FULL_THREAD_LIMIT_TEXT = f"{CROSS_SCREW_FULL_THREAD_MIN_TEXT} MIN"
if CROSS_SCREW_FULL_THREAD_MIN_IN * 25.4 >= CROSS_SCREW_SHANK_LEN:
    raise AssertionError("the cross-screw thread check exceeds the stock screw's length")
# The rough cut is the column's own supply length (fr_tube_frame_spec,
# printed on its sheet as SUPPLY n.nn MIN): round 1 review, "LONG" gave no
# length to cut to.
COLUMN_ROUGH_CUT_LENGTH_TEXT = f"{COLUMN_SUPPLY_LENGTH_MIN_IN:.2f} MIN"
