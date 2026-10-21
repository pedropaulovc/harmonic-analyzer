"""Offline contract for the complete-machine fitter package (MHA-HA-00)."""

from pathlib import Path

import pytest

import build_ha_harmonic_analyzer_assembly as builder
import ch_channel_assembly_steps
import draw_ha_harmonic_analyzer_assembly as drawing
import fr_top_frame_spec
import fr_tube_frame_spec
import ha_harmonic_analyzer_assembly_sheet as notes
import ha_harmonic_analyzer_assembly_spec as spec
import ha_harmonic_analyzer_assembly_steps as steps
import joint_retention
import ch_vn_spring_hook_spec
from _assembly_contract import assembly_contract
from _drawing_registry import DRAWING_TEMPLATES, DRAWINGS_BY_NAME, DrawingLayout


def test_registry_outputs_and_sheet_templates() -> None:
    registered = DRAWINGS_BY_NAME["ha_harmonic_analyzer_assembly"]
    assert registered.source_kind == "assembly"
    assert registered.part == "ha_harmonic_analyzer"
    assert registered.layout is DrawingLayout.PORTRAIT
    assert drawing.SOURCE == registered.source
    assert drawing.OUTPUTS == drawing.OUTPUTS.__class__(
        registered.outputs["slddrw"],
        registered.outputs["pdf"],
        registered.outputs["png"],
    )
    assert set(drawing.SHEET_LAYOUTS) == set(drawing.SHEET_NAMES)
    assert set(drawing.SHEET_SCALES) == set(drawing.SHEET_NAMES)
    assert drawing.SHEET_LAYOUTS[drawing.SHEET_NAMES[0]] is registered.layout
    assert {
        DRAWING_TEMPLATES[layout].path for layout in drawing.SHEET_LAYOUTS.values()
    } == set(registered.assets)
    # The 1:8 single sheet was illegible (#1533): the assembled views read at 1:5.
    assert drawing.SHEET_SCALES[drawing.SHEET_NAMES[0]] == (1.0, 5.0)


def test_bom_is_one_row_per_subassembly_in_insertion_order() -> None:
    assert spec.BOM_ORDER == (*builder.SUBASSEMBLIES, spec.MEASURING_STICK)
    assert len(spec.BOM_ORDER) == len(set(spec.BOM_ORDER)) == 8
    assert drawing.BOM_PART_NUMBERS == {
        stem: assembly_contract(stem).number for stem in spec.BOM_ORDER
    }
    assert all(number.endswith("-00") for number in drawing.BOM_PART_NUMBERS.values())
    assert set(notes.BOM_DESCRIPTIONS) == set(spec.BOM_ORDER)
    assert (
        max(map(len, notes.BOM_DESCRIPTIONS.values()))
        <= drawing.BOM_DESCRIPTION_MAX_CHARS
    )


@pytest.mark.parametrize("row", spec.BOM_ORDER)
def test_each_row_balloons_a_part_only_its_subassembly_builds(row: str) -> None:
    part = notes.BALLOON_PARTS[row]
    scripts = Path(builder.__file__).parent
    owners = [
        stem
        for stem in spec.BOM_ORDER
        if f'"{part}"'
        in (scripts / f"build_{stem.replace('-', '_')}_assembly.py").read_text(
            encoding="utf-8"
        )
    ]
    assert owners == [row]


def test_builder_recipe_does_not_read_the_sheet_text() -> None:
    # Wording edits must not rebuild the complete-machine assembly.
    for module in (builder, spec):
        source = Path(module.__file__).read_text(encoding="utf-8")
        assert "import ha_harmonic_analyzer_assembly_sheet" not in source
        assert "from ha_harmonic_analyzer_assembly_sheet" not in source


def test_explode_moves_every_subassembly_but_the_frame_once_each() -> None:
    instances = [spec.Instance(f"{stem}-1", stem) for stem in spec.BOM_ORDER]
    plan = spec.plan_explode(instances)
    moved = {name for _step, names in plan for name in names}
    assert moved == {f"{stem}-1" for stem in spec.BOM_ORDER if stem != "fr-frame"}
    assert all(len(names) == 1 for _step, names in plan)
    with pytest.raises(ValueError, match="absent"):
        spec.plan_explode(instances[1:-1])
    with pytest.raises(ValueError, match="more than once"):
        spec.plan_explode([*instances, spec.Instance("pn-pen-2", "pn-pen")])


def test_settings_are_derived_from_the_pose_sources() -> None:
    assert spec.BAR_HEIGHT_MM == pytest.approx(529.9)
    # The pen stud stands 0.8 higher since its 3.2 engagement (code review C05).
    assert spec.STUD_DROP_MM == pytest.approx(61.7)
    assert {line.dimension: line.length for line in spec.SETTING_LINES} == {
        spec.BAR_HEIGHT_DIMENSION: spec.BAR_HEIGHT_MM,
        spec.STUD_DROP_DIMENSION: spec.STUD_DROP_MM,
    }
    assert spec.DRAWING_DIMENSIONS == {
        spec.SETTING_FEATURE: {line.dimension for line in spec.SETTING_LINES}
    }


def test_bar_height_chain_lies_on_the_west_front_column_axis() -> None:
    """Machinist review r2/r3 (b4df34ad9): at the deck's west edge the shown
    chain floated beside the column. It lies on the column's axis, and the
    front view's centreline is picked on that axis above the chain's top."""
    (bar,) = [
        line for line in spec.SETTING_LINES if line.dimension == spec.BAR_HEIGHT_DIMENSION
    ]
    assert bar.x == spec.BAR_HEIGHT_X == fr_top_frame_spec.COLUMN_X
    x_m, y_m, _z = drawing.BAR_COLUMN_PICK_M
    assert x_m * 1000.0 == pytest.approx(fr_top_frame_spec.COLUMN_X)
    assert bar.y_high + 100.0 < y_m * 1000.0 < drawing.TOP_SCREW_Y - 100.0


def test_stud_drop_text_stands_east_of_the_east_column() -> None:
    # East is -x; the text's west end (half its ~80 mm of model width at 1:5)
    # must clear the column's outer face.
    column_face = -(fr_top_frame_spec.COLUMN_X + fr_tube_frame_spec.OUTER_DIA / 2.0)
    assert column_face == pytest.approx(-209.7)
    half_width = len(notes.SETTING_CALLOUTS[spec.STUD_DROP_DIMENSION]) * 2.3 * 5 / 2
    assert drawing.STUD_DIMENSION_TEXT_MODEL_X_MM + half_width < column_face - 10.0


def test_steps_cover_the_sequence_and_print_no_setting_values() -> None:
    assert len(notes.ASSEMBLY_STEPS) == len(steps.SEQUENCE)
    for number, line in enumerate(notes.ASSEMBLY_STEPS, 1):
        assert line.startswith(f"{number}. ")
    printed = " ".join(
        (*notes.ASSEMBLY_STEPS, *notes.ASSEMBLY_CHECKS, drawing.ASSEMBLED_NOTE)
    )
    # The settings live on the associative sheet-1 dimensions only.
    for value in (spec.BAR_HEIGHT_MM, spec.STUD_DROP_MM):
        assert f"{value:.1f}" not in printed
    assert "PER MHA-MG-00 SHEET 4." in printed
    # Period hardware: no step leans on, or names, a chemical or nylon lock.
    for bad in ("TBD", "TODO", "THREADLOCK", "LOCTITE", "NYLON", "NYLOC"):
        assert bad not in printed
    # The anchor's install and acceptance are the anchor spec's text, unforked.
    assert ch_vn_spring_hook_spec.ANCHOR_INSTALL_STEP in printed
    assert ch_vn_spring_hook_spec.ANCHOR_INSTALL_CHECK in printed


def test_the_parked_nib_is_set_on_the_paper_before_the_line_check() -> None:
    """Code review C08: the model and the feeler step park the nib
    PEN_PAPER_CLEARANCE_MM off the paper, and nothing on the plumb, guided
    carriage closes that gap, yet check 3 needs a drawn line. The fitter
    slides the marker on in its V until the nib touches, after the parking
    step and before any check; sheet 1 says the views show it parked."""
    from _recording_geometry import PEN_PAPER_CLEARANCE_MM

    parked, contact = steps.step_number("nib-set"), steps.step_number("nib-on-paper")
    assert contact == parked + 1
    by_number = {
        int(line.split(". ", 1)[0]): line for line in notes.ASSEMBLY_STEPS
    }
    feeler = f"{PEN_PAPER_CLEARANCE_MM:.2f} FEELER"
    assert feeler in by_number[parked]
    assert "TOUCHES THE PAPER" in by_number[contact]
    assert "FEELER" not in by_number[contact].replace("NO FEELER", "")
    assert f"REPEAT STEP {parked}" in by_number[contact]
    # No later step re-parks the nib, and the checks find it on the paper
    # before the straight-line run.
    for number in range(contact + 1, len(notes.ASSEMBLY_STEPS) + 1):
        assert "NIB" not in by_number[number]
    checks = " ".join(notes.ASSEMBLY_CHECKS)
    assert "FEELER" not in checks
    assert "THE NIB TOUCHES THE PAPER" in notes.ASSEMBLY_CHECKS[0]
    assert "DRAW A STRAIGHT LINE" in notes.ASSEMBLY_CHECKS[2]
    assert notes.NIB_PARKED_NOTE in drawing.ASSEMBLED_NOTE.replace("\n   ", " ")
    assert (
        f"PARKED {PEN_PAPER_CLEARANCE_MM:.2f} OFF THE PAPER (STEP {parked}); "
        f"STEP {contact} SETS IT ON."
    ) in notes.NIB_PARKED_NOTE
    lines = drawing.ASSEMBLED_NOTE.count("\n") + 1
    portrait = DRAWING_TEMPLATES[DrawingLayout.PORTRAIT]
    bottom = drawing.ASSEMBLED_NOTE_XY[1] - lines * drawing.NOTE_LINE_PITCH
    assert bottom > portrait.title_block_top_m
    assert max(map(len, drawing.ASSEMBLED_NOTE.splitlines())) <= (
        drawing.ASSEMBLED_NOTE_WIDTH
    )


def test_integration_joints_point_at_their_integration_steps() -> None:
    rows = {joint.id: joint for joint in joint_retention.JOINTS}
    anchor = rows["ha-harmonic-analyzer/channel-anchor-in-summing-plate"]
    nut = rows["ha-harmonic-analyzer/channel-anchor-jam-nut-on-anchor"]
    step = steps.step_ref("channel-anchors-set")
    assert anchor.installed_at == anchor.lock_step == nut.installed_at == step
    assert anchor.lock is joint_retention.Lock.JAM_NUT
    assert anchor.lock_part == nut.member == "ch_anchor_jam_nut"
    bracket = rows["ha-harmonic-analyzer/magnifying-bracket-screws"]
    assert bracket.installed_at == steps.step_ref("magnifier-bracket-screwed")


def test_channel_sheet_cites_the_anchor_step_by_its_number() -> None:
    # MHA-CH-00 prints this pointer as a literal (its steps module sits below
    # this one in the stack); a reorder here must move it too.
    assert ch_channel_assembly_steps.HA_ANCHORS_SET_REF == steps.step_ref(
        "channel-anchors-set"
    )


def test_steps_sheet_text_clears_the_title_block() -> None:
    landscape = DRAWING_TEMPLATES[DrawingLayout.LANDSCAPE]
    assert drawing.STEPS_COLUMN_BOTTOM_Y > landscape.title_block_top_m
    for block in (drawing.STEPS_LEFT, drawing.STEPS_RIGHT, drawing.ASSEMBLY_CHECKS):
        assert max(map(len, block.splitlines())) <= drawing.STEPS_LINE_WIDTH


# Native added-strip behavior belongs to the integrated assembly: neither the
# summing nor magnifier subassembly contains both sides of these installed fits.
class _ReceiverBody:
    def __init__(self, scene, points=(), *, predicate=None, temporary=False, tag=""):
        self.scene = scene
        self.points = frozenset(points)
        self.predicate = predicate
        self.temporary = temporary
        self.tag = tag
        self.consumed = False
        self.Check3 = type("Faults", (), {"Count": 0})()

    def GetType(self):
        return 0

    def Copy(self):
        assert not self.consumed
        return _ReceiverBody(
            self.scene, self.points, predicate=self.predicate, temporary=True, tag=self.tag
        )

    def ApplyTransform(self, transform):
        assert self.temporary and not self.consumed
        self.scene.transforms.append((self.tag, transform))
        if self.scene.transform_fail:
            return False
        values = transform.ArrayData
        self.points = frozenset(
            tuple(
                sum(point[j] * values[j * 3 + k] for j in range(3))
                + 1000.0 * values[9 + k]
                for k in range(3)
            )
            for point in self.points
        )
        return True

    def Operations2(self, operation, tool, _error):
        assert self.temporary and tool.temporary
        assert not self.consumed and not tool.consumed
        self.consumed = tool.consumed = True
        if self.scene.boolean_fail and tool.tag == self.scene.failed_neighbor:
            return None, 1058
        selected = {
            point for point in self.points
            if (tool.predicate(point) if tool.predicate else point in tool.points)
        }
        points = selected if operation == 15901 else self.points - selected
        if not points:
            return None, 0
        return (_ReceiverBody(self.scene, points, temporary=True, tag=self.tag),), 0

    def GetMassProperties(self, _density):
        return (0.0, 0.0, 0.0, len(self.points) / 1e9, *([0.0] * 8))

    def GetExtremePoint(self, x, y, z):
        point = max(self.points, key=lambda p: p[0] * x + p[1] * y + p[2] * z)
        return (True, *(value / 1000.0 for value in point))


class _ReceiverComponent:
    def __init__(self, scene, family, index):
        from types import SimpleNamespace as NS

        parent = "ch-channel" if family.startswith("ch-") else (
            "mg-magnifier" if family.startswith("mg-") else "sm-summing"
        )
        self.Name2 = f"{parent}-1/{family}-{index}"
        source = f"{family}-stretch00" if family == "ch-vn-channel-spring-installed" else family
        self.source = f"C:\\native\\{source}.SLDPRT"
        self.Transform2 = NS(ArrayData=(
            1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0,
            0.5, 0.98, -0.004, 1.0, 0.0, 0.0, 0.0,
        ))
        self.scene = scene
        self.suppressed = False
        if family == "sm-summing-lever":
            # Finite samples at both strip boundaries AND the interior: plate,
            # cylinder, pad, slanted rib, R.4 fill and unchanged -X web.
            points = {
                (x, y, z) for z in (-68.0, -67.4, -66.8)
                for x, y in ((20.0, 0.0), (0.0, 0.0), (35.0, -3.0),
                             (20.0, 8.0), (35.9, 2.7), (-20.0, 0.0))
            }
        else:
            points = {(200.0 + index, 0.0, -67.4)}
        self.bodies = [_ReceiverBody(scene, points, tag=self.Name2)]

    def GetPathName(self):
        return self.source

    def IsSuppressed(self):
        return self.suppressed

    def GetBodies3(self, kind):
        assert kind == 0
        self.scene.body_reads.append(self)
        return tuple(self.bodies), tuple(0 for _ in self.bodies)

    def FeatureByName(self, name):
        from types import SimpleNamespace as NS
        import _native_receiver_clearance as native

        dims = {
            "EdgeRibBack": {"RibDepth": self.scene.depth},
            "CoefficientsPlate": {"PlateThickness": native.lever.PLATE_T},
            "CylinderProfile": {"CylDia": 2.0 * native.lever.CYL_R},
            "SpringPadProfile": {"SpringPadWidth": native.lever.SPRING_PAD_W,
                                 "SpringSeatThickness": native.lever.SPRING_SEAT_T},
            "EdgeRibBackProfile": {"EdgeRibBackEndTopX": native.lever.RIB_PLATE_REACH},
        }
        if name not in dims:
            return None
        planes = [
            NS(GetSurface=lambda z=z: NS(
                IsPlane=lambda: True, PlaneParams=(0.0, 0.0, 1.0, 0.0, 0.0, z / 1000.0)
            ))
            for z in (native.OUTER_Z_MM, self.scene.cap)
        ]
        return NS(
            Parameter=lambda key: NS(SystemValue=dims[name][key] / 1000.0)
            if key in dims[name] else None,
            GetFaces=lambda: planes,
        )


class _ReceiverScene:
    def __init__(self):
        import _native_receiver_clearance as native

        self.boxes = []
        self.body_reads, self.transforms, self.root_lookups = [], [], []
        self.boolean_fail = self.transform_fail = self.exploded = False
        self.bad_distance = None
        self.depth, self.cap = 9.40, -66.8
        self.currentModel = self.swApp = self
        counts = {**dict.fromkeys(native.CHANNEL_FAMILIES, 2), **native.FIXED_COUNTS}
        self.components = [
            _ReceiverComponent(self, family, index)
            for family, count in counts.items() for index in range(1, count + 1)
        ]
        self.failed_neighbor = self.components[-1].Name2

    def IsExploded(self):
        return self.exploded

    def GetComponents(self, top_only):
        assert top_only is False  # A top-only walk silently misses every leaf.
        return tuple(reversed(self.components))  # Native order is unspecified.

    def GetComponentByName(self, name):
        self.root_lookups.append(name)
        raise AssertionError(f"root GetComponentByName cannot resolve nested occurrence aliases: {name}")

    def GetModeler(self):
        return self

    def CreateBodyFromBox3(self, values):
        cx, cy, z, ax, ay, az, w, length, height = values
        assert (ax, ay, az) == (0.0, 0.0, 1.0)
        low = ((cx - w / 2.0) * 1000.0, (cy - length / 2.0) * 1000.0, z * 1000.0)
        high = ((cx + w / 2.0) * 1000.0, (cy + length / 2.0) * 1000.0, (z + height) * 1000.0)
        self.boxes.append((low, high))
        return _ReceiverBody(
            self, predicate=lambda p: all(
                a - 1e-9 <= value <= b + 1e-9
                for value, a, b in zip(p, low, high, strict=True)
            ), temporary=True, tag="box",
        )

    def CreateBodyFromCyl(self, values):
        x, y, z, ax, ay, az, radius, height = values
        assert (x, y, ax, ay, az) == (0.0, 0.0, 0.0, 0.0, 1.0)
        return _ReceiverBody(
            self, predicate=lambda p: (
                p[0] ** 2 + p[1] ** 2 <= (radius * 1000.0) ** 2
                and z * 1000.0 - 1e-9 <= p[2] <= (z + height) * 1000.0 + 1e-9
            ), temporary=True, tag="cylinder",
        )

    def ClosestDistance(self, first, second):
        import math

        assert first.temporary and second.temporary
        assert not first.consumed and not second.consumed
        distance, p, q = min(
            (math.dist(p, q), p, q) for p in first.points for q in second.points
        )
        return (
            self.bad_distance if self.bad_distance is not None else distance / 1000.0,
            tuple(v / 1000.0 for v in p), tuple(v / 1000.0 for v in q),
        )


@pytest.fixture
def receiver_scene(monkeypatch):
    import _native_receiver_clearance as native

    scene = _ReceiverScene()
    monkeypatch.setattr(native, "double_array", tuple)
    monkeypatch.setattr(native._config, "active_count", lambda: 2)
    return scene


def test_receiver_strip_subtracts_invariants_but_retains_native_rib_and_round(receiver_scene):
    import _native_receiver_clearance as native

    lever = next(c for c in receiver_scene.components if "/sm-summing-lever-" in c.Name2)
    pieces = native._added_material(receiver_scene, lever.bodies)
    points = set().union(*(b.points for b in pieces))
    assert {p[:2] for p in points} == {(20.0, 8.0), (35.9, 2.7), (-20.0, 0.0)}
    assert {p[2] for p in points} == {-68.0, -67.4, -66.8}
    assert receiver_scene.boxes[0][0][2] == pytest.approx(-68.0)
    assert receiver_scene.boxes[0][1][2] == pytest.approx(-66.8)
    assert all(not body.consumed for body in lever.bodies)
    assert lever.bodies[0].points != frozenset(points)


def test_receiver_strip_measures_every_actual_nested_pair_and_machine_witness(receiver_scene):
    import _native_receiver_clearance as native

    records = native.assert_receiver_added_strip(receiver_scene, builder.ASM_NAME)
    expected = {c.Name2 for c in receiver_scene.components if "/sm-summing-lever-" not in c.Name2}
    assert {row["neighbor"] for row in records} == expected
    assert len(records) == 5 * 2 + sum(native.FIXED_COUNTS.values()) - 1
    assert all(row["overlap_mm3"] == 0.0 and row["closest_distance_mm"] > 0.0 for row in records)
    assert all(row["material_scope"] == native.MATERIAL_SCOPE and row["claim"] == native.CLAIM for row in records)
    assert all(row["closest_points_mm"][0][1] > 900.0 for row in records)
    assert all(not b.consumed for c in receiver_scene.components for b in c.bodies)


def test_receiver_strip_uses_enumerated_occurrence_bodies_and_distinct_root_relative_poses(receiver_scene):
    import math
    import _native_receiver_clearance as native

    occurrences = {component.Name2: component for component in receiver_scene.components}
    originals = {name: component.bodies[0].points for name, component in occurrences.items()}
    for index, component in enumerate(occurrences.values()):
        assert "/" in component.Name2  # None is a top-level lookup key.
        values = list(component.Transform2.ArrayData)
        values[9:12] = (0.5 + index / 100.0, 0.98 + index / 1000.0, -0.004 - index / 1000.0)
        component.Transform2.ArrayData = tuple(values)

    records = native.assert_receiver_added_strip(receiver_scene, builder.ASM_NAME)

    assert receiver_scene.root_lookups == []
    assert len(receiver_scene.body_reads) == len(occurrences)
    assert {id(component) for component in receiver_scene.body_reads} == {
        id(component) for component in occurrences.values()
    }
    assert {name for name, _pose in receiver_scene.transforms} == set(occurrences)
    assert all(pose is occurrences[name].Transform2 for name, pose in receiver_scene.transforms)

    def placed_points(name, points):
        translation = occurrences[name].Transform2.ArrayData[9:12]
        return {
            tuple(value + 1000.0 * offset for value, offset in zip(point, translation, strict=True))
            for point in points
        }

    receiver_name = next(name for name in occurrences if "/sm-summing-lever-" in name)
    added = placed_points(receiver_name, {
        point for point in originals[receiver_name]
        if point[:2] in {(20.0, 8.0), (35.9, 2.7), (-20.0, 0.0)}
    })
    for record in records:
        neighbor = record["neighbor"]
        fixed = placed_points(neighbor, originals[neighbor])
        first, second = record["closest_points_mm"]
        assert any(first == pytest.approx(point) for point in added)
        assert any(second == pytest.approx(point) for point in fixed)
        assert record["closest_distance_mm"] == pytest.approx(
            min(math.dist(p, q) for p in added for q in fixed)
        )
    assert all(
        component.bodies[0].points == originals[name] and not component.bodies[0].consumed
        for name, component in occurrences.items()
    )


def test_receiver_strip_does_not_mistake_existing_intended_plate_contact_for_air_failure(receiver_scene):
    import _native_receiver_clearance as native

    neighbor = receiver_scene.components[-1]
    # Whole-lever contact at an invariant plate point is deliberately zero.
    neighbor.bodies[0].points = frozenset({(20.0, 0.0, -67.4)})
    rows = native.assert_receiver_added_strip(receiver_scene, builder.ASM_NAME)
    row = next(row for row in rows if row["neighbor"] == neighbor.Name2)
    assert row["overlap_mm3"] == 0.0
    assert row["closest_distance_mm"] > 0.0  # Strip-only, not whole-component distance.


@pytest.mark.parametrize("mode", ["collision", "boolean", "touch", "transform"])
def test_receiver_strip_native_failures_cannot_be_waived(receiver_scene, monkeypatch, mode):
    import _native_receiver_clearance as native

    if mode == "collision":
        receiver_scene.components[-1].bodies[0].points = frozenset({(20.0, 8.0, -67.4)})
        message = "intersects"
    elif mode == "boolean":
        receiver_scene.boolean_fail = True
        message = "1058"
    elif mode == "touch":
        receiver_scene.bad_distance = 0.0
        message = "no positive static native air"
    else:
        receiver_scene.transform_fail = True
        message = "transform failed"
    # The local checker has no access to, and cannot inherit, allowed_pairs.
    monkeypatch.setattr(builder, "allowed_interference_pairs", lambda *_: pytest.fail("allowance read"))
    with pytest.raises(RuntimeError, match=message):
        native.assert_receiver_added_strip(receiver_scene, builder.ASM_NAME)


@pytest.mark.parametrize("wrong", ["depth", "cap", "actual_strip"])
def test_receiver_strip_rejects_wrong_receiver_geometry(receiver_scene, wrong):
    import _native_receiver_clearance as native

    if wrong == "depth":
        receiver_scene.depth = 8.20
    elif wrong == "cap":
        receiver_scene.cap = -68.0
    else:
        lever = next(c for c in receiver_scene.components if "/sm-summing-lever-" in c.Name2)
        lever.bodies[0].points = frozenset(p for p in lever.bodies[0].points if p[2] < -67.0)
    with pytest.raises(RuntimeError, match="expected|caps|bounds"):
        native.assert_receiver_added_strip(receiver_scene, builder.ASM_NAME)


@pytest.mark.parametrize("family", [
    "ch-vn-channel-spring-installed", "ch-vn-spring-hook", "ch-anchor-jam-nut",
    "ch-channel-lever", "ch-connecting-rod", "sm-vn-counter-spring",
    "sm-vn-boss-hook", "sm-vn-boss-hook-jam-nut", "sm-knife-mount",
    "mg-magnifying-bracket", "mg-vn-magnifying-bracket-screw",
    "mg-magnifying-lever", "mg-magnifying-vertical-rod", "mg-vn-lever-wire",
    "mg-magnifying-clamp", "mg-vn-thumb-screw", "mg-output-fixture",
])
def test_receiver_strip_requires_all_relevant_installed_families(receiver_scene, family):
    import _native_receiver_clearance as native

    missing = next(c for c in receiver_scene.components if f"/{family}-" in c.Name2)
    receiver_scene.components.remove(missing)
    with pytest.raises(RuntimeError, match=f"missing coverage for {family}"):
        native.assert_receiver_added_strip(receiver_scene, builder.ASM_NAME)


@pytest.mark.parametrize("bad_distance", [-1.0, float("nan"), float("inf"), 0.001])
def test_receiver_strip_requires_finite_consistent_positive_distance_witnesses(receiver_scene, bad_distance):
    import _native_receiver_clearance as native

    receiver_scene.bad_distance = bad_distance
    with pytest.raises(RuntimeError, match="static native air|witness disagreement"):
        native.assert_receiver_added_strip(receiver_scene, builder.ASM_NAME)


def test_receiver_strip_is_static_and_cannot_certify_exploded_or_missing_solids(receiver_scene):
    import _native_receiver_clearance as native

    receiver_scene.exploded = True
    with pytest.raises(RuntimeError, match="collapsed"):
        native.assert_receiver_added_strip(receiver_scene, builder.ASM_NAME)
    receiver_scene.exploded = False
    receiver_scene.components[-1].bodies = []
    with pytest.raises(RuntimeError, match="no actual solid"):
        native.assert_receiver_added_strip(receiver_scene, builder.ASM_NAME)


@pytest.fixture
def receiver_save_pipeline(tmp_path, monkeypatch):
    """Exercise the real save/refresh callback ordering, not source-string tests."""
    import _assembly
    from types import SimpleNamespace as NS

    events = []
    target = tmp_path / f"{builder.ASM_NAME}.SLDASM"
    target.write_bytes(b"original")
    proof = tmp_path / "proof"
    proof.write_text("same\n", encoding="utf-8")
    model = NS(
        IsExploded=lambda: False, ForceRebuild3=lambda *_: True,
        Extension=NS(NeedsRebuild2=0), GetConfigurationNames=lambda: ["Default"],
    )

    async def opened(*_):
        events.append("open")
        return NS(is_success=True, data={}, error=None)

    async def configurations():
        return NS(is_success=True, data=["Default"], error=None)

    async def digest(*_):
        events.append("digest")
        return "same"

    async def reconciled(*_):
        events.append("reconcile")

    async def images(*_):
        return {}

    adapter = NS(
        currentModel=model, open_model=opened, list_configurations=configurations,
        _attempt=lambda function, default=None: function(),
    )
    monkeypatch.setattr(_assembly, "OUT_SLDASM", tmp_path)
    monkeypatch.setattr(_assembly, "_massprops_sidecar", lambda *_: proof)
    monkeypatch.setattr(_assembly, "check", lambda _label, result: result.data)
    monkeypatch.setattr(_assembly, "sync_simplified_configuration", lambda *_a, **_k: 0)
    monkeypatch.setattr(_assembly, "saved_rebuild_status", lambda *_: 0)
    monkeypatch.setattr(_assembly, "active_configuration_name", lambda *_: "Default")
    monkeypatch.setattr(_assembly, "_rebuild_faults", lambda *_: [])
    monkeypatch.setattr(_assembly, "assembly_geometry_digest", digest)
    monkeypatch.setattr(_assembly, "reconcile_saved_rebuild_state", reconciled)
    monkeypatch.setattr(_assembly, "_export_assembly_images", images)
    for name in ("assert_saved_display_data", "final_rebuild_before_save",
                 "assert_model_healthy", "assert_pose_ledger", "audit_flip_seeds",
                 "assert_reference_geometry_hidden", "set_isometric_view",
                 "_discard_copy_source", "assert_manifest_dof_state", "check_no_interference"):
        monkeypatch.setattr(_assembly, name, lambda *_a, **_k: None)
    monkeypatch.setattr(_assembly, "rebuild_if_needed_before_save", lambda *_: False)
    monkeypatch.setattr(_assembly, "_save_new_assembly_as_copy", lambda *_: events.append("save"))
    monkeypatch.setattr(_assembly, "save_assembly_in_place", lambda _a, _n, changed, **_kwargs: (
        events.append("save" if changed else "skip_save") or changed
    ))
    return NS(adapter=adapter, events=events, proof=proof, target=target, module=_assembly)


def test_top_fresh_save_runs_native_gate_after_reconcile_before_proof(receiver_save_pipeline):
    import asyncio

    p = receiver_save_pipeline

    def callback(adapter, asm_name):
        assert adapter is p.adapter and asm_name == builder.ASM_NAME
        assert not p.proof.exists()
        p.events.append("native")

    asyncio.run(p.module.save_assembly_and_images(
        p.adapter, builder.ASM_NAME, [], native_contact_check=callback,
        solved_gates=lambda _adapter: p.events.append("pre_native"),
    ))
    assert p.events == ["pre_native", "save", "reconcile", "native", "digest"]
    assert p.proof.read_text(encoding="utf-8") == "same\n"


@pytest.mark.parametrize("changed", [False, True])
def test_top_refresh_never_skips_pre_save_or_persisted_native_gate(receiver_save_pipeline, changed):
    import asyncio

    p = receiver_save_pipeline
    if changed:
        p.proof.write_text("old\n", encoding="utf-8")

    def callback(_adapter, _name):
        assert not p.proof.exists()
        p.events.append("native")

    asyncio.run(p.module.refresh_assembly(
        p.adapter, builder.ASM_NAME, [], native_contact_check=callback,
    ))
    assert p.events == (
        ["open", "digest", "native", "save", "reconcile", "native"]
        if changed else ["open", "digest", "native", "skip_save", "native"]
    )
    assert p.proof.read_text(encoding="utf-8") == "same\n"


@pytest.mark.parametrize("path", ["save", "refresh"])
def test_top_native_failure_leaves_no_certificate(receiver_save_pipeline, path):
    import asyncio

    p = receiver_save_pipeline

    def failing(*_):
        raise RuntimeError("strip collision")

    function = p.module.save_assembly_and_images if path == "save" else p.module.refresh_assembly
    with pytest.raises(RuntimeError, match="strip collision"):
        asyncio.run(function(p.adapter, builder.ASM_NAME, [], native_contact_check=failing))
    assert not p.proof.exists()
    if path == "refresh":
        assert "save" not in p.events
        assert p.target.read_bytes() == b"original"


@pytest.mark.parametrize("path", ["save", "refresh"])
def test_top_native_callback_is_mandatory_before_any_save(receiver_save_pipeline, path):
    import asyncio

    p = receiver_save_pipeline
    function = p.module.save_assembly_and_images if path == "save" else p.module.refresh_assembly
    with pytest.raises(ValueError, match="requires native_contact_check"):
        asyncio.run(function(p.adapter, builder.ASM_NAME, []))
    assert p.events == []


def test_top_refresh_entrypoint_passes_the_same_native_gate(monkeypatch):
    import asyncio
    import refresh_assembly

    seen = []

    async def refresh(adapter, asm_name, **kwargs):
        assert kwargs["native_contact_check"] is builder._assert_receiver_added_strip
        kwargs["native_contact_check"](adapter, asm_name)
        return {"assembly": "saved"}

    async def exports(_adapter):
        return {}

    monkeypatch.setattr(builder, "assert_receiver_added_strip", lambda _a, name: seen.append(name))
    monkeypatch.setattr(builder, "export_gallery_and_bom", exports)
    monkeypatch.setattr(refresh_assembly, "refresh_assembly", refresh)
    asyncio.run(refresh_assembly._refresh_parts(object(), builder.ASM_NAME))
    assert seen == [builder.ASM_NAME]


@pytest.mark.parametrize("operation", [15901, 15902])
def test_receiver_strip_construction_boolean_failure_is_fatal(receiver_scene, monkeypatch, operation):
    import _native_receiver_clearance as native

    original = _ReceiverBody.Operations2

    def fail(self, kind, tool, error):
        if kind == operation and tool.tag in ("box", "cylinder"):
            assert self.temporary and tool.temporary
            self.consumed = tool.consumed = True
            return None, 1058
        return original(self, kind, tool, error)

    monkeypatch.setattr(_ReceiverBody, "Operations2", fail)
    with pytest.raises(RuntimeError, match="1058"):
        native.assert_receiver_added_strip(receiver_scene, builder.ASM_NAME)


def test_top_builder_passes_native_gate_to_both_solved_and_persisted_paths(monkeypatch):
    import asyncio
    from types import SimpleNamespace as NS

    seen = []

    async def success(*_args, **_kwargs):
        return NS(data={"name": "component", "fixed": True})

    async def author(*_):
        pass

    async def save(adapter, asm_name, **kwargs):
        assert kwargs["solved_gates"] is builder._assert_receiver_added_strip
        assert kwargs["native_contact_check"] is builder._assert_receiver_added_strip
        kwargs["solved_gates"](adapter)
        kwargs["native_contact_check"](adapter, asm_name)
        return {"assembly": "saved"}

    async def exports(*_):
        return {}

    for name in ("activate_assembly_contract", "assert_component_placed",
                 "assert_components_fully_defined", "check_no_interference",
                 "apply_custom_properties", "remap_front_to_machine_front",
                 "author_in_drawing_configurations", "_discard_copy_source"):
        monkeypatch.setattr(builder, name, lambda *_a, **_k: None)
    monkeypatch.setattr(builder, "check", lambda _label, result: result.data)
    monkeypatch.setattr(builder, "_subassembly", lambda name: f"C:/native/{name}.SLDASM")
    monkeypatch.setattr(builder, "_author_integration_settings", author)
    monkeypatch.setattr(builder, "save_assembly_and_images", save)
    monkeypatch.setattr(builder, "export_gallery_and_bom", exports)
    monkeypatch.setattr(builder, "assert_receiver_added_strip", lambda _a, name: seen.append(name))
    adapter = NS(create_assembly=success, insert_component=success, open_model=success)
    asyncio.run(builder.build(adapter))
    assert seen == [builder.ASM_NAME, builder.ASM_NAME]


def test_receiver_strip_checks_later_native_bodies_of_each_occurrence(receiver_scene):
    import _native_receiver_clearance as native

    neighbor = receiver_scene.components[-1]
    neighbor.bodies.append(_ReceiverBody(
        receiver_scene, {(35.9, 2.7, -67.4)}, tag=neighbor.Name2
    ))
    with pytest.raises(RuntimeError, match="intersects"):
        native.assert_receiver_added_strip(receiver_scene, builder.ASM_NAME)


def test_receiver_strip_rejects_suppressed_required_occurrence(receiver_scene):
    import _native_receiver_clearance as native

    receiver_scene.components[-1].suppressed = True
    with pytest.raises(RuntimeError, match="required occurrence suppressed"):
        native.assert_receiver_added_strip(receiver_scene, builder.ASM_NAME)


def test_top_pre_save_strip_failure_revokes_old_proof_without_replacing_assembly(receiver_save_pipeline):
    import asyncio

    p = receiver_save_pipeline

    def failing(_adapter):
        raise RuntimeError("pre-save strip collision")

    with pytest.raises(RuntimeError, match="pre-save strip collision"):
        asyncio.run(p.module.save_assembly_and_images(
            p.adapter, builder.ASM_NAME, [],
            native_contact_check=lambda *_: None, solved_gates=failing,
        ))
    assert not p.proof.exists()
    assert "save" not in p.events
    assert p.target.read_bytes() == b"original"
