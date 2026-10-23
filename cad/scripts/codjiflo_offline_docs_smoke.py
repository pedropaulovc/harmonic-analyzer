"""Temporary documentation-backed review fixture; never merge this branch."""

def set_dimension_prefix(display_dimension, document, prefix):
    """Set a prefix while preserving the dimension value and suffix."""
    display_dimension.SetText(0, prefix)
    document.GraphicsRedraw2()
