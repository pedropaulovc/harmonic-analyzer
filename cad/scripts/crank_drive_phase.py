"""Frozen actual-stock crank phase qualification for the coefficient budget.

No current-source whole-period and 21-stall qualification is published.
The interrupted source-captured candidate search refused its numerical
surface enclosure; it did not prove physical infeasibility. Historical
phase-zero measurements from other engine versions are not rebound here.
A refusal has no phase observations and must never be interpreted as zero TE.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

QUALIFIED = False
REFUSAL = (
    "Current finite stock16/ref14 + normal64/ref55 has no complete "
    "source-captured all-corner whole-pitch qualification, common physical "
    "clock or 21-stall phase certificate. The interrupted nominal C+0.4 "
    "phase-zero study exhausted its surface enclosure; that algorithm "
    "refusal is not a proved interference or shop-infeasibility result."
)
# Absence is explicit. Readers must check QUALIFIED before accessing data;
# neither None nor an empty tuple represents a measured zero or a fallback.
CONE_SHAFT_SENSE = None
STALL_DRIVER_RAD: tuple[float, ...] = ()
CONE_SHAFT_LAG_RAD: tuple[float, ...] = ()
BOUND_RAD: tuple[float, ...] = ()
GEOMETRY_SHA256 = None


def geometry_sha256() -> str:
    """Bind actual profiles/corners/physical grades and implementing geometry.

    Imports remain pure geometry/config. In particular neither a diagnostic
    solver nor native authoring code is imported into this budget reader.
    """
    import crank_mesh_geometry as geometry

    def profile(p):
        return (p.teeth,p.template.reference_teeth,p.template.diametral_pitch,
                p.template.pressure_angle_deg,p.blank_radius_mm,
                p.radial_translation_mm,p.helix_angle_deg)

    values = geometry.qualification_inputs()
    values["profiles"] = [profile(spec.STOCK_PROFILE) for spec in (geometry.pinion,geometry.gear64)]
    values["manufactured_corners"] = [
        [(label,profile(p)) for label,p in spec.STOCK_PROFILE_CORNERS]
        for spec in (geometry.pinion,geometry.gear64)
    ]
    values["physical_case_placements"] = geometry.calibration_case_placements()
    values["physical_case_domains"] = geometry.calibration_case_domains()
    root = Path(__file__).resolve().parent
    values["geometry_source_sha256"] = {
        name:hashlib.sha256((root/name).read_bytes()).hexdigest()
        for name in ("stock_form_cutter.py","crank_mesh_geometry.py")
    }
    return hashlib.sha256(json.dumps(values,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()
