"""Static contracts for document defaults owned by category DRWDOT files."""

from __future__ import annotations

import inspect

import _drawing_common


def test_new_drawing_does_not_rewrite_template_dimension_style():
    source = inspect.getsource(_drawing_common.new_project_drawing)
    assert "SetUserPreferenceInteger" not in source
    assert "GetUserPreferenceInteger" not in source
    assert "dimension_text_and_leader_style" not in source


def test_runtime_dimension_style_normalizer_is_retired():
    assert not hasattr(_drawing_common, "_pin_dimension_text_and_leader_style")
