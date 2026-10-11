"""Pure 91794A112 fillister dimensions; isolate each SKU's cache inputs."""

# 18-8 stainless fillister, the same 0.183 x 0.107 #4-40 head (McMaster
# 91794A product table, read 2026-09-25).
FILLISTER_SIZE = (2.8448, 15.875, 2.7178, 4.6482, 0.635)

THREAD = "#4-40"
SKU = "91794A112"
SHANK_DIA, SHANK_LEN, HEAD_H, HEAD_DIA, _PITCH = FILLISTER_SIZE
