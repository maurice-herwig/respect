

Specification name: EscapingGuard

Named domains:
- Dim: Int(0..D)

Environment variables:
- none

System variables:
- robotX: Dim
- robotY: Dim

The system controls the position of a robot on a two-dimensional grid using the variables `robotX` and `robotY`. Both coordinates are integers ranging from 0 to 7. The system must ensure that the robot never collides with fixed obstacles. Specifically, at all times, the robot is prohibited from occupying any position where the `robotX` coordinate is 2 and the `robotY` coordinate is 2, 3, 4, or 5.