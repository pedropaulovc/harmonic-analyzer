"""Real triangle topology regressions and COM-free source-slicing contracts."""

from __future__ import annotations

import hashlib
import math
import sys
from types import ModuleType

import numpy as np
import pytest
import trimesh

from diagnostics import collect_dt_swing_gravity as collector


TETRA_FACES = np.array([[0, 2, 1], [0, 1, 3], [0, 3, 2], [1, 2, 3]])


def _tetra_with_seam(lower, upper):
    vertices = np.array(
        [
            [lower, 0.0, 0.0],
            [lower + 1.0, 0.0, 0.0],
            [lower, 1.0, 0.0],
            [lower, 0.0, 1.0],
        ]
    )
    triangles = vertices[TETRA_FACES].copy()
    # One occurrence of the common corner comes from the other tessellated
    # B-rep face. Every facet still has its own STL-style vertex indices.
    triangles[1, 0, 0] = upper
    return trimesh.Trimesh(
        vertices=triangles.reshape((-1, 3)),
        faces=np.arange(12).reshape((-1, 3)),
        process=False,
    )


def _write_stl(tmp_path, mesh):
    path = tmp_path / "native.STL"
    path.write_bytes(trimesh.exchange.stl.export_stl(mesh))
    return path


def test_sub_ulp_seam_weld_crosses_rounding_grid_boundary():
    tolerance = collector.WELD_TOLERANCE_MM
    boundary = 2.0 + tolerance / 2.0
    ulp = float(np.spacing(np.float32(2.0)))
    lower, upper = boundary - 0.1 * ulp, boundary + 0.1 * ulp
    assert 0.0 < upper - lower < ulp < tolerance
    assert np.round(lower / tolerance) != np.round(upper / tolerance)
    mesh = _tetra_with_seam(lower, upper)
    exact = mesh.copy()
    exact.merge_vertices(digits_vertex=12)
    assert not exact.is_watertight  # positive control: the seam really is split

    welded = collector.weld_vertices(mesh)
    assert welded.is_watertight
    assert welded.is_winding_consistent
    assert welded.is_volume
    assert len(welded.vertices) == 4
    assert len(welded.faces) == len(mesh.faces) == 4
    assert welded.volume == pytest.approx(1.0 / 6.0, rel=0.0, abs=1e-12)
    np.testing.assert_allclose(
        welded.center_mass,
        [lower + 0.25, 0.25, 0.25],
        rtol=0.0,
        atol=1e-12,
    )
    # Representatives are native coordinates, not averaged or grid-snapped.
    assert all(
        any(np.array_equal(v, original) for original in mesh.vertices)
        for v in welded.vertices
    )


def test_binary_float32_seam_reports_real_topology_and_provenance(tmp_path):
    boundary = 2.0 + collector.WELD_TOLERANCE_MM / 2.0
    nearest = np.float32(boundary)
    if float(nearest) < boundary:
        lower, upper = nearest, np.nextafter(nearest, np.float32(np.inf))
    else:
        lower, upper = np.nextafter(nearest, np.float32(-np.inf)), nearest
    path = _write_stl(tmp_path, _tetra_with_seam(float(lower), float(upper)))
    row = collector.read_mesh(path)
    assert row["watertight"] is True
    assert row["winding_consistent"] is True
    assert row["input_faces"] == row["faces"] == 4
    assert row["input_vertices"] == 12
    assert row["welded_vertices"] == 4
    assert row["weld_tolerance_mm"] == 1e-5
    assert row["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert row["native_mesh_volume_mm3"] == pytest.approx(1.0 / 6.0, abs=1e-7)


def test_actual_hole_is_rejected_without_filling_or_removing_faces(tmp_path):
    mesh = _tetra_with_seam(2.0, 2.0)
    open_mesh = trimesh.Trimesh(
        vertices=mesh.vertices,
        faces=mesh.faces[:-1],
        process=False,
    )
    welded = collector.weld_vertices(open_mesh)
    assert len(welded.faces) == len(open_mesh.faces) == 3
    assert not welded.is_watertight
    assert welded.is_winding_consistent
    with pytest.raises(collector.MeshTopologyError) as caught:
        collector.read_mesh(_write_stl(tmp_path, open_mesh))
    assert caught.value.watertight is False
    assert caught.value.winding_consistent is True
    assert "open or non-manifold edges" in str(caught.value)
    assert "inconsistent winding" not in str(caught.value)


def test_inconsistent_winding_is_rejected_without_reorientation(tmp_path):
    mesh = _tetra_with_seam(2.0, 2.0)
    mesh.faces[0] = mesh.faces[0, ::-1]
    welded = collector.weld_vertices(mesh)
    assert len(welded.faces) == 4
    assert welded.is_watertight
    assert not welded.is_winding_consistent
    with pytest.raises(collector.MeshTopologyError) as caught:
        collector.read_mesh(_write_stl(tmp_path, mesh))
    assert caught.value.watertight is True
    assert caught.value.winding_consistent is False
    assert "inconsistent winding" in str(caught.value)
    assert "open or non-manifold edges" not in str(caught.value)


def test_consistently_inward_mesh_is_not_silently_flipped(tmp_path):
    mesh = _tetra_with_seam(2.0, 2.0)
    mesh.faces = mesh.faces[:, ::-1]
    with pytest.raises(RuntimeError, match="invalid positive volume/COM"):
        collector.read_mesh(_write_stl(tmp_path, mesh))


def test_source_slices_do_not_import_builders_or_transform_common(tmp_path):
    scripts = tmp_path / "cad/scripts"
    scripts.mkdir(parents=True)
    (scripts / "build_test.py").write_text(
        "from _com import forbidden\n"
        "from _transforms import axis\n"
        "raise RuntimeError('builder module executed')\n"
        "VALUE = 2 * axis(0.0)\n",
        encoding="utf-8",
    )
    (scripts / "_transforms.py").write_text(
        "import math\nfrom _com import forbidden\n"
        "raise RuntimeError('transform module executed')\n"
        "def axis(angle):\n    return math.cos(angle)\n",
        encoding="utf-8",
    )
    reader = collector.SourceSlices(tmp_path)
    with collector.source_environment(tmp_path):
        assert reader.get("build_test.py", "VALUE") == 2.0
        with pytest.raises(ImportError, match="COM/build import is forbidden"):
            reader.get("build_test.py", "forbidden")
    assert set(reader.hashes) == {
        "cad/scripts/build_test.py",
        "cad/scripts/_transforms.py",
    }


@pytest.mark.parametrize(
    "name", ["build_test", "_com", "_session", "pythoncom", "win32com.client"]
)
def test_forbidden_imports_stay_blocked_when_cached(tmp_path, monkeypatch, name):
    scripts = tmp_path / "cad/scripts"
    scripts.mkdir(parents=True)
    (scripts / "build_test.py").write_text(f"import {name} as bad\nVALUE = bad.VALUE\n")
    module = ModuleType(name)
    module.VALUE = 3
    monkeypatch.setitem(sys.modules, name, module)
    with pytest.raises(ImportError, match="COM/build import is forbidden"):
        collector.SourceSlices(tmp_path).get("build_test.py", "VALUE")


@pytest.mark.parametrize("units,origin", [(1, True), (0, False)])
def test_export_units_refuse_scaling_or_origin_guessing(tmp_path, units, origin):
    scripts = tmp_path / "cad/scripts"
    scripts.mkdir(parents=True)
    (scripts / "_preferences.py").write_text(
        "PREF_STL_UNITS = 211\nTOGGLE_STL_NO_TRANSLATE = 71\n"
        f"STL_EXPORT_PREFERENCES = Preferences(integers={{PREF_STL_UNITS: {units}}}, "
        f"toggles={{TOGGLE_STL_NO_TRANSLATE: {origin}}})\n",
        encoding="utf-8",
    )
    (scripts / "_part_save.py").write_text(
        "async def export_part_stl(adapter):\n"
        "    await enforce_preferences(adapter, STL_EXPORT_PREFERENCES)\n",
        encoding="utf-8",
    )
    with pytest.raises(RuntimeError, match="swMM|part-local origin"):
        collector.SourceSlices(tmp_path).export_units()


def test_report_cannot_write_inside_source_tree(tmp_path):
    with pytest.raises(RuntimeError, match="report must be outside the source tree"):
        collector.main(
            [
                "--source-root",
                str(tmp_path),
                "--outroot",
                str(tmp_path),
                "--report",
                str(tmp_path / "report.json"),
            ]
        )
    assert not (tmp_path / "report.json").exists()


@pytest.mark.parametrize(
    "source_field,new_value,report_fields",
    [
        ("DIAMETRAL_PITCH", 48.0, ("DIAMETRAL_PITCH",)),
        ("PRESSURE_ANGLE_DEG", 20.0, ("PRESSURE_ANGLE_DEG",)),
        ("CUTTER_REFERENCE_TEETH", 26, ("CUTTER_REFERENCE_TEETH",)),
        ("CUTTER_RADIAL_TRANSLATION_MM", 0.1, ("CUTTER_RADIAL_TRANSLATION_MM",)),
        ("PITCH_TOOTH_THICKNESS_MM", 0.8, ("PITCH_TOOTH_THICKNESS_MM",)),
        ("ROOT_ENVELOPE_DIA_MM", (13.0, 15.0), ("ROOT_MIN_DIA_MM",)),
        ("ROOT_ENVELOPE_DIA_MM", (14.0, 16.0), ("ROOT_MAX_DIA_MM",)),
        ("SUPPORT_OUTSIDE_DIA_MM", 18.0, ("SUPPORT_OUTSIDE_DIA_MM",)),
        ("OUTSIDE_DIA", 17.9, ("OUTSIDE_DIA",)),
        ("WHOLE_DEPTH", 1.2, ("WHOLE_DEPTH",)),
        ("MAX_CUT_DEPTH_MM", 1.8, ("MAX_CUT_DEPTH_MM",)),
        ("BASE_TANGENT_SPAN", 4.0, ("BASE_TANGENT_SPAN",)),
    ],
)
def test_fingerprint_freezes_each_actual_stock_form_dimension(
    tmp_path, source_field, new_value, report_fields
):
    scripts = tmp_path / "cad/scripts"
    scripts.mkdir(parents=True)
    for filename, names in collector.DIMENSION_SOURCES.values():
        values = {
            name: (14.0, 15.0) if name == "ROOT_ENVELOPE_DIA_MM" else index + 1.0
            for index, name in enumerate(names)
        }
        (scripts / filename).write_text(
            "\n".join(f"{name} = {value!r}" for name, value in values.items()),
            encoding="utf-8",
        )
    measured = collector.dimension_fingerprint(collector.SourceSlices(tmp_path))
    drum = measured["dt-alignment-pinion"]
    assert drum["ROOT_MIN_DIA_MM"] == 14.0
    assert drum["ROOT_MAX_DIA_MM"] == 15.0
    assert "ROOT_DIA" not in drum
    assert "AS_CUT_RADIAL_TOOTH_DEPTH" not in drum
    assert "ROOT_ENVELOPE_DIA_MM" not in drum
    assert all(
        math.isfinite(value) for row in measured.values() for value in row.values()
    )
    # A collected snapshot is independent of subsequent governing-source edits.
    filename, _names = collector.DIMENSION_SOURCES["dt-alignment-pinion"]
    with (scripts / filename).open("a", encoding="utf-8") as source:
        source.write(f"\n{source_field} = {new_value!r}\n")
    current = collector.dimension_fingerprint(collector.SourceSlices(tmp_path))
    assert current["dt-alignment-pinion"] != drum
    changed = {
        name for name, value in current["dt-alignment-pinion"].items()
        if value != drum[name]
    }
    assert changed == set(report_fields)
