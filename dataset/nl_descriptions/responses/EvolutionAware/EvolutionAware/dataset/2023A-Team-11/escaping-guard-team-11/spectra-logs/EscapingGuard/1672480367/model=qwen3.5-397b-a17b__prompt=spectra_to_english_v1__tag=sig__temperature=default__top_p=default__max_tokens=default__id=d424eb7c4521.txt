

Specification name: EscapingGuard

Named domains:
- Dim: Int(0..D)

Environment variables:
- guardLeftCornerX: Dim
- guardLeftCornerY: Dim

System variables:
- robotX: Dim
- robotY: Dim

This specification describes a reactive system controlling a robot moving on a two-dimensional grid. The grid coordinates are integers ranging from 0 to 7, inclusive, where the constant D is defined as 7. This range is represented by the domain `Dim`.

The system controls the robot's horizontal position `robotX` and vertical position `robotY`. The environment controls the guard's position through inputs `guardLeftCornerX` and `guardLeftCornerY`.

Regarding initial conditions, the robot starts at coordinates (7, 0). The environment assumes the guard starts at coordinates (0, 0).

Regarding safety requirements, the system must ensure constrained movement for the robot at every step. For both the `robotX` and `robotY` variables, the value at the next step must be equal to the current value, exactly one greater than the current value, or exactly one less than the current value. This ensures the robot moves at most one unit per step in each dimension.

Regarding liveness requirements, the system guarantees that the robot infinitely often visits three specific target locations during operation. These targets are fixed at coordinates (0, 0), (0, 7), and (7, 7). The robot must return to each of these locations repeatedly throughout the system's execution.