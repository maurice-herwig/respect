

Specification name: Robot_movement

Named domains:
- DimX: Int(0..DX)
- DimY: Int(0..DY)
- Coord: Int(0..DY)

Environment variables:
- none

System variables:
- robotX0: DimX
- robotY0: DimY
- robotX1: DimX
- robotY1: DimY

The system controls the movement of two robots, Robot 0 and Robot 1, within a grid defined by the specified domains. All variables are controlled by the system; there are no environment-controlled inputs.

Initially, both Robot 0 and Robot 1 must start with their Y-coordinates (`robotY0` and `robotY1`) set to 0.

Regarding movement safety, the X-coordinate of each robot (`robotX0` and `robotX1`) may change by at most 1 in any single step. This means each robot can move left by 1, stay in place, or move right by 1 along the X-axis.

Movement along the Y-axis is restricted based on the X-position. For each robot, if its X-coordinate is not 0, its Y-coordinate must remain unchanged in the next step. Consequently, a robot may only change its Y-coordinate when its X-coordinate is 0.

To prevent collisions, the two robots must never occupy the same position simultaneously; they cannot have identical X and Y coordinates at any time. Additionally, if both robots are on the same Y-coordinate, they are prohibited from swapping X-coordinates in the next step. Specifically, if `robotY0` equals `robotY1`, it must not be the case that `robotX0` moves to the current position of `robotX1` while `robotX1` moves to the current position of `robotX0`.