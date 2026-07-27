

Specification name: EscapingGuard

Named domains:
- Dim: Int(0..D)

Environment variables:
- guardX: Dim
- guardY: Dim

System variables:
- robotX: Dim
- robotY: Dim

**Requirements Description**

This specification defines a reactive system where a robot navigates a grid while avoiding a moving guard. The grid coordinates are integers ranging from 0 to D, where D is 7.

**Variables and Control**
The system controls the robot's horizontal and vertical position, represented by `robotX` and `robotY`. The environment controls the guard's position, represented by `guardX` and `guardY`, which denote the top-left corner of the guard's occupied area.

**Timing Mechanism**
The system maintains an internal cycle counter, `turnNum`, which ranges from 0 to 2. This counter initializes to 0 and increments by 1 at each step, cycling continuously through the sequence 0, 1, 2, 0, and so on. This counter divides time into three-phase cycles.

**Environment Assumptions**
The environment is assumed to behave according to the following rules regarding the guard:
1.  **Initial Position:** The guard starts at coordinates (0, 0).
2.  **Occupied Area:** The guard occupies a 2x2 area consisting of the cells `(guardX, guardY)`, `(guardX+1, guardY)`, `(guardX, guardY+1)`, and `(guardX+1, guardY+1)`.
3.  **Movement Constraints:**
    *   At every step, the guard's X and Y coordinates may change by at most 1 unit (including staying in place).
    *   During `turnNum` 0 and 1, the guard must remain stationary (both coordinates remain unchanged).
    *   During `turnNum` 2, the guard may move, subject to specific directional constraints based on the robot's position:
        *   If the robot's X coordinate is greater than `guardX + 1`, the guard's X coordinate must increase by 1.
        *   If the robot's Y coordinate is greater than `guardY + 1`, the guard's Y coordinate must increase by 1.
        *   If the robot's X coordinate is less than `guardX`, the guard's X coordinate must decrease by 1.
        *   If the robot's Y coordinate is less than `guardY`, the guard's Y coordinate must decrease by 1.

**System Guarantees**
The system must ensure the following safety requirement at all times:
*   **Collision Avoidance:** The robot must never occupy any of the four cells covered by the guard's 2x2 area. Specifically, the robot's position `(robotX, robotY)` must not equal `(guardX, guardY)`, `(guardX+1, guardY)`, `(guardX, guardY+1)`, or `(guardX+1, guardY+1)`.