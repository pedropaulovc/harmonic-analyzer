"""Offline contracts for the paper-drive assembly and its drawing (MHA-PD-000)."""

import ast
import inspect
import math
import re
from itertools import product
from pathlib import Path

import pytest

import _assembly
import _chain as chain
import _config
import _drawing_common
import build_pd_paper_drive_assembly as assembly
import draw_pd_paper_drive_assembly as drawing
import dt_drive_train_steps
import fr_harmonic_base_spec as base
import fr_nameplate_spec as nameplate
import pd_paper_drive_assembly_steps as steps
import pd_paper_drive_explode_spec as explode
import pd_transgear_drive_collar_spec as collar
import transgear_cluster_fit as cluster_fit
import pd_transgear_front_bushing_spec as front_bushing
import vn_transgear_knob_cup_pin_spec as cup_pin
import pd_transgear_knob_cup_spec as cup
import pd_transgear_knob_shaft_spec as knob_shaft
import pd_transgear_rear_bushing_spec as rear_bushing
import pd_transgear_removable_spec as sprocket
from _drawing_layout_check import LeaderSegment, find_leader_leader_crossings
from _drawing_registry import DRAWING_TEMPLATES, DRAWINGS_BY_NAME

STEP_HEAD = re.compile(r"^(\d+)\. ", re.MULTILINE)
STEP_POINTER = re.compile(r"(MHA-[A-Z]{2}-000)\s+STEP\s+(\d+)")
# Default-format note text, measured on r743-rocker-fix3's render (leaf
# 20260926T112244Z-1-a884759d), as test_channel_assembly_drawing uses them;
# #945 moves these into _drawing_common.
NOTE_CHAR_WIDTH = 0.00276
NOTE_LINE_PITCH = 0.0045
# Words no sheet of the package may print (drawing-simplicity policy).
FORBIDDEN_SHEET_WORDS = ("EXCEPTION", "ACCEPTED", "RULING", "POLICY", "BOOK FIDELITY")

# CONTRACT-paper-drive.md, the round-10 component set.
UNCHANGED_FAMILIES = {
    "pd-support-bar",
    "sh-column-clamp-front",
    "sh-column-clamp-back",
    "vn-clamp-screw",
    "pd-platen",
    "pd-platen-rack",
    "pd-platen-guide",
    "pd-guide-lock",
    "pd-platen-clip",
    "pd-platen-paper",
    "vn-fillister-screw",
    "vn-guide-lock-screw",  # R9-31: the eight lock screws leave MHA-VN-006
    "vn-chain-inner-link",
    "vn-chain-outer-link",
    "pd-transgear-removable",
}
CONTRACT_TRANSGEAR_QUANTITIES = {
    "pd-transgear-arm": 1,
    "pd-transgear-arm-plate": 1,
    "vn-transgear-arm-plate-screw": 2,
    "pd-transgear-pivot-spacer": 1,
    "vn-transgear-pivot-screw": 1,
    "vn-transgear-pivot-spring": 1,
    "vn-transgear-latch-pin": 1,
    "pd-latch-hook-bracket": 1,
    "vn-latch-hook-bracket-screw": 2,
    "pd-latch-hook": 1,
    "vn-latch-hook-rivet": 2,
    "pd-transgear-pin": 1,
    "pd-transgear-rear-bushing": 1,
    "pd-transgear-feed-pinion": 1,
    "pd-transgear-disc-hub": 1,
    "pd-transgear-front-bushing": 1,
    "vn-transgear-retaining-ring": 1,
    "pd-rack-pinion": 1,
    "vn-transgear-disc-screw": 3,
    "pd-transgear-knob-shaft": 1,
    "pd-transgear-drive-collar": 1,
    "vn-transgear-collar-cross-pin": 1,
    "vn-transgear-knob-drive-pin": 2,
    "pd-transgear-removable": 3,
    "pd-transgear-thumbnut": 1,
    "pd-transgear-knob-thrust-ring": 1,
    "pd-transgear-knob-cup": 1,
    "vn-transgear-knob-cup-pin": 1,
}
RETIRED_FAMILIES = {
    "transgear-latch",
    "transgear-pinion",
    "transgear-bracket",
    "bracket-screw",
}


def _step_body(key: str) -> str:
    """The printed text of one step, from its head to the next head."""
    text = drawing.FITUP_STEPS
    heads = list(STEP_HEAD.finditer(text))
    index = steps.step_number(key) - 1
    end = heads[index + 1].start() if index + 1 < len(heads) else len(text)
    return " ".join(text[heads[index].end() : end].split())


def _number(stem: str) -> str:
    return _config.parts(stem)["number"]


def _literal_number(script: str, key: str) -> str:
    """The drawing number a build script stamps into its Number property."""
    path = Path(drawing.__file__).with_name(script)
    tree = ast.parse(path.read_text(encoding="utf-8"))
    values = {
        node.values[index].value
        for node in ast.walk(tree)
        if isinstance(node, ast.Dict)
        for index, item in enumerate(node.keys)
        if isinstance(item, ast.Constant) and item.value == key
    }
    (value,) = values
    return value


def test_paper_drive_keeps_registry_outputs_and_names_its_sheets() -> None:
    spec = DRAWINGS_BY_NAME["pd_paper_drive_assembly"]
    assert spec.source_kind == "assembly"
    assert spec.part == "pd_paper_drive"
    assert drawing.SOURCE == spec.source
    assert drawing.OUTPUTS == drawing.OUTPUTS.__class__(
        spec.outputs["slddrw"], spec.outputs["pdf"], spec.outputs["png"]
    )
    assert set(drawing.SHEET_SCALES) == set(drawing.SHEET_NAMES)
    assert set(drawing.SHEET_LAYOUTS) == set(drawing.SHEET_NAMES)
    assert len(set(drawing.SHEET_NAMES)) == len(drawing.SHEET_NAMES)


def test_the_step_registry_names_this_sheet() -> None:
    assert steps.DRAWING_NUMBER == _literal_number(
        "build_pd_paper_drive_assembly.py", "Number"
    )
    assert steps.step_ref(steps.SEQUENCE[3]) == f"{steps.DRAWING_NUMBER} STEP 4"
    with pytest.raises(KeyError):
        steps.step_number("no-such-step")


def test_the_printed_step_heads_are_the_registry_in_order() -> None:
    printed = [int(n) for n in STEP_HEAD.findall(drawing.FITUP_STEPS)]
    assert printed == list(range(1, len(steps.SEQUENCE) + 1))
    # The hook step opens the second column, the chain fit-up under it.
    second = [int(n) for n in STEP_HEAD.findall(drawing.FITUP_COLUMNS[1])]
    assert second[0] == steps.step_number(drawing.FITUP_SECOND_COLUMN_KEY)


def test_the_crank_side_pointer_names_the_sheet_that_prints_those_steps() -> None:
    """§13.2 (1): the chain fit-up starts from the crank side's own fit-up,
    and the pointer names the MHA-DT-000 sheet whose note prints both steps."""
    import draw_dt_drive_train_assembly as drive_train

    pointers = re.findall(
        r"(MHA-[A-Z]{2}-000) SHEET (\d+), STEPS (\d+) AND (\d+)",
        drawing.FITUP_COLUMNS[1].replace("\n", " "),
    )
    wanted = [str(dt_drive_train_steps.step_number(key)) for key in steps.CRANK_SIDE_KEYS]
    assert pointers == [
        (dt_drive_train_steps.DRAWING_NUMBER, str(drive_train.SEQUENCE_SHEET), *wanted)
    ]
    assert steps.CRANK_SIDE_KEYS == ("crank-mesh-checked", "paper-drive-wheel")
    # The cone-and-crank steps are the note package_note_fields stacks on
    # SEQUENCE_SHEET.
    printed = set(STEP_HEAD.findall(drive_train.CONE_CRANK_STEPS))
    assert set(wanted) <= printed
    fitup_ref = steps.step_number(drawing.FITUP_CHAIN_KEY)
    assert f"STEP {fitup_ref}" in _step_body("fitup-accepted")
    heading = drawing.FITUP_COLUMNS[1].index("CHAIN FIT-UP")
    assert drawing.FITUP_COLUMNS[1].index(f"\n{fitup_ref}. ") > heading


def test_the_steps_fit_their_fields() -> None:
    template = DRAWING_TEMPLATES[drawing.SPEC.layout]
    fields = (
        *zip(drawing.FITUP_NOTES, drawing.FITUP_NOTE_XY, drawing.FITUP_NOTE_LIMITS),
        (
            drawing.PLATEN_STEPS,
            drawing.PLATEN_NOTE_XY,
            (drawing.PLATEN_NOTE_RIGHT, template.title_block_top_m),
        ),
    )
    for text, (left, top), (right_limit, bottom_limit) in fields:
        lines = text.splitlines()
        assert left + max(map(len, lines)) * NOTE_CHAR_WIDTH < right_limit
        assert top - len(lines) * NOTE_LINE_PITCH > bottom_limit
    (first_left, _), (second_left, _) = drawing.FITUP_NOTE_XY
    first_limit, second_limit = drawing.FITUP_NOTE_LIMITS
    assert first_limit[0] < second_left
    assert second_limit[1] > template.title_block_top_m
    assert first_left > 0.0 and second_limit[0] < template.width_m
    # Sheet 3's caption sits under its steps, sheet 1's under the front view.
    assert drawing.EXPLODED_CAPTION_XY[1] < drawing.PLATEN_NOTE_XY[1] - (
        len(drawing.PLATEN_STEPS.splitlines()) * NOTE_LINE_PITCH
    )
    assert drawing.EXPLODED_CAPTION_XY[1] - NOTE_LINE_PITCH > template.title_block_top_m


def test_the_bom_fits_left_of_the_title_block_and_inside_the_border() -> None:
    """Machinist review of 6c385465d: item 41 sat below the inner border; the
    old check stopped at the sheet's edge."""
    template = DRAWING_TEMPLATES[drawing.SPEC.layout]
    left, top = drawing.BOM_ANCHOR
    width = sum(drawing.BOM_COLUMN_WIDTHS.values())
    # A description past the measured one-line length wraps to a second line.
    wrapped = sum(
        len(text) > drawing.BOM_DESCRIPTION_MAX_CHARS
        for text in drawing.BOM_DESCRIPTIONS.values()
    )
    assert wrapped <= len(drawing.GROUPED_DESCRIPTION_STEMS)
    height = (len(drawing.BOM_PART_NUMBERS) + 1 + wrapped) * drawing.BOM_ROW_HEIGHT
    assert left + width < template.title_block_left_m
    assert top - height >= (
        drawing.SHEET_INNER_BORDER_BOTTOM + drawing.BOM_BORDER_CLEARANCE
    )
    assert top < template.height_m - 0.003


def test_bom_rows_are_exactly_the_round10_families() -> None:
    families = set(drawing.BOM_PART_NUMBERS)
    assert families == UNCHANGED_FAMILIES | set(CONTRACT_TRANSGEAR_QUANTITIES)
    assert not families & RETIRED_FAMILIES
    assert drawing.TRANSGEAR_QUANTITIES == CONTRACT_TRANSGEAR_QUANTITIES


def test_bom_numbers_and_purchased_skus_come_from_the_registry() -> None:
    for stem, number in drawing.BOM_PART_NUMBERS.items():
        assert number == _number(stem), stem
    for stem, description in drawing.BOM_DESCRIPTIONS.items():
        skus = _config.parts(stem).get("supplier_skus") or ()
        if skus:
            assert description.endswith(f"MCMASTER {skus[0]}"), stem
        else:
            assert "MCMASTER" not in description, stem
    # A number never repeats, so the alias map is total.
    assert len(drawing.BOM_NORMALIZED_ALIASES) == len(drawing.BOM_PART_NUMBERS)


def test_sheet_two_shows_and_balloons_exactly_the_transgear() -> None:
    expected = {
        f"{stem}-{index}"
        for stem, count in CONTRACT_TRANSGEAR_QUANTITIES.items()
        for index in range(1, count + 1)
        if stem != "pd-transgear-removable"
    } | {"pd-transgear-removable-1"}
    assert drawing.TRANSGEAR_INSTANCES == expected
    # The collar alone has no batch anchor: it balloons on its rear rim.
    anchored = set(CONTRACT_TRANSGEAR_QUANTITIES) - {drawing.COLLAR_STEM}
    assert set(drawing.TRANSGEAR_BALLOON_ANCHORS) == anchored
    # The knob's T24 is instance 1; the crank T12 and the spare T18 stay off.
    assert drawing.TRANSGEAR_BALLOON_ANCHORS["pd-transgear-removable"].instance == (
        "pd-transgear-removable-1"
    )


def test_the_collar_leader_lands_on_its_rear_rim_beside_the_lower_end() -> None:
    # The inner view sees the collar's rims edge-on from the right; hit tests
    # missed them on farm runs 20261002T160324403Z, 20261002T164049933Z and
    # 20261002T171234232Z. The leader lands past the drive-pin hole, so one
    # re-solved to the rim line's nearer end stays in limit.
    x, y, z = drawing.COLLAR_LANDING_MM
    radius = collar.OD / 2.0
    assert math.hypot(x, y) == pytest.approx(radius, abs=1e-9)
    assert z == pytest.approx(collar.LENGTH)
    assert -y > collar.PIN_CIRCLE_RADIUS + collar.PIN_HOLE_DIA / 2.0
    # Green run 20261001T172013211Z's 1:2 rear-rim line, -Y end to +Y end.
    minus_end, plus_end = (0.21852, 0.171822), (0.21852, 0.180572)
    landing = drawing.collar_rim_landing(minus_end, plus_end)
    assert landing[0] == pytest.approx(0.21852)
    assert landing[1] - minus_end[1] == pytest.approx((radius + y) / 2.0 / 1000.0)
    largest_scale = max(num / den for num, den in drawing.INNER_SCALE_LADDER)
    end_gap_m = (radius + y) * largest_scale / 1000.0
    assert end_gap_m < _drawing_common._BALLOON_LANDING_TOLERANCE_M / 2.0
    # Below the axis is away from the feed sleeve: its stud stands above the knob.
    assert assembly.STUD_XY[1] > assembly.KNOB_SHAFT_XY[1]


def _circle(
    z: float, radius: float, closest: tuple[float, float, float], axis_z: float = 1.0
) -> drawing.RimCandidate:
    return drawing.RimCandidate(
        edge=object(),
        circle=(0.0, 0.0, z, 0.0, 0.0, axis_z, radius),
        closest_mm=closest,
    )


def test_the_collar_rim_matcher_takes_the_one_arc_holding_the_landing() -> None:
    radius, z = collar.OD / 2.0, collar.LENGTH
    landing = drawing.COLLAR_LANDING_MM
    # The rear slot splits the rear rim: the -Y arc holds the landing, the +Y
    # arc's nearest point is its end at the slot's wall.
    lower = _circle(z, radius, landing)
    slot_y = collar.SLOT_WIDTH / 2.0
    upper = _circle(z, radius, (-math.sqrt(radius**2 - slot_y**2), slot_y, z))
    front = _circle(0.0, radius, (landing[0], landing[1], 0.0))
    bore = _circle(z, collar.BORE_DIA / 2.0, (landing[0] / 2, landing[1] / 2, z))
    assert drawing.collar_rear_rim([front, upper, lower, bore]) is lower
    # Either axis sense is the collar's.
    flipped = _circle(z, radius, landing, axis_z=-1.0)
    assert drawing.collar_rear_rim([front, flipped, upper]) is flipped
    # 2 micrometres off the landing is another arc.
    near = _circle(z, radius, (landing[0], landing[1] - 0.002, z))
    with pytest.raises(RuntimeError, match=r"matched 0 of 4 circles: r 8\.7500"):
        drawing.collar_rear_rim([front, upper, bore, near])
    with pytest.raises(RuntimeError, match="matched 0 of 0 circles: none"):
        drawing.collar_rear_rim([])
    with pytest.raises(RuntimeError, match="matched 2 of 3 circles"):
        drawing.collar_rear_rim([lower, flipped, upper])


# Farm run 20261002T180658288Z's inner-view ring (its drawing.balloon_ring
# event): BOM item and attachment (sheet m), in ring order. 17 is the
# arm-plate screw, 24 the rear bushing, 32 the collar.
INNER_RING_180658 = (
    ("34", (0.219889, 0.176708)),
    ("32", (0.220362, 0.174046)),
    ("18", (0.229903, 0.170997)),
    ("35", (0.234541, 0.176240)),
    ("39", (0.236058, 0.178096)),
    ("26", (0.226995, 0.178996)),
    ("24", (0.228995, 0.180840)),
    ("17", (0.233308, 0.188817)),
    ("33", (0.218228, 0.178923)),
)
# That run logged no outline: run 20261002T172458664Z's 1:2 inner outline,
# scaled to 1:3 about the collar's landing (218.520, 171.821 there; 220.362,
# 174.046 here). Its circles render r 5.232 mm.
INNER_OUTLINE_180658 = (0.209403, 0.162653, 0.239943, 0.192772)
BALLOON_RADIUS = 0.005232


def _ring_centres(
    outline: tuple[float, float, float, float],
) -> list[tuple[float, float]]:
    """_spread_balloons' circle centres for INNER_RING_180658, in its order."""
    cx, cy = (outline[0] + outline[2]) / 2.0, (outline[1] + outline[3]) / 2.0
    rx = (outline[2] - outline[0]) / 2.0 + drawing.BALLOON_MARGIN
    ry = (outline[3] - outline[1]) / 2.0 + drawing.BALLOON_MARGIN
    thetas = [math.atan2(y - cy, x - cx) for _item, (x, y) in INNER_RING_180658]
    order = sorted(range(len(thetas)), key=thetas.__getitem__)
    gap = _drawing_common._min_angular_gap(
        min(rx, ry), BALLOON_RADIUS, clearance=_drawing_common._BALLOON_CLEARANCE_M
    )
    angles = _drawing_common._push_apart_on_ring(
        [thetas[index] for index in order], min_gap=gap
    )
    centres = [(0.0, 0.0)] * len(thetas)
    for index, angle in zip(order, angles):
        centres[index] = (cx + rx * math.cos(angle), cy + ry * math.sin(angle))
    return centres


def _crossed_items(
    centres: list[tuple[float, float]], slots: list[int]
) -> set[frozenset[str]]:
    """The item pairs whose printed leaders, circle edge to attachment, cross."""
    segments = []
    for (item, (x, y)), slot in zip(INNER_RING_180658, slots):
        bx, by = centres[slot]
        length = math.hypot(x - bx, y - by)
        segments.append(
            LeaderSegment(
                label=item,
                kind="balloon",
                x0=bx + (x - bx) / length * BALLOON_RADIUS,
                y0=by + (y - by) / length * BALLOON_RADIUS,
                x1=x,
                y1=y,
            )
        )
    return {
        frozenset((crossing.a.label, crossing.b.label))
        for crossing in find_leader_leader_crossings(segments)
    }


def test_the_inner_ring_swaps_crossing_leaders_onto_each_others_slots() -> None:
    attachments = [attach for _item, attach in INNER_RING_180658]
    identity = list(range(len(INNER_RING_180658)))
    centres = _ring_centres(INNER_OUTLINE_180658)
    # The ring as run 20261002T180658288Z left it crosses 17 over 24.
    assert _crossed_items(centres, identity) == {frozenset({"17", "24"})}
    slots = drawing.uncrossed_ring_slots(centres, attachments)
    moved = {INNER_RING_180658[index][0] for index in identity if slots[index] != index}
    assert moved == {"17", "24"}
    assert _crossed_items(centres, slots) == set()
    # The outline is reconstructed: within 2 mm of it either way, whatever
    # the ring crosses, the slots it takes cross nothing, and no leader runs
    # through another balloon's circle.
    for dx, dy in product((-0.002, 0.0, 0.002), repeat=2):
        x0, y0, x1, y1 = INNER_OUTLINE_180658
        shifted = _ring_centres((x0 + dx, y0 + dy, x1 + dx, y1 + dy))
        slots = drawing.uncrossed_ring_slots(shifted, attachments)
        assert sorted(slots) == identity
        assert _crossed_items(shifted, slots) == set(), (dx, dy)
        for index, (x, y) in enumerate(attachments):
            bx, by = shifted[slots[index]]
            for other, (ox, oy) in enumerate(shifted):
                if other == slots[index]:
                    continue
                t = ((ox - bx) * (x - bx) + (oy - by) * (y - by)) / (
                    (x - bx) ** 2 + (y - by) ** 2
                )
                t = min(1.0, max(0.0, t))
                gap = math.hypot(bx + t * (x - bx) - ox, by + t * (y - by) - oy)
                assert gap > BALLOON_RADIUS, (dx, dy, index, other)


def test_an_uncrossed_ring_keeps_its_slots() -> None:
    centres = [(0.0, 1.0), (1.0, 0.0), (0.0, -1.0)]
    attachments = [(0.0, 0.1), (0.1, 0.0), (0.0, -0.1)]
    assert drawing.uncrossed_ring_slots(centres, attachments) == [0, 1, 2]
    # Two leaders swapped across each other go back.
    assert drawing.uncrossed_ring_slots(centres[:2], attachments[1::-1]) == [1, 0]


# The transgear families the sheet-2 isometric draws no reachable ink of (farm
# run 20261001T051043622Z failed on the sleeve; the rear bushing stands behind
# the Ø81.5 disc): they balloon on the inner view.
HIDDEN_BY_THE_ISOMETRIC = {
    "pd-transgear-feed-pinion",
    "pd-transgear-knob-shaft",
    "pd-transgear-drive-collar",
    "vn-transgear-collar-cross-pin",
    "vn-transgear-knob-drive-pin",
    "vn-transgear-knob-cup-pin",
    "vn-transgear-arm-plate-screw",
    "vn-transgear-latch-pin",
    "pd-transgear-rear-bushing",
}


def test_each_transgear_family_balloons_once_on_the_view_that_shows_it() -> None:
    # Item numbers against the dict order, so the order must come from them.
    items = {
        stem: str(len(drawing.BOM_PART_NUMBERS) - index)
        for index, stem in enumerate(drawing.BOM_PART_NUMBERS)
    }
    iso, inner = drawing.transgear_balloon_items(items)
    iso_stems = {stem for stem, _item in iso}
    inner_stems = {stem for stem, _item in inner}
    assert inner_stems == HIDDEN_BY_THE_ISOMETRIC
    assert iso_stems == set(CONTRACT_TRANSGEAR_QUANTITIES) - HIDDEN_BY_THE_ISOMETRIC
    for balloons in (iso, inner):
        assert all(items[stem] == item for stem, item in balloons)
        numbers = [int(item) for _stem, item in balloons]
        assert numbers == sorted(numbers)
    # The inner view shows every instance of its families and nothing else,
    # so no outer part covers them there.
    assert drawing.INNER_INSTANCES == {
        f"{stem}-{index}"
        for stem in inner_stems
        for index in range(1, CONTRACT_TRANSGEAR_QUANTITIES[stem] + 1)
    }
    assert drawing.INNER_INSTANCES <= drawing.TRANSGEAR_INSTANCES


# Native run 20261001T062924323Z (024e240b3) read sheet 2's outlines in x: the
# isolated transgear at 2:3 centred at x 355 mm spans 295.3 to 404.8, the
# inner *Right view at 2:3 placed at x 240 spans 201.0 to 258.3. Their y
# extents are estimates from the builder's stations (the run reported no y).
ISO_OUTLINE_AT_355 = (0.2953, 0.1438, 0.4048, 0.2319)
INNER_OUTLINE_AT_2_3 = (0.2010, 0.1622, 0.2583, 0.2179)


def _iso_outline(center_x: float) -> tuple[float, float, float, float]:
    dx = center_x - 0.355
    x0, y0, x1, y1 = ISO_OUTLINE_AT_355
    return (x0 + dx, y0, x1 + dx, y1)


def _scaled(
    outline: tuple[float, float, float, float], scale: tuple[float, float]
) -> tuple[float, float, float, float]:
    """``outline`` (read at 2:3) at ``scale``, about its centre."""
    k = (scale[0] / scale[1]) / (2.0 / 3.0)
    x0, y0, x1, y1 = outline
    cx, cy, hw, hh = (x0 + x1) / 2, (y0 + y1) / 2, (x1 - x0) / 2 * k, (y1 - y0) / 2 * k
    return (cx - hw, cy - hh, cx + hw, cy + hh)


def test_the_024e240b3_layout_is_refused_naming_each_overflow() -> None:
    """The native failure: both views at 2:3, the isometric centred at 355."""
    with pytest.raises(ValueError) as refused:
        drawing.inner_view_shift(_iso_outline(0.355), INNER_OUTLINE_AT_2_3)
    message = str(refused.value)
    assert "isometric ring right 421.8 mm past 415.0 mm" in message
    assert "inner view ring left 184.0 mm past 185.0 mm" in message
    assert (
        "inner view ring right 275.3 mm within 4 mm of the isometric ring (278.3 mm)"
        in message
    )
    with pytest.raises(ValueError, match="no inner-view scale fits.*1:2.*1:3"):
        drawing.inner_view_scale(_iso_outline(0.355), INNER_OUTLINE_AT_2_3, (2.0, 3.0))


def test_both_rings_fit_between_the_bom_and_the_sheet_edge_with_margin() -> None:
    iso = _iso_outline(drawing.TRANSGEAR_VIEW_CENTER[0])
    scale = drawing.inner_view_scale(iso, INNER_OUTLINE_AT_2_3, (2.0, 3.0))
    assert scale == (1.0, 2.0)
    inner = _scaled(INNER_OUTLINE_AT_2_3, scale)
    dx, dy = drawing.inner_view_shift(iso, inner)
    reach = drawing.BALLOON_RING_REACH
    iso_left, iso_right = iso[0] - reach, iso[2] + reach
    left, right = inner[0] + dx - reach, inner[2] + dx + reach
    assert drawing.BOM_RIGHT == pytest.approx(0.182)
    assert iso_right <= 0.415 - 0.002
    assert left >= drawing.BOM_RIGHT + 0.003 + 0.0015
    assert right <= iso_left - drawing.SHEET_TWO_RING_GAP - 0.0015
    # Level with the isometric.
    assert (inner[1] + inner[3]) / 2.0 + dy == pytest.approx((iso[1] + iso[3]) / 2.0)
    # Its caption stands under the ring, over the title block, left of the
    # isometric's ring.
    template = DRAWING_TEMPLATES[drawing.SPEC.layout]
    caption_top = inner[1] + dy - reach - drawing.INNER_CAPTION_GAP
    assert caption_top - NOTE_LINE_PITCH > template.title_block_top_m
    assert left + len(drawing.INNER_CAPTIONS[scale]) * NOTE_CHAR_WIDTH < iso_left


def test_an_inner_view_wider_than_measured_steps_down_to_1_3() -> None:
    """Ten per cent wider at 2:3 overflows at 1:2; 1:3 then fits."""
    x0, y0, x1, y1 = INNER_OUTLINE_AT_2_3
    wider = (x0 - (x1 - x0) * 0.05, y0, x1 + (x1 - x0) * 0.05, y1)
    iso = _iso_outline(drawing.TRANSGEAR_VIEW_CENTER[0])
    with pytest.raises(ValueError, match="inner view ring"):
        drawing.inner_view_shift(iso, _scaled(wider, (1.0, 2.0)))
    assert drawing.inner_view_scale(iso, wider, (2.0, 3.0)) == (1.0, 3.0)


def test_no_sheet_prints_a_forbidden_word() -> None:
    texts = (*drawing.SHEET_TEXTS, *drawing.BOM_DESCRIPTIONS.values())
    for text in texts:
        for word in FORBIDDEN_SHEET_WORDS:
            assert word not in text.upper(), (word, text)


def test_no_retired_part_is_named_on_the_sheet() -> None:
    retired = {"MHA-079", "MHA-080", "MHA-108", "MHA-109"}
    printed = set(re.findall(r"MHA-[A-Z]{2}-\d{3}", drawing.FITUP_STEPS))
    assert not printed & retired
    assert printed <= set(drawing.BOM_PART_NUMBERS.values())


def test_the_knob_stack_prints_front_to_rear() -> None:
    """Contract §1: thumbnut | T24 | collar | 12T | ring | plate hub | plate |
    rear boss | cup | screw."""
    body = _step_body("knob-stack-fitted")
    order = [
        "pd-transgear-thumbnut",
        "pd-transgear-removable",
        "pd-transgear-drive-collar",
        "pd-transgear-knob-shaft",
        "pd-transgear-knob-thrust-ring",
        "pd-transgear-arm-plate",
        "pd-transgear-knob-cup",
        "vn-transgear-knob-cup-pin",
    ]
    assert [stem for stem, _label in drawing.KNOB_STACK if stem] == order
    positions = [body.index(_number(stem)) for stem in order]
    assert positions == sorted(positions)
    assert body.index("PLATE HUB") < body.index(_number("pd-transgear-arm-plate"))
    assert body.index("REAR BOSS") < body.index(_number("pd-transgear-knob-cup"))


def test_the_pivot_screw_is_threadlocked_and_the_spacer_pressed_as_made() -> None:
    """R9-7 adds threadlocker to MHA-VN-041; R9-6 never faces MHA-PD-020.  R9-71:
    the spacer is pressed on the shoulder flush with its end, and the MHA-VN-049
    spring under the head holds the arm on it."""
    body = _step_body("hanger-pivoted")
    assert "LOW-STRENGTH THREADLOCKER" in body
    assert _number("vn-transgear-pivot-screw") in body
    assert _number("pd-transgear-pivot-spacer") in body
    assert _number("vn-transgear-pivot-spring") in body
    assert "AS MADE" in body
    assert "FLUSH WITH ITS END ON A FLAT" in body
    # No step shortens the spacer.
    assert not re.search(r"\bFACE (IT|THE SPACER|TO)\b", drawing.FITUP_STEPS)


def test_the_fitup_acceptance_prints_the_contract_bands() -> None:
    """§13.2 (8): offset 0.05 ±0.10, knob float at the cup's feeler band
    (R9-70: 0.15..0.25), collar-disc air 0.10 min, the T24 free under the
    nut.  R9-71: the hanger has no head play left to read."""
    assert drawing.KNOB_END_FLOAT_RANGE == pytest.approx((0.15, 0.25), abs=1e-9)
    body = _step_body("fitup-accepted")
    for text in (
        "0.05 \u00b10.10 FORWARD",
        "0.15 TO 0.25",
        "0.10 MIN",
        "T24 FREE UNDER THE NUT",
    ):
        assert text in body, text
    assert "HEAD PLAY" not in body


def test_the_knob_stack_is_pinned_and_the_nut_seats_on_the_faced_pilot() -> None:
    """R9-70: the cup set on the end-float feeler and cross-pinned to the
    journal at the cup spec's station; the collar's pilot faced proud of the
    wheels before the collar is pinned, and the nut tightened on it."""
    knob = _step_body("knob-stack-fitted")
    for text in (
        f"{knob_shaft.END_FLOAT:.1f} FEELER AT THE BOSS",
        cup_pin.HOLE_TEXT,
        f"{cup.PIN_HOLE_FROM_FRONT:.1f} FROM THE CUP FRONT",
    ):
        assert text in knob, text
    seq = steps.SEQUENCE
    assert seq.index("pilot-faced-to-fit") < seq.index("knob-stack-fitted")
    assert seq.index("pilot-faced-to-fit") < seq.index("collar-pinned")
    assert f"{collar.PILOT_PROUD_TEXT} PROUD" in _step_body("pilot-faced-to-fit")
    assert _step_body("collar-pinned").endswith("TIGHT ON THE PILOT.")


def test_the_collar_gap_stop_is_the_seat_limit_less_the_collar() -> None:
    """§13.2 (4): g past the collar's seat limit from the 12T front face less
    its length L stops the fit-up."""
    assert drawing.COLLAR_GAP_MAX == pytest.approx(
        collar.SEAT_MAX_FROM_F - collar.LENGTH, abs=1e-9
    )
    body = _step_body("collar-gap-measured")
    assert f"{drawing.COLLAR_GAP_MAX:.2f}" in body
    assert f"g = d + {collar.FIT_UP_OFFSET_TARGET:.2f}" in body


def test_the_fitup_steps_and_the_collar_note_print_one_setting_drill_and_cut() -> None:
    """R9-30: the collar steps and the MHA-PD-022 fit-up note (which the collar's
    own sheet prints) state the collar setting, the core drill and the stud
    cut in the same words, so the two instructions cannot drift apart; the
    steps also carry the note's two seat limits, so A06 need not repeat it."""
    note = " ".join(collar.FIT_UP_NOTE.split())
    for key, phrase in (
        ("collar-gap-measured", collar.FIT_UP_OFFSET_SET_TEXT),
        ("collar-pinned", collar.CROSS_PIN_DRILL_PHRASE),
        ("stud-end-cut", collar.STUD_CUT_PHRASE),
    ):
        assert phrase in _step_body(key), key
        assert phrase in note, key
    gap_step = _step_body("collar-gap-measured")
    assert f"T24 SEAT {collar.SEAT_MAX_FROM_F:.2f} MAX IN FRONT OF THE 12T" in gap_step
    assert "COLLAR-TO-12T GAP 0 MIN" in gap_step
    assert not any("COLLAR SUPPLIED UNPINNED" in text for text in drawing.SHEET_TEXTS)
    # The drill phrase carries the cross pin's functional hole band (R9-11).
    assert "\u00d81.6 +0.05/0 THROUGH THE CORE" in collar.CROSS_PIN_DRILL_PHRASE
    assert "0.3 TO 1.0 BELOW THE RIM" in collar.STUD_CUT_PHRASE


def test_the_collar_is_pinned_before_the_stud_is_cut_and_the_stack_accepted() -> None:
    order = [
        "hook-set-and-riveted",
        "fitup-pose-set",
        "collar-gap-measured",
        "collar-pinned",
        "stud-end-cut",
        "fitup-accepted",
    ]
    numbers = [steps.step_number(key) for key in order]
    assert numbers == sorted(numbers)
    # Only the chain's closure and run follow the transgear's acceptance.
    assert steps.SEQUENCE.index("fitup-accepted") == len(steps.SEQUENCE) - 3
    # The drive pins are in the collar before the stack is built.
    assert steps.step_number("collar-pins-pressed") < steps.step_number(
        "knob-stack-fitted"
    )


def test_the_cluster_float_and_pin_bands_print_their_spec_ranges() -> None:
    rear = _step_body("rear-bushing-faced-to-fit")
    assert f"DISC END FLOAT {cluster_fit.FLOAT_WINDOW_TEXT}" in rear
    assert cluster_fit.FIT_WINDOW_TEXT in _step_body("front-bushing-faced-to-fit")
    assert "2.30 TO 2.50 PROUD" in _step_body("collar-pins-pressed")
    assert "12.96 TO 14.49 PROUD" in _step_body("latch-pin-pressed")


def test_the_hub_recess_is_in_m_and_in_the_disc_end_float() -> None:
    """Codex P2 (6c385465d): the hub stands up to HUB_NOSE_WINDOW behind the
    nose, so hub and disc reach the front bushing that much ahead of the
    step. m is read with them forward, so the recess cannot close it below
    FIT_WINDOW's minimum, and the front bushing's longest fit carries it; the
    rear bushing leaves the sleeve the float less the recess, so the disc's
    end float stays FLOAT_WINDOW (the disc-to-platen stack's term)."""
    recess = cluster_fit.HUB_NOSE_WINDOW
    longest = (
        cluster_fit.FRONT_CHAIN_NOMINAL
        + cluster_fit.FRONT_CHAIN_BAND
        + cluster_fit.FIT_WINDOW[1]
        + recess[1]
    )
    assert cluster_fit.FRONT_BUSHING_FITTED_MAX == pytest.approx(longest)
    assert front_bushing.BLANK_LENGTH_MIN >= longest + front_bushing.FACING_ALLOWANCE
    sleeve = cluster_fit.SLEEVE_FLOAT_WINDOW
    for r in recess:
        assert cluster_fit.FLOAT_WINDOW[0] <= sleeve[0] + r
        assert sleeve[1] + r <= cluster_fit.FLOAT_WINDOW[1] + 1e-9
    # The model, cluster rearward with the hub on the step, reads m forward.
    forward = (
        cluster_fit.SLEEVE_FLOAT_WINDOW_CENTRE + cluster_fit.HUB_NOSE_WINDOW_CENTRE
    )
    assert cluster_fit.DISC_FRONT_Z - forward - cluster_fit.F_Z == pytest.approx(
        cluster_fit.FIT_WINDOW_CENTRE
    )
    assert "CLUSTER, HUB AND DISC FORWARD, FEEL m" in _step_body(
        "front-bushing-faced-to-fit"
    )


def test_the_rear_bushing_blank_is_faced_to_the_gauged_gap_before_it_goes_on() -> None:
    """Codex P2 (724f78f26): the MHA-PD-024 blank is longer than the gap it
    fills (6.85 MIN against 6.30 nominal, cluster forward), so refitted
    unfaced it keeps the ring out of its groove. The step gauges that gap,
    sleeve rear face from the arm's front face, with the front bushing and
    ring on, faces the blank to it less the float, and only then puts it on
    the pin."""
    gap_nominal = (
        cluster_fit.REAR_CHAIN_NOMINAL
        - cluster_fit.FIT_WINDOW_CENTRE
        - cluster_fit.HUB_NOSE_WINDOW_CENTRE
    )
    assert rear_bushing.BLANK_LENGTH_MIN > gap_nominal
    lo, hi = cluster_fit.SLEEVE_REAR_FORWARD_FROM_ARM
    assert lo <= gap_nominal <= hi
    # The gap less the sleeve's float band is the length band the bushing's
    # sheet sets.
    sleeve = cluster_fit.SLEEVE_FLOAT_WINDOW
    assert lo - sleeve[1] == pytest.approx(rear_bushing.GAP_MIN)
    assert hi - sleeve[0] == pytest.approx(rear_bushing.GAP_MAX)
    rear = _step_body("rear-bushing-faced-to-fit")
    gauged = rear.index("DEPTH-GAUGE THE SLEEVE REAR FACE FROM THE ARM")
    faced = rear.index(f"BLANK TO THAT LESS {cluster_fit.SLEEVE_FLOAT_WINDOW_TEXT}")
    fitted = rear.index("BLANK ON")
    assert gauged < faced < fitted
    # The hung cluster carries no rear bushing until then.
    assert "NO REAR BUSHING YET" in _step_body("disc-cluster-hung")
    assert steps.step_number("disc-cluster-hung") < steps.step_number(
        "rear-bushing-faced-to-fit"
    )


def test_the_hub_is_faced_to_the_nose_before_the_disc_is_tapped() -> None:
    """R9-68: the hub's front face is faced to stand just behind the sleeve
    nose on the bench, disc seated and hub on the flat, before the flange
    holes are transferred; the front bushing then bears on the nose."""
    order = ["disc-cluster-assembled", "hub-faced-to-nose", "disc-taps-transferred"]
    numbers = [steps.step_number(key) for key in order]
    assert numbers == list(range(numbers[0], numbers[0] + 3))
    faced = _step_body("hub-faced-to-nose")
    assert f"TILL {cluster_fit.HUB_NOSE_WINDOW_TEXT} BEHIND" in faced
    assert "ON THE NOSE TRAPS HUB AND DISC" in _step_body("disc-cluster-hung")


def test_the_plate_screws_are_cut_to_the_limit_the_lock_sweep_clears() -> None:
    """R9-44: the 5/8 stock screws are cut once the plate is tightened and
    before the arm is hung, to the proud limit the guide-lock sweep is held
    clear of; the screw sheet's installation note states the same limit."""
    import transgear_hanger_joints as joints

    order = ["arm-plate-fitted", "arm-plate-screws-cut", "hanger-pivoted"]
    numbers = [steps.step_number(key) for key in order]
    assert numbers == list(range(numbers[0], numbers[0] + 3))
    body = _step_body("arm-plate-screws-cut")
    limit = f"FLUSH TO {joints.PLATE_SCREW_CUT_PROUD_MAX:.2f} PROUD"
    assert limit in body
    assert "BREAK THE CUT EDGE 0.1 MAX" in body
    assert joints.PLATE_SCREW_TIP_PROUD_MAX == joints.PLATE_SCREW_CUT_PROUD_MAX
    row = _config.parts("vn-transgear-arm-plate-screw")
    assert limit in " ".join(row["installation_notes"].split())
    # Positive control: the fit step itself does not mention the cut.
    assert "CUT" not in _step_body("arm-plate-fitted")


def _spare_world_point(monkeypatch, local):
    """Exercise the production row-vector transform without a COM connection."""
    transform = [value for row in assembly.ROT_X_NEG90 for value in row]
    transform += [value / 1000.0 for value in assembly.SPARE_GEAR_POS]
    transform += [1.0, 0.0, 0.0, 0.0]
    adapter = object()

    def component_transform(actual_adapter, name):
        assert actual_adapter is adapter
        assert name == "pd-transgear-removable-3"
        return transform

    monkeypatch.setattr(_assembly, "component_transform", component_transform)
    return _assembly.world_point(adapter, "pd-transgear-removable-3", local)


def test_spare_sprocket_transformed_underside_contacts_base_deck(monkeypatch):
    # The spec's plate is local Z=0..PLATE, identical in all tooth configs.
    underside = _spare_world_point(monkeypatch, [0.0, 0.0, 0.0])
    top = _spare_world_point(monkeypatch, [0.0, 0.0, sprocket.PLATE])
    assert underside[1] == pytest.approx(base.STACK_HEIGHT, rel=0, abs=1e-9)
    assert top[1] == pytest.approx(base.STACK_HEIGHT + sprocket.PLATE, rel=0, abs=1e-9)
    assert (underside[0], underside[2]) == (160.0, -75.0)
    assert (top[0], top[2]) == (160.0, -75.0)


def test_spare_t18_footprint_is_on_flat_deck_not_raised_rim(monkeypatch):
    radius = sprocket.outside_dia(sprocket.TEETH["T18"]) / 2.0
    for x, y, z in product((-radius, radius), (-radius, radius), (0.0, sprocket.PLATE)):
        world = _spare_world_point(monkeypatch, [x, y, z])
        assert abs(world[0]) < base.TOP_LENGTH / 2.0 - base.LIP_W
        assert abs(world[2]) < base.TOP_WIDTH / 2.0 - base.LIP_W


def test_spare_storage_clears_nameplate_envelope_by_five_mm(monkeypatch):
    # Native top gate rejected the first deck-seating candidate: retaining
    # X=160/Z=-15 intersected the brass nameplate by 605.55 mm^3.
    radius = sprocket.outside_dia(sprocket.TEETH["T18"]) / 2.0
    plate_corners = [
        nameplate.mount_point(point)
        for point in product(
            (0.0, nameplate.PLATE_WIDTH),
            (0.0, nameplate.PLATE_HEIGHT),
            (-nameplate.PLATE_THICKNESS, 0.0),
        )
    ]
    spare_max_z = max(
        _spare_world_point(monkeypatch, [x, y, z])[2]
        for x, y, z in product(
            (-radius, radius), (-radius, radius), (0.0, sprocket.PLATE)
        )
    )
    assert spare_max_z <= min(point[2] for point in plate_corners) - 5.0


def test_spare_remains_fixed_t18_sibling_with_original_rotation():
    tree = ast.parse(Path(assembly.__file__).read_text(encoding="utf-8"))
    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "place_component"
        and any(
            keyword.arg == "label"
            and isinstance(keyword.value, ast.Constant)
            and keyword.value.value == "transgear-removable (spare T18)"
            for keyword in node.keywords
        )
    ]
    assert len(calls) == 1
    call = calls[0]
    assert [ast.unparse(arg) for arg in call.args] == [
        "adapter",
        "'transgear-removable'",
        "list(SPARE_GEAR_POS)",
        "[-90.0, 0.0, 0.0]",
        "ROT_X_NEG90",
    ]
    assert {
        keyword.arg: ast.literal_eval(keyword.value) for keyword in call.keywords
    } == {
        "configuration": "T18",
        "label": "transgear-removable (spare T18)",
    }
    assert (
        inspect.signature(_assembly.place_component).parameters["ground"].default
        is True
    )
    assert assembly.ROT_X_NEG90 == [[1.0, 0.0, 0.0], [0.0, 0.0, -1.0], [0.0, 1.0, 0.0]]


def _numbered_items() -> dict[str, str]:
    """Item numbers against the dict order, so plans must sort by them."""
    return {
        stem: str(len(drawing.BOM_PART_NUMBERS) - index)
        for index, stem in enumerate(drawing.BOM_PART_NUMBERS)
    }


def test_every_bom_item_is_ballooned_on_some_sheet() -> None:
    """Codex B1 (19e33c6c2): items 1-12 and the chain had no balloon."""
    items = _numbered_items()
    iso, inner = drawing.transgear_balloon_items(items)
    plans = (
        drawing.assembled_balloon_items(items),
        drawing.platen_balloon_items(items),
        iso,
        inner,
    )
    ballooned = [stem for plan in plans for stem, _item in plan]
    assert set(ballooned) == set(drawing.BOM_PART_NUMBERS)
    for plan in plans:
        assert [int(item) for _stem, item in plan] == sorted(
            int(item) for _stem, item in plan
        )
    # Only the removable is ballooned twice: on the knob's T24 (sheet 2) and
    # on the spare T18 on the deck (sheet 1), which the caption names.
    repeated = {stem for stem in ballooned if ballooned.count(stem) > 1}
    assert repeated == {"pd-transgear-removable"}
    spare = drawing.ASSEMBLED_BALLOON_ANCHORS["pd-transgear-removable"].instance
    assert spare == "pd-transgear-removable-3"
    for caption in drawing.ASSEMBLED_CAPTIONS.values():
        assert "T18 SPARE, STORED LOOSE" in " ".join(caption.split())


def test_the_exploded_sheet_balloons_exactly_the_platen_group() -> None:
    platen_group = {
        "pd-support-bar",
        "sh-column-clamp-front",
        "sh-column-clamp-back",
        "vn-clamp-screw",
        "pd-platen",
        "pd-platen-rack",
        "pd-platen-guide",
        "pd-guide-lock",
        "pd-platen-clip",
        "pd-platen-paper",
        "vn-fillister-screw",
        "vn-guide-lock-screw",
    }
    assert set(drawing.PLATEN_BALLOON_ANCHORS) == platen_group
    assert explode.SHOWN_STEMS == platen_group
    assert drawing.SHEET_NAMES[2] == "PLATEN AND SUPPORT"


def _platen_instances(**overrides) -> list[explode.Instance]:
    instances = [
        explode.Instance(f"{stem}-1", stem)
        for stem in explode.SHOWN_STEMS - explode.ROLE_STEMS
    ]
    instances += [
        explode.Instance(f"vn-fillister-screw-{n}", "vn-fillister-screw", role)
        for n, role in (
            (1, explode.GUIDE_SCREW_ROLE),
            (2, explode.CLIP_SCREW_ROLE),
        )
    ]
    instances.append(explode.Instance("pd-rack-pinion-1", "pd-rack-pinion"))
    for name, instance in overrides.items():
        instances = [i for i in instances if i.name != name] + [instance]
    return instances


def test_the_explode_moves_only_the_platen_group_and_keeps_the_platen() -> None:
    plan = explode.plan_explode(_platen_instances())
    moved = {name for _step, names in plan for name in names}
    assert "pd-rack-pinion-1" not in moved
    assert "pd-platen-1" not in moved
    assert {name.rsplit("-", 1)[0] for name in moved} == (
        explode.SHOWN_STEMS - explode.STATIONARY_STEMS
    )
    # The guide screws leave with the guides' step, the clip screws with the
    # clips': a role mix-up would move a screw with the wrong part.
    by_label = {step.label: names for step, names in plan}
    assert any("vn-fillister-screw-1" in names for names in by_label.values())
    assert any("vn-fillister-screw-2" in names for names in by_label.values())
    for names in by_label.values():
        assert not {"vn-fillister-screw-1", "vn-fillister-screw-2"} <= set(names)


def test_the_explode_refuses_an_untagged_fillister_screw() -> None:
    untagged = explode.Instance("vn-fillister-screw-1", "vn-fillister-screw")
    with pytest.raises(ValueError, match="role tags"):
        explode.plan_explode(_platen_instances(**{"vn-fillister-screw-1": untagged}))


def test_the_platen_group_is_built_and_hung_before_its_locks_are_set() -> None:
    """Codex B2: the steps started with the locks already on."""
    order = ["bar-clamped", "rack-soldered", "guides-screwed", "clips-fitted"]
    order += ["platen-hung", "guide-locks-set", "lock-seats-faced"]
    assert list(steps.SEQUENCE[: len(order)]) == order
    assert f"{steps.BAR_TOP_ABOVE_DECK:.1f} ABOVE THE BASE DECK" in _step_body(
        "bar-clamped"
    )
    # The latched hook cannot take up a rack set off its band (rack-crest
    # ruling): the step prints the crest band itself.
    assert f"CRESTS {steps.RACK_CREST_TEXT} BELOW ITS BOTTOM EDGE" in _step_body(
        "rack-soldered"
    )
    assert steps.BAR_TOP_ABOVE_DECK == pytest.approx(
        assembly.BAR_TOP_Y - assembly.BASE_DECK_Y, abs=5e-4
    )
    assert steps.RACK_CREST_DROP == pytest.approx(
        assembly.PLATE_Y0 - assembly.RACK_TIP_Y, abs=1e-9
    )
    # Codex P2 (724f78f26): the step solders the rack flush; the model places
    # it so (the platen pose, not the rack, takes the mesh phasing).
    assert "ENDS FLUSH WITH THE PLATEN'S" in _step_body("rack-soldered")
    assert assembly.RACK_X0 == assembly.PLATE_X0
    # Every platen-group screw count the steps print is the model's.
    assert f"{drawing.GUIDE_SCREWS} " in _step_body("guides-screwed")
    assert drawing.GUIDE_SCREWS + drawing.CLIP_SCREWS == len(
        assembly.GUIDE_SCREW_XY
    ) + len(assembly.CLIP_SCREW_XY)


def test_the_chain_is_closed_and_run_after_the_collar_is_accepted() -> None:
    """Codex B3: routing, closure, adjustment and a functional run."""
    assert steps.SEQUENCE[-3:] == (
        "fitup-accepted",
        "chain-closed",
        "chain-run-accepted",
    )
    closed = _step_body("chain-closed")
    assert f"LOOP {chain.LINK_COUNT} PITCHES" in closed
    assert "CONNECTING LINK" in closed and "CLOSED END LEADING" in closed
    assert "NO TENSIONING" in closed
    run = _step_body("chain-run-accepted")
    assert "EVERY TOOTH" in run and "TOUCHES NOTHING" in run
    assert "LOOPED" not in _step_body("collar-pinned")


def test_the_setting_and_the_acceptance_offsets_are_told_apart() -> None:
    """Codex clarity: 0.05 ±0.05 sets, 0.05 ±0.10 accepts; a T24 behind
    the T12 within the acceptance passes."""
    setting = _step_body("collar-gap-measured")
    accepted = _step_body("fitup-accepted")
    assert f"STEP {steps.step_number('fitup-accepted')} RE-CHECKS" in setting
    assert f"STEP {steps.step_number('collar-gap-measured')}'S SETTING" in accepted
    behind = steps.OFFSET_ACCEPT_TOL - collar.FIT_UP_OFFSET_TARGET
    assert behind > 0.0
    assert f"UP TO {behind:.2f} BEHIND PASSES" in accepted


def test_the_t24_is_read_held_back_on_its_seat() -> None:
    """Codex P2 on b2eb9a0e1: the T24 floats 0.05-0.15 forward of its seat
    under the nut, so d and the acceptance read it held back on the seat, the
    pose the chain-plane budget starts from; the float is then forward only.
    Accepted at 0.05 ±0.10 seated, the pair runs -0.85..+0.10 in service."""
    pose = _step_body("fitup-pose-set")
    assert steps.T24_HELD_BACK_TEXT in pose
    assert _step_body("collar-gap-measured").startswith(
        f"{steps.T24_HELD_BACK_TEXT}, MEASURE d"
    )
    accepted = _step_body("fitup-accepted")
    assert accepted.startswith(f"ACCEPT, IN STEP {steps.step_number('fitup-pose-set')}")
    low, high = steps.ACCEPTED_CHAIN_OFFSET_IN_SERVICE
    assert (low, high) == pytest.approx((-0.85, 0.10), abs=1e-9)
    # The float is in the budget, forward: the contract's set range and the
    # acceptance both lose it at their forward ends.
    assert collar.CHAIN_OFFSET_IN_SERVICE[0] == pytest.approx(
        collar.CHAIN_SET_RANGE[0]
        - collar.CRANK_END_PLAY_MAX
        - collar.KNOB_END_FLOAT_MAX
        - max(collar.T24_FLOAT_RANGE)
    )
    assert max(abs(low), abs(high)) <= collar.CHAIN_OFFSET_LIMIT


def test_a_balloon_ring_is_centred_in_its_room_or_refused() -> None:
    limits = (0.2, 0.1, 0.4, 0.3)
    outline = (0.0, 0.0, 0.1, 0.1)
    dx, dy = drawing.ring_fit_shift(outline, limits, name="t")
    ring = drawing._grown(
        (outline[0] + dx, outline[1] + dy, outline[2] + dx, outline[3] + dy),
        drawing.BALLOON_RING_REACH,
    )
    assert ring[0] - limits[0] == pytest.approx(limits[2] - ring[2])
    assert ring[1] - limits[1] == pytest.approx(limits[3] - ring[3])
    with pytest.raises(ValueError, match="width"):
        drawing.ring_fit_shift((0.0, 0.0, 0.19, 0.1), limits, name="t")


# Farm run 20261001T142942518Z (8689c2a0d) read sheet 1's isometric at 1:3:
# its outline 187.7 mm tall; its width passed, so at most 149 mm.
ISO_OUTLINE_AT_1_3 = (0.250, 0.075, 0.250 + 0.149, 0.075 + 0.1877)


class _PaddedView:
    """A view whose read-back outline is its content, which scales, plus a
    fixed sheet-space padding, which does not (SolidWorks' outline)."""

    def __init__(self, size_m, at_scale, padding_m):
        self.content = tuple(
            (side - padding_m) / (at_scale[0] / at_scale[1]) for side in size_m
        )
        self.padding = padding_m
        self.applied = []

    def outline_at(self, scale):
        self.applied.append(scale)
        ratio = scale[0] / scale[1]
        width, height = (side * ratio + self.padding for side in self.content)
        return (0.2, 0.1, 0.2 + width, 0.1 + height)


def test_the_sheet_one_isometric_ring_fits_at_the_sheet_scale() -> None:
    """The 1:3 isometric's ring overflowed natively (221.7 > 198.0 mm); at the
    sheet's scale the same view's ring fits, whatever its fixed padding."""
    with pytest.raises(ValueError, match=r"height 221\.7 mm > room 198\.0 mm"):
        drawing.ring_fit_shift(
            ISO_OUTLINE_AT_1_3, drawing.ISO_RING_LIMITS, name="sheet 1 isometric"
        )
    size = (
        ISO_OUTLINE_AT_1_3[2] - ISO_OUTLINE_AT_1_3[0],
        ISO_OUTLINE_AT_1_3[3] - ISO_OUTLINE_AT_1_3[1],
    )
    assert drawing.ISO_SCALE_LADDER[0] == drawing.ASSEMBLED_SCALE
    for padding in (0.0, 0.0127, 0.0254):
        view = _PaddedView(size, (1.0, 3.0), padding)
        scale, _outline = drawing.step_down_to_fit(
            view.outline_at, drawing.ISO_SCALE_LADDER, drawing.ISO_RING_LIMITS, name="t"
        )
        assert scale == drawing.ASSEMBLED_SCALE, padding
    # Every scale the isometric may take has its caption.
    assert set(drawing.ASSEMBLED_CAPTIONS) == set(drawing.ISO_SCALE_LADDER)


def test_the_exploded_view_steps_down_on_its_native_outline() -> None:
    """Codex P2 (aa9d3b681): a 211.9 mm wide outline at 1:3 with 12.7 mm of
    fixed padding, scaled whole, predicts a 192.9 mm ring at 1:4 in the 193.0
    room; natively it is 196.1, so the view must go on to 1:5 (166.2)."""
    ladder = drawing.EXPLODED_SCALE_LADDER
    limits = drawing.EXPLODED_RING_LIMITS
    assert limits[2] - limits[0] == pytest.approx(0.193)
    view = _PaddedView((0.2119, 0.100), (1.0, 3.0), 0.0127)
    scale, outline = drawing.step_down_to_fit(view.outline_at, ladder, limits, name="t")
    assert scale == (1.0, 5.0)
    assert view.applied == list(ladder)
    assert outline == view.outline_at(scale)
    # A view that fits as placed is not rescaled.
    view = _PaddedView((0.120, 0.120), (1.0, 3.0), 0.0127)
    assert (
        drawing.step_down_to_fit(view.outline_at, ladder, limits, name="t")[0]
        == (ladder[0])
    )
    assert view.applied == [ladder[0]]
    # Only when 1:5 still overflows does it refuse, naming every scale.
    view = _PaddedView((0.5, 0.5), (1.0, 3.0), 0.0127)
    with pytest.raises(ValueError, match=r"no t scale fits: .*1:3.*1:4.*1:5"):
        drawing.step_down_to_fit(view.outline_at, ladder, limits, name="t")
    assert set(drawing.EXPLODED_CAPTIONS) == set(ladder)


def test_the_hook_is_set_on_a_meshed_and_run_hanger() -> None:
    """Codex (8b5e1f354) / R9-62: the hook was match-drilled with the hanger
    "latched" but the pinion-in-rack mesh never set nor the platen run."""
    meshed, hooked = (
        steps.step_number(key) for key in ("hanger-meshed", "hook-set-and-riveted")
    )
    assert hooked == meshed + 1
    text = drawing._step_text()
    mesh = " ".join(text["hanger-meshed"].split())
    assert f"SET {steps.MESH_BACKLASH_TEXT} PLATEN SHAKE ALONG THE RACK" in mesh
    assert "FULL TRAVEL: NO TIGHT SPOT, SHAKE AT EVERY TOOTH" in mesh
    hook = " ".join(text["hook-set-and-riveted"].split())
    assert hook.startswith("HOLDING THAT MESH")
    # Codex P1 on b2eb9a0e1: set clear of the pin, the unclamped arm fell
    # through the hole's clearance and opened the feed mesh.
    pin = drawing._N["vn-transgear-latch-pin"]
    assert f"ITS HOLE'S LOWER EDGE ON THE {pin} PIN" in hook
    assert "CLEAR" not in hook
    # Machinist review of 0316d0951: "its drawn place" had no dimension a
    # fitter could measure. The step locates the hook's rivet holes from the
    # MHA-PD-021 datums: the flap's lower edge and the bar's back face, on which
    # the bracket's base sits.
    assert "DRAWN PLACE" not in hook
    flap_edge_y = assembly.HOOK_BRACKET.MACHINE_ORIGIN[1]
    (_, front_y, front_z), _upper = sorted(
        assembly.HOOK_RIVET_POS, key=lambda pos: pos[2]
    )
    above = f"{front_y - flap_edge_y:.2f}"
    rear = f"{front_z - assembly.BAR_BACK_Z:.2f}"
    assert (above, rear) == ("3.80", "11.30")
    assert (
        f"ITS RIVET HOLES {above} ABOVE THE FLAP'S LOWER EDGE, THE FRONT ONE "
        f"{rear} REAR OF THE BAR, {steps.HOOK_SET_TEXT}, ELSE REPORT; CLAMP."
    ) in hook
    assert steps.HOOK_SET_TEXT == "\u00b10.51"
    assert hook.endswith("UNCLAMP, LATCH, RE-RUN THE TRAVEL.")


def test_the_feed_mesh_sits_mid_reach_with_a_working_contact_ratio() -> None:
    """R9-62: at the 2.00 crest drop the nominal mesh ran at e 0.80, contact
    ratio 0.86; the rack set 2.25 down puts it at 0.55, and the backlash band
    the fit-up accepts stays inside what the hook's set range can hold."""
    assert assembly.RACK_MESH_EXT == pytest.approx(0.55)
    assembly._assert_rack_mesh()
    # The hook's set range moves the pin by the pivot-to-pin over the
    # pivot-to-latch lever.
    lever = (assembly.STUD_X - assembly.BAR.PIVOT_TAP_X) / (
        sum(assembly.HOOK.PLANE_X) / 2.0 - assembly.BAR.PIVOT_TAP_X
    )
    reach = assembly.HOOK_BRACKET_SPEC.HOOK_SET_RANGE * lever
    low, high = (steps.mesh_extension(b) for b in steps.MESH_BACKLASH_RANGE)
    assert low < assembly.RACK_MESH_EXT < high
    assert assembly.RACK_MESH_EXT - reach <= low and high <= (
        assembly.RACK_MESH_EXT + reach
    )
    # A 0.80 extension (the 2.00 drop) runs under one tooth in contact.
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(assembly, "RACK_MESH_EXT", 0.80)
        patch.setattr(assembly, "RACK_PITCH_Y", assembly.RACK_PITCH_Y + 0.25)
        with pytest.raises(RuntimeError, match="contact ratio 0.86 < 1.2"):
            assembly._assert_rack_mesh()


def test_the_mesh_band_ends_both_mesh_on_the_form_cut_pinion() -> None:
    """Codex P2 (234a39c87) / R9-62a: the (0.20, 0.35) shake band put the rack
    into the 12T's radial flank at its tight end (e 0.39) and under the 1.1
    contact-ratio rule at its loose end (e 0.68, smallest printed tip)."""
    with pytest.raises(ValueError, match="leaves the working window"):
        steps.check_mesh_band((0.20, 0.35))
    low, high = steps.MESH_BACKLASH_RANGE
    with pytest.raises(ValueError, match="leaves the working window"):
        steps.check_mesh_band((0.20, high))
    with pytest.raises(ValueError, match="leaves the working window"):
        steps.check_mesh_band((low, 0.35))
    steps.check_mesh_band(steps.MESH_BACKLASH_RANGE)
    # The window's ends are where the two criteria change sign.
    e_min, e_max = steps.MESH_EXTENSION_MIN, steps.MESH_EXTENSION_MAX
    assert steps.feed_mesh_penetration(e_min) <= 1e-5
    assert steps.feed_mesh_penetration(e_min - 0.03) > 1e-4
    assert steps.feed_mesh_contact_ratio(e_max, steps.TIP_DIA_MIN) == pytest.approx(
        steps.MESH_CONTACT_RATIO_FLOOR
    )
    # The old tight end's reach into the flank, the old loose end's ratio.
    assert steps.feed_mesh_penetration(steps.mesh_extension(0.20)) > 0.003
    assert (
        steps.feed_mesh_contact_ratio(steps.mesh_extension(0.35), steps.TIP_DIA_MIN)
        < 1.1
    )
