

Specification name: EscapingGuard

Named domains:
- Dim: Int(0..D)

Environment variables:
- none

System variables:
- robotX: Dim
- robotY: Dim

The system controls the robot's horizontal and vertical coordinates, `robotX` and `robotY`, respectively. Both variables are integers ranging from 0 to 7. The system must satisfy a safety guarantee that applies at all times, including the initial state. Specifically, the robot must never be located at position (2, 6) and must never be located at position (3, 6). The system guarantees hold unconditionally without environmental assumptions.