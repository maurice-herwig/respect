

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

The system controls the positions of two robots, Robot 0 and Robot 1, on a two-dimensional grid. The grid coordinates for both the X and Y axes are integers ranging from 0 to 7 inclusive.

Initially, Robot 0 is positioned at coordinates (0, 0), and Robot 1 is positioned at coordinates (7, 0).

In each step, each robot must update its position according to the following movement rules: the robot must either remain stationary or change exactly one coordinate (either X or Y) by at most 1 unit. Simultaneous changes to both X and Y coordinates are not permitted.

The system must ensure that Robot 0 and Robot 1 never occupy the same grid position simultaneously.

Additionally, there are forbidden zones on the grid. Neither Robot 0 nor Robot 1 is allowed to occupy any position where the Y coordinate is 1 and the X coordinate is 2, 3, 4, or 5.

Finally, there is a sequencing constraint on movement. Robot 1 must remain stationary until Robot 0 reaches the position (0, 7). Once Robot 0 has reached (0, 7) at least once, Robot 1 is permitted to move according to the general movement rules.