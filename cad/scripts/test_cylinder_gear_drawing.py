"""Finished-fit and tooth-system contracts consumed by the native drawing."""

from __future__ import annotations

import runpy
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

import pytest

import _config
from _buildgraph import module_deps_of
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS
import build_cylinder_gear as part
from involute_gear import gear_facts
import cylinder_gear_shaft_spec as arbor
import cylinder_gear_spec as spec
import draw_cylinder_gear as drawing


def test_running_bore_limits_follow_the_finished_arbor() -> None:
    # Opposite ends of the arbor size band must not receive one fixed bore band.
    assert spec.matched_bore_limits(9.505) == pytest.approx((9.535, 9.575))
    assert spec.matched_bore_limits(9.525) == pytest.approx((9.555, 9.595))


def test_native_bore_represents_a_finished_running_fit() -> None:
    # Equal nominal bore/arbor diameters previously modeled zero clearance,
    # even though the drawing required a positive matched running clearance.
    minimum, maximum = spec.matched_bore_limits(arbor.SHAFT_DIA)
    assert minimum <= spec.BORE_DIA <= maximum
    assert spec.BORE_DIA - arbor.SHAFT_DIA == pytest.approx(0.050)


def test_blank_and_tooth_profile_follow_the_same_configured_pitch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configured_pitch = 40.0  # Deliberately differs from the current machine setting.
    original_machine = _config.machine

    def machine_value(*keys: str):
        if keys == ("gear_train", "diametral_pitch"):
            return configured_pitch
        return original_machine(*keys)

    monkeypatch.setattr(_config, "machine", machine_value)
    dimensions = runpy.run_path(spec.__file__)
    profile = gear_facts(dimensions["TEETH"], configured_pitch)
    assert dimensions["OUTSIDE_DIA"] / 2.0 == pytest.approx(profile["Ra"] * 25.4)


def test_every_marked_dimension_has_exactly_one_view_owner() -> None:
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    ownership = Counter(
        name
        for view_dimensions in (
            drawing.FRONT_KEEP,
            drawing.RIGHT_KEEP,
            drawing.NOTCH_DETAIL_DIMENSIONS,
        )
        for name in view_dimensions
    )
    assert ownership == Counter(marked)
    assert set(drawing.DIMENSION_CALLOUTS) <= marked


def test_the_part_owns_every_printed_decimal_place() -> None:
    """Policy rule 2: places are the tolerance, so the .SLDPRT carries them.

    Three places only where a three-place band rides the dimension (the
    matched bore's reference nominal, the cam eccentricity); four on the
    stacking thickness that sets the station pitch, 7.0565 +/-0.025, exact
    only at four (#743, user ruling L20 d'); the cam thickness is the one
    sheet-derived value, a parenthesised reference.
    """
    by_name = spec.DRAWING_PRECISION_BY_NAME
    assert set(by_name) == set().union(*spec.DRAWING_DIMENSIONS.values())
    assert {name for name, places in by_name.items() if places == 3} == {
        "BoreDia",
        "CamCy",
    }
    assert {name for name, places in by_name.items() if places == 4} == {
        "OverallThickness",
    }
    assert spec.DRAWING_REFERENCE_PRECISION == {"cam thickness reference": 2}
    part_source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_precision(adapter, DRAWING_PRECISION)" in part_source
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    # The sheet reads the places back and never rewrites them.
    assert "set_dimension_precision" not in source
    assert "assert_imported_precision(" in source
    assert Path(drawing.__file__).name in PRECISION_MIGRATED_DRAWINGS


@pytest.mark.parametrize(
    ("assembly_script", "reads_cylinder_spec"),
    (
        ("build_channel_assembly.py", True),
        ("build_drive_train_assembly.py", True),
        # paper-drive read the cylinder spec only through the drive-train
        # script; it now takes the crank axis from cone_line (#880).
        ("build_paper_drive_assembly.py", False),
    ),
)
def test_assembly_recipes_exclude_cylinder_drawing_prose(
    assembly_script: str, reads_cylinder_spec: bool
) -> None:
    dependencies = {
        Path(path).name
        for path in module_deps_of(Path(__file__).with_name(assembly_script))
    }
    assert ("cylinder_gear_spec.py" in dependencies) is reads_cylinder_spec
    assert dependencies.isdisjoint({"build_cylinder_gear.py", "cylinder_gear_notes.py"})


def test_stacking_thickness_is_the_held_marked_dimension() -> None:
    import cylinder_bank_layout as bank
    import cylinder_gear_notes as notes

    # The overall thickness sets every station of the solid bank (#743), so it
    # is a marked model dimension printed to four places with its own band;
    # the cam thickness between it and the face width is only a reference.
    assert spec.DRAWING_DIMENSIONS["CamBoss"] == {"OverallThickness"}
    assert spec.DRAWING_PRECISION_BY_NAME["OverallThickness"] == 4
    assert "OverallThickness" in drawing.RIGHT_KEEP
    assert f"{bank.RING_OVERHANG_MAX:.2f}" in notes.STACK_FIT_CALLOUT


class _RimEdge:
    """IEdge double of a circular boundary at ``station_mm`` along the axis."""

    def __init__(
        self,
        station_mm: float,
        *,
        radius_mm: float = spec.CAM_DIA / 2.0,
        center_y_mm: float = spec.ECCENTRICITY,
        axis: tuple[float, float, float] = (0.0, 0.0, 1.0),
    ) -> None:
        self.curve = SimpleNamespace(
            IsCircle=lambda: True,
            CircleParams=(
                0.0,
                center_y_mm / 1000.0,
                station_mm / 1000.0,
                *axis,
                radius_mm / 1000.0,
            ),
        )

    def GetCurve(self):  # noqa: N802 - the COM member name
        return self.curve


class _CamFace:
    """IFace2 double of a cylinder about the eccentric axis, cam-boss long."""

    def __init__(
        self, edges: list[_RimEdge], diameter_mm: float = spec.CAM_DIA
    ) -> None:
        self.edges = edges
        self.surface = SimpleNamespace(
            Identity=4002,  # swSurfaceTypes_e.CYLINDER_TYPE
            CylinderParams=(
                0.0,
                spec.ECCENTRICITY / 1000.0,
                0.0,
                0.0,
                0.0,
                1.0,
                diameter_mm / 2000.0,
            ),
        )

    def GetSurface(self):  # noqa: N802
        return self.surface

    def GetBox(self):  # noqa: N802
        r = spec.CAM_DIA / 2000.0
        y = spec.ECCENTRICITY / 1000.0
        return (
            -r,
            y - r,
            spec.FACE_WIDTH / 1000.0,
            r,
            y + r,
            spec.OVERALL_THICKNESS / 1000.0,
        )

    def GetEdges(self):  # noqa: N802
        return self.edges


class _CamView:
    """The right view's visible faces (swViewEntityType_Face = 3)."""

    def __init__(self, faces: list[_CamFace]) -> None:
        self.faces = faces

    def GetVisibleComponents(self):  # noqa: N802
        return ["cylinder-gear"]

    def GetVisibleEntities2(self, component, kind):  # noqa: N802
        return self.faces if kind == 3 else []


def test_cam_thickness_takes_only_the_cam_faces_two_rims() -> None:
    """Farm run 20261002T180658288Z: coordinate picks for the cam thickness
    produced a dimension reading 1570.8 -- pi/2, an angle.  The reference now
    dimensions the controlled cam face's two circular rims, and nothing else on
    it or on another cylinder: not the bore circle at the rear station, not a
    rim at another station, not the gear blank's circle."""
    shoulder = _RimEdge(spec.FACE_WIDTH)
    rear = _RimEdge(spec.OVERALL_THICKNESS, axis=(0.0, 0.0, -1.0))
    bore = _RimEdge(
        spec.OVERALL_THICKNESS, radius_mm=spec.BORE_DIA / 2.0, center_y_mm=0.0
    )
    origin = _RimEdge(0.0)
    cam = _CamFace([rear, bore, shoulder, origin])
    gear = _CamFace([_RimEdge(spec.FACE_WIDTH)], spec.OUTSIDE_DIA)

    rims = drawing._cam_thickness_rims(_CamView([gear, cam]))

    assert rims == {spec.FACE_WIDTH: shoulder, spec.OVERALL_THICKNESS: rear}
    span_mm = (
        rims[spec.OVERALL_THICKNESS].curve.CircleParams[2]
        - rims[spec.FACE_WIDTH].curve.CircleParams[2]
    ) * 1000.0
    assert span_mm == pytest.approx(spec.CAM_THICKNESS)


@pytest.mark.parametrize(
    "fault", ("missing", "radius", "center", "axis", "station", "ambiguous")
)
def test_cam_thickness_refuses_a_wrong_or_ambiguous_rim(fault: str) -> None:
    edges = [_RimEdge(spec.FACE_WIDTH)]
    if fault == "radius":
        edges.append(
            _RimEdge(spec.OVERALL_THICKNESS, radius_mm=spec.CAM_DIA / 2.0 + 1.0)
        )
    elif fault == "center":
        edges.append(
            _RimEdge(spec.OVERALL_THICKNESS, center_y_mm=spec.ECCENTRICITY + 1.0)
        )
    elif fault == "axis":
        edges.append(_RimEdge(spec.OVERALL_THICKNESS, axis=(1.0, 0.0, 0.0)))
    elif fault == "station":
        edges.append(_RimEdge(spec.OVERALL_THICKNESS + 1.0))
    elif fault == "ambiguous":
        edges.extend(
            [_RimEdge(spec.OVERALL_THICKNESS), _RimEdge(spec.OVERALL_THICKNESS)]
        )
    with pytest.raises(RuntimeError, match="expected one circular cam rim"):
        drawing._cam_thickness_rims(_CamView([_CamFace(edges)]))


@pytest.mark.parametrize("count", (0, 2))
def test_cam_thickness_refuses_a_missing_or_ambiguous_cam_face(count: int) -> None:
    faces = [
        _CamFace([_RimEdge(spec.FACE_WIDTH), _RimEdge(spec.OVERALL_THICKNESS)])
        for _ in range(count)
    ]
    with pytest.raises(RuntimeError, match=f"expected one cam face, got {count}"):
        drawing._cam_thickness_rims(_CamView(faces))
