"""Offline contracts for the magnifying-bracket drawing.

The print follows cad/docs/drawing-simplicity-policy.md: a bracket is not on
the GD&T allowlist and it is lock-mated to the lever rod in service, so it
carries no datum, frame, roughness or basic dimension; every size is on a
view (the collar diameters, the thicknesses and the axis-based stations the
review of 2026-09-02 found buried in the notes), and the two note lines are
the match-drill instruction for the unmodelled mounting pattern and the
flange's centring on the collar axis.
"""

from __future__ import annotations

from pathlib import Path

import build_magnifying_bracket as part
import draw_magnifying_bracket as drawing
import magnifying_bracket_spec
from _drawing_registry import DRAWINGS_BY_NAME


def _source() -> str:
    return Path(drawing.__file__).read_text(encoding="utf-8")


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/magnifying-bracket.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/magnifying-bracket.pdf")
    assert drawing.PNG.as_posix().endswith("/png/magnifying-bracket_drawing.png")
    assert (
        DRAWINGS_BY_NAME["magnifying_bracket"].script
        == Path(drawing.__file__).resolve()
    )


def test_spec_is_the_single_source_of_the_marked_dimension_set() -> None:
    assert part.DRAWING_DIMENSIONS is magnifying_bracket_spec.DRAWING_DIMENSIONS
    marked = set().union(*magnifying_bracket_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.TOP_KEEP) | set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP)
    assert kept == marked
    # Plan: the two rectangles' widths/depth and their far corners from the
    # collar axis (one origin per view); front: the collar length.
    assert set(drawing.TOP_KEEP) == {
        "ArmWidth",
        "ArmCornerZ",
        "FlangeWidth",
        "FlangeDepth",
        "FlangeCornerZ",
        "FlangeCornerX",
    }
    assert set(drawing.FRONT_KEEP) == {"WallLen"}
    assert drawing.RIGHT_KEEP == {}
    assert set(drawing.DIMENSION_CALLOUTS) <= kept
    assert set(drawing.TOP_CALLOUTS) <= set(drawing.TOP_KEEP)
    assert set(drawing.FRONT_CALLOUTS) <= set(drawing.FRONT_KEEP)


def test_arm_and_flange_dim_names_are_disambiguated() -> None:
    # Arm + flange are both extruded rectangles emitting bare "Width"/"Depth";
    # the build renames them per-feature so the top view's keep map is
    # unambiguous.  The collision would otherwise repoint the wrong dimension.
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert '"ArmWidth", "ArmDepth"' in source
    assert '"FlangeWidth", "FlangeDepth"' in source


def test_nominals_live_in_the_spec_and_the_drawing_reads_them() -> None:
    # The build and the drawing aim their picks off ONE set of nominals.
    for name in ("COLLAR_OD", "COLLAR_BORE", "COLLAR_HALF_LEN", "ARM_Y", "FLANGE_Y"):
        assert getattr(drawing, name) == getattr(magnifying_bracket_spec, name)
        assert getattr(part, name) == getattr(magnifying_bracket_spec, name)
    assert drawing.ARM_THICKNESS == 7.5
    assert drawing.FLANGE_THICKNESS == 5.08
    assert drawing.ARM_TOP_FROM_COLLAR_OD == 1.5


def test_bracket_is_uncoupled_from_the_assembly_nominals() -> None:
    # The magnifier assembly places the bracket BY NAME and mates it by named
    # references, so it imports no bracket Python constant -- hence one _spec
    # module is right (no _geom split).
    assert not Path(part.__file__).with_name("magnifying_bracket_geom.py").exists()
    assembly = Path(part.__file__).with_name("build_magnifier_assembly.py").read_text(
        encoding="utf-8"
    )
    assert "from build_magnifying_bracket import" not in assembly


def test_notes_are_few_specific_and_never_the_title_block() -> None:
    notes = magnifying_bracket_spec.DRAWING_NOTES
    lines = notes.split("\n")
    assert len(lines) == 2
    # The unmodelled mounting pattern is a process instruction, not a hold;
    # the flange's centring on the axis is the one relationship no single
    # dimension states.
    assert "MATCH-DRILL TO THE SUMMING PLATE AT ASSEMBLY" in notes
    assert "FLANGE CENTRED ON THE COLLAR AXIS" in notes
    # Every size is on a view: no collar, no thickness, no bare integer.
    assert not any(character.isdigit() for character in notes)
    for banned in (
        "COLLAR Ø",
        "THICK",
        "SLIP",
        "DO NOT RELEASE",
        "UNDRILLED BLANK",
        "NOT DEFINED",
        "AISI 1018",
        "BLACK-OXIDE",
        "UOS",
        "DIMENSIONS IN",
        "+/-",
        "DATUM",
        "MHA-",
        "DEBURR",
        "BREAK SHARP",
        "X.XX",
    ):
        assert banned not in notes, banned
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in _source()
    # The isometric caption no longer repeats the sheet scale.
    assert magnifying_bracket_spec.ISOMETRIC_VIEW_NOTE == "ISOMETRIC VIEW"


def test_the_two_tens_are_labelled() -> None:
    # The arm is exactly as wide as the collar is long.
    assert drawing.TOP_CALLOUTS == {"ArmWidth": "ARM WIDTH"}
    assert drawing.FRONT_CALLOUTS == {"WallLen": "COLLAR LENGTH"}


def test_collar_and_thickness_dimensions_are_tied_to_view_geometry() -> None:
    # Every size is a dimension on selected geometry.  In particular, the arm
    # thickness is no longer detached note text: its two picks are the arm's
    # longitudinal edges in the collar-end view.
    source = _source()
    for label in (
        'label="collar OD"',
        'label="arm top face from collar OD"',
        'label="flange thickness"',
        'label="arm thickness"',
        'label="collar bore"',
    ):
        assert label in source, label
    assert source.count("add_edge_dimension(") == 4
    assert source.count("_add_circle_diameter(") == 2  # def + call
    assert "_display_as_diameter(adapter, collar_od" in source
    assert "ARM_THICKNESS_NOTE" not in source
    assert "if add_note(adapter, ARM_THICKNESS_NOTE" not in source
    assert 'label="arm lower longitudinal edge"' in source
    assert 'label="arm upper longitudinal edge"' in source
    # The bore reads on its visible circle (one pick: a second pick on the
    # same circle would deselect it) with the ASME centre mark.
    assert source.count("auto_center_marks(") == 1
    assert "AddDiameterDimension2(" in source
    # ...and the created type is verified: a radius would print half the bore.
    assert "dimension_type != _DIAMETER_DIMENSION" in source
    assert drawing._DIAMETER_DIMENSION == 6
    # The plan's stations read against the collar-axis centreline.
    assert source.count("add_view_centerline(") == 1
    # Non-front geometry is projected through each view's own transform.
    assert "model_point_in_view(" in source
    assert source.count("= _model_frame(") == 2


def test_layout_is_third_angle_and_clear_of_the_title_block() -> None:
    # Plan above the front view, collar-end view beside the front view.
    assert drawing.TOP_CENTER[0] == drawing.FRONT_CENTER[0]
    assert drawing.TOP_CENTER[1] > drawing.FRONT_CENTER[1]
    assert drawing.RIGHT_CENTER[1] == drawing.FRONT_CENTER[1]
    assert drawing.RIGHT_CENTER[0] > drawing.FRONT_CENTER[0]
    # The increased plan/front gap gives the two width callouts complete lanes
    # without dropping either into the front-view dimension cluster.
    assert drawing.TOP_CENTER[1] - drawing.FRONT_CENTER[1] >= 0.095
    assert (
        drawing.TOP_KEEP["ArmWidth"][1] - drawing.TOP_KEEP["FlangeWidth"][1]
        >= 0.015
    )
    assert drawing.TOP_KEEP["FlangeWidth"][1] - drawing.FRONT_CENTER[1] >= 0.040
    collar_bottom = drawing._fy(-drawing.COLLAR_OD / 2.0)
    assert drawing.FRONT_KEEP["WallLen"][1] <= collar_bottom - 0.008
    assert drawing.ARM_TOP_DIMENSION_OFFSET <= 0.005
    # Plan side lanes: the flange's far-edge station nearest, arm outside.
    assert drawing.TOP_KEEP["FlangeCornerZ"][0] > drawing.TOP_KEEP["ArmCornerZ"][0]


def test_print_carries_no_gdt_finish_or_basic_dimensions() -> None:
    source = _source()
    for helper in (
        "add_datum_feature(",
        "add_feature_control_frame(",
        "add_surface_finish(",
        "set_basic_dimension(",
        "project_part_pmi(",
    ):
        assert helper not in source, helper
    assert not hasattr(magnifying_bracket_spec, "GEOMETRIC_TOLERANCES_MM")
    assert not hasattr(magnifying_bracket_spec, "SURFACE_FINISHES")


def test_hidden_lines_stay_on_in_every_orthographic_view() -> None:
    source = _source()
    assert "for view in (top, front, right):\n        set_hidden_lines_visible" in source
    assert "set_hidden_lines_removed(adapter, iso)" in source


def test_unresolved_mounting_pattern_is_not_encoded_as_fake_geometry() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "SCREW_HOLE_DIA" not in source
    assert "SCREW_HOLE_X" not in source


def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    config = _config.parts("magnifying-bracket")
    # The library material renders the model; the spec is what the shop buys
    # (the title block's MATERIAL cell shows the spec).
    assert config["material_specification"] == "AISI 1018 cold-finished steel bar"
    assert config["material_specification"] != config["material"]
    assert config["finish"]
    assert int(config["quantity"]) == 1
