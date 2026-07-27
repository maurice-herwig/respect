

Specification name: c

Named domains:
- Color: {RED, GREEN, BLUE, EMPTY, NOT}

Environment variables:
- color0: Color
- color1: Color
- color2: Color

System variables:
- a: Int(0..2)
- b: Int(0..2)

This specification describes a reactive system that interacts with an environment managing three color values. The system selects two distinct indices to monitor specific environment colors.

**Environment Assumptions**
The environment controls the variables `color0`, `color1`, and `color2`. The specification assumes that the environment maintains stability for the colors at the indices currently selected by the system. Specifically, in every transition, the environment must ensure that the next value of the color variable corresponding to the system's current index `a` remains equal to its current value. Similarly, the next value of the color variable corresponding to the system's current index `b` must remain equal to its current value.

**System Guarantees**
The system controls the variables `a` and `b`, which serve as indices into the environment's color variables. The system must satisfy the following requirements:

1.  **Distinct Indices:** The system must ensure that `a` and `b` are always distinct. This constraint holds in the initial state and must be preserved in all subsequent states.
2.  **Color Tracking:** The system utilizes auxiliary variables `aColor` and `bColor` to track the environment state. The system guarantees that `aColor` always equals the current value of the environment color variable selected by `a` (e.g., if `a` is 0, `aColor` equals `color0`). Likewise, `bColor` always equals the current value of the environment color variable selected by `b`.