"""Every fit band a build script hands to SolidWorks is valid at import time.

A band only reaches ``_fit_deviations.deviations`` (or the bilateral setter) inside
``build()``, which needs a SolidWorks seat. So an inverted or zero-width band
used to pass the whole offline suite and fail its farm leaf instead: warm-c486
lost ``part:dt_crank_drive_gear`` to "fit band is inverted: (0.025, 0.025)" at
``build_crank_drive_gear.build()`` -> ``deviations(BORE_DIA_BAND)``.

This file finds every band consumer by reading the scripts' source, resolves each
argument in the imported module (the value ``build()`` would see), and applies
the same checks ``build()`` would:

* ``deviations(band)`` and ``_printed_limits.limits(model, places, band)``
  take ``(upper, lower)``; the helper must accept it and return lower < upper.
* ``set_dimension_bilateral_tolerance(..., *BAND)`` splats ``(lower, upper)``
  straight into the setter, which refuses lower >= upper.

A second test inventories every module-level ``*_BAND`` / ``*_BANDS`` /
``*_BAND_MM`` tuple in the ``build_*``, ``*_spec``, ``*_geometry`` and ``*_geom``
modules. Each must be fed to a checked consumer, be listed in
``INDEXED_FIT_BANDS`` (a fit band read by index, checked the same way), or be
listed in ``NOT_FIT_BANDS`` with the reason it is not a fit.

Isolated AST-source controls also exercise both scanners and their source
anchors against empty discovery and one-directory-deep source moves.
"""

from __future__ import annotations

import ast
import importlib
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

import _fit_close_running
import _fit_deviations
import _gear_fit_limits

SCRIPTS = Path(__file__).resolve().parent

# Helpers that take an (upper, lower) band, and the positional index of the band.
_BAND_HELPERS = {"deviations": 0, "limits": 2}
_SETTER = "set_dimension_bilateral_tolerance"

# A consumer whose argument is a name local to build() (so it cannot be read off
# the imported module) must say here which module-level expression build()
# derives it from. "each" checks a tuple of bands; "values" checks a band mapping.
LOCAL_BAND_SOURCES: dict[tuple[str, str], tuple[str, str]] = {
    # for name, band in ((keyseat S,),): ... deviations(band); the keyseat
    # width and the turned diameters are REF (fit batch DT, 2026-11-24)
    ("build_dt_cone_gear_shaft", "band"): (
        "(cone_land_key.KEYSEAT_S_BAND,)",
        "each",
    ),
    # def gear_tip_band_mm(grade): band = ...; deviations(band)
    ("_gear_fit_limits", "band"): (
        "(gear_tip_band_mm('standard'), gear_tip_band_mm('contact_critical'))",
        "each",
    ),
    # drilled_limits derives its native band from the title-block drilled row.
    (
        "_printed_limits",
        "(drilled_oversize_mm(unit=unit), -drilled_undersize_mm(unit=unit))",
    ): (
        "((drilled_oversize_mm(unit='mm'), -drilled_undersize_mm(unit='mm')),"
        " (drilled_oversize_mm(unit='in'), -drilled_undersize_mm(unit='in')))",
        "each",
    ),
    # for (feature, name), band in spec.MODEL_BANDS_MM.items(): deviations(band)
    ("build_dt_cone_gear_tl_keyed_arbor", "band"): ("spec.MODEL_BANDS_MM", "values"),
    ("build_dt_cylinder_gear_tl_cam_fixture", "deviations"): ("MODEL_BANDS_MM", "values"),
    # _far_station passes its caller's band: only the collar rear station has one.
    ("draw_dt_crankshaft", "band"): (
        "((COLLAR_STATION_TOL, -COLLAR_STATION_TOL),)",
        "each",
    ),
    # _single_limits passes each single-limit band (MIN chamfer, MAX rounds).
    ("build_pn_pen_v_block", "limit_band"): (
        "tuple(limit[3] for limit in _SINGLE_LIMITS)",
        "each",
    ),
    # set_single_limit converts each caller's single-limit band.
    ("_single_limit_tolerance", "band"): (
        "(__import__('pn_pen_hanger_spec').SLOT_CORNER_R_BAND,"
        " __import__('dt_pinion_cam_spec').THIN_WALL_MIN_BAND,"
        " __import__('pn_pen_rod_spec').TAP_WALL_MIN_BAND,"
        " __import__('dt_crank_handle_pivot_screw_spec').TIP_CHAMFER_BAND,"
        " __import__('pd_transgear_arm_spec').PIN_HOLE_DEPTH_BAND,"
        " __import__('fr_top_frame_spec').HANGER_PIN_HOLE_DEPTH_BAND,"
        " __import__('ch_fulcrum_keeper_spec').CORNER_R_BAND)",
        "each",
    ),
    # for configuration, teeth in CONFIGS: band = band_for(teeth); deviations(band)
    ("build_dt_cone_gear", "band"): (
        "tuple(band_for(teeth) for _feature, _name, band_for in _BANDED_DIMENSIONS"
        " for teeth in __import__('dt_cone_gear_spec').CONFIGURATION_TEETH)",
        "each",
    ),
    # for name, band in (("BlankDia", blank_dia_band(teeth)), ...): deviations(band)
    ("draw_dt_cone_gear", "band"): (
        "tuple(band_for(teeth) for band_for in (blank_dia_band, tooth_thickness_band)"
        " for teeth in __import__('dt_cone_gear_spec').CONFIGURATION_TEETH)",
        "each",
    ),
    # The cone tip gear's loop over its own module-level bands.
    ("build_dt_cone_tip_gear", "band"): (
        "(BLANK_DIA_BAND, FACE_WIDTH_BAND, TOOTH_THICKNESS_BAND, SPIGOT_DIA_BAND)",
        "each",
    ),
    # _apply_neck_and_flat_limits passes its one native LIMIT band.
    ("build_pd_transgear_knob_shaft", "band"): ("(FRONT_RELIEF_DIA_BAND,)", "each"),
    # for feature, name, band_for in _BANDED_DIMENSIONS: band = band_for(teeth), every configuration
    ("_cone_gear_readback", "band"): (
        "tuple(band_for(teeth) for _feature, _name, band_for in _BANDED_DIMENSIONS"
        " for teeth in __import__('dt_cone_gear_spec').CONFIGURATION_TEETH)",
        "each",
    ),
}

# Consumer modules that cannot be imported without SolidWorks, with the reason.
# Empty today: every band consumer imports offline.
OFFLINE_IMPORT_EXCLUSIONS: dict[str, str] = {}

# Module-level *_BAND tuples that are not fit bands, so no checked consumer
# reads them. A new band tuple must be fed to a consumer above or listed here.
NOT_FIT_BANDS: dict[tuple[str, str], str] = {
    ("dt_pinion_cam_pin_spec", "SEAT_BAND"): (
        "restatement of dt_pinion_bracket_spec.PIN_SEAT_DIA_BAND (checked there) "
        "for the MHA-DT-25 bond-gap arithmetic; the cam-pin drawing test pins them equal"
    ),
    ("build_dt_drive_train_assembly", "ARBOR_PED_SOUTH_Z_BAND"): (
        "plan z extent of the south pedestal foot (clearance geometry)"
    ),
    ("build_dt_drive_train_assembly", "ARBOR_PED_NORTH_Z_BAND"): (
        "plan z extent of the north pedestal foot (clearance geometry)"
    ),
    ("dt_crank_pin_spec", "BIG_END_DIA_BAND"): (
        "ASME B18.8.2 catalogue tolerance of the bought No. 3 pin's big end (#2368); it bounds the "
        "cross-hole web and the keeper ring's air, while the taper fit is reamed to suit the pin"
    ),
    ("dt_crank_pin_ring_spec", "BUTT_GAP_BAND"): (
        "pliers-closed butt gap between the keeper ring's own wire ends (note: GAP 0-.010); "
        "no mating part"
    ),
    # The 16T/T120 and row checks (c'' variant B): print-worst (lower, upper)
    # deviations already derived by printed_deviations/deviations from each
    # printed band, corners of the clearance scans rather than fits.
    ("build_dt_drive_train_assembly", "_PINION_FACE_BAND"): (
        "16T face print-worst deviations (clearance/engagement corners)"
    ),
    ("build_dt_drive_train_assembly", "_PINION_SHOULDER_BAND"): (
        "16T shoulder print-worst deviations (T120 air corners)"
    ),
    ("build_dt_drive_train_assembly", "_PINION_TIP_RADIUS_BAND"): (
        "16T tip-radius print-worst deviations (T120 air corners)"
    ),
    ("build_dt_drive_train_assembly", "_PINION_TURNED_DIA_BAND"): (
        "16T turned-band diameter print-worst deviations (T120 radial and band contact corners)"
    ),
    ("build_dt_drive_train_assembly", "_BOSS_NORTH_BAND"): (
        "post crank-boss north face print-worst deviations (16T station corners)"
    ),
    ("build_dt_drive_train_assembly", "_CONE_BOSS_NORTH_BAND"): (
        "post cone-boss north face print-worst deviations (cone stack corners)"
    ),
    ("build_dt_drive_train_assembly", "_COLLAR_WIDTH_BAND"): (
        "cone-shaft collar print-worst deviations (cone stack corners)"
    ),
    ("build_dt_drive_train_assembly", "_CRANK_HEIGHT_BAND"): (
        "crank-above-cone print-worst deviations (radial clearance corners)"
    ),
    ("build_dt_drive_train_assembly", "_T120_NORTH_BAND"): (
        "T120 north-face (upper, lower) station band sampled by the T120 scan"
    ),
    ("build_dt_drive_train_assembly", "_ARB_Z_BANDS"): (
        "(z extent, minimum gap) pairs for the swing-plate clearance sweep"
    ),
    ("build_dt_drive_train_assembly", "_SWING_RIG_BANDS"): (
        "(z low, z high, name) pinion-rig extents for the engage-swing sweep"
    ),
    ("build_dt_drive_train_assembly", "_SPRING_Z_BAND"): (
        "plan z extent of the return spring for the engage-swing sweep"
    ),
    ("build_dt_drive_train_assembly", "CRANK_COLUMN_BANDS"): (
        "(z front, z rear, diameter, name) crank-seat column extents for the "
        "radial clearance sweep"
    ),
    ("dt_pinion_spring_geometry", "FORMED_CONTACT_BANDS"): (
        "names of the formed dimensions the contact corners perturb, not a band"
    ),
    ("pd_transgear_disc_screw_spec", "STOCK_LENGTH_BAND"): (
        "the fillister screw's B18.6.3 length tolerance (plus, minus): indexed "
        "for the stock's reach past the disc's rear face before its cut"
    ),
    ("pd_rack_pinion_spec", "_SPAN_DESIGN_SETTING_BAND"): (
        "the cutter radial-setting design band the printed span limits are solved from"
    ),
    ("pd_rack_pinion_spec", "RADIAL_SETTING_BAND"): (
        "the cutter radial setting implied by the printed span limits (a machine setting)"
    ),
    ("pd_transgear_feed_pinion_spec", "_SPAN_DESIGN_SETTING_BAND"): (
        "the cutter radial-setting design band the printed span limits are solved from"
    ),
    ("pd_transgear_knob_shaft_spec", "_SPAN_DESIGN_SETTING_BAND"): (
        "the cutter radial-setting design band the printed span limits are solved from"
    ),
    ("pd_transgear_knob_shaft_spec", "RADIAL_SETTING_BAND"): (
        "the cutter radial setting implied by the printed span limits (a machine setting)"
    ),
    ("pd_vn_guide_lock_screw_spec", "SHANK_LEN_BAND"): (
        "the pan-head screw's B18.6.3 length tolerance (plus, minus): "
        "indexed for the shortest reach into the platen guide's through tap"
    ),
    # MHA-PD-00's setting details (rule 22): absolute (low, high) windows in
    # mm of an assembly setting dimension, not (upper, lower) part-fit
    # deviations; the spec's import-time loop proves each on the .001 grid
    # with its nominal strictly inside.
    ("pd_paper_drive_setting_details_spec", "DRIVE_PIN_PROUD_BAND"): (
        "DETAIL F's printed limits for the collar dowels' proud (an assembly setting)"
    ),
    ("pd_paper_drive_setting_details_spec", "LATCH_PROUD_BAND"): (
        "DETAIL L's printed limits for the latch dowel's proud (an assembly setting)"
    ),
    ("pd_paper_drive_setting_details_spec", "RACK_CREST_BAND"): (
        "DETAIL J's printed window for the rack crests below the platen (an assembly setting)"
    ),
    ("pd_paper_drive_setting_details_spec", "RACK_FRONT_BAND"): (
        "DETAIL J's printed window for the rack front behind the guide (an assembly setting)"
    ),
    ("dt_vn_cylinder_bank_spring_spec", "ID_BAND"): (
        "McMaster 9714K392's catalogue ID tolerance (plus, minus): indexed for "
        "the tightest spring against the largest arbor"
    ),
    ("dt_vn_cylinder_bank_spring_spec", "OD_BAND"): (
        "McMaster 9714K392's catalogue OD tolerance (plus, minus): indexed for "
        "its seat on the washer and strap faces"
    ),
    ("mg_magnifying_vertical_rod_geom", "ROD_DIA_BAND"): (
        "as-bought 1/4 brass rod's supplier tolerance (upper, lower): indexed "
        "for the fixture cross-bore clearance and the turned relief"
    ),
}

# (upper, lower) fit bands that no helper reads: the owning module indexes them
# to print or derive limits. An inverted one prints wrong limits, so they get
# the same check as a helper-fed band.
INDEXED_FIT_BANDS: dict[tuple[str, str], str] = {
    # Fit audit 2026-11-23: MHA-PD-08's core and D-flat are made to fit
    # MHA-PD-22 by feel and print as REF with no band; these are the ANALYSIS
    # bands the collar's stacks index (the drilled bore's DRILLED HOLES row
    # less the fitted air), tied to each other by the collar spec's asserts.
    ("pd_transgear_drive_collar_spec", "BORE_DIA_BAND"): (
        "DRILLED HOLES row of the #11 bore, indexed for the walls and the core's analysis band"
    ),
    ("pd_transgear_knob_shaft_spec", "CORE_DIA_BAND"): (
        "analysis band of the core turned to fit the drilled bore, indexed for the stacks"
    ),
    ("pd_transgear_knob_shaft_spec", "CORE_FLAT_BAND"): (
        "analysis band of the D-flat milled to fit the pressed pin's crest, indexed for the stacks"
    ),
    # #2144 item 11.4: McMaster 91829A566 catalogue bands, indexed
    # into MIN/MAX limits that sm_gooseneck_spring_joint charges; the sheets
    # print them as untoleranced REF.
    ("sm_vn_gooseneck_shoulder_screw_spec", "SHOULDER_DIA_BAND"): (
        "catalogue shoulder band, indexed for the eye clearance and head retention"
    ),
    ("sm_vn_gooseneck_shoulder_screw_spec", "SHOULDER_LENGTH_BAND"): (
        "catalogue shoulder-length band, indexed for the eye's axial play"
    ),
    ("mg_wheel_axle_spec", "THREAD_LEN_BAND"): (
        "equal band indexed into the native symmetric (+/-) tolerance"
    ),
    # Owner ruling 2026-11-24, fit audit question 17: an analysis band, not a
    # printed limit.
    ("mg_wheel_drum_geom", "DRUM_BORE_BAND"): (
        "title-block drilled-hole deviations (the 1/2 DRILL THRU callout's row, "
        "no native band); indexed for the drum's worst wall and the spigot's "
        "least size under the bond clearance (SPIGOT_DIA_MIN)"
    ),
    # Owner ruling 2026-11-24, fit audit question 18: likewise.
    ("mg_wheel_bar_geom", "AXLE_BORE_BAND"): (
        "title-block drilled-hole deviations (the 3/16 DRILL THRU callout's row, "
        "no native band); indexed for the bar's row walls and the axle's bond "
        "gap (mg_wheel_group.BAR_BOND_GAP)"
    ),
    # Owner ruling 2026-11-24, fit audit question 20: an analysis band, not a
    # printed limit.
    ("pn_pen_v_block_spec", "PIVOT_BORE_BAND"): (
        "title-block drilled-hole deviations (the #30 DRILL THRU callout's row, "
        "no native band); indexed for the step clearance, the neck break's wall "
        "and the set screw's reach to the pivot's groove"
    ),
    # Owner ruling 2026-11-24, fit audit OQ19 (A): MHA-SM-02 datum B is a #30
    # drill; its band is an analysis band, not a printed limit.
    ("sm_vn_knife_mount_dowel_spec", "SLIP_HOLE_DIA_BAND"): (
        "title-block drilled-hole deviations (the #30 DRILL callout's row, no "
        "native band); indexed for the dowel's slip, the tilt allowance and "
        "the knife-hanger bolt float"
    ),
    ("sm_knife_mount_spec", "PIN_HOLE_DIA_BAND"): (
        "the dowel spec's #30 drilled-hole deviations, re-exported; indexed "
        "for the block's webs round datum B"
    ),
    ("pd_transgear_feed_pinion_spec", "FLAT_TO_AXIS_BAND"): (
        "equal band indexed into the native symmetric (+/-) tolerance and the "
        "hub key pin's air to the flat"
    ),
    ("dt_crank_drive_gear_spec", "BORE_DIA_BAND"): (
        "the .3760 reamer's analysis band, never printed (fit audit 2026-11-23, "
        "MHA-DT-07.bore): indexed for the modelled reamer size and the keyed "
        "arbor's and collar-annulus walls"
    ),
    ("dt_alignment_pinion_spec", "BASE_TANGENT_SPAN_BAND"): (
        "indexed into the span-measurement note text"
    ),
    ("dt_cone_gear_shaft_spec", "STOCK_DIA_BAND"): (
        "the 5/8 bar's supplied size band, indexed for the thrust ring's "
        "worst-case width (THRUST_RING_MIN)"
    ),
    ("dt_cone_gear_shaft_spec", "_T030_NORTH_BAND"): (
        "the cone gear stack's T030 north-face station band (an axial stack "
        "position, not a fit), indexed into T024_NORTH_FACE_DEVIATION_MM"
    ),
    # Fit batch DT, 2026-11-24 (rule 4 forms 2/3): the bores print the
    # reamer's size with no band and the mates are made last to them; these
    # stay the analysis bands the stacks index.
    ("dt_cone_gear_spec", "BORE_DIA_BAND"): (
        "the keyed bores' reamed spread over the Ø.3750 nominal, indexed for "
        "the seat clearance (GEAR_SEAT_CLEARANCE) and cone_set_stack's float"
    ),
    ("dt_cone_gear_spec", "LAND_SEAT_BORE_BAND"): (
        "the reamed land-seat bores' spread above the reamer's size, indexed "
        "for the seat and bond clearances; the sheet prints no band"
    ),
    # Machinist review r1 (farm run 20261124T110807008Z): the 1/16 key's
    # widths print REF, the key is the gauge (rule 4, form 3).
    ("dt_crank_drive_gear_spec", "KEYWAY_WIDTH_BAND"): (
        "the 1/16 A broach's analysis band (cone_land_key.KEYWAY_WIDTH_BAND; the "
        "width prints REF), indexed for the keyway walls and side clearance"
    ),
    ("dt_cone_gear_tl_keyed_arbor_spec", "KEYSEAT_WIDTH_BAND"): (
        "the 1/16 end mill's analysis band (cone_land_key.KEYSEAT_WIDTH_BAND; the "
        "width prints REF, the key bonded), indexed for the keyseat's corner reach"
    ),
    ("pn_pen_hanger_spec", "STRAP_T_STOCK_BAND"): (
        "the 3 mm strap stock's supplied thickness band, indexed for the "
        "slot-bottom gap (SLOT_BOTTOM_GAP_MIN) and the arm cover "
        "(GUIDE_ARM_COVER_MIN); the sheet prints the thickness as a reference"
    ),
    ("dt_cylinder_end_disc_spec", "WASHER_BORE_BAND"): (
        "title-block drilled-hole deviations; upper limit indexed by "
        "installed_clearance_budget for free-bore tilt and drive clearance"
    ),
    ("dt_vn_cone_pivot_screw_spec", "SHOULDER_DIA_BAND"): (
        "McMaster 91829A560 supplied shoulder diameter +0/-0.0254 mm; "
        "upper/lower deviations used by the platform's stock pivot fit"
    ),
    ("dt_vn_cone_pivot_screw_spec", "SHOULDER_LEN_BAND"): (
        "McMaster 91829A560 supplied shoulder length +0.0508/0 mm; "
        "upper/lower deviations used by the platform's stock axial stack"
    ),
    ("dt_vn_cone_shaft_key_spec", "SIZE_BAND"): (
        "McMaster 98830A511 supplied undersized key-stock section +0/-0.0508 mm, "
        "printed as supplier REF; cone_land_key's keyseat/keyway clearance proofs "
        "read the same band as KEY_STOCK_BAND"
    ),
    ("dt_cone_gear_tl_arbor_key_spec", "SIZE_BAND"): (
        "1/16 undersized key-stock section +0/-0.0508 mm as supplied, printed as "
        "stock REF; cone_land_key's keyseat/keyway clearance proofs read the same "
        "band as KEY_STOCK_BAND"
    ),
    ("dt_crankshaft_spec", "SEAT_COLLAR_BAND"): (
        "the seat face's station deviations, indexed for the hub-to-sprocket air"
    ),
    # Codjiflo 3548-2: the three note-3 fits print REF and export dia_ref with
    # the clearance; their turning aims stay as analysis bands only.
    ("dt_crankshaft_spec", "JOURNAL_DIA_BAND"): (
        "analysis aim of the REF journals turned to MHA-DT-05's measured bores; "
        "dt_crankshaft_notes.FIT_CLEARANCES derives note 3's .0010-.0023 from it"
    ),
    ("dt_crankshaft_spec", "PINION_SEAT_DIA_BAND"): (
        "analysis aim of the REF pinion seat turned to MHA-DT-10's measured bore; "
        "dt_crankshaft_notes.FIT_CLEARANCES derives note 3's .0010-.0023 from it"
    ),
    # D27 below: delegated ruling 2026-11-25 (Main), precedent: the
    # fit-necessity rule of the owner-approved fit policy (owner ruling
    # 2026-11-24); owner review #2144.
    ("dt_crank_hub_geometry", "SHAFT_DIA_BAND"): (
        "analysis aim of MHA-DT-11's REF stub turned to MHA-DT-31's measured bore "
        "(the 3/8 drill's, D27) less SHAFT_CLEARANCE, note 3's clearance"
    ),
    ("dt_crank_hub_geometry", "HUB_BORE_BAND"): (
        "the 3/8 drilled hub bore's ANALYSIS band, the title block's "
        "drilled-hole row (no native band; D27): indexed for the seam web, "
        "the relief wall and the hub's float on the stub"
    ),
    ("dt_crank_handle_butt_cup_spec", "POCKET_DIA_BAND"): (
        "the pocket's own .248-.257 as deviations on the modelled .250; the sheet "
        "and export carry dia_ref and dia_max (POCKET_DIA_LIMITS), fit audit Q15"
    ),
    ("_sprocket_seat_geometry", "PLATE_BAND"): (
        "the wheel plate's thickness deviations, indexed for the hub-to-sprocket "
        "air and the chain envelope's reach"
    ),
    ("ch_connecting_rod_spec", "RING_THICKNESS_BAND"): (
        "the ring's .170 thickness, a size printed at the ring (#982 review "
        "r1; #3114), indexed by cylinder_bank_layout for the thickest ring "
        "its cam slot holds"
    ),
    ("ch_connecting_rod_spec", "SHANK_FACE_BAND"): (
        "the shank's near face from the fork's datum face at the title "
        "block's .XX (#3114), indexed by ch_connecting_rod_spec to keep each "
        "shank face inside its ring face"
    ),
    ("ch_connecting_rod_spec", "FORK_THICKNESS_BAND"): (
        "the fork over the tines, a reference: two TINE_BANDs and the "
        "FORK_SLOT_BAND, indexed by sh_vn_pivot_pin_rod_spec for the bought "
        "pin's dressing stock"
    ),
    ("dt_cylinder_gear_spec", "WHOLE_DEPTH_BAND"): (
        "indexed into the cylinder gear-data whole-depth limits"
    ),
    # Fit audit 2026-11-23 (drawing-guidelines rule 4): an analysis band, not
    # a printed limit.
    ("dt_cylinder_gear_spec", "BORE_DIA_BAND"): (
        "analysis band of the .3760 reamed bore, which prints the reamer's "
        "size and no band: indexed for the running clearance on MHA-DT-13, "
        "the cam wall, the cone tip's air and the cam fixture's stub float"
    ),
    ("ch_connecting_rod_spec", "SHANK_THICKNESS_BAND"): (
        "the shank's .13 thickness at the title block's .XX (#3114), "
        "indexed by ch_connecting_rod_spec to keep each shank face inside "
        "its ring face and by cylinder_bank_layout for the thickest shank"
    ),
    ("dt_cylinder_gear_spec", "OVERALL_THICKNESS_BAND"): (
        "centred (cylinder_bank_layout asserts it): indexed as the symmetric "
        "tolerance and the fit-up mic limits"
    ),
    ("dt_pinion_arbor_collar_spec", "BORE_BAND"): (
        "the title block's drilled-hole row, indexed for the slide-clearance, "
        "wall and pin-end-depth stacks (not printed on the bore)"
    ),
    ("dt_pinion_arbor_geometry", "DRUM_LEN_BAND"): "indexed into the drum-length limits",
    ("dt_pinion_arbor_geometry", "BOND_LAND_DIA_BAND"): (
        "the MHA-DT-01 bond lands' ANALYSIS band (no native band; the lands "
        "are turned to the 5/16 drilled drum bore, fit audit question 13), "
        "indexed for the bond gap's BOND_GAP_MAX"
    ),
    ("dt_pinion_arbor_geometry", "DRUM_BORE_BAND"): (
        "the 5/16 drilled MHA-DT-01 bore's ANALYSIS band, the title block's "
        "drilled-hole row, indexed for the bond gap and the relief air"
    ),
    ("dt_pinion_arbor_geometry", "CROSS_HOLE_DIA_BAND"): (
        "the .2510 reamed crossrod hole's ANALYSIS band (no native band; the "
        "MHA-DT-15 rod is its gauge, fit audit F14), indexed for the bond's "
        "CROSSROD_MIN/MAX_CLEARANCE and the head webs"
    ),
    ("dt_alignment_pinion_spec", "ARBOR_BORE_BAND"): (
        "the 5/16 drilled drum bore's ANALYSIS band, the title block's "
        "drilled-hole row (no native band; MHA-DT-22's bond lands are made to "
        "fit it, fit audit question 13)"
    ),
    ("dt_pinion_bracket_spec", "ARBOR_BORE_BAND"): (
        "the 5/16 drilled strap bore's ANALYSIS band, the title block's "
        "drilled-hole row (no native band; the MHA-DT-22 journals are made to "
        "fit it, fit audit question 12)"
    ),
    ("dt_pinion_pivot_block_spec", "LIFT_BORE_BAND"): (
        "the F drilled lift bore's ANALYSIS band, the title block's "
        "drilled-hole row (no native band; fit audit F26)"
    ),
    ("dt_arbor_pedestal_spec", "BORE_DIA_BAND"): (
        "the V drilled arbor bore's ANALYSIS band, the title block's "
        "drilled-hole row (no native band; fit audit F01): indexed for the "
        "set screw's thread, point margin and the arbor's float"
    ),
    ("dt_pinion_handle_geometry", "ROD_DIA_BAND"): (
        "indexed by pinion_arbor_spec for the cross-rod fit limits"
    ),
    ("dt_pinion_cam_pin_spec", "PIN_DIA_BAND"): (
        "the 5/32 drill rod's supplied +/-.0005 in (no native band; the size "
        "prints REF, AS SUPPLIED): indexed for the bonded slip fit's "
        "BOND_CLEARANCE_MIN/MAX and the traveler's rod check"
    ),
    ("dt_pinion_lever_pin_spec", "PIN_DIA_BAND"): (
        "the 1/16 drill rod's supplied +/-.0003 in (no native band; the size "
        "prints REF, AS SUPPLIED): indexed for the pin's clearance in the #51 "
        "match-drilled hole and the traveler's rod check"
    ),
    ("dt_cone_swing_platform_pivot_spec", "PIVOT_HOLE_BAND"): (
        "the .2510 reamed pivot bore's ANALYSIS band (no native band; fit "
        "audit question 10, necessity N-01): indexed into the float on the "
        "91829A560 shoulder, the cone set stack's transfer-punch and "
        "support-pose pivot float and the assembly's pivot air"
    ),
    ("ch_rocker_arm_spec", "PIVOT_HOLE_BAND"): (
        "title-block drilled-hole deviations (the F DRILL THRU row, no native "
        "band); indexed into the hub's wall floor (HUB_DIA_MIN) and wall note"
    ),
    ("pd_transgear_knob_cup_spec", "HOLE_BAND"): (
        "title-block drilled-hole deviations (the web's #33 DRILL THRU row, no "
        "native band); indexed for CLEAR_HOLE_MIN against MHA-PD-VN-71's "
        "under-head fillet envelope and CLEAR_HOLE_MAX for the head's bearing land"
    ),
    ("pd_transgear_knob_thrust_ring_spec", "ID_BAND"): (
        "title-block drilled-hole deviations (the DRILL THRU callout's row, no "
        "native band); upper limit indexed for the ring's worst wall and the "
        "knob shaft's rear tooth-end bearing (RING_TRANSVERSE_FLOAT_MAX)"
    ),
    ("pd_transgear_pivot_spacer_spec", "BORE_DIA_BAND"): (
        "title-block drilled-hole deviations (the #11 DRILL THRU callout's row, "
        "no native band); indexed for the bond gap on MHA-PD-VN-57's shoulder "
        "(BOND_GAP) and the ring's worst wall"
    ),
    ("pd_vn_transgear_latch_pin_spec", "DIA_BAND"): (
        "the pressed dowel's catalogue diameter: read by min/max for the press "
        "interference against the arm's blind hole"
    ),
    ("pd_rack_pinion_spec", "CENTRE_DISTANCE_SET_BAND"): (
        "the reducer's fine-pitch set band (+.002/-0 centre allowance): the "
        "window the mesh gates are read over and the DRO's mid-band aim for K "
        "(pd_paper_drive_knob_setting_spec); DETAIL K prints the trial band's "
        "limits, which paper_drive_arm_registration reads (owner ruling "
        "2026-11-24, audit part 2 question C1); no fit"
    ),
    ("pd_rack_pinion_spec", "CENTRE_DISTANCE_TRIAL_BAND"): (
        "MHA-PD-00 DETAIL K's S to N limits (+.002/-.001): the set band opened "
        "by the trial mesh's move toward S (owner ruling 2026-11-24, audit part "
        "2 question C1), read by paper_drive_arm_registration and the knob "
        "setting spec; no fit"
    ),
    ("sm_vn_knife_mount_dowel_spec", "DIA_BAND"): (
        "the pressed dowel's catalogue diameter: read by min/max for the press "
        "interference against the crossbar's blind ream and the slip clearance "
        "in the knife mount's round hole and slot"
    ),
    ("fr_top_frame_spec", "HANGER_CLEARANCE_DIA_BAND"): (
        "the title-block DRILLED HOLES +.004/0 float-hole diameter: indexed into "
        "its accepted minimum/maximum, without a redundant explicit callout band"
    ),
    ("sm_knife_mount_spec", "STUD_TAP_DIA_BAND"): (
        "the title-block DRILLED HOLES +0.10/0 tap-pilot diameter: indexed into "
        "accepted limits, without a redundant explicit callout band"
    ),
    ("pd_transgear_drive_collar_spec", "PILOT_DIA_BAND"): (
        "the title block's .XX row on the .39 pilot (no authored band): indexed "
        "for the wheel-bore air, the pilot wall and the thumbnut's seat"
    ),
    # Fit audit 2026-11-23 (drawing-guidelines rule 4): analysis bands, not
    # printed limits.
    ("pd_rack_pinion_spec", "BORE_BAND"): (
        "analysis band of the reamed Ø.501 bore, which prints the reamer's "
        "size and no band: indexed for the spigot clearance, the disc's float "
        "and the tap-to-bore web"
    ),
    ("pd_transgear_feed_pinion_spec", "BOSS_DIA_BAND"): (
        "analysis band of the boss, which prints REF and is turned to the "
        "MHA-PD-17 bore by feel: indexed for the hub's clearance, rock and "
        "the boss wall"
    ),
    ("pd_transgear_disc_hub_geometry", "SPIGOT_DIA_BAND"): (
        "analysis band of the spigot, which prints REF and is turned to the "
        "reamed MHA-PD-06 bore at the printed clearance: indexed for the "
        "spigot wall and the disc's float"
    ),
    ("pd_transgear_knob_cup_spec", "BORE_BAND"): (
        "analysis band of the pilot, which prints REF and is bored to the "
        "MHA-PD-08 journal at the printed clearance: indexed for the bond "
        "gap and the pilot wall"
    ),
    ("pd_transgear_knob_bush_geometry", "PRESS_DIA_BAND"): (
        "analysis band of the press diameter, which prints its interference "
        "to the measured MHA-PD-19 hole and no band: indexed for the plate "
        "stub's envelope and the press-to-bore wall"
    ),
}

KNOWN_BAD: dict[str, pytest.MarkDecorator] = {}


@dataclass(frozen=True)
class BandUse:
    module: str  # consumer module stem
    line: int
    expression: str  # the argument as written
    order: str  # "upper_lower" (helpers) or "lower_upper" (setter splat)


def _call_name(node: ast.Call) -> str | None:
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return None


def _identifier_spelling(text: str) -> str:
    """``text`` as the parser sees its identifiers, for substring prefilters.

    Python NFKC-normalizes identifiers, so ``WIDTH_\uff22AND`` names
    ``WIDTH_BAND``; search the normalized copy, parse the original."""
    return text if text.isascii() else unicodedata.normalize("NFKC", text)


def _band_uses() -> list[BandUse]:
    uses: list[BandUse] = []
    for path in sorted(SCRIPTS.glob("*.py")):
        if path.name.startswith("test_"):
            continue
        text = path.read_text(encoding="utf-8")
        # Every matched call spells one of these names in its source; parsing
        # only the files that do yields the same uses for a fraction of the cost.
        spelled = _identifier_spelling(text)
        if not any(name in spelled for name in (*_BAND_HELPERS, _SETTER)):
            continue
        tree = ast.parse(text, filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = _call_name(node)
            if name in _BAND_HELPERS:
                index = _BAND_HELPERS[name]
                if len(node.args) > index:
                    arg = node.args[index]
                    uses.append(
                        BandUse(path.stem, node.lineno, ast.unparse(arg), "upper_lower")
                    )
            elif name == _SETTER:
                # A splat that is not itself a helper call hands the setter a
                # raw (lower, upper) pair.
                for arg in node.args:
                    if isinstance(arg, ast.Starred) and not isinstance(
                        arg.value, ast.Call
                    ):
                        uses.append(
                            BandUse(
                                path.stem,
                                node.lineno,
                                ast.unparse(arg.value),
                                "lower_upper",
                            )
                        )
    return uses


BAND_USES = _band_uses()


def _import(module: str) -> Any:
    if module in OFFLINE_IMPORT_EXCLUSIONS:
        pytest.skip(f"{module}: {OFFLINE_IMPORT_EXCLUSIONS[module]}")
    return importlib.import_module(module)


def _resolve(use: BandUse) -> list[tuple[str, Any]]:
    """The value(s) build() passes, read from the imported consumer module."""
    module = _import(use.module)
    key = (use.module, use.expression)
    if key in LOCAL_BAND_SOURCES:
        source, how = LOCAL_BAND_SOURCES[key]
        value = eval(source, vars(module))  # noqa: S307 -- repo source
        if how == "values":
            return [(f"{source}[{places!r}]", band) for places, band in value.items()]
        assert how == "each", f"unknown local-source mode {how!r}"
        return [(f"{source}[{i}]", band) for i, band in enumerate(value)]
    try:
        value = eval(use.expression, vars(module))  # noqa: S307 -- repo source
    except NameError as error:
        raise AssertionError(
            f"{use.module}:{use.line}: band argument {use.expression!r} is not a "
            "module-level value, so this test cannot see what build() passes. Add "
            "it to LOCAL_BAND_SOURCES with the module-level value it derives from."
        ) from error
    return [(use.expression, value)]


@pytest.mark.parametrize(
    ("module_name", "expected"),
    [
        ("build_dt_cone_gear_tl_keyed_arbor", "spec.MODEL_BANDS_MM"),
    ],
)
def test_local_sources_cover_every_band(module_name: str, expected: str) -> None:
    module = _import(module_name)
    source = eval(expected, vars(module))  # noqa: S307 -- repo source
    bands = list(source.values()) if isinstance(source, dict) else list(source)
    resolved = _resolve(BandUse(module_name, 0, "band", "upper_lower"))
    assert [band for _, band in resolved] == bands
    assert all(any(band is actual for _, actual in resolved) for band in bands)

def _check_band(label: str, band: Any, order: str) -> None:
    assert isinstance(band, tuple) and len(band) == 2, f"{label}: not a 2-tuple: {band!r}"
    assert all(isinstance(v, (int, float)) for v in band), f"{label}: {band!r}"
    if order == "upper_lower":
        # Exactly what build() does; raises on an inverted or zero-width band.
        lower, upper = _fit_deviations.deviations(band)
    else:
        lower, upper = band
    assert lower < upper, f"{label}: lower {lower} >= upper {upper} ({order})"
    assert upper - lower > 0.0, f"{label}: zero-width band {band!r}"


def _case_ids() -> list[Any]:
    params = []
    seen: set[str] = set()
    for use in BAND_USES:
        case_id = f"{use.module}:{use.expression}"
        if case_id in seen:
            continue
        seen.add(case_id)
        marks = [KNOWN_BAD[case_id]] if case_id in KNOWN_BAD else []
        params.append(pytest.param(use, id=case_id, marks=marks))
    return params


def test_band_uses_are_found() -> None:
    # A scanner that silently finds nothing would pass every case below.
    helpers = [u for u in BAND_USES if u.order == "upper_lower"]
    assert len(helpers) >= 50, f"band consumer scan found only {len(helpers)} helper uses"
    ids = {f"{u.module}:{u.expression}" for u in BAND_USES}
    # The 64T's face width is the anchor since its reamed bore and then its
    # keyway width lost their bands (fit audit 2026-11-23, MHA-DT-07.bore;
    # machinist review r1, farm run 20261124T110807008Z).
    assert "build_dt_crank_drive_gear:GEAR_FACE_WIDTH_BAND" in ids, (
        "missing band consumer anchor: build_dt_crank_drive_gear:GEAR_FACE_WIDTH_BAND"
    )
    assert "build_dt_cone_gear_shaft:band" in ids, (
        "missing band consumer anchor: build_dt_cone_gear_shaft:band"
    )


def test_known_bad_ids_are_live() -> None:
    ids = {f"{u.module}:{u.expression}" for u in BAND_USES}
    assert set(KNOWN_BAD) <= ids, set(KNOWN_BAD) - ids
    assert set(LOCAL_BAND_SOURCES) <= {(u.module, u.expression) for u in BAND_USES}


@pytest.mark.parametrize("use", _case_ids())
def test_every_band_build_passes_is_valid(use: BandUse) -> None:
    for label, band in _resolve(use):
        _check_band(f"{use.module}:{use.line} {label}", band, use.order)


def _inventory() -> list[tuple[str, str]]:
    """(module, name) of every module-level *_BAND / *_BANDS / *_BAND_MM
    assignment whose value is a tuple, in the band-owning module families."""
    found: list[tuple[str, str]] = []
    for path in sorted(SCRIPTS.glob("*.py")):
        stem = path.stem
        if not (
            stem.startswith("build_")
            or stem.endswith(("_spec", "_geometry", "_geom"))
        ):
            continue
        text = path.read_text(encoding="utf-8")
        if "_BAND" not in _identifier_spelling(text):
            continue  # no assignment target can end in _BAND/_BANDS/_BAND_MM
        tree = ast.parse(text, filename=str(path))
        for node in tree.body:
            targets = (
                node.targets
                if isinstance(node, ast.Assign)
                else [node.target]
                if isinstance(node, ast.AnnAssign)
                else []
            )
            for target in targets:
                if isinstance(target, ast.Name) and target.id.endswith(
                    ("_BAND", "_BANDS", "_BAND_MM")
                ):
                    found.append((stem, target.id))
    return found


def test_every_band_tuple_is_checked_or_classified() -> None:
    checked: set[int] = set()
    for use in BAND_USES:
        if use.module in OFFLINE_IMPORT_EXCLUSIONS:
            continue
        module = importlib.import_module(use.module)
        key = (use.module, use.expression)
        if key in LOCAL_BAND_SOURCES:
            source = eval(LOCAL_BAND_SOURCES[key][0], vars(module))  # noqa: S307
            checked.add(id(source))
            checked.update(id(band) for _, band in _resolve(use))
            continue
        try:
            checked.add(id(eval(use.expression, vars(module))))  # noqa: S307
        except NameError:
            continue  # reported by the per-use test
    unclassified = []
    for module_name, name in _inventory():
        value = getattr(importlib.import_module(module_name), name)
        if not isinstance(value, tuple):
            continue  # a scalar .X/.XX half-width, not a two-sided band
        key = (module_name, name)
        if id(value) in checked or key in NOT_FIT_BANDS or key in INDEXED_FIT_BANDS:
            continue
        unclassified.append(f"{module_name}.{name} = {value!r}")
    assert not unclassified, (
        "band tuples that no checked consumer reads; feed them through "
        "_fit_deviations.deviations or list them in NOT_FIT_BANDS with a reason: "
        + "; ".join(unclassified)
    )


@pytest.mark.parametrize(
    ("module_name", "name"),
    sorted(INDEXED_FIT_BANDS),
    ids=[f"{m}:{n}" for m, n in sorted(INDEXED_FIT_BANDS)],
)
def test_indexed_fit_bands_are_valid(module_name: str, name: str) -> None:
    band = getattr(importlib.import_module(module_name), name)
    _check_band(f"{module_name}.{name}", band, "upper_lower")


def test_classification_lists_are_current() -> None:
    inventory = set(_inventory())
    assert ("dt_cylinder_gear_spec", "OVERALL_THICKNESS_BAND") in inventory, (
        "missing band inventory anchor: dt_cylinder_gear_spec:OVERALL_THICKNESS_BAND"
    )
    for listing in (NOT_FIT_BANDS, INDEXED_FIT_BANDS):
        stale = set(listing) - inventory
        assert not stale, f"listed constants that are gone: {sorted(stale)}"
    assert not set(NOT_FIT_BANDS) & set(INDEXED_FIT_BANDS)


@pytest.fixture
def band_use_source_tree(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """AST-only sources: every consumer anchor plus a rich unrelated module."""
    anchors = {
        "build_dt_crank_drive_gear": "GEAR_FACE_WIDTH_BAND",
        "build_dt_cone_gear_shaft": "band",
    }
    for module, expression in anchors.items():
        (tmp_path / f"{module}.py").write_text(
            f"deviations({expression})\n", encoding="utf-8"
        )
    (tmp_path / "build_unrelated.py").write_text(
        "".join(f"deviations(UNRELATED_{i}_BAND)\n" for i in range(60)),
        encoding="utf-8",
    )
    monkeypatch.setitem(globals(), "SCRIPTS", tmp_path)
    return tmp_path


def test_band_uses_anchor_rejects_no_match(
    band_use_source_tree: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The positive control makes an actual scanner-glob mutation fail too.
    monkeypatch.setitem(globals(), "BAND_USES", _band_uses())
    test_band_uses_are_found()
    monkeypatch.setitem(globals(), "SCRIPTS", band_use_source_tree / "nowhere")
    monkeypatch.setitem(globals(), "BAND_USES", _band_uses())
    with pytest.raises(AssertionError, match="band consumer scan found only 0"):
        test_band_uses_are_found()


@pytest.mark.parametrize(
    ("module", "expression"),
    [
        ("build_dt_crank_drive_gear", "GEAR_FACE_WIDTH_BAND"),
        ("build_dt_cone_gear_shaft", "band"),
    ],
)
def test_band_uses_anchor_rejects_one_directory_deep_source(
    band_use_source_tree: Path,
    monkeypatch: pytest.MonkeyPatch,
    module: str,
    expression: str,
) -> None:
    monkeypatch.setitem(globals(), "BAND_USES", _band_uses())
    test_band_uses_are_found()
    moved = band_use_source_tree / "moved"
    moved.mkdir()
    (band_use_source_tree / f"{module}.py").rename(moved / f"{module}.py")
    monkeypatch.setitem(globals(), "BAND_USES", _band_uses())
    # Sixty unrelated helpers still meet the count; only this source is lost.
    with pytest.raises(
        AssertionError, match=f"missing band consumer anchor: {module}:{expression}"
    ):
        test_band_uses_are_found()


@pytest.fixture
def band_inventory_source_tree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Path:
    """AST-only assignments satisfy real lists without importing their owners."""
    names = set(NOT_FIT_BANDS) | set(INDEXED_FIT_BANDS) | {
        ("dt_cylinder_gear_spec", "OVERALL_THICKNESS_BAND"),
    }
    by_module: dict[str, list[str]] = {}
    for module, name in sorted(names):
        by_module.setdefault(module, []).append(f"{name} = (0.02, -0.02)\n")
    for module, assignments in by_module.items():
        (tmp_path / f"{module}.py").write_text(
            "".join(assignments), encoding="utf-8"
        )
    (tmp_path / "build_unrelated.py").write_text(
        "".join(f"UNRELATED_{i}_BAND = (0.02, -0.02)\n" for i in range(60)),
        encoding="utf-8",
    )
    monkeypatch.setitem(globals(), "SCRIPTS", tmp_path)
    return tmp_path


def test_inventory_anchor_rejects_no_match(
    band_inventory_source_tree: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    test_classification_lists_are_current()
    monkeypatch.setitem(globals(), "SCRIPTS", band_inventory_source_tree / "nowhere")
    with pytest.raises(
        AssertionError,
        match="missing band inventory anchor: dt_cylinder_gear_spec:OVERALL_THICKNESS_BAND",
    ):
        test_classification_lists_are_current()


@pytest.mark.parametrize(
    ("module", "name"),
    [
        ("dt_cylinder_gear_spec", "OVERALL_THICKNESS_BAND"),
    ],
)
def test_inventory_anchor_rejects_one_directory_deep_source(
    band_inventory_source_tree: Path, module: str, name: str
) -> None:
    test_classification_lists_are_current()
    moved = band_inventory_source_tree / "moved"
    moved.mkdir()
    (band_inventory_source_tree / f"{module}.py").rename(moved / f"{module}.py")
    # Unrelated assignments and every other source cannot replace this anchor.
    with pytest.raises(
        AssertionError, match=f"missing band inventory anchor: {module}:{name}"
    ):
        test_classification_lists_are_current()


@pytest.mark.parametrize(
    ("band", "order"),
    [
        ((0.025, 0.025), "upper_lower"),  # the warm-c486 crank_drive_gear band
        ((0.010, 0.050), "upper_lower"),
        ((0.050, 0.010), "lower_upper"),
        ((0.020, 0.020), "lower_upper"),
    ],
)
def test_check_band_rejects_inverted_and_zero_width_bands(
    band: tuple[float, float], order: str
) -> None:
    # The guard must fail on the shapes it exists to catch, in both argument
    # orders, or every parametrized case above passes vacuously.
    with pytest.raises((AssertionError, ValueError)):
        _check_band("synthetic", band, order)


@pytest.mark.parametrize(
    ("source", "replacement"),
    [
        ("REAM_H7", (0.017, 0.002)),
        ("SHAFT_G6_3_TO_6_MM", (-0.006, -0.015)),
    ],
)
def test_measured_close_running_clearance_tracks_shared_bands(
    monkeypatch: pytest.MonkeyPatch,
    source: str,
    replacement: tuple[float, float],
) -> None:
    hole_lower, hole_upper = _fit_deviations.deviations(_fit_close_running.REAM_H7)
    shaft_lower, shaft_upper = _fit_deviations.deviations(_fit_close_running.SHAFT_G6_3_TO_6_MM)
    expected = hole_lower - shaft_upper, hole_upper - shaft_lower
    assert _fit_close_running.measured_close_running_clearance_mm() == pytest.approx(expected)
    assert 0.0 < expected[0] < expected[1]

    # Change each input independently: a copied clearance literal cannot pass.
    monkeypatch.setattr(_fit_close_running, source, replacement)
    hole_lower, hole_upper = _fit_deviations.deviations(_fit_close_running.REAM_H7)
    shaft_lower, shaft_upper = _fit_deviations.deviations(_fit_close_running.SHAFT_G6_3_TO_6_MM)
    changed = hole_lower - shaft_upper, hole_upper - shaft_lower
    assert changed != expected
    assert _fit_close_running.measured_close_running_clearance_mm() == pytest.approx(changed)


@pytest.mark.parametrize("grade", ("standard", "contact_critical"))
def test_gear_tip_grade_reads_its_shared_configuration(grade: str) -> None:
    import _config

    configured = tuple(float(value) for value in _config.fit("gear_tip", f"{grade}_band_mm"))
    assert _gear_fit_limits.gear_tip_band_mm(grade) == configured
    assert configured[0] == 0.0
    assert configured[1] < 0.0


def test_gear_tip_grade_reader_tracks_config_edits(monkeypatch: pytest.MonkeyPatch) -> None:
    import _config

    seen = []

    def fit_value(*keys: str):
        seen.append(keys)
        return [0.0, -0.03]

    monkeypatch.setattr(_config, "fit", fit_value)
    assert _gear_fit_limits.gear_tip_band_mm("standard") == (0.0, -0.03)
    assert seen == [("gear_tip", "standard_band_mm")]


def test_gear_tip_grade_reader_refuses_unknown_or_inverted_grades(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import _config

    with pytest.raises(ValueError, match="unsupported gear-tip grade"):
        _gear_fit_limits.gear_tip_band_mm("routine")
    monkeypatch.setattr(_config, "fit", lambda *keys: (-0.02, 0.0))
    with pytest.raises(ValueError, match="inverted"):
        _gear_fit_limits.gear_tip_band_mm("contact_critical")


@pytest.mark.parametrize("band", [(0.025, 0.025), (0.010, 0.050)])
def test_fit_helpers_share_band_validation(band: tuple[float, float]) -> None:
    for helper in (
        _fit_deviations.validate_band,
        _fit_deviations.deviations,
    ):
        with pytest.raises(ValueError) as error:
            helper(band)
        assert str(error.value) == f"fit band is inverted: {band!r}"


@pytest.mark.parametrize(
    "band",
    [
        (0.025, 0.010),
        (0.000, -0.020),
        (0.012, 0.000),
        (-0.010, -0.030),
    ],
)
def test_deviations_preserves_released_bands(band: tuple[float, float]) -> None:
    assert _fit_deviations.deviations(band) == (band[1], band[0])


def test_scans_find_nfkc_normalized_identifiers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The text prefilters must not drop a source the parser would match:
    Python NFKC-normalizes identifiers, so full-width spellings count."""
    (tmp_path / "width_spec.py").write_text(
        "WIDTH_ＢAND = (0.0, 1.0)\nｄeviations(WIDTH_BAND)\n", encoding="utf-8"
    )
    monkeypatch.setitem(globals(), "SCRIPTS", tmp_path)
    assert _inventory() == [("width_spec", "WIDTH_BAND")]
    assert [(use.module, use.expression) for use in _band_uses()] == [
        ("width_spec", "WIDTH_BAND")
    ]
