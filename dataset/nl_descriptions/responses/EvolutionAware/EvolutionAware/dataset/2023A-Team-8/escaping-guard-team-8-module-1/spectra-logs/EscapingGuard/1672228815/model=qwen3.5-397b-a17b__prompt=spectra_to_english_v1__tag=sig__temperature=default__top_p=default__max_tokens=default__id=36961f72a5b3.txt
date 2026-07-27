

Specification name: EscapingGuard

Named domains:
- Dim: Int(0..D)

Environment variables:
- none

System variables:
- robotX: Dim
- robotY: Dim

The system controls the movement of a robot on a two-dimensional grid where both coordinates, `robotX` and `robotY`, range from 0 to 7 (where D is 7). The robot starts at the initial position `robotX` = 7 and `robotY` = 0.

The robot's movement is constrained by an internal timing cycle. Every third step, the robot is required to remain stationary at its current coordinates. During the other steps, the robot may either remain stationary or move to an adjacent grid cell, changing each coordinate by at most 1 unit (either -1, 0, or +1), provided the new position remains within the grid boundaries.

There are static obstacles on the grid that the robot must never occupy. Specifically, the robot is forbidden from being at coordinates (2, 2), (2, 3), (2, 4), or (2, 5) at any time.

The system must satisfy two liveness requirements: the robot must visit the position (0, 0) infinitely often, and it must visit the position (0, 7) infinitely often.

Additionally, there is a specific ordering constraint on visiting these target positions. After the robot visits position (0, 0), it is forbidden from visiting position (0, 7) until it has subsequently visited position (7, 7). Once the robot visits (7, 7), this restriction is cleared, allowing it to visit (0, 7) again before the cycle repeats.