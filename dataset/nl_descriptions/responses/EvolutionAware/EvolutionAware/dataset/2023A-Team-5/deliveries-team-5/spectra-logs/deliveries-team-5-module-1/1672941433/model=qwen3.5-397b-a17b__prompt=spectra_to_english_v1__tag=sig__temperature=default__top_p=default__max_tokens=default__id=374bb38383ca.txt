

Specification name: Module1

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

The system controls the positions of two robots, Robot 0 and Robot 1, on a grid defined by the dimensions DimX and DimY. Each robot's position is determined by an X-coordinate (robotX0, robotX1) and a Y-coordinate (robotY0, robotY1).

**Initial Conditions**
At the start of operation, both Robot 0 and Robot 1 must have their Y-coordinates set to DY.

**Movement Constraints**
The system must ensure the following movement rules for both robots at every step:
1.  **X-Axis Movement:** The X-coordinate of each robot may change by at most 1 unit per step (increase by 1, decrease by 1, or remain unchanged).
2.  **Axis Alignment:** A robot cannot move diagonally. At each step, a robot must either keep its X-coordinate constant or keep its Y-coordinate constant.
3.  **Y-Axis Restriction:** A robot is only permitted to change its Y-coordinate if its X-coordinate is 0. If a robot's X-coordinate is not 0, its Y-coordinate must remain unchanged.

**Safety Requirements**
The system must prevent collisions and invalid swapping between the two robots:
1.  **Collision Avoidance:** The two robots must never occupy the same grid position simultaneously (i.e., they cannot have both the same X-coordinate and the same Y-coordinate).
2.  **Swap Prevention:** If both robots are on the same Y-coordinate line, they cannot swap X-positions in a single step. Specifically, Robot 0 cannot move to Robot 1's current X-coordinate while Robot 1 moves to Robot 0's current X-coordinate.