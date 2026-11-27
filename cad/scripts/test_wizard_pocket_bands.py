"""Every guard on a Hole Wizard counterbore is asserted at the band its callout prints.

Rule 3 (cad/docs/drawing-guidelines.md): "Counterbore and countersink diameters
and depths in a Hole Wizard callout print in its standard three-place form;
they are clearance pockets toleranced by the `.XX` grade, not
over-specification." and "A dimension that carries its own band is toleranced
by that band." The specs of MHA-PD-02 and MHA-PD-27 read the three printed
places as ``.XXX`` (±.005) while their sheets allowed ±.01 (#3619, #3620; the
index plate's #3497 first).

For each pocket dimension the printed band is its own band when the part puts
one on the Hole Wizard feature, or the drawing on the callout's own variable
(owner rulings 2026-11-25), else the wizard's ``.XX`` (``_wizard_pocket_band``).
The feature export (what the sheet's callout
declares, and what the traveler inspects against) must carry exactly that band.
Each guard's worst case is then recomputed here from the exported limits, and
the test fails when a spec's value is more favourable than the printed band
allows: a guard asserted tighter than the callout prints.
"""

from __future__ import annotations

import ast
import inspect

import pytest

import build_ch_rocker_strap_tl_sub_plate
import build_pd_platen
import build_pd_platen_bottom_guide
import ch_rocker_strap_tl_sub_plate_spec as sub_plate
import draw_pd_platen
import export_features
import pd_feed_rack_spec as rack
import pd_platen_bottom_guide_spec as guide
import pd_platen_spec as platen
from _mcmaster_91794a060 import HEAD_DIA as RACK_SCREW_HEAD_DIA
from _wizard_pocket_band import WIZARD_POCKET_BAND_MM
from sh_vn_brass_fillister_screw_spec import HEAD_DIA as GUIDE_SCREW_HEAD_DIA
from sh_vn_brass_fillister_screw_spec import HEAD_H as GUIDE_SCREW_HEAD_H
from sh_vn_brass_fillister_screw_spec import SHANK_DIA as GUIDE_SCREW_SHANK_DIA

INCH = 25.4
TOL = 1e-9


def _features(stem: str) -> dict:
    return export_features.requirement_manifest(stem)["features"]


def _names_in(module) -> set[str]:
    """Every bare name a module's source loads (its constants and calls)."""
    tree = ast.parse(inspect.getsource(module))
    return {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}


# Per spec, each wizard pocket dimension's band constant, the feature-export
# field the sheet declares for it, and the module that writes that band (the
# builder on the Hole Wizard feature, or the draw script on the callout's own
# variable), or None when it is left to the wizard's .XX. The platen's depth
# is banded on the callout: its hole table reads the feature
# (draw_pd_platen._print_counterbore_depth_band).
POCKETS = {
    "pd_platen": (
        platen,
        build_pd_platen,
        "guide_b1",
        {
            "cbore_dia": ("CBORE_DIA", "CBORE_DIA_BAND", None),
            "cbore_depth": ("CBORE_DEPTH", "CBORE_DEPTH_BAND", draw_pd_platen),
        },
    ),
    "pd_platen_bottom_guide": (
        guide,
        build_pd_platen_bottom_guide,
        "rack_screw_hole_1",
        {
            "cbore_dia": (
                "SCREW_CBORE_DIA", "SCREW_CBORE_DIA_BAND", build_pd_platen_bottom_guide
            ),
            "cbore_depth": (
                "SCREW_CBORE_DEPTH", "SCREW_CBORE_DEPTH_BAND", build_pd_platen_bottom_guide
            ),
        },
    ),
    # MHA-CH-13-TL-01's hub counterbore: no band of its own (#3622).
    "ch_rocker_strap_tl_sub_plate": (
        sub_plate,
        build_ch_rocker_strap_tl_sub_plate,
        "hub_counterbore",
        {
            "dia": ("HUB_CBORE_DIA", "HUB_CBORE_BAND", None),
            "depth": ("HUB_CBORE_DEPTH", "HUB_CBORE_BAND", None),
        },
    ),
}


def test_the_wizard_pocket_band_is_rule_3s_inch_two_place_row() -> None:
    assert WIZARD_POCKET_BAND_MM == pytest.approx(0.010 * INCH)


@pytest.mark.parametrize("stem", sorted(POCKETS))
def test_each_pocket_band_is_the_one_its_callout_prints(stem: str) -> None:
    spec, builder, feature, pockets = POCKETS[stem]
    exported = _features(stem)[feature]
    builder_names = _names_in(builder)
    for field, (nominal_name, band_name, writer) in pockets.items():
        nominal = getattr(spec, nominal_name)
        upper, lower = getattr(spec, band_name)
        if writer is not None:
            # The band is the part's (Hole Wizard feature) or the callout
            # variable's own, so the native callout displays it.
            assert band_name in _names_in(writer), (stem, band_name)
        else:
            # No band of its own: the wizard pocket's .XX, which no builder
            # writes.
            assert (upper, lower) == pytest.approx(
                (WIZARD_POCKET_BAND_MM, -WIZARD_POCKET_BAND_MM)
            ), (stem, band_name)
        if writer is not builder:
            assert band_name not in builder_names, (stem, band_name)
        assert exported[field] == pytest.approx(
            [nominal + lower, nominal + upper], abs=1e-6
        ), (stem, field)


def test_platen_guards_hold_at_the_printed_bands() -> None:
    features = _features("pd_platen")
    hole = features["guide_b1"]
    thickness_min = features["back_face"]["thickness"][0]
    dia_min = hole["cbore_dia"][0]
    depth_min, depth_max = hole["cbore_depth"]
    hole_max = hole["dia"][1]
    # The head below the paper face in the shallowest pocket.
    head_recess = depth_min - GUIDE_SCREW_HEAD_H
    assert platen.HEAD_RECESS_MIN <= head_recess + TOL
    assert head_recess / INCH == pytest.approx(0.003, abs=1e-6)
    # The floor in the thinnest plate under the deepest pocket.
    floor = thickness_min - depth_max
    assert platen.CBORE_FLOOR_MIN <= floor + TOL
    assert floor / INCH == pytest.approx(0.027, abs=1e-6)
    # The head in the narrowest pocket, the shank anywhere in the largest hole.
    radial = (dia_min - GUIDE_SCREW_HEAD_DIA) / 2.0 - (hole_max - GUIDE_SCREW_SHANK_DIA) / 2.0
    assert platen.HEAD_RADIAL_CLEARANCE_MIN <= radial + TOL
    assert radial > 0.0254


def test_bottom_guide_guards_hold_at_the_printed_bands() -> None:
    features = _features("pd_platen_bottom_guide")
    hole = features["rack_screw_hole_1"]
    height_min, height_max = features["top_face"]["height"]
    dia_min, dia_max = hole["cbore_dia"]
    depth_min, depth_max = hole["cbore_depth"]
    # The head enters the narrowest pocket (the spec's float bounds the
    # transfer the head follows).
    entry = dia_min - 2.0 * guide.SCREW_FLOAT_RADIAL - RACK_SCREW_HEAD_DIA
    assert guide.SCREW_HEAD_ENTRY_MIN <= entry + TOL
    assert entry / INCH == pytest.approx(0.022, abs=1e-4)
    # The floor between the pocket and the underside, both its printed ends.
    floor_min = height_min - depth_max
    floor_max = height_max - depth_min
    assert rack.SCREW_FLOOR - rack.SCREW_FLOOR_BAND <= floor_min + TOL
    assert rack.SCREW_FLOOR + rack.SCREW_FLOOR_BAND >= floor_max - TOL
    # The longest screw on the thinnest floor stops at the tap's least full
    # thread: the margin is ZERO (pd_feed_rack_spec.SCREW_TIP_MARGIN). TOL,
    # 1e-9 mm (4e-11 in), only absorbs float noise in the manifest's inch
    # limits; a negative margin any larger fails.
    tip_reach = rack.SCREW_LENGTH - floor_min
    assert rack.SCREW_TIP_REACH_MAX >= tip_reach - TOL
    assert tip_reach <= rack.TAP_THREAD_DEPTH_MIN + TOL
    assert rack.SCREW_TIP_MARGIN == pytest.approx(0.0, abs=1e-12)
    # The shortest screw on the thickest floor engages what MHA-PD-26 prints.
    engagement = (
        rack.SCREW_LENGTH_MIN
        - floor_max
        - rack.SCREW_FIRST_THREAD_LOSS
        - rack.TAP_MOUTH_BREAK
    )
    assert rack.ENGAGEMENT_WORST <= engagement + TOL
    assert engagement >= rack.ENGAGEMENT_CALLOUT_MIN * INCH - TOL
    # The widest pocket's wall to the front face, as the sheet states it.
    wall = (
        guide.SCREW_CBORE_FRONT_WALL_NOMINAL
        + guide.SCREW_CBORE_DIA / 2.0
        - guide._SCREW_HOLE_Z_BAND
        - dia_max / 2.0
        - guide.EDGE_BREAK
    )
    assert guide.SCREW_CBORE_FRONT_WALL_MIN <= wall + TOL
    assert wall >= 0.044 * INCH - TOL
    # The widest pocket keeps its wall to every through tap along the rail.
    tap_wall = min(
        abs(x - t)
        for x in guide.SCREW_HOLE_X
        for t in (*guide.PLATEN_TAP_X, *guide.LOCK_TAP_X)
    ) - (
        rack.TAP_STATION_SLIP_MAX
        + 2.0 * guide.HOLE_TRANSFER_BAND
        + guide.BAND
        + dia_max / 2.0
        + guide._TAP_MAJOR / 2.0
    )
    assert guide.SCREW_HOLE_TAP_WALL_MIN <= tap_wall + TOL


def test_support_bar_round_counterbores_hold_at_the_printed_bands() -> None:
    """MHA-PD-07's round clamp counterbores keep the owner's own band on the
    Ø (#2422, Ø.3125 +.010/0, put on the ClampHoles Hole Wizard feature) and
    the wizard's .XX on the depth. The guard is recomputed from the exported
    limits, and the wizard .XX on the Ø is shown to fail it, the failure
    necessity/pd-support-bar.yaml N-01 registers (D52)."""
    import build_pd_support_bar as bar
    import machinist_necessity
    import pd_support_bar_drawing_spec as bar_sheet
    import pd_support_bar_spec as bar_spec
    from _inch_wall_limits import WALL_TARGET_MM
    from _paths import CAD_ROOT
    from _printed_tolerance import printed_deviations
    from sh_vn_clamp_screw_spec import HEAD_DIA, HEAD_H, SHANK_DIA

    shop_reads = 0.001 * INCH
    lower, upper = bar_sheet.CLAMP_CBORE_DIA_LIMITS
    assert "CLAMP_CBORE_DIA_LIMITS" in _names_in(bar)
    features = _features("pd_support_bar")
    for name in ("clamp_hole_1", "clamp_hole_2"):
        hole = features[name]
        assert hole["cbore_dia"] == pytest.approx(
            [bar.CLAMP_CBORE_DIA + lower, bar.CLAMP_CBORE_DIA + upper], abs=1e-6
        ), name
        assert hole["cbore_depth"] == pytest.approx(
            [
                bar.CLAMP_CBORE_DEPTH - WIZARD_POCKET_BAND_MM,
                bar.CLAMP_CBORE_DEPTH + WIZARD_POCKET_BAND_MM,
            ],
            abs=1e-6,
        ), name
        dia_min = hole["cbore_dia"][0]
        depth_min, depth_max = hole["cbore_depth"]
        float_max = (hole["dia"][1] - SHANK_DIA) / 2.0
        # The head, its shank floated across the widest hole, in the
        # narrowest pocket: +.0032 at .3125. The builder's guard floats it in
        # the printed .196's limits, the export in the model's .19598's.
        radial = (dia_min - HEAD_DIA) / 2.0 - float_max
        assert bar.clamp_round_head_clearance() == pytest.approx(radial, abs=5e-4)
        assert radial >= shop_reads - TOL
        assert radial / INCH == pytest.approx(0.00325, abs=1e-5)
        # The same at the wizard's .XX on the three printed places (.313,
        # .303 at least): the head meets the wall by .0015.
        row_lower, _ = printed_deviations(
            bar.CLAMP_CBORE_DIA,
            3,
            (-WIZARD_POCKET_BAND_MM, WIZARD_POCKET_BAND_MM),
            unit="in",
        )
        row = (bar.CLAMP_CBORE_DIA + row_lower - HEAD_DIA) / 2.0 - float_max
        assert row / INCH == pytest.approx(-0.0015, abs=1e-5)
        # The head below the front face the platen slides across, and the
        # floor under the deepest pocket in the thinnest bar.
        assert depth_min - HEAD_H >= shop_reads - TOL
        assert bar_spec.BAR_DEPTH_MIN - depth_max >= WALL_TARGET_MM
    necessity = {
        entry.id: entry
        for entry in machinist_necessity.load_necessity(CAD_ROOT / "config", "pd_support_bar")
    }
    assert necessity["N-01"].kind == "gap"
    assert "Ø.3125 +.0100/.0000" in necessity["N-01"].feature
    assert "#2422" in necessity["N-01"].source
