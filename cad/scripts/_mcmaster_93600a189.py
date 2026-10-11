"""Pure 93600A189 dowel dimensions; isolate this SKU's cache inputs."""

__all__ = ["DOWEL_SIZE", "ENDS"]

# part:        (nominal dia, length), mm. 316 stainless nominal reference only;
# its m6/incoming limits live in vn_transgear_arm_plate_locating_pin_spec.
DOWEL_SIZE = (2.0, 6.0)
# The supplier gives chamfered ends but no dimensions: a plain cylinder.
ENDS = None
