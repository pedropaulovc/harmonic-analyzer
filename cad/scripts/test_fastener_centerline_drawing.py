"""Fastener centerlines use named-feature cylinder identity, never sheet picks."""

import asyncio
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

import _fastener_drawing as factory
from draw_cone_tip_pinch_screw import RECIPE


@pytest.mark.parametrize("scale,center", [((8, 1), (0.19, 0.19)), ((3, 1), (0.3, 0.08))])
def test_factory_resolves_feature_role_independently_of_layout(monkeypatch, tmp_path, scale, center):
    source = tmp_path / "source.SLDPRT"
    source.touch()
    source_model, face = object(), object()
    side = SimpleNamespace(ReferencedDocument=source_model)
    adapter = SimpleNamespace(open_model=AsyncMock(), currentModel=source_model)
    resolver = Mock()
    resolver.return_value.resolve.return_value = {"side_axis": face}
    centerline = Mock()
    monkeypatch.setattr(factory, "ModelEntities", resolver)
    monkeypatch.setattr(factory, "add_view_centerline", centerline)
    monkeypatch.setattr(factory, "new_project_drawing", Mock(return_value=(object(), object())))
    monkeypatch.setattr(factory, "place_view", Mock(return_value=side))
    monkeypatch.setattr(factory, "finalize_drawing", AsyncMock(return_value={"drawing": "done"}))
    for name in ("check", "read_required_properties", "stamp_drawing_summary", "set_hidden_lines_removed",
                 "auto_center_marks", "curate_view_dimensions", "set_dimension_callouts", "add_property_linked_note"):
        monkeypatch.setattr(factory, name, Mock())
    recipe = replace(RECIPE, scale=scale, side_center=center)
    result = asyncio.run(factory.build_fastener_sheet(
        adapter, source=source, property_view="pinch", outputs=object(), recipe=recipe,
    ))
    assert result == {"drawing": "done"}
    resolver.assert_called_once_with(source_model)
    resolver.return_value.resolve.assert_called_once_with({"side_axis": RECIPE.side_centerline_face})
    centerline.assert_called_once_with(adapter, side, entity=face, label="pinch side-view axis centerline")


def test_centerline_recipe_has_no_coordinate_identity_field():
    assert "side_centerline_face_xy" not in factory.FastenerSheet.__dataclass_fields__
