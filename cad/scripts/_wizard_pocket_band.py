"""The band a Hole Wizard counterbore or countersink takes with no band of its own.

Rule 3 (cad/docs/drawing-guidelines.md, "Decimal places carry the tolerance"),
verbatim: "Counterbore and countersink diameters and depths in a Hole Wizard
callout print in its standard three-place form; they are clearance pockets
toleranced by the `.XX` grade, not over-specification." and "On inch sheets,
three places mean `.XXX ±.005`, two mean `.XX ±.01`".

So a wizard pocket's Ø or depth that prints ``.115`` is ±.01, not ±.005: a guard
on it reads this band unless the callout prints the dimension's own band ("A
dimension that carries its own band is toleranced by that band"), and then the
guard reads that band, which the part puts on the Hole Wizard feature so the
callout displays it. Reading the three printed places as ``.XXX`` asserted the
pockets of MHA-PD-02 and MHA-PD-27 at ±.005 while their sheets allowed ±.01
(#3619, #3620; the index plate's #3497 first).

The rule is an inch-sheet rule, so the row is the title block's inch ``.XX``
(``unit="in"``; the default millimetre row is ±0.51 mm). One constant in its
own module: a spec that guards a wizard pocket imports it, and only those
specs' leaves re-key when it moves (in ``_printed_tolerance`` or
``_hole_spec`` it would re-key 428 of 639 leaves).

Pure data; no SolidWorks.
"""

from __future__ import annotations

from _printed_tolerance import printed_band_mm

WIZARD_POCKET_BAND_MM = printed_band_mm(2, unit="in")
