"""A property link is a real call, not a comment or particular line layout."""

import pytest

from _drawing_test_support import linked_note_properties


@pytest.mark.parametrize("source", [
    'add_property_linked_note(adapter, "Manufacturing Notes", .02, .075)',
    'note = add_property_linked_note(\n adapter,\n "Manufacturing Notes",\n .02, .075\n)',
])
def test_actual_property_link_survives_formatting_and_handle_capture(source):
    assert linked_note_properties(source) == ("Manufacturing Notes",)


@pytest.mark.parametrize("source", [
    '# add_property_linked_note(adapter, "Manufacturing Notes", .02, .075)',
    'add_note(adapter, "Manufacturing Notes", .02, .075)',
    'add_property_linked_note(adapter, "Wrong Property", .02, .075)',
])
def test_non_linked_or_wrong_note_does_not_satisfy_contract(source):
    assert "Manufacturing Notes" not in linked_note_properties(source)
