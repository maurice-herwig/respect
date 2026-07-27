

Specification name: Patrolling

Named domains:
- DimX: Int(0..DX)
- DimY: Int(0..DY)

Environment variables:
- goalsX: DimX[num_targets]
- goalsY: DimY[num_targets]
- movingObstacleX: DimX

System variables:
- robotX: DimX
- robotY: DimY

**Requirements Description**

This specification defines the behavior of a robot patrolling a grid environment. The grid coordinates range from 0 to 4 in both the X and Y dimensions. The system controls the robot's position, while the environment provides target locations and obstacle information.

**Inputs and Outputs**
The environment controls three input variables: the X and Y coordinates for three distinct goals (`goalsX`, `goalsY`), and the X coordinate of a moving obstacle (`movingObstacleX`). The system controls two output variables: the robot's X and Y coordinates (`robotX`, `robotY`). Additionally, the system defines five static obstacles at fixed coordinate pairs known internally.

**Environment Assumptions**
The environment must satisfy the following conditions:
1.  **Static Goals:** The locations of the three goals remain fixed throughout operation; they do not change from one step to the next.
2.  **Valid Goal Placement:** No goal is located at the same coordinates as any of the five static obstacles.

**System Guarantees**
Whenever the environment satisfies its assumptions, the system must satisfy the following guarantees:
1.  **Movement Constraint:** In every step, the robot's X coordinate and Y coordinate must each change by at most one unit (either increasing by one, decreasing by one, or remaining the same).
2.  **Static Obstacle Avoidance:** The robot must never occupy the same location as any of the five static obstacles.
3.  **Goal Visitation:** The robot must visit the location of each of the three goals infinitely often during operation.