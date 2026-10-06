"""Offline contracts for the arbor-pedestal drawing."""

from __future__ import annotations

import re
from pathlib import Path

import dt_arbor_pedestal_spec
import build_dt_arbor_pedestal as part
import draw_dt_arbor_pedestal as drawing
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS, model_toleranced_dimensions
from _drawing_registry import DRAWING_TEMPLATES, DRAWINGS_BY_NAME
from _hole_spec import blind_cut_dia_mm


def _drawing_source() -> str:
    return Path(drawing.__file__).read_text(encoding="utf-8")


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/dt-arbor-pedestal.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/dt-arbor-pedestal.pdf")
    assert drawing.PNG.as_posix().endswith("/png/dt-arbor-pedestal_drawing.png")
    assert DRAWINGS_BY_NAME["dt_arbor_pedestal"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_drawing_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is dt_arbor_pedestal_spec.DRAWING_DIMENSIONS
    marked = set().union(*dt_arbor_pedestal_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP) | set(drawing.TOP_KEEP)
    # Every marked dimension is placed by exactly one view, and no view keeps a
    # name the part never marks: an unplaced import is deleted silently.
    assert kept == marked
    assert not set(drawing.FRONT_KEEP) & set(drawing.TOP_KEEP)
    assert marked == {
        "Width",
        "Depth",
        "FootHt",
        "BoreDia",
        "BoreHeight",
        "DomeRadius",
        "StrapDepth",
        "HoldDownLocation",
        "HoleLateral",
        "BoreLateral",
        "SetScrewLocation",
    }
    # The strap band is owned by its reference sketch, so the strap profile
    # stays unmarked.
    assert "StrapProfile" not in dt_arbor_pedestal_spec.DRAWING_DIMENSIONS


def test_the_part_owns_every_printed_decimal_place() -> None:
    """Policy rule 2: places are the tolerance, so the .SLDPRT carries them."""
    by_name = dt_arbor_pedestal_spec.DRAWING_PRECISION_BY_NAME
    assert by_name == {
        "Width": 1,
        "Depth": 1,
        "FootHt": 1,
        "BoreDia": 2,
        "BoreHeight": 2,
        "DomeRadius": 1,
        "StrapDepth": 1,
        "HoldDownLocation": 1,
        "HoleLateral": 1,
        "BoreLateral": 1,
        "SetScrewLocation": 2,
    }
    part_source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_precision(adapter, DRAWING_PRECISION)" in part_source
    source = _drawing_source()
    # The sheet reads the places back and never rewrites them.
    assert "set_dimension_precision" not in source
    assert "assert_imported_precision(" in source
    assert Path(drawing.__file__).name in PRECISION_MIGRATED_DRAWINGS


def test_no_feature_asks_for_a_third_decimal() -> None:
    """cad/docs/tolerance-policy.md reserves three places for mating sizes.

    Nothing on this post is one: the journal bore's own band is what holds the
    running fit, and the axis height perturbs no transfer quantity.
    """
    places = {
        **dt_arbor_pedestal_spec.DRAWING_PRECISION_BY_NAME,
        **dt_arbor_pedestal_spec.DRAWING_REFERENCE_PRECISION,
    }
    assert max(places.values()) == 2
    assert model_toleranced_dimensions(part) == {
        ("BoreProfile", "BoreDia"): "*deviations(BORE_DIA_BAND)"
    }


def test_sheet_derived_dimensions_take_their_places_from_the_spec() -> None:
    """A label the spec does not know is a KeyError ten minutes into a farm
    leaf, so the recipe's labels and the spec's keys are matched here."""
    labels = set(
        re.findall(r'_set_reference_precision\([^,]+,\s*"([^"]+)"\)', _drawing_source())
    )
    assert labels == set(dt_arbor_pedestal_spec.DRAWING_REFERENCE_PRECISION)
    assert labels == {"overall height"}


def test_crown_radius_is_the_dome_radius_the_part_drives() -> None:
    """#810 Codex l4afp follow-up (Main): the R11.0 crown is a controlling
    dimension, so it is the dome boss's own model dimension, never a radius the
    sheet measures off the arc.

    v37 printed R22.0: the dome carried a DIAMETER dimension driven by
    ``"TopRadius" * 2`` and the sheet flipped it radial, so the drawing's
    rebuild fed 22 into a radius and doubled the crown (the part render stayed
    R11). The part now dimensions the crown as the radius it is, and each dome
    equation evaluates to the as-built value it drives."""
    spec = dt_arbor_pedestal_spec
    assert spec.DRAWING_DIMENSIONS["DomeProfile"] == {"DomeRadius"}
    assert spec.DRAWING_PRECISION["DomeProfile"] == {"DomeRadius": 1}
    assert "DomeRadius" in drawing.FRONT_KEEP
    globals_mm = {"BoreHeight": spec.BORE_HEIGHT, "TopRadius": spec.TOP_RADIUS}
    as_built = {"DomeCy": spec.BORE_HEIGHT, "DomeRadius": spec.TOP_RADIUS}
    assert set(part.DOME_DRIVES) == set(as_built)
    for name, expression in part.DOME_DRIVES.items():
        text = re.sub(r'"(\w+)"', lambda m: repr(globals_mm[m.group(1)]), expression)
        assert float(eval(text, {"__builtins__": {}})) == as_built[name], name  # noqa: S307
    # 810-l4afp-1 eye pass: the radius line ran through the bore to the
    # centre; the arrow sits outside the arc so the leader stops on it.
    assert drawing._ARROWS_OUTSIDE == 1
    assert "_show_crown_radius(adapter, front_annotations)" in _drawing_source()


# Every Diametric write a drawing script may make, each onto a dimension that
# is ALREADY a diameter, so the write changes nothing the model solves. Setting
# Diametric on a MODEL dimension keeps its value and re-reads it as the other
# kind: False on a diameter doubles the feature (v37 MHA-DT-002 printed an R22
# crown on the R11 part), True on a radius halves it. A new writer must show
# its dimension is sheet-made or already the kind it sets, and join this list.
_DIAMETRIC_WRITERS = {
    # The OD is the blank's define_circle DIAMETER (build_alignment_pinion).
    "draw_dt_alignment_pinion.py": 1,
    # A sheet-made edge dimension (AddDimension2), not a model dimension.
    "draw_dt_crank_pin.py": 1,
    # The OD reference is sheet-made; the cross-hole callout is the
    # CrossHoleProfile define_circle DIAMETER.
    "draw_fr_tube_frame.py": 2,
    # set_near_side_diameter styles imported define_circle DIAMETERS.
    "_drawing_leaders.py": 1,
}


def test_no_sheet_re_solves_a_model_dimension_through_diametric() -> None:
    """A radial print must come from a radial model dimension (define_circle
    size_dimension="radius"), never from flipping a diameter on the sheet."""
    writes = re.compile(r"""Diametric["']?\s*(?:=|,)\s*(True|False)\b""")
    scripts = Path(drawing.__file__).parent
    found: dict[str, list[str]] = {}
    for path in sorted(scripts.glob("draw_*.py")) + sorted(scripts.glob("_drawing_*.py")):
        values = writes.findall(path.read_text(encoding="utf-8"))
        if values:
            found[path.name] = values
    assert all(value == "True" for values in found.values() for value in values), found
    assert {name: len(values) for name, values in found.items()} == _DIAMETRIC_WRITERS


def test_manufacturing_locations_are_model_dimensions() -> None:
    """#810 Codex l4afp, policy rule 2: the strap band, the hold-down station
    and both lateral locations carry the .X band, so the part owns them --
    hidden reference sketches whose one driving dimension IS the value --
    and the sheet imports them verbatim instead of deriving them from view
    edges and rewriting their precision."""
    spec = dt_arbor_pedestal_spec
    owned = {
        "StrapDepthReference": "StrapDepth",
        "HoldDownReference": "HoldDownLocation",
        "HoleLateralReference": "HoleLateral",
        "BoreLateralReference": "BoreLateral",
        "SetScrewReference": "SetScrewLocation",
    }
    assert spec.REFERENCE_SKETCHES == tuple(owned)
    for sketch, name in owned.items():
        assert spec.DRAWING_DIMENSIONS[sketch] == {name}
        # The apex tap's station prints at two places (SET_SCREW_WEB_MM).
        places = 2 if name == "SetScrewLocation" else 1
        assert spec.DRAWING_PRECISION[sketch] == {name: places}
    source = _drawing_source()
    assert "from _drawing_hidden_sketches import curate_view_dimensions" in source
    assert source.count("dimensions_by_feature=DRAWING_DIMENSIONS") == 2
    for label in ("strap depth", "hold-down hole location", "lateral location"):
        assert f'label="{label}' not in source
    part_source = Path(part.__file__).read_text(encoding="utf-8")
    assert "_hide_reference_sketches(adapter)" in part_source


def test_reference_lines_restate_the_geometry_their_equations_drive() -> None:
    """Each reference line's value, and the origin anchors that place it on
    the outline, evaluate from the part's globals to the as-built value: the
    deferred equations are neutral, and a global edit moves the line."""
    spec = dt_arbor_pedestal_spec
    globals_mm = {
        "FootWidth": spec.FOOT_WIDTH,
        "FootDepth": spec.FOOT_DEPTH,
        "StrapInnerZ": spec.STRAP_INNER_Z,
        "StrapThickness": spec.STRAP_T,
        "ScrewZ": -spec.SCREW_Z,
        "SetScrewZ": spec.SET_SCREW_Z,
    }

    def evaluate(expression: str) -> float:
        text = re.sub(r'"(\w+)"', lambda m: repr(globals_mm[m.group(1)]), expression)
        return float(eval(text, {"__builtins__": {}}))  # noqa: S307 - literal arithmetic

    expected = {
        "StrapDepth": spec.STRAP_T,
        "HoldDownLocation": spec.STRAP_INNER_Z - spec.SCREW_Z,
        "HoleLateral": spec.FOOT_WIDTH / 2.0,
        "BoreLateral": spec.FOOT_WIDTH / 2.0,
        "SetScrewLocation": spec.STRAP_INNER_Z - spec.SET_SCREW_Z,
    }
    for sketch, plane, name, start, end, orientation, value, drives in part.REFERENCE_LINES:
        assert value == expected[name]
        axis = 1 if orientation == "vertical" else 0
        assert abs(end[axis] - start[axis]) == value
        assert end[1 - axis] == start[1 - axis]
        anchors = [abs(c) for c in start if abs(c) > 1e-9]
        assert [evaluate(d) for d in drives] == [value, *anchors], sketch
        # Rule 7: every line starts on a feature -- the west side face for a
        # lateral location, the far face or strap root for a plan depth.
        if name in ("HoleLateral", "BoreLateral", "HoldDownLocation"):
            assert start[0] == -spec.FOOT_WIDTH / 2.0
        assert plane == ("Front" if name == "BoreLateral" else "Top")


def test_arbor_bore_closes_the_configured_running_fit() -> None:
    import _config

    assert round(dt_arbor_pedestal_spec.BORE_DIA, 2) == 9.55
    assert drawing.DIMENSION_CALLOUTS == {"BoreDia": "REAM THRU"}
    shaft_limits = (9.505, 9.525)
    bore_limits = (9.550, 9.580)
    clearances = (
        bore_limits[0] - shaft_limits[1],
        bore_limits[1] - shaft_limits[0],
    )
    expected = tuple(_config.fit("shaft_in_bushing", "diametral_clearance_mm"))
    assert tuple(round(value, 3) for value in clearances) == expected


def test_screw_hole_contract_is_part_owned() -> None:
    spec = dt_arbor_pedestal_spec.SCREW_HOLE_SPEC
    assert part.SCREW_HOLE_SPEC is spec
    assert spec.kind == "clearance"
    assert spec.size == "#8"
    assert spec.fit == "close"
    assert dt_arbor_pedestal_spec.SCREW_HOLE_DIA == blind_cut_dia_mm(spec)
    assert part.SCREW_HOLE_DIA == blind_cut_dia_mm(spec)


def test_foot_grew_outboard_only_around_an_unmoved_strap() -> None:
    """U34c: the strap band and part origin stay put; only the ledge grew."""
    spec = dt_arbor_pedestal_spec
    assert (spec.STRAP_ROOT_Z, spec.STRAP_INNER_Z) == (-2.0, 8.0)
    assert spec.FOOT_DEPTH == 28.0
    assert spec.LEDGE_DEPTH == 18.0
    assert spec.FOOT_NEAR_Z == -20.0
    assert spec.SCREW_Z == -11.0


def test_hold_down_hole_webs_hold_u27_at_the_printed_worst_case() -> None:
    """The plan locates the hole off the strap inner face at one place (±0.8),
    and the foot depth and strap depth print at one place too. Every web the
    hole leaves must keep the 2.0 target with those bands stacked against it,
    plus the title block's +0.10 drilled-hole oversize."""
    import _config

    spec = dt_arbor_pedestal_spec
    band_1pl = 0.8
    assert _config.title_block("linear_1pl")["display"] == "±0.8"
    radius = spec.SCREW_HOLE_DIA / 2.0 + 0.05
    to_strap_root = spec.STRAP_ROOT_Z - spec.SCREW_Z - radius
    to_ledge_end = spec.SCREW_Z - spec.FOOT_NEAR_Z - radius
    to_side = spec.FOOT_WIDTH / 2.0 - radius
    assert to_strap_root - 2 * band_1pl >= 2.0
    assert to_ledge_end - 2 * band_1pl >= 2.0
    assert to_side - band_1pl - band_1pl / 2.0 >= 2.0
    # The MHA-VN-032 head (Ø6.858) floats with the shank in the hole; it must
    # still clear the strap root it is tightened beside.
    head_r = 6.858 / 2.0
    float_r = (spec.SCREW_HOLE_DIA - 4.1656) / 2.0
    assert spec.STRAP_ROOT_Z - spec.SCREW_Z - head_r - 2 * band_1pl - float_r >= 2.0
    # Dimensioned from the strap inner face, the printed value is the strap
    # plus half the ledge -- one datum for every Z on the plan.
    assert spec.STRAP_INNER_Z - spec.SCREW_Z == 19.0


def test_no_dead_band_between_wizard_correction_and_the_builder_assert() -> None:
    """What the wizard will FORCE must cover what the builder will ACCEPT.

    These were two different literals -- `_holes` only corrected a drift over
    0.05 mm, while `build_arbor_pedestal` rejected anything over 0.005. A #4
    clearance initialized at 3.2512 instead of 3.264 drifts 0.0128 and lands in
    the gap: the wizard leaves it, the builder refuses it, and NO value of the
    spec pin can satisfy both. It read as the seat's table "moving" and cost
    three flip-flops of the pin before Codex spotted the real mechanism on #422.

    Both now read one constant. This test fails if they are ever separated
    again, including by someone tightening only the builder's side.
    """
    import _holes

    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "DIAMETER_TOLERANCE_MM" in source, "builder must use the shared tolerance"
    # Any numeric literal compared against the cut diameter re-opens the band.
    # Regex rather than a fixed string so `>0.005`, `> 0.0050` and friends are
    # caught too -- a whitespace variant slipping through would defeat the gate.
    assert not re.search(r"[<>]=?\s*0\.0*5\b|[<>]=?\s*0\.005\d*", source), (
        "builder compares the cut diameter against a numeric literal; use "
        "_holes.DIAMETER_TOLERANCE_MM so the wizard's correction threshold and "
        "this acceptance threshold cannot separate into a dead band again"
    )

    holes_source = Path(_holes.__file__).read_text(encoding="utf-8")
    assert (
        "abs(initialized_dia_mm - pinned_dia_mm) > DIAMETER_TOLERANCE_MM"
        in holes_source
    )

    # The tolerance must sit strictly between the benign rounding gap (the
    # 0.0001 between CLEARANCE_MM's 3.264 and the live 3.2639 -- writing there
    # would corrupt swHoleThru 25 into 26) and the wrong-row drift it must
    # catch (3.264 vs ("#3","loose") 3.251 = 0.0128).
    rounding_gap = abs(3.2639 - _holes.CLEARANCE_MM[("#4", "normal")])
    wrong_row_drift = abs(
        _holes.CLEARANCE_MM[("#4", "normal")] - _holes.CLEARANCE_MM[("#3", "loose")]
    )
    assert rounding_gap < _holes.DIAMETER_TOLERANCE_MM < wrong_row_drift


def test_the_sheet_carries_no_notes() -> None:
    """Every digit on this print is a dimension: the taper angle and upright
    root the old sheet spelled out in a note are now the crown radius, the
    tangency statement and the foot width the views already carry."""
    assert not hasattr(dt_arbor_pedestal_spec, "DRAWING_NOTES")
    source = _drawing_source()
    for helper in ("add_note(", "add_attached_note(", "add_property_linked_note("):
        assert helper not in source, helper
    assert "Manufacturing Notes" not in source
    # The only free text left is digit-free and tied to the dimension it
    # qualifies (a reaming instruction, a concentricity/tangency statement).
    assert not re.search(r'SetText\(\d+,\s*"[^"]*\d', source)
    for text in drawing.DIMENSION_CALLOUTS.values():
        assert not re.search(r"\d", text), text


def test_pedestal_has_no_gdt_or_basic_dimensions() -> None:
    source = _drawing_source()
    for helper in (
        "add_datum_feature(",
        "add_feature_control_frame(",
        "set_basic_dimension(",
        "project_part_pmi(",
    ):
        assert helper not in source, helper
    assert "datum=" not in source
    assert "characteristic=" not in source
    assert not hasattr(dt_arbor_pedestal_spec, "GEOMETRIC_TOLERANCES_MM")


def test_running_bore_and_mating_foot_seat_carry_surface_finish_controls() -> None:
    source = _drawing_source()
    by_key = {c.key: c for c in dt_arbor_pedestal_spec.SURFACE_FINISHES}
    assert set(by_key) == {"arbor_bore", "foot_seat"}
    assert by_key["arbor_bore"].roughness_um == 1.6
    assert by_key["arbor_bore"].face.contains_y_mm == dt_arbor_pedestal_spec.BORE_HEIGHT
    # The seat is the only face that MUST be cut on a part the title block
    # otherwise leaves CAST/MACHINED; it is the y=0 plane facing -Y.
    assert by_key["foot_seat"].roughness_um == 3.2
    assert by_key["foot_seat"].face.normal == (0, -1, 0)
    assert by_key["foot_seat"].face.offset_mm == 0.0
    for key in by_key:
        assert f'surface_finish_by_key(SURFACE_FINISHES, "{key}")' in source
    assert source.count("add_surface_finish(") == 2


def test_projected_views_stay_aligned_and_ordered() -> None:
    """Third angle: the plan sits above the elevation on the same centre, and
    the two view boxes do not overlap at the sheet's 2:1 scale."""
    assert drawing.SHEET_SCALE == (2.0, 1.0)
    assert drawing.TOP_CENTER[0] == drawing.FRONT_CENTER[0]
    dome_top = drawing._front_y(
        dt_arbor_pedestal_spec.BORE_HEIGHT + dt_arbor_pedestal_spec.TOP_RADIUS
    )
    plan_bottom = drawing._top_y(dt_arbor_pedestal_spec.STRAP_INNER_Z)
    # Air for the crown callout between the elevation and the plan.
    assert plan_bottom - dome_top >= 0.012
    # The plan's near edge (the exposed hold-down ledge) projects to its top,
    # and the view is centred on its bounding box, not on model z 0.
    plan_top = drawing._top_y(dt_arbor_pedestal_spec.FOOT_NEAR_Z)
    assert plan_top > plan_bottom
    assert abs((plan_top + plan_bottom) / 2.0 - drawing.TOP_CENTER[1]) < 1e-12
    assert drawing._front_y(0.0) < drawing._front_y(dt_arbor_pedestal_spec.FOOT_HEIGHT)


def test_every_annotation_anchor_prints_inside_the_sheet() -> None:
    """A mistyped lane coordinate is a dimension off the sheet edge or buried
    in the title block -- neither survives a machinist review, and neither is
    visible until the farm renders the PDF."""
    template = DRAWING_TEMPLATES[DRAWINGS_BY_NAME["dt_arbor_pedestal"].layout]
    margin = 0.0127
    anchors = {
        **drawing.FRONT_KEEP,
        **drawing.TOP_KEEP,
        "front view": drawing.FRONT_CENTER,
        "plan view": drawing.TOP_CENTER,
        "isometric view": drawing.ISO_CENTER,
        "bore lateral lane": drawing.BORE_LATERAL_XY,
        "hole lateral lane": drawing.HOLE_LATERAL_XY,
        "set-screw callout": drawing.SET_SCREW_CALLOUT_XY,
    }
    for label, (x, y) in anchors.items():
        assert margin < x < template.width_m - margin, label
        assert margin < y < template.height_m - margin, label
        assert not (
            x > template.title_block_left_m and y < template.title_block_top_m
        ), f"{label} is inside the title block"


# The native hole-callout font as v37 MHA-DT-002 printed it: the thread line
# "TAP TO BORE, AT CROWN APEX 4-40 UNC <depth> 0.00" (42 glyphs) ran
# 109.7 mm at the 3.5 mm cap height, and its two lines stood 16.8 pt apart.
_CALLOUT_CAP_M = 0.0035
_CALLOUT_ADVANCE = 109.7 / (42 * 3.5)
_CALLOUT_LINE_SPACING = 16.8 * 25.4 / 72.0 / 3.5


def _estimated_set_screw_callout():
    from _layout_geometry import estimate_text_box

    drill = f"Ø{blind_cut_dia_mm(dt_arbor_pedestal_spec.SET_SCREW_HOLE_SPEC):.2f} THRU"
    thread = f"{drawing.SET_SCREW_PROCESS} 4-40 UNC-2B THRU"
    return estimate_text_box(
        f"{drill}\n{thread}",
        anchor=drawing.SET_SCREW_CALLOUT_XY,
        height=_CALLOUT_CAP_M,
        reference=2,  # swCENTER: callout_xy is the text block's centre
        advance_ratio=_CALLOUT_ADVANCE,
        line_spacing=_CALLOUT_LINE_SPACING,
    )


def test_apex_tap_callout_prints_inside_the_zone_frame() -> None:
    """V37 blocker: the callout's CENTRE sat on the sheet, its text ran 22.6 mm
    past the left zone frame. The whole estimated block must fit, with the
    clear gap the sheet's read-back proof demands."""
    from _drawing_annotation_extent import CLEAR_GAP_M

    template = DRAWING_TEMPLATES[DRAWINGS_BY_NAME["dt_arbor_pedestal"].layout]
    frame = 0.0127
    box = _estimated_set_screw_callout()
    assert box.xmin >= frame + CLEAR_GAP_M
    assert box.xmax <= template.width_m - frame - CLEAR_GAP_M
    # Left of the hole, so the leader rises right into the plan.
    assert box.xmax < drawing.TOP_CENTER[0]


def test_apex_tap_callout_clears_the_crown_the_plan_and_the_left_lanes() -> None:
    """V37 blocker: the callout sat on the (61.72) and the elevation. Its
    estimated block must clear every neighbour the sheet's read-back proof
    checks, WITHOUT place_callout_clear having to move it (a move only goes up
    or right, toward the plan)."""
    from _drawing_annotation_extent import CLEAR_GAP_M, PLACE_SETTLE_M, boxes_clear

    box = _estimated_set_screw_callout()
    block = (box.xmin, box.ymin, box.xmax, box.ymax)
    below = drawing.set_screw_callout_below()
    beside = drawing.set_screw_callout_beside()
    above = drawing.set_screw_callout_above()
    assert set(below) == {
        "crown apex and its overall-height extension line",
        "overall height dimension line",
    }
    assert set(above) == {"plan far face"}
    neighbours = {**below, **beside, **above}
    crowded = [name for name, other in neighbours.items() if not boxes_clear(block, other)]
    assert crowded == []
    # No upward move: the band's floor already clears the crown with settle.
    assert all(box.ymin >= other[3] + CLEAR_GAP_M + PLACE_SETTLE_M for other in below.values())
    # The leader may cross the plan's own far face to reach the hole, never
    # the extension lines drawn off it (place_callout_clear checks below and
    # beside only).
    assert "plan far face" not in {**below, **beside}


def test_the_tap_note_solidworks_adds_is_removed() -> None:
    """V37: a stray "#4-40 Tapped Hole" note printed over the plan's 24.0."""
    source = _drawing_source()
    assert 'redundant_note_substrings=("Tapped Hole",)' in source
    assert "expected_redundant_notes=1" in source


def test_part_stamps_make_flexible_material_and_protective_finish() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    assert part.MATERIAL == "Plain Carbon Steel"
    import _config

    config = _config.parts("dt-arbor-pedestal")
    assert config["material"] == "LOW-CARBON STEEL OR GRAY IRON"
    assert config["material_specification"] == "LOW-CARBON STEEL OR GRAY IRON"
    assert config["finish"] == (
        "BLACK JAPAN/ENAMEL; MASK BORE AND FOOT SEAT; OIL BARE MACHINED SURFACES"
    )
    assert config["process"] == "machined from solid stock or casting"
    # Two identical pedestals: the south support plus the north one rotated
    # 180 about Y (build_drive_train_assembly places both).
    assert int(config["quantity"]) == 2


def test_lateral_locations_start_on_a_feature_not_the_symmetry_axis() -> None:
    """Policy rule 7: X is dimensioned from the foot's west side face in both
    views, and no callout falls back on the part centreline."""
    source = _drawing_source()
    assert "PART C/L" not in source
    starts = {row[2]: row[3] for row in part.REFERENCE_LINES}
    assert starts["BoreLateral"][0] == -dt_arbor_pedestal_spec.FOOT_WIDTH / 2.0
    assert starts["HoleLateral"][0] == -dt_arbor_pedestal_spec.FOOT_WIDTH / 2.0
    # The hole lane sits above the plan's near edge; the foot-width lane sits
    # below the far face, over the tap callout's shoulder.
    plan_top = drawing._top_y(dt_arbor_pedestal_spec.FOOT_NEAR_Z)
    assert plan_top < drawing.HOLE_LATERAL_XY[1]
    assert (
        drawing.SET_SCREW_CALLOUT_XY[1]
        < drawing.TOP_KEEP["Width"][1]
        < drawing._top_y(dt_arbor_pedestal_spec.STRAP_INNER_Z)
    )
    # The bore lane sits below the seat.
    assert drawing.BORE_LATERAL_XY[1] < drawing._front_y(0.0)


def test_crown_callout_says_where_the_tapered_flanks_start() -> None:
    """Round-2 review: the flanks run from the foot corners (the strap root is
    the full foot width) up to tangency with the crown."""
    import build_dt_arbor_pedestal

    source = Path(build_dt_arbor_pedestal.__file__).read_text(encoding="utf-8")
    assert "half_root = FOOT_WIDTH / 2.0" in source
    assert "FOOT CORNERS" in drawing.CROWN_CALLOUT
    assert "TANGENT" in drawing.CROWN_CALLOUT
    assert not re.search(r"\d", drawing.CROWN_CALLOUT)


def test_apex_set_screw_tap_keeps_1_5d_only_at_r11() -> None:
    """#743 Q3 (user: "set screw located at apex of straps"): a #4-40 tap
    through the crown onto the arbor. At the printed worst case (crown radius
    .X low, bore at its maximum, both sags across the thread and a one-pitch
    entry lost) the photographed R10 crown leaves 1.21D of full thread and
    fails rule 12; R11 leaves 1.57D."""
    spec = dt_arbor_pedestal_spec
    assert spec.TOP_RADIUS == 11.0
    assert spec.SET_SCREW_THREAD == "#4-40"
    assert spec.SET_SCREW_HOLE_SPEC.kind == "tapped"
    # Through-next: the tap stops in the bore, never drills on into the strap.
    assert spec.SET_SCREW_HOLE_SPEC.end == "through_next"
    assert spec.set_screw_engagement_d(10.0) < 1.5 <= spec.SET_SCREW_ENGAGEMENT_D
    assert round(spec.SET_SCREW_ENGAGEMENT_D, 2) == 1.57
    assert round(spec.SET_SCREW_FULL_THREAD_MM, 2) == 4.46
    terms = spec.set_screw_wall_terms(spec.TOP_RADIUS)
    assert terms["crown radius at .X minimum"] == spec.TOP_RADIUS - 0.8
    assert all(v < 0 for k, v in terms.items() if k != "crown radius at .X minimum")


def test_apex_set_screw_sits_mid_strap_with_its_webs() -> None:
    """The tap stands at the strap's mid-depth; its station prints at two
    places so the outer web keeps the 2.0 target (1.98 at one place)."""
    spec = dt_arbor_pedestal_spec
    assert spec.SET_SCREW_Z == (spec.STRAP_INNER_Z + spec.STRAP_ROOT_Z) / 2.0
    assert spec.DRAWING_PRECISION_BY_NAME["SetScrewLocation"] == 2
    assert spec.SET_SCREW_WEB_MM >= 2.0
    assert round(spec.SET_SCREW_WEB_MM, 2) == 2.27
    part_source = Path(part.__file__).read_text(encoding="utf-8")
    assert "wizard_hole_on_cylinder(" in part_source
    assert '"SetScrewStationPlane", "Right Plane"' in part_source
    source = _drawing_source()
    assert 'label="apex set-screw tap"' in source
    assert not re.search(r"\d", drawing.SET_SCREW_PROCESS)
    assert "_prove_set_screw_callout_clear(adapter, tap_callout)" in source
