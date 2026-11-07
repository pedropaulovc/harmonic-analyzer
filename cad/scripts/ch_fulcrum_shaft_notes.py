r"""Fulcrum shaft (MHA-CH-04) drawing-only data: the callouts, the
manufacturing note and the isometric label the part build stamps into the
SLDPRT.

Kept out of ``ch_fulcrum_shaft_spec`` (the ``ch_rocker_arm_notes`` split): the
channel assembly and the lever drawing import the spec, so prose there would
re-key them on every sheet edit. Imported ONLY by ``build_ch_fulcrum_shaft``,
``draw_ch_fulcrum_shaft`` and the offline test.
"""

from __future__ import annotations

# The shaft is the first-made part of the keeper fit (drawing-guidelines.md
# rule 4: the band lives here, the bore's .XXX is the mate's): one fit, named
# by its standard name and its mate. Its SHAFT_H band is narrower than the
# shop's turned-diameter row, so the callout names the route at the feature:
# bought ground stock (fan-out F1, delegated ruling 2026-11-07). One fit
# statement per feature (rule 7: a second mate's sentence is narration, and a
# callout carries two lines of words). No line ends in punctuation: the
# widest row ends on the dimension's vertical leader, and a trailing ';'
# touched it (machinist review r2).
SHAFT_DIA_CALLOUT = "SLIDING FIT IN MHA-CH-07 BORES\n1/4 GROUND STOCK OK"
# AcrossFlat's .XXX is the set screw's seat height: it sets both the >= 1.5D
# engagement and the proud limit (a .XX band breaks both).
ACROSS_FLAT_CALLOUT = "SETS MHA-CH-VN-55\nENGAGEMENT"
# rule 7: the one part-specific fact the views cannot carry.
DRAWING_NOTES = "CENTRE MARKS .04 DEEP MAX."
# The isometric renders at ISO_SCALE (1, 1) while the sheet/title block reads
# 2:1, so without this the pictorial is silently half scale.
ISO_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:1"
