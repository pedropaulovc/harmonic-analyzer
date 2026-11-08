"""MHA-DT-00's drum-station setting: the assembly owns the band MHA-DT-22 drops.

Farm run 20261103T022858451Z's machinist review (2 of 3) read the arbor's
.XX drum station as a size to cut or check; Main's ruling (a) prints it on the
arbor as a reference and puts the setting band on an associative MHA-DT-00
dimension, the cylinder-bank settings' pattern (dt_cylinder_bank_setting_spec).
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

import build_dt_drive_train_assembly as assembly
import draw_dt_drive_train_assembly as drawing
import dt_cylinder_bank_setting_spec as bank_settings
import dt_drive_train_assembly_spec as package
import dt_drum_station_setting_spec as setting
import dt_pinion_arbor_geometry as arbor
import dt_pinion_arbor_spec as arbor_spec
from _drawing_tolerances import _tolerance_places

SCRIPTS = Path(__file__).resolve().parent
# Measured on run 20261103T022858451Z sheet 15 (90 dpi raster of the PDF):
# the frame's inner edge is at 419.1 mm and the title block's top at 65.5 mm;
# the DT-00 note font advances ~2.43 mm a character (the 43-character spring
# callout ran 104.4).  The package's view-overlap audit reads native view
# outlines, which pad the ink: run 20261103T063712849Z put the bank's right
# edge at 311.0 mm with its centre at 0.205, and the drum station view's left
# edge 58.3 mm left of its centre (305.7 at 0.364), past its 44 mm crop.
BANK_OUTLINE_RIGHT = 0.3110 - (0.205 - drawing.BANK_SETTING_CENTER[0])
DRUM_OUTLINE_LEFT_REACH = 0.0583
FRAME_INNER_RIGHT = 0.4191
FRAME_INNER_TOP = 0.2667
TITLE_BLOCK_TOP = 0.0655
NOTE_CHAR_ADVANCE = 0.00243


def test_the_leg_runs_from_the_placed_head_rear_face_to_the_placed_drum_front() -> None:
    """Assembly-frame ends from the built pose, not typed numbers: the arbor
    rides the drum at its station and both lie along machine Z."""
    ((feature, name, south, north),) = setting.LEGS
    assert (feature, name) == (setting.FEATURE, setting.DIMENSION)
    assert south == pytest.approx(assembly.ARBOR_Z0 + assembly.ARBOR_HEAD_REAR_Z, abs=1e-9)
    assert north == pytest.approx(assembly.APINION_Z_FRONT, abs=1e-9)
    assert north - south == pytest.approx(arbor.DRUM_STATION, abs=1e-9)
    assert setting.AXIS_Y == assembly.APINION_Y
    # The Right-plane leg is true length only along machine Z.
    assert [row[2] for row in assembly.ARBOR_ROWS] == [0.0, 0.0, 1.0]
    source = inspect.getsource(setting)
    for literal in ("60.96", "2.40", "0.254", "95.25"):
        assert literal not in source


def test_one_band_feeds_every_drum_station_stack() -> None:
    upper, lower = setting.DIMENSION_BANDS[setting.DIMENSION]
    assert upper is arbor.DRUM_STATION_BAND
    assert lower == -arbor.DRUM_STATION_BAND
    assert assembly.ARBOR_DRUM_STATION_BAND is arbor.DRUM_STATION_BAND
    assert arbor_spec.DRUM_STATION_BAND is arbor.DRUM_STATION_BAND
    for stack in (assembly.ARBOR_SOUTH_TRAVEL_STACK, assembly.ARBOR_NORTH_TRAVEL_STACK):
        bands = [value for key, value in stack.items() if "drum station" in key]
        assert bands == [arbor.DRUM_STATION_BAND]
    # ±.010 in is ±0.254 mm: the inch sheet prints it exactly, and the nominal
    # (on the .001 grid) at the band's three places.
    assert upper == pytest.approx(0.254)
    assert _tolerance_places(lower, upper, display_unit="in") <= setting.TOLERANCE_PRECISION
    assert setting.DRAWING_PRECISION == {
        setting.FEATURE: {setting.DIMENSION: setting.TOLERANCE_PRECISION}
    }
    places = setting.TOLERANCE_PRECISION
    assert round(arbor.DRUM_STATION / 25.4, places) * 25.4 == pytest.approx(
        arbor.DRUM_STATION, abs=1e-9
    )
    assert setting.DRAWING_DIMENSIONS == {setting.FEATURE: {setting.DIMENSION}}


def test_the_callout_says_what_is_set_from_where_and_when() -> None:
    lines = setting.DIMENSION_CALLOUTS[setting.DIMENSION].split("\n")
    text = " ".join(lines)
    assert "SET AT BOND" in text
    assert f"{arbor_spec.SETTING_DRAWING_NUMBER}" not in text  # printed on DT-00 itself
    assert "MHA-DT-22 HEAD REAR FACE" in text
    assert "MHA-DT-01 FRONT END" in text
    stripped = text.replace("MHA-DT-22", "").replace("MHA-DT-01", "")
    assert not any(char.isdigit() for char in stripped)
    # Widest line on top; the line on the dimension line stays inside the
    # extension lines so their overshoot cannot cross it.
    widths = [len(line) * NOTE_CHAR_ADVANCE for line in lines]
    assert widths[0] == max(widths)
    assert widths[-1] < arbor.DRUM_STATION / 1000.0


def test_build_authors_both_settings_through_one_globals_driven_recipe() -> None:
    source = inspect.getsource(assembly._author_setting_references)
    tree = ast.parse(source)
    spec_reads = {
        node.value.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name)
        and node.attr in {"LEGS", "AXIS_Y", "DIMENSION_BANDS", "DIMENSION_CALLOUTS"}
    }
    assert spec_reads == {"settings"}
    for call in (
        'adapter.create_sketch("Right")',
        "set_global(adapter, start_global",
        "set_global(adapter, axis_global",
        "set_global(adapter, name,",
        "drive_dimension(adapter, name, expression)",
        "set_dimension_symmetric_tolerance(\n            adapter, feature, name, upper,\n"
        "            display_unit=assembly_contract(ASM_NAME).drawing_unit,",
        "display_unit=assembly_contract(ASM_NAME).drawing_unit,\n            label=name,",
        "display.SetText(4, text)",
        "mark_dimensions_for_drawing(adapter, feature, names)",
        "blank_sketch(adapter, feature)",
    ):
        assert call in source
    build = inspect.getsource(assembly.build)
    assert "for settings in (bank_settings, drum_station_setting):" in build
    assert "await _author_setting_references(adapter, settings)" in build
    # The two specs keep distinct features, dimensions and globals.
    names = [name for spec in (bank_settings, setting) for _f, name, _s, _n in spec.LEGS]
    features = [feature for spec in (bank_settings, setting) for feature, *_ in spec.LEGS]
    assert len(set(names)) == len(names) and len(set(features)) == len(features)


def test_the_drum_station_view_isolates_the_arbor_and_drum() -> None:
    rig = set(package.CLUSTERS["pinion-rig"])
    assert drawing.DRUM_STATION_SETTING_STEMS == {"dt-pinion-arbor", "dt-alignment-pinion"}
    assert drawing.DRUM_STATION_SETTING_STEMS <= rig
    assert drawing.DRUM_STATION_SETTING_SCALE == (1.0, 1.0)
    assert drawing.SHEET_SCALES[drawing.SHEET_NAMES[drawing.BANK_SETTINGS_SHEET - 1]] == (
        drawing.DRUM_STATION_SETTING_SCALE
    )
    # The sheet names the drum's part, the alignment pinion, by its number.
    assert "MHA-DT-01 STATION SETTINGS" in drawing.SHEET_NAMES[drawing.BANK_SETTINGS_SHEET - 1]


def test_the_crop_holds_the_whole_head_and_the_drum_front_end() -> None:
    head_tip, drum_side = drawing.DRUM_STATION_CROP_Z
    assert head_tip == pytest.approx(
        assembly.ARBOR_Z0 + assembly.ARBOR_HEAD_FRONT_Z - assembly.ARBOR_HEAD_CAP_SAG
    )
    assert drum_side > setting.DRUM_FRONT_END_Z
    centre = drawing.DRUM_STATION_CROP_CENTRE_Z
    radius = drawing.DRUM_STATION_CROP_RADIUS_MM
    for z in (head_tip, setting.HEAD_REAR_FACE_Z, setting.DRUM_FRONT_END_Z, drum_side):
        assert abs(z - centre) < radius
    # The drum's teeth (tip radius) stay inside the circle at its front end.
    reach = (setting.DRUM_FRONT_END_Z - centre) ** 2 + assembly.TIP_APINION**2
    assert reach < radius**2


def test_the_drum_station_view_fits_beside_the_bank_above_the_title_block() -> None:
    gap = drawing.VIEW_CAPTION_GAP
    x, y = drawing.DRUM_STATION_SETTING_CENTER
    radius = drawing.DRUM_STATION_CROP_RADIUS_MM / 1000.0
    assert x - DRUM_OUTLINE_LEFT_REACH >= BANK_OUTLINE_RIGHT + gap
    assert x + radius <= FRAME_INNER_RIGHT - 2 * gap
    # The caption (one ~3.5 mm line, 8 mm under the circle) clears the title block.
    assert y - radius - 2 * gap - 0.0035 >= TITLE_BLOCK_TOP + gap
    # The value and callout block hangs over the circle, under the frame,
    # even if it grows upward from its text point.
    lines = setting.DIMENSION_CALLOUTS[setting.DIMENSION].count("\n") + 1
    assert drawing.DRUM_STATION_TEXT_Y - lines * 0.0056 >= y + radius + gap
    assert drawing.DRUM_STATION_TEXT_Y + lines * 0.0056 + 0.0035 <= FRAME_INNER_TOP - gap
    # Its widest line, centred on the leg's middle, stays in the column.
    width = max(map(len, setting.DIMENSION_CALLOUTS[setting.DIMENSION].split("\n")))
    middle_offset = (sum(setting.LEGS[0][2:]) / 2.0 - drawing.DRUM_STATION_CROP_CENTRE_Z) / 1000
    half = width * NOTE_CHAR_ADVANCE / 2.0
    assert x - abs(middle_offset) - half >= BANK_OUTLINE_RIGHT + gap
    assert x + abs(middle_offset) + half <= FRAME_INNER_RIGHT - gap


def test_the_settings_sheet_reads_back_the_drum_setting_like_the_bank() -> None:
    assert drawing.SETTING_DIMENSIONS[setting.FEATURE] == {setting.DIMENSION}
    assert drawing.SETTING_PRECISION[setting.DIMENSION] == setting.TOLERANCE_PRECISION
    assert drawing.SETTING_CALLOUTS[setting.DIMENSION] is (
        setting.DIMENSION_CALLOUTS[setting.DIMENSION]
    )
    assert drawing.SETTING_BANDS[setting.DIMENSION] == setting.DIMENSION_BANDS[setting.DIMENSION]
    # The bank's closed stack and spring gap are setting-table rows and
    # labels (rubric sample fix), not imported model dimensions.
    for name in (bank_settings.STACK_DIMENSION, bank_settings.SPRING_DIMENSION):
        assert name not in drawing.SETTING_PRECISION
        assert name not in drawing.SETTING_BANDS
    source = inspect.getsource(drawing._place_bank_setting_sheet)
    for fragment in (
        "adapter, drum_view, keep=drum_keep",
        "dimensions_by_feature=SETTING_DIMENSIONS",
        "drum_view.Crop2(False, False, 1)",
        "drum_view.IsCropped()",
        '(drum_view, DRUM_VIEW_CAPTION, False, "drum station caption")',
        "assert_imported_precision(adapter, annotations, SETTING_PRECISION)",
        "SETTING_CALLOUTS[name]",
        "SETTING_BANDS[name]",
        "(drum_view, drum_station_setting.DIMENSION, \"drum station setting\")",
    ):
        assert fragment in source
    # Never SetText on an imported dimension: the model owns the callout.
    assert "SetText(" not in source
