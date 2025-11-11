"""
Test - Direct translation of macro recorder output to Python
"""

# /// script
# requires-python = ">=3.8"
# dependencies = [
#   "pywin32",
# ]
# ///

import win32com.client
from win32com.client import VARIANT
from pythoncom import VT_DISPATCH

def test_macro():
    """
    Direct translation of the VBA macro to Python
    """

    # Connect to SolidWorks
    print("Connecting to SolidWorks...")
    sw_app = win32com.client.Dispatch("SldWorks.Application")

    if sw_app is None:
        print("Error: Failed to connect to SolidWorks")
        return None

    # Make SolidWorks visible
    sw_app.Visible = True

    # Get active document
    print("Getting active document...")
    part = sw_app.ActiveDoc

    if part is None:
        print("Error: No active document. Please open a part in SolidWorks first.")
        return None

    # Create NULL variant for Callout parameter
    null_variant = VARIANT(VT_DISPATCH, None)

    # Insert sketch
    print("Inserting sketch...")
    part.SketchManager.InsertSketch(True)

    # Select Top Plane
    print("Selecting Top Plane...")
    boolstatus = part.Extension.SelectByID2(
        "Top Plane", "PLANE",
        0.0437886626854794, -0.0558921160241118, 0.0121054206500761,
        False, 0, null_variant, 0
    )
    print(f"SelectByID2 result: {boolstatus}")

    # Clear selection
    part.ClearSelection2(True)

    # Create lines (exact coordinates from macro)
    print("Creating lines...")
    seg1 = part.SketchManager.CreateLine(-0.074907, 0.022628, 0.0, 0.05618, 0.022628, 0.0)
    seg2 = part.SketchManager.CreateLine(0.05618, 0.022628, 0.0, 0.05618, -0.018987, 0.0)
    seg3 = part.SketchManager.CreateLine(0.05618, -0.018987, 0.0, -0.074907, -0.018987, 0.0)
    seg4 = part.SketchManager.CreateLine(-0.074907, -0.018987, 0.0, -0.074907, 0.022628, 0.0)

    print(f"Lines created: {seg1}, {seg2}, {seg3}, {seg4}")

    # Clear selection
    part.ClearSelection2(True)

    # Exit sketch
    print("Exiting sketch...")
    part.SketchManager.InsertSketch(True)

    # Try to extrude
    print("Attempting extrusion...")
    extrude_depth = 0.01  # 10mm
    try:
        feat_mgr = part.FeatureManager
        extrude_feature = feat_mgr.FeatureExtrusion2(
            True,   # Single direction
            False,  # Don't flip
            False,  # Don't flip direction
            0,      # Blind end condition
            0,      # Not used
            extrude_depth,  # Depth
            0.0,    # Not used
            False, False, False, False,  # No draft
            0.0, 0.0,  # Draft angles
            False, False, False, False,  # No offset/translate
            True,   # Merge
            False,  # No feature scope
            True,   # Auto select
            0,      # Start from sketch plane
            0.0,    # No start offset
            False   # Don't flip start
        )
        print(f"Extrusion result: {extrude_feature}")
    except Exception as e:
        print(f"Extrusion error: {e}")

    # Rebuild
    part.ForceRebuild3(False)
    part.ViewZoomtofit2()

    print("\n=== Test completed! ===")
    return part


if __name__ == "__main__":
    test_macro()
