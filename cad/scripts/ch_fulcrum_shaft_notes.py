r"""Fulcrum shaft (MHA-CH-04) drawing-only data: the callouts, the
manufacturing note and the isometric label the part build stamps into the
SLDPRT.

Kept out of ``ch_fulcrum_shaft_spec`` (the ``ch_rocker_arm_notes`` split): the
channel assembly and the lever drawing import the spec, so prose there would
re-key them on every sheet edit. Imported ONLY by ``build_ch_fulcrum_shaft``,
``draw_ch_fulcrum_shaft`` and the offline test.
"""

from __future__ import annotations

# The shaft is the bought 1/4 ground rod, its O.D. never cut: the sheet
# prints the stock as a fraction reference with this line under it, not
# limits of size (drawing-guidelines.md rule 4, "A diameter that is bought to
# size and never cut prints the stock"; owner ruling 2026-11-20, #2346: buy
# ground rod). The keeper bores name this shaft as their mate (F DRILL THRU,
# SLIDING CLEARANCE ON MHA-CH-04; owner ruling 2026-11-24, fit audit
# question 1), so the shaft carries no fit statement of its own. No line
# ends in punctuation: the widest row ends on the dimension's vertical
# leader, and a trailing ';' touched it (machinist review r2).
SHAFT_DIA_CALLOUT = "GROUND ROD, AS SUPPLIED"
# AcrossFlat's .XXX is the set screw's seat height: it sets both the >= 1.5D
# engagement and the proud limit (a .XX band breaks both).
ACROSS_FLAT_CALLOUT = "SETS MHA-CH-VN-55\nENGAGEMENT"
# rule 7: the one part-specific fact the views cannot carry.
DRAWING_NOTES = "CENTRE MARKS .04 DEEP MAX."
# The isometric renders at ISO_SCALE (1, 1) while the sheet/title block reads
# 2:1, so without this the pictorial is silently half scale.
ISO_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:1"
