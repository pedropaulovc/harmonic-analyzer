"""Pure 92240A539 hex-screw dimensions; isolate this SKU's cache inputs."""

# Catalog dimensions, millimetres.  Keep the diameter as a public constant;
# the radius is derived so the catalog law has one source of truth.
MAJOR_DIAMETER_MM = 6.35
LENGTH_MM = 15.875
HEX_WIDTH_MM = 11.1125
HEX_HEIGHT_MM = 3.96875
PITCH_MM = 1.27
WASHER_DEPTH_MM = HEX_WIDTH_MM * 0.025

# Vendor axial placement, expressed in the adapter's model-Y build frame.
UNDERSIDE_MM = 0.0
HEAD_TOP_MM = UNDERSIDE_MM + HEX_HEIGHT_MM

HEX_SCREW_SIZE = (
    MAJOR_DIAMETER_MM,
    LENGTH_MM,
    HEX_WIDTH_MM,
    HEX_HEIGHT_MM,
    PITCH_MM,
    WASHER_DEPTH_MM,
    UNDERSIDE_MM,
)
