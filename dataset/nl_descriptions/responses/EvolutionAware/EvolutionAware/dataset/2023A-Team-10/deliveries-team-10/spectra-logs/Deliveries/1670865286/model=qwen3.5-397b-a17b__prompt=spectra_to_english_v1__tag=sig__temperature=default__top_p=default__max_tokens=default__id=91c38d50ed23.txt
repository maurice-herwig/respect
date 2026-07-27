

Specification name: Deliveries

Named domains:
- DimX: Int(0..DX)
- DimY: Int(0..DY)
- Coord: Int(0..DY)

Environment variables:
- elevatorY: DimY

System variables:
- robotX0: DimX
- robotY0: DimY
- robotX1: DimX
- robotY1: DimY

The system controls the positions of two robots, Robot 0 and Robot 1, within a grid where the horizontal dimension ranges from 0 to DX and the vertical dimension ranges from 0 to DY (both DX and DY are defined as 5). The environment controls the vertical position of an elevator via `elevatorY`, while the elevator's horizontal position is fixed at 0.

Initially, both robots start at vertical position 0 (`robotY0 = 0` and `robotY1 = 0`).

The system must satisfy the following guarantees:

1.  **Collision Avoidance:** The two robots must never collide. It is always required that `robotX0` and `robotY0` are not simultaneously equal to `robotX1` and `robotY1`, respectively.
2.  **Horizontal Movement:** The horizontal positions `robotX0` and `robotX1` are constrained in each step. The next value of each horizontal coordinate must be either the current value, the current value plus 1, or the current value minus 1.
3.  **Elevator Alignment:** Whenever a robot's horizontal position equals 0 (the elevator's horizontal position), its vertical position must match the environment's `elevatorY`. Specifically, if `robotX0` is 0, then `robotY0` must equal `elevatorY`. Similarly, if `robotX1` is 0, then `robotY1` must equal `elevatorY`.