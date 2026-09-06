"""Mixed-command diagnostic must preserve exact manufacturing attachments."""

from copy import deepcopy
from types import SimpleNamespace

import pytest

from probe_drawing_mixed_commands import unchanged


def witness():
    annotation, entity = object(), object()
    adapter = SimpleNamespace(swApp=SimpleNamespace(IsSame=lambda a, b: int(a is b)))
    row = {
        "2:DatumA": {
            "kind": 2,
            "visibility": 1,
            "attachment_types": (2,),
            "content": ("A",),
            "position": (0.1, 0.2, 0),
        }
    }
    native = {"2:DatumA": (annotation, (entity,))}
    return adapter, row, native


def test_only_native_position_may_change():
    adapter, before, native = witness()
    after = deepcopy(before)
    after["2:DatumA"]["position"] = (0.2, 0.3, 0)
    unchanged(adapter, before, native, after, native)


@pytest.mark.parametrize(
    "field,value",
    [("kind", 7), ("visibility", 3), ("attachment_types", (1,)), ("content", ("B",))],
)
def test_changed_manufacturing_content_is_rejected(field, value):
    adapter, before, native = witness()
    after = deepcopy(before)
    after["2:DatumA"][field] = value
    with pytest.raises(RuntimeError, match="changed"):
        unchanged(adapter, before, native, after, native)


def test_identical_metadata_cannot_hide_replaced_native_attachment():
    adapter, before, native = witness()
    replacement = {"2:DatumA": (native["2:DatumA"][0], (object(),))}
    with pytest.raises(RuntimeError, match="exact attachment"):
        unchanged(adapter, before, native, before, replacement)
