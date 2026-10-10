"""Offline drawing requirements, exact datum domains and raw STEP binding."""

from __future__ import annotations

import hashlib
import math
import tomllib
from pathlib import Path

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
    # The strap's native 2.500 +/-0.025 (Main ruling 2026-10, option b).
    for name in ("strap_datum_b", "strap_faces"):
        assert features[name]["thickness"] == [2.475, 2.525]
        assert features[name]["precision"]["thickness"] == 3
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
    assert set(shaft["features"]) == {"pivot_bearing", "north_flat", "south_flat", "north_dome", "south_dome"}
    assert shaft["features"]["pivot_bearing"]["requirements"] == ["dia", "finish_ra"]


def test_shaft_flats_are_coplanar_faces_named_by_their_stations() -> None:
    shaft = exporter.shaft
    features = exporter.requirement_manifest("ch_pivot_shaft")["features"]
    selectors = exporter.feature_selectors("ch_pivot_shaft")
    flat_y = shaft.FLAT_AF - shaft.SHAFT_DIA / 2
    half_chord = shaft.flat_chord(shaft.FLAT_DEPTH) / 2
    for side, station in zip(("south", "north"), exporter.bank.PIVOT_SHAFT_FLAT_STATIONS):
        name = f"{side}_flat"
        assert features[name]["kind"] == "face"
        assert features[name]["station_nominal"] == station
        assert features[name]["height_nominal"] == shaft.FLAT_AF
        assert selectors[name][0].contains_z_mm == -station
        box = (
            -half_chord / 1000, flat_y / 1000, (-station - shaft.FLAT_LENGTH / 2) / 1000,
            half_chord / 1000, flat_y / 1000, (-station + shaft.FLAT_LENGTH / 2) / 1000,
        )
        face = _FaceGeometry(None, 4001, (0, 1, 0, 0, flat_y / 1000, -station / 1000), (0, 1, 0), box)
        assert _owners("ch_pivot_shaft", face) == [name]


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


def test_cone_native_tolerances_angularity_and_exact_datums() -> None:
    manifest = exporter.requirement_manifest("dt_cone_pivot_post")
    features = manifest["features"]
    crank = features["crank_bore"]
    assert crank["dia"] == [11.413, 11.443]
    assert features["journal_bore"]["dia"] == [12.2558, 12.2858]
    assert features["journal_bore"]["height"] == [33.118, 33.618]
    assert crank["separation"] == [39.332, 39.702]
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


def test_shaft_axial_extents_tile_the_turned_axis() -> None:
    features = exporter.requirement_manifest("ch_pivot_shaft")["features"]
    selectors = exporter.feature_selectors("ch_pivot_shaft")
    order = ("south_dome", "pivot_bearing", "north_dome")
    spans = {name: features[name]["z_mm"] for name in order}
    assert all(features[name]["frame"] == "model" and low < high for name, (low, high) in spans.items())
    for below, above in zip(order, order[1:]):
        assert spans[below][1] == pytest.approx(spans[above][0]), (below, above)
    # The O.D. runs the whole cylinder; its named patch lies inside it.
    assert spans["pivot_bearing"] == pytest.approx([-exporter.bank.PIVOT_SHAFT_LENGTH, 0.0])
    low, high = spans["pivot_bearing"]
    assert low < selectors["pivot_bearing"][0].contains_z_mm < high
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
