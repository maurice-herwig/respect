

Specification name: GridL4

Named domains:
- Coord: Int(0..upper)

Environment variables:
- rob: Coord[2]

System variables:
- move: {UP, DOWN, LEFT, RIGHT, STAY}

**System Overview**
The system controls the movement of a robot on a two-dimensional grid. The grid coordinates range from 0 to 8, where the constant `upper` is defined as 8. The environment manages the robot's current position, while the system issues movement commands.

**Initial Condition**
At the start of operation, the robot is positioned at coordinates (0, 0).

**Environment Behavior**
The environment updates the robot's position (`rob`) in response to the system's movement command (`move`). The coordinates are constrained within the range [0, 8]. The position updates according to the following rules:
- **UP:** The second coordinate (`rob[1]`) decreases by 1, unless it is already 0, in which case it remains 0. The first coordinate (`rob[0]`) remains unchanged.
- **DOWN:** The second coordinate (`rob[1]`) increases by 1, unless it is already 8, in which case it remains 8. The first coordinate (`rob[0]`) remains unchanged.
- **LEFT:** The first coordinate (`rob[0]`) decreases by 1, unless it is already 0, in which case it remains 0. The second coordinate (`rob[1]`) remains unchanged.
- **RIGHT:** The first coordinate (`rob[0]`) increases by 1, unless it is already 8, in which case it remains 8. The second coordinate (`rob[1]`) remains unchanged.

**System Requirements**
The system must satisfy the following guarantees regarding the robot's position:
1.  **Safety Constraint:** The robot must not remain away from the starting position (0, 0) for 20 consecutive steps. Within any sequence of 20 steps, the robot must be at position (0, 0) at least once.
2.  **Liveness Requirement 1:** The robot must visit the position (0, 8) infinitely often.
3.  **Liveness Requirement 2:** The robot must visit the position (8, 0) infinitely often.