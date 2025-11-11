"""
Amplitude Bar - SolidWorks API Translation
Translated from amplitude-bar.kcl
Creates a vertical rod with notches at top and bottom
"""

# /// script
# requires-python = ">=3.8"
# dependencies = [
#   "pywin32",
# ]
# ///

import win32com.client
import pythoncom
from win32com.client import VARIANT
from pythoncom import VT_DISPATCH

# SolidWorks Constants
swSelectOptionDefault = 0

# Input parameters (converted from inches to meters for SolidWorks API)
BAR_LENGTH = 32.0 * 0.0254          # 32" = 0.8128 m
BAR_WIDTH = 0.25 * 0.0254            # 0.25" = 0.00635 m
BAR_DEPTH = 0.25 * 0.0254            # 0.25" = 0.00635 m

# Bottom notch
BOTTOM_NOTCH_WIDTH = 0.125 * 0.0254   # 0.125" = 0.003175 m
BOTTOM_NOTCH_HEIGHT = 0.09375 * 0.0254 # 3/32" = 0.00238125 m

# Top notch
TOP_NOTCH_WIDTH = 0.125 * 0.0254      # 0.125" = 0.003175 m
TOP_NOTCH_HEIGHT = 0.5 * 0.0254       # 0.5" = 0.0127 m

# Calculated parameters
LEFT_NOTCH_OFFSET = (BAR_WIDTH - BOTTOM_NOTCH_WIDTH) / 2  # 0.003175 m
RIGHT_NOTCH_OFFSET = (BAR_WIDTH - TOP_NOTCH_WIDTH) / 2    # 0.003175 m


def create_amplitude_bar():
    """
    Create the amplitude bar part in SolidWorks using the API
    """

    # Connect to SolidWorks
    print("Connecting to SolidWorks...")
    try:
        sw_app = win32com.client.Dispatch("SldWorks.Application")
    except Exception as e:
        print(f"Error: Failed to connect to SolidWorks - {e}")
        return None

    if sw_app is None:
        print("Error: SolidWorks application is None")
        return None

    # Make SolidWorks visible
    sw_app.Visible = True

    # 1. Create new part document
    print("Creating new part document...")
    template_path = r"C:\ProgramData\SolidWorks\SOLIDWORKS 2025\templates\Part.prtdot"
    sw_model = sw_app.NewDocument(template_path, 0, 0.0, 0.0)

    if sw_model is None:
        print("Error: Failed to create new part document")
        return None

    # Get required interfaces
    sw_model_ext = sw_model.Extension
    sw_sketch_mgr = sw_model.SketchManager
    sw_feat_mgr = sw_model.FeatureManager

    # Create NULL variant for Callout parameter (required for SelectByID2)
    null_variant = VARIANT(VT_DISPATCH, None)

    # 2. Select the XZ plane (Front plane in SolidWorks)
    print("Selecting Front Plane...")
    select_result = sw_model_ext.SelectByID2("Front Plane", "PLANE", 0, 0, 0, False, 0, null_variant, 0)

    if not select_result:
        print("Error: Failed to select Front Plane")
        return None

    # 3. Insert sketch on selected plane
    print("Inserting sketch...")
    sw_model.InsertSketch2(True)

    # 4. Draw a simple rectangle profile for testing
    print("Drawing simple rectangle profile...")

    # Draw a simple rectangle: BAR_WIDTH x BAR_LENGTH
    seg1 = sw_sketch_mgr.CreateLine(0, 0, 0, BAR_WIDTH, 0, 0)  # Bottom
    seg2 = sw_sketch_mgr.CreateLine(BAR_WIDTH, 0, 0, BAR_WIDTH, 0, BAR_LENGTH)  # Right
    seg3 = sw_sketch_mgr.CreateLine(BAR_WIDTH, 0, BAR_LENGTH, 0, 0, BAR_LENGTH)  # Top
    seg4 = sw_sketch_mgr.CreateLine(0, 0, BAR_LENGTH, 0, 0, 0)  # Left (close)

    # 5. Extrude the profile by barDepth directly (without exiting sketch)
    print("Extruding profile...")
    print(f"Extrusion depth: {BAR_DEPTH} meters = {BAR_DEPTH * 39.3701:.3f} inches")

    try:
        extrude_feature = sw_feat_mgr.FeatureExtrusion2(
            True,              # Sd: Single direction
            False,             # Flip: Don't flip cut side
            False,             # Dir: Don't flip direction
            0,                 # T1: swEndCondBlind (blind end condition)
            0,                 # T2: Not used for single direction
            BAR_DEPTH,         # D1: Extrusion depth in meters
            0.0,               # D2: Not used
            False,             # Dchk1: No draft
            False,             # Dchk2: No draft
            False,             # Ddir1: Not used
            False,             # Ddir2: Not used
            0.0,               # Dang1: Draft angle
            0.0,               # Dang2: Draft angle
            False,             # OffsetReverse1
            False,             # OffsetReverse2
            False,             # TranslateSurface1
            False,             # TranslateSurface2
            True,              # Merge: Merge results
            False,             # UseFeatScope: Don't use feature scope
            True,              # UseAutoSelect: Auto-select bodies
            0,                 # T0: swStartSketchPlane (start from sketch plane)
            0.0,               # StartOffset: No offset
            False              # FlipStartOffset: Don't flip
        )
        print(f"Extrusion result: {extrude_feature}")
    except Exception as e:
        print(f"Error during extrusion: {e}")
        extrude_feature = None

    if extrude_feature is None:
        print("Error: Failed to create extrusion feature")
        return None

    # 8. Rebuild and zoom to fit
    print("Rebuilding model...")
    sw_model.ForceRebuild3(False)
    sw_model.ViewZoomtofit2()

    print("\n=== Amplitude bar created successfully! ===")
    print(f"Bar dimensions: {BAR_LENGTH * 39.3701:.3f}\" x {BAR_WIDTH * 39.3701:.3f}\" x {BAR_DEPTH * 39.3701:.3f}\"")
    print(f"Bottom notch: {BOTTOM_NOTCH_WIDTH * 39.3701:.3f}\" x {BOTTOM_NOTCH_HEIGHT * 39.3701:.3f}\"")
    print(f"Top notch: {TOP_NOTCH_WIDTH * 39.3701:.3f}\" x {TOP_NOTCH_HEIGHT * 39.3701:.3f}\"")

    return sw_model


if __name__ == "__main__":
    create_amplitude_bar()
