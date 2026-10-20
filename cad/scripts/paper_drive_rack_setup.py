"""The paper-drive feed-rack datum setup and its closed-form gates.

The builder refuses a model whose rack pitch line, mesh or engaged-feed window
leaves these bands, and MHA-PD-00 prints the same bands
(``pd_paper_drive_assembly_steps``). Owned here, not by the steps module, so
the assembly's recipe carries the setup it gates on and never the sheet text.
The frozen finite-rack reader requires the exact source-derived measured-datum
physical stack. Its configured operating-domain wrapper additionally guards
the actual cut ends and the entire located, graded recording-paper sweep;
no hardware stop or reduced paper stroke is implied. No SolidWorks imports.
"""

from __future__ import annotations

import math

import paper_drive_geom as paper_geometry
import paper_drive_mesh_check as mesh_check
import paper_drive_rack_travel as rack_travel
import pd_transgear_feed_pinion_spec as feed_pinion
import transgear_hanger_joints as joints

# The feed owner's range is a tooth-centred rack-normal DATUM setup. The
# platen's endpoint-to-endpoint shake equals this band only with a feed tooth
# bisector directly below a rack-space bisector.
RACK_DATUM_BACKLASH_RANGE = feed_pinion.RACK_BACKLASH_RANGE
# The model's pitch-line distance at the nominal translation, across the
# datum band (pd_transgear_feed_pinion_spec's backlash law).
RACK_DATUM_MODEL_AXIS_DISTANCE_RANGE = tuple(
    mesh_check.feed_rack_axis_distance_mm(backlash, feed_pinion.RADIAL_SETTING)
    for backlash in RACK_DATUM_BACKLASH_RANGE
)

# Codex P1 on b2eb9a0e1: the hook's Ø3.3 pin hole is match-drilled from the
# MHA-PD-VN-58 pin with the largest pin on its lower edge
# ("hook-pin-hole-match-drilled"), so the unclamped arm cannot fall through
# the hole. With no slack the latch adds no opening to the rack mesh's loose
# datum end.
LATCH_SLACK_ALONG = 0.0


def require_feed_rack_datum_axis_distance(
    axis_distance_mm: float,
    datum_backlash_band: tuple[float, float] = RACK_DATUM_BACKLASH_RANGE,
) -> None:
    """The model's pitch-line distance must give a datum backlash in band."""
    low, high = datum_backlash_band
    specified_low, specified_high = RACK_DATUM_BACKLASH_RANGE
    if not specified_low <= low <= high <= specified_high:
        raise ValueError("rack datum setup band leaves its specified limits")
    near = mesh_check.feed_rack_axis_distance_mm(low, feed_pinion.RADIAL_SETTING)
    far = mesh_check.feed_rack_axis_distance_mm(high, feed_pinion.RADIAL_SETTING)
    # 1e-6 mm absorbs the native model's length round trip only.
    if not near - 1e-6 <= axis_distance_mm <= far + 1e-6:
        raise ValueError(
            f"rack pitch line {axis_distance_mm:.6f} mm from the feed axis is "
            f"outside the datum band {near:.6f}..{far:.6f} mm"
        )


def require_feed_rack_mesh(
    datum_backlash_band: tuple[float, float] = RACK_DATUM_BACKLASH_RANGE,
    latch_slack_along: float = LATCH_SLACK_ALONG,
) -> mesh_check.MeshCheck:
    """Closed-form gates for the set rack mesh over the printed corners.

    The latch pin's drop with ``latch_slack_along`` of travel left opens the
    loose end of the datum band.
    """
    low, high = datum_backlash_band
    specified_low, specified_high = RACK_DATUM_BACKLASH_RANGE
    if not specified_low <= low <= high <= specified_high:
        raise ValueError("rack datum setup band leaves its specified limits")
    if not math.isfinite(latch_slack_along) or latch_slack_along < 0.0:
        raise ValueError("latch opening must be finite and nonnegative")
    return mesh_check.feed_rack_mesh(
        datum_backlash_band, joints.latch_pinion_drop(latch_slack_along)
    ).require()


def feed_rack_operating_domain() -> rack_travel.RackOperatingDomain:
    """The engaged-feed window, checked against the located paper sweep."""
    domain = rack_travel.rack_operating_domain_mm(
        contact_half_width_mm=mesh_check.feed_rack_contact_half_width_mm(
            RACK_DATUM_BACKLASH_RANGE
        ),
        lateral_deviation_mm=paper_geometry.feed_lateral_deviation_mm(),
        profilecentre_x_offset_band_mm=(
            paper_geometry.feed_profilecentre_x_offset_band_mm()
        ),
        cut_end_section_maxima_mm=(
            paper_geometry.feed_rack_cut_end_section_maxima_mm()
        ),
    )
    domain.require_recording_paper_sweep_mm(
        **paper_geometry.recording_paper_sweep_bands_mm()
    )
    return domain
