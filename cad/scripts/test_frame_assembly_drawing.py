"""Observable package contract for the frame assembly drawing."""

import draw_frame_assembly as drawing
from _drawing_registry import DRAWINGS_BY_NAME, DrawingLayout


def test_frame_assembly_keeps_registered_identity_and_outputs() -> None:
    spec = DRAWINGS_BY_NAME["frame_assembly"]
    assert spec.source_kind == "assembly"
    assert spec.part == "frame"
    assert spec.layout is DrawingLayout.LANDSCAPE
    assert drawing.SOURCE == spec.source
    assert drawing.OUTPUTS == drawing.OUTPUTS.__class__(
        spec.outputs["slddrw"], spec.outputs["pdf"], spec.outputs["png"]
    )


def test_frame_package_covers_every_as_built_component_family() -> None:
    assert drawing.SHEET_NAMES == (
        "ASSEMBLED + JOINT SECTIONS",
        "EXPLODED VIEW + BOM",
        "FITTING + ASSEMBLY",
    )
    assert drawing.BOM_QUANTITIES == {
        "harmonic-base": 1,
        "tube-frame": 4,
        "tube-frame-cap": 4,
        "rocker-arm-support": 1,
        "lag-screw": 4,
        "top-frame": 1,
        "nameplate": 1,
        "fillister-screw": 4,
        "frame-cross-screw": 8,
        "gooseneck-set-screw": 1,
    }
    assert sum(drawing.BOM_QUANTITIES.values()) == 29
    assert set(drawing.BOM_COMPONENTS) == set(drawing.BOM_DESCRIPTIONS)
    assert drawing.BOM_PART_NUMBERS == {
        "harmonic-base": "MHA-035",
        "tube-frame": "MHA-083",
        "tube-frame-cap": "MHA-133",
        "rocker-arm-support": "MHA-089",
        "lag-screw": "MHA-039",
        "top-frame": "MHA-077",
        "nameplate": "MHA-086",
        "fillister-screw": "MHA-030",
        "frame-cross-screw": "MHA-132",
        "gooseneck-set-screw": "MHA-118",
    }
    assert drawing.BOM_IDENTITY_ALIASES == {
        number: stem for stem, number in drawing.BOM_PART_NUMBERS.items()
    }
