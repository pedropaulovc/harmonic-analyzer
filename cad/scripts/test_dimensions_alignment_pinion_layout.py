"""The narrative alignment-pinion record in dimensions.yaml tracks the CAD.

``cad/config/dimensions.yaml`` is read by no part, so nothing rebuilds when
the rig moves, and its alignment-pinion layout summary drifted three geometry
revisions behind (Codex P2s on #814: a 2.0 gap and −18.626 axis, 5 mm straps,
the Ø10.32/e1.4 scalloped cam, a 34.0 spring foot).  Every number the summary
and the two rig rows print is re-derived here from the constant that owns it,
at the places the prose prints, so the record cannot drift silently again.
"""

from __future__ import annotations

import re
from pathlib import Path

import build_dt_drive_train_assembly as dt
import cone_line
import cone_pitch
import cylinder_bank_layout as cylinder_bank
import dt_alignment_pinion_spec as alignment
import dt_cone_gear_spec as cone
import dt_cone_gear_shaft_spec as cone_shaft
import dt_cone_pivot_post_spec as post
import dt_cone_swing_platform_geometry as platform_geometry
import dt_cone_swing_platform_spec as platform
import dt_crank_drive_gear_spec as gear64
import dt_crank_pinion_spec as crank_pinion
import dt_crankshaft_spec as crankshaft
import dt_cylinder_gear_spec as drum
import dt_pinion_bracket_geometry as strap
from dt_pinion_arbor_spec import SHAFT_LEN as ARBOR_LEN
import dt_pinion_spring_geometry as spring
import gen_dimensions
import vn_post_mount_screw_spec as post_screw
import vn_cone_tip_collar_spec as tip_collar
import vn_cone_tip_adjuster_spec as tip_adjuster
import vn_cone_pivot_screw_spec as pivot_screw
import vn_swing_stop_screw_spec as stop_screw

DIMENSIONS = Path(__file__).resolve().parents[1] / "config" / "dimensions.yaml"


def _strings(node: object) -> list[str]:
    if isinstance(node, str):
        return [node]
    if isinstance(node, dict):
        return [s for key, value in node.items() for s in _strings(key) + _strings(value)]
    if isinstance(node, list):
        return [s for item in node for s in _strings(item)]
    return []


def _prose(record: object) -> str:
    """Every string in the parsed real configuration, whitespace collapsed.

    The renderer regression separately rejects valid-YAML non-string cells;
    these fragment tests keep the selected geometry tied to its spec readers.
    """
    return re.sub(r"\s+", " ", " ".join(_strings(record)))


def test_real_configured_dimensions_tables_render_and_keep_dt_suffixes() -> None:
    assert gen_dimensions.DIMENSIONS_YAML == DIMENSIONS
    record = gen_dimensions.load_doc()
    for section in record["sections"]:
        for element in section["elements"]:
            if "table" not in element:
                continue
            table = element["table"]
            assert all(isinstance(cell, str) for cell in table["columns"]), section["heading"]
            for row in table["rows"]:
                if isinstance(row, dict):
                    assert isinstance(row.get("raw"), str), (section["heading"], row)
                else:
                    assert isinstance(row, list), (section["heading"], row)
                    assert all(isinstance(cell, str) for cell in row), (
                        section["heading"],
                        row,
                    )
    assert gen_dimensions.render_markdown(record).strip()

    arbor = gen_dimensions.find_row(record, "Chapter 13", "Arbor ends and set screws")
    assert arbor is not None
    assert "#4-40" in arbor[1]
    adjuster = gen_dimensions.find_row(record, "Chapter 13", "`vn-cone-tip-adjuster`")
    assert adjuster is not None
    assert "#10-32" in adjuster[1]
    assert "t00147:" in adjuster[3]


def _mm(value: float, places: int = 3) -> str:
    """Format a signed value the way the record prints it (Unicode minus)."""
    return f"{value:.{places}f}".replace("-", "−")


def _section_mm(value: float) -> str:
    """A strip dimension as the record prints it: 5.0, 6.35."""
    text = f"{value:.3f}".rstrip("0")
    return text + "0" if text.endswith(".") else text


def test_the_spring_pad_the_record_calls_square_is_square() -> None:
    assert spring.PAD_LEN == spring.PAD_WIDTH


def _expected_fragments() -> list[str]:
    authority = (dt.FPIN_DIA + dt.CAM_OD) / 2.0 - dt._D_ENG
    follower_reserve = dt._FPIN_TIP_S - dt._S_CAM_ENG
    return [
        # Layout summary.
        f"U28 {dt.APINION_GAP} mm parked tip gap",
        f"axis ({_mm(dt.APINION_X)}, {dt.APINION_Y:g})",
        f"drum radius {dt.TIP_DRUM120:.3f}, pinion radius {dt.TIP_APINION:.3f} "
        f"and parked gap {dt.APINION_GAP}",
        f"Drum z {_mm(dt.APINION_Z_FRONT)}..+{dt.APINION_Z_BACK:.3f}",
        f"({dt.APINION_Z_BACK - dt.APINION_Z_FRONT:.1f} face",
        f"root z {_mm(dt.ARBOR_Z0)}..+{dt.ARBOR_Z0 + ARBOR_LEN:.3f}",
        f"head/crossrod axis z {_mm(dt.HANDLE_Z)}",
        f"crossrod at +{dt.HANDLE_TILT_DEG:g}°",
        f"Straps: {strap.WIDTH:g} wide × {strap.THICKNESS:g} thick with "
        f"R{strap.R_END:g} ends, plain (no cam relief)",
        f"pivot ({_mm(dt.PIVOT_X)}, {dt.PIVOT_Y:g})",
        f"c2c {dt.STRAP_C2C:.1f}",
        f"{dt.STRAP_LEAN_DEG:.3f}° lean",
        f"bores at ({_mm(dt.LIFT_X)}, {_mm(dt.LIFT_Y)})",
        f"The collar is Ø{dt.CAM_OD:g} with a {dt.CAM_ECC:.1f} eccentricity "
        f"and keeps a {dt.CAM_THIN_SIDE_WALL:.3f} thin-side wall",
        f"Current nominal parked surface gap is {dt._PARK_GAP:.3f}",
        f"{_mm(dt.CAM_ENGAGE_ROTATION_DEG)}° cam rotation, "
        f"{authority:.3f} mm engaged authority and "
        f"{follower_reserve:.3f} mm follower projection beyond contact",
        # Engage-lever row keeps the current linkage, not the historical photo angle.
        f"source-law eccentric-cam rotation {_mm(dt.CAM_ENGAGE_ROTATION_DEG)}° "
        f"carries it through vertical to {_mm(dt.LEVER_ENGAGED_TILT_DEG)}°",
        f"eccentricity {dt.CAM_ECC:.1f}, source thin-side wall "
        f"{dt.CAM_THIN_SIDE_WALL:.3f}",
        # The current spring's section, pad, offset and contact station remain
        # reader-derived; its historical material interpretation is independent.
        f"{spring.THICK:g} ×{_section_mm(spring.WIDTH)} ",
        f"{spring.SCREW_EAST_OF_PIVOT:.1f} EAST of pivot",
        f"{spring.PAD_LEN:g} square pad",
        f"{spring.CONTACT_T:.1f} up strap",
    ]


def test_alignment_pinion_record_matches_the_cad_constants() -> None:
    prose = _prose(gen_dimensions.load_doc())
    missing = [fragment for fragment in _expected_fragments() if fragment not in prose]
    assert not missing, "dimensions.yaml drifted from the CAD:\n" + "\n".join(missing)


def test_current_drive_train_record_matches_the_selected_production_specs() -> None:
    """Check current cells; history must not satisfy a stale selected dimension.

    Deliberately reader-only quantities keep their named authority, rather than
    duplicating a pending contact, installed-fit or physical-air result.
    """
    record = gen_dimensions.load_doc()
    prose = _prose(record)
    expected = [
        f"DP {cone.DIAMETRAL_PITCH:g} (m = {cone.MODULE_MM:.12f} mm)",
        f"{cone.PRESSURE_ANGLE_DEG:g}° selected",
        f"{cone_pitch.SEAT_PITCH:.12f} mm along-shaft cone seat pitch",
        f"face width floored to {cone.FACE_WIDTH:g} mm",
        f"{cone_pitch.INCLINE_DEG:.15g}° = "
        f"arcsin({cone_pitch.RADIUS_STEP:g}/{cone_pitch.Z_PITCH:g})",
        f"pitch diameter {drum.PITCH_DIA:g} mm",
        f"{drum.CAM_THICKNESS:.4f} mm",
        f"{drum.BORE_DIA:g} mm model nominal",
        f"{alignment.ENGAGED_CENTER_DISTANCE_MM:.6f} engaged centre",
        f"Current cylindrical length {crankshaft.SHAFT_LENGTH:g} mm",
    ]
    missing = [fragment for fragment in expected if fragment not in prose]
    assert not missing, (
        "current production dimensions drifted from the specs:\n" + "\n".join(missing)
    )

    crank_row = gen_dimensions.find_row(record, "Chapter 12", "Crank-drive gear")
    assert crank_row is not None
    for spec, plunge_label in ((gear64, "normal-tool plunge"), (crank_pinion, "cutter plunge")):
        current_fragments = (
            f"{spec.TEETH}T pitch Ø{spec.PITCH_DIA:.12f}",
            f"blank Ø{spec.OUTSIDE_DIA:.2f} ±{spec.OUTSIDE_DIA_TOLERANCE_MM:.2f}",
            f"nominal root-envelope MIN/MAX Ø{2 * spec.STOCK_PROFILE.root_radius_min_mm:.12f}"
            f" / {2 * spec.STOCK_PROFILE.root_radius_max_mm:.12f}",
            f"{plunge_label} {spec.TOOL_PLUNGE_MM:.9f} mm",
        )
        for fragment in current_fragments:
            assert fragment in crank_row[1], fragment
        assert (
            f"shared {spec.TOOTH_RUNOUT_TIR_MM:.2f} mm TIR limit to its finished bore"
            in crank_row[3]
        )
    assert (
        f"Normal {gear64.CUTTER_DIAMETRAL_PITCH:g}DP "
        f"PA{gear64.CUTTER_PRESSURE_ANGLE_DEG:g} pair" in crank_row[1]
    )
    assert f"beta = cone incline {gear64.HELIX_ANGLE_DEG:.15g}°" in crank_row[1]
    assert f"face {gear64.FACE_WIDTH:.4f} ±{gear64.FACE_WIDTH_BAND[0]:g}" in crank_row[1]
    assert (
        "normal tangent-span limits are reader-owned by "
        "dt_crank_drive_gear_spec / dt_crank_pinion_spec" in crank_row[1]
    )

    for section, label, spec in (
        ("Chapter 13", "Gear outer diameter", drum),
        ("Chapter 25", "Outer diameter", alignment),
    ):
        row = gen_dimensions.find_row(record, section, label)
        assert row is not None
        lower, upper = spec.outside_dia_limits_mm()
        assert f"{spec.OUTSIDE_DIA:.2f} mm blank" in row[1]
        assert f"tooth-tip MIN/MAX {lower:.2f}..{upper:.2f} mm" in row[1]
        current_form = row[3].split("Earlier")[0]
        native_fragments = (
            f"#{spec.CUTTER_NUMBER} stock form, {spec.CUTTER_REFERENCE_TEETH}T reference",
            f"{spec.TEETH}T {spec.DIAMETRAL_PITCH:g}DP PA{spec.PRESSURE_ANGLE_DEG:g}",
            f"nominal support Ø{spec.SUPPORT_OUTSIDE_DIA_MM:.9f}",
            f"root-envelope MIN/MAX Ø{spec.ROOT_ENVELOPE_DIA_MM[0]:.9f} "
            f"/ {spec.ROOT_ENVELOPE_DIA_MM[1]:.9f}",
            f"cutter plunge {spec.WHOLE_DEPTH:.9f}",
        )
        for fragment in native_fragments:
            assert fragment.lower() in current_form.lower(), (label, fragment)
    alignment_row = gen_dimensions.find_row(record, "Chapter 25", "Outer diameter")
    assert alignment_row is not None
    assert f"tangent span {alignment.BASE_TANGENT_SPAN:.9f} mm" in alignment_row[3]
    span_min, span_max = alignment.base_tangent_span_limits_mm()
    assert (
        f"printed span {span_min:.{alignment.BASE_TANGENT_SPAN_PLACES}f}"
        f"..{span_max:.{alignment.BASE_TANGENT_SPAN_PLACES}f}" in alignment_row[3]
    )
    assert (
        f"span-corner support Ø{alignment.MIN_SPAN_SUPPORT_OUTSIDE_DIA_MM:.9f}"
        in alignment_row[3]
    )
    drum_row = gen_dimensions.find_row(record, "Chapter 13", "Gear outer diameter")
    assert drum_row is not None
    assert f"depth-corner cap Ø{drum.MAX_DEPTH_SUPPORT_OUTSIDE_DIA_MM:.9f}" in drum_row[3]
    cam_row = gen_dimensions.find_row(record, "Chapter 13", "Cam diameter")
    assert cam_row is not None
    assert f"minimum cam web {drum.CAM_ROOT_WEB_MIN_MM:.9f} mm" in cam_row[3]

    shaft_row = gen_dimensions.find_row(record, "Chapter 12", "Cone shaft diameter")
    assert shaft_row is not None
    assert f"/ {cone_shaft.SECTION_FLAT_AF[-1]:.3f}," in shaft_row[1]
    assert (
        f"terminal-flat edge break {cone_shaft.TERMINAL_FLAT_EDGE_BREAK_MAX:.3f} MAX"
        in shaft_row[3]
    )
    assert "cone_shaft_land_bands owns diameters, flats and retention bands" in shaft_row[3]
    assert "its end follows SHAFT_LENGTH" in shaft_row[1]
    shaft_length_row = gen_dimensions.find_row(record, "Chapter 12", "Cone shaft length")
    assert shaft_length_row is not None
    assert f"{cone_shaft.SHAFT_LENGTH:.12f} mm overall" in shaft_length_row[1]
    assert "dt_cone_gear_shaft_spec.SHAFT_LENGTH is the reader" in shaft_length_row[1]

    for label in ("Cone gear j (", "Cylinder arbor (stationary)"):
        row = gen_dimensions.find_row(record, "Chapter 13", label)
        assert row is not None
        assert f"y = {cone_line.Y_DRIVE:g}" in row[1], label
    arbor_row = gen_dimensions.find_row(record, "Chapter 13", "Cylinder arbor (stationary)")
    assert arbor_row is not None
    assert (
        f"cylindrical span z {_mm(cylinder_bank.ARBOR_SOUTH_Z, 9)}"
        f"..+{cylinder_bank.ARBOR_SOUTH_Z + cylinder_bank.ARBOR_LENGTH:.9f}"
        f" ({cylinder_bank.ARBOR_LENGTH:.2f} mm)" in arbor_row[1]
    )
    platform_row = gen_dimensions.find_row(record, "Chapter 13", "`dt-cone-swing-platform`")
    assert platform_row is not None
    assert f"wedge length {platform_geometry.PLATE_LEN:.12f} along the cone axis" in platform_row[1]
    assert "unrelieved under the crank gear" in platform_row[1]
    assert f"cone journal is {platform.POST_CONE_BORE_HEIGHT:g} mm above it" in platform_row[1]
    assert "crank_gear_platform_clearance() owns the full-turn printed/service air budget" in platform_row[1]
    assert f"Pivot at cone station {cone_line.PIVOT_STATION:.12f}" in platform_row[2]
    assert (
        f"machine ({_mm(cone_line.PIVOT_XZ[0], 9)}, +{cone_line.PIVOT_XZ[1]:.9f})"
        in platform_row[2]
    )
    assert f"post local Z {_mm(platform_geometry.POST_LOCAL_Z, 12)}" in platform_row[2]
    post_row = gen_dimensions.find_row(record, "Chapter 13", "`dt-cone-pivot-post`")
    assert post_row is not None
    for fragment in (
        f"Current body Ø{post.BLOCK_DIA:g} ×{post.BLOCK_HEIGHT:g} high",
        f"head Ø{post.HEAD_DIA:g} ×{post.HEAD_HEIGHT:g}",
        f"running bore at {post.CRANK_BORE_HEIGHT:.12f} above platform",
    ):
        assert fragment in post_row[1], fragment
    screw_row = gen_dimensions.find_row(record, "Chapter 13", "`vn-post-mount-screw`")
    assert screw_row is not None
    for fragment in (
        f"MSC {post_screw.SKU}",
        f"×{post_screw.STOCK_LENGTH_MM / drum.MM_PER_IN:g} in "
        f"/ {post_screw.STOCK_LENGTH_MM:g} mm supplied stock",
        f"reference cut length {post_screw.CUT_LENGTH_MM:g} mm",
    ):
        assert fragment in screw_row[1], fragment
    tip_block_row = gen_dimensions.find_row(record, "Chapter 13", "`dt-cone-tip-block`")
    assert tip_block_row is not None
    tip_block_point = cone_line.cone_station(cone_line.TIP_BLOCK_STATION)
    for fragment in (
        f"current nominal centre ({_mm(tip_block_point[0], 9)}, +{tip_block_point[2]:.9f})",
        f"cone station {cone_line.TIP_BLOCK_STATION:.12f}",
        f"north/south faces {cone_shaft.TIP_BLOCK_NORTH_FACE_STATION:.12f}"
        f" / {cone_shaft.TIP_BLOCK_SOUTH_FACE_STATION:.12f}",
    ):
        assert fragment in tip_block_row[2], fragment

    collar_row = gen_dimensions.find_row(record, "Chapter 13", "`vn-cone-tip-collar`")
    assert collar_row is not None
    body_places = tip_collar.DRAWING_PRECISION_BY_NAME["CollarDia"]
    for fragment in (
        f"McMaster {tip_collar.SET_SCREW_SKU}",
        f"body OD{tip_collar.OUTER_DIA:.{body_places}f} ±{tip_collar.ROUTINE_BAND_MM:.2f} mm",
        f"width {tip_collar.WIDTH:.1f} at the routine ±{tip_collar.WIDTH_BAND_MM:.2f} band",
        f"south nose length {tip_collar.NOSE_LENGTH:.1f}",
        f"BASIC tap station {tip_collar.TAP_STATION:.1f}",
        f"Ø{tip_collar.NOSE_DIA:.2f} nose",
        "ground positive dog governed by the shared retention reader",
        "model-owned tap-position and dog-runout controls",
        "not a frozen purchased-collar diameter or native/full-P1 acceptance",
    ):
        assert fragment in collar_row[1], fragment
    assert f"terminal AF {cone_shaft.SECTION_FLAT_AF[-1]:.3f} D-flat" in collar_row[2]
    assert (
        "dt_cone_gear_shaft_spec.TIP_COLLAR_START_STATION / TIP_COLLAR_END_STATION"
        in collar_row[2]
    )
    assert "no physical-air or native realization qualification asserted" in collar_row[4]
    pivot_row = gen_dimensions.find_row(record, "Chapter 13", "`vn-cone-pivot-screw`")
    assert pivot_row is not None
    for fragment in (
        f"supplied shoulder diameter {pivot_screw.SHOULDER_DIA:g} "
        f"+0/{_mm(pivot_screw.SHOULDER_DIA_BAND[1], 4)}",
        f"length {pivot_screw.SHOULDER_LEN:g} +{pivot_screw.SHOULDER_LEN_BAND[0]:.4f}/0",
        f"thread major MAX Ø{pivot_screw.THREAD_MAJOR_MAX_MM:.5f}",
        f"pitch diameter MIN Ø{pivot_screw.EXTERNAL_PITCH_DIA_MIN_MM:.5f} mm",
        f"full-form useful engagement MIN {pivot_screw.MIN_USEFUL_ENGAGEMENT_MM:.2f} mm",
        "inspection requirement, not a supplied-tail or coaxiality grade",
    ):
        assert fragment in pivot_row[1], fragment
    assert (
        f"current nominal ({_mm(cone_line.PIVOT_XZ[0], 9)}, "
        f"+{cone_line.PIVOT_XZ[1]:.9f})" in pivot_row[2]
    )
    adjuster_row = gen_dimensions.find_row(record, "Chapter 13", "`vn-cone-tip-adjuster`")
    assert adjuster_row is not None
    for fragment in (
        f"#10-32 UNF-{tip_adjuster.THREAD_CLASS}",
        f"Ø{tip_adjuster.CUP_DIA:g} / depth {tip_adjuster.CUP_DEPTH:g}",
        f"thread major MAX Ø{tip_adjuster.THREAD_MAJOR_MAX_MM:.5f}",
        f"pitch diameter MIN Ø{tip_adjuster.EXTERNAL_PITCH_DIA_MIN_MM:.5f} mm",
        "constrain threaded material, not supplied cup/body/length grades",
    ):
        assert fragment in adjuster_row[1], fragment
    assert f"model apex/tip station is {cone_shaft.T006_TIP_STATION:.12f}" in adjuster_row[2]
    stop_row = gen_dimensions.find_row(record, "Chapter 13", "`vn-swing-stop-screw`")
    assert stop_row is not None
    for fragment in (
        f"{stop_screw.STOCK_STANDARD} #4-40 UNC-{stop_screw.THREAD_CLASS}",
        f"head diameter {stop_screw.HEAD_DIA_MIN_MM:.5f}"
        f"..{stop_screw.HEAD_DIA_MAX_MM:.5f}",
        f"total height {stop_screw.HEAD_TOTAL_MIN_MM:.5f}"
        f"..{stop_screw.HEAD_TOTAL_MAX_MM:.5f}",
        f"under-head length {stop_screw.LENGTH_MIN_MM:.5f}"
        f"..{stop_screw.LENGTH_MAX_MM:.5f}",
        f"bearing circle MIN Ø{stop_screw.HEAD_BEARING_DIA_MIN_MM:.5f}",
        f"unslotted head height MIN {stop_screw.UNSLOTTED_HEAD_HEIGHT_MIN_MM:.5f} mm",
        f"thread major MAX Ø{stop_screw.THREAD_MAJOR_MAX_MM:.5f}",
        f"pitch diameter MIN Ø{stop_screw.EXTERNAL_PITCH_DIA_MIN_MM:.5f}",
        f"full-form useful engagement MIN {stop_screw.MIN_USEFUL_ENGAGEMENT_MM:.2f} mm",
    ):
        assert fragment in stop_row[1], fragment
    assert "sourced bounds are not proof of a measured installed screw" in stop_row[3]
    spring_row = gen_dimensions.find_row(record, "Chapter 25", "Return spring")
    assert spring_row is not None
    assert f"blade {spring.BLADE_STRAIGHT_LEN:.9f} mm" in spring_row[1]
    assert f"free preset {spring.PRESET:.9f}" in spring_row[1]
    assert f"/ {spring.PRESET_DEG:g}° further bend" in spring_row[1]


def test_superseded_rig_values_are_gone() -> None:
    prose = _prose(gen_dimensions.load_doc())
    for stale in (
        "−18.626",
        "15 wide × 5 thick",
        "Ø10.32",
        "cam eccentricity is 1.4",
        "R6.90 bracket scallops",
        # Only the retired follower-stud sentence: dt-crank's 64T crank-drive
        # gear row legitimately allows a silver-brazed shaft joint.
        "follower-stud mouth is silver-brazed",
        "34.0 foot",
        "−81.793",
        "2.115 thin-side",
        "retained 2 mm parked tip gap",
    ):
        assert stale not in prose, stale
