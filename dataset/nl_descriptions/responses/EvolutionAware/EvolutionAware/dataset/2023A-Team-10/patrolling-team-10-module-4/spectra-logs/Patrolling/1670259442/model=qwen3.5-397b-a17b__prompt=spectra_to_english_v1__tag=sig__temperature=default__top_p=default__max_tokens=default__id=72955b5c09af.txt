

Specification name: Patrolling

Named domains:
- DimX: Int(0..DX)
- DimY: Int(0..DY)
- Dim: Int(0..4)

Environment variables:
- movingObstacleX: DimX
- movingObstacleY: DimY
- lowBattery: boolean

System variables:
- robot: Dim[2]

**Requirements Description**

This specification defines the behavior of a robot patrolling a grid environment while avoiding obstacles and managing battery levels. The system controls the robot's position, while the environment controls the position of a moving obstacle and the battery status signal.

**Environment Assumptions**
The environment adheres to the following constraint:
*   The Y-coordinate of the moving obstacle is always 2.

**System Guarantees**
The system must satisfy the following requirements:

*   **Collision Avoidance (Safety):** The robot must never occupy the same position as the moving obstacle. Additionally, the robot must never occupy any of the following static obstacle positions: (1,1), (3,3), (2,1), (0,3), or (3,4).
*   **Movement Constraints (Next-State):** In every step, the robot's X and Y coordinates must each either remain unchanged, increase by 1, or decrease by 1.
*   **Charging Response (Liveness):** Whenever the `lowBattery` signal becomes true, the robot must eventually reach the charging station located at position (4,0).