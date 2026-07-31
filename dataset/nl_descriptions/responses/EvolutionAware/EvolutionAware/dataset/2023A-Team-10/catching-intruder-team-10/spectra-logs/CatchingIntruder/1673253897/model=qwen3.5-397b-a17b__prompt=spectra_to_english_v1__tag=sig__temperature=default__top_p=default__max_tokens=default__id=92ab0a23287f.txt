

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

The system controls the movement of two robots, Robot 0 and Robot 1, on a grid where coordinates range from 0 to 7. All position variables are controlled by the system.

**Initial Conditions**
At the start of operation, Robot 0 is positioned at coordinates (0, 0), and Robot 1 is positioned at coordinates (7, 0).

**Safety Requirements**
The system must ensure the following conditions hold at all times:
1.  **Obstacle Avoidance:** Neither robot may occupy obstacle locations. The forbidden coordinates are (2, 1), (3, 1), (4, 1), and (5, 1).
2.  **Collision Avoidance:** Robot 0 and Robot 1 must never occupy the same grid cell simultaneously.
3.  **Robot 0 Movement:** At every step, Robot 0 must move exactly one unit in either the X or Y direction. It cannot remain stationary, and it cannot move diagonally (changing both coordinates simultaneously).
4.  **Robot 1 Movement:** Robot 1 is prohibited from moving diagonally. At every step, at least one of its coordinates (X or Y) must remain unchanged from the previous step.

**Liveness and Conditional Requirements**
1.  **Goal Reachability:** Whenever Robot 1 makes a valid move (changing exactly one coordinate by one unit), the system must ensure that Robot 0 eventually reaches the target position (0, 7).