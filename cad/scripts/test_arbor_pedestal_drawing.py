"""Offline contracts for the arbor-pedestal drawing."""

from __future__ import annotations

import re
from pathlib import Path

import arbor_pedestal_spec
import build_arbor_pedestal as part
import draw_arbor_pedestal as drawing
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS, model_toleranced_dimensions
from _drawing_registry import DRAWING_TEMPLATES, DRAWINGS_BY_NAME
from _hole_spec import blind_cut_dia_mm


def _drawing_source() -> str:
    return Path(drawing.__file__).read_text(encoding="utf-8")


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/arbor-pedestal.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/arbor-pedestal.pdf")
    assert drawing.PNG.as_posix().endswith("/png/arbor-pedestal_drawing.png")
    assert DRAWINGS_BY_NAME["arbor_pedestal"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_drawing_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is arbor_pedestal_spec.DRAWING_DIMENSIONS
    marked = set().union(*arbor_pedestal_spec.DRAWING_DIMENSIONS.values())
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
        "StrapDepth",
        "HoldDownLocation",
        "HoleLateral",
        "BoreLateral",
    }
    # The strap band is owned by its reference sketch, and the crown is an arc
    # radius the sheet restates, so the profile sketches stay unmarked.
    assert "StrapProfile" not in arbor_pedestal_spec.DRAWING_DIMENSIONS
    assert "DomeProfile" not in arbor_pedestal_spec.DRAWING_DIMENSIONS


def test_the_part_owns_every_printed_decimal_place() -> None:
    """Policy rule 2: places are the tolerance, so the .SLDPRT carries them."""
    by_name = arbor_pedestal_spec.DRAWING_PRECISION_BY_NAME
    assert by_name == {
        "Width": 1,
        "Depth": 1,
        "FootHt": 1,
        "BoreDia": 2,
        "BoreHeight": 2,
        "StrapDepth": 1,
        "HoldDownLocation": 1,
        "HoleLateral": 1,
        "BoreLateral": 1,
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
        **arbor_pedestal_spec.DRAWING_PRECISION_BY_NAME,
        **arbor_pedestal_spec.DRAWING_REFERENCE_PRECISION,
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
    assert labels == set(arbor_pedestal_spec.DRAWING_REFERENCE_PRECISION)
    assert labels == {"overall height", "crown radius"}


def test_manufacturing_locations_are_model_dimensions() -> None:
    """#810 Codex l4afp, policy rule 2: the strap band, the hold-down station
    and both lateral locations carry the .X band, so the part owns them --
    hidden reference sketches whose one driving dimension IS the value --
    and the sheet imports them verbatim instead of deriving them from view
    edges and rewriting their precision."""
    spec = arbor_pedestal_spec
    owned = {
        "StrapDepthReference": "StrapDepth",
        "HoldDownReference": "HoldDownLocation",
        "HoleLateralReference": "HoleLateral",
        "BoreLateralReference": "BoreLateral",
    }
    assert spec.REFERENCE_SKETCHES == tuple(owned)
    for sketch, name in owned.items():
        assert spec.DRAWING_DIMENSIONS[sketch] == {name}
        assert spec.DRAWING_PRECISION[sketch] == {name: 1}
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
    spec = arbor_pedestal_spec
    globals_mm = {
        "FootWidth": spec.FOOT_WIDTH,
        "FootDepth": spec.FOOT_DEPTH,
        "StrapInnerZ": spec.STRAP_INNER_Z,
        "StrapThickness": spec.STRAP_T,
        "ScrewZ": -spec.SCREW_Z,
    }

    def evaluate(expression: str) -> float:
        text = re.sub(r'"(\w+)"', lambda m: repr(globals_mm[m.group(1)]), expression)
        return float(eval(text, {"__builtins__": {}}))  # noqa: S307 - literal arithmetic

    expected = {
        "StrapDepth": spec.STRAP_T,
        "HoldDownLocation": spec.STRAP_INNER_Z - spec.SCREW_Z,
        "HoleLateral": spec.FOOT_WIDTH / 2.0,
        "BoreLateral": spec.FOOT_WIDTH / 2.0,
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

    assert round(arbor_pedestal_spec.BORE_DIA, 2) == 9.55
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
    spec = arbor_pedestal_spec.SCREW_HOLE_SPEC
    assert part.SCREW_HOLE_SPEC is spec
    assert spec.kind == "clearance"
    assert spec.size == "#8"
    assert spec.fit == "close"
    assert arbor_pedestal_spec.SCREW_HOLE_DIA == blind_cut_dia_mm(spec)
    assert part.SCREW_HOLE_DIA == blind_cut_dia_mm(spec)


def test_foot_grew_outboard_only_around_an_unmoved_strap() -> None:
    """U34c: the strap band and part origin stay put; only the ledge grew."""
    spec = arbor_pedestal_spec
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

    spec = arbor_pedestal_spec
    band_1pl = 0.8
    assert _config.title_block("linear_1pl")["display"] == "±0.8"
    radius = spec.SCREW_HOLE_DIA / 2.0 + 0.05
    to_strap_root = spec.STRAP_ROOT_Z - spec.SCREW_Z - radius
    to_ledge_end = spec.SCREW_Z - spec.FOOT_NEAR_Z - radius
    to_side = spec.FOOT_WIDTH / 2.0 - radius
    assert to_strap_root - 2 * band_1pl >= 2.0
    assert to_ledge_end - 2 * band_1pl >= 2.0
    assert to_side - band_1pl - band_1pl / 2.0 >= 2.0
    # The MHA-143 head (Ø6.858) floats with the shank in the hole; it must
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
    assert not hasattr(arbor_pedestal_spec, "DRAWING_NOTES")
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
    assert not hasattr(arbor_pedestal_spec, "GEOMETRIC_TOLERANCES_MM")


def test_running_bore_and_mating_foot_seat_carry_surface_finish_controls() -> None:
    source = _drawing_source()
    by_key = {c.key: c for c in arbor_pedestal_spec.SURFACE_FINISHES}
    assert set(by_key) == {"arbor_bore", "foot_seat"}
    assert by_key["arbor_bore"].roughness_um == 1.6
    assert by_key["arbor_bore"].face.contains_y_mm == arbor_pedestal_spec.BORE_HEIGHT
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
        arbor_pedestal_spec.BORE_HEIGHT + arbor_pedestal_spec.TOP_RADIUS
    )
    plan_bottom = drawing._top_y(arbor_pedestal_spec.STRAP_INNER_Z)
    # Air for the crown callout between the elevation and the plan.
    assert plan_bottom - dome_top >= 0.012
    # The plan's near edge (the exposed hold-down ledge) projects to its top,
    # and the view is centred on its bounding box, not on model z 0.
    plan_top = drawing._top_y(arbor_pedestal_spec.FOOT_NEAR_Z)
    assert plan_top > plan_bottom
    assert abs((plan_top + plan_bottom) / 2.0 - drawing.TOP_CENTER[1]) < 1e-12
    assert drawing._front_y(0.0) < drawing._front_y(arbor_pedestal_spec.FOOT_HEIGHT)


def test_every_annotation_anchor_prints_inside_the_sheet() -> None:
    """A mistyped lane coordinate is a dimension off the sheet edge or buried
    in the title block -- neither survives a machinist review, and neither is
    visible until the farm renders the PDF."""
    template = DRAWING_TEMPLATES[DRAWINGS_BY_NAME["arbor_pedestal"].layout]
    margin = 0.0127
    anchors = {
        **drawing.FRONT_KEEP,
        **drawing.TOP_KEEP,
        "front view": drawing.FRONT_CENTER,
        "plan view": drawing.TOP_CENTER,
        "isometric view": drawing.ISO_CENTER,
        "bore lateral lane": drawing.BORE_LATERAL_XY,
        "hole lateral lane": drawing.HOLE_LATERAL_XY,
    }
    for label, (x, y) in anchors.items():
        assert margin < x < template.width_m - margin, label
        assert margin < y < template.height_m - margin, label
        assert not (
            x > template.title_block_left_m and y < template.title_block_top_m
        ), f"{label} is inside the title block"


def test_part_stamps_make_flexible_material_and_protective_finish() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    assert part.MATERIAL == "Plain Carbon Steel"
    import _config

    config = _config.parts("arbor-pedestal")
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
    assert starts["BoreLateral"][0] == -arbor_pedestal_spec.FOOT_WIDTH / 2.0
    assert starts["HoleLateral"][0] == -arbor_pedestal_spec.FOOT_WIDTH / 2.0
    # The hole lane sits between the plan's near edge and the foot-width lane.
    plan_top = drawing._top_y(arbor_pedestal_spec.FOOT_NEAR_Z)
    assert plan_top < drawing.HOLE_LATERAL_XY[1] < drawing.TOP_KEEP["Width"][1]
    # The bore lane sits below the seat.
    assert drawing.BORE_LATERAL_XY[1] < drawing._front_y(0.0)


def test_crown_callout_says_where_the_tapered_flanks_start() -> None:
    """Round-2 review: the flanks run from the foot corners (the strap root is
    the full foot width) up to tangency with the crown."""
    import build_arbor_pedestal

    source = Path(build_arbor_pedestal.__file__).read_text(encoding="utf-8")
    assert "half_root = FOOT_WIDTH / 2.0" in source
    assert "FOOT CORNERS" in drawing.CROWN_CALLOUT
    assert "TANGENT" in drawing.CROWN_CALLOUT
    assert not re.search(r"\d", drawing.CROWN_CALLOUT)
