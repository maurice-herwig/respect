

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

The system controls the positions of two robots, Robot 0 and Robot 1, on a two-dimensional grid. The horizontal and vertical coordinates for each robot are represented by the system variables `robotX0`, `robotY0`, `robotX1`, and `robotY1`. These coordinates are integers ranging from 0 to 7.

Initially, Robot 0 is located at the top-left corner with coordinates (0, 0), and Robot 1 is located at the top-right corner with coordinates (7, 0).

At every step of the system operation, both robots must adhere to specific movement constraints. From one state to the next, each robot may either remain in its current cell or move to an immediately adjacent cell horizontally or vertically. Diagonal movements are not permitted.

Additionally, the system must ensure that neither robot enters a region containing static obstacles. Specifically, if a robot's vertical coordinate is 1, its horizontal coordinate must not be 2, 3, 4, or 5. This safety constraint regarding obstacle avoidance must hold at all times for both robots.