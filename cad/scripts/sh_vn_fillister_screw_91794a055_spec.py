r"""MHA-SH-VN-59: the purchased #0-80 x 1/4 slotted fillister, cut to fit.

PURE DATA, no SolidWorks/COM imports. McMaster-Carr 91794A055 (18-8
stainless, slotted fillister head, fully threaded; ``_mcmaster_91794a055``),
three screws joining the MHA-PD-17 hub flange to the MHA-PD-06 disc, each tip
cut to fit at MHA-PD-00 (``pd_transgear_disc_screw_spec``). Retained under
its frozen MHA-SH-VN-59 identity after the four MHA-PD-26 rack screws moved
to 1/2 in 91794A060 (MHA-PD-VN-72, owner ruling 2026-11-26, #3738).

Frame (the fillister family's): axis +Y, head up, the under-head bearing face
at y = 0 (Top Plane); ``ScrewAxis`` is Front Plane x Right Plane.
"""

from __future__ import annotations

import _config
from _package_units import drawing_unit

PART_STEM = "sh-vn-fillister-screw-91794a055"
UNIT = drawing_unit(
    f"parts/{PART_STEM}", _config.parts("sh-vn-fillister-screw-91794a055")
)
CONFIGURATION = "Default"
