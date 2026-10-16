"""Offline contract for the channel assembly drawing (MHA-CH-000)."""

from __future__ import annotations

import re

from _assembly_contract import assembly_contract
import _config
import ch_channel_assembly_steps as steps
import draw_ch_channel_assembly as drawing
import dt_drive_train_steps
import pytest
import rocker_bank_layout as bank
from _drawing_registry import DRAWINGS_BY_NAME

STEP_HEAD = re.compile(r"^(\d+)\. ", re.MULTILINE)
# A drive-train or frame sequence head, sub-steps included ("9F. ").
ANY_STEP_HEAD = re.compile(r"^(\d+[A-Z]?)\. ", re.MULTILINE)
STEP_POINTER = re.compile(r"(MHA-[A-Z]{2}-000) STEP (\d+[A-Z]?)")
# Default-format note text, measured on r743-rocker-fix3's render (leaf
# 20260926T112244Z-1-a884759d); #945 moves these into _drawing_common.
NOTE_CHAR_WIDTH = 0.00276
NOTE_LINE_PITCH = 0.0045


def _step_body(key: str) -> str:
    """The printed text of one step, from its head to the next head."""
    text = drawing.FITUP_STEPS
    heads = list(STEP_HEAD.finditer(text))
    index = steps.step_number(key) - 1
    end = heads[index + 1].start() if index + 1 < len(heads) else len(text)
    return " ".join(text[heads[index].end() : end].split())


def _sequence_steps(text: str) -> dict[str, str]:
    """Every step of a printed sequence: its head label to its joined text."""
    heads = list(ANY_STEP_HEAD.finditer(text))
    bodies = {}
    for index, head in enumerate(heads):
        end = heads[index + 1].start() if index + 1 < len(heads) else len(text)
        assert head.group(1) not in bodies, f"step {head.group(1)} printed twice"
        bodies[head.group(1)] = " ".join(text[head.end() : end].split())
    return bodies




def test_channel_assembly_keeps_registry_outputs_and_precomputed_placement() -> None:
    spec = DRAWINGS_BY_NAME["ch_channel_assembly"]
    assert spec.source_kind == "assembly"
    assert spec.part == "ch_channel"
    assert drawing.SOURCE == spec.source
    assert drawing.OUTPUTS == drawing.OUTPUTS.__class__(
        spec.outputs["slddrw"], spec.outputs["pdf"], spec.outputs["png"]
    )
    assert drawing.SHEET_SCALE == (1.0, 7.0)
    assert drawing.FRONT_CENTER == (0.060, 0.150)
    assert drawing.RIGHT_CENTER == (0.130, 0.150)
    assert drawing.ISO_CENTER == (0.225, 0.150)


def test_step_numbers_follow_the_sequence_and_unknown_steps_are_refused() -> None:
    for index, key in enumerate(steps.SEQUENCE, start=1):
        assert steps.step_number(key) == index
    with pytest.raises(KeyError):
        steps.step_number("no-such-step")


def test_every_cross_sheet_step_pointer_lands_on_the_step_it_names() -> None:
    """Codex #936 (PRRT_kwDOPHDy386mRlAE): step 2 sent the fitter to an A03
    step that did not exist. The user ruled option A: an A03 step sets the
    north bracket by DRO, after MHA-FR-000 step 8 has screwed the support down.
    Each pointer must land on a printed step that does what it cites, and the
    A02 pointer is the A03 registry's, never a typed number."""
    import draw_dt_drive_train_assembly as drive_train
    import draw_fr_frame_assembly as frame

    bracket = _config.parts("ch-pivot-bracket")["number"]
    support = _config.parts("fr-rocker-arm-support")["number"]
    channel_number = assembly_contract("ch-channel").number
    fitup_number = assembly_contract("dt-drive-train").number
    frame_number = assembly_contract("fr-frame").number
    north_ref = (
        f"{fitup_number} STEP "
        f"{dt_drive_train_steps.step_number(steps.NORTH_BRACKET_SET_KEY)}"
    )
    stack_ref = (
        f"{fitup_number} STEP "
        f"{dt_drive_train_steps.step_number(steps.CYLINDER_STACK_KEY)}"
    )
    sheets = {
        channel_number: _sequence_steps(drawing.FITUP_STEPS),
        fitup_number: _sequence_steps(
            "\n".join(
                (
                    drive_train.CONE_CRANK_STEPS,
                    drive_train.BANK_STEPS,
                    drive_train.rig_steps(pivot_blocks=2, cams=2, slotted=4),
                )
            )
        ),
        frame_number: _sequence_steps(frame.ASSEMBLY_STEPS),
    }
    # What each pointer's target must name, keyed by (citing sheet, pointer).
    expected = {
        (channel_number, north_ref): f"THE NORTH {bracket}",
        # The rod rings go onto their cams in the cylinder stack, so the
        # bench-pinned rod + arm pairs must exist by then.
        (channel_number, stack_ref): "ON ITS CAM AS ITS GEAR GOES ON",
        # ... and that drive-train step names the pinning step it relies on.
        (fitup_number, steps.RODS_PINNED_REF): "ROD FORK TO ITS",
        (fitup_number, f"{frame_number} STEP 8"): f"{support} ON DECK",
        # The drive-train step that sets the north bracket keeps the miced
        # north washer for the channel sheet's threading of the shaft.
        (fitup_number, steps.step_ref("north-ear-datum")): "PUSH THE",
    }
    found = set()
    # MHA-HA-000's sequence is not on this branch's base: its one pointer is
    # checked by value against steps.HA_ANCHORS_SET_REF instead.
    foreign = set()
    for sheet, bodies in sheets.items():
        for body in bodies.values():
            for pointer in STEP_POINTER.finditer(body):
                if pointer.group(1) not in sheets:
                    foreign.add((sheet, pointer.group(0)))
                    continue
                found.add((sheet, pointer.group(0)))
                target = sheets[pointer.group(1)][pointer.group(2)]
                assert expected[(sheet, pointer.group(0))] in target, pointer.group(0)
    assert found == set(expected)
    assert foreign == {(channel_number, steps.HA_ANCHORS_SET_REF)}
    north_label = str(dt_drive_train_steps.step_number(steps.NORTH_BRACKET_SET_KEY))
    north = sheets[fitup_number][north_label]
    assert "EAR INNER FACE TO Y" in north and "DRO STILL ZEROED AS 9A" in north
    # The plain shaft threads through the set ear: the bracket stays down,
    # and the channel sheet threads the shaft and the miced washer from the
    # north.
    assert "LIFT IT OFF" not in north
    assert "MIC ONE MHA-VN-070, W" in north
    north_ear = _step_body("north-ear-datum")
    washer = _config.parts("vn-rocker-thrust-washer")["number"]
    assert "FLATS UP" in north_ear and "SOUTH THROUGH THE EAR" in north_ear
    assert f"THE {washer} MICED AND KEPT AT THAT STEP" in north_ear
    # Positive control: the step before it is the bank's end play, not the ear.
    assert f"NORTH {bracket}" not in sheets[fitup_number]["9F"]
    # It follows 9F, the bank's last sub-step, on the bank sheet: the rig's
    # first step comes after it.
    labels = list(sheets[fitup_number])
    assert labels.index(north_label) == labels.index("9F") + 1
    # The rig's first step is whichever key the registry puts right after the
    # north bracket, so reordering the rig's own steps cannot break this.
    sequence = dt_drive_train_steps.SEQUENCE
    assert steps.NORTH_BRACKET_SET_KEY in sequence[:-1], (
        f"{steps.NORTH_BRACKET_SET_KEY!r} must be in "
        "drive_train_steps.SEQUENCE with a rig step after it"
    )
    rig_first_key = sequence[sequence.index(steps.NORTH_BRACKET_SET_KEY) + 1]
    rig_first = str(dt_drive_train_steps.step_number(rig_first_key))
    assert labels.index(rig_first) == labels.index(north_label) + 1


def test_the_printed_step_heads_are_the_registry_in_order() -> None:
    printed = [int(n) for n in STEP_HEAD.findall(drawing.FITUP_STEPS)]
    assert printed == list(range(1, len(steps.SEQUENCE) + 1))
    assert len(steps.SEQUENCE) == 14
    assert steps.SEQUENCE[6:] == (
        "set-screws-driven",
        "preload-accepted",
        steps.KEEPERS_PAIR_REAMED_KEY,
        steps.KEEPERS_SET_KEY,
        steps.BARS_PINNED_KEY,
        steps.LEVER_BANK_THREADED_KEY,
        steps.SET_SCREWS_STAKED_KEY,
        steps.SPRINGS_HOOKED_KEY,
    )


def test_the_spring_set_and_its_preload_check_are_printed_from_the_layout() -> None:
    """#948 ruling R (PR #1292): the south bracket is set off the MHA-VN-070
    washer by the spring's set blade, beside the MHA-VN-053 spring, which is
    first run along the shaft (its catalogue ID can bind). drawing-guidelines.md rule 7 (notes: few, flagged, never a method): the blade
    comes from rocker_bank_layout, never typed; the acceptance is the preload."""
    spring = _config.parts("vn-rocker-bank-spring")["number"]
    shaft = _config.parts("ch-pivot-shaft")["number"]
    setting = _step_body("south-bracket-spring-set")
    assert f"RUN A {spring} SPRING ALONG THE {shaft}; REJECT ONE THAT BINDS." in setting
    assert "SPRING-SET BLADE (DETAIL A) BESIDE THE SPRING" in setting
    assert "PULL THE BLADE" in setting
    # r10 machinist review: worded as step 10's keeper transfer.
    support = _config.parts("fr-rocker-arm-support")["number"]
    hold_down = _config.parts("vn-pedestal-hold-down-screw")["number"]
    assert (
        f"TRANSFER ITS FOOT HOLE INTO THE {support} RAIL, TAP AS {support}, "
        f"SCREW DOWN ONE {hold_down}, PULL THE BLADE."
    ) in setting
    accept = _step_body("preload-accepted")
    assert "PUSHED SOUTH," in accept
    assert "THE BANK SPRINGS BACK ONTO THE NORTH WASHER" in accept
    assert f"STEP {steps.step_number('south-bracket-spring-set')}" in accept
    stack = _step_body("rocker-stack-accepted")
    assert "TO THE ROCKER BANK VIEW'S STACK DIMENSION" in stack
    # The numbers live in the model dimensions, never in the step text.
    assert f"{bank.ROCKER_SPRING_SET:.2f}" not in setting
    assert f"{bank.STACK_L20_ACCEPT[0]:.2f}" not in stack
    assert steps.NORTH_BRACKET_SET_REF in _step_body("north-ear-datum")
    # No feeler end play survives the ruling.
    assert "FEELER" not in drawing.FITUP_STEPS
    assert "END PLAY" not in drawing.FITUP_STEPS
    # Positive control: the spring is not what step 4 fits.
    assert spring not in _step_body("south-washer-fitted")




def test_each_step_block_fits_the_field_right_of_its_bank_view() -> None:
    rocker, lever = drawing.FITUP_NOTES
    assert drawing.FITUP_STEPS == f"{rocker}\n{lever}"
    template = drawing._TEMPLATE
    left, top = drawing.STEPS_XY
    for note in (rocker, lever):
        lines = note.splitlines()
        assert left + max(map(len, lines)) * NOTE_CHAR_WIDTH < (
            template.width_m - drawing.BORDER
        )
        assert top - len(lines) * NOTE_LINE_PITCH > template.title_block_top_m
        assert top < template.height_m - drawing.BORDER
    # Each 1:1 bank's ends (the keeper and ear outer faces) clear the block.
    for view, south_z in (
        (drawing.ROCKER_BANK, -80.4589 - 2.0),
        (drawing.LEVER_BANK, drawing.asm.LUG_INNER_FACE_Z[0] - 10.0),
    ):
        assert view.sheet_xy(south_z, 0.0)[0] < left - 0.010
    assert rocker.startswith("ROCKER BANK FIT-UP\n1. ")
    assert lever.startswith(
        f"LEVER BANK FIT-UP\n{steps.step_number(steps.KEEPERS_PAIR_REAMED_KEY)}. "
    )
    assert "TIGHTEN" not in rocker
    assert "TIGHTEN" in lever and "STAKE" in lever
    assert _config.parts("vn-arbor-set-screw")["number"] not in lever


def test_the_package_sheets_and_settings_contract() -> None:
    assert drawing.SHEET_NAMES == (
        "ASSEMBLED VIEWS",
        "EXPLODED VIEW + BOM",
        "ROCKER BANK FIT-UP",
        "LEVER BANK FIT-UP",
    )
    assert set(drawing.SHEET_SCALES) == set(drawing.SHEET_NAMES)
    asm = drawing.asm
    kept = {
        **drawing.STACK_KEEP,
        **drawing.SPRING_KEEP,
        **drawing.LUG_KEEP,
    }
    assert sorted(kept) == sorted(asm.DIMENSION_FEATURE)
    # Each bank view shows only its own axis's sketch.
    assert {asm.DIMENSION_FEATURE[name] for name in drawing.LUG_KEEP} == {
        asm.FULCRUM_FEATURE
    }
    assert {
        asm.DIMENSION_FEATURE[name] for name in (*drawing.STACK_KEEP, *drawing.SPRING_KEEP)
    } == {asm.PIVOT_FEATURE}
    assert set(asm.DIMENSION_CALLOUTS) == set(kept)
    assert asm.REFERENCE_DIMENSIONS == {asm.LUG_SPAN_DIMENSION}
    assert set(asm.DIMENSION_TOLERANCES) == set(kept) - asm.REFERENCE_DIMENSIONS
    lower, upper = asm.DIMENSION_TOLERANCES[asm.SPRING_SET_DIMENSION]
    assert (lower, upper) == (-bank.ROCKER_SPRING_SET_BAND, bank.ROCKER_SPRING_SET_BAND)
    # Every kept dimension text lands on its own sheet, inside the border.
    for x, y in kept.values():
        assert drawing.BORDER < x < drawing.STEPS_XY[0]
        assert drawing.BORDER < y < drawing._TEMPLATE.height_m - drawing.BORDER
    # The south-end detail's spring-set text sits above its crop circle,
    # clear of the arc (r7 layout audit: inside it, the arc crossed the text).
    detail = drawing.SOUTH_END
    _, y = drawing.SPRING_KEEP[asm.SPRING_SET_DIMENSION]
    radius = detail.crop_radius_mm * detail.mm
    assert y > detail.centre[1] + radius
    # The parent rocker-bank view carries the detail's boundary, about the
    # same model point the detail is centred on, lettered outside it; the
    # detail's title and step 5 cite the same letter.
    (cx, cy), parent_radius = drawing.detail_boundary(drawing.ROCKER_BANK, detail)
    assert (cx, cy) == drawing.ROCKER_BANK.sheet_xy(
        detail.centre_xyz[2], detail.centre_xyz[1]
    )
    assert parent_radius == detail.crop_radius_mm / 1000.0
    lx, ly = drawing.letter_xy((cx, cy), parent_radius)
    assert (lx - cx) ** 2 + (ly - cy) ** 2 > parent_radius**2
    assert drawing.BORDER < lx < drawing.STEPS_XY[0]
    assert detail.letter == drawing.DETAIL_LETTER
    assert detail.title.startswith(f"DETAIL {drawing.DETAIL_LETTER},")
    assert f"(DETAIL {drawing.DETAIL_LETTER})" in _step_body("south-bracket-spring-set")


def _iso(point: tuple[float, float, float]) -> tuple[float, float]:
    """The *Isometric projection (eye on +x +y +z), model mm on the view."""
    x, y, z = point
    return (x - z) * 0.5**0.5, (2.0 * y - x - z) / 6.0**0.5


def test_the_exploded_details_enlarge_the_north_hardware_beside_the_bom() -> None:
    asm = drawing.asm
    north = "north"
    lug_z = drawing.FULCRUM_KEEPER_CENTRE_Z + drawing.KEEPER_Z_OFF
    # 60 north, then the whole north-end cluster 100 further north and 300 up,
    # clear of the hanging rocker arms (r10 machinist review, DETAIL B).
    assert drawing.exploded_offset(asm.BRACKET, north) == (0.0, 300.0, 160.0)
    assert drawing.exploded_offset(asm.BRACKET_SET_SCREW, north) == (0.0, 325.0, 160.0)
    assert drawing.exploded_offset(asm.WASHER, north) == (0.0, 300.0, 120.0)
    assert drawing.exploded_offset(asm.KEEPER_FOOT_SCREW, north) == (0.0, 25.0, 50.0)
    assert drawing.exploded_offset(asm.BRACKET, "south") == (0.0, 0.0, -60.0)
    bracket, keeper = drawing.NORTH_BRACKET_DETAIL, drawing.NORTH_KEEPER_DETAIL
    assert drawing.EXPLODED_DETAILS == (bracket, keeper)
    # Each cluster member's exploded reference point projects inside its
    # circle with room for the part round it: the washer (Ø10.2), the set
    # screw above the ear apex, the hold-down over its foot hole.
    pivot_x, pivot_y = drawing.ROCKER_PIVOT_XY
    ear_z = bank.PIVOT_BRACKET_Z[1]
    washer_z = sum(bank.NORTH_WASHER_Z) / 2.0
    members = {
        bracket: (
            drawing._exploded((pivot_x, pivot_y, washer_z), asm.WASHER, north),
            drawing._exploded(
                (pivot_x, pivot_y + 15.0, ear_z), asm.BRACKET_SET_SCREW, north
            ),
            drawing._exploded(
                (pivot_x, pivot_y - 15.0, ear_z + 8.0), asm.BRACKET_HOLD_DOWN, north
            ),
        ),
        keeper: (
            drawing._exploded(
                (keeper.centre_xyz[0], drawing.LEVER_FULCRUM_XY[1] + 10.0, lug_z),
                asm.KEEPER_SET_SCREW,
                north,
            ),
            drawing._exploded(
                (keeper.centre_xyz[0], drawing.LEVER_FULCRUM_XY[1] - 20.0, lug_z + 8.5),
                asm.KEEPER_FOOT_SCREW,
                north,
            ),
        ),
    }
    for detail, points in members.items():
        assert detail.orientation == "*Isometric" and detail.exploded
        assert detail.title == f"DETAIL {detail.letter}"
        cu, cv = _iso(detail.centre_xyz)
        for point in points:
            u, v = _iso(point)
            assert ((u - cu) ** 2 + (v - cv) ** 2) ** 0.5 < detail.crop_radius_mm - 5.0
    # The column right of the BOM, inside the border and above the title
    # block, the circles apart and each label (under its circle) inside it.
    template = drawing._TEMPLATE
    bom_right = drawing.BOM_ANCHOR[0] + sum(drawing.BOM_COLUMN_WIDTHS.values())
    right = template.width_m - drawing.BORDER
    previous_bottom = template.height_m - drawing.BORDER
    for detail in drawing.EXPLODED_DETAILS:
        (x, y), radius = detail.centre, detail.crop_radius_mm * detail.mm
        assert bom_right + 0.004 < x - radius and x + radius < right
        assert y + radius < previous_bottom
        lines = detail.label_text.splitlines()
        lx, ly = detail.crop_label_xy
        assert lx + max(map(len, lines)) * NOTE_CHAR_WIDTH < right
        previous_bottom = ly - len(lines) * NOTE_LINE_PITCH
    assert previous_bottom > template.title_block_top_m


def test_the_bom_covers_every_family_once_with_its_sku() -> None:
    assert len(drawing.BOM_COMPONENTS) == 19
    assert set(drawing.BOM_PART_NUMBERS) == set(drawing.BOM_COMPONENTS)
    assert len(set(drawing.BOM_PART_NUMBERS.values())) == len(drawing.BOM_COMPONENTS)
    for stem in drawing.BOM_COMPONENTS:
        row = drawing.PART_ROWS[stem]
        skus = row.get("supplier_skus") or ()
        assert drawing.BOM_SKUS[stem] == (
            " / ".join(map(str, skus)) if skus else drawing.MADE_PART_SKU
        )
        assert drawing.BOM_DESCRIPTIONS[stem]
    assert drawing.BOM_QUANTITIES[drawing.SPRING_STEM] == drawing.CHANNELS
    assert sum(drawing.BOM_QUANTITIES.values()) == 2 + 7 * 2 + 1 + 9 * drawing.CHANNELS
    # The anchor's jam nut (MHA-CH-012, made) is its own row, one per anchor.
    nut = drawing.asm.ANCHOR_NUT
    assert drawing.BOM_QUANTITIES[nut] == drawing.BOM_QUANTITIES[drawing.asm.HOOK]
    assert drawing.BOM_SKUS[nut] == drawing.MADE_PART_SKU
    body = _step_body(steps.SPRINGS_HOOKED_KEY)
    assert (
        f"THREADED AND JAMMED BY ITS {drawing.BOM_PART_NUMBERS[nut]} PER "
        f"{steps.HA_ANCHORS_SET_REF}."
    ) in body


def test_the_explode_plan_moves_every_family_and_only_them() -> None:
    asm = drawing.asm
    names = {asm.EXPLODED_VIEW_NAME}
    assert names == {drawing.EXPLODED_VIEW_NAMES[drawing.ASSEMBLY_VIEW_CONFIGURATION]}
    instances = []
    for stem, quantity in drawing.BOM_QUANTITIES.items():
        if quantity == 2:
            instances += [
                asm.Instance(f"{stem}-1", stem, -70.0),
                asm.Instance(f"{stem}-2", stem, 70.0),
            ]
        else:
            instances += [
                asm.Instance(f"{stem}-{j + 1}", stem, -70.0 + 7.0 * j)
                for j in range(quantity)
            ]
    plan = asm.plan_explode(instances)
    moved = {name for step in plan for name in step[1]}
    assert moved == {
        instance.name for instance in instances if instance.stem in asm.EXPLODED_STEMS
    }
    assert {"ch-pivot-shaft", "ch-rocker-arm", "ch-channel-lever"}.isdisjoint(
        asm.EXPLODED_STEMS
    )
    assert asm.FULCRUM_SHAFT in asm.EXPLODED_STEMS


def test_the_fulcrum_keepers_are_pair_reamed_set_by_dro_and_staked() -> None:
    """GPT review F5/F6 and round 3 (PR #1311): the two keeper bores share one
    axis only if they are reamed through in one pass at their installed
    spacing, feet on one flat; the actual shaft gauges that line in the
    clamped setup. The pair is then set on the top frame by DRO with the
    shaft through both, and each crown tap's mouth is staked over its set
    screw (drawing-guidelines.md rule 23 (lock threaded joints exposed to operating loads)'s lock). The keeper print points at these steps."""
    import ch_fulcrum_keeper_spec as keeper
    import draw_ch_fulcrum_keeper as keeper_drawing
    from channel_frame_geom import LEVER_FULCRUM_XY
    from frame_column_stations import COLUMN_X

    number = _config.parts("ch-fulcrum-keeper")["number"]
    fulcrum_shaft = _config.parts("ch-fulcrum-shaft")["number"]
    top_frame = _config.parts("fr-top-frame")["number"]
    assert steps.SEQUENCE[-6:-4] == drawing.LEVER_KEYS[:2]
    assert drawing.LEVER_KEYS == (
        steps.KEEPERS_PAIR_REAMED_KEY,
        steps.KEEPERS_SET_KEY,
        steps.BARS_PINNED_KEY,
        steps.LEVER_BANK_THREADED_KEY,
        steps.SET_SCREWS_STAKED_KEY,
        steps.SPRINGS_HOOKED_KEY,
    )
    places = keeper.KEEPER_FITUP_PLACES
    front, rear = keeper.KEEPER_INNER_FACE_FROM_FRONT_SOCKET_MM
    reamed = _step_body(steps.KEEPERS_PAIR_REAMED_KEY)
    # The controlling operation: installed spacing (KEEPERS_SET_KEY's two faces),
    # one common flat, axis set to it, one pass with a reamer that reaches.
    assert keeper.KEEPER_INNER_FACE_SPAN_MM == pytest.approx(rear - front) == 142.0
    assert f"CLAMP BOTH {number}, FEET OUTBOARD ON ONE FLAT" in reamed
    assert "INNER LUG FACES AT THE LEVER BANK VIEW'S LUG SPAN" in reamed
    assert keeper.KEEPER_INNER_FACE_SPAN_MM == pytest.approx(
        drawing.asm.LUG_INNER_FACE_Z[1] - drawing.asm.LUG_INNER_FACE_Z[0]
    )
    assert "BORE AXIS PARALLEL TO THE FLAT" in reamed
    assert (
        "DRILL AND REAM BOTH IN ONE PASS WITH A 0.2515 IN DIA REAMER, 12 IN LONG."
        in reamed
    )
    assert keeper.PAIR_REAMER_REACH_MARGIN_MM > 0.0
    assert (
        f"ACCEPT IF THE {fulcrum_shaft} SHAFT SLIDES FREELY THROUGH BOTH, CLAMPED."
        in reamed
    )
    # r10 machinist blocker (Main's ruling A): the crown is finished to the
    # keeper print's crown diameter about a pin in its own bore, then tapped,
    # and gauged over the pin. The gauge's low limit never admits a crown
    # under the .X minimum the crown thread's 1.5D is proved at.
    assert (
        f"ON A 6.35 PIN IN EACH BORE, ROUND ITS CROWN TO THE {number} CROWN DIA "
        "14.0 ABOUT THE PIN AND TAP IT #1-72 TO THE BORE." in reamed
    )
    assert reamed.endswith("ACCEPT: CROWN TOP 9.8 TO 10.6 OVER THE PIN'S UNDERSIDE.")
    least_crown = keeper.set_screw_wall_terms(keeper.CROWN_DIA)[
        "crown radius at .X minimum"
    ]
    assert 9.8 - keeper.BORE_DIA / 2.0 >= least_crown
    assert keeper.SET_SCREW_ENGAGEMENT_D >= keeper.SET_SCREW_MIN_ENGAGEMENT_D
    fitted = _step_body(steps.KEEPERS_SET_KEY)
    assert f"{top_frame} ON THE MILL:" in fitted
    # Main's ruling: X off the receiving web, Z off the upper-left socket.
    assert keeper.KEEPER_FITUP_X_FROM_WEB_MM == pytest.approx(
        LEVER_FULCRUM_XY[0] - COLUMN_X
    )
    x = f"{keeper.KEEPER_FITUP_X_FROM_WEB_MM:.{places}f}"
    assert f"{x} WEST OF THE RAIL WEB CENTRE BELOW IT" in fitted
    z = f"Z {front:.{places}f} AND {rear:.{places}f} FROM THE UPPER-LEFT SOCKET"
    assert z in fitted
    assert f"WITHIN {keeper.KEEPER_FITUP_LOCATION_BAND_MM:.{places}f}: THE " in fitted
    # The band's function (Main's ruling, 2026-10-16): the shaft's flat-station
    # window, 0.14 at 0.02 and gone by 0.09 (ch_fulcrum_shaft_spec). The slide
    # (r11 review) moves both flats at once; the band is what leaves it a seat.
    staked_number = steps.step_number(steps.SET_SCREWS_STAKED_KEY)
    assert (
        f"THE {fulcrum_shaft} FLATS ARE A FIXED PITCH APART, AND THIS BAND LEAVES "
        f"ONE STEP {staked_number} SHAFT POSITION WITH BOTH FLATS UNDER THEIR "
        "CROWN TAPS AND NO LEVER HUB ON A FLAT."
    ) in fitted
    assert "EACH FLAT LIES UNDER ITS CROWN TAP" in _step_body(
        steps.SET_SCREWS_STAKED_KEY
    )
    assert "TRANSFER EACH FOOT HOLE INTO THE RAIL" in fitted
    staked = _step_body(steps.SET_SCREWS_STAKED_KEY)
    assert "STAKE EACH TAP MOUTH AT 2 POINTS" in staked
    # The keeper print cites these steps by key.
    assert keeper_drawing.DIMENSION_CALLOUTS["BoreDia"].endswith(
        f"PER {steps.step_ref(steps.KEEPERS_PAIR_REAMED_KEY)}"
    )
    assert keeper_drawing.DIMENSION_CALLOUTS["CrownRadius"].endswith(
        f"PER {steps.step_ref(steps.KEEPERS_PAIR_REAMED_KEY)}"
    )
    staking = steps.step_ref(steps.SET_SCREWS_STAKED_KEY)
    assert staking in keeper_drawing.SET_SCREW_QUALIFIER


def test_each_rod_fork_is_pinned_to_its_arm_at_the_bench_first() -> None:
    """The rod ring is captured in its closed cam slot during the cylinder
    stack, and a pressed pin needs its far tine backed on the press, so the
    MHA-CH-010 pin goes in at the bench, before that drive-train step -- after
    the hub stack is proved on the shaft and the rockers come off in order.
    User ruling 2026-10-09 (PR #1292 review F1): pressed, ends dressed flush,
    removable with a punch, as the MHA-CH-011 bar pin."""
    from ch_rod_pivot_pin_spec import PIN_END_PROUD_MAX

    assert steps.SEQUENCE[:2] == ("rocker-stack-accepted", steps.RODS_PINNED_KEY)
    stack = _step_body("rocker-stack-accepted")
    assert stack.endswith("SLIDE THE ROCKERS OFF IN ORDER AND KEEP THAT ORDER.")
    body = _step_body(steps.RODS_PINNED_KEY)
    rod = _config.parts("ch-connecting-rod")["number"]
    arm = _config.parts("ch-rocker-arm")["number"]
    pin = _config.parts("ch-rod-pivot-pin")["number"]
    assert f"BEFORE {steps.CYLINDER_STACK_REF}, AT THE BENCH:" in body
    assert f"EACH {rod} ROD FORK TO ITS {arm} ARM WITH ONE {pin}." in body
    assert "PRESS IT IN, FAR TINE BACKED; DRESS BOTH ENDS FLUSH." in body
    assert PIN_END_PROUD_MAX == 0.0  # what "FLUSH" states
    # Removal is a property of the pin, not a step: the later steps need the
    # pin in place (CodeRabbit, PR #1292).
    assert "PIN REMOVABLE WITH PUNCH." in body
    assert "DRIVE OUT" not in body
    assert "SWINGS FREE UNDER ITS OWN WEIGHT" in body
    assert "PEEN" not in drawing.FITUP_STEPS
    assert "COUNTERSINK" not in drawing.FITUP_STEPS
    # Positive control: no other step pins this pin; only the bar pin presses.
    for key in steps.SEQUENCE:
        if key != steps.RODS_PINNED_KEY:
            assert pin not in _step_body(key)
        if key not in (steps.RODS_PINNED_KEY, steps.BARS_PINNED_KEY):
            assert "PRESS" not in _step_body(key)



def test_the_finished_shaft_is_set_by_its_north_tip_before_the_screws() -> None:
    """Machinist review (fleet pass): MHA-CH-005 comes finished, domed both
    ends to its overall length, so nothing is cut at assembly. Between the
    south bracket's setting and the set screws one step sets the shaft's
    north tip DOME_HEIGHT proud of the north ear, within the layout's band."""
    import ch_pivot_shaft_spec as shaft

    assert "UNCUT" not in shaft.DRAWING_NOTES and "SUPPLY" not in shaft.DRAWING_NOTES
    assert not hasattr(shaft, "LENGTH_CALLOUT")
    for key in steps.SEQUENCE:
        body = _step_body(key)
        assert "CUT THE" not in body and "SCRIBE" not in body and "UNCUT" not in body
    key = "shaft-set"
    number = steps.step_number(key)
    assert steps.step_number("south-bracket-spring-set") < number
    assert number < steps.step_number("set-screws-driven")
    low = shaft.DOME_HEIGHT - bank.SHAFT_TIP_SET_BAND
    high = shaft.DOME_HEIGHT + bank.SHAFT_TIP_SET_BAND
    assert (
        f"NORTH TIP STANDS {low:.2f} TO {high:.2f} PROUD OF THE NORTH EAR'S OUTER FACE"
        in _step_body(key)
    )
    # Positive control: no other step sets the tip.
    for other in steps.SEQUENCE:
        if other != key:
            assert "NORTH TIP" not in _step_body(other)


def test_the_set_screws_go_in_after_the_shaft_is_set_and_print_the_engagement_fact() -> None:
    """User, 2026-10-10: one MHA-VN-034 down each ear's apex tap onto the
    plain shaft's flat, once the shaft is set, before the preload is
    accepted. The step prints the bracket spec's engagement fact from the
    spec, never typed."""
    import ch_pivot_bracket_spec as bracket_spec

    set_screw = _config.parts("vn-arbor-set-screw")["number"]
    key = "set-screws-driven"
    number = steps.step_number(key)
    assert steps.step_number("shaft-set") < number
    assert number < steps.step_number("preload-accepted")
    body = _step_body(key)
    assert f"RUN ONE {set_screw} DOWN EACH APEX TAP ONTO ITS FLAT" in body
    assert "FLATS UP" in body and "NORTH FIRST" in body
    # drawing-guidelines.md rule 23, period hardware: staked as the keeper
    # set screws are, never threadlocked.
    assert "SNUG, AND STAKE EACH TAP MOUTH AT 2 POINTS." in body
    assert "LOCTITE" not in drawing.FITUP_STEPS
    assert body.endswith(" ".join(bracket_spec.SET_SCREW_ENGAGEMENT_ASSEMBLY_FACT.split()))
    # Positive control: no other step fits the set screws or prints the fact.
    for other in steps.SEQUENCE:
        if other != key:
            assert set_screw not in _step_body(other)
    assert drawing.FITUP_STEPS.count("ENGAGEMENT") == 1


def test_the_set_screw_step_states_a_fact_that_needs_no_declaration() -> None:
    """The owner's 2026-10-15 shortfall ruling (#1371) covered the R8 arch's
    1.08D; the lifted arch holds 1.5D, so the step's engagement fact is no
    shortfall and the channel contract declares no exception for it."""
    import ch_pivot_bracket_spec as bracket_spec
    from _paths import CAD_ROOT
    from machinist_exceptions import load_exceptions

    name = "ch_channel_assembly"
    assert DRAWINGS_BY_NAME[name].source_kind == "assembly"
    assert load_exceptions(CAD_ROOT / "config", name, "assembly") == ()
    fact = (
        f"{bracket_spec.SET_SCREW_THREAD} ENGAGEMENT "
        f"{bracket_spec.SET_SCREW_FULL_THREAD_MIN:.2f} MIN "
        f"({bracket_spec.SET_SCREW_ENGAGEMENT_PRINTED:.2f}D)."
    )
    assert _step_body("set-screws-driven").endswith(fact)
    assert bracket_spec.SET_SCREW_ENGAGEMENT_PRINTED >= 1.5
    assert assembly_contract("ch-channel").number == "MHA-CH-000"


def test_the_set_screw_interference_allowance_is_the_ear_tap() -> None:
    """_interference_contracts restates the ear's apex height over the bore
    and the bore as literals (every assembly imports it); they must be the
    bracket spec's, and the screws' thread its apex tap's."""
    import _interference_contracts as ic
    import ch_pivot_bracket_spec as bracket_spec
    import vn_arbor_set_screw_spec as screw_spec

    assert ic.PIVOT_EAR_APEX_AND_BORE == (
        bracket_spec.APEX_ABOVE_BORE,
        bracket_spec.BORE_DIA,
    )
    assert screw_spec.THREAD == bracket_spec.SET_SCREW_THREAD
    pairs = ic.allowed_interference_pairs("ch-channel")
    for n in (1, 2):
        pair = frozenset((f"vn-arbor-set-screw-{n}", f"ch-pivot-bracket-{n}"))
        assert pairs[pair] == ic.PIVOT_EAR_SET_SCREW_LIMIT
