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

    print("\n=== Rectangle created successfully! ===")
    return part


if __name__ == "__main__":
    test_macro()
