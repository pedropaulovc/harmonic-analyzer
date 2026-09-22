"""Offline manufacturing boundaries for the shortened purchased stud."""

import pytest

import draw_knife_hanger_stud as drawing
import knife_hanger_stud_spec as spec
from _hole_spec import TAP_DRILL_MM
from diagnostics.diag_build_91247A720 import GB_MAJOR_R


def test_root_chamfer_flat_clears_the_receiving_tap_drill() -> None:
    tap_drill = TAP_DRILL_MM["1/2-13"]
    flat_diameter = 2.0 * (GB_MAJOR_R - spec.CHAMFER_WIDTH_MM)
    assert flat_diameter < tap_drill


def test_iso_fit_translation_centres_the_outline_with_clearance() -> None:
    # The measured pictorial outline at 1.5:1 (54.3 x 101.4 mm: GetOutline is
    # 72.4 x 135.2 mm at 2:1 -- 1.37x the rendered ink -- scaled by 0.75).
    box = (0.330, 0.150, 0.3843, 0.2514)
    dx, dy = drawing._fit_translation(box, drawing.ISO_REGION, drawing.ISO_FIT_MARGIN_M)
    moved = (box[0] + dx, box[1] + dy, box[2] + dx, box[3] + dy)
    region = drawing.ISO_REGION
    margin = drawing.ISO_FIT_MARGIN_M
    assert moved[0] >= region[0] + margin and moved[2] <= region[2] - margin
    assert moved[1] >= region[1] + margin and moved[3] <= region[3] - margin
    # Centring splits the remaining slack evenly: no side is starved of margin.
    assert moved[0] - region[0] == pytest.approx(region[2] - moved[2])
    assert moved[1] - region[1] == pytest.approx(region[3] - moved[3])


def test_iso_fit_rejects_an_outline_that_cannot_fit() -> None:
    with pytest.raises(RuntimeError, match="cannot fit"):
        drawing._fit_translation((0.0, 0.0, 0.1, 0.12), drawing.ISO_REGION, drawing.ISO_FIT_MARGIN_M)


class _FakeDisplay:
    """Records ``SetText`` part writes the way IDisplayDimension stores them."""

    def __init__(self, parts: dict[int, str]) -> None:
        self.parts = dict(parts)
        self.writes: list[tuple[int, str]] = []

    def SetText(self, part: int, text: str) -> None:
        self.writes.append((part, text))
        self.parts[part] = text

    def GetText(self, part: int) -> str:
        return self.parts.get(part, "")


def test_root_finish_callout_writes_definition_then_resolved() -> None:
    display = _FakeDisplay({})
    drawing._write_root_finish_callout(display, drawing.ROOT_FINISH_CALLOUT_TEXT)
    # The stored definition (7) FIRST, then the resolved lane (3) it renders
    # from -- a definition written last can clear what was just resolved.
    assert display.writes == [
        (drawing.CALLOUT_ABOVE_DEFINITION, drawing.ROOT_FINISH_CALLOUT_TEXT),
        (drawing.CALLOUT_ABOVE, drawing.ROOT_FINISH_CALLOUT_TEXT),
    ]
    drawing._assert_root_finish_callout(display, drawing.ROOT_FINISH_CALLOUT_TEXT)


def test_root_finish_callout_lost_across_a_rebuild_is_rejected() -> None:
    text = drawing.ROOT_FINISH_CALLOUT_TEXT
    # The stored definition empty again: the rebuild re-resolved part 3 away.
    display = _FakeDisplay({drawing.CALLOUT_ABOVE: text})
    with pytest.raises(RuntimeError, match="callout"):
        drawing._assert_root_finish_callout(display, text)


