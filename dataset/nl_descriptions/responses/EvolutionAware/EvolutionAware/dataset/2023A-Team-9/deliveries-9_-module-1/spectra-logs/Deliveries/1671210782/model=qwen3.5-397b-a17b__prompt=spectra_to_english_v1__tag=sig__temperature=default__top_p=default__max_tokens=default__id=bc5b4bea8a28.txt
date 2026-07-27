

Specification name: Deliveries

Named domains:
- DimX: Int(0..DX)
- DimY: Int(0..DY)
- Coord: Int(0..DY)

Environment variables:
- elevator: DimY

System variables:
- robotX0: DimX
- robotY0: DimY
- robotX1: DimX
- robotY1: DimY

The system controls the coordinates of two robots, robot0 and robot1, on a grid where the maximum X dimension (DX) and Y dimension (DY) are both 5. The environment provides the current Y-coordinate of an elevator.

Initially, both robots start at the Y-coordinate equal to DX (5). The initial X-coordinates for the robots are not constrained by the initial conditions.

During operation, the system must ensure the following safety requirements:

1.  **Movement Limits:** In every step, each robot may change its X-coordinate and Y-coordinate by at most one unit. A robot may also choose to remain stationary in either dimension.
2.  **Vertical Movement Restrictions:** Vertical movement (changes to the Y-coordinate) is permitted only when a robot is located at X-coordinate 0. If a robot is at any X-coordinate other than 0, its Y-coordinate must remain unchanged in the next step.
3.  **Elevator Alignment:** When a robot is located at X-coordinate 0, its Y-coordinate must exactly match the current Y-coordinate of the environment's elevator.
4.  **Collision Avoidance:** The two robots must never occupy the same location simultaneously. At no time may robot0 and robot1 share both the same X-coordinate and the same Y-coordinate.