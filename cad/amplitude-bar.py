"""
Amplitude Bar - SolidWorks API Translation
Translated from amplitude-bar.kcl
Creates a vertical rod with notches at top and bottom
"""

import win32com.client
import pythoncom

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
    sw_model = sw_app.NewDocument("", 0, 0.0, 0.0)

    if sw_model is None:
        print("Error: Failed to create new part document")
        return None

    # Get required interfaces
    sw_model_ext = sw_model.Extension
    sw_sketch_mgr = sw_model.SketchManager
    sw_feat_mgr = sw_model.FeatureManager

    # 2. Select the XZ plane (Front plane in SolidWorks)
    print("Selecting Front Plane...")
    select_result = sw_model_ext.SelectByID2(
        "Front Plane",     # Plane name
        "PLANE",           # Selection type
        0, 0, 0,           # X, Y, Z coordinates (not used for named selection)
        False,             # Append = False (clear previous selection)
        0,                 # Mark
        None,              # Callout
        0                  # swSelectOptionDefault
    )

    if not select_result:
        print("Error: Failed to select Front Plane")
        return None

    # 3. Insert sketch on selected plane
    print("Inserting sketch...")
    sw_sketch_mgr.InsertSketch(True)

    # 4. Draw the profile with notches
    # The profile traces around both centered notches
    #   ##  ##
    #   ##  ##
    #   ##  ##
    #   ######
    #   ######
    #   ######
    #   ######
    #   ######
    #   ######
    #   ######
    #   ######
    #   ######
    #   ##  ##
    #   ##  ##

    print("Drawing sketch profile...")

    # Track current position
    x = 0.0
    z = 0.0

    # Start at origin [0, 0] and draw lines in sequence
    # Note: In XZ plane, Y is always 0

    # Line 1: Right to leftNotchOffset
    seg1 = sw_sketch_mgr.CreateLine(x, 0, z, x + LEFT_NOTCH_OFFSET, 0, z)
    x += LEFT_NOTCH_OFFSET

    # Line 2: Up by bottomNotchHeight
    seg2 = sw_sketch_mgr.CreateLine(x, 0, z, x, 0, z + BOTTOM_NOTCH_HEIGHT)
    z += BOTTOM_NOTCH_HEIGHT

    # Line 3: Right by bottomNotchWidth
    seg3 = sw_sketch_mgr.CreateLine(x, 0, z, x + BOTTOM_NOTCH_WIDTH, 0, z)
    x += BOTTOM_NOTCH_WIDTH

    # Line 4: Down by bottomNotchHeight
    seg4 = sw_sketch_mgr.CreateLine(x, 0, z, x, 0, z - BOTTOM_NOTCH_HEIGHT)
    z -= BOTTOM_NOTCH_HEIGHT

    # Line 5: Right to leftNotchOffset
    seg5 = sw_sketch_mgr.CreateLine(x, 0, z, x + LEFT_NOTCH_OFFSET, 0, z)
    x += LEFT_NOTCH_OFFSET

    # Line 6: Up by barLength
    seg6 = sw_sketch_mgr.CreateLine(x, 0, z, x, 0, z + BAR_LENGTH)
    z += BAR_LENGTH

    # Line 7: Left by rightNotchOffset
    seg7 = sw_sketch_mgr.CreateLine(x, 0, z, x - RIGHT_NOTCH_OFFSET, 0, z)
    x -= RIGHT_NOTCH_OFFSET

    # Line 8: Down by topNotchHeight
    seg8 = sw_sketch_mgr.CreateLine(x, 0, z, x, 0, z - TOP_NOTCH_HEIGHT)
    z -= TOP_NOTCH_HEIGHT

    # Line 9: Left by topNotchWidth
    seg9 = sw_sketch_mgr.CreateLine(x, 0, z, x - TOP_NOTCH_WIDTH, 0, z)
    x -= TOP_NOTCH_WIDTH

    # Line 10: Up by topNotchHeight
    seg10 = sw_sketch_mgr.CreateLine(x, 0, z, x, 0, z + TOP_NOTCH_HEIGHT)
    z += TOP_NOTCH_HEIGHT

    # Line 11: Left by rightNotchOffset
    seg11 = sw_sketch_mgr.CreateLine(x, 0, z, x - RIGHT_NOTCH_OFFSET, 0, z)
    x -= RIGHT_NOTCH_OFFSET

    # Line 12: Close back to origin (down to z=0)
    seg12 = sw_sketch_mgr.CreateLine(x, 0, z, 0, 0, 0)

    # 5. Exit sketch
    print("Exiting sketch...")
    sw_sketch_mgr.InsertSketch(True)

    # 6. Select the sketch for extrusion
    print("Selecting sketch for extrusion...")
    select_result = sw_model_ext.SelectByID2(
        "Sketch1",         # Sketch name
        "SKETCH",          # Selection type
        0, 0, 0,           # X, Y, Z coordinates
        False,             # Append = False
        0,                 # Mark
        None,              # Callout
        0                  # swSelectOptionDefault
    )

    if not select_result:
        print("Error: Failed to select sketch for extrusion")
        return None

    # 7. Extrude the profile by barDepth
    print("Extruding profile...")
    extrude_feature = sw_feat_mgr.FeatureExtrusion3(
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
        False,             # UseAutoSelect: Don't auto-select bodies
        0,                 # T0: swStartSketchPlane (start from sketch plane)
        0.0,               # StartOffset: No offset
        False              # FlipStartOffset: Don't flip
    )

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
