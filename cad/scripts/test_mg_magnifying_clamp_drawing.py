"""Offline contracts for the magnifying-clamp drawing."""

from __future__ import annotations

import math
from pathlib import Path

import pytest

import build_mg_magnifying_clamp as part
import draw_mg_magnifying_clamp as drawing
import mg_magnifying_clamp_spec as spec
import mg_rod_clamp_joint as joint
from _drawing_registry import DRAWINGS_BY_NAME


def test_no_surface_finish_on_the_clamped_bore() -> None:
    # The lever is clamped in its bore: it neither runs nor slides (rule 6).
    assert not hasattr(spec, "SURFACE_FINISHES")
    part_source = Path(part.__file__).read_text(encoding="utf-8")
    drawing_source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "surface_finishes=" not in part_source
    assert "add_surface_finish" not in drawing_source
    assert "roughness_ra=" not in drawing_source


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/mg-magnifying-clamp.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/mg-magnifying-clamp.pdf")
    assert drawing.PNG.as_posix().endswith("/png/mg-magnifying-clamp_drawing.png")
    assert (
        DRAWINGS_BY_NAME["mg_magnifying_clamp"].script == Path(drawing.__file__).resolve()
    )


def test_spec_is_the_single_source_of_the_marked_dimension_set() -> None:
    assert part.DRAWING_DIMENSIONS is spec.DRAWING_DIMENSIONS
    assert part.DRAWING_PRECISION is spec.DRAWING_PRECISION
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.RIGHT_KEEP) | set(drawing.TOP_KEEP)
    assert kept == marked
    assert set(drawing.DIMENSION_CALLOUTS) <= kept
    assert spec.REFERENCE_DIMENSIONS <= set(drawing.TOP_KEEP)


def test_drawing_contract_is_split_from_the_assembly_nominals() -> None:
    # The hex and bore stations the assembly imports live in the drawing-FREE
    # geom module, so a print-note edit cannot enter the assembly recipe.
    import mg_magnifying_clamp_geom as geom

    assert geom.HEX_AF == pytest.approx(7.0 / 16.0 * 25.4)
    assert geom.BLOCK_DEPTH == pytest.approx(geom.HEX_AC)
    assert (geom.LEVER_BORE_Y, geom.BLOCK_HEIGHT) == (19.65, 28.65)
    for gone in ("BLOCK_WIDTH", "ROD_BORE_DIA", "ROD_BORE_X"):
        assert not hasattr(geom, gone)
    assembly = Path(part.__file__).with_name("build_mg_magnifier_assembly.py").read_text(
        encoding="utf-8"
    )
    assert "from mg_magnifying_clamp_geom import" in assembly
    assert "from build_mg_magnifying_clamp import" not in assembly


def test_worst_case_walls_and_engagement_hold_the_contract() -> None:
    for name, (nominal, worst) in spec.WALLS.items():
        assert worst >= spec.WALL_TARGET, name
        assert nominal >= worst, name
    assert spec.WALLS["rod-tap drill point to the lever bore"][1] == pytest.approx(
        spec.ROD_TAP_FLOOR_WALL_WORST
    )
    # The bore centred between the flats by symmetry: its largest drilled Ø
    # on the thinnest stock, off centre by the drill's run-off to mid-block.
    bore_nominal, bore_worst = spec.WALLS["lever bore to a flat"]
    assert bore_nominal == pytest.approx((spec.HEX_AF - 6.2) / 2.0)
    wander = 0.10 + spec.HEX_AC / 2.0 * math.tan(math.radians(0.3))
    assert bore_worst == pytest.approx(
        (spec.HEX_AF - spec.HEX_AF_BAND) / 2.0 - (6.2 + 0.10) / 2.0 - wander
    )
    assert bore_worst == pytest.approx(2.2077, abs=1e-4)
    assert bore_worst >= spec.WALL_TARGET
    # No printed location from a flat: the bore's only offset is its wander.
    assert spec.BORE_OFFSET_MAX == spec.BORE_WANDER == pytest.approx(wander)
    for gone in (
        "LEVER_BORE_FROM_FLAT",
        "LEVER_BORE_FROM_FLAT_PLACES",
        "BORE_WALL",
        "BORE_WALL_STATED_MIN",
    ):
        assert not hasattr(spec, gone), gone
    for module in (part, drawing, spec):
        source = Path(module.__file__).read_text(encoding="utf-8")
        assert "BoreFromFlat" not in source, module.__name__
        assert "FlatWitness" not in source, module.__name__
    assert spec.THUMB_ENGAGEMENT_WORST >= joint.ENGAGEMENT_MIN
    assert joint.ENGAGEMENT_WORST >= joint.ENGAGEMENT_MIN
    assert spec.TAP_REACH_NEEDED <= spec.PLUG_TAP_USABLE_LENGTH
    assert spec.TAP_STOP_WINDOW > 0.0
    assert spec.THUMB_DRILL_NEAR_CLEAR > 0.0 and spec.THUMB_DRILL_FAR_CLEAR > 0.0
    assert spec.ROD_TAP_SPEC is joint.ROD_TAP_SPEC


def test_linked_notes_state_stock_only_and_the_bore_states_no_wall() -> None:
    notes = spec.DRAWING_NOTES
    assert notes == "7/16 HEX BAR, FLATS AS SUPPLIED."
    for gone in ("CENTRED", "PLUG TAP", "CHAMFER", "WALL", "SEAT", "THREAD ENDS"):
        assert gone not in notes
    assert not hasattr(spec, "TAP_TOOL_NOTE")
    assert not hasattr(spec, "BORE_WALL_NOTE")
    # The bore's wall to a flat holds the target: the sheet states none (rule 20).
    assert "WALL" not in spec.LEVER_BORE_CALLOUT
    assert spec.LEVER_BORE_CALLOUT == "DRILL THRU CORNERS\nSLIP ON Ø6 LEVER MHA-MG-03"
    assert "MHA-MG-03" in spec.LEVER_BORE_CALLOUT
    assert spec.SEAT_NOTE.startswith("MHA-MG-04 SHOULDER SEAT")
    assert "NO CHAMFER OR SPOTFACE" in spec.SEAT_NOTE
    assert spec.THUMB_TAP_PROCESS == "TAP INTO BORE"
    for stale in ("SKEW", "5.2", "Ø5 VERTICAL ROD"):
        assert stale not in notes
    assert "BRASS" not in notes and "C36000" not in notes
    assert "DEBURR" not in notes and "BREAK SHARP" not in notes
    assert "X.XX" not in notes
    assert "LINEAR +/-" not in notes
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source
    assert "text=SEAT_NOTE" in source


def test_no_gdt_one_section_and_native_tap_callouts() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert not hasattr(spec, "GEOMETRIC_TOLERANCES_MM")
    assert "add_datum_feature" not in source
    assert "add_feature_control_frame" not in source
    assert "add_surface_finish" not in source
    assert "auto_center_marks" not in source
    assert source.count("create_section_view(") == 1
    # The section hatches in the part's material crosshatch (IFaceHatch's
    # pattern is get-only): the part sets it, the sheet only reads it back.
    assert spec.SECTION_HATCH_PATTERN == "ANSI31 (Iron BrickStone)"
    assert "SECTION_HATCH_PATTERN =" not in source
    assert "UseMaterialHatch =" not in source
    assert "_solid_line_hatch" not in source
    # Both #4-40 taps print native Hole Wizard callouts at the .XX depth places.
    assert source.count("add_native_hole_callout(") == 2
    assert set(spec.TAP_CALLOUT_PRECISION.values()) == {joint.HOLE_DEPTH_PLACES}


class _Extension:
    def __init__(self) -> None:
        self.integers: dict[tuple[int, int], int] = {}
        self.strings: dict[tuple[int, int], str] = {}

    def SetUserPreferenceInteger(self, pref: int, option: int, value: int) -> bool:
        self.integers[pref, option] = value
        return True

    def GetUserPreferenceInteger(self, pref: int, option: int) -> int:
        return self.integers.get((pref, option), 0)

    def SetUserPreferenceString(self, pref: int, option: int, value: str) -> bool:
        self.strings[pref, option] = value
        return True

    def GetUserPreferenceString(self, pref: int, option: int) -> str:
        return self.strings.get((pref, option), "ANSI33 (Bronze Brass)")


class _Model:
    def __init__(self) -> None:
        self.Extension = _Extension()


class _Hatch:
    def __init__(self, material: bool, pattern: str) -> None:
        self.UseMaterialHatch = material
        self.Pattern = pattern


class _Section:
    def __init__(self, part: _Model, hatches: tuple[object, ...]) -> None:
        self.ReferencedDocument = part
        self._hatches = hatches

    def GetFaceHatches(self) -> tuple[object, ...]:
        return self._hatches

    def GetFaceHatchCount(self) -> int:
        return len(self._hatches)


def test_part_sets_the_section_crosshatch_and_the_sheet_reads_it_back() -> None:
    model = _Model()

    class _Adapter:
        currentModel = model

    part._set_section_hatch(_Adapter())
    ext = model.Extension
    assert ext.integers == {
        (spec.PREF_MATERIAL_HATCH_STYLE, 0): spec.AREA_HATCH_STYLE_PATTERN
    }
    assert ext.strings == {
        (spec.PREF_MATERIAL_HATCH_PATTERN, 0): spec.SECTION_HATCH_PATTERN
    }
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert source.index("apply_material(adapter, MATERIAL)") < source.index(
        "_set_section_hatch(adapter)"
    )
    # Null slots are skipped; a real slot must be the ANSI31 material hatch.
    hatch = _Hatch(True, "ANSI31")
    drawing._assert_material_hatch(_Section(model, (None, hatch, None)))
    drawing._assert_material_hatch(_Section(model, (None, None, None)))
    with pytest.raises(RuntimeError, match="face hatch is not the ANSI31"):
        drawing._assert_material_hatch(
            _Section(model, (_Hatch(True, "ANSI33 (Bronze Brass)"),))
        )
    with pytest.raises(RuntimeError, match="face hatch is not the ANSI31"):
        drawing._assert_material_hatch(_Section(model, (_Hatch(False, "ANSI31"),)))
    # A part whose crosshatch was never set (the Brass default) is refused.
    with pytest.raises(RuntimeError, match="clamp part crosshatch"):
        drawing._assert_material_hatch(_Section(_Model(), (hatch,)))


def test_part_refuses_a_crosshatch_that_does_not_read_back() -> None:
    model = _Model()
    model.Extension.SetUserPreferenceString = lambda *_args: False  # type: ignore[method-assign]

    class _Adapter:
        currentModel = model

    with pytest.raises(RuntimeError, match="crosshatch read back"):
        part._set_section_hatch(_Adapter())


def test_end_views_are_third_angle_projections_of_the_front() -> None:
    half_pi = math.pi / 2.0
    assert drawing.FRONT_AXES == {"+Z": math.pi, "+Y": half_pi}
    assert drawing.TOP_AXES == {"+X": -half_pi, "+Z": math.pi}
    assert drawing.BOTTOM_AXES == {"+X": half_pi, "+Z": math.pi}
    # In line with the front: same column, above and below it.
    assert drawing.TOP_CENTER[0] == drawing.RIGHT_CENTER[0] == drawing.BOTTOM_CENTER[0]
    front_half = spec.BLOCK_HEIGHT / 2.0 * drawing._S
    end_half = spec.HEX_AC / 2.0 * drawing._S
    assert drawing.TOP_CENTER[1] - end_half > drawing.RIGHT_CENTER[1] + front_half
    assert drawing.BOTTOM_CENTER[1] + end_half < drawing.RIGHT_CENTER[1] - front_half


def test_thumb_tap_reference_thread_depth_brackets_only_the_thread() -> None:
    definitions = {5: "TAP INTO BORE", 7: "<hw-threaddepth> <hw-tapdrldepth>"}
    wanted = drawing.reference_thread_depth_definitions(definitions)
    assert wanted[7] == "(<hw-threaddepth>) <hw-tapdrldepth>"
    with pytest.raises(RuntimeError):
        drawing.reference_thread_depth_definitions(wanted)


def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    config = _config.parts("mg-magnifying-clamp")
    assert config["material"] == config["material_specification"]
    assert config["finish"]
    assert int(config["quantity"]) == 1
