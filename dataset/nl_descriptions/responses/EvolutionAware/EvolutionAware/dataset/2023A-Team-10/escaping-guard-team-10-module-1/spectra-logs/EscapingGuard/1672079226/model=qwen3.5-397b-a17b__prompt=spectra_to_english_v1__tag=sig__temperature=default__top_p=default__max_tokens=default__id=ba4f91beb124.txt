

Specification name: EscapingGuard

Named domains:
- Dim: Int(0..D)

Environment variables:
- none

System variables:
- robot: Dim[2]

The system controls the position of a robot on a two-dimensional grid using the variable `robot`, which comprises two coordinates, `robot[0]` and `robot[1]`. Each coordinate is an integer value within the domain 0 to 7.

Initially, the robot is positioned at `robot[0] = 7` and `robot[1] = 0`.

The system must satisfy the following safety requirements at all times:
1. The robot must never occupy any of the following obstacle locations: (2, 2), (2, 3), (2, 4), or (2, 5).
2. For each coordinate (`robot[0]` and `robot[1]`), the value in the next state must either remain the same as the current value, increase by exactly 1, or decrease by exactly 1.

The system must also satisfy the following liveness requirements:
1. The robot must visit the target location (0, 0) infinitely often.
2. The robot must visit the target location (7, 7) infinitely often.
3. The robot must visit the target location (7, 0) infinitely often.