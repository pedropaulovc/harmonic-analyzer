"""Pure 90280A203 fillister dimensions; isolate each SKU's cache inputs."""

# Live product page read 2026-10-08: #8-32 x 1-1/2, ASME B18.6.3, fully
# threaded zinc-plated steel, flat tip; length measured under the head.
SHANK_DIA = 4.1656
SHANK_LEN = 38.1
HEAD_DIA = 6.858
HEAD_H = 3.9624
PITCH = 0.79375

# part:        (major dia, length, head height, head dia, pitch)
FILLISTER_SIZE = (SHANK_DIA, SHANK_LEN, HEAD_H, HEAD_DIA, PITCH)
