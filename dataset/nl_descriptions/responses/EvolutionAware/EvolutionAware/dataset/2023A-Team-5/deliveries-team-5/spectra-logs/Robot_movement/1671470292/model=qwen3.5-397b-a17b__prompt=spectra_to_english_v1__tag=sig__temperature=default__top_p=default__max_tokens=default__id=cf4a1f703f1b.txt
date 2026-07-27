

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

**Requirements Description**

The system controls the movement of two robots, Robot 0 and Robot 1, on a two-dimensional grid. The grid dimensions are defined such that X and Y coordinates range from 0 to 5. The system determines the position of both robots at every step.

**Initial Conditions**
- Initially, the Y coordinate for both Robot 0 and Robot 1 is 0.

**Safety and Movement Constraints**
- **X-Axis Movement:** In each step, the X coordinate for each robot must change by at most 1. The next X coordinate must be within the range of [current X - 1, current X + 1].
- **Y-Axis Movement:** The Y coordinate for a robot must remain unchanged in the next step if the robot's current X coordinate is not 0.
- **Continuous Movement:** In every step, each robot must change either its X coordinate or its Y coordinate (or both). A robot cannot remain stationary.
- **Collision Avoidance:** At all times, Robot 0 and Robot 1 must not occupy the same position. Their X coordinates or Y coordinates must differ.
- **Position Switching:** If both robots are on the same Y row (same Y coordinate), they cannot swap X positions in a single step. For example, if Robot 0 is at X=a and Robot 1 is at X=b, they cannot transition to Robot 0 at X=b and Robot 1 at X=a simultaneously.