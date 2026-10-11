"""Pure 98296A027 spring-pin dimensions; isolate this SKU's cache inputs."""

from _spring_pin_dimensions import MM_PER_IN, WALL_T

__all__ = ["MM_PER_IN", "SPRING_PIN_SIZE", "WALL_T"]

# part:        (nominal dia, length), mm
SPRING_PIN_SIZE = (MM_PER_IN / 16.0, MM_PER_IN / 2.0)  # 1/16 x 1/2
