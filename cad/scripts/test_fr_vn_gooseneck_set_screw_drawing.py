"""MHA-FR-VN-52 gooseneck set screw (McMaster 91410A540): its inch sheet, offline."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import draw_fr_vn_gooseneck_set_screw as draw
from _part_properties import part_drawing_unit


def test_sheet_prints_decimal_inches() -> None:
    assert part_drawing_unit("fr-vn-gooseneck-set-screw") == "in"


def test_only_the_thread_text_shelves_right_of_its_witnesses() -> None:
    assert draw.SHELVES == {"SupplierThreadDiameter": (True, "right")}


def test_right_moves_level_with_front_and_settled_check_refuses_drift(
    monkeypatch,
) -> None:
    # Projected model origin sits a fixed offset from each view's centre.
    front = SimpleNamespace(Position=(0.10, 0.12), origin_offset=-0.004)
    right = SimpleNamespace(Position=(0.30, 0.11), origin_offset=0.002)

    def project(_adapter, view, xyz, *, label):
        assert xyz == (0.0, 0.0, 0.0)
        return (view.Position[0], view.Position[1] + view.origin_offset)

    def move(_adapter, view, x, y, *, move_children):
        assert move_children is False
        view.Position = (x, y)
        return True

    monkeypatch.setattr(draw, "model_point_in_view", project)
    monkeypatch.setattr(draw, "set_view_position", move)
    monkeypatch.setattr(draw, "rebuild_drawing", lambda *_args, **_kwargs: None)

    settled = draw._align_right(object(), {"*Front": front, "*Right": right})

    assert front.Position == (0.10, 0.12)
    assert right.Position == pytest.approx((0.30, 0.114))
    settled()
    right.Position = (0.30, 0.111)
    with pytest.raises(RuntimeError, match="not aligned"):
        settled()
