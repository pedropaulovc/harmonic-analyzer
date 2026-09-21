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
    assert marked == {"Width", "Depth", "FootHt", "BoreDia", "BoreHeight"}
    # The strap and the crown are described by sheet-derived geometry (a band
    # between two faces, an arc radius), so their sketches stay unmarked.
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
    assert labels == {
        "overall height",
        "crown radius",
        "strap depth",
        "hold-down hole location",
    }


def test_arbor_bore_closes_the_configured_running_fit() -> None:
    import _config

    assert round(arbor_pedestal_spec.BORE_DIA, 2) == 9.55
    assert drawing.DIMENSION_CALLOUTS == {"BoreDia": "REAM THRU; ON PART C/L"}
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
    assert spec.size == "#4"
    assert spec.fit == "normal"
    assert arbor_pedestal_spec.SCREW_HOLE_DIA == blind_cut_dia_mm(spec)
    assert part.SCREW_HOLE_DIA == blind_cut_dia_mm(spec)


def test_hold_down_hole_sits_clear_inside_the_exposed_ledge() -> None:
    """The plan locates the hole off the foot's far face, so the print is only
    honest if the hole clears both the near edge and the strap it hides under."""
    half_depth = arbor_pedestal_spec.FOOT_DEPTH / 2.0
    strap_face = half_depth - arbor_pedestal_spec.STRAP_T
    radius = arbor_pedestal_spec.SCREW_HOLE_DIA / 2.0
    to_near_edge = arbor_pedestal_spec.SCREW_Z + half_depth
    to_strap_face = strap_face - arbor_pedestal_spec.SCREW_Z
    assert to_near_edge > radius
    assert to_strap_face > radius
    # Dimensioned from the far face, the printed value is the whole depth less
    # the ledge offset -- one datum for every Z on the plan.
    assert half_depth - arbor_pedestal_spec.SCREW_Z == 13.0


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
    plan_bottom = drawing._top_y(arbor_pedestal_spec.FOOT_DEPTH / 2.0)
    assert dome_top < plan_bottom
    # The plan's near edge (the exposed hold-down ledge) projects to its top.
    assert drawing._top_y(-arbor_pedestal_spec.FOOT_DEPTH / 2.0) > plan_bottom
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
