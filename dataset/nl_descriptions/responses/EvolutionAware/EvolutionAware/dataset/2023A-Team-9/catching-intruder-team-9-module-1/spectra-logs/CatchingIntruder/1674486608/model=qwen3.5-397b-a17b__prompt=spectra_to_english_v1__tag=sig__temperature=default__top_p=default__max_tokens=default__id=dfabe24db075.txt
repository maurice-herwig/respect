

Specification name: CatchingIntruder

Named domains:
- Dim: Int(0..D)

Environment variables:
- none

System variables:
- robotX0: Dim
- robotY0: Dim
- robotX1: Dim
- robotY1: Dim

**Requirements Description**

The system controls the movement of two robots, Robot 0 and Robot 1, on a two-dimensional grid. The grid coordinates for both the X and Y axes range from 0 to 7. The system determines the position of both robots at all times.

**Initial Conditions**
At the start of operation, Robot 0 is positioned at coordinates (0, 0). Robot 1 is positioned at coordinates (7, 0).

**Movement Rules**
In each step, each robot must adhere to the following movement constraints:
1.  **Axis-Aligned Movement:** A robot may change its X-coordinate while keeping its Y-coordinate constant, or change its Y-coordinate while keeping its X-coordinate constant. Diagonal movement (changing both coordinates simultaneously) is not permitted.
2.  **Step Size:** When a coordinate changes, it may increase by 1, decrease by 1, or remain unchanged.
3.  **Stationary Option:** A robot may choose to remain stationary (neither coordinate changes).

**Safety Requirements**
1.  **Collision Avoidance:** The two robots must never occupy the same position at the same time. That is, it is never allowed for Robot 0's X and Y coordinates to simultaneously equal Robot 1's X and Y coordinates.
2.  **Forbidden Zones:** Both robots are prohibited from entering specific positions on the grid. Neither Robot 0 nor Robot 1 may ever occupy any position where the Y-coordinate is 1 and the X-coordinate is 2, 3, 4, or 5.

**Conditional Behavior**
Robot 1 is restricted from moving until Robot 0 reaches a specific target location. Specifically, Robot 1 must remain stationary (both X and Y coordinates must remain unchanged) until Robot 0 reaches the position (0, 7). Once Robot 0 has reached (0, 7), Robot 1 is permitted to move according to the standard movement rules described above.