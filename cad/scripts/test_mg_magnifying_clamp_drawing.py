"""Offline contracts for the magnifying-clamp drawing."""

from __future__ import annotations

import itertools
import math
from fractions import Fraction
from pathlib import Path
from types import SimpleNamespace

import pytest

import build_mg_magnifying_clamp as part
import draw_mg_magnifying_clamp as drawing
import mg_magnifying_clamp_spec as spec
import mg_rod_clamp_joint as joint
import _drawing_dimension_import as dimension_import
import _drawing_dimensions as drawing_dimensions
import _drawing_notes as drawing_notes
from _layout_audit import arrowhead_segments
from _layout_geometry import (
    ARROW_TEXT_CLEARANCE_M,
    AnnotationGeometry,
    Box,
    Segment,
    segment_box_distance,
    segment_box_overlap_length,
)
from _drawing_registry import DRAWINGS_BY_NAME, DRAWING_TEMPLATES


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
    kept = set(drawing.RIGHT_KEEP) | set(drawing.TOP_KEEP) | set(drawing.RIGHT_LOCATION_KEEP) | set(drawing.TOP_LOCATION_KEEP) | set(drawing.BOTTOM_KEEP)
    assert kept == marked
    assert set(drawing.DIMENSION_CALLOUTS) <= kept
    assert spec.DRAWING_PRECISION["HexProfile"]["HexAf"] == 2


def test_drawing_contract_is_split_from_the_assembly_nominals() -> None:
    # The hex and bore stations the assembly imports live in the drawing-FREE
    # geom module, so a print-note edit cannot enter the assembly recipe.
    import mg_magnifying_clamp_geom as geom

    assert geom.HEX_AF == pytest.approx(0.5 * 25.4)
    assert geom.BLOCK_DEPTH == pytest.approx(geom.HEX_AC)
    assert (geom.LEVER_BORE_Y, geom.BLOCK_HEIGHT) == (19.95, 29.50)
    for gone in ("BLOCK_WIDTH", "ROD_BORE_DIA", "ROD_BORE_X"):
        assert not hasattr(geom, gone)
    assembly = Path(part.__file__).with_name("build_mg_magnifier_assembly.py").read_text(
        encoding="utf-8"
    )
    assert "from mg_magnifying_clamp_geom import" in assembly
    assert "from build_mg_magnifying_clamp import" not in assembly


def test_worst_case_walls_and_engagement_hold_the_contract() -> None:
    for name, (nominal, worst) in spec.DERIVED_WALL_BOUNDS.items():
        assert worst >= spec.WALL_TARGET, name
        assert nominal >= worst, name
    assert spec.DERIVED_WALL_BOUNDS["rod-tap drill point to the lever bore"][1] == pytest.approx(
        spec.ROD_TAP_FLOOR_WALL_WORST
    )
    # Finished stock form is separately accepted. Bore and tap axes each
    # have an independent ordinary .XX location from the SAME actual flat.
    import mg_magnifying_clamp_geom as geom

    entry_errors = [
        abs(tap_error - bore_error)
        for tap_error, bore_error in itertools.product((-0.51, 0.51), repeat=2)
    ]
    assert geom.TAP_TO_BORE_ENTRY_Z_MAX == pytest.approx(max(entry_errors))
    assert geom.BORE_FULL_ANGULAR == pytest.approx(15.0 * math.tan(math.radians(0.3)))
    assert spec.FINISHED_NET_WALL_MINIMUMS == {
        "lever bore to outer faces": 2.0,
        "rod-tap thread to outer faces": 2.0,
        "thumb-screw tap thread to outer faces": 2.0,
    }
    assert set(spec.FINISHED_NET_WALL_MINIMUMS).isdisjoint(spec.DERIVED_WALL_BOUNDS)
    assert spec.ROD_TAP_FLOOR_WALL_WORST == pytest.approx(2.092143505152)
    assert spec.THUMB_ENGAGEMENT_WORST >= joint.ENGAGEMENT_MIN
    assert joint.ENGAGEMENT_WORST >= joint.ENGAGEMENT_MIN
    assert spec.TAP_REACH_NEEDED <= spec.PLUG_TAP_USABLE_LENGTH
    assert spec.TAP_STOP_WINDOW > 0.0
    assert spec.THUMB_DRILL_NEAR_CLEAR > 0.0 and spec.THUMB_DRILL_FAR_CLEAR > 0.0
    assert spec.ROD_TAP_SPEC is joint.ROD_TAP_SPEC


def test_vertical_bore_wander_is_spent_in_both_dependent_stacks() -> None:
    import mg_magnifying_clamp_geom as geom
    from _printed_tolerance import printed_band_mm

    band = printed_band_mm(geom.HEIGHT_PLACES)
    radius_max = (geom.LEVER_BORE_DIA + 0.10) / 2.0
    slope = math.tan(math.radians(0.3))
    # Charge the whole accepted transverse envelope even at a central tap;
    # no ideal-hex midpoint or longitudinal stock alignment is assumed.
    wander = 15.0 * slope
    floor = geom.LEVER_BORE_Y - band - radius_max - joint.ROD_TAP_DRILL_DEPTH_MAX - geom.ROD_TAP_DRILL_POINT - wander
    assert floor == pytest.approx(geom.ROD_TAP_FLOOR_WALL_WORST)
    assert geom.BORE_FULL_ANGULAR == pytest.approx(wander)
    assert floor >= geom.WALL_TARGET
    assert geom.LEVER_BORE_Y == 19.95  # approved hook/seat interface, not re-solved
    assert geom.THUMB_ENGAGEMENT_WORST >= joint.ENGAGEMENT_MIN


def test_installed_thumb_full_overlap_includes_actual_male_tip_and_seating() -> None:
    import mg_magnifying_clamp_geom as geom
    from _mcmaster_91882a221 import COLLAR_DIA, SHANK_LEN, TIP_CHAMFER, TIP_FLAT_R
    from _printed_tolerance import printed_band_mm
    from mg_lever_thread_joint import ROD_DIA, ROD_DIA_BAND

    band = printed_band_mm(geom.HEIGHT_PLACES)
    overlaps, collar_gaps = [], []
    # Actual parallel-cylinder sections at all height/diameter/angle corners.
    # Include every extreme seating, even the conservative upper bore cap:
    # this must not rely on a centreline or perfectly bottom-seated rod.
    for height, bore_y, bore_dia, rod_dia, drift, angle, seat in itertools.product(
        (geom.BLOCK_HEIGHT - band, geom.BLOCK_HEIGHT + band),
        (geom.LEVER_BORE_Y - band, geom.LEVER_BORE_Y + band),
        (geom.LEVER_BORE_DIA, geom.LEVER_BORE_DIA + 0.10),
        (ROD_DIA + ROD_DIA_BAND[1], ROD_DIA),
        (-geom.BORE_FULL_ANGULAR, geom.BORE_FULL_ANGULAR),
        (-geom.THUMB_CONTACT_ANGLE_MAX, 0.0, geom.THUMB_CONTACT_ANGLE_MAX),
        (-1.0, 0.0, 1.0),
    ):
        sec, slope = 1.0 / math.cos(angle), abs(math.tan(angle))
        cy, rb, rr = bore_y + drift, bore_dia / 2.0, rod_dia / 2.0
        # Include the worst transverse finite-flat miss, not a centreline
        # contact. Independent bore/tap entrance errors remain present.
        miss = max(geom.THUMB_CONTACT_Z_MAX + rb * sec - rr - TIP_FLAT_R, 0.0)
        chord_loss = rr - math.sqrt(rr**2 - miss**2)
        contact = cy + seat * (rb - rr) * sec + rr * sec + TIP_FLAT_R * slope
        female = (cy + rb * sec + (joint.THREAD_MAJOR / 2.0 + 0.025) * slope, height - geom.EDGE_BREAK)
        male = (contact + TIP_CHAMFER, contact - chord_loss - 2.0 * TIP_FLAT_R * slope + SHANK_LEN * math.cos(angle))
        overlaps.append(min(female[1], male[1]) - max(female[0], male[0]))
        collar_gaps.append(male[1] - height - COLLAR_DIA / 2.0 * abs(math.sin(angle)))
    assert min(overlaps) >= geom.THUMB_ENGAGEMENT_WORST - 1e-9
    assert min(overlaps) >= joint.ENGAGEMENT_MIN
    assert min(collar_gaps) >= geom.THUMB_COLLAR_CLEARANCE_MIN - 1e-9
    assert geom.THUMB_COLLAR_CLEARANCE_MIN > 0.0
    # Pre-fix mutation: an accepted bottom-seated part at the old height loses
    # 1.5D once the REAL male tip chamfer is removed from the full interval.
    contact = geom.LEVER_BORE_Y + band + geom.BORE_FULL_ANGULAR + ROD_DIA - geom.LEVER_BORE_DIA / 2.0
    old_overlap = (28.95 - band - geom.EDGE_BREAK) - (contact + TIP_CHAMFER)
    assert old_overlap < joint.ENGAGEMENT_MIN


def test_feature_owned_acceptance_retains_stock_envelope_wall_and_seat_requirements() -> None:
    notes = spec.DRAWING_NOTES
    assert float(Fraction(spec.STOCK_AF_CALLOUT.split()[0])) * 25.4 == pytest.approx(spec.HEX_AF)
    assert spec.STOCK_AF_CALLOUT == "1/2 HEX STOCK; FLATS AS SUPPLIED"
    assert (spec.HEX_AF - spec.HEX_AF_BAND, spec.HEX_AF + spec.HEX_AF_BAND) == pytest.approx((12.57, 12.83))
    for gone in ("CENTRED", "PLUG TAP", "CHAMFER", "SEAT", "THREAD ENDS"):
        assert gone not in notes
    assert spec.WALL_NOTE.splitlines() == ["2.0 MIN FINISHED NET WALL", "BORE/TAPS/OUTER FACES, FULL DEPTH"]
    assert f"TRANSVERSE ENVELOPE {spec.STOCK_WIDTH_MAX:.2f} MAX" in notes
    assert "OVER FULL HEIGHT" in notes
    assert not hasattr(spec, "TAP_TOOL_NOTE")
    assert not hasattr(spec, "BORE_WALL_NOTE")
    # This is finished acceptance, not an AF/Rule#1 form guarantee.
    assert "WALL" not in notes
    assert spec.LEVER_BORE_CALLOUT.splitlines() == ["DRILL THRU CORNERS", "SLIP ON 1/4 IN LEVER MHA-MG-03", *spec.WALL_NOTE.splitlines()]
    assert "MHA-MG-03" in spec.LEVER_BORE_CALLOUT
    assert spec.SEAT_NOTE.startswith("MHA-MG-04 SHOULDER SEAT")
    assert "NO CHAMFER OR SPOTFACE" in spec.SEAT_NOTE
    assert spec.THUMB_TAP_PROCESS == "TAP INTO BORE; MHA-MG-VN-50"
    assert "AT TAP" in spec.SEAT_NOTE
    assert notes.startswith("AS-SUPPLIED STOCK FORM ACCEPTANCE\n")
    assert spec.HEIGHT_CALLOUT == "CONTROLS TOP-TAP WALL"
    for stale in ("SKEW", "5.2", "Ø5 VERTICAL ROD"):
        assert stale not in notes
    assert "BRASS" not in notes and "C36000" not in notes
    assert "DEBURR" not in notes and "BREAK SHARP" not in notes
    assert "X.XX" not in notes
    assert "LINEAR +/-" not in notes


def _front_drawing_layout(monkeypatch):
    """Use the real named curation, SetPosition and below-text application."""
    view = SimpleNamespace(GetName2=lambda: "front")
    values = {
        "Height": 0.0295, "LeverBoreYDim": 0.01995, "LeverBoreDiaDim": 0.0065,
        "LeverBoreFromZFlat": 0.00635, "ThumbTapFromZFlat": 0.00635,
        "RodTapFromZFlat": 0.00635,
    }

    class Annotation:
        def __init__(self, name, value):
            self.owner, self.entities, self.position = view, (object(), object()), None
            self.dimension = SimpleNamespace(
                Name=name, SystemValue=value,
                Tolerance=SimpleNamespace(
                    Type=0, minimum=0.0, maximum=0.0,
                ),
            )
            self.text = {4: spec.HEIGHT_CALLOUT if name == "Height" else ""}
            self.display = SimpleNamespace(
                GetDimension=lambda: self.dimension,
                GetDimension2=lambda _index: self.dimension,
                SetText=lambda part, text: self.text.__setitem__(part, text),
                GetText=lambda part: self.text.get(part, ""),
                ShowParenthesis=False,
            )

        def GetSpecificAnnotation(self):
            return self.display

        def SetPosition(self, x, y, z):
            self.position = (x, y, z)
            return True

        def GetPosition(self):
            return self.position

        def Select2(self, *_args):
            raise AssertionError("the layout must not delete a native dimension")

    annotations = {name: Annotation(name, value) for name, value in values.items()}
    before = {
        name: (item.dimension, item.dimension.SystemValue, item.dimension.Tolerance,
               item.dimension.Tolerance.Type, item.dimension.Tolerance.minimum,
               item.dimension.Tolerance.maximum, item.display.ShowParenthesis,
               item.owner, item.entities)
        for name, item in annotations.items()
    }

    def read_member(value, member):
        result = getattr(value, member)
        return result() if callable(result) else result

    adapter = SimpleNamespace(
        currentModel=SimpleNamespace(EditRebuild3=lambda: True),
        _attempt=lambda reader, default=None: reader(), _get_attr_or_call=read_member,
    )

    def imported(_adapter, target, features):
        assert _adapter is adapter and target is view
        return [
            (name, annotations[name])
            for feature in features for name in sorted(spec.DRAWING_DIMENSIONS[feature])
        ]

    monkeypatch.setattr(dimension_import, "insert_feature_dimensions", imported)
    monkeypatch.setattr(
        drawing_dimensions._sw_type_info, "early_bound_or_flag",
        lambda value, _interface, *_members: value,
    )
    curated = []
    for keep in (drawing.RIGHT_KEEP, drawing.RIGHT_LOCATION_KEEP):
        curated.extend(drawing.curate_view_dimensions(
            adapter, view, keep=keep, view_label="front",
            dimensions_by_feature=spec.DRAWING_DIMENSIONS,
        ))
    drawing.set_dimension_callouts(adapter, curated, {name: text for name, text in drawing.DIMENSION_CALLOUTS.items() if name in annotations})
    return SimpleNamespace(annotations=annotations, curated=curated, before=before)


def test_front_layout_moves_native_dimensions_and_wraps_only_height_below_text(monkeypatch) -> None:
    state = _front_drawing_layout(monkeypatch)
    assert len(state.curated) == len(state.annotations)
    for name, item in state.annotations.items():
        wanted = (drawing.RIGHT_KEEP | drawing.RIGHT_LOCATION_KEEP)[name]
        assert item.GetPosition() == (*wanted, 0.0)
        assert state.before[name] == (
            item.dimension, item.dimension.SystemValue, item.dimension.Tolerance,
            item.dimension.Tolerance.Type, item.dimension.Tolerance.minimum,
            item.dimension.Tolerance.maximum, item.display.ShowParenthesis,
            item.owner, item.entities,
        )
        assert set(item.text) == {4}
    height = state.annotations["Height"].display.GetText(4)
    assert height.splitlines() == ["CONTROLS TOP-TAP", "WALL"]
    assert height.split() == spec.HEIGHT_CALLOUT.split()
    assert state.annotations["LeverBoreDiaDim"].display.GetText(4) == spec.LEVER_BORE_CALLOUT
    assert state.annotations["LeverBoreFromZFlat"].display.GetText(4) == "BORE AND BOTH\nTAP ENTRY AXES"
    for name in spec.GROUPED_HIDDEN_DIMENSIONS:
        assert state.annotations[name].display.GetText(4) == ""




def test_common_flat_witness_station_clears_the_frozen_native_A_stroke(monkeypatch) -> None:
    state = _front_drawing_layout(monkeypatch)
    # R21's actual A stroke and old flat witness prove the original crossing.
    # The new 3X caption has different ink: only its native settled audit can
    # certify that new text, not a translated old single-value glyph box.
    a_ink = Box(0.0652137, 0.1761622, 0.0710726, 0.1823344)
    original = Segment(0.06595, 0.17245, 0.06595, 0.1862219, "ext-line")
    assert segment_box_overlap_length(original, a_ink) > 0.006
    _x, y, _z = state.annotations["LeverBoreFromZFlat"].GetPosition()
    shortened = Segment(0.06595, 0.17245, 0.06595, y - 0.0017781, "ext-line")
    assert segment_box_distance(shortened, a_ink) >= ARROW_TEXT_CLEARANCE_M

    def arrow_gap(anchor_y):
        arrow = (0.06595, anchor_y - 0.0027781, 0.0003,
                 -1.0, 0.0, 0.0, 0.003556, 0.000762, 0.0, 0.0, 0.0, 1.0)
        return min(segment_box_distance(segment, a_ink) for segment in arrowhead_segments(arrow))

    assert arrow_gap(0.1865) < ARROW_TEXT_CLEARANCE_M
    assert arrow_gap(y) >= ARROW_TEXT_CLEARANCE_M


def test_r27_group_text_moves_clear_of_actual_neighbor_ink_without_raising_witness(monkeypatch) -> None:
    state = _front_drawing_layout(monkeypatch)
    # R27 563f494, a7481abc leaf: actual three-row native boxes, rounded by
    # the audit to 0.1 mm. This predicts text translation, not a native rerender.
    before = (
        Box(0.0423, 0.1792, 0.0577, 0.1828),
        Box(0.0319, 0.1737, 0.0681, 0.1772),
        Box(0.0324, 0.1681, 0.0674, 0.1717),
    )
    section_a = Box(0.0652137, 0.1761622, 0.0710726, 0.1823344)
    diagonal_value = Box(0.0388, 0.1842, 0.0473, 0.1877)
    height_witness = Segment(0.084, 0.17145, 0.035, 0.17145, "ext-line")
    front_edge = Segment(0.06595, 0.17145, 0.06595, 0.08295, "geometry")
    assert before[0].gap(diagonal_value) < 0.00178
    assert before[1].gap(section_a) == 0.0
    assert segment_box_overlap_length(height_witness, before[2]) > 0.032
    assert segment_box_overlap_length(front_edge, before[2]) > 0.003
    x, y, _z = state.annotations["LeverBoreFromZFlat"].GetPosition()
    dx, dy = x - 0.050, y - 0.1755
    assert dy == 0.0  # Preserve R21's already-cleared flat witness/A station.
    moved = tuple(Box(b.xmin + dx, b.ymin + dy, b.xmax + dx, b.ymax + dy) for b in before)
    neighbors = (
        section_a, diagonal_value,
        Box(0.060362, 0.077362, 0.109638, 0.177038),  # actual front outline
        Box(0.1083, 0.1338, 0.1917, 0.1541),  # R27's former four-row callout, not the new five-row extent
        Box(0.0137, 0.1471, 0.0583, 0.1619),  # height value and both function rows
    )
    assert min(box.gap(neighbor) for box in moved for neighbor in neighbors) > 0.004
    assert all(segment_box_distance(line, box) > 0.004 for line in (height_witness, front_edge) for box in moved)
    assert state.annotations["LeverBoreFromZFlat"].display.GetText(4) == "BORE AND BOTH\nTAP ENTRY AXES"


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


class _TapCallout:
    def __init__(self, *, accepts=True, stuck=False, token=True):
        self.definition = "<hw-threaddesc> - <hw-threadclass>" if token else "<hw-threaddesc>"
        self.depth = "<hw-threaddepth> <hw-tapdrldepth>"
        self.accepts, self.stuck = accepts, stuck

    def IsHoleCallout(self):
        return True

    def SetText(self, part, text):
        assert part == 1
        if self.accepts:
            self.definition = text

    def GetText(self, part):
        if part == 5:
            return self.definition
        if part == 7:
            return self.depth
        if part == 1:
            return "4-40 UNC - 2B" if self.stuck else self.definition.replace("<hw-threaddesc>", "4-40 UNC").replace("<hw-threadclass>", "2B")
        return ""


def test_native_tap_class_omission_preserves_live_size_and_depth_variables() -> None:
    display = _TapCallout()
    drawing._omit_tap_thread_class(display, label="thumb or rod tap")
    assert display.GetText(1) == "4-40 UNC"
    assert display.definition == "<hw-threaddesc>"
    assert display.depth == "<hw-threaddepth> <hw-tapdrldepth>"


@pytest.mark.parametrize("options", ({"accepts": False}, {"stuck": True}, {"token": False}))
def test_native_tap_class_omission_rejects_refused_or_stale_callouts(options) -> None:
    with pytest.raises(RuntimeError):
        drawing._omit_tap_thread_class(_TapCallout(**options), label="native tap")


class _AfTolerance:
    def __init__(self):
        self.Type, self.minimum, self.maximum = 4, -0.00013, 0.00013
        self.calls, self.refuse, self.stale = [], False, False

    def SetValues(self, minimum, maximum):
        self.calls.append((minimum, maximum))
        if self.refuse:
            return False
        if not self.stale:
            self.minimum, self.maximum = minimum, maximum
        return True

    def GetMinValue(self):
        return self.minimum

    def GetMaxValue(self):
        return self.maximum


class _AfDisplay:
    def __init__(self, dimension, annotation):
        self.dimension, self.annotation = dimension, annotation
        self.ShowParenthesis, self.places, self.tolerance_places = False, 2, 2
        self.text, self.precision_calls, self.stale_precision = "", [], False
        self.prefix, self.suffix = "", ""

    def GetDimension2(self, configuration):
        assert configuration == 0
        return self.dimension

    def GetAnnotation(self):
        return self.annotation

    def GetPrimaryPrecision2(self):
        return self.places

    def GetPrimaryTolPrecision2(self):
        return self.tolerance_places

    def SetPrecision3(self, primary, dual, tolerance, dual_tolerance):
        self.precision_calls.append((primary, dual, tolerance, dual_tolerance))
        if not self.stale_precision:
            self.tolerance_places = tolerance
        return 0

    def GetText(self, part):
        assert part in (1, 2, 4)
        return {1: self.prefix, 2: self.suffix, 4: self.text}[part]

    def SetText(self, part, text):
        assert part in (1, 2, 4)
        setattr(self, {1: "prefix", 2: "suffix", 4: "text"}[part], text)
        return True


def _af_fixture(monkeypatch):
    import _drawing_tolerances as tolerances

    _install_witness_interfaces(monkeypatch)
    owner = _NativeSketch("actual hex", "HexProfile")
    points = [_WitnessPoint(owner, -0.003666, 0.00635), _WitnessPoint(owner, -0.003666, -0.00635)]
    source_annotation = SimpleNamespace(
        entities=points, types=(11, 11), count=2, dangling=False,
    )
    source_annotation.GetAttachedEntities3 = lambda: source_annotation.entities
    source_annotation.GetAttachedEntityTypes = lambda: source_annotation.types
    source_annotation.GetAttachedEntityCount3 = lambda: source_annotation.count
    source_annotation.IsDangling = lambda: source_annotation.dangling
    tolerance = _AfTolerance()
    source_dimension = SimpleNamespace(
        Tolerance=tolerance, SystemValue=0.0127,
        FullName="HexAf@HexProfile@actual-clamp.Part", native_token="actual AF",
    )
    source_display = _AfDisplay(source_dimension, source_annotation)
    model = SimpleNamespace(FeatureManager=_native_inventory(*points))
    view = SimpleNamespace(ReferencedDocument=model)
    imported_dimension = SimpleNamespace(**vars(source_dimension))
    imported_annotation = SimpleNamespace(Owner=view, OwnerType=0, dangling=False)
    imported_annotation.IsDangling = lambda: imported_annotation.dangling
    imported_display = _AfDisplay(imported_dimension, imported_annotation)
    imported_display.text = spec.STOCK_AF_CALLOUT
    imported_annotation.GetSpecificAnnotation = lambda: imported_display
    records, same_calls = [], []

    def same(left, right):
        same_calls.append((left, right))
        if hasattr(left, "native_token") and hasattr(right, "native_token"):
            return int(left.native_token == right.native_token)
        return _native_same(left, right)

    adapter = SimpleNamespace(currentModel=model, swApp=SimpleNamespace(IsSame=same), _attempt=lambda reader, default=None: reader())

    def named(context, feature, dimension):
        assert context.currentModel is model
        assert (feature, dimension) == ("HexProfile", "HexAf")
        return source_display, source_dimension

    for module in (part, drawing, tolerances):
        monkeypatch.setattr(module, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(part, "_named_dimension", named)
    monkeypatch.setattr(tolerances, "_named_dimension", named)
    monkeypatch.setattr(drawing._telemetry, "info", lambda message, **fields: records.append((message, fields)))
    return SimpleNamespace(
        adapter=adapter, model=model, view=view, points=points,
        source_annotation=source_annotation, source_dimension=source_dimension,
        source_display=source_display, tolerance=tolerance,
        annotation=imported_annotation, dimension=imported_dimension, display=imported_display,
        records=records, same_calls=same_calls,
    )


def test_native_af_authoring_owns_real_limits_precision_and_nonreference_source(monkeypatch):
    state = _af_fixture(monkeypatch)
    state.tolerance.Type = 0
    state.tolerance.minimum = state.tolerance.maximum = 0.0
    state.source_display.ShowParenthesis = True
    state.source_display.tolerance_places = -2
    part._author_stock_af(state.adapter)
    assert state.tolerance.calls == [(-0.00013, 0.00013)]
    assert state.tolerance.Type == 4
    assert state.source_display.precision_calls == [(-1, -1, 2, -1)]
    assert state.source_display.ShowParenthesis is False
    assert ((state.source_dimension.SystemValue + state.tolerance.GetMinValue()) * 1000,
            (state.source_dimension.SystemValue + state.tolerance.GetMaxValue()) * 1000) == pytest.approx((12.57, 12.83))
    assert all(point._oleobj_.calls for point in state.points)


@pytest.mark.parametrize("fault", ("refused", "stale-values", "stale-precision"))
def test_native_af_authoring_refuses_failed_or_nonpersistent_native_writes(monkeypatch, fault):
    state = _af_fixture(monkeypatch)
    state.tolerance.minimum = state.tolerance.maximum = 0.0
    state.tolerance.refuse = fault == "refused"
    state.tolerance.stale = fault == "stale-values"
    state.source_display.stale_precision = fault == "stale-precision"
    state.source_display.tolerance_places = 3
    with pytest.raises(RuntimeError):
        part._author_stock_af(state.adapter)
    assert len(state.tolerance.calls) == 1


@pytest.mark.parametrize("field,value", (
    ("places", 3), ("tolerance_places", -2), ("ShowParenthesis", True),
    ("SystemValue", 0.0128), ("Type", 0), ("minimum", -0.00051),
    ("maximum", 0.00051), ("FullName", "Wrong@HexProfile@actual-clamp.Part"),
))
def test_native_af_readback_refuses_changed_acceptance(monkeypatch, field, value):
    state = _af_fixture(monkeypatch)
    target = state.display if hasattr(state.display, field) else state.dimension if hasattr(state.dimension, field) else state.tolerance
    setattr(target, field, value)
    with pytest.raises(RuntimeError, match="HexAf"):
        part._assert_stock_af(state.display, state.dimension, stage="after-rebuild")
    assert state.records[-1][1]["operation_stage"] == "after-rebuild"


@pytest.mark.parametrize("prefix,suffix", (("(", ")"), ("(", ""), ("", ")")))
@pytest.mark.parametrize("target,stage", (
    ("source", "HexAf.source-authored"),
    ("source", "HexAf.imported"),
    ("import", "HexAf.imported"),
    ("source", "HexAf.after-final-rebuild"),
    ("import", "HexAf.after-final-rebuild"),
))
def test_native_af_rejects_stale_reference_affixes_with_parenthesis_property_false(monkeypatch, prefix, suffix, target, stage):
    state = _af_fixture(monkeypatch)

    def accept():
        if stage == "HexAf.source-authored":
            part._assert_stock_af_source(state.adapter, stage=stage)
        else:
            drawing._assert_stock_af_import(state.adapter, state.view, state.annotation, stage=stage)

    accept()  # The ordinary AF and its existing stock qualifier are allowed.
    display = state.source_display if target == "source" else state.display
    # Exercise the same independent native text parts as set_reference_dimension.
    display.SetText(1, prefix)
    display.SetText(2, suffix)
    assert display.ShowParenthesis is False
    with pytest.raises(RuntimeError, match="native reference affix remained"):
        accept()
    expected_stage = f"{stage}.source" if target == "source" and stage != "HexAf.source-authored" else stage
    assert state.records[-1][1]["operation_stage"] == expected_stage
    assert f"'prefix': {prefix!r}" in state.records[-1][1]["native_measurement"]
    assert f"'suffix': {suffix!r}" in state.records[-1][1]["native_measurement"]


@pytest.mark.parametrize("fault", ("count", "null", "type", "dangling", "alias", "owner", "span", "normal-offset", "capability"))
def test_native_af_source_requires_actual_distinct_opposite_flat_endpoints(monkeypatch, fault):
    state = _af_fixture(monkeypatch)
    if fault == "count":
        state.source_annotation.count = 1
    elif fault == "null":
        state.source_annotation.entities = (None, state.points[1])
    elif fault == "type":
        state.source_annotation.types = (10, 11)
    elif fault == "dangling":
        state.source_annotation.dangling = True
    elif fault == "alias":
        state.points[1].identifiers = state.points[0].identifiers
    elif fault == "owner":
        state.points[0].owner.feature_name = "WrongProfile"
        state.model.FeatureManager = _native_inventory(*state.points)
    elif fault == "span":
        state.points[1].Y -= 0.001
    elif fault == "normal-offset":
        state.points[1].X += 0.001
    else:
        state.points[0]._oleobj_.capabilities[_WitnessDispatch.segment_iid] = True
    with pytest.raises(RuntimeError):
        part._assert_stock_af_source(state.adapter, stage="source-rebuilt")


def test_native_af_import_keeps_supplied_stock_callout_on_actual_source_dimension_and_top_view(monkeypatch):
    state = _af_fixture(monkeypatch)
    monkeypatch.setattr(drawing_dimensions._sw_type_info, "early_bound_or_flag", lambda value, _interface, *_members: value)
    monkeypatch.setattr(drawing_dimensions, "dimension_name", lambda _adapter, annotation: "HexAf")
    drawing.set_dimension_callouts(state.adapter, [state.annotation], {"HexAf": spec.STOCK_AF_CALLOUT})
    drawing._assert_stock_af_import(state.adapter, state.view, state.annotation, stage="after-final-rebuild")
    assert state.display.GetText(4) == "1/2 HEX STOCK; FLATS AS SUPPLIED"
    assert any(left is state.dimension and right is state.source_dimension for left, right in state.same_calls)
    assert any(left is state.annotation.Owner and right is state.view for left, right in state.same_calls)


def test_native_top_af_placement_and_attached_stock_text_preserve_source_acceptance(monkeypatch):
    state = _af_fixture(monkeypatch)
    state.dimension.Name = "HexAf"
    state.display.GetDimension = lambda: state.dimension
    state.view.GetName2 = lambda: "actual top"
    state.annotation.position = None

    def position(x, y, z):
        state.annotation.position = (x, y, z)
        return True

    def read_member(value, member):
        result = getattr(value, member)
        return result() if callable(result) else result

    def imported(adapter, view, features):
        assert adapter is state.adapter and view is state.view
        assert set(features) == {"HexProfile"}
        return [("HexAf", state.annotation)]

    state.annotation.SetPosition = position
    state.adapter._get_attr_or_call = read_member
    before = (state.dimension.SystemValue, state.tolerance.minimum, state.tolerance.maximum,
              state.annotation.Owner, tuple(state.points))
    monkeypatch.setattr(dimension_import, "insert_feature_dimensions", imported)
    monkeypatch.setattr(drawing_dimensions._sw_type_info, "early_bound_or_flag", lambda value, _interface, *_members: value)
    curated = drawing.curate_view_dimensions(
        state.adapter, state.view, keep=drawing.TOP_KEEP, view_label="top",
        dimensions_by_feature=spec.DRAWING_DIMENSIONS,
    )
    drawing.set_dimension_callouts(state.adapter, curated, {"HexAf": spec.STOCK_AF_CALLOUT})
    assert curated == [state.annotation]
    assert state.annotation.position == (0.085, 0.255, 0.0)
    assert state.display.GetText(4) == "1/2 HEX STOCK; FLATS AS SUPPLIED"
    assert before == (state.dimension.SystemValue, state.tolerance.minimum, state.tolerance.maximum,
                      state.annotation.Owner, tuple(state.points))
    assert state.display.GetPrimaryPrecision2() == state.display.GetPrimaryTolPrecision2() == 2
    assert state.display.ShowParenthesis is False


def test_unchanged_envelope_row_keeps_r28_blank_lane_clearance():
    # R28 native text: this exact surviving row was 118.9611 mm wide.
    # This proves only its placement budget, not the new heading/AF/bore ink.
    assert spec.DRAWING_NOTES.splitlines()[1] == "TRANSVERSE ENVELOPE 15.00 MAX OVER FULL HEIGHT"
    x, y = drawing.STOCK_FORM_NOTE_XY
    row = Box(x, y - 0.0090514, x + 0.1189611, y - 0.0090514 + 0.0035)
    template = DRAWING_TEMPLATES[drawing.SPEC.layout]
    assert template.width_m - 0.0127 - row.xmax > 0.015
    assert row.gap(Box(0.222415, 0.120162, 0.277585, 0.219838)) > 0.007
    assert row.gap(Box(0.2602567, 0.1124082, 0.4062721, 0.1159736)) > 0.014


@pytest.mark.parametrize("fault", ("dimension", "view", "owner-type", "dangling", "text", "unknown-self", "source-span"))
def test_native_af_import_refuses_wrong_source_context_or_postrebuild_drift(monkeypatch, fault):
    state = _af_fixture(monkeypatch)
    if fault == "dimension":
        state.dimension.native_token = "wrong AF with same name and size"
    elif fault == "view":
        state.annotation.Owner = SimpleNamespace(ReferencedDocument=state.model)
    elif fault == "owner-type":
        state.annotation.OwnerType = 1
    elif fault == "dangling":
        state.annotation.dangling = True
    elif fault == "text":
        state.display.text = "FLATS AS SUPPLIED"
    elif fault == "unknown-self":
        same = state.adapter.swApp.IsSame
        state.adapter.swApp.IsSame = lambda left, right: 2 if left is right is state.view else same(left, right)
    else:
        state.points[1].Y -= 0.001
    with pytest.raises(RuntimeError):
        drawing._assert_stock_af_import(state.adapter, state.view, state.annotation, stage="after-final-rebuild")


@pytest.mark.parametrize("fault", (None, "activation", "stale-property", "leader", "position"))
def test_global_stock_form_acceptance_is_linked_unleadered_and_sheet_placed(monkeypatch, fault):
    state = SimpleNamespace(active=False, inserted=[], text=spec.DRAWING_NOTES, leaders=0, position=(*drawing.STOCK_FORM_NOTE_XY, 0.0))

    def activate(name):
        assert name == "ActualSheet"
        state.active = fault != "activation"
        return state.active

    def insert(adapter, text, x, y):
        assert state.active and text == drawing_notes.property_link("Manufacturing Notes")
        assert (x, y) == drawing.STOCK_FORM_NOTE_XY
        annotation = SimpleNamespace(GetLeaderCount=lambda: state.leaders, GetPosition=lambda: state.position)
        note = SimpleNamespace(GetAnnotation=lambda: annotation, GetText=lambda: state.text)
        state.inserted.append(note)
        return note

    adapter = SimpleNamespace(currentModel=SimpleNamespace(
        ActivateSheet=activate, GetCurrentSheet=lambda: SimpleNamespace(GetName=lambda: "ActualSheet"),
    ))
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(drawing_notes, "add_note", insert)
    if fault == "stale-property":
        state.text = "OLD STOCK"
    elif fault == "leader":
        state.leaders = 1
    elif fault == "position":
        state.position = (0.305, 0.140, 0.0)
    if fault is not None:
        with pytest.raises(RuntimeError):
            drawing._add_stock_form_note(adapter)
        assert len(state.inserted) == (0 if fault == "activation" else 1)
    else:
        note = drawing._add_stock_form_note(adapter)
        drawing._assert_stock_form_note(note, stage="after-final-rebuild")
        state.text = "TRANSVERSE ENVELOPE 15.00 MAX"  # Lost full-height authority.
        with pytest.raises(RuntimeError):
            drawing._assert_stock_form_note(note, stage="after-final-rebuild")


@pytest.mark.parametrize("interface", ("IEntity", "ISketchPoint", "ISketchSegment"))
@pytest.mark.parametrize("accepts", (True, False))
def test_location_selection_uses_actual_native_entity_and_zero_mark(monkeypatch, interface, accepts) -> None:
    data = SimpleNamespace(Mark=99)
    selected, bindings = [], []
    entity = SimpleNamespace(Select4=lambda append, selection: selected.append((append, selection)) or accepts)
    model = SimpleNamespace(SelectionManager=SimpleNamespace(CreateSelectData=lambda: data))

    def bind(value, requested):
        bindings.append((value, requested))
        return value

    monkeypatch.setattr(part, "_early_bound", bind)
    adapter = SimpleNamespace(currentModel=model)
    if accepts:
        part._native_select(adapter, entity, interface, append=True)
        assert selected == [(True, data)] and data.Mark == 0
        assert any(value is entity and requested == interface for value, requested in bindings)
    else:
        with pytest.raises(RuntimeError, match="cannot select"):
            part._native_select(adapter, entity, interface, append=False)


@pytest.mark.parametrize("mode", ("linked", "unlinked-copy", "refused", "duplicate", "nonconstruction"))
def test_converted_location_geometry_requires_actual_source_identity(monkeypatch, mode) -> None:
    source, same_coordinate_copy = object(), object()
    segments, selected = [], []

    class Converted:
        def __init__(self):
            self.construction = False

        def GetRelations(self):
            target = same_coordinate_copy if mode == "unlinked-copy" else source
            return (SimpleNamespace(GetDefinitionEntities2=lambda: (target,)),)

        @property
        def ConstructionGeometry(self):
            return self.construction

        @ConstructionGeometry.setter
        def ConstructionGeometry(self, value):
            if mode != "nonconstruction":
                self.construction = value

    sketch = SimpleNamespace(GetSketchSegments=lambda: tuple(segments))
    model = SimpleNamespace(GetActiveSketch2=lambda: sketch, ClearSelection2=lambda _all: None)

    def convert(chain, loops):
        assert chain is False and loops is False
        if mode == "refused":
            return False
        segments.extend(Converted() for _ in range(2 if mode == "duplicate" else 1))
        return True

    application = SimpleNamespace(IsSame=lambda left, right: int(left is right))
    adapter = SimpleNamespace(currentModel=model, currentSketchManager=SimpleNamespace(SketchUseEdge3=convert), swApp=application)
    monkeypatch.setattr(part, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(part, "_native_select", lambda _adapter, entity, interface, *, append: selected.append((entity, interface, append)))
    if mode == "linked":
        converted = part._convert_location_source(adapter, source, "IEntity")
        assert converted is segments[0] and converted.ConstructionGeometry
        assert selected == [(source, "IEntity", False)]
    else:
        with pytest.raises(RuntimeError):
            part._convert_location_source(adapter, source, "IEntity")


class _NativeSketch:
    """A sketch has native identity, but deliberately no IFeature.Name member."""

    def __init__(self, token, feature_name):
        self.token = token
        self.feature_name = feature_name


class _NativeFeature:
    def __init__(self, sketch, *, kind="ProfileFeature"):
        self.sketch = sketch
        self.Name = sketch.feature_name
        self.kind = kind

    def GetTypeName2(self):
        return self.kind

    def GetSpecificFeature2(self):
        return self.sketch


def _native_same(left, right):
    if isinstance(left, _NativeSketch) and isinstance(right, _NativeSketch):
        return int(left.token == right.token)
    return int(left is right)


class _WitnessComError(Exception):
    def __init__(self, hresult):
        super().__init__(f"native HRESULT {hresult}")
        self.hresult = hresult


class _WitnessDispatch:
    point_iid = "fixture-point-IID"
    segment_iid = "fixture-segment-IID"

    def __init__(self, interface):
        self.calls = []
        self.capabilities = {
            self.point_iid: interface == "ISketchPoint",
            self.segment_iid: interface == "ISketchSegment",
        }

    def QueryInterface(self, iid, use_iid):
        self.calls.append((iid, use_iid))
        assert use_iid == "fixture-IUnknown"
        outcome = self.capabilities[iid]
        if isinstance(outcome, Exception):
            raise outcome
        if outcome is False:
            raise _WitnessComError(-2147467262)
        if outcome is None:
            return None
        assert outcome is True
        # Capability-only pointer: it deliberately exposes no sketch methods.
        return object()


def _install_witness_interfaces(monkeypatch):
    import sys

    monkeypatch.setitem(sys.modules, "pythoncom", SimpleNamespace(
        IID_IUnknown="fixture-IUnknown", com_error=_WitnessComError,
    ))
    monkeypatch.setitem(sys.modules, "solidworks_mcp.adapters._generated.sldworks_2026", SimpleNamespace(
        ISketchPoint=SimpleNamespace(CLSID=_WitnessDispatch.point_iid),
        ISketchSegment=SimpleNamespace(CLSID=_WitnessDispatch.segment_iid),
    ))


def _native_sketch_segment(*, owner="ActualLocationProfile", kind=0, identifiers=(1, 2)):
    sketch = _NativeSketch(owner, owner)
    return SimpleNamespace(
        _oleobj_=_WitnessDispatch("ISketchSegment"),
        owner_sketch=sketch,
        GetSketch=lambda: sketch,
        GetType=lambda: kind,
        GetID=lambda: identifiers,
    )


def _native_inventory(*segments):
    owners = {}
    for segment in segments:
        sketch = segment.owner_sketch
        owners.setdefault(sketch.token, _NativeFeature(_NativeSketch(sketch.token, sketch.feature_name)))

    def features(top_level_only):
        assert top_level_only is False, "absorbed sketch owners must be inventoried"
        return tuple(reversed(tuple(owners.values())))

    return SimpleNamespace(GetFeatures=features)


@pytest.mark.parametrize("mode", ("measured", "missing", "wrong-distance", "not-driven", "name-refused", "reference-ink", "input-dialog"))
def test_flat_location_is_measured_without_writing_hole_geometry(monkeypatch, mode) -> None:
    selections = []
    _install_witness_interfaces(monkeypatch)
    flat = _native_sketch_segment()
    center = _WitnessPoint(flat.GetSketch(), 0.0, 0.0)
    toggles = {}

    class Dimension:
        state, name = 2, ""
        Tolerance = SimpleNamespace(Type=0)

        @property
        def SystemValue(self):
            return (spec.HEX_AF / 2.0 + (0.2 if mode == "wrong-distance" else 0.0)) / 1000.0

        @SystemValue.setter
        def SystemValue(self, _value):
            raise AssertionError("a measured location must never move geometry")

        @property
        def DrivenState(self):
            return self.state

        @DrivenState.setter
        def DrivenState(self, value):
            if mode != "not-driven":
                self.state = value

        @property
        def Name(self):
            return self.name

        @Name.setter
        def Name(self, value):
            if mode != "name-refused":
                self.name = value

    dimension = Dimension()

    class Display:
        reference = True

        def GetDimension2(self, index):
            assert index == 0
            return dimension

        def GetAnnotation(self):
            return SimpleNamespace(GetAttachedEntities3=lambda: (center, flat), GetAttachedEntityTypes=lambda: (11, 10), IsDangling=lambda: False)

        @property
        def ShowParenthesis(self):
            return self.reference

        @ShowParenthesis.setter
        def ShowParenthesis(self, value):
            if mode != "reference-ink":
                self.reference = value

    display = Display()

    def add_dimension(*_position):
        assert selections == [(center, "ISketchPoint", False), (flat, "ISketchSegment", True)]
        return None if mode == "missing" else display

    manager = SimpleNamespace(
        GetSelectedObjectCount2=lambda _mark: len(selections),
        GetSelectedObject6=lambda index, _mark: selections[index - 1][0],
        GetSelectedObjectType3=lambda index, _mark: (11, 10)[index - 1],
    )
    model = SimpleNamespace(ClearSelection2=lambda _all: selections.clear(), AddDimension2=add_dimension, SelectionManager=manager, FeatureManager=_native_inventory(flat))
    application = SimpleNamespace(
        SetUserPreferenceToggle=lambda preference, value: toggles.__setitem__(preference, value),
        GetUserPreferenceToggle=lambda preference: mode == "input-dialog" or toggles[preference],
        IsSame=_native_same,
    )
    adapter = SimpleNamespace(currentModel=model, swApp=application)
    monkeypatch.setattr(part, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(part, "_native_select", lambda _adapter, entity, interface, *, append: selections.append((entity, interface, append)))
    if mode == "measured":
        part._measure_location(adapter, center, flat, "ActualTapFromFlat")
        assert dimension.DrivenState == 1 and dimension.Name == "ActualTapFromFlat"
        assert display.ShowParenthesis is False
        assert toggles == {10: False, 372: False, 520: False}
    else:
        with pytest.raises(RuntimeError):
            part._measure_location(adapter, center, flat, "ActualTapFromFlat")


@pytest.mark.parametrize("mode", ("actual", "wrong-station", "duplicate"))
def test_location_sources_select_finite_stock_boundaries_and_actual_entry_rims(monkeypatch, mode) -> None:
    a, r, y = spec.HEX_AF / 2.0, spec.HEX_AC / 2.0, spec.BLOCK_HEIGHT
    wanted = ((-r / 2.0, y, a), (r / 2.0, y, a))

    def line(points):
        curve = SimpleNamespace(IsLine=lambda: True, IsCircle=lambda: False)
        vertices = [SimpleNamespace(GetPoint=lambda point=point: tuple(value / 1000.0 for value in point)) for point in points]
        return SimpleNamespace(GetCurve=lambda: curve, GetStartVertex=lambda: vertices[0], GetEndVertex=lambda: vertices[1])

    def circle(station, radius=spec.ROD_TAP_DRILL_DIA / 2.0, axis=(0.0, 1.0, 0.0)):
        curve = SimpleNamespace(IsLine=lambda: False, IsCircle=lambda: True, CircleParams=(0.0, station / 1000.0, 0.0, *axis, radius / 1000.0))
        return SimpleNamespace(GetCurve=lambda: curve)

    actual_edge, actual_rim = line(wanted[::-1]), circle(y)
    # A shortened line has the SAME midpoint; a cosmetic major rim the SAME
    # centre. Neither is the actual finite stock edge / drill-diameter entry.
    edges = [
        line(((-r / 3.0, y, a), (r / 3.0, y, a))),
        line(((-r / 2.0, 0.0, a), (r / 2.0, 0.0, a))),
        circle(0.0), circle(y, radius=joint.THREAD_MAJOR / 2.0),
        circle(y, axis=(1.0, 0.0, 0.0)),
    ]
    if mode != "wrong-station":
        edges.extend((actual_edge, actual_rim))
    if mode == "duplicate":
        edges.extend((line(wanted), circle(y)))
    face = SimpleNamespace(GetEdges=lambda: tuple(edges))
    monkeypatch.setattr(part, "_early_bound", lambda value, _interface: value)
    if mode == "actual":
        assert part._stock_edge(face, wanted) is actual_edge
        assert part._tap_entry_circle(face, y) is actual_rim
    else:
        with pytest.raises(RuntimeError, match="matched"):
            part._stock_edge(face, wanted)
        with pytest.raises(RuntimeError, match="matched"):
            part._tap_entry_circle(face, y)


def test_actual_thumb_drill_cone_clears_both_walls_over_its_finite_length() -> None:
    import mg_magnifying_clamp_geom as geom

    slope, band = math.tan(math.radians(0.3)), 0.51
    bore_r = geom.LEVER_BORE_DIA / 2.0
    drill_r = (geom.ROD_TAP_DRILL_DIA + 0.10) / 2.0
    point = drill_r / math.tan(math.radians(59.0))
    depth = geom.THUMB_TAP_DRILL_DEPTH + band + point
    bore_wander = 15.0 * slope
    # Two independent common-flat .XX locations, then actual angular travel.
    relative_offset = 1.02 + depth * slope + bore_wander

    def clearance(distance):
        actual_radius = drill_r * (1.0 - distance / point)
        return math.sqrt(bore_r**2 - (relative_offset + actual_radius)**2) - 3.0 * band - bore_wander - distance

    endpoints = (clearance(0.0), clearance(point))
    # The chord is concave, and the cone radius is affine: its whole
    # continuous minimum lies at an endpoint. Interior probes catch an
    # implementation accidentally retaining full radius at the point.
    assert all(clearance(point * step / 200.0) >= min(endpoints) - 1e-9 for step in range(201))
    assert spec.THUMB_DRILL_NEAR_CLEAR == pytest.approx(endpoints[0])
    assert spec.THUMB_DRILL_FAR_CYLINDER_CLEAR == pytest.approx(endpoints[0])
    assert spec.THUMB_DRILL_FAR_POINT_CLEAR == pytest.approx(endpoints[1])
    assert spec.THUMB_DRILL_FAR_CLEAR == pytest.approx(min(endpoints))
    assert min(endpoints) > 0.0
    # Mutation control: falsely extending the full drill cylinder through
    # the point loses >0.7 mm and must NOT define the real point clearance.
    cylinder_to_tip = endpoints[0] - point
    assert spec.THUMB_DRILL_FAR_CLEAR > cylinder_to_tip + 0.7


@pytest.mark.parametrize("mode", ("retained", "lost-source", "underdefined", "extra-segment", "wrong-distance", "reference-ink"))
def test_linked_native_locations_are_rechecked_after_equations_and_rebuild(monkeypatch, mode) -> None:
    fixture = _TapProjectionFixture(monkeypatch)
    fixture.install_rebuild(monkeypatch, {})
    if mode == "lost-source":
        fixture.flat.relations.clear()
    elif mode == "underdefined":
        fixture.status = 2
    elif mode == "extra-segment":
        fixture.lines.append(fixture.flat)
    elif mode == "wrong-distance":
        fixture.mode = "wrong-value"
    elif mode == "reference-ink":
        fixture.displays[0].ShowParenthesis = True
    if mode == "retained":
        part._assert_location_profiles(fixture.adapter)
    else:
        with pytest.raises(RuntimeError):
            part._assert_location_profiles(fixture.adapter)


@pytest.mark.parametrize("mode", ("actual", "missing", "two-points", "profile-not-placement", "underdefined", "unknown"))
def test_relative_locations_use_actual_wizard_points(monkeypatch, mode) -> None:
    points = {"ThumbTap": object(), "RodTap": object()}

    def feature(name):
        if mode == "missing":
            return None
        sketch = SimpleNamespace(
            GetSketchPoints2=lambda: (points[name], object()) if mode == "two-points" else (points[name],),
            GetSketchSegments=lambda: (object(),) if mode == "profile-not-placement" else (),
            GetConstrainedStatus=lambda: None if mode == "unknown" else 2 if mode == "underdefined" else 3,
        )
        child = SimpleNamespace(GetTypeName2=lambda: "ProfileFeature", GetSpecificFeature2=lambda: sketch, GetNextSubFeature=lambda: None)
        return SimpleNamespace(GetFirstSubFeature=lambda: child)

    monkeypatch.setattr(part, "_early_bound", lambda value, _interface: value)
    adapter = SimpleNamespace(currentModel=SimpleNamespace(FeatureByName=feature))
    if mode == "actual":
        result = part._tap_placement_points(adapter)
        assert result["ThumbTapFromZFlat"] is points["ThumbTap"]
        assert result["RodTapFromZFlat"] is points["RodTap"]
    else:
        with pytest.raises(RuntimeError):
            part._tap_placement_points(adapter)


class _WitnessTransform:
    def __init__(self, forward, inverse):
        self.forward, self.inverse = forward, inverse

    def Inverse(self):
        return _WitnessTransform(self.inverse, self.forward)


class _WitnessPoint:
    _next_id = 1

    def __init__(self, owner, x, y, z=0.0):
        self.owner, self.X, self.Y, self.Z = owner, x, y, z
        self.relations = []
        self._oleobj_ = _WitnessDispatch("ISketchPoint")
        self.identifiers = _WitnessPoint._next_id, 0
        _WitnessPoint._next_id += 1

    @property
    def owner_sketch(self):
        return self.owner

    def GetID(self):
        return self.identifiers

    def GetSketch(self):
        return self.owner

    def GetRelations(self):
        return tuple(self.relations)


def _point_proxy(point):
    proxy = _WitnessPoint(point.GetSketch(), point.X, point.Y, point.Z)
    proxy.identifiers = point.GetID()
    proxy.relations = point.relations
    return proxy


class _WitnessRelation:
    def __init__(self, entities, kind):
        self.entities, self.kind = tuple(entities), kind
        self.Suppressed = False

    def GetRelationType(self):
        return self.kind

    def GetDefinitionEntities2(self):
        # Native definition order is not part of the relation contract.
        return self.entities[::-1]

    def GetEntities(self):
        return self.entities[::-1]

    def GetEntitiesType(self):
        # These describe the internal entities, not the definition array.
        return tuple(2 if isinstance(entity, _WitnessPoint) else 3 if hasattr(entity, "GetType") and entity.GetType() == 0 else 4 for entity in self.GetEntities())


class _TapProjectionFixture:
    """Native-shaped state, distinct sketch frames, and read-only measured value."""

    def __init__(self, monkeypatch, *, mode="retained"):
        from solidworks_mcp.adapters import com_variant
        import _telemetry
        _install_witness_interfaces(monkeypatch)

        self.mode = mode
        self.events, self.selections, self.lines, self.relations, self.displays = [], [], [], [], []
        self.status = 3
        self.sketch = _NativeSketch("right", "LeverBoreLocationProfile")
        self.sketch.ModelToSketchTransform = _WitnessTransform(
            lambda p: (-p[2], p[1], p[0]), lambda p: (p[2], p[1], -p[0]),
        )
        self.sketch.GetConstrainedStatus = lambda: self.status
        self.sketch.GetSketchSegments = lambda: (self.circle, self.flat, *self.lines)
        source = _NativeSketch("top", "ThumbPlacement")
        source.ModelToSketchTransform = _WitnessTransform(
            lambda p: (p[0], -p[2], p[1] - 0.0295),
            lambda p: (p[0], p[2] + 0.0295, -p[1]),
        )
        self.tap = _WitnessPoint(source, 0.0, 0.0)
        self.center = _WitnessPoint(self.sketch, 0.0, 0.01995)
        self.circle = _native_sketch_segment(owner=self.sketch.feature_name, kind=1)
        self.circle.owner_sketch = self.sketch
        self.circle.GetSketch = lambda: self.sketch
        self.circle.GetCenterPoint2 = lambda: self.center
        self.circle.GetRadius = lambda: 0.00325
        self.source_circle = SimpleNamespace(_oleobj_=_WitnessDispatch("IEdge"))
        self.circle.relations = [_WitnessRelation((self.source_circle,), 32)]
        self.circle.GetRelations = lambda: tuple(self.circle.relations)
        self.flat = _native_sketch_segment(owner=self.sketch.feature_name, kind=0, identifiers=(99, 1))
        self.flat.owner_sketch = self.sketch
        self.flat.GetSketch = lambda: self.sketch
        flat_start, flat_end = _WitnessPoint(self.sketch, -0.00635, 0.0), _WitnessPoint(self.sketch, -0.00635, 0.0295)
        self.flat.GetStartPoint2, self.flat.GetEndPoint2 = lambda: flat_start, lambda: flat_end
        self.flat.ConstructionGeometry = True
        self.source_flat = SimpleNamespace(_oleobj_=_WitnessDispatch("IEdge"))
        self.flat.relations = [_WitnessRelation((self.source_flat,), 32)]
        self.flat.GetRelations = lambda: tuple(self.flat.relations)
        self.manager = SimpleNamespace(AddToDB=False, CreateLine=self.create_line)
        self.sketch.RelationManager = SimpleNamespace(AddRelation=self.add_relation)
        selection = SimpleNamespace(
            GetSelectedObjectCount2=lambda _mark: len(self.selections),
            GetSelectedObjectType3=lambda index, _mark: 11 if isinstance(self.selections[index - 1], _WitnessPoint) else 10,
            GetSelectedObject6=lambda index, _mark: self.selections[index - 1],
        )
        self.model = SimpleNamespace(
            GetActiveSketch2=lambda: None if mode == "no-active-sketch" else self.sketch,
            ClearSelection2=lambda _all: self.selections.clear(),
            SelectionManager=selection,
            FeatureManager=SimpleNamespace(GetFeatures=lambda top: _native_inventory(self.circle, self.tap).GetFeatures(top)),
            AddDimension2=self.dimension,
            GraphicsRedraw2=lambda: None,
            FeatureByName=lambda _name: _NativeFeature(self.sketch),
        )

        def math_point(coordinates):
            return SimpleNamespace(
                ArrayData=tuple(coordinates),
                MultiplyTransform=lambda transform: math_point(transform.forward(tuple(coordinates))),
            )

        self.preferences = {}
        self.adapter = SimpleNamespace(
            currentModel=self.model, currentSketchManager=self.manager,
            swApp=SimpleNamespace(
                IsSame=_native_same, GetMathUtility=lambda: SimpleNamespace(CreatePoint=math_point),
                SetUserPreferenceToggle=lambda key, value: self.preferences.__setitem__(key, value),
                GetUserPreferenceToggle=lambda key: self.preferences[key],
            ),
        )
        monkeypatch.setattr(part, "_early_bound", lambda value, _interface: value)
        monkeypatch.setattr(part, "_native_select", lambda _adapter, entity, _interface, *, append: self.selections.append(entity))
        monkeypatch.setattr(com_variant, "double_array", lambda values: values)
        monkeypatch.setattr(com_variant, "dispatch_array", lambda values: values)
        monkeypatch.setattr(_telemetry, "info", lambda message, **fields: self.events.append((message, fields)))

    def create_line(self, x1, y1, z1, x2, y2, z2):
        assert self.manager.AddToDB is True, "database insertion must suppress inference"
        if self.mode == "missing-line":
            return None
        # AddToDB does not prevent exact-coordinate database point reuse.
        existing = [self.center]
        for old in self.lines:
            existing.extend((old.GetStartPoint2(), old.GetEndPoint2()))

        def point_at(x, y, z):
            for point in existing:
                if (point.X, point.Y, point.Z) == (x, y, z):
                    return point
            point = _WitnessPoint(self.sketch, x, y, z)
            existing.append(point)
            return point

        start, end = point_at(x1, y1, z1), point_at(x2, y2, z2)
        line = _native_sketch_segment(owner=self.sketch.feature_name, identifiers=(len(self.lines) + 2, 1))
        line.owner_sketch = self.sketch
        line.GetSketch = lambda: self.sketch
        line.GetStartPoint2, line.GetEndPoint2 = lambda: start, lambda: end
        line.relations = []
        line.GetRelations = lambda: tuple(line.relations)
        line.ConstructionGeometry = False
        self.lines.append(line)
        return line

    def add_relation(self, entities, kind):
        assert self.manager.AddToDB is False, "restore inference isolation before constraints solve"
        if self.mode == "missing-relation":
            return None
        relation = _WitnessRelation(entities, kind)
        if self.mode == "wrong-definition" and kind == 26:
            relation.entities = (entities[0], _WitnessPoint(self.tap.owner, self.tap.X, self.tap.Y))
        if self.mode == "wrong-relation-kind":
            relation.kind = 17
        if self.mode == "segment-dispatch-proxy" and kind in (4, 9):
            segment = entities[-1]
            proxy = _native_sketch_segment(
                owner=segment.owner_sketch.feature_name,
                kind=segment.GetType(), identifiers=segment.GetID(),
            )
            proxy.owner_sketch = segment.owner_sketch
            proxy.GetSketch = lambda: segment.owner_sketch
            assert _native_same(proxy, segment) == 0
            relation.entities = (*entities[:-1], proxy)
        for entity in entities:
            entity.relations.append(relation)
        self.relations.append(relation)
        # A small stateful model of these four equations, not a native-success
        # claim. Constraints move independent point objects without merging them.
        if self.mode != "unsolved":
            if kind == 4:
                entities[0].GetEndPoint2().Y = entities[0].GetStartPoint2().Y
            elif kind == 26:
                source = entities[1]
                model = source.owner.ModelToSketchTransform.Inverse().forward((source.X, source.Y, source.Z))
                entities[0].X = self.sketch.ModelToSketchTransform.forward(model)[0]
            elif kind == 25:
                end, center = entities
                end.Y = center.Y
                line = next(line for line in self.lines if line.GetEndPoint2() is end)
                line.GetStartPoint2().Y = end.Y
            elif kind == 9:
                end, circle = entities
                center = circle.GetCenterPoint2()
                half_chord = math.sqrt(circle.GetRadius() ** 2 - (end.Y - center.Y) ** 2)
                end.X = center.X + math.copysign(half_chord, end.X - center.X)
        if self.mode == "underdefined":
            self.status = 2
        return relation

    def dimension(self, *position):
        assert len(self.selections) == 2
        measured_point, selected_flat = self.selections
        assert isinstance(measured_point, _WitnessPoint) and selected_flat is self.flat
        assert position == pytest.approx((0.02, 0.02, 0.0))
        if measured_point is not self.center:
            assert measured_point is self.lines[-1].GetStartPoint2()
            assert [relation.kind for relation in self.relations[-4:]] == [4, 26, 25, 9]
        if self.mode == "missing-dimension":
            return None
        state = self

        class MeasuredDimension:
            DrivenState, Name = 2, ""
            Tolerance = SimpleNamespace(Type=0)

            @property
            def FullName(self):
                return f"{self.Name}@LeverBoreLocationProfile@Clamp.Part"

            @property
            def SystemValue(self):
                return abs(measured_point.X - state.flat.GetStartPoint2().X) + (0.0002 if state.mode == "wrong-value" else 0.0)

        attached = list(self.selections)
        if self.mode == "coordinate-copy":
            attached[0] = _WitnessPoint(self.sketch, attached[0].X, attached[0].Y)
        annotation = SimpleNamespace(
            GetAttachedEntities3=lambda: tuple(attached[::-1]),
            GetAttachedEntityTypes=lambda: (10, 11),
            IsDangling=lambda: None if self.mode == "unknown-dangling" else self.mode == "dangling",
        )
        measured = MeasuredDimension()
        display = SimpleNamespace(GetDimension2=lambda _index: measured, GetAnnotation=lambda: annotation, ShowParenthesis=True, GetPrimaryPrecision2=lambda: 2)
        annotation.GetSpecificAnnotation = lambda: display
        annotation.Visible = 1
        self.displays.append(display)
        return display

    def install_rebuild(self, monkeypatch, points):
        part._measure_location(self.adapter, self.center, self.flat, "LeverBoreFromZFlat")
        dimensions = {display.GetDimension2(0).Name: display for display in self.displays}
        monkeypatch.setattr(part, "_location_sources", lambda _adapter: {"LeverBoreLocationProfile": ("Right", self.source_circle, "ISketchSegment", (("LeverBoreFromZFlat", self.source_flat),))})
        monkeypatch.setattr(part, "_tap_placement_points", lambda _adapter: dict(points))
        monkeypatch.setattr(part, "_named_dimension", lambda _adapter, _feature, name: (dimensions[name], dimensions[name].GetDimension2(0)))
        return dimensions


@pytest.mark.parametrize("mode", (
    "retained", "no-active-sketch", "missing-line", "missing-relation", "wrong-definition",
    "segment-dispatch-proxy",
    "wrong-relation-kind", "underdefined", "missing-dimension",
    "wrong-value", "coordinate-copy", "dangling", "unknown-dangling",
))
def test_tap_flat_dimension_uses_actual_source_constrained_projection(monkeypatch, mode) -> None:
    fixture = _TapProjectionFixture(monkeypatch, mode=mode)
    if mode in ("retained", "segment-dispatch-proxy"):
        part._measure_tap_from_flat(fixture.adapter, fixture.tap, fixture.circle, fixture.flat, "ThumbTapFromZFlat")
        dimension = fixture.displays[0].GetDimension2(0)
        assert dimension.Name == "ThumbTapFromZFlat" and dimension.DrivenState == 1
        assert fixture.displays[0].ShowParenthesis is False
        assert dimension.SystemValue == pytest.approx(0.00635)
        assert fixture.relations[1].entities[1] is fixture.tap
        assert fixture.relations[3].entities[1].GetID() == fixture.circle.GetID()
        assert fixture.lines[0].ConstructionGeometry is True
    else:
        with pytest.raises(RuntimeError):
            part._measure_tap_from_flat(fixture.adapter, fixture.tap, fixture.circle, fixture.flat, "ThumbTapFromZFlat")
    assert fixture.manager.AddToDB is False
    if mode in ("retained", "segment-dispatch-proxy", "missing-dimension"):
        constructor = [fields for _message, fields in fixture.events if fields.get("operation_stage") == "ThumbTapFromZFlat.point-flat-constructor"]
        assert len(constructor) == 1
        assert constructor[0]["native_created"] is (mode != "missing-dimension")
        assert constructor[0]["native_method"] == "IModelDoc2.AddDimension2"
        assert constructor[0]["placement_m"] == (0.02, 0.02, 0.0)


def test_witness_source_transform_and_distinct_overlaid_tap_lines(monkeypatch) -> None:
    fixture = _TapProjectionFixture(monkeypatch)
    other = _WitnessPoint(fixture.tap.owner, 0.0, 0.0)
    for name, tap in (("ThumbTapFromZFlat", fixture.tap), ("RodTapFromZFlat", other)):
        part._measure_tap_from_flat(fixture.adapter, tap, fixture.circle, fixture.flat, name)
    first, second = fixture.lines
    assert first.GetID() != second.GetID()
    assert first.GetStartPoint2() is not second.GetStartPoint2()
    assert first.GetEndPoint2() is not second.GetEndPoint2()
    assert first.GetStartPoint2() is not fixture.center
    assert second.GetStartPoint2() is not fixture.center
    seeds = [fields for _message, fields in fixture.events if fields.get("operation_stage", "").endswith(".seed-readback")]
    assert len(seeds) == 2
    for seed in seeds:
        assert seed["provisional_seed_m"] == seed["actual_seed_m"]
        assert seed["actual_seed_m"][0] != first.GetStartPoint2().X
        assert seed["actual_seed_m"][1] != fixture.center.Y
    assert first.GetStartPoint2().X == second.GetStartPoint2().X == 0.0
    fixture.tap.Y = 0.0004  # Top sketch local Y becomes Right sketch X, not Y.
    assert part._point_in_location_sketch(fixture.adapter, fixture.tap, fixture.sketch) == pytest.approx((0.0004, 0.0295, 0.0))
    with pytest.raises(RuntimeError, match="point alignment differs"):
        part._assert_tap_projection(fixture.adapter, first, fixture.tap, fixture.circle, stage="moved-source")


@pytest.mark.parametrize("point_type", (11, 25))
@pytest.mark.parametrize("mode", ("retained", "different-segment-dispatch", "unknown-segment-dispatch", "unknown-segment-self", "one-selected", "missing-object", "wrong-point", "unknown-point", "unknown-point-self", "wrong-selection-type", "wrong-owner", "wrong-kind", "wrong-id", "unknown-owner", "invalid-id"))
def test_selection_diagnostics_discriminate_native_segment_identity(monkeypatch, mode, point_type) -> None:
    import _telemetry

    _install_witness_interfaces(monkeypatch)
    circle = _native_sketch_segment(kind=1)
    point = _WitnessPoint(circle.GetSketch(), 0.0, 0.0)
    selected_point = _WitnessPoint(circle.GetSketch(), 0.0, 0.0) if mode in ("wrong-point", "unknown-point") else point
    returned_circle = _native_sketch_segment(
        owner="OtherProfile" if mode == "wrong-owner" else "ActualLocationProfile",
        kind=0 if mode == "wrong-kind" else 1,
        identifiers=(2, 1) if mode == "wrong-id" else (1,) if mode == "invalid-id" else (1, 2),
    )
    if mode == "unknown-owner":
        returned_circle.GetSketch = lambda: None
    selected = (point,) if mode == "one-selected" else (selected_point, None if mode == "missing-object" else returned_circle)
    selected_types = (point_type, 2 if mode == "wrong-selection-type" else 10)[:len(selected)]
    events = []

    def same(left, right):
        if mode == "unknown-point-self" and left is point and right is point:
            return -1
        if mode == "unknown-segment-self" and left is circle and right is circle:
            return -1
        if mode == "unknown-point" and left is selected_point and right is point:
            return -1
        if left is returned_circle and right is circle:
            return 1 if mode == "retained" else -1 if mode == "unknown-segment-dispatch" else 0
        return _native_same(left, right)

    manager = SimpleNamespace(
        GetSelectedObjectCount2=lambda _mark: len(selected),
        GetSelectedObject6=lambda index, _mark: selected[index - 1],
        GetSelectedObjectType3=lambda index, _mark: selected_types[index - 1],
    )
    adapter = SimpleNamespace(
        currentModel=SimpleNamespace(SelectionManager=manager, FeatureManager=_native_inventory(circle, returned_circle)),
        swApp=SimpleNamespace(IsSame=same),
    )
    monkeypatch.setattr(part, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(_telemetry, "info", lambda message, **fields: events.append((message, fields)))
    accepted = ("retained", "different-segment-dispatch", "unknown-segment-dispatch", "unknown-segment-self")
    if mode in accepted:
        part._require_location_selection(adapter, circle, point=point, stage="native-positive-control")
    else:
        reason = {
            "one-selected": "expected two selected",
            "missing-object": "selected object unavailable",
            "wrong-point": "selected point identity",
            "unknown-point": "selected point identity",
            "unknown-point-self": "point identity positive control",
            "wrong-selection-type": "selection types",
            "wrong-owner": "segment owner/type/ID",
            "wrong-kind": "segment owner/type/ID",
            "wrong-id": "segment owner/type/ID",
            "unknown-owner": "segment identity readback failed",
            "invalid-id": "segment identity readback failed",
        }[mode]
        with pytest.raises(RuntimeError, match=reason):
            part._require_location_selection(adapter, circle, point=point, stage="native-positive-control")
    selection_events = [(message, fields) for message, fields in events if "selection_count" in fields]
    assert len(selection_events) == 1
    message, fields = selection_events[0]
    assert fields["operation_stage"] == "native-positive-control"
    assert fields["selection_count"] == len(selected)
    assert fields["selected_types"] == selected_types
    assert fields["selected_available"] == tuple(entity is not None for entity in selected)
    assert f"count={len(selected)}" in message and "point_keys=" in message
    if mode in accepted:
        assert fields["selected_segment_identity"] == fields["expected_segment_identity"] == repr(("ActualLocationProfile", 1, 1, 2))
        assert fields["selected_and_expected_point_identities"] == repr((("ActualLocationProfile", "ISketchPoint", *point.GetID()),) * 2)


@pytest.mark.parametrize("mode", ("valid", "missing-owner", "empty-owner", "nonstring-owner", "negative-type", "bool-type", "short-id", "float-id", "bool-id"))
def test_native_segment_identity_requires_complete_documented_key(monkeypatch, mode) -> None:
    segment = _native_sketch_segment(
        owner="" if mode == "empty-owner" else None if mode == "nonstring-owner" else "ActualLocationProfile",
        kind=-1 if mode == "negative-type" else True if mode == "bool-type" else 1,
        identifiers=(1,) if mode == "short-id" else (1.0, 2) if mode == "float-id" else (True, 2) if mode == "bool-id" else (1, 2),
    )
    if mode == "missing-owner":
        segment.GetSketch = lambda: None
    monkeypatch.setattr(part, "_early_bound", lambda value, _interface: value)
    adapter = SimpleNamespace(currentModel=SimpleNamespace(FeatureManager=_native_inventory(segment)), swApp=SimpleNamespace(IsSame=_native_same))
    if mode == "valid":
        assert part._segment_identity(adapter, segment, stage="key-control", role="selected") == ("ActualLocationProfile", 1, 1, 2)
    else:
        with pytest.raises(RuntimeError, match="native segment"):
            part._segment_identity(adapter, segment, stage="key-control", role="selected")


@pytest.mark.parametrize("mode", (
    "retained", "wrong-tap", "wrong-circle-id", "missing-constraint", "duplicate-constraint",
    "suppressed-constraint", "unknown-suppression",
    "wrong-branch", "underdefined", "wrong-value", "wrong-band", "nonconstruction",
))
def test_rebuilt_tap_projection_retains_actual_constraints_identity_value_and_default_band(monkeypatch, mode) -> None:
    fixture = _TapProjectionFixture(monkeypatch)
    part._measure_tap_from_flat(fixture.adapter, fixture.tap, fixture.circle, fixture.flat, "ThumbTapFromZFlat")
    fixture.install_rebuild(monkeypatch, {"ThumbTapFromZFlat": fixture.tap})
    line = fixture.lines[0]
    display = fixture.displays[0]
    dimension = display.GetDimension2(0)
    if mode == "wrong-tap":
        fixture.tap = _WitnessPoint(fixture.tap.owner, fixture.tap.X, fixture.tap.Y)
    elif mode == "wrong-circle-id":
        copied = _native_sketch_segment(owner="LeverBoreLocationProfile", kind=1, identifiers=(99, 99))
        copied.owner_sketch = fixture.sketch
        copied.GetSketch = lambda: fixture.sketch
        fixture.relations[3].entities = (line.GetEndPoint2(), copied)
    elif mode == "missing-constraint":
        line.GetStartPoint2().relations.clear()
    elif mode == "duplicate-constraint":
        line.GetEndPoint2().relations.append(fixture.relations[3])
    elif mode in ("suppressed-constraint", "unknown-suppression"):
        fixture.relations[3].Suppressed = True if mode == "suppressed-constraint" else None
    elif mode == "wrong-branch":
        line.GetEndPoint2().X *= -1.0
    elif mode == "underdefined":
        fixture.status = 2
    elif mode == "wrong-value":
        fixture.mode = mode
    elif mode == "wrong-band":
        dimension.Tolerance = SimpleNamespace(Type=2, GetMinValue=lambda: -0.002, GetMaxValue=lambda: 0.002)
    elif mode == "nonconstruction":
        line.ConstructionGeometry = False
    monkeypatch.setattr(part, "_tap_placement_points", lambda _adapter: {"ThumbTapFromZFlat": fixture.tap})
    if mode == "retained":
        part._assert_location_profiles(fixture.adapter)
    else:
        with pytest.raises(RuntimeError):
            part._assert_location_profiles(fixture.adapter)


@pytest.mark.parametrize("mode", (
    "child-owner", "3d-owner", "no-match", "ambiguous", "unknown-match",
    "bool-match", "bad-owner-self", "bad-candidate-self", "null-specific",
    "null-inventory", "null-feature", "bad-feature-type", "matrix-name", "readback-error",
))
def test_segment_owner_is_resolved_only_through_actual_feature_inventory(monkeypatch, mode) -> None:
    import ast
    import _telemetry

    segment = _native_sketch_segment(kind=1)
    owner = segment.GetSketch()
    candidate = _NativeSketch(owner.token, "ActualLocationProfile")
    if mode == "no-match":
        # Same feature name and coincident geometry cannot establish ownership.
        candidate.token = "unrelated-native-sketch"
    feature = _NativeFeature(candidate, kind="3DProfileFeature" if mode == "3d-owner" else "ProfileFeature")
    unrelated = _NativeFeature(_NativeSketch("other", "OtherProfile"))
    parent = _NativeFeature(_NativeSketch("boss", "Boss"), kind="Boss")
    parent.GetSpecificFeature2 = lambda: pytest.fail("non-sketch feature must not be cast to ISketch")
    children = [unrelated, feature]
    if mode == "ambiguous":
        children.append(_NativeFeature(_NativeSketch(owner.token, "SecondClaimedOwner")))
    if mode == "null-specific":
        feature.GetSpecificFeature2 = lambda: None
    if mode == "matrix-name":
        feature.Name = (1.0, 0.0, 0.0, 0.0) * 4  # frozen R7 failure shape
    if mode == "bad-feature-type":
        feature.kind = None
    if mode == "readback-error":
        def fail_specific():
            raise RuntimeError("native specific sketch readback unavailable")
        feature.GetSpecificFeature2 = fail_specific
    calls, events, bindings = [], [], []

    def features(top_level_only):
        calls.append(top_level_only)
        if mode == "null-inventory":
            return None
        if mode == "null-feature":
            return (parent, None)
        # The owner is an absorbed child and deliberately not first.
        return (parent,) if top_level_only else (parent, *children)

    def same(left, right):
        if left is owner and right is owner and mode == "bad-owner-self":
            return -1
        if left is candidate and right is candidate and mode == "bad-candidate-self":
            return 0
        if left is owner and right is candidate:
            if mode == "unknown-match":
                return -1
            if mode == "bool-match":
                return True
        return _native_same(left, right)

    def bind(value, interface):
        bindings.append((value, interface))
        if isinstance(value, _NativeSketch):
            assert interface == "ISketch", "a sketch is not an IFeature dispatch"
        if isinstance(value, _NativeFeature):
            assert interface == "IFeature"
        return value

    adapter = SimpleNamespace(
        currentModel=SimpleNamespace(FeatureManager=SimpleNamespace(GetFeatures=features)),
        swApp=SimpleNamespace(IsSame=same),
    )
    monkeypatch.setattr(part, "_early_bound", bind)
    monkeypatch.setattr(_telemetry, "info", lambda message, **fields: events.append((message, fields)))
    if mode in ("child-owner", "3d-owner"):
        assert part._segment_identity(adapter, segment, stage="owner-control", role="selected") == ("ActualLocationProfile", 1, 1, 2)
        assert calls == [False]
        assert (feature, "IFeature") in bindings
    else:
        reason = {
            "no-match": "no matching sketch feature",
            "ambiguous": "ambiguous sketch features",
            "unknown-match": "comparison unavailable",
            "bool-match": "comparison unavailable",
            "bad-owner-self": "owner identity positive control",
            "bad-candidate-self": "inventory sketch identity positive control",
            "null-specific": "sketch unavailable",
            "null-inventory": "inventory unavailable",
            "null-feature": "inventory contains null",
            "bad-feature-type": "feature type unavailable",
            "matrix-name": "invalid native sketch owner feature name",
            "readback-error": "specific sketch readback unavailable",
        }[mode]
        with pytest.raises(RuntimeError, match=reason):
            part._segment_identity(adapter, segment, stage="owner-control", role="selected")
    assert len(events) == 1
    _message, fields = events[0]
    assert fields["operation_stage"] == "owner-control"
    assert fields["identity_role"] == "selected"
    assert fields["segment_type"] == 1 and fields["segment_ids"] == (1, 2)
    assert fields["owner_self_identity_code"] == (-1 if mode == "bad-owner-self" else 1)
    candidates = ast.literal_eval(fields["owner_candidates"])
    expected_names = [] if mode in ("bad-owner-self", "null-inventory", "null-feature") else ["OtherProfile"]
    if mode not in ("bad-owner-self", "null-inventory", "null-feature", "bad-feature-type"):
        expected_names.append(feature.Name)
    if mode == "ambiguous":
        expected_names.append("SecondClaimedOwner")
    assert [candidate["name"] for candidate in candidates] == expected_names
    if mode in ("child-owner", "3d-owner"):
        assert candidates[-1]["self_code"] == 1
        assert candidates[-1]["owner_match_code"] == 1
        assert fields["owner_matches"] == ("ActualLocationProfile",)
        assert fields["segment_identity_readback_error"] == "None"
    else:
        assert fields["segment_identity_readback_error"] != "None"
    if mode == "ambiguous":
        assert fields["owner_matches"] == ("ActualLocationProfile", "SecondClaimedOwner")
    if mode == "no-match":
        assert fields["owner_matches"] == ()


def test_segment_owner_inventory_is_refreshed_after_rename_and_rebuild(monkeypatch) -> None:
    segment = _native_sketch_segment(kind=1)
    feature = _NativeFeature(segment.GetSketch())
    features = [feature]
    calls = []

    def inventory(top_level_only):
        calls.append(top_level_only)
        return tuple(features)

    adapter = SimpleNamespace(
        currentModel=SimpleNamespace(FeatureManager=SimpleNamespace(GetFeatures=inventory)),
        swApp=SimpleNamespace(IsSame=_native_same),
    )
    monkeypatch.setattr(part, "_early_bound", lambda value, _interface: value)
    assert part._segment_identity(adapter, segment, stage="before-rebuild", role="expected")[0] == "ActualLocationProfile"
    feature.Name = "RenamedProfile"
    assert part._segment_identity(adapter, segment, stage="after-rename", role="expected")[0] == "RenamedProfile"
    features.clear()
    with pytest.raises(RuntimeError, match="no matching sketch feature"):
        part._segment_identity(adapter, segment, stage="after-rebuild", role="expected")
    assert calls == [False, False, False]


@pytest.mark.parametrize("mode", ("retained", "wrong-point", "bad-point-self", "unavailable-readback"))
def test_attachment_failures_report_actual_native_state_before_raising(monkeypatch, mode) -> None:
    fixture = _TapProjectionFixture(monkeypatch)
    part._measure_tap_from_flat(fixture.adapter, fixture.tap, fixture.circle, fixture.flat, "TapFromZFlat")
    display = fixture.displays[0]
    annotation = display.GetAnnotation()
    start = fixture.lines[0].GetStartPoint2()
    if mode == "wrong-point":
        annotation.GetAttachedEntities3 = lambda: (fixture.flat, object())
    elif mode == "unavailable-readback":
        def unavailable():
            raise RuntimeError("native attachment readback unavailable")
        annotation.GetAttachedEntities3 = unavailable
    elif mode == "bad-point-self":
        fixture.adapter.swApp.IsSame = lambda left, right: -1 if left is start and right is start else _native_same(left, right)
    if mode == "retained":
        part._assert_tap_flat_attachment(fixture.adapter, display, fixture.tap, fixture.circle, fixture.flat, name="TapFromZFlat", stage="after-rebuild")
    else:
        with pytest.raises(RuntimeError):
            part._assert_tap_flat_attachment(fixture.adapter, display, fixture.tap, fixture.circle, fixture.flat, name="TapFromZFlat", stage="after-rebuild")
    _message, fields = next(event for event in reversed(fixture.events) if "attachment_readback_error" in event[1])
    assert fields["operation_stage"] == "after-rebuild"
    assert (fields["attachment_readback_error"] == "None") is (mode == "retained")
    if mode != "unavailable-readback":
        assert fields["attachment_count"] == 2
        assert fields["attached_types"] == (10, 11)


@pytest.mark.parametrize("types", (
    (0, 10), (1, 10), (3, 10), (6, 10), (9, 10), (10, 10), (24, 10),
    (-1, 10), (11, 24), (25, 24), (11, 25), (25, 25), (10, 11),
))
def test_location_selection_rejects_other_entity_kinds_even_when_identity_matches(monkeypatch, types) -> None:
    point, circle = object(), _native_sketch_segment(kind=1)
    selected = (point, circle)
    manager = SimpleNamespace(
        GetSelectedObjectCount2=lambda _mark: 2,
        GetSelectedObject6=lambda index, _mark: selected[index - 1],
        GetSelectedObjectType3=lambda index, _mark: types[index - 1],
    )
    adapter = SimpleNamespace(
        currentModel=SimpleNamespace(SelectionManager=manager, FeatureManager=_native_inventory(circle)),
        swApp=SimpleNamespace(IsSame=_native_same),
    )
    monkeypatch.setattr(part, "_early_bound", lambda value, _interface: value)
    with pytest.raises(RuntimeError, match="selection types"):
        part._require_location_selection(adapter, circle, point=point, stage="wrong-native-kinds")


@pytest.mark.parametrize("types", (
    (), (25,), (11, 11, 11), (0, 11), (3, 11), (6, 11), (9, 11),
    (24, 11), (-1, 11), (11, 24), (25, 24), (11, 11), (10, 10),
))
def test_attachment_types_require_exactly_one_native_point_and_flat(monkeypatch, types) -> None:
    fixture = _TapProjectionFixture(monkeypatch)
    part._measure_tap_from_flat(fixture.adapter, fixture.tap, fixture.circle, fixture.flat, "TapFromZFlat")
    display = fixture.displays[0]
    display.GetAnnotation().GetAttachedEntityTypes = lambda: types
    with pytest.raises(RuntimeError, match="invalid native point/flat attachment"):
        part._assert_tap_flat_attachment(fixture.adapter, display, fixture.tap, fixture.circle, fixture.flat, name="TapFromZFlat", stage="wrong-native-kinds")


@pytest.mark.parametrize("mode", (
    "unknown-point-self", "unknown-segment-self", "bool-segment-self",
    "null-definition", "extra-definition", "unknown-kind", "wrong-owner",
    "nonfinite-center", "nonfinite-endpoint", "unknown-status",
))
def test_native_witness_constraints_fail_closed_on_unavailable_identity_or_geometry(monkeypatch, mode) -> None:
    fixture = _TapProjectionFixture(monkeypatch)
    part._measure_tap_from_flat(fixture.adapter, fixture.tap, fixture.circle, fixture.flat, "TapFromZFlat")
    line = fixture.lines[0]
    if mode in ("unknown-point-self", "unknown-segment-self", "bool-segment-self"):
        target = fixture.tap if mode == "unknown-point-self" else fixture.circle
        result = True if mode == "bool-segment-self" else -1
        fixture.adapter.swApp.IsSame = lambda left, right: result if left is target and right is target else _native_same(left, right)
    elif mode == "null-definition":
        fixture.relations[3].entities = (line.GetEndPoint2(), None)
    elif mode == "extra-definition":
        fixture.relations[3].entities += (fixture.center,)
    elif mode == "unknown-kind":
        fixture.relations[3].kind = None
    elif mode == "wrong-owner":
        line.GetStartPoint2().owner = _NativeSketch("other", "Other")
    elif mode == "nonfinite-center":
        fixture.center.Y = float("nan")
    elif mode == "nonfinite-endpoint":
        line.GetEndPoint2().X = float("nan")
    elif mode == "unknown-status":
        fixture.status = None
    with pytest.raises(RuntimeError):
        part._assert_tap_projection(fixture.adapter, line, fixture.tap, fixture.circle, stage="native-unavailable")


def test_distinct_tap_names_cannot_share_one_attached_measurement_line(monkeypatch) -> None:
    fixture = _TapProjectionFixture(monkeypatch)
    for name in ("ThumbTapFromZFlat", "RodTapFromZFlat"):
        part._measure_tap_from_flat(fixture.adapter, fixture.tap, fixture.circle, fixture.flat, name)
    dimensions = fixture.install_rebuild(monkeypatch, {"ThumbTapFromZFlat": fixture.tap, "RodTapFromZFlat": fixture.tap})
    dimensions["RodTapFromZFlat"] = dimensions["ThumbTapFromZFlat"]
    with pytest.raises(RuntimeError, match="distinct tap witnesses merged"):
        part._assert_location_profiles(fixture.adapter)


def test_wrong_active_sketch_is_rejected_before_constructing_witness(monkeypatch) -> None:
    fixture = _TapProjectionFixture(monkeypatch)
    fixture.model.GetActiveSketch2 = lambda: _NativeSketch("wrong-active", "Other")
    with pytest.raises(RuntimeError, match="not owned by the active sketch"):
        part._create_tap_projection(fixture.adapter, fixture.tap, fixture.circle, "TapFromZFlat")
    assert fixture.lines == []
    assert fixture.events[-1][1]["operation_stage"] == "TapFromZFlat.active-sketch"




@pytest.mark.parametrize("count, missing, expected_types", (
    (0, False, ()),
    (1, False, (11,)),
    (3, False, (11, 10, 2)),
    (None, False, ()),
    (2, True, (11, 10)),
))
def test_point_flat_selection_logs_actual_count_and_null_handles_before_refusal(monkeypatch, count, missing, expected_types) -> None:
    fixture = _TapProjectionFixture(monkeypatch)
    manager = fixture.model.SelectionManager
    reads = []

    def actual_count(mark):
        reads.append(mark)
        return count

    def same(left, right):
        assert left is not None and right is not None, "never call native IsSame on an absent selection"
        return _native_same(left, right)

    manager.GetSelectedObjectCount2 = actual_count
    extra = object()
    manager.GetSelectedObjectType3 = lambda index, _mark: (11, 10, 2)[index - 1]
    manager.GetSelectedObject6 = lambda index, _mark: None if missing and index == 1 else (*fixture.selections, extra)[index - 1]
    fixture.adapter.swApp.IsSame = same
    with pytest.raises(RuntimeError, match=f"count={count!r}"):
        part._measure_tap_from_flat(fixture.adapter, fixture.tap, fixture.circle, fixture.flat, "TapFromZFlat")
    assert reads == [-1]
    message, fields = fixture.events[-1]
    assert fields["operation_stage"] == "TapFromZFlat.point-flat.before-create"
    assert fields["selection_count"] == count
    assert fields["selected_types"] == expected_types
    assert fields["selected_and_expected_point_identities"] == "()"
    assert fields["selected_segment_identity"] == "None"
    assert f"count={count!r}" in message
    if missing:
        assert fields["selected_available"] == (False, True)
    assert fixture.displays == []


def test_selection_readback_exception_keeps_stage_and_count_evidence(monkeypatch) -> None:
    fixture = _TapProjectionFixture(monkeypatch)

    def unavailable(_index, _mark):
        raise RuntimeError("native selected handle unavailable")

    fixture.model.SelectionManager.GetSelectedObject6 = unavailable
    with pytest.raises(RuntimeError, match="native selected handle unavailable"):
        part._measure_tap_from_flat(fixture.adapter, fixture.tap, fixture.circle, fixture.flat, "TapFromZFlat")
    fields = fixture.events[-1][1]
    assert fields["operation_stage"] == "TapFromZFlat.point-flat.before-create"
    assert fields["selection_count"] == 2
    assert fields["selected_types"] == (11,)
    assert "native selected handle unavailable" in fields["selection_identity_readback_error"]
    assert fixture.displays == []


@pytest.mark.parametrize("actual_kind", (5, 17, 32, 0, 999, None, True))
def test_relation_kind_mismatch_records_actual_definitions_without_kind_alias(monkeypatch, actual_kind) -> None:
    import ast

    fixture = _TapProjectionFixture(monkeypatch)
    line = part._create_tap_projection(fixture.adapter, fixture.tap, fixture.circle, "TapFromZFlat")
    relation = fixture.relations[1]
    relation.kind = actual_kind  # Matching definition identities never authorize a kind alias.
    with pytest.raises(RuntimeError, match="actual kinds="):
        part._require_witness_relation(
            fixture.adapter, (relation,), 26, (line.GetStartPoint2(), fixture.tap),
            stage="owner-kind-mismatch",
        )
    message, fields = fixture.events[-1]
    assert fields["relation_kind"] == 26
    assert fields["actual_relation_kinds"] == (actual_kind,)
    assert fields["relation_matches"] == 0
    row, = ast.literal_eval(fields["relation_definitions"])
    assert row["kind"] == actual_kind and row["count"] == 2
    assert row["definition_interfaces"] == ["ISketchPoint", "ISketchPoint"]
    assert all(len(entity["id"]) == 2 for entity in row["definition_fields"])
    assert all(len(entity["coordinates"]) == 3 for entity in row["definition_fields"])
    assert row["identity_matches"] is False
    assert row["alignment"] is None and row["point_keys"] == ()
    assert "requested_kind=26" in message and "actual_kinds=" in message


def test_all_owner_relation_kinds_are_captured_before_any_rejection(monkeypatch) -> None:
    import ast

    fixture = _TapProjectionFixture(monkeypatch)
    line = part._create_tap_projection(fixture.adapter, fixture.tap, fixture.circle, "TapFromZFlat")
    first = _WitnessRelation((line.GetStartPoint2(), fixture.tap), 5)
    second = _WitnessRelation((line.GetStartPoint2(), None), 26)
    with pytest.raises(RuntimeError):
        part._require_witness_relation(fixture.adapter, (first, second), 26, (line.GetStartPoint2(), fixture.tap), stage="all-kinds")
    fields = fixture.events[-1][1]
    assert fields["actual_relation_kinds"] == (5, 26)
    rows = ast.literal_eval(fields["relation_definitions"])
    assert len(rows) == 2
    assert rows[0]["identity_matches"] is False and rows[0]["alignment"] is None
    assert rows[1]["definition_fields"][0]["present"] is False


def test_definition_interfaces_are_classified_before_native_cross_class_equality(monkeypatch) -> None:
    fixture = _TapProjectionFixture(monkeypatch, mode="segment-dispatch-proxy")
    checked = []

    def same(left, right):
        if isinstance(left, _WitnessPoint) != isinstance(right, _WitnessPoint):
            pytest.fail("native point-versus-segment IsSame must never be attempted")
        checked.append((left, right))
        return _native_same(left, right)

    fixture.adapter.swApp.IsSame = same
    part._create_tap_projection(fixture.adapter, fixture.tap, fixture.circle, "TapFromZFlat")
    assert checked
    assert any(left is fixture.tap and right is fixture.tap for left, right in checked)


def test_internal_entity_type_array_is_not_applied_to_actual_definition_array(monkeypatch) -> None:
    import ast

    fixture = _TapProjectionFixture(monkeypatch)
    line = part._create_tap_projection(fixture.adapter, fixture.tap, fixture.circle, "TapFromZFlat")
    relation = fixture.relations[1]
    relation.GetEntities = lambda: (fixture.circle,)
    relation.GetEntitiesType = lambda: (4,)  # A solver-created arc, not either defining point.
    part._require_witness_relation(fixture.adapter, (relation,), 26, (line.GetStartPoint2(), fixture.tap), stage="separate-arrays")
    row, = ast.literal_eval(fixture.events[-1][1]["relation_definitions"])
    assert row["internal_count"] == 1 and row["internal_entity_types"] == (4,)
    assert row["definition_interfaces"] == ["ISketchPoint", "ISketchPoint"]
    assert row["identity_matches"] is True


@pytest.mark.parametrize("mode", (
    "neither-interface", "both-interfaces", "point-qi-unavailable",
    "segment-qi-unavailable", "non-com-failure", "null-pointer",
    "unavailable-definitions",
))
def test_unknown_definition_capability_is_logged_and_never_cast_or_accepted(monkeypatch, mode) -> None:
    import ast

    fixture = _TapProjectionFixture(monkeypatch)
    line = part._create_tap_projection(fixture.adapter, fixture.tap, fixture.circle, "TapFromZFlat")
    relation = fixture.relations[1]
    dispatch = fixture.tap._oleobj_
    dispatch.calls.clear()
    if mode == "neither-interface":
        dispatch.capabilities[dispatch.point_iid] = False
    elif mode == "both-interfaces":
        dispatch.capabilities[dispatch.segment_iid] = True
    elif mode == "point-qi-unavailable":
        dispatch.capabilities[dispatch.point_iid] = _WitnessComError(-2147352565)
    elif mode == "segment-qi-unavailable":
        dispatch.capabilities[dispatch.segment_iid] = _WitnessComError(-2147467259)
    elif mode == "non-com-failure":
        dispatch.capabilities[dispatch.point_iid] = RuntimeError("disconnected native dispatch")
    elif mode == "null-pointer":
        dispatch.capabilities[dispatch.point_iid] = None
    else:
        def unavailable():
            raise RuntimeError("native definitions unavailable")
        relation.GetDefinitionEntities2 = unavailable

    original_bind = part._early_bound

    def bind(entity, interface):
        if entity is fixture.tap and mode != "unavailable-definitions":
            pytest.fail("unclassified native definition must never be speculatively bound")
        return original_bind(entity, interface)

    monkeypatch.setattr(part, "_early_bound", bind)
    with pytest.raises(RuntimeError):
        part._require_witness_relation(fixture.adapter, (relation,), 26, (line.GetStartPoint2(), fixture.tap), stage="capability-unavailable")
    fields = fixture.events[-1][1]
    assert fields["actual_relation_kinds"] == (26,)
    row, = ast.literal_eval(fields["relation_definitions"])
    assert row["identity_matches"] is False
    assert row["readback_errors"]
    assert row["mandatory_readback_errors"]
    if mode == "unavailable-definitions":
        assert dispatch.calls == [
            (dispatch.point_iid, "fixture-IUnknown"),
            (dispatch.segment_iid, "fixture-IUnknown"),
        ]  # Expected source still needs its own positive capability control.
    else:
        assert dispatch.calls == [
            (dispatch.point_iid, "fixture-IUnknown"),
            (dispatch.segment_iid, "fixture-IUnknown"),
        ] * 2  # Actual definition and retained source are independently classified.
        definition = row["definition_fields"][0]  # Fixture returns definitions reversed.
        assert definition["interface"] is None
        queries = definition["query_interfaces"]
        assert [query["iid"] for query in queries] == [dispatch.point_iid, dispatch.segment_iid]
        if mode == "neither-interface":
            assert [query["supported"] for query in queries] == [False, False]
            assert [query["hresult"] for query in queries] == [-2147467262, -2147467262]
        elif mode == "both-interfaces":
            assert [query["supported"] for query in queries] == [True, True]
            assert [query["hresult"] for query in queries] == [0, 0]
        elif mode == "point-qi-unavailable":
            assert [query["supported"] for query in queries] == [None, False]
            assert [query["hresult"] for query in queries] == [-2147352565, -2147467262]
        elif mode == "segment-qi-unavailable":
            assert [query["supported"] for query in queries] == [True, None]
            assert [query["hresult"] for query in queries] == [0, -2147467259]
        else:
            assert [query["supported"] for query in queries] == [None, False]
            assert [query["hresult"] for query in queries] == [None, -2147467262]


def test_horizontal_definition_uses_native_qi_without_dispatch_type_metadata(monkeypatch) -> None:
    import ast

    fixture = _TapProjectionFixture(monkeypatch, mode="segment-dispatch-proxy")
    line = part._create_tap_projection(fixture.adapter, fixture.tap, fixture.circle, "TapFromZFlat")
    relation = fixture.relations[0]
    actual, = relation.GetDefinitionEntities2()
    assert actual is not line
    assert fixture.adapter.swApp.IsSame(actual, line) == 0
    actual._oleobj_.calls.clear()
    part._require_witness_relation(fixture.adapter, (relation,), 4, (), line, stage="horizontal-positive-control")
    assert actual._oleobj_.calls == [
        (_WitnessDispatch.point_iid, "fixture-IUnknown"),
        (_WitnessDispatch.segment_iid, "fixture-IUnknown"),
    ]
    fields = fixture.events[-1][1]
    assert fields["actual_relation_kinds"] == (4,)
    row, = ast.literal_eval(fields["relation_definitions"])
    assert row["identity_matches"] is True
    assert row["segment_key"] == ("LeverBoreLocationProfile", 0, 2, 1)
    assert row["mandatory_readback_errors"] == []
    definition, = row["definition_fields"]
    assert definition["interface"] == "ISketchSegment"
    assert [query["hresult"] for query in definition["query_interfaces"]] == [-2147467262, 0]
    assert [query["supported"] for query in definition["query_interfaces"]] == [False, True]


@pytest.mark.parametrize("unavailable_field", ("GetEntities", "GetEntitiesType"))
def test_optional_internal_metadata_failure_does_not_invalidate_native_horizontal_control(monkeypatch, unavailable_field) -> None:
    import ast

    fixture = _TapProjectionFixture(monkeypatch)
    line = part._create_tap_projection(fixture.adapter, fixture.tap, fixture.circle, "TapFromZFlat")
    relation = fixture.relations[0]

    def unavailable():
        raise RuntimeError("optional internal metadata unavailable")

    setattr(relation, unavailable_field, unavailable)
    part._require_witness_relation(fixture.adapter, (relation,), 4, (), line, stage="horizontal-control")
    fields = fixture.events[-1][1]
    assert fields["relation_matches"] == 1
    row, = ast.literal_eval(fields["relation_definitions"])
    assert row["readback_errors"]
    assert row["mandatory_readback_errors"] == []
    assert row["identity_matches"] is True
    assert row["segment_key"] == ("LeverBoreLocationProfile", 0, 2, 1)


def test_point_id_failure_refuses_relation_despite_matching_dispatch_and_alignment(monkeypatch) -> None:
    import ast

    fixture = _TapProjectionFixture(monkeypatch)
    line = part._create_tap_projection(fixture.adapter, fixture.tap, fixture.circle, "TapFromZFlat")

    def unavailable():
        raise RuntimeError("authoritative point ID unavailable")

    fixture.tap.GetID = unavailable
    with pytest.raises(RuntimeError, match="authoritative point ID unavailable"):
        part._require_witness_relation(fixture.adapter, (fixture.relations[1],), 26, (line.GetStartPoint2(), fixture.tap), stage="point-id-unavailable")
    fields = fixture.events[-1][1]
    assert fields["relation_matches"] == 0
    row, = ast.literal_eval(fields["relation_definitions"])
    assert row["mandatory_readback_errors"]
    assert row["identity_matches"] is False


@pytest.mark.parametrize("mode", ("null-handle", "binding-failure", "missing-members"))
def test_bad_relation_handle_does_not_hide_later_actual_kinds(monkeypatch, mode) -> None:
    import ast

    fixture = _TapProjectionFixture(monkeypatch)
    line = part._create_tap_projection(fixture.adapter, fixture.tap, fixture.circle, "TapFromZFlat")
    bad = None if mode == "null-handle" else object()
    later = _WitnessRelation((line.GetStartPoint2(), fixture.tap), 5)

    def bind(value, _interface):
        if value is bad and mode == "binding-failure":
            raise RuntimeError("native relation binding unavailable")
        return value

    monkeypatch.setattr(part, "_early_bound", bind)
    with pytest.raises(RuntimeError, match="actual kinds="):
        part._require_witness_relation(fixture.adapter, (bad, later), 26, (line.GetStartPoint2(), fixture.tap), stage="bad-handle-first")
    fields = fixture.events[-1][1]
    assert fields["actual_relation_kinds"] == (None, 5)
    first, second = ast.literal_eval(fields["relation_definitions"])
    assert first["readback_errors"] and first["mandatory_readback_errors"]
    assert {"kind", "definitions", "suppressed", "internal_types", "internal_entities"} <= set(first["unavailable_fields"])
    assert first["definitions_available"] is False
    assert second["kind"] == 5 and second["count"] == 2
    assert second["definition_interfaces"] == ["ISketchPoint", "ISketchPoint"]
    assert {tuple(entity["id"]) for entity in second["definition_fields"]} == {fixture.tap.GetID(), line.GetStartPoint2().GetID()}
    assert all([query["supported"] for query in entity["query_interfaces"]] == [True, False] for entity in second["definition_fields"])
    assert second["readback_errors"] == [] and second["mandatory_readback_errors"] == []
    assert second["definitions_available"] is True
    assert second["identity_matches"] is False and second["alignment"] is None


@pytest.mark.parametrize("effect", (
    "correct", "none", "wrong-kind", "wrong-definition", "suppressed",
    "unaligned", "wrong-interface", "duplicate",
))
def test_constraint_effect_comes_from_owner_inventory_not_useedge_return(monkeypatch, effect) -> None:
    import ast

    fixture = _TapProjectionFixture(monkeypatch)
    original_add = fixture.sketch.RelationManager.AddRelation
    calls = []
    # Match R12's returned USEEDGE definition classes and internal types,
    # independently of whatever mutation actually happened on the endpoint.
    reported = _WitnessRelation((fixture.circle, fixture.source_circle), 32)
    reported.GetEntitiesType = lambda: (3, 3)

    def add(entities, kind):
        calls.append(kind)
        if kind != 26:
            return original_add(entities, kind)
        if effect == "none":
            return reported
        actual = original_add(entities, kind)
        if effect == "wrong-kind":
            actual.kind = 32
        elif effect == "wrong-definition":
            actual.entities = (entities[0], _WitnessPoint(fixture.tap.owner, fixture.tap.X, fixture.tap.Y))
        elif effect == "suppressed":
            actual.Suppressed = True
        elif effect == "unaligned":
            # Top Y maps to model -Z, then Right X: this breaks VERTPOINTS.
            # Top X maps to Right Z and does not change transverse alignment.
            before = part._point_in_location_sketch(fixture.adapter, fixture.tap, fixture.sketch)
            fixture.tap.Y += 0.001
            after = part._point_in_location_sketch(fixture.adapter, fixture.tap, fixture.sketch)
            assert after[0] - before[0] == pytest.approx(0.001)
            assert after[1:] == pytest.approx(before[1:])
        elif effect == "wrong-interface":
            actual.entities = (entities[0], fixture.circle)
        elif effect == "duplicate":
            duplicate = _WitnessRelation(entities, kind)
            for entity in entities:
                entity.relations.append(duplicate)
        return reported

    fixture.sketch.RelationManager.AddRelation = add
    if effect == "correct":
        part._measure_tap_from_flat(fixture.adapter, fixture.tap, fixture.circle, fixture.flat, "ThumbTapFromZFlat")
        assert calls == [4, 26, 25, 9]
        assert len(fixture.displays) == 1
    else:
        with pytest.raises(RuntimeError):
            part._measure_tap_from_flat(fixture.adapter, fixture.tap, fixture.circle, fixture.flat, "ThumbTapFromZFlat")
        assert calls == [4, 26]
        assert fixture.displays == []
    returned, = [
        fields for _message, fields in fixture.events
        if fields.get("operation_stage") == "ThumbTapFromZFlat.add-relation" and fields.get("relation_kind") == 26
    ]
    assert returned["returned_relation_kinds"] == (32,)
    returned_row, = ast.literal_eval(returned["returned_relation_definitions"])
    assert returned_row["count"] == 2
    assert returned_row["definition_interfaces"] == [None, "ISketchSegment"]
    assert returned_row["internal_entity_types"] == (3, 3)
    assert returned_row["identity_matches"] is False
    before, = [
        fields for _message, fields in fixture.events
        if fields.get("operation_stage") == "ThumbTapFromZFlat.before-constraint" and fields.get("relation_kind") == 26
    ]
    assert before["actual_relation_kinds"] == ()
    after, = [
        fields for _message, fields in fixture.events
        if fields.get("operation_stage") == "ThumbTapFromZFlat.created-constraint" and fields.get("relation_kind") == 26
    ]
    if effect == "correct":
        assert after["actual_relation_kinds"] == (26,)
        assert after["relation_matches"] == 1
        actual_row, = ast.literal_eval(after["relation_definitions"])
        assert actual_row["identity_matches"] is True
        assert actual_row["alignment"]["aligned"] is True
        assert actual_row["definition_interfaces"] == ["ISketchPoint", "ISketchPoint"]
    else:
        assert after["relation_readback_error"] != "None"
        assert after["relation_matches"] == (2 if effect == "duplicate" else 0)
        if effect == "none":
            assert after["actual_relation_kinds"] == ()
        elif effect == "wrong-kind":
            assert after["actual_relation_kinds"] == (32,)
        elif effect == "unaligned":
            actual_row, = ast.literal_eval(after["relation_definitions"])
            assert actual_row["identity_matches"] is True
            assert actual_row["alignment"]["axis"] == 0
            assert abs(actual_row["alignment"]["delta_m"]) == pytest.approx(0.001)
            assert actual_row["alignment"]["aligned"] is False
            assert "native defining point alignment differs" in after["relation_readback_error"]


@pytest.mark.parametrize("before", ("existing-kind", "null-handle", "unavailable"))
def test_constraint_creation_requires_observed_absence_before_single_mutation(monkeypatch, before) -> None:
    fixture = _TapProjectionFixture(monkeypatch)
    original_create = fixture.manager.CreateLine
    original_add = fixture.sketch.RelationManager.AddRelation
    calls = []

    def unavailable():
        raise RuntimeError("native endpoint relation inventory unavailable")

    def create(*coordinates):
        line = original_create(*coordinates)
        start = line.GetStartPoint2()
        if before == "existing-kind":
            start.relations.append(_WitnessRelation((start, fixture.tap), 26))
        elif before == "null-handle":
            start.relations.append(None)
        else:
            start.GetRelations = unavailable
        return line

    def add(entities, kind):
        calls.append(kind)
        return original_add(entities, kind)

    fixture.manager.CreateLine = create
    fixture.sketch.RelationManager.AddRelation = add
    with pytest.raises(RuntimeError, match="already exists|pre-constraint relation inventory unavailable"):
        part._create_tap_projection(fixture.adapter, fixture.tap, fixture.circle, "ThumbTapFromZFlat")
    assert calls == [4]  # Never retry or add an unobservably duplicate relation 26.
    fields = fixture.events[-1][1]
    assert fields["operation_stage"] == "ThumbTapFromZFlat.before-constraint"
    assert fields["relation_kind"] == 26
    assert fields["actual_relation_kinds"] == ((26,) if before == "existing-kind" else (None,) if before == "null-handle" else ())
    if before == "unavailable":
        assert "native endpoint relation inventory unavailable" in fields["relation_readback_error"]


def test_constraint_return_cannot_replace_unavailable_native_poststate(monkeypatch) -> None:
    fixture = _TapProjectionFixture(monkeypatch)
    original_create = fixture.manager.CreateLine
    original_add = fixture.sketch.RelationManager.AddRelation
    calls = []

    def create(*coordinates):
        line = original_create(*coordinates)
        start = line.GetStartPoint2()

        def relations():
            if start.relations:
                raise RuntimeError("native post-state unavailable")
            return ()

        start.GetRelations = relations
        return line

    def add(entities, kind):
        calls.append(kind)
        return original_add(entities, kind)

    fixture.manager.CreateLine = create
    fixture.sketch.RelationManager.AddRelation = add
    with pytest.raises(RuntimeError, match="post-constraint relation inventory unavailable"):
        part._create_tap_projection(fixture.adapter, fixture.tap, fixture.circle, "ThumbTapFromZFlat")
    assert calls == [4, 26]
    fields = fixture.events[-1][1]
    assert fields["operation_stage"] == "ThumbTapFromZFlat.constraint-poststate"
    assert fields["relation_kind"] == 26
    assert "native post-state unavailable" in fields["relation_readback_error"]


def test_native_shaped_database_reuses_exact_points_despite_add_to_db(monkeypatch) -> None:
    fixture = _TapProjectionFixture(monkeypatch)
    fixture.manager.AddToDB = True
    y, radius = fixture.center.Y, fixture.circle.GetRadius()
    first = fixture.create_line(0.0, y, 0.0, radius, y, 0.0)
    second = fixture.create_line(0.0, y, 0.0, radius, y, 0.0)
    assert first.GetStartPoint2() is fixture.center
    assert second.GetStartPoint2() is first.GetStartPoint2()
    assert second.GetEndPoint2() is first.GetEndPoint2()
    with pytest.raises(RuntimeError, match="endpoints merged"):
        part._require_independent_witness_endpoints(fixture.adapter, first, fixture.center, stage="nominal-seed-control")


@pytest.mark.parametrize("failure", ("center-reuse", "null-start", "foreign-owner", "source-swap", "unknown-self", "invalid-id"))
def test_provisional_witness_requires_independent_native_seed_endpoints(monkeypatch, failure) -> None:
    import ast

    fixture = _TapProjectionFixture(monkeypatch)
    original_create = fixture.manager.CreateLine

    def create(*coordinates):
        line = original_create(*coordinates)
        start, end = line.GetStartPoint2(), line.GetEndPoint2()
        if failure == "center-reuse":
            line.GetStartPoint2 = lambda: fixture.center
        elif failure == "null-start":
            line.GetStartPoint2 = lambda: None
        elif failure == "foreign-owner":
            start.owner = _NativeSketch("foreign", "WrongSketch")
        elif failure == "source-swap":
            line.GetStartPoint2, line.GetEndPoint2 = lambda: end, lambda: start
        elif failure == "invalid-id":
            start.identifiers = (True, 0)
        else:
            def same(left, right):
                if failure == "unknown-self" and left is start and right is start:
                    return -1
                return _native_same(left, right)
            fixture.adapter.swApp.IsSame = same
        return line

    fixture.manager.CreateLine = create
    with pytest.raises(RuntimeError):
        part._create_tap_projection(fixture.adapter, fixture.tap, fixture.circle, "ThumbTapFromZFlat")
    assert fixture.relations == []  # No constraint mutation on an invalid seed.
    fields = fixture.events[-1][1]
    if failure == "source-swap":
        assert fields["operation_stage"] == "ThumbTapFromZFlat.seed-readback"
        assert fields["actual_seed_m"] != fields["provisional_seed_m"]
    else:
        assert fields["operation_stage"] == "ThumbTapFromZFlat.seed-endpoint-identity"
        assert fields["endpoint_identity_readback_error"] != "None"
        rows = ast.literal_eval(fields["endpoint_identity_rows"])
        assert rows[0]["role"] == "start"


@pytest.mark.parametrize("failure", ("center-merge", "previous-start-merge", "previous-end-merge", "source-swap", "invalid-id"))
def test_solved_overlaid_witnesses_keep_independent_endpoint_authority(monkeypatch, failure) -> None:
    fixture = _TapProjectionFixture(monkeypatch)
    other = _WitnessPoint(fixture.tap.owner, 0.0, 0.0)
    first = part._create_tap_projection(fixture.adapter, fixture.tap, fixture.circle, "ThumbTapFromZFlat")
    second = part._create_tap_projection(fixture.adapter, other, fixture.circle, "RodTapFromZFlat")
    start, end = second.GetStartPoint2(), second.GetEndPoint2()
    if failure == "center-merge":
        second.GetStartPoint2 = lambda: fixture.center
    elif failure == "previous-start-merge":
        second.GetStartPoint2 = first.GetStartPoint2
    elif failure == "previous-end-merge":
        second.GetEndPoint2 = first.GetEndPoint2
    elif failure == "source-swap":
        second.GetStartPoint2, second.GetEndPoint2 = lambda: end, lambda: start
    else:
        start.identifiers = None
    with pytest.raises(RuntimeError):
        part._assert_tap_projection(fixture.adapter, second, other, fixture.circle, stage="after-rebuild")


def test_provisional_seed_is_not_a_substitute_for_actual_constraint_motion(monkeypatch) -> None:
    fixture = _TapProjectionFixture(monkeypatch, mode="unsolved")
    with pytest.raises(RuntimeError, match="point alignment differs"):
        part._create_tap_projection(fixture.adapter, fixture.tap, fixture.circle, "ThumbTapFromZFlat")
    assert [relation.kind for relation in fixture.relations] == [4, 26]


@pytest.mark.parametrize("cross_proxy_result", (0, -1, "exception"))
def test_all_point_guards_use_documented_keys_not_cross_proxy_dispatch_equality(monkeypatch, cross_proxy_result) -> None:
    fixture = _TapProjectionFixture(monkeypatch)
    proxies = []

    def proxy(entity):
        if not isinstance(entity, _WitnessPoint):
            return entity
        result = _point_proxy(entity)
        assert result is not entity and _native_same(result, entity) == 0
        proxies.append((result, entity))
        return result

    def same(left, right):
        if isinstance(left, _WitnessPoint) and isinstance(right, _WitnessPoint) and left is not right:
            if cross_proxy_result == "exception":
                raise RuntimeError("cross-proxy IsSame unavailable")
            return cross_proxy_result
        return _native_same(left, right)

    fixture.adapter.swApp.IsSame = same
    monkeypatch.setattr(_WitnessRelation, "GetDefinitionEntities2", lambda relation: tuple(proxy(entity) for entity in relation.entities[::-1]))
    manager = fixture.model.SelectionManager
    manager.GetSelectedObject6 = lambda index, _mark: proxy(fixture.selections[index - 1])
    manager.GetSelectedObjectType3 = lambda index, _mark: (25, 10)[index - 1]
    fixture.selections[:] = [fixture.tap, fixture.circle]
    part._require_location_selection(fixture.adapter, fixture.circle, point=fixture.tap, stage="point-flat-proxy")
    manager.GetSelectedObjectType3 = lambda index, _mark: (11, 10)[index - 1]
    original_dimension = fixture.model.AddDimension2

    def dimension(*position):
        display = original_dimension(*position)
        annotation = display.GetAnnotation()
        original_entities = annotation.GetAttachedEntities3
        annotation.GetAttachedEntities3 = lambda: tuple(proxy(entity) for entity in original_entities())
        return display

    fixture.model.AddDimension2 = dimension
    part._measure_tap_from_flat(fixture.adapter, fixture.tap, fixture.circle, fixture.flat, "ThumbTapFromZFlat")
    line = fixture.lines[0]
    part._assert_tap_projection(fixture.adapter, line, fixture.tap, fixture.circle, stage="after-rebuild-proxy")
    part._assert_tap_flat_attachment(fixture.adapter, fixture.displays[0], fixture.tap, fixture.circle, fixture.flat, name="ThumbTapFromZFlat", stage="attachment-after-rebuild-proxy")
    assert proxies and len(fixture.displays) == 1
    assert fixture.displays[0].GetDimension2(0).SystemValue == pytest.approx(0.00635)


@pytest.mark.parametrize("failure", (
    "short-id", "long-id", "bool-id", "float-id", "null-id", "wrong-type",
    "both-types", "neither-type", "qi-unavailable", "null-qi", "self-unavailable",
    "bool-self", "owner-unavailable", "owner-self-unavailable", "unknown-owner", "ambiguous-owner",
))
def test_point_identity_requires_native_type_ordered_integer_pair_and_unique_actual_owner(monkeypatch, failure) -> None:
    import ast

    fixture = _TapProjectionFixture(monkeypatch)
    point = _point_proxy(fixture.tap)
    if failure in ("short-id", "long-id", "bool-id", "float-id", "null-id"):
        point.identifiers = {"short-id": (1,), "long-id": (1, 2, 3), "bool-id": (True, 2), "float-id": (1, 2.0), "null-id": None}[failure]
    elif failure == "wrong-type":
        point._oleobj_ = _WitnessDispatch("ISketchSegment")
    elif failure == "both-types":
        point._oleobj_.capabilities[_WitnessDispatch.segment_iid] = True
    elif failure == "neither-type":
        point._oleobj_.capabilities[_WitnessDispatch.point_iid] = False
    elif failure == "qi-unavailable":
        point._oleobj_.capabilities[_WitnessDispatch.segment_iid] = _WitnessComError(-2147467259)
    elif failure == "null-qi":
        point._oleobj_.capabilities[_WitnessDispatch.point_iid] = None
    elif failure in ("self-unavailable", "bool-self"):
        fixture.adapter.swApp.IsSame = lambda left, right: (True if failure == "bool-self" else -1) if left is point and right is point else _native_same(left, right)
    elif failure == "owner-unavailable":
        point.owner = None
    elif failure == "owner-self-unavailable":
        fixture.adapter.swApp.IsSame = lambda left, right: -1 if left is point.owner and right is point.owner else _native_same(left, right)
    elif failure == "unknown-owner":
        point.owner = _NativeSketch("unlisted", "NotInFeatureInventory")
    elif failure == "ambiguous-owner":
        original_features = fixture.model.FeatureManager.GetFeatures
        fixture.model.FeatureManager.GetFeatures = lambda top: (*original_features(top), _NativeFeature(_NativeSketch(point.owner.token, "SecondClaimedOwner")))
    with pytest.raises(RuntimeError, match="native point identity readback failed"):
        part._point_identity(fixture.adapter, point, stage="invalid-point-key", role="actual")
    fields = fixture.events[-1][1]
    assert fields["operation_stage"] == "invalid-point-key"
    assert fields["point_identity"] == "None"
    queries = ast.literal_eval(fields["point_interface_queries"])
    assert [row["interface"] for row in queries] == ["ISketchPoint", "ISketchSegment"]
    assert fields["point_identity_readback_error"] != "None"


@pytest.mark.parametrize("mutation", ("different-id", "reversed-id", "different-owner", "duplicate-definition"))
def test_relation_point_keys_refuse_coordinate_copies_owner_collisions_and_aliases(monkeypatch, mutation) -> None:
    import ast

    fixture = _TapProjectionFixture(monkeypatch)
    line = part._create_tap_projection(fixture.adapter, fixture.tap, fixture.circle, "ThumbTapFromZFlat")
    start = line.GetStartPoint2()
    actual = _point_proxy(fixture.tap)
    if mutation == "different-id":
        actual.identifiers = (fixture.tap.GetID()[0] + 1, 0)
    elif mutation == "reversed-id":
        actual.identifiers = fixture.tap.GetID()[::-1]
    elif mutation == "different-owner":
        actual.owner = fixture.sketch
    else:
        actual = _point_proxy(start)
    relation = _WitnessRelation((start, actual), 26)
    with pytest.raises(RuntimeError, match="expected exactly one native constraint"):
        part._require_witness_relation(fixture.adapter, (relation,), 26, (start, fixture.tap), stage="wrong-native-point-key")
    row, = ast.literal_eval(fixture.events[-1][1]["relation_definitions"])
    assert row["alignment"]["aligned"] is True
    assert row["identity_matches"] is False
    assert row["point_keys"] and row["expected_point_keys"]


def test_point_keys_are_refreshed_after_rename_and_native_id_change(monkeypatch) -> None:
    fixture = _TapProjectionFixture(monkeypatch)
    first = part._point_identity(fixture.adapter, fixture.tap, stage="before", role="source")
    fixture.tap.owner.feature_name = "RenamedPlacement"
    fixture.tap.identifiers = (7, 19)
    after = part._point_identity(fixture.adapter, _point_proxy(fixture.tap), stage="after-rebuild", role="source")
    assert first[0] == "ThumbPlacement"
    assert after == ("RenamedPlacement", "ISketchPoint", 7, 19)
    assert first != after


@pytest.mark.parametrize("alias", ("center", "previous-start", "previous-end"))
def test_independence_refuses_native_point_key_aliases_even_for_different_dispatches(monkeypatch, alias) -> None:
    fixture = _TapProjectionFixture(monkeypatch)
    first = part._create_tap_projection(fixture.adapter, fixture.tap, fixture.circle, "ThumbTapFromZFlat")
    other_tap = _WitnessPoint(fixture.tap.owner, 0.0, 0.0)
    second = part._create_tap_projection(fixture.adapter, other_tap, fixture.circle, "RodTapFromZFlat")
    target = {"center": fixture.center, "previous-start": first.GetStartPoint2(), "previous-end": first.GetEndPoint2()}[alias]
    proxy = _point_proxy(target)
    assert _native_same(proxy, target) == 0
    second.GetStartPoint2 = lambda: proxy
    with pytest.raises(RuntimeError, match="endpoints merged"):
        part._require_independent_witness_endpoints(fixture.adapter, second, fixture.center, stage="after-rebuild")


def test_point_and_segment_ids_can_collide_without_colliding_typed_identity(monkeypatch) -> None:
    fixture = _TapProjectionFixture(monkeypatch)
    fixture.center.identifiers = fixture.circle.GetID()
    point_key = part._point_identity(fixture.adapter, fixture.center, stage="typed-collision", role="point")
    segment_key = part._segment_identity(fixture.adapter, fixture.circle, stage="typed-collision", role="segment")
    assert point_key[0] == segment_key[0] and point_key[2:] == segment_key[2:]
    assert point_key[1] == "ISketchPoint" and segment_key[1] == 1
    assert point_key != segment_key


@pytest.mark.parametrize("requested_kind", (25, 26))
@pytest.mark.parametrize("inventory", ("other-first", "other-last", "other-only"))
def test_unrelated_suppressed_distance_cannot_veto_or_replace_requested_constraint(monkeypatch, requested_kind, inventory) -> None:
    import ast

    fixture = _TapProjectionFixture(monkeypatch)
    line = part._create_tap_projection(fixture.adapter, fixture.tap, fixture.circle, "ThumbTapFromZFlat")
    requested = fixture.relations[1 if requested_kind == 26 else 2]
    points = (line.GetStartPoint2(), fixture.tap) if requested_kind == 26 else (line.GetEndPoint2(), fixture.center)
    unrelated = _WitnessRelation(requested.entities, 1)
    unrelated.Suppressed = True
    relations = (unrelated,) if inventory == "other-only" else (unrelated, requested) if inventory == "other-first" else (requested, unrelated)
    if inventory == "other-only":
        with pytest.raises(RuntimeError, match=f"expected exactly one native constraint {requested_kind}, found 0"):
            part._require_witness_relation(fixture.adapter, relations, requested_kind, points, stage="requested-kind-authority")
    else:
        part._require_witness_relation(fixture.adapter, relations, requested_kind, points, stage="requested-kind-authority")
    fields = fixture.events[-1][1]
    assert fields["actual_relation_kinds"] == tuple(relation.kind for relation in relations)
    assert fields["relation_matches"] == (0 if inventory == "other-only" else 1)
    rows = ast.literal_eval(fields["relation_definitions"])
    assert len(rows) == len(relations)
    other_row = next(row for row in rows if row["kind"] == 1)
    assert other_row["suppressed"] is True
    assert other_row["definition_interfaces"] == ["ISketchPoint", "ISketchPoint"]
    assert all(len(entity["id"]) == 2 for entity in other_row["definition_fields"])
    assert other_row["identity_matches"] is False and other_row["alignment"] is None
    if inventory != "other-only":
        requested_row = next(row for row in rows if row["kind"] == requested_kind)
        assert requested_row["identity_matches"] is True
        assert requested_row["alignment"]["aligned"] is True
        assert fields["relation_readback_error"] == "None"


def test_common_flat_cutover_changes_the_accepted_set_without_tightening_dot_xx() -> None:
    import mg_magnifying_clamp_geom as geom

    low, high = 6.35 - 0.51, 6.35 + 0.51
    assert spec.LOCATION_PLACES == 2 and spec.LOCATION_BAND == pytest.approx(0.51)
    assert geom.TAP_TO_BORE_ENTRY_Z_MAX == pytest.approx(high - low)

    def old_accepts(bore, tap, radius):
        return low <= bore <= high and abs(bore + radius - tap - 3.25) <= 1.02 + 1e-12

    def new_accepts(bore, tap):
        return low <= bore <= high and low <= tap <= high

    assert old_accepts(6.35, 7.37, 3.25) and not new_accepts(6.35, 7.37)
    assert new_accepts(high, low) and not old_accepts(high, low, 3.30)
    # All three positions are independently accepted, not an implied coincidence.
    assert max(abs(tap - bore) for tap, bore in itertools.product((low, high), repeat=2)) == pytest.approx(1.02)
    assert geom.BLOCK_HEIGHT == 29.50 and geom.LEVER_BORE_Y == 19.95
    assert spec.THUMB_ENGAGEMENT_WORST == pytest.approx(4.402888710865)
    assert spec.ROD_TAP_FLOOR_WALL_WORST == pytest.approx(2.092143505152)
    assert spec.TAP_REACH_NEEDED == pytest.approx(11.901655204897)
    assert spec.TAP_STOP_WINDOW == pytest.approx(0.668770658377)
    assert spec.THUMB_DRILL_NEAR_CLEAR == pytest.approx(0.651607939983)
    assert spec.THUMB_DRILL_FAR_POINT_CLEAR == pytest.approx(0.720010993346)


def _flat_group_fixture(monkeypatch):
    import sys

    fixture = _TapProjectionFixture(monkeypatch)
    points = dict(zip(spec.Z_FLAT_DIMENSIONS[1:], (fixture.tap, _WitnessPoint(fixture.tap.owner, 0.0, 0.0)), strict=True))
    for name, point in points.items():
        part._measure_tap_from_flat(fixture.adapter, point, fixture.circle, fixture.flat, name)
    # R26 bd160ae task.log 158–161, 295–337, 355–410: the observed bore
    # source/view IDs are (0,2), flat line (1,2). Other members remain stateful
    # synthetic regressions, NOT claims of native forward success for those taps.
    fixture.center.identifiers = (0, 2)
    fixture.flat.GetID = lambda: (1, 2)
    for index, line in enumerate(fixture.lines):
        line.GetStartPoint2().identifiers = (5 + 3 * index, 6 + 3 * index)
        line.GetEndPoint2().identifiers = (6 + 3 * index, 7 + 3 * index)
    dimensions = fixture.install_rebuild(monkeypatch, points)
    fixture.source_displays = dimensions
    wrapper = sys.modules["solidworks_mcp.adapters._generated.sldworks_2026"]
    sys.modules["pythoncom"].IID_IDispatch = "fixture-IDispatch"
    for interface in ("IAnnotation", "IDimension", "IFeature", "IModelDoc2", "ISketch", "IView"):
        setattr(wrapper, interface, SimpleNamespace(CLSID=f"fixture-{interface}-IID"))

    def tag(value, interface):
        if not hasattr(value, "_oleobj_"):
            value._oleobj_ = _WitnessDispatch(interface)
        value._oleobj_.capabilities[getattr(wrapper, interface).CLSID] = True
        value._oleobj_.capabilities["fixture-IDispatch"] = True
        return value

    fixture.tag = tag
    fixture.drawing_sketch = tag(_NativeSketch("drawing-right", fixture.sketch.feature_name), "ISketch")
    fixture.forward_sketch = tag(_NativeSketch("drawing-right", fixture.sketch.feature_name), "ISketch")
    tag(fixture.sketch, "ISketch")
    tag(fixture.model, "IModelDoc2")
    fixture.model.GetType = lambda: 1
    # R26 411=0, 412=1: GetFeatureOwner's sketch is deliberately NOT part
    # authority, even though the feature name and native dimension agree.
    fixture.dimension_feature = tag(_NativeFeature(fixture.drawing_sketch), "IFeature")
    fixture.forward_feature = tag(_NativeFeature(fixture.forward_sketch), "IFeature")
    fixture.forward_entities, fixture.source_by_import = {}, {}
    fixture.mapping_calls, fixture.inverse_calls = [], []

    def source_key(entity):
        kind = "ISketchPoint" if isinstance(entity, _WitnessPoint) else entity.GetType()
        return entity.GetSketch().token, kind, *entity.GetID()

    fixture.source_key = source_key

    def drawing_entity(source, owner):
        if isinstance(source, _WitnessPoint):
            proxy = _point_proxy(source)
            proxy.owner = owner
            proxy.X += 0.125
            return tag(proxy, "ISketchPoint")
        proxy = _native_sketch_segment(owner=owner.feature_name, kind=source.GetType(), identifiers=source.GetID())
        proxy.owner_sketch = owner
        proxy.GetSketch = lambda: owner
        return tag(proxy, "ISketchSegment")

    def import_entity(source):
        tag(source, "ISketchPoint" if isinstance(source, _WitnessPoint) else "ISketchSegment")
        proxy = drawing_entity(source, fixture.drawing_sketch)
        fixture.source_by_import[id(proxy)] = source
        key = source_key(source)
        if key not in fixture.forward_entities:
            fixture.forward_entities[key] = drawing_entity(source, fixture.forward_sketch)
        return proxy

    def corresponding_view(entity):
        fixture.mapping_calls.append(entity)
        if entity is fixture.dimension_feature:
            return fixture.forward_feature
        # Only actual source entities are accepted; owner-only mapping is not
        # an alternative. Source IDs identify the fake API input, not the view.
        assert entity.GetSketch() is fixture.sketch
        return fixture.forward_entities.get(source_key(entity))

    def inverse_forbidden(entity):
        fixture.inverse_calls.append(entity)
        raise AssertionError("reverse correspondence is not part of attachment acceptance")

    fixture.import_entity = import_entity
    fixture.model.Extension = SimpleNamespace(GetCorresponding2=inverse_forbidden)
    view = tag(SimpleNamespace(ReferencedDocument=fixture.model, GetCorresponding=corresponding_view), "IView")
    annotations = []
    for name, source_display in dimensions.items():
        source_dimension = tag(source_display.GetDimension2(0), "IDimension")
        source_dimension.dimension_token = name
        source_dimension.GetFeatureOwner = lambda: fixture.dimension_feature
        source_annotation = tag(source_display.GetAnnotation(), "IAnnotation")
        source_annotation.OwnerType, source_annotation.Owner = 3, fixture.model
        dimension = tag(SimpleNamespace(
            Name=name, FullName=source_dimension.FullName, DrivenState=1,
            SystemValue=source_dimension.SystemValue, Tolerance=SimpleNamespace(Type=0),
            dimension_token=name, GetFeatureOwner=lambda: fixture.dimension_feature,
        ), "IDimension")
        text = {}
        attached = tuple(import_entity(entity) for entity in source_annotation.GetAttachedEntities3())
        annotation = tag(SimpleNamespace(
            GetAttachedEntities3=lambda value=attached: value,
            GetAttachedEntityTypes=source_annotation.GetAttachedEntityTypes,
            IsDangling=lambda: False, Visible=1, OwnerType=0, Owner=view,
        ), "IAnnotation")
        display = SimpleNamespace(
            GetDimension2=lambda _index, value=dimension: value,
            GetPrimaryPrecision2=lambda: 2, ShowParenthesis=False,
            GetAnnotation=lambda value=annotation: value,
            SetText=lambda kind, value, state=text: state.__setitem__(kind, value),
            GetText=lambda kind, state=text: state.get(kind, ""),
        )
        annotation.GetSpecificAnnotation = lambda value=display: value
        annotations.append(annotation)

    def native_same(left, right):
        if hasattr(left, "dimension_token") and hasattr(right, "dimension_token"):
            return int(left.dimension_token == right.dimension_token)
        return _native_same(left, right)

    fixture.same = native_same
    fixture.adapter.swApp.IsSame = native_same
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(drawing, "_named_dimension", part._named_dimension)
    monkeypatch.setattr(drawing, "dimension_name", lambda _adapter, annotation: annotation.GetSpecificAnnotation().GetDimension2(0).Name)
    return fixture, view, annotations[::-1]


def test_grouping_retains_three_distinct_source_measurements_and_one_real_visible_dimension(monkeypatch) -> None:
    fixture, view, annotations = _flat_group_fixture(monkeypatch)
    endpoints = [point for line in fixture.lines for point in (line.GetStartPoint2(), line.GetEndPoint2())]
    before = [(point.GetID(), point.X, point.Y, point.Z) for point in endpoints]
    drawing._group_flat_locations(fixture.adapter, view, annotations)
    assert [(point.GetID(), point.X, point.Y, point.Z) for point in endpoints] == before
    assert len({point.GetID() for point in endpoints}) == 4
    states = {drawing.dimension_name(fixture.adapter, a): a.Visible for a in annotations}
    assert states == {"LeverBoreFromZFlat": 1, "ThumbTapFromZFlat": 3, "RodTapFromZFlat": 3}
    leader = next(a for a in annotations if drawing.dimension_name(fixture.adapter, a) == "LeverBoreFromZFlat")
    assert leader.GetSpecificAnnotation().GetText(1) == "3X "
    assert all(a.GetSpecificAnnotation().GetDimension2(0).SystemValue == pytest.approx(0.00635) for a in annotations)
    assert len(spec.DRAWING_PRECISION_BY_NAME) == 9 and len(spec.VISIBLE_DIMENSIONS) == 7
    assert spec.DIMENSION_GROUPS == {"LeverBoreFromZFlat": spec.Z_FLAT_DIMENSIONS}
    # Two readbacks, three dimensions, a feature and two actual entities each.
    assert len(fixture.mapping_calls) == 18
    assert sum(entity is fixture.dimension_feature for entity in fixture.mapping_calls) == 6
    assert all(entity.GetSketch() is fixture.sketch for entity in fixture.mapping_calls if entity is not fixture.dimension_feature)
    assert fixture.inverse_calls == []
    assert _native_same(fixture.dimension_feature.GetSpecificFeature2(), fixture.sketch) == 0
    fields = fixture.events[-1][1]
    assert fields["source_dimension_count"] == 3 and fields["visible_dimension_count"] == 1
    drawing._assert_grouped_flat_locations(fixture.adapter, view, annotations)


@pytest.mark.parametrize("failure", (
    "missing", "duplicate", "wrong-feature", "wrong-model", "wrong-value",
    "explicit-band", "wrong-precision", "wrong-point-same-coordinates",
    "wrong-flat-same-coordinates", "wrong-source-association", "dangling",
))
def test_grouping_refuses_unproved_native_members_before_hiding_any_dimension(monkeypatch, failure) -> None:
    fixture, view, annotations = _flat_group_fixture(monkeypatch)
    original_annotations = annotations[:]
    annotation = next(a for a in annotations if drawing.dimension_name(fixture.adapter, a) == "ThumbTapFromZFlat")
    display = annotation.GetSpecificAnnotation()
    dimension = display.GetDimension2(0)
    if failure == "missing":
        annotations.remove(annotation)
    elif failure == "duplicate":
        annotations.append(annotation)
    elif failure == "wrong-feature":
        dimension.FullName = "ThumbTapFromZFlat@OtherProfile@Clamp.Part"
    elif failure == "wrong-model":
        dimension.FullName = "ThumbTapFromZFlat@LeverBoreLocationProfile@Other.Part"
    elif failure == "wrong-value":
        dimension.SystemValue += 0.0002
    elif failure == "explicit-band":
        dimension.Tolerance.Type = 2
    elif failure == "wrong-precision":
        display.GetPrimaryPrecision2 = lambda: 3
    elif failure == "wrong-point-same-coordinates":
        # The other tap is nominally coincident, but is a DIFFERENT source.
        flat, _point = annotation.GetAttachedEntities3()
        annotation.GetAttachedEntities3 = lambda: (flat, fixture.import_entity(fixture.lines[1].GetStartPoint2()))
    elif failure == "wrong-flat-same-coordinates":
        other_flat = _native_sketch_segment(owner=fixture.sketch.feature_name, kind=0, identifiers=(99, 2))
        other_flat.owner_sketch = fixture.sketch
        other_flat.GetSketch = lambda: fixture.sketch
        other_flat.GetStartPoint2 = fixture.flat.GetStartPoint2
        other_flat.GetEndPoint2 = fixture.flat.GetEndPoint2
        _flat, point = annotation.GetAttachedEntities3()
        imported_flat = fixture.import_entity(other_flat)
        annotation.GetAttachedEntities3 = lambda: (imported_flat, point)
    elif failure == "wrong-source-association":
        fixture.lines[0].GetStartPoint2().relations.clear()
    elif failure == "dangling":
        annotation.IsDangling = lambda: True
    with pytest.raises(RuntimeError):
        drawing._group_flat_locations(fixture.adapter, view, annotations)
    assert all(a.Visible == 1 for a in original_annotations)
    assert all(a.GetSpecificAnnotation().GetText(1) == "" for a in original_annotations)


def test_grouping_matches_distinct_drawing_proxies_without_equating_model_ids(monkeypatch) -> None:
    fixture, view, annotations = _flat_group_fixture(monkeypatch)
    for index, annotation in enumerate(annotations):
        flat, point = annotation.GetAttachedEntities3()
        model_point = fixture.source_by_import[id(point)]
        mapped_point = fixture.forward_entities[fixture.source_key(model_point)]
        mapped_flat = fixture.forward_entities[fixture.source_key(fixture.flat)]
        assert _native_same(mapped_point, point) == 0
        assert _native_same(mapped_flat, flat) == 0
        point.identifiers = mapped_point.identifiers = (9000 + 2 * index, 9001 + 2 * index)
        flat.GetID = mapped_flat.GetID = lambda: (9900, 9901)
        assert point.GetID() != model_point.GetID()
        assert flat.GetID() != fixture.flat.GetID()
        annotation.GetAttachedEntities3 = lambda flat=flat, point=point: (point, flat)
        annotation.GetAttachedEntityTypes = lambda: (11, 10)
    drawing._group_flat_locations(fixture.adapter, view, annotations)
    assert fixture.inverse_calls == []


def test_view_attachment_is_not_a_part_object_even_with_same_name_and_ids(monkeypatch) -> None:
    fixture, view, annotations = _flat_group_fixture(monkeypatch)
    annotation = annotations[0]
    _flat, point = annotation.GetAttachedEntities3()
    model_point = fixture.source_by_import[id(point)]
    assert point.GetID() == model_point.GetID()
    assert point.GetSketch().feature_name == model_point.GetSketch().feature_name
    assert _native_same(point.GetSketch(), model_point.GetSketch()) == 0
    with pytest.raises(RuntimeError):
        part._point_flat_attachment(fixture.adapter, annotation.GetSpecificAnnotation(), fixture.flat, stage="unmapped-view")
    assert not fixture.mapping_calls
    drawing._group_flat_locations(fixture.adapter, view, annotations)
    assert fixture.inverse_calls == []


@pytest.mark.parametrize("failure", (
    "missing-point", "missing-flat", "wrong-point-type", "wrong-flat-type",
    "ambiguous-point", "unavailable-point-capability", "null-point-capability",
    "invalid-point-id", "bool-point-id", "reversed-point-id", "wrong-flat-id", "wrong-flat-kind",
    "wrong-drawing-type", "drawing-point-self", "mapped-point-self", "drawing-owner-self",
    "mapped-owner-self", "unknown-owner-comparison", "wrong-view-sketch", "null-owner", "wrong-owner-interface",
    "wrong-view", "owner-type", "unknown-view-identity", "wrong-dimension", "dimension-self",
    "wrong-feature", "missing-feature-map", "wrong-feature-map-interface", "wrong-feature-type",
    "wrong-feature-name", "missing-feature-sketch", "wrong-feature-sketch-interface", "wrong-feature-sketch",
    "feature-sketch-self", "missing-attached", "null-attached", "wrong-types", "unknown-dangling", "mapping-error",
))
def test_grouping_rejects_unproved_forward_correspondence_before_hiding(monkeypatch, failure) -> None:
    import ast
    import sys

    fixture, view, annotations = _flat_group_fixture(monkeypatch)
    annotation = next(a for a in annotations if drawing.dimension_name(fixture.adapter, a) == "ThumbTapFromZFlat")
    flat, point = annotation.GetAttachedEntities3()
    model_point = fixture.source_by_import[id(point)]
    point_key = fixture.source_key(model_point)
    flat_key = fixture.source_key(fixture.flat)
    mapped = fixture.forward_entities[point_key]
    mapped_flat = fixture.forward_entities[flat_key]
    dimension = annotation.GetSpecificAnnotation().GetDimension2(0)
    wrapper = sys.modules["solidworks_mcp.adapters._generated.sldworks_2026"]
    if failure == "missing-point":
        fixture.forward_entities[point_key] = None
    elif failure == "missing-flat":
        fixture.forward_entities[flat_key] = None
    elif failure == "wrong-point-type":
        fixture.forward_entities[point_key] = mapped_flat
    elif failure == "wrong-flat-type":
        fixture.forward_entities[flat_key] = mapped
    elif failure == "ambiguous-point":
        mapped._oleobj_.capabilities[_WitnessDispatch.segment_iid] = True
    elif failure == "unavailable-point-capability":
        mapped._oleobj_.capabilities[_WitnessDispatch.point_iid] = _WitnessComError(-2147418111)
    elif failure == "null-point-capability":
        mapped._oleobj_.capabilities[_WitnessDispatch.point_iid] = None
    elif failure == "invalid-point-id":
        mapped.identifiers = (1,)
    elif failure == "bool-point-id":
        mapped.identifiers = (True, 2)
    elif failure == "reversed-point-id":
        mapped.identifiers = point.GetID()[::-1]
        assert (mapped.X, mapped.Y, mapped.Z) == (point.X, point.Y, point.Z)
    elif failure == "wrong-flat-id":
        mapped_flat.GetID = lambda: (999, 2)
    elif failure == "wrong-flat-kind":
        mapped_flat.GetType = lambda: 1
    elif failure == "wrong-drawing-type":
        point._oleobj_.capabilities[_WitnessDispatch.point_iid] = False
        point._oleobj_.capabilities[_WitnessDispatch.segment_iid] = True
    elif failure in ("drawing-point-self", "mapped-point-self", "drawing-owner-self", "mapped-owner-self", "dimension-self", "feature-sketch-self"):
        broken = {
            "drawing-point-self": point, "mapped-point-self": mapped,
            "drawing-owner-self": point.GetSketch(), "mapped-owner-self": mapped.GetSketch(),
            "dimension-self": dimension, "feature-sketch-self": fixture.forward_feature.GetSpecificFeature2(),
        }[failure]
        fixture.adapter.swApp.IsSame = lambda left, right: 2 if left is broken and right is broken else fixture.same(left, right)
    elif failure == "unknown-owner-comparison":
        fixture.adapter.swApp.IsSame = lambda left, right: 2 if left is mapped.GetSketch() and right is point.GetSketch() else fixture.same(left, right)
    elif failure == "wrong-view-sketch":
        point.owner = fixture.tag(_NativeSketch("other-view", fixture.sketch.feature_name), "ISketch")
    elif failure == "null-owner":
        mapped.owner = None
    elif failure == "wrong-owner-interface":
        mapped.owner._oleobj_.capabilities[wrapper.ISketch.CLSID] = False
    elif failure == "wrong-view":
        annotation.Owner = fixture.tag(SimpleNamespace(), "IView")
    elif failure == "owner-type":
        annotation.OwnerType = False  # bool is not the native view-owner enum 0.
    elif failure == "unknown-view-identity":
        owner = fixture.tag(SimpleNamespace(), "IView")
        annotation.Owner = owner
        fixture.adapter.swApp.IsSame = lambda left, right: 2 if left is owner and right is view else fixture.same(left, right)
    elif failure == "wrong-dimension":
        dimension.dimension_token = "different-native-dimension"
    elif failure == "wrong-feature":
        other = fixture.tag(_NativeFeature(fixture.drawing_sketch), "IFeature")
        dimension.GetFeatureOwner = lambda: other
    elif failure == "missing-feature-map":
        fixture.forward_feature = None
    elif failure == "wrong-feature-map-interface":
        fixture.forward_feature._oleobj_.capabilities[wrapper.IFeature.CLSID] = False
    elif failure == "wrong-feature-type":
        fixture.forward_feature.kind = "Boss"
    elif failure == "wrong-feature-name":
        fixture.forward_feature.Name = "OtherProfile"
    elif failure == "missing-feature-sketch":
        fixture.forward_feature.sketch = None
    elif failure == "wrong-feature-sketch-interface":
        fixture.forward_feature.sketch._oleobj_.capabilities[wrapper.ISketch.CLSID] = False
    elif failure == "wrong-feature-sketch":
        fixture.forward_feature.sketch = fixture.tag(_NativeSketch("wrong-feature-view", fixture.sketch.feature_name), "ISketch")
    elif failure == "missing-attached":
        annotation.GetAttachedEntities3 = lambda: (point,)
    elif failure == "null-attached":
        annotation.GetAttachedEntities3 = lambda: (flat, None)
    elif failure == "wrong-types":
        annotation.GetAttachedEntityTypes = lambda: (10, True)
    elif failure == "unknown-dangling":
        annotation.IsDangling = lambda: None
    else:
        original = view.GetCorresponding

        def unavailable(entity):
            if entity is model_point:
                raise _WitnessComError(-2147418111)
            return original(entity)

        view.GetCorresponding = unavailable
    with pytest.raises(_WitnessComError if failure == "mapping-error" else RuntimeError):
        drawing._group_flat_locations(fixture.adapter, view, annotations)
    assert all(a.Visible == 1 for a in annotations)
    assert all(a.GetSpecificAnnotation().GetText(1) == "" for a in annotations)
    assert fixture.inverse_calls == []
    records = [fields for _message, fields in fixture.events if "attachment_forward" in fields]
    assert records and records[-1]["attachment_readback_error"] != "None"
    audit = ast.literal_eval(records[-1]["attachment_forward"])
    assert audit["step"]
    if failure == "wrong-feature-sketch":
        assert audit["attachments"][-1]["owner_match"] == 1
        assert audit["attachments"][-1]["feature_owner_match"] == 0
    if failure == "wrong-dimension":
        assert audit["full_names"][0] == audit["full_names"][1]
        assert audit["dimension_match"] == 0
    if failure == "wrong-feature":
        assert audit["feature_names"][0] == audit["feature_names"][1]
        assert audit["feature_match"] == 0
    if failure == "missing-attached":
        assert audit["attachment_count"] == 1 and audit["attached_types"] == (10, 11)
    if failure == "null-attached":
        assert audit["attachment_count"] == 2
    if failure == "unavailable-point-capability":
        queries = audit["native"]["point.forward"]["queries"]
        assert len(queries) == 3
        assert queries[0]["hresult"] == -2147418111 and queries[0]["supported"] is None
        assert queries[-1]["supported"] is False
    if failure == "mapping-error":
        assert audit["attachments"][-1]["mapped_present"] is None
        assert any(fields.get("operation_stage") == "ThumbTapFromZFlat.drawing-import.forward-before" for _message, fields in fixture.events)



def test_forward_mapping_cannot_substitute_for_unknown_source_part_owner(monkeypatch) -> None:
    fixture, view, annotations = _flat_group_fixture(monkeypatch)
    source_display = fixture.source_displays["ThumbTapFromZFlat"]
    source_annotation = source_display.GetAnnotation()
    flat, point = source_annotation.GetAttachedEntities3()
    proxy = _point_proxy(point)
    proxy.owner = fixture.tag(_NativeSketch("unknown-source", point.GetSketch().feature_name), "ISketch")
    fixture.tag(proxy, "ISketchPoint")
    source_annotation.GetAttachedEntities3 = lambda: (flat, proxy)
    # Even if the view API could give a plausible object, part ownership must
    # refuse first. No accepting fake mapping is installed in production.
    with pytest.raises(RuntimeError):
        drawing._group_flat_locations(fixture.adapter, view, annotations)
    assert fixture.mapping_calls == [] and fixture.inverse_calls == []
    assert all(annotation.Visible == 1 for annotation in annotations)


@pytest.mark.parametrize("fault", ("logger", "original-repr"))
@pytest.mark.parametrize("boundary", ("model-attachment", "feature-forward", "point-forward"))
def test_attachment_refusal_preserves_original_exception_and_traceback(monkeypatch, fault, boundary) -> None:
    import _telemetry

    class UnprintableOriginal(RuntimeError):
        def __repr__(self):
            raise ValueError("original repr unavailable")

    original = UnprintableOriginal("native attachment refusal") if fault == "original-repr" else RuntimeError("native attachment refusal")
    native_tracebacks = []

    def refuse(*_args):
        try:
            raise original
        except RuntimeError:
            native_tracebacks.append(original.__traceback__)
            raise

    def logger(_message, **fields):
        if fault == "logger" and "attachment_readback_error" in fields:
            raise ValueError("secondary telemetry failure")

    if boundary == "model-attachment":
        annotation = SimpleNamespace(GetAttachedEntities3=refuse)
        display = SimpleNamespace(GetAnnotation=lambda: annotation)
        monkeypatch.setattr(part, "_early_bound", lambda value, _interface: value)

        def invoke():
            return part._point_flat_attachment(SimpleNamespace(), display, object(), stage="original-refusal")
    else:
        fixture, view, annotations = _flat_group_fixture(monkeypatch)
        annotation = next(a for a in annotations if drawing.dimension_name(fixture.adapter, a) == "LeverBoreFromZFlat")
        source_display = fixture.source_displays["LeverBoreFromZFlat"]
        source_annotation = source_display.GetAnnotation()
        entities, types = source_annotation.GetAttachedEntities3(), source_annotation.GetAttachedEntityTypes()
        key = part._point_identity(fixture.adapter, fixture.center, stage="fixture-source", role="source")
        original_mapping = view.GetCorresponding
        target = fixture.dimension_feature if boundary == "feature-forward" else fixture.center

        def mapping(entity):
            return refuse(entity) if entity is target else original_mapping(entity)

        view.GetCorresponding = mapping

        def invoke():
            return drawing._require_flat_import(fixture.adapter, view, source_display, annotation.GetSpecificAnnotation(), entities, types, key, stage="original-refusal")
    monkeypatch.setattr(_telemetry, "info", logger)
    with pytest.raises(RuntimeError, match="native attachment refusal") as refused:
        invoke()
    assert refused.value is original
    current = refused.value.__traceback__
    while current is not None and current is not native_tracebacks[0]:
        current = current.tb_next
    assert current is native_tracebacks[0]


def test_group_correspondence_is_read_again_after_rebuild_without_cached_keys(monkeypatch) -> None:
    fixture, view, annotations = _flat_group_fixture(monkeypatch)
    drawing._group_flat_locations(fixture.adapter, view, annotations)
    annotation = next(a for a in annotations if drawing.dimension_name(fixture.adapter, a) == "ThumbTapFromZFlat")
    _flat, point = annotation.GetAttachedEntities3()
    key = fixture.source_key(fixture.source_by_import[id(point)])
    fixture.forward_entities[key].identifiers = (500, 501)
    with pytest.raises(RuntimeError, match="imported native drawing identity differs"):
        drawing._assert_grouped_flat_locations(fixture.adapter, view, annotations)
    assert fixture.inverse_calls == []


@pytest.mark.parametrize("failure", ("hide-refused", "unknown-visible", "prefix-lost", "source-constraint-lost"))
def test_group_visibility_and_source_proof_remain_strict_after_native_rebuild(monkeypatch, failure) -> None:
    fixture, view, annotations = _flat_group_fixture(monkeypatch)
    if failure == "hide-refused":
        class RefusingAnnotation:
            def __init__(self, native):
                self.native = native

            def __getattr__(self, name):
                return getattr(self.native, name)

            @property
            def Visible(self):
                return self.native.Visible

            @Visible.setter
            def Visible(self, _value):
                pass  # Native refusal fixture: the required state never persisted.

        annotations = [RefusingAnnotation(a) if drawing.dimension_name(fixture.adapter, a) == "RodTapFromZFlat" else a for a in annotations]
        with pytest.raises(RuntimeError, match="native visibility"):
            drawing._group_flat_locations(fixture.adapter, view, annotations)
        return
    drawing._group_flat_locations(fixture.adapter, view, annotations)
    if failure == "unknown-visible":
        annotations[0].Visible = 0
    elif failure == "prefix-lost":
        leader = next(a for a in annotations if drawing.dimension_name(fixture.adapter, a) == "LeverBoreFromZFlat")
        leader.GetSpecificAnnotation().SetText(1, "")
    else:
        fixture.lines[0].GetStartPoint2().relations.clear()
    with pytest.raises(RuntimeError):
        drawing._assert_grouped_flat_locations(fixture.adapter, view, annotations)


@pytest.mark.parametrize("failure", ("none", "value", "reference", "state", "band", "bool-band", "precision", "unavailable"))
def test_ordinary_location_readback_reports_actual_metadata_before_refusal(monkeypatch, failure) -> None:
    import ast
    import _telemetry

    dimension = SimpleNamespace(
        DrivenState=2 if failure == "state" else 1,
        SystemValue=0.00655 if failure == "value" else 0.00635,
        Tolerance=SimpleNamespace(Type=False if failure == "bool-band" else 2 if failure == "band" else 0),
    )
    display = SimpleNamespace(ShowParenthesis=failure == "reference", GetPrimaryPrecision2=lambda: 3 if failure == "precision" else 2)
    if failure == "unavailable":
        def unavailable():
            raise RuntimeError("native precision unavailable")
        display.GetPrimaryPrecision2 = unavailable
    events = []
    monkeypatch.setattr(part, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(_telemetry, "info", lambda message, **fields: events.append((message, fields)))
    if failure == "none":
        part._assert_ordinary_location(display, dimension, "ActualFromFlat")
    else:
        with pytest.raises(RuntimeError):
            part._assert_ordinary_location(display, dimension, "ActualFromFlat")
    _message, fields = events[-1]
    assert fields["operation_stage"] == "ActualFromFlat.ordinary-location-readback"
    actual = ast.literal_eval(fields["native_measurement"])
    assert actual["value_m"] == dimension.SystemValue
    assert actual["driven_state"] == dimension.DrivenState
    assert actual["tolerance_type"] == dimension.Tolerance.Type
    assert type(actual["tolerance_type"]) is type(dimension.Tolerance.Type)
    assert (fields["measurement_readback_error"] == "None") is (failure != "unavailable")
    if failure == "unavailable":
        assert "places" not in actual and "native precision unavailable" in fields["measurement_readback_error"]









