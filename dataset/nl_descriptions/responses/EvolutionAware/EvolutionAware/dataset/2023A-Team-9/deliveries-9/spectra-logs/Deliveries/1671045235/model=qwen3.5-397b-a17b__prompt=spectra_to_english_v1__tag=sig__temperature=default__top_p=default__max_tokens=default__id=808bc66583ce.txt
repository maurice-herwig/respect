

Specification name: Deliveries

Named domains:
- DimX: Int(0..DX)
- DimY: Int(0..DY)
- Coord: Int(0..DY)

Environment variables:
- lamp0X: DimX
- lamp0Y: DimY
- lamp1X: DimX
- lamp1Y: DimY
- elevator: DimY

System variables:
- robotX0: DimX
- robotY0: DimY
- robotX1: DimX
- robotY1: DimY

**Requirements Description**

The system controls the positions of two robots (Robot 0 and Robot 1) on a grid, while the environment controls the position of an elevator and two lamps. The grid dimensions are bounded by DX in the X direction and DY in the Y direction.

**Environment Assumptions**
The environment manages the `elevator` variable, representing its vertical position. The elevator moves along the Y-axis such that its position changes by at most one unit per step; it may move up, move down, or remain stationary. Additionally, the environment ensures that the elevator infinitely often reaches the bottom position (0) and infinitely often reaches the top position (DY).

**System Guarantees**
The system must ensure the following behaviors for both Robot 0 and Robot 1:

1.  **Step Size Constraint:** In every step, each robot's X-coordinate and Y-coordinate must change by at most one unit.
2.  **Vertical Movement Restriction:** A robot is prohibited from changing its Y-coordinate unless its X-coordinate is 0. If a robot is located at any X-coordinate other than 0, its Y-coordinate must remain identical in the next state.
3.  **Elevator Synchronization:** When a robot's X-coordinate is 0, its Y-coordinate must exactly match the current Y-coordinate of the `elevator`. This constrains the robots to share the elevator's vertical position whenever they are aligned at X=0.