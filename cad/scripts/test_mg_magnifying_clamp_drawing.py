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
import _gtol_face_resolve
from _gtol_face import FaceGeometry, SURFACE_PLANE
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
    kept = set(drawing.RIGHT_KEEP) | set(drawing.TOP_KEEP) | set(drawing.RIGHT_LOCATION_KEEP) | set(drawing.TOP_LOCATION_KEEP) | set(drawing.BOTTOM_KEEP)
    assert kept == marked
    assert set(drawing.DIMENSION_CALLOUTS) <= kept
    assert spec.REFERENCE_DIMENSIONS <= set(drawing.TOP_KEEP)


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
    for name, (nominal, worst) in spec.WALLS.items():
        assert worst >= spec.WALL_TARGET, name
        assert nominal >= worst, name
    assert spec.WALLS["rod-tap drill point to the lever bore"][1] == pytest.approx(
        spec.ROD_TAP_FLOOR_WALL_WORST
    )
    # The raw-stock form is not certified by nominal CAD symmetry. The
    # finished-wall requirement is a separate physical acceptance, while
    # relative axes are directly measured from the bore rim.
    import mg_magnifying_clamp_geom as geom

    entry_errors = [
        abs(geom.LEVER_BORE_DIA / 2.0 + radius_change - (geom.LEVER_BORE_DIA / 2.0 + error))
        for radius_change, error in itertools.product((0.0, 0.05), (-1.02, 1.02))
    ]
    assert geom.TAP_TO_BORE_ENTRY_Z_MAX == pytest.approx(max(entry_errors))
    assert geom.BORE_FULL_ANGULAR == pytest.approx(15.0 * math.tan(math.radians(0.3)))
    for name in ("lever bore to a flat", "rod-tap thread to a flat", "thumb-screw tap thread to a flat"):
        assert spec.WALLS[name][1] == spec.WALL_TARGET
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


def test_linked_notes_own_finished_acceptance_without_claiming_stock_form() -> None:
    notes = spec.DRAWING_NOTES
    assert float(Fraction(notes.split()[0])) * 25.4 == pytest.approx(spec.HEX_AF)
    for gone in ("CENTRED", "PLUG TAP", "CHAMFER", "SEAT", "THREAD ENDS"):
        assert gone not in notes
    assert f"{spec.WALL_TARGET:.1f} MIN FINISHED WALL AT BORE/TAPS" in notes
    assert f"TRANSVERSE ENVELOPE {spec.STOCK_WIDTH_MAX:.2f} MAX" in notes
    assert "OVER FULL HEIGHT" in notes
    assert not hasattr(spec, "TAP_TOOL_NOTE")
    assert not hasattr(spec, "BORE_WALL_NOTE")
    # This is finished acceptance, not an AF/Rule#1 form guarantee.
    assert "WALL" not in spec.LEVER_BORE_CALLOUT
    assert spec.LEVER_BORE_CALLOUT == "DRILL THRU CORNERS\nSLIP ON 1/4 IN LEVER MHA-MG-03"
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


@pytest.mark.parametrize("stale_property", (False, True))
@pytest.mark.parametrize("has_supplied_flat", (True, False))
def test_stock_note_resolves_and_attaches_only_the_actual_supplied_flat(monkeypatch, has_supplied_flat, stale_property) -> None:
    def face(normal, origin):
        native = SimpleNamespace()
        native.geometry = FaceGeometry(native, SURFACE_PLANE, (*normal, *origin), normal, (0.0,) * 6)
        return native

    cap = face((0.0, 1.0, 0.0), (0.0, spec.BLOCK_HEIGHT / 1000.0, 0.0))
    opposite = face((0.0, 0.0, -1.0), (0.0, 0.0, -spec.HEX_AF / 2000.0))
    supplied = face((0.0, 0.0, 1.0), (0.0, 0.0, spec.HEX_AF / 2000.0))
    faces = [cap, opposite, *([supplied] if has_supplied_flat else [])]
    for native, following in zip(faces, [*faces[1:], None], strict=True):
        native.GetNextFace = lambda following=following: following
    model = SimpleNamespace(GetBodies2=lambda _kind, _visible: (SimpleNamespace(GetFirstFace=lambda: faces[0]),), properties={"Manufacturing Notes": "OLD STOCK" if stale_property else spec.STOCK_NOTE})
    view = SimpleNamespace(ReferencedDocument=model)
    calls = []
    monkeypatch.setattr(_gtol_face_resolve, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(_gtol_face_resolve, "_bind", lambda value, _interface: value)
    monkeypatch.setattr(_gtol_face_resolve, "_com_invoke", lambda value, _interface, member: getattr(value, member)())
    monkeypatch.setattr(_gtol_face_resolve, "face_geometry", lambda value, *, identities: value.geometry)

    def insert_note(_adapter, picked_view, **kwargs):
        calls.append((picked_view, kwargs))
        property_name = kwargs["text"].split('"')[1]
        return SimpleNamespace(GetText=lambda: model.properties[property_name])

    monkeypatch.setattr(drawing, "add_attached_note", insert_note)
    if not has_supplied_flat:
        with pytest.raises(RuntimeError, match="matched 0 faces"):
            drawing._add_stock_note(None, view)
        assert calls == []
    elif stale_property:
        with pytest.raises(RuntimeError, match="model property did not resolve"):
            drawing._add_stock_note(None, view)
    else:
        drawing._add_stock_note(None, view)
        assert len(calls) == 1 and calls[0][0] is view
        arguments = calls[0][1]
        assert arguments["entity_type"] == "FACE"
        assert arguments["entity"] is arguments["attached_to"] is supplied
        assert arguments["text"] == drawing.property_link("Manufacturing Notes")
        assert "entity_xy" not in arguments  # no free pointer pretending to attach


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


def _native_sketch_segment(*, owner="ActualLocationProfile", kind=0, identifiers=(1, 2)):
    sketch = _NativeSketch(owner, owner)
    return SimpleNamespace(
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
    center, flat = object(), _native_sketch_segment()
    toggles = {}

    class Dimension:
        state, name = 2, ""

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
    # Direct rim/axis band includes the bore's radial +0.05 allowance.
    relative_offset = 1.02 + 0.05 + depth * slope + bore_wander

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
    circle, flat = object(), object()

    def converted(source):
        return SimpleNamespace(GetRelations=lambda: (SimpleNamespace(GetDefinitionEntities2=lambda: (source,)),))

    segments = [converted(circle), converted(flat if mode != "lost-source" else object())]
    if mode == "extra-segment":
        segments.append(converted(object()))
    sketch = SimpleNamespace(GetSketchSegments=lambda: tuple(segments), GetConstrainedStatus=lambda: 2 if mode == "underdefined" else 3)
    model = SimpleNamespace(FeatureByName=lambda name: SimpleNamespace(GetSpecificFeature2=lambda: sketch))
    application = SimpleNamespace(IsSame=lambda left, right: int(left is right))
    adapter = SimpleNamespace(currentModel=model, swApp=application)
    monkeypatch.setattr(part, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(part, "_location_sources", lambda _adapter: {"ActualLocationProfile": ("Top", circle, "IEntity", (("ActualFromFlat", flat),))})
    monkeypatch.setattr(part, "_named_dimension", lambda _adapter, feature, name: (SimpleNamespace(ShowParenthesis=mode == "reference-ink"), SimpleNamespace(DrivenState=1, SystemValue=(spec.HEX_AF / 2.0 + (0.2 if mode == "wrong-distance" else 0.0)) / 1000.0)))
    if mode == "retained":
        part._assert_location_profiles(adapter)
    else:
        with pytest.raises(RuntimeError):
            part._assert_location_profiles(adapter)


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
        assert result["ThumbTapToBoreRim"] is points["ThumbTap"]
        assert result["RodTapToBoreRim"] is points["RodTap"]
    else:
        with pytest.raises(RuntimeError):
            part._tap_placement_points(adapter)


@pytest.mark.parametrize("mode", ("measured", "reversed-attachments", "segment-dispatch-proxy", "missing", "arc-refused", "no-arc", "two-arcs", "wrong-value", "coordinate-copy", "dangling", "unknown-dangling", "wrong-circle-owner", "wrong-circle-type", "wrong-circle-id", "wrong-attachment-types", "extra-attachment"))
def test_direct_relative_axis_dimension_measures_real_wizard_point_and_cut_circle(monkeypatch, mode) -> None:
    point, circle, copy = object(), _native_sketch_segment(kind=1), object()
    selections = []
    picks = []
    ends = {1: 1 if mode == "two-arcs" else 0, 2: 0 if mode == "no-arc" else 1}
    attached_circle = _native_sketch_segment(
        owner="OtherProfile" if mode == "wrong-circle-owner" else "ActualLocationProfile",
        kind=0 if mode == "wrong-circle-type" else 1,
        identifiers=(2, 1) if mode == "wrong-circle-id" else (1, 2),
    ) if mode in ("segment-dispatch-proxy", "wrong-circle-owner", "wrong-circle-type", "wrong-circle-id") else circle
    attached = (copy if mode == "coordinate-copy" else point, attached_circle)
    types = (11, 11) if mode == "wrong-attachment-types" else (11, 10)
    if mode == "reversed-attachments":
        attached, types = attached[::-1], types[::-1]
    if mode == "extra-attachment":
        attached, types = (*attached, object()), (*types, 11)
    annotation = SimpleNamespace(
        GetAttachedEntities3=lambda: attached,
        GetAttachedEntityTypes=lambda: types,
        IsDangling=lambda: None if mode == "unknown-dangling" else mode == "dangling",
    )
    dimension = SimpleNamespace(
        DrivenState=2, Name="",
        SystemValue=(spec.LEVER_BORE_DIA / 2.0 + (0.2 if mode == "wrong-value" else 0.0)) / 1000.0,
        GetArcEndCondition=lambda index: ends[index],
    )

    def set_end(index, condition):
        if mode == "arc-refused":
            return -1
        ends[index] = condition
        return 0

    dimension.SetArcEndCondition = set_end
    display = SimpleNamespace(GetDimension2=lambda _index: dimension, GetAnnotation=lambda: annotation, ShowParenthesis=True)

    def horizontal(*_position):
        assert selections == [(point, "ISketchPoint", False), (circle, "ISketchSegment", True)]
        assert picks == [circle], "the actual rim must be picked before creating the dimension"
        return None if mode == "missing" else display

    manager = SimpleNamespace(
        GetSelectedObjectCount2=lambda _mark: len(selections),
        GetSelectedObject6=lambda index, _mark: selections[index - 1][0],
        GetSelectedObjectType3=lambda index, _mark: (11, 10)[index - 1],
    )
    model = SimpleNamespace(ClearSelection2=lambda _all: selections.clear(), AddHorizontalDimension2=horizontal, GraphicsRedraw2=lambda: None, SelectionManager=manager, FeatureManager=_native_inventory(circle, attached_circle))
    adapter = SimpleNamespace(currentModel=model, swApp=SimpleNamespace(IsSame=_native_same))
    monkeypatch.setattr(part, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(part, "_native_select", lambda _adapter, entity, interface, *, append: selections.append((entity, interface, append)))
    monkeypatch.setattr(part, "_select_bore_rim", lambda _adapter, actual: picks.append(actual))
    if mode in ("measured", "reversed-attachments", "segment-dispatch-proxy"):
        part._measure_relative_axis(adapter, point, circle, "ThumbTapToBoreRim")
        assert dimension.Name == "ThumbTapToBoreRim" and dimension.DrivenState == 1
        assert display.ShowParenthesis is False and ends == {1: 0, 2: 2}
    else:
        with pytest.raises(RuntimeError):
            part._measure_relative_axis(adapter, point, circle, "ThumbTapToBoreRim")


@pytest.mark.parametrize("mode", ("retained", "bad-radius", "wrong-count", "wrong-circle", "set-refused", "stale-pick", "unavailable-pick", "bad-transform"))
def test_native_rim_pick_uses_actual_circle_and_sketch_to_model_transform(monkeypatch, mode) -> None:
    from solidworks_mcp.adapters import com_variant
    import _telemetry

    events = []
    monkeypatch.setattr(_telemetry, "info", lambda message, **fields: events.append((message, fields)))

    local = (0.00425, 0.01995, 0.0)
    inverse = object()
    calls = []
    retained = [None]
    point = object()
    circle = _native_sketch_segment(kind=1)
    circle.GetCenterPoint2 = lambda: SimpleNamespace(X=0.001, Y=0.01995)
    circle.GetRadius = lambda: -1.0 if mode == "bad-radius" else 0.00325

    def create_point(coordinates):
        assert tuple(coordinates) == pytest.approx(local)

        def multiply(actual_transform):
            assert actual_transform is inverse, "a model-to-sketch transform is not its inverse"
            x, y, z = coordinates
            return SimpleNamespace(ArrayData=(float("nan"),) if mode == "bad-transform" else (z + 0.4, y + 0.2, -x + 0.3))

        return SimpleNamespace(MultiplyTransform=multiply)

    def set_point(index, mark, x, y, z):
        assert (index, mark) == (2, -1)
        calls.append((x, y, z))
        retained[0] = (0.3 - z, y - 0.2, x - 0.4)
        return mode != "set-refused"

    manager = SimpleNamespace(
        GetSelectedObjectCount2=lambda _mark: 1 if mode == "wrong-count" else 2,
        GetSelectedObject6=lambda index, _mark: point if index == 1 else object() if mode == "wrong-circle" else circle,
        GetSelectedObjectType3=lambda index, _mark: (11, 10)[index - 1],
        SetSelectionPoint2=set_point,
        GetSelectionPointInSketchSpace2=lambda _index, _mark: None if mode == "unavailable-pick" else (0.0, 0.0, 0.0) if mode == "stale-pick" else retained[0],
    )
    sketch = SimpleNamespace(ModelToSketchTransform=SimpleNamespace(Inverse=lambda: inverse))
    model = SimpleNamespace(GetActiveSketch2=lambda: sketch, SelectionManager=manager, FeatureManager=_native_inventory(circle))
    application = SimpleNamespace(
        GetMathUtility=lambda: SimpleNamespace(CreatePoint=create_point),
        IsSame=_native_same,
    )
    adapter = SimpleNamespace(currentModel=model, swApp=application)
    monkeypatch.setattr(part, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(com_variant, "double_array", lambda values: values)
    if mode == "retained":
        part._select_bore_rim(adapter, circle)
        assert calls == [pytest.approx((0.4, 0.21995, 0.29575))]
    else:
        with pytest.raises(RuntimeError):
            part._select_bore_rim(adapter, circle)
    if mode in ("retained", "set-refused", "stale-pick", "unavailable-pick"):
        message, fields = events[-1]
        assert fields["operation_stage"] == "bore-rim.selection-point-readback"
        assert fields["rim_sketch_m"] == pytest.approx(local)
        assert fields["requested_model_m"] == pytest.approx((0.4, 0.21995, 0.29575))
        assert fields["selection_point_accepted"] is (mode != "set-refused")
        assert "retained_sketch=" in message


@pytest.mark.parametrize("mode", ("retained", "different-segment-dispatch", "unknown-segment-dispatch", "unknown-segment-self", "one-selected", "missing-object", "wrong-point", "unknown-point", "unknown-point-self", "wrong-selection-type", "wrong-owner", "wrong-kind", "wrong-id", "unknown-owner", "invalid-id"))
def test_selection_diagnostics_discriminate_native_segment_identity(monkeypatch, mode) -> None:
    import _telemetry

    point, circle = object(), _native_sketch_segment(kind=1)
    selected_point = object() if mode in ("wrong-point", "unknown-point") else point
    returned_circle = _native_sketch_segment(
        owner="OtherProfile" if mode == "wrong-owner" else "ActualLocationProfile",
        kind=0 if mode == "wrong-kind" else 1,
        identifiers=(2, 1) if mode == "wrong-id" else (1,) if mode == "invalid-id" else (1, 2),
    )
    if mode == "unknown-owner":
        returned_circle.GetSketch = lambda: None
    selected = (point,) if mode == "one-selected" else (selected_point, None if mode == "missing-object" else returned_circle)
    selected_types = (11, 2 if mode == "wrong-selection-type" else 10)[:len(selected)]
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
            "unknown-owner": "segment identity unavailable",
            "invalid-id": "segment identity unavailable",
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
    assert f"count={len(selected)}" in message and "IsSame=" in message
    if mode in accepted:
        assert fields["selected_segment_identity"] == fields["expected_segment_identity"] == repr(("ActualLocationProfile", 1, 1, 2))
    if mode == "different-segment-dispatch":
        assert fields["identity_codes"] == (1, 0)
    if mode == "unknown-segment-dispatch":
        assert fields["identity_codes"] == (1, -1)
    if mode == "unknown-segment-self":
        assert fields["self_identity_codes"] == (1, -1)


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


@pytest.mark.parametrize("mode", ("native-proxy", "wrong-point", "wrong-circle-id", "dangling", "unknown-dangling", "missing-attachment", "wrong-value", "wrong-band", "wrong-end"))
def test_rebuilt_relative_witness_retains_native_identity_value_band_and_arc_end(monkeypatch, mode) -> None:
    source_circle, point = object(), object()
    circle = _native_sketch_segment(owner="LeverBoreLocationProfile", kind=1)
    circle.GetRadius = lambda: spec.LEVER_BORE_DIA / 2000.0
    circle.GetRelations = lambda: (SimpleNamespace(GetDefinitionEntities2=lambda: (source_circle,)),)
    attached_circle = _native_sketch_segment(
        owner="LeverBoreLocationProfile", kind=1,
        identifiers=(2, 1) if mode == "wrong-circle-id" else (1, 2),
    )
    attached = (object() if mode == "wrong-point" else point, attached_circle)
    if mode == "missing-attachment":
        attached = (point,)
    annotation = SimpleNamespace(
        GetAttachedEntities3=lambda: attached,
        GetAttachedEntityTypes=lambda: (11, 10)[:len(attached)],
        IsDangling=lambda: None if mode == "unknown-dangling" else mode == "dangling",
    )
    display = SimpleNamespace(ShowParenthesis=False, GetAnnotation=lambda: annotation)
    dimension = SimpleNamespace(
        DrivenState=1,
        SystemValue=(spec.LEVER_BORE_DIA / 2.0 + (0.2 if mode == "wrong-value" else 0.0)) / 1000.0,
        Tolerance=SimpleNamespace(
            Type=2,
            GetMinValue=lambda: -(part.RELATIVE_AXIS_BAND + (0.1 if mode == "wrong-band" else 0.0)) / 1000.0,
            GetMaxValue=lambda: part.RELATIVE_AXIS_BAND / 1000.0,
        ),
        GetArcEndCondition=lambda index: 0 if index == 1 else 1 if mode == "wrong-end" else 2,
    )
    sketch = SimpleNamespace(GetSketchSegments=lambda: (circle,), GetConstrainedStatus=lambda: 3)
    model = SimpleNamespace(FeatureByName=lambda _name: SimpleNamespace(GetSpecificFeature2=lambda: sketch), FeatureManager=_native_inventory(circle, attached_circle))
    adapter = SimpleNamespace(currentModel=model, swApp=SimpleNamespace(IsSame=_native_same))
    monkeypatch.setattr(part, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(part, "_location_sources", lambda _adapter: {"LeverBoreLocationProfile": ("Right", source_circle, "ISketchSegment", ())})
    monkeypatch.setattr(part, "_tap_placement_points", lambda _adapter: {"ThumbTapToBoreRim": point})
    monkeypatch.setattr(part, "_named_dimension", lambda _adapter, _feature, _name: (display, dimension))
    if mode == "native-proxy":
        # The annotation's native proxy is deliberately not the selected Python
        # object; only its documented owning sketch/type/ID identifies it.
        assert attached_circle is not circle
        part._assert_location_profiles(adapter)
    else:
        with pytest.raises(RuntimeError):
            part._assert_location_profiles(adapter)


@pytest.mark.parametrize("mode", (
    "child-owner", "3d-owner", "no-match", "ambiguous", "unknown-match",
    "bool-match", "bad-owner-self", "bad-candidate-self", "null-specific",
    "null-inventory", "null-feature", "bad-feature-type", "matrix-name", "readback-error",
))
def test_segment_owner_is_resolved_only_through_actual_feature_inventory(monkeypatch, mode) -> None:
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
            "matrix-name": "invalid native segment owner feature name",
            "readback-error": "specific sketch readback unavailable",
        }[mode]
        with pytest.raises(RuntimeError, match=reason):
            part._segment_identity(adapter, segment, stage="owner-control", role="selected")
    assert len(events) == 1
    message, fields = events[0]
    assert fields["operation_stage"] == "owner-control"
    assert fields["identity_role"] == "selected"
    assert fields["segment_type"] == 1 and fields["segment_ids"] == (1, 2)
    assert "candidates=" in message and "owner_self=" in message
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


@pytest.mark.parametrize("mode", ("retained", "wrong-point", "bad-point-self", "wrong-owner", "unavailable-readback"))
def test_attachment_failures_report_actual_native_state_before_raising(monkeypatch, mode) -> None:
    import _telemetry

    point = object()
    circle = _native_sketch_segment(kind=1)
    attached_circle = _native_sketch_segment(owner="OtherProfile" if mode == "wrong-owner" else "ActualLocationProfile", kind=1)
    attached_point = object() if mode == "wrong-point" else point

    def entities():
        if mode == "unavailable-readback":
            raise RuntimeError("native attachment readback unavailable")
        return attached_circle, attached_point

    def same(left, right):
        if mode == "bad-point-self" and left is point and right is point:
            return -1
        return _native_same(left, right)

    annotation = SimpleNamespace(GetAttachedEntities3=entities, GetAttachedEntityTypes=lambda: (10, 11), IsDangling=lambda: False)
    display = SimpleNamespace(GetAnnotation=lambda: annotation)
    adapter = SimpleNamespace(
        currentModel=SimpleNamespace(FeatureManager=_native_inventory(circle, attached_circle)),
        swApp=SimpleNamespace(IsSame=same),
    )
    events = []
    monkeypatch.setattr(part, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(_telemetry, "info", lambda message, **fields: events.append((message, fields)))
    if mode == "retained":
        part._assert_relative_attachment(adapter, display, point, circle, name="TapToBoreRim", stage="after-rebuild")
    else:
        with pytest.raises(RuntimeError, match="readback unavailable" if mode == "unavailable-readback" else "attachment identity differs"):
            part._assert_relative_attachment(adapter, display, point, circle, name="TapToBoreRim", stage="after-rebuild")
    message, fields = events[-1]
    assert fields["operation_stage"] == "after-rebuild"
    assert "point_self=" in message and "segment=" in message
    if mode == "unavailable-readback":
        assert "readback unavailable" in fields["attachment_readback_error"]
    else:
        assert fields["attachment_count"] == 2
        assert fields["attached_types"] == (10, 11)
        assert fields["expected_segment_identity"] == repr(("ActualLocationProfile", 1, 1, 2))
    if mode == "wrong-owner":
        assert fields["attached_segment_identity"] == repr(("OtherProfile", 1, 1, 2))
