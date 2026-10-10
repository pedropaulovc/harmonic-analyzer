"""Pure 40923898 fillister dimensions; isolate each SKU's cache inputs."""

# MSC 40923898 (mfr 1456MSL), 1/4-20 x 3-1/2 slotted fillister, fully
# threaded; MSC lists no head sizes, so the head is ASME B18.6.3's 1/4
# maximum (A 0.414, O 0.237).  The supplied 3-1/2 in length: MHA-VN-031
# (build_vn_post_mount_screw) cuts it to fit, never this row.
FILLISTER_SIZE = (6.35, 3.5 * 25.4, 0.237 * 25.4, 0.414 * 25.4, 25.4 / 20.0)
