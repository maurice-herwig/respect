

Specification name: EscapingGuard

Named domains:
- Dim: Int(0..D)

Environment variables:
- none

System variables:
- robotX: Dim
- robotY: Dim

The system controls the position of a robot on a two-dimensional grid. The horizontal coordinate is represented by `robotX` and the vertical coordinate by `robotY`. Both coordinates are integers ranging from 0 to 7.

The system maintains an internal cycle counter that starts at 0 and increments by 1 at each step, repeating the sequence 0, 1, 2 indefinitely.

The system guarantees the following behavior regarding position updates:
1. In every step, the value of `robotX` may change by at most 1; it may increase by 1, decrease by 1, or remain unchanged.
2. In every step, the value of `robotY` may change by at most 1; it may increase by 1, decrease by 1, or remain unchanged.
3. Whenever the internal cycle counter is at 2, the robot must remain stationary. In this case, both `robotX` and `robotY` must retain exactly the same values in the next step as they held in the current step.