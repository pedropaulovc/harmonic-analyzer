"""Offline drawing requirements, exact datum domains and raw STEP binding."""

from __future__ import annotations

import asyncio
import hashlib
import math
import tomllib
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml
from prechips.model import Features

import export_features as exporter
from _export_feature_faces import FeatureFaceError, face_name
from _part_pmi import _FaceGeometry, _face_matches


def _step(tmp_path: Path, stem: str) -> Path:
    labels = [face_name(feature, 1) for feature in exporter.feature_selectors(stem)]
    if stem == "ch_rocker_arm":
        labels.insert(0, face_name("pivot_bore", 1))
    rows = ["ISO-10303-21;", "HEADER;", "ENDSEC;", "DATA;"]
    rows += [f"#{index} = ADVANCED_FACE('{label}',(#1),#2,.T.);" for index, label in enumerate(labels, start=10)]
    rows += ["ENDSEC;", "END-ISO-10303-21;"]
    path = tmp_path / stem / f"{stem.replace('_', '-')}.STEP"
    path.parent.mkdir(parents=True)
    path.write_bytes("\r\n".join(rows).encode("utf-8"))
    return path


def _load(path: Path) -> dict:
    return tomllib.loads(path.read_text(encoding="utf-8"))


def _plane(normal: tuple[float, float, float], point_mm: tuple[float, float, float]) -> _FaceGeometry:
    return _FaceGeometry(None, 4001, (*normal, *(v / 1000 for v in point_mm)), normal, ())


def _owners(stem: str, geometry: _FaceGeometry) -> list[str]:
    return [
        feature for feature, selectors in exporter.feature_selectors(stem).items()
        if any(_face_matches(geometry, selector) for selector in selectors)
    ]


def test_rocker_bands_respect_native_nominals_and_displayed_general_rows() -> None:
    manifest = exporter.requirement_manifest("ch-rocker-arm")
    features = manifest["features"]
    assert manifest["general_tolerances"]["linear_1pl"] == 0.8
    assert manifest["general_tolerances"]["linear_2pl"] == 0.51
    assert manifest["general_tolerances"]["linear_3pl"] == 0.13
    assert features["hub_od"]["dia"] == [9.69, 10.71]
    assert features["hub_faces"]["length"] == [7.0565, 7.1065]
    assert features["hub_faces"]["length_nominal"] == 7.0565
    for name in ("tip_land_pos_x", "tip_land_neg_x"):
        assert features[name]["tip_land"] == [5.08, 6.10]
    for name in ("strap_datum_b", "strap_faces"):
        assert features[name]["thickness"] == [1.99, 3.01]
    assert features["rod_hole"]["dia"] == [1.994, 2.094]
    assert features["rod_hole"]["nominal_dia"] == 1.994
    assert features["rod_hole"]["precision"]["dia"] == 2
    assert features["pivot_bore"]["dia"] == [6.50, 6.53]
    assert features["rod_hole"]["at"] == pytest.approx([133.06740213488345, 16.456064115939025, 0.0])


def test_unknown_requirements_and_references_do_not_acquire_acceptance_bands() -> None:
    features = exporter.requirement_manifest("ch_rocker_arm")["features"]
    for name in ("tip_land_pos_x", "tip_land_neg_x"):
        assert features[name]["land_angle_deg"] == "unknown"
        assert features[name]["requirements"] == ["tip_land", "land_angle_deg"]
    assert features["profile_outer"]["requirements"] == ["bottom_radius", "bottom_arc_len", "mirror_symmetric"]
    assert "depth_ref" not in features["profile_outer"]["requirements"]
    assert "centre_from_pivot_ref" not in features["top_edge"]["requirements"]
    shaft = exporter.requirement_manifest("ch_pivot_shaft")
    assert "length" not in shaft["features"]["pivot_bearing"]["requirements"]
    assert shaft["datums"] == {}
    assert shaft["features"]["north_relief"]["dia"] == [5.57, 5.83]
    assert shaft["features"]["pivot_journal"]["length"] == [5.2, 6.8]


def test_rocker_datum_domains_are_only_the_drawing_bore_broad_face_and_positive_tip() -> None:
    manifest = exporter.requirement_manifest("ch_rocker_arm")
    rocker = exporter.rocker
    assert manifest["datums"]["A"]["feature"] == "pivot_bore"
    assert manifest["datums"]["B"]["feature"] == "strap_datum_b"
    assert manifest["datums"]["C"]["feature"] == "tip_land_pos_x"
    assert _owners("ch_rocker_arm", _plane((0, 0, 1), (0, 0, rocker.ARM_THICKNESS / 2))) == ["strap_datum_b"]
    assert _owners("ch_rocker_arm", _plane((0, 0, -1), (0, 0, -rocker.ARM_THICKNESS / 2))) == ["strap_faces"]
    # The authored land is radial from the top arc's endpoint. Its surface
    # normal is perpendicular to that radius, independently of selector code.
    radial_x = rocker.TOP_END_X / rocker.R_TOP
    radial_y = (rocker.TOP_END_Y - rocker.CENTER_Y) / rocker.R_TOP
    tip = (rocker.ROD_TIP_X, rocker.TOP_END_Y + rocker.TIP_FACE * radial_y, 0.0)
    assert _owners("ch_rocker_arm", _plane((-radial_y, radial_x, 0), tip)) == ["tip_land_pos_x"]
    assert _owners("ch_rocker_arm", _plane((radial_y, radial_x, 0), (-tip[0], tip[1], 0))) == ["tip_land_neg_x"]
    bottom = (rocker.BOT_END_X, rocker.CENTER_Y - math.sqrt(rocker.R_BOTTOM**2 - rocker.BOT_END_X**2))
    dx, dy = bottom[0] - tip[0], bottom[1] - tip[1]
    length = math.hypot(dx, dy)
    assert _owners("ch_rocker_arm", _plane((-dy / length, dx / length, 0), tip)) == ["profile_outer"]
    assert "datum" not in manifest["features"]["profile_outer"]
    assert "datum" not in manifest["features"]["strap_faces"]
    assert "datum" not in manifest["features"]["tip_land_neg_x"]


def test_shaft_finish_applies_only_to_south_shoulder_not_north_seat() -> None:
    shaft = exporter.shaft
    features = exporter.requirement_manifest("ch_pivot_shaft")["features"]
    assert _owners("ch_pivot_shaft", _plane((0, 0, 1), (0, 0, -shaft.JOURNAL_LENGTH))) == ["shoulder_north_face"]
    assert _owners("ch_pivot_shaft", _plane((0, 0, -1), (0, 0, shaft.SHOULDER_SOUTH_Z_MM))) == ["shoulder_thrust"]
    assert features["shoulder_north_face"]["length"] == features["shoulder_thrust"]["length"] == [0.99, 2.01]
    assert features["shoulder_north_face"]["requirements"] == ["length"]
    assert "finish_ra" not in features["shoulder_north_face"]
    assert features["shoulder_thrust"]["finish_ra"] == 1.6


def test_cone_native_tolerances_angularity_and_exact_datums() -> None:
    cone = exporter.cone
    manifest = exporter.requirement_manifest("dt_cone_pivot_post")
    features = manifest["features"]
    crank = features["crank_bore"]
    assert crank["dia"] == [11.413, 11.443]
    assert features["journal_bore"]["dia"] == [12.2558, 12.2858]
    assert features["journal_bore"]["height"] == [33.118, 33.618]
    assert cone.CRANK_ABOVE_CONE_BAND == (0.37, 0.0)
    upper, lower = cone.CRANK_ABOVE_CONE_BAND
    assert crank["separation"] == pytest.approx(
        [cone.CRANK_ABOVE_CONE + lower, cone.CRANK_ABOVE_CONE + upper],
        rel=0.0, abs=1e-12,
    )
    assert crank["height_from"] == "journal_bore"
    assert crank["height_nominal"] == pytest.approx(cone.CRANK_BORE_HEIGHT)
    assert crank["at"] == pytest.approx([0.0, cone.CRANK_BORE_HEIGHT, 0.0])
    assert crank["angularity_dia"] == 0.10
    assert crank["angularity_datums"] == ["A", "B"]
    assert "angularity_dia" in crank["requirements"]
    assert "angle_tol_deg" not in crank["requirements"]
    assert "position_dia" not in crank
    assert "height" not in crank["requirements"]
    assert "unknown" in features["journal_bore"]["requirements"]
    assert features["mount_west"]["dia"] == [7.14248, 7.24248]
    assert features["mount_west"]["nominal_dia"] == 7.14248
    assert features["mount_west"]["precision"]["dia"] == 2
    selectors = exporter.feature_selectors("dt_cone_pivot_post")
    for datum in exporter.cone.PART_DATUMS:
        assert selectors[manifest["datums"][datum.letter]["feature"]] == (datum.face,)
    # A same-diameter face away from the drawing journal must not become A.
    diameter = exporter.cone.BORE_DIA / 1000
    remote = _FaceGeometry(None, 4002, (0, 0, 0, 0, 0, 1, diameter / 2), None, (-diameter, 0, -0.1, diameter, 0.005, 0.1))
    assert not _face_matches(remote, selectors["journal_bore"][0])


def test_mount_stations_lie_in_their_own_signed_bands_and_mirror() -> None:
    features = exporter.requirement_manifest("dt_cone_pivot_post")["features"]
    west, east = features["mount_west"], features["mount_east"]
    for hole in (west, east):
        low, high = hole["station"]
        assert low < hole["station_nominal"] < high
        assert hole["station_nominal"] == hole["at"][0]
    assert west["station_nominal"] < 0 < east["station_nominal"]
    assert west["station"] == [-value for value in reversed(east["station"])]


def _plane_z(face) -> float:
    assert face.normal[:2] == (0, 0) and abs(face.normal[2]) == 1
    return face.offset_mm * face.normal[2]


def test_shaft_axial_extents_tile_the_turned_axis_with_reliefs_overlaid_at_the_shoulder() -> None:
    features = exporter.requirement_manifest("ch_pivot_shaft")["features"]
    selectors = exporter.feature_selectors("ch_pivot_shaft")
    order = ("south_dome", "pivot_bearing", "shoulder_od", "pivot_journal", "north_dome")
    spans = {name: features[name]["z_mm"] for name in (*order, "north_relief", "south_relief")}
    assert all(features[name]["frame"] == "model" and low < high for name, (low, high) in spans.items())
    for below, above in zip(order, order[1:]):
        assert spans[below][1] == pytest.approx(spans[above][0]), (below, above)
    # The shoulder's two faces bound it and the O.D.s either side.
    assert _plane_z(selectors["shoulder_north_face"][0]) == pytest.approx(spans["shoulder_od"][1])
    assert _plane_z(selectors["shoulder_thrust"][0]) == pytest.approx(spans["shoulder_od"][0])
    # Each relief lies inside its O.D., flush against one shoulder face and
    # ending at its own step face; every named patch lies inside its span.
    for groove, host, shoulder_end, step_end in (("north_relief", "pivot_journal", 0, 1), ("south_relief", "pivot_bearing", 1, 0)):
        assert spans[host][0] <= spans[groove][0] < spans[groove][1] <= spans[host][1]
        assert spans[groove][shoulder_end] == pytest.approx(spans["shoulder_od"][1 - shoulder_end])
        assert spans[groove][step_end] == pytest.approx(_plane_z(selectors[groove][1]))
    for name in ("pivot_bearing", "pivot_journal", "north_relief", "south_relief"):
        low, high = spans[name]
        assert low < selectors[name][0].contains_z_mm < high, name
    # Domes run from the end circle of the O.D. to the sphere's apex.
    for name, apex_index, base_index in (("north_dome", 1, 0), ("south_dome", 0, 1)):
        sphere = selectors[name][0]
        radius, centre = sphere.diameter_mm / 2, sphere.center_mm[2]
        apex, base = spans[name][apex_index], spans[name][base_index]
        assert abs(apex - centre) == pytest.approx(radius)
        assert features[name]["base_radius"] ** 2 + (base - centre) ** 2 == pytest.approx(radius**2)
        assert features[name]["base_radius"] * 2 == pytest.approx(features["pivot_bearing"]["dia_nominal"])


def _on_axis(point: list[float], at: list[float], axis: list[float]) -> bool:
    offset = [p - a for p, a in zip(point, at)]
    along = sum(o * v for o, v in zip(offset, axis))
    return all(abs(o - along * v) < 1e-9 for o, v in zip(offset, axis))


def _on_plane(point: list[float], face) -> bool:
    return abs(sum(p * n for p, n in zip(point, face.normal)) - face.offset_mm) < 1e-9


def test_cone_axial_extents_map_through_source_frames_onto_authored_faces() -> None:
    from prechips.rules.coordinates import model_point

    manifest = exporter.requirement_manifest("dt_cone_pivot_post")
    features, frames = manifest["features"], manifest["frames"]
    selectors = exporter.feature_selectors("dt_cone_pivot_post")
    assert frames["setup"] == "unknown"

    def ends(name: str) -> list[list[float]]:
        frame = frames[features[name]["frame"]]
        return [model_point([0.0, 0.0, z], frame) for z in features[name]["z_mm"]]

    foot, body_top = ends("body")
    head_base, head_top = ends("head")
    assert head_base == pytest.approx([0.0, exporter.cone.HEAD_BASE_Y, 0.0])
    assert head_top == pytest.approx([0.0, exporter.cone.BLOCK_HEIGHT, 0.0])
    assert foot == pytest.approx([0.0, 0.0, 0.0]) and _on_plane(foot, selectors["foot_seat"][0])
    assert body_top == pytest.approx(head_base)
    assert _on_plane(head_top, selectors["head"][1])
    crank = features["crank_bore"]
    for point, face in zip(ends("crank_boss"), selectors["crank_boss_faces"]):
        assert _on_axis(point, crank["at"], crank["axis"]) and _on_plane(point, face)
    journal = features["journal_bore"]
    north, south = ends("cone_boss")
    for point, face in ((north, selectors["cone_boss_north_face"][0]), (south, selectors["cone_boss_south_face"][0])):
        assert _on_axis(point, journal["at"], journal["axis"]) and _on_plane(point, face)


def test_turned_profile_resolves_only_spans_coaxial_with_its_setup() -> None:
    from prechips.rules.turned_profile import _axial_span

    cone = exporter.cone
    manifest = exporter.requirement_manifest("dt_cone_pivot_post")
    features, frames = manifest["features"], manifest["frames"]
    # A spindle on the post axis facing the head top: setup +Z runs model -Y.
    spindle = {"origin": [0.0, cone.BLOCK_HEIGHT, 0.0], "x": [1.0, 0.0, 0.0], "y": [0.0, 0.0, 1.0], "z": [0.0, -1.0, 0.0]}
    assert _axial_span(features["head"], spindle, frames, 1.0) == pytest.approx((0.0, cone.HEAD_HEIGHT))
    assert _axial_span(features["body"], spindle, frames, 1.0) == pytest.approx((cone.HEAD_HEIGHT, cone.BLOCK_HEIGHT))
    assert _axial_span(features["crank_boss"], spindle, frames, 1.0) is None
    assert _axial_span(features["cone_boss"], spindle, frames, 1.0) is None


@pytest.mark.parametrize("stem", exporter.SUPPORTED_PARTS)
def test_raw_step_face_sets_and_values_satisfy_installed_consumer_schema(tmp_path: Path, stem: str) -> None:
    step = _step(tmp_path, stem)
    content = step.read_bytes()
    path = exporter.write_manifest(stem.replace("_", "-"), step, revision="v40")
    assert path == step.with_name("features.toml")
    manifest = _load(path)
    loaded = Features.model_validate(manifest)
    if stem == "ch_rocker_arm":
        assert loaded.features["pivot_bore"].faces == [
            "#10/ADVANCED_FACE[1]/HAF_PIVOT_BORE__P01",
            "#11/ADVANCED_FACE[2]/HAF_PIVOT_BORE__P01",
        ]
        assert loaded.features[loaded.datums["B"].feature].faces == ["#15/ADVANCED_FACE[6]/HAF_STRAP_DATUM_B__P01"]
        assert loaded.features[loaded.datums["C"].feature].faces == ["#18/ADVANCED_FACE[9]/HAF_TIP_LAND_POS_X__P01"]
    assert loaded.step == step.name
    assert loaded.step_sha256 == hashlib.sha256(content).hexdigest()
    assert loaded.drawing.revision == "v40"
    assert manifest["cite"]["step_sha256"] == [f"harmonic-analyzer/cad/out/features/{stem}/{step.name}"]
    assert {file.name for file in path.parent.iterdir()} == {step.name, "features.toml"}
    assert step.read_bytes() == content


def test_raw_step_ansi_metadata_and_line_endings_are_never_rewritten(tmp_path: Path) -> None:
    step = _step(tmp_path, "ch_rocker_arm")
    content = step.read_bytes().replace(b"HEADER;\r\n", b"HEADER;\r\nFILE_DESCRIPTION(('M\xe9tal \x80 metadata'),'2;1');\r\n")
    step.write_bytes(content)
    path = exporter.write_manifest("ch_rocker_arm", step, revision="v40")
    assert _load(path)["step_sha256"] == hashlib.sha256(content).hexdigest()
    assert step.read_bytes() == content


def test_writer_uses_supplied_revision_and_replaces_adjacent_manifest(tmp_path: Path, monkeypatch) -> None:
    step = _step(tmp_path, "ch_rocker_arm")
    monkeypatch.setattr(exporter._config, "release_revision", lambda: "v999")
    path = exporter.write_manifest("ch_rocker_arm", step, revision="v40")
    old_digest = _load(path)["step_sha256"]
    step.write_bytes(step.read_bytes() + b"\r\n/* raw export header changed */\r\n")
    assert exporter.write_manifest("ch_rocker_arm", step, revision="v41") == path
    manifest = _load(path)
    assert manifest["drawing"]["revision"] == "v41"
    assert manifest["step_sha256"] == hashlib.sha256(step.read_bytes()).hexdigest() != old_digest
    assert exporter.SOURCE_MAP["drawing_revision"][0] in manifest["drawing"]["cite"]


def test_missing_label_fails_before_installing_requirements(tmp_path: Path) -> None:
    step = _step(tmp_path, "ch_pivot_shaft")
    step.write_bytes(step.read_bytes().replace(face_name("north_dome", 1).encode(), b"NONE"))
    with pytest.raises(FeatureFaceError, match="north_dome"):
        exporter.write_manifest("ch_pivot_shaft", step, revision="v40")
    assert not step.with_name("features.toml").exists()


def test_unsupported_part_is_rejected_without_a_bundle(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="unsupported"):
        exporter.write_manifest("unrelated_part", tmp_path / "missing.STEP", revision="v40")


@pytest.mark.parametrize("stem,module", [("ch_rocker_arm", exporter.rocker_notes), ("ch_pivot_shaft", exporter.shaft), ("dt_cone_pivot_post", exporter.cone)])
def test_construction_uses_the_actual_drawing_notes_and_explicit_permission(monkeypatch, stem, module) -> None:
    original = exporter.requirement_manifest(stem)
    assert original["construction"] == "one_piece"
    assert original["notes"]["manufacturing"] == module.DRAWING_NOTES.splitlines()
    citation = original["cite"]["construction"]
    assert citation == exporter._cite(module, "DRAWING_NOTES")
    permission = "BUILT-UP CONSTRUCTION IS PERMITTED."
    monkeypatch.setattr(module, "BUILT_UP_PERMISSION_NOTE", permission, raising=False)
    with pytest.raises(ValueError, match="explicit text in DRAWING_NOTES"):
        exporter.requirement_manifest(stem)
    monkeypatch.setattr(module, "DRAWING_NOTES", module.DRAWING_NOTES + "\n" + permission)
    manifest = exporter.requirement_manifest(stem)
    assert manifest["construction"] == "built_up_permitted"
    assert manifest["notes"]["manufacturing"][-1] == permission
    assert manifest["cite"]["construction"] == citation


def test_emitted_yaml_citations_resolve_to_scalar_requirement_sources() -> None:
    def strings(value):
        if isinstance(value, str):
            yield value
        elif isinstance(value, dict):
            for child in value.values():
                yield from strings(child)
        elif isinstance(value, list):
            for child in value:
                yield from strings(child)
    for stem in exporter.SUPPORTED_PARTS:
        citations = set(strings(exporter.requirement_manifest(stem)))
        yaml_citations = {
            citation for citation in citations
            if citation.startswith("harmonic-analyzer/") and ".yaml" in citation
        }
        dashed = stem.replace("_", "-")
        assert f"harmonic-analyzer/cad/config/parts/{dashed}.yaml:{dashed}.number" in yaml_citations
        for reference in yaml_citations:
            filename, separator, key_path = reference.removeprefix("harmonic-analyzer/").partition(":")
            assert separator and key_path, reference
            value = yaml.safe_load((exporter.REPO / filename).read_text(encoding="utf-8"))
            for key in key_path.split("."):
                assert isinstance(value, dict) and key in value, f"{reference}: missing key {key!r}"
                value = value[key]
            assert value is not None and not isinstance(value, (dict, list)), f"{reference}: not a scalar value"


class _GearProfileAdapter:
    """Record authored equations and paths without COM or a geometric substitute."""

    def __init__(self) -> None:
        self.curves = []
        self.planes = []
        self.active_plane = None
        self.constraints = []
        self.path_length = None
        self.path_name = None
        self.sweep = None

    @staticmethod
    def _result(data=None):
        return SimpleNamespace(is_success=True, data=data, error=None)

    async def create_sketch(self, plane):
        assert self.active_plane is None
        assert plane in ("Front", "Top")
        self.planes.append(plane)
        self.active_plane = plane
        return self._result()

    async def create_equation_driven_curve(self, params):
        assert self.active_plane == "Front"
        assert (params.range_start, params.range_end) == ("0", "1")
        assert not params.z_expression
        self.curves.append(params)
        return self._result(f"Curve{len(self.curves)}")

    async def check_sketch_fully_defined(self):
        assert self.active_plane is not None
        return self._result({"definition_state": "fully_defined"})

    async def exit_sketch(self):
        assert self.active_plane is not None
        self.active_plane = None
        return self._result()

    async def add_line(self, x1, y1, x2, y2):
        assert self.active_plane == "Top"
        assert (x1, y1, x2) == (0.0, 0.0, 0.0)
        assert y2 < 0.0
        self.path_length = -y2
        return self._result("Line1")

    async def add_sketch_constraint(self, entity, other, kind):
        assert self.active_plane == "Top"
        assert (entity, other, kind) in (
            ("Line1", None, "vertical"),
            ("Line1.start", "origin", "coincident"),
        )
        self.constraints.append((entity, other, kind))
        return self._result()

    async def add_sketch_dimension(self, first, second, kind, value):
        assert (first, second, kind) == (
            "Line1.start", "Line1.end", "vertical_distance"
        )
        assert value == self.path_length
        return self._result("D1@ToothPath")

    def name_last_feature(self, name):
        assert self.active_plane is None
        assert self.planes == ["Front", "Top"]
        assert name == "ToothPath"
        self.path_name = name
        return name

    async def create_sweep(self, params):
        assert self.active_plane is None
        assert len(self.curves) == 6
        assert len(self.constraints) == 2
        assert params.path == self.path_name == "ToothPath"
        assert params.twist_along_path and params.merge_result
        self.sweep = params
        return self._result(SimpleNamespace(name="ToothSweep"))

    async def create_cut_extrude(self, params):
        assert self.active_plane is None
        assert self.planes == ["Front"]
        assert params.depth > 0.0
        return self._result(SimpleNamespace(name="ToothGap"))


@pytest.fixture
def gear_profile_adapter(monkeypatch):
    import _gear

    adapter = _GearProfileAdapter()
    monkeypatch.setattr(
        _gear, "name_last_feature",
        lambda seat, name: seat.name_last_feature(name),
    )
    return adapter


def _curve_point(curve, t):
    # Evaluate the actual numeric radian expressions handed to the adapter,
    # rather than inspecting source strings or rebuilding a second profile.
    scope = {"__builtins__": {}, "cos": math.cos, "sin": math.sin, "t": t}
    return (
        eval(curve.x_expression, scope),
        eval(curve.y_expression, scope),
    )


def _profile_points(curves, walk, *, samples=64, radial_clip=None):
    points = []
    for index, reverse in walk:
        segment = [
            _curve_point(curves[index], (samples - i if reverse else i) / samples)
            for i in range(samples + 1)
        ]
        if points:
            assert segment[0] == pytest.approx(points[-1], rel=0.0, abs=3e-11)
        points.extend(segment if not points else segment[1:])
    assert points[-1] == pytest.approx(points[0], rel=0.0, abs=3e-11)
    points[-1] = points[0]
    if radial_clip is not None:
        lo, hi = radial_clip
        points = [
            (
                x * min(hi, max(lo, math.hypot(x, y))) / math.hypot(x, y),
                y * min(hi, max(lo, math.hypot(x, y))) / math.hypot(x, y),
            )
            for x, y in points
        ]
    return points


def _polygon_area(points):
    return abs(sum(
        x1 * y2 - x2 * y1
        for (x1, y1), (x2, y2) in zip(points, points[1:])
    )) / 2.0


def _assert_simple_profile(points):
    def cross(a, b, c):
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])

    edges = list(zip(points, points[1:]))
    for i, (a, b) in enumerate(edges):
        assert math.dist(a, b) > 1e-12
        for j in range(i + 2, len(edges)):
            if i == 0 and j == len(edges) - 1:
                continue
            c, d = edges[j]
            if (
                max(a[0], b[0]) < min(c[0], d[0])
                or max(c[0], d[0]) < min(a[0], b[0])
                or max(a[1], b[1]) < min(c[1], d[1])
                or max(c[1], d[1]) < min(a[1], b[1])
            ):
                continue
            assert not (
                cross(a, b, c) * cross(a, b, d) <= 0.0
                and cross(c, d, a) * cross(c, d, b) <= 0.0
            ), f"non-adjacent profile edges {i}, {j} intersect"


_TOOTH_WALK = ((0, False), (1, False), (2, True), (3, False), (4, False), (5, False))


def _crank_gear_profile():
    import cone_line
    from dt_crank_drive_gear_spec import (
        BACKLASH_MM, CUTTER_DIAMETRAL_PITCH, DEDENDUM_FACTOR,
        DIAMETRAL_PITCH, FACE_WIDTH, HELIX_ANGLE_DEG, LONG_ADDENDUM_MM,
        PRESSURE_ANGLE_DEG, ROOT_DIA, TEETH,
    )
    from involute_gear import gear_facts

    assert TEETH == 64
    assert CUTTER_DIAMETRAL_PITCH == pytest.approx(24.0, abs=1e-10)
    assert DEDENDUM_FACTOR == 1.25
    assert LONG_ADDENDUM_MM == 0.0
    assert FACE_WIDTH == 7.2244
    assert HELIX_ANGLE_DEG == pytest.approx(cone_line.INCLINE_DEG, abs=1e-10)
    assert DIAMETRAL_PITCH == pytest.approx(
        CUTTER_DIAMETRAL_PITCH * math.cos(math.radians(HELIX_ANGLE_DEG)),
        abs=1e-10,
    )
    normal_pa = math.degrees(math.atan(
        math.tan(math.radians(PRESSURE_ANGLE_DEG))
        * math.cos(math.radians(HELIX_ANGLE_DEG))
    ))
    assert normal_pa == pytest.approx(20.0, abs=1e-10)

    extra = 1.0 / CUTTER_DIAMETRAL_PITCH - 1.0 / DIAMETRAL_PITCH + LONG_ADDENDUM_MM / 25.4
    facts = gear_facts(
        TEETH, DIAMETRAL_PITCH, PRESSURE_ANGLE_DEG, addendum_extra_in=extra
    )
    pitch_r = TEETH / (2.0 * DIAMETRAL_PITCH)
    root = pitch_r - DEDENDUM_FACTOR / CUTTER_DIAMETRAL_PITCH
    assert root * 50.8 == pytest.approx(ROOT_DIA)
    eps = BACKLASH_MM / (2.0 * pitch_r * 25.4)
    twist = FACE_WIDTH * math.tan(math.radians(HELIX_ANGLE_DEG)) / (pitch_r * 25.4)
    return facts, root, eps, twist, FACE_WIDTH, extra, DIAMETRAL_PITCH, PRESSURE_ANGLE_DEG


def test_normal24_pa20_swept_profile_starts_at_root_and_never_crosses(gear_profile_adapter):
    import _gear
    from involute_gear import involute_point

    facts, root, eps, twist, face, extra, dp, pa = _crank_gear_profile()
    assert root > facts["Rb"]
    assert root - _gear._TOOTH_EMBED_MM / 25.4 > facts["Rb"]
    rho = -twist / 2.0
    name = asyncio.run(_gear.boss_tooth_swept(
        gear_profile_adapter, facts, face, twist_deg=math.degrees(twist),
        rotate_rad=rho, widen_rad=eps, root_r_in=root,
    ))
    assert name == "ToothSweep"
    assert gear_profile_adapter.sweep.twist_angle == pytest.approx(math.degrees(twist))
    curves = gear_profile_adapter.curves
    points = _profile_points(curves, _TOOTH_WALK)
    _assert_simple_profile(points)

    u0 = math.sqrt((root / facts["Rb"])**2 - 1.0)
    assert _gear._root_start_parameter(facts["Rb"], root) == pytest.approx(u0)
    inv0 = u0 - math.atan(u0)
    foot_angles = (
        facts["Gamma"] - facts["Delta"] + eps + rho + inv0,
        facts["Gamma"] + facts["Delta"] - eps + rho - inv0,
    )
    # Reparameterising the same involute must not alter geometry outside
    # the root, including the diagnostic mesh domain.
    for i in range(17):
        t = i / 16.0
        u = u0 + (facts["Tmax"] - u0) * t
        for index, upper, rotation in (
            (0, True, eps + rho),
            (2, False, facts["Gamma"] - eps + rho),
        ):
            x, y = involute_point(facts, u, upper=upper)
            reference = (
                x * math.cos(rotation) - y * math.sin(rotation),
                x * math.sin(rotation) + y * math.cos(rotation),
            )
            assert _curve_point(curves[index], t) == pytest.approx(
                reference, rel=0.0, abs=3e-11
            )
    for index, angle in zip((0, 2), foot_angles):
        assert _curve_point(curves[index], 0.0) == pytest.approx(
            (root * math.cos(angle), root * math.sin(angle)), rel=0.0, abs=3e-11
        )
        radii = [math.hypot(*_curve_point(curves[index], i / 64.0)) for i in range(65)]
        assert all(a < b for a, b in zip(radii, radii[1:]))
        assert radii[-1] == pytest.approx(facts["Ra"], rel=0.0, abs=3e-11)
    embed = root - _gear._TOOTH_EMBED_MM / 25.4
    for index, reverse in ((3, False), (5, True)):
        radii = [
            math.hypot(*_curve_point(curves[index], (64 - i if reverse else i) / 64.0))
            for i in range(65)
        ]
        assert radii[0] == pytest.approx(root, rel=0.0, abs=3e-11)
        assert radii[-1] == pytest.approx(embed, rel=0.0, abs=3e-11)
        assert all(a > b for a, b in zip(radii, radii[1:]))

    # The embedded sliver adds no material to the root-cylinder union.
    physical = _profile_points(
        curves, _TOOTH_WALK, samples=2000, radial_clip=(root, facts["Ra"])
    )
    gap = _gear.gap_area_in_disc_ext(
        64, dp, pa, eps, root, addendum_extra_in=extra
    )
    tooth = math.pi * (facts["Ra"]**2 - root**2) / 64.0 - gap
    assert _polygon_area(physical) == pytest.approx(tooth, rel=0.0, abs=2e-9)


def test_normal24_pa20_gap_clips_to_same_root_and_volume_oracle(gear_profile_adapter):
    import _gear

    facts, root, eps, twist, face, extra, dp, pa = _crank_gear_profile()
    asyncio.run(_gear.cut_tooth_gap(
        gear_profile_adapter, facts, face + 1.0,
        rotate_rad=-twist / 2.0, widen_rad=eps, root_r_in=root,
    ))
    curves = gear_profile_adapter.curves
    assert len(curves) == 6  # no zero-length or outward base-to-root extensions
    walk = ((0, False), (2, False), (3, False), (4, False), (1, True), (5, False))
    _assert_simple_profile(_profile_points(curves, walk))
    for index in (0, 1):
        assert math.hypot(*_curve_point(curves[index], 0.0)) == pytest.approx(
            root, rel=0.0, abs=3e-11
        )
    clipped = _profile_points(
        curves, walk, samples=2000, radial_clip=(root, facts["Ra"])
    )
    expected = _gear.gap_area_in_disc_ext(
        64, dp, pa, eps, root, addendum_extra_in=extra
    )
    assert _polygon_area(clipped) == pytest.approx(expected, rel=0.0, abs=2e-10)
    u0 = math.sqrt((root / facts["Rb"])**2 - 1.0)
    inv0 = u0 - math.atan(u0)
    root_span = facts["Gamma"] - 2.0 * facts["Delta"] + 2.0 * eps + 2.0 * inv0
    tip_span = facts["ThetaU"] - facts["ThetaL"] + 2.0 * eps
    exact = (
        facts["Ra"]**2 * tip_span - root**2 * root_span
        - 2.0 * facts["Rb"]**2 * (facts["Tmax"]**3 - u0**3) / 3.0
    ) / 2.0
    assert expected == pytest.approx(exact, rel=0.0, abs=2e-9)


@pytest.mark.parametrize("teeth,dp,pa", ((16, 24.0, 20.0), (64, 24.74, 14.5), (12, 12.7, 14.5)))
def test_below_base_sweep_keeps_original_profile(gear_profile_adapter, teeth, dp, pa):
    import _gear
    from involute_gear import gear_facts

    facts = gear_facts(teeth, dp, pa)
    root = teeth / (2.0 * dp) - 1.157 / dp
    assert 0.0 < root < facts["Rb"]
    assert _gear._root_start_parameter(facts["Rb"], root) == 0.0
    eps, rho = 0.001, -0.012
    asyncio.run(_gear.boss_tooth_swept(
        gear_profile_adapter, facts, 7.2244, twist_deg=2.0,
        rotate_rad=rho, widen_rad=eps, root_r_in=root,
    ))
    rb, ra = facts["Rb"], facts["Ra"]
    embed = root - _gear._TOOTH_EMBED_MM / 25.4
    a_lo = facts["Gamma"] - facts["Delta"] + eps + rho
    a_hi = facts["Gamma"] + facts["Delta"] - eps + rho
    for i in range(17):
        t = i / 16.0
        u = facts["Tmax"] * t
        ph_a, ph_b = u + a_lo, u - a_hi
        tip = facts["ThetaU"] + eps + rho + t * (
            facts["Gamma"] + facts["ThetaL"] - facts["ThetaU"] - 2.0 * eps
        )
        arc = a_hi + t * (a_lo - a_hi)
        reference = (
            (rb * (math.cos(ph_a) + u * math.sin(ph_a)), rb * (math.sin(ph_a) - u * math.cos(ph_a))),
            (ra * math.cos(tip), ra * math.sin(tip)),
            (rb * (math.cos(ph_b) + u * math.sin(ph_b)), rb * (u * math.cos(ph_b) - math.sin(ph_b))),
            ((rb + t * (embed - rb)) * math.cos(a_hi), (rb + t * (embed - rb)) * math.sin(a_hi)),
            (embed * math.cos(arc), embed * math.sin(arc)),
            ((embed + t * (rb - embed)) * math.cos(a_lo), (embed + t * (rb - embed)) * math.sin(a_lo)),
        )
        for curve, point in zip(gear_profile_adapter.curves, reference, strict=True):
            assert _curve_point(curve, t) == pytest.approx(point, rel=0.0, abs=3e-11)


@pytest.mark.parametrize("root_kind", ("chord", "below", "base"))
def test_below_base_gap_keeps_floor_and_involute_endpoints(gear_profile_adapter, root_kind):
    import _gear
    from involute_gear import gap_area_in_disc, gear_facts, involute_point

    facts = gear_facts(16, 24.0, 20.0)
    root = {"chord": None, "below": 7.14375 / 25.4, "base": facts["Rb"]}[root_kind]
    assert _gear._root_start_parameter(facts["Rb"], root) == 0.0
    asyncio.run(_gear.cut_tooth_gap(gear_profile_adapter, facts, 8.0, root_r_in=root))
    curves = gear_profile_adapter.curves
    assert len(curves) == (8 if root_kind == "below" else 6)
    for i in range(17):
        t = i / 16.0
        for index, upper in ((0, False), (1, True)):
            assert _curve_point(curves[index], t) == pytest.approx(
                involute_point(facts, facts["Tmax"] * t, upper=upper),
                rel=0.0, abs=3e-11,
            )
    floor_walk = ((5, False), (6, False), (7, False)) if root_kind == "below" else ((5, False),)
    walk = ((0, False), (2, False), (3, False), (4, False), (1, True), *floor_walk)
    _assert_simple_profile(_profile_points(curves, walk))
    area = _gear.gap_area_in_disc_ext(16, 24.0, 20.0, root_r_in=root)
    if root_kind == "chord":
        assert area == pytest.approx(gap_area_in_disc(16, dp=24.0, pa_deg=20.0), abs=1e-12)
    clipped = _profile_points(
        curves, walk, samples=2000, radial_clip=(0.0, facts["Ra"])
    )
    assert _polygon_area(clipped) == pytest.approx(area, rel=0.0, abs=2e-10)


@pytest.mark.parametrize("root_kind", ("negative", "zero", "tip", "above_tip", "embed_zero"))
def test_invalid_root_is_refused_before_sweep_profile(gear_profile_adapter, root_kind):
    import _gear

    facts, _, eps, twist, face, extra, dp, pa = _crank_gear_profile()
    root = {
        "negative": -1.0, "zero": 0.0, "tip": facts["Ra"],
        "above_tip": facts["Ra"] + 0.01, "embed_zero": _gear._TOOTH_EMBED_MM / 25.4,
    }[root_kind]
    with pytest.raises(ValueError, match="root"):
        asyncio.run(_gear.boss_tooth_swept(
            gear_profile_adapter, facts, face, twist_deg=math.degrees(twist),
            rotate_rad=0.0, widen_rad=eps, root_r_in=root,
        ))
    assert not gear_profile_adapter.curves
    assert not gear_profile_adapter.planes
    if root_kind != "embed_zero":
        with pytest.raises(ValueError, match="root"):
            asyncio.run(_gear.cut_tooth_gap(
                gear_profile_adapter, facts, face, root_r_in=root,
            ))
        with pytest.raises(ValueError, match="root"):
            _gear.gap_area_in_disc_ext(
                64, dp, pa, eps, root, addendum_extra_in=extra,
            )


@pytest.mark.parametrize(
    "root,expected",
    ((None, 0.0), (0.2, 0.0), (0.25, 0.0), (0.3125, 0.75)),
    ids=("chord", "below_base", "on_base", "above_base"),
)
def test_canonical_root_start_selects_physical_involute_domain(root, expected):
    import _gear

    assert _gear._root_start_parameter(0.25, root) == pytest.approx(expected)


@pytest.mark.parametrize("root", (-1.0, 0.0, math.inf, math.nan), ids=("negative", "zero", "infinite", "nan"))
def test_canonical_root_start_rejects_nonphysical_radii(root):
    import _gear

    with pytest.raises(ValueError, match="positive and finite"):
        _gear._root_start_parameter(0.25, root)
