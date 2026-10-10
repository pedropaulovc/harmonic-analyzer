"""Offline contracts for the magnifying-bracket drawing."""

from __future__ import annotations

from pathlib import Path

import build_mg_magnifying_bracket as part
import draw_mg_magnifying_bracket as drawing
import mg_magnifying_bracket_spec
from _drawing_registry import DRAWINGS_BY_NAME


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/mg-magnifying-bracket.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/mg-magnifying-bracket.pdf")
    assert drawing.PNG.as_posix().endswith("/png/mg-magnifying-bracket_drawing.png")
    assert (
        DRAWINGS_BY_NAME["mg_magnifying_bracket"].script
        == Path(drawing.__file__).resolve()
    )


def test_spec_is_the_single_source_of_the_marked_dimension_set() -> None:
    assert part.DRAWING_DIMENSIONS is mg_magnifying_bracket_spec.DRAWING_DIMENSIONS
    marked = set().union(*mg_magnifying_bracket_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.TOP_KEEP) | set(drawing.FRONT_KEEP) | set(drawing.BACK_KEEP) | set(drawing.RIGHT_KEEP)
    assert kept == marked
    assert marked == {"ArmWidth", "ArmDepth", "FlangeWidth", "FlangeDepth", "FlangeHeight", "MountingX0", "MountingX1", "MountingY0"}


def test_arm_and_flange_dim_names_are_disambiguated() -> None:
    # Arm + flange are both extruded rectangles emitting bare "Width"/"Depth";
    # the build renames them per-feature so the top view's keep map is
    # unambiguous.  The collision would otherwise repoint the wrong dimension.
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert '"ArmWidth", "ArmDepth"' in source
    assert '"FlangeWidth", "FlangeDepth"' in source


def test_bracket_is_uncoupled_from_the_assembly_nominals() -> None:
    # The magnifier assembly places the bracket BY NAME and mates it by named
    # references, so it imports no bracket Python constant -- hence one _spec
    # module is right (no _geom split).
    assert not Path(part.__file__).with_name("magnifying_bracket_geom.py").exists()
    assembly = Path(part.__file__).with_name("build_mg_magnifier_assembly.py").read_text(
        encoding="utf-8"
    )
    assert "from build_mg_magnifying_bracket import" not in assembly


def test_notes_carry_the_collar_and_fit_that_have_no_marked_dim() -> None:
    notes = mg_magnifying_bracket_spec.DRAWING_NOTES
    assert "Ø12 OD" in notes
    assert "Ø6.2" in notes
    assert "AISI 1018" not in notes
    assert "BLACK-OXIDE" not in notes
    assert "DEBURR" not in notes and "BREAK SHARP" not in notes
    assert "X.XX" not in notes and "X.XXX" not in notes
    assert "MATCH-DRILLED" not in notes
    assert "THICKNESS" not in notes
    assert "#4" not in notes and "CENTRES" not in notes
    assert "SEAT ON SUMMING-LEVER FRONT" in notes
    assert "UNDRILLED" not in notes and "DO NOT RELEASE" not in notes


def test_collar_bore_takes_the_center_mark() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("auto_center_marks(") == 1
    assert "curate_hidden_dimensions(" in source
    assert "add_native_hole_callout(" in source


def test_mounting_pattern_consumes_joint_contract() -> None:
    import magnifying_bracket_joint_layout as joint
    assert part.FLANGE_X is joint.SIDE_PLATE_X
    assert part.FLANGE_Y is joint.SIDE_PLATE_Y
    assert part.FLANGE_Z is joint.SIDE_PLATE_Z
    assert part.BRACKET_HOLE_POINTS is joint.BRACKET_HOLE_POINTS
    assert part.CLEARANCE_SPEC is joint.CLEARANCE_SPEC
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert 'name="MountingCounterbores"' in source
    assert "(0.0, 0.0, -1.0)" in source
    assert "cut_volume" in source


def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    config = _config.parts("mg-magnifying-bracket")
    assert config["material"] == config["material_specification"]
    assert config["finish"]
    assert int(config["quantity"]) == 1


def test_mounting_rim_scan_uses_back_visible_entry_plane(monkeypatch) -> None:
    from types import SimpleNamespace
    import magnifying_bracket_joint_layout as joint
    front = object()
    calls = []

    def circle_at(center, radius, *, axis, label):
        calls.append((center, radius, axis))
        return SimpleNamespace(edge=object())

    def scan(view, *, label):
        assert view is front
        return SimpleNamespace(circle_at=circle_at)

    monkeypatch.setattr(drawing, "scan_view_edges", scan)
    assert len(drawing._mounting_rims(front)) == len(joint.BRACKET_HOLE_POINTS)
    assert [call[0] for call in calls] == [
        (point[0], point[1], joint.SIDE_PLATE_Z[0])
        for point in joint.BRACKET_HOLE_POINTS
    ]
    assert all(call[1] == joint.COUNTERBORE_DIA / 2.0 for call in calls)


def test_counterbore_volume_and_native_bands() -> None:
    import magnifying_bracket_joint_layout as joint
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "CLEARANCE_DIA ** 2 * SIDE_PLATE_THICKNESS" in source
    assert "(COUNTERBORE_DIA ** 2 - CLEARANCE_DIA ** 2) * COUNTERBORE_DEPTH" in source
    assert joint.CLEARANCE_DIA == 2.591
    assert joint.COUNTERBORE_DIA == 3.8
    assert joint.COUNTERBORE_DEPTH == 1.55
    assert joint.SIDE_PLATE_THICKNESS == 3.175
    assert joint.PLATE_THICKNESS_BAND == 0.05
    assert joint.COUNTERBORE_DEPTH_BAND == 0.05
    assert '"FlangeProfile", "FlangeDepth", PLATE_THICKNESS_BAND' in source
    assert '"MountingCounterbores", native_names["CounterBoreDepth"], COUNTERBORE_DEPTH_BAND' in source
    assert '"MountingCounterbores", native_names["CounterBoreDiameter"], 0.0, 0.10' in source
    assert "apply_drawing_precision(adapter, DRAWING_PRECISION)" in source
    assert part.DRAWING_PRECISION["FlangeProfile"]["FlangeDepth"] == 3
    assert "MountingCounterbores" not in part.DRAWING_PRECISION
    assert "#4" not in source


def test_counterbore_entry_view_callout_and_feature_origin() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert '"*Back", *BACK_CENTER' in source
    assert 'process="DRILL / COUNTERBORE"' in source
    assert "set_hidden_lines_removed(adapter, back)" in source
    assert '"MountingCoordinates": ("MountingX0", "MountingX1", "MountingY0")' in source
    assert "curate_hidden_dimensions(" in source


def test_coordinates_and_hole_dimensions_are_owned_by_model() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "start = (FLANGE_X[0], FLANGE_Y[0])" in source
    assert 'name_last_feature(adapter, "MountingCoordinates")' in source
    assert 'set_dimension_symmetric_tolerance(adapter, "MountingCoordinates", name, POSITION_BAND)' in source
    assert "model.BlankSketch()" in source
    assert "feature.GetFirstDisplayDimension()" in source
    assert "feature.GetNextDisplayDimension(display)" in source
    assert "resolved[name] = str(dimensions[0].Name)" in source
    assert "dimensions[0].Name =" not in source
    assert "expected one native" in source
    assert mg_magnifying_bracket_spec.DRAWING_POSITION_BAND == 0.05
    assert f"COUNTERBORE FLOOR {mg_magnifying_bracket_spec.GRIP_MIN:.3f} MIN." in mg_magnifying_bracket_spec.DRAWING_NOTES


def test_flange_height_is_native_and_primary_views_stay_aligned() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert 'height = flange.Parameter("D1")' in source
    assert 'height.Name = "FlangeHeight"' in source
    assert "(FLANGE_Y[1] - FLANGE_Y[0])" in source
    assert part.DRAWING_PRECISION["Flange"]["FlangeHeight"] == 2
    assert drawing.FRONT_KEEP.keys() == {"FlangeHeight"}
    assert drawing.TOP_CENTER[0] == drawing.FRONT_CENTER[0]
    assert drawing.TOP_CENTER[1] == drawing.RIGHT_CENTER[1]
    assert drawing.BACK_CENTER[0] != drawing.FRONT_CENTER[0]
    drawing_source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert '"*Front", *FRONT_CENTER' in drawing_source


def test_native_counterbore_dimensions_keep_names_and_route_annotations(monkeypatch) -> None:
    """Offline routing contract, not proof of native SOLIDWORKS geometry."""
    from types import SimpleNamespace
    import pytest
    import _appearance
    import _com
    import _custom_properties
    import _feature_tree
    import _part_checks
    import _part_properties
    import _part_save
    import _rebuild
    import _session
    import _sketch
    import _sketch_rectangle

    class WizardDimension:
        def __init__(self, full_name, nominal):
            self.FullName = full_name
            self.SystemValue = nominal / 1000.0

        @property
        def Name(self):
            return self.FullName.split("@")[0]

        @Name.setter
        def Name(self, value):
            raise AssertionError("Hole Wizard dimension identifiers must not be renamed")

    height = SimpleNamespace(Name="D1", SystemValue=12.7 / 1000.0)
    native = [
        WizardDimension("Thru Hole Dia.@MountingCounterbores", 2.591),
        WizardDimension("Counterbore Dia.@MountingCounterbores", 3.8),
        WizardDimension("Counterbore Depth@MountingCounterbores", 1.55),
    ]
    original_names = [dim.Name for dim in native]
    displays = [SimpleNamespace(GetDimension=lambda dim=dim: dim) for dim in native]
    holes = SimpleNamespace(
        GetFirstDisplayDimension=lambda: displays[0] if displays else None,
        GetNextDisplayDimension=lambda current: (
            displays[displays.index(current) + 1]
            if displays.index(current) + 1 < len(displays) else None
        ),
    )
    features = {
        "Flange": SimpleNamespace(Parameter=lambda name: height if name == "D1" else None),
        "MountingCounterbores": holes,
    }
    adapter = SimpleNamespace(currentModel=SimpleNamespace(FeatureByName=features.get))
    monkeypatch.setattr(_appearance, "_early_bound", lambda value, interface: value)
    monkeypatch.setattr(_com, "_early_bound", lambda value, interface: value)
    monkeypatch.setattr(_custom_properties, "_early_bound", lambda value, interface: value)
    monkeypatch.setattr(_feature_tree, "_early_bound", lambda value, interface: value)
    monkeypatch.setattr(_part_checks, "_early_bound", lambda value, interface: value)
    monkeypatch.setattr(_part_properties, "_early_bound", lambda value, interface: value)
    monkeypatch.setattr(_part_save, "_early_bound", lambda value, interface: value)
    monkeypatch.setattr(_rebuild, "_early_bound", lambda value, interface: value)
    monkeypatch.setattr(_session, "_early_bound", lambda value, interface: value)
    monkeypatch.setattr(_sketch, "_early_bound", lambda value, interface: value)
    monkeypatch.setattr(_sketch_rectangle, "_early_bound", lambda value, interface: value)
    resolved = part._resolve_native_mounting_dimensions(adapter)
    assert height.Name == "FlangeHeight"
    assert resolved == {
        "HoleDiameter": "Thru Hole Dia.",
        "CounterBoreDiameter": "Counterbore Dia.",
        "CounterBoreDepth": "Counterbore Depth",
    }
    calls = []
    monkeypatch.setattr(part, "set_dimension_symmetric_tolerance", lambda *args: calls.append(("symmetric", args)))
    monkeypatch.setattr(part, "set_dimension_bilateral_tolerance", lambda *args: calls.append(("bilateral", args)))
    monkeypatch.setattr(part, "set_dimension_display_precision", lambda *args: calls.append(("precision", args)))
    part._apply_native_mounting_annotations(adapter, resolved)
    assert calls == [
        ("symmetric", (adapter, "MountingCounterbores", "Counterbore Depth", 0.05)),
        ("bilateral", (adapter, "MountingCounterbores", "Counterbore Dia.", 0.0, 0.10)),
        ("precision", (adapter, "MountingCounterbores", "Thru Hole Dia.", 3)),
        ("precision", (adapter, "MountingCounterbores", "Counterbore Dia.", 2)),
        ("precision", (adapter, "MountingCounterbores", "Counterbore Depth", 2)),
    ]
    assert [dim.Name for dim in native] == original_names
    duplicate = WizardDimension("Second Counterbore Dia.@MountingCounterbores", 3.8)
    displays.append(SimpleNamespace(GetDimension=lambda: duplicate))
    with pytest.raises(RuntimeError, match="expected one native CounterBoreDiameter, found 2"):
        part._resolve_native_mounting_dimensions(adapter)
    displays.pop()
    missing = displays.pop(1)
    with pytest.raises(RuntimeError, match="expected one native CounterBoreDiameter, found 0"):
        part._resolve_native_mounting_dimensions(adapter)
    displays.insert(1, missing)
    native[1].SystemValue = 3.9 / 1000.0
    with pytest.raises(RuntimeError, match="expected one native CounterBoreDiameter, found 0"):
        part._resolve_native_mounting_dimensions(adapter)
    native[1].SystemValue = 3.8 / 1000.0
    native[1].FullName = "Counterbore Depth@MountingCounterbores"
    with pytest.raises(RuntimeError, match="expected one native CounterBoreDiameter, found 0"):
        part._resolve_native_mounting_dimensions(adapter)
    assert height.Name == "FlangeHeight"


def test_final_forced_volume_guard_follows_annotations_before_publication() -> None:
    """Source ordering only; the parent must still validate rebuilt native geometry."""
    import ast

    source = Path(part.__file__).read_text(encoding="utf-8")
    build = next(
        node for node in ast.parse(source).body
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "build"
    )
    rebuild, guard, publish = build.body[-3:]
    assert isinstance(rebuild, ast.Expr) and isinstance(rebuild.value, ast.Await)
    assert rebuild.value.value.func.id == "force_rebuild"
    assert isinstance(guard, ast.Expr) and isinstance(guard.value, ast.Await)
    call = guard.value.value
    assert call.func.id == "volume_check"
    assert call.args[1].value == "final magnifying-bracket (annotations neutral)"
    assert call.args[2].id == "expected"
    assert ast.unparse(call.args[3]) == "0.02 * cut_volume"
    assert isinstance(publish, ast.Return) and isinstance(publish.value, ast.Await)
    assert publish.value.value.func.id == "save_part_and_images"
    for mutation in (
        "_resolve_native_mounting_dimensions",
        "_mounting_coordinate_dimensions",
        "set_dimension_symmetric_tolerance",
        "_apply_native_mounting_annotations",
        "apply_drawing_precision",
        "clear_dimensions_for_drawing",
        "mark_dimensions_for_drawing",
        "apply_drawing_properties",
    ):
        calls = [
            node for node in ast.walk(build)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            and node.func.id == mutation
        ]
        assert calls, mutation
        assert all(node.lineno < rebuild.lineno for node in calls), mutation
