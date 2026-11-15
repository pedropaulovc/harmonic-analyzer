r"""MHA-SH-VN-59: the purchased #0-80 x 1/4 slotted fillister in two modelled forms.

PURE DATA, no SolidWorks/COM imports. One McMaster-Carr 91794A055 SKU (18-8
stainless, slotted fillister head, fully threaded; ``_mcmaster_91794a055``)
in two installed members of ``pd-paper-drive``: ``DiscScrew`` (x3) joins the
MHA-PD-17 hub flange to the MHA-PD-06 disc, each tip cut to fit at MHA-PD-00
(``pd_transgear_disc_screw_spec``), and ``RackScrew`` (x4) screws the
MHA-PD-26 strip to the MHA-PD-27 rail at stock length
(``pd_feed_rack_screw_spec``). A SKU whose members take more than one
modelled form is Shared (``cad/docs/subsystem-identities.md``); the disc
screws were MHA-PD-VN-55 until 2026-11-14 (#2410).

Frame (the fillister family's, both members): axis +Y, head up, the
under-head bearing face at y = 0 (Top Plane); ``ScrewAxis`` is Front Plane x
Right Plane.

The purchase drawing shows ``RackScrew``, the screw as supplied, so every
catalogue reference prints on it, the 1/4 stock length included; the disc
screws' cut is MHA-PD-00's step.
"""

from __future__ import annotations

import _config
from _package_units import drawing_unit

PART_STEM = "sh-vn-fillister-screw-91794a055"
UNIT = drawing_unit(
    f"parts/{PART_STEM}", _config.parts("sh-vn-fillister-screw-91794a055")
)

DISC_SCREW_CONFIGURATION = "DiscScrew"
RACK_SCREW_CONFIGURATION = "RackScrew"
# The registry order: default member first.
CONFIGURATIONS = (DISC_SCREW_CONFIGURATION, RACK_SCREW_CONFIGURATION)
# The member the purchase drawing's views show: the screw as supplied.
DRAWING_CONFIGURATION = RACK_SCREW_CONFIGURATION
