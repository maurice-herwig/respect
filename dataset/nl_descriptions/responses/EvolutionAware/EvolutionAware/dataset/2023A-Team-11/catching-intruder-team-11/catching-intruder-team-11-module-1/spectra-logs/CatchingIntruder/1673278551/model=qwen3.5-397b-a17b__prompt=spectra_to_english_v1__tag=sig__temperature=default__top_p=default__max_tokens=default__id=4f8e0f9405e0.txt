

Specification name: CatchingIntruder

Named domains:
- Dim: Int(0..D)

Environment variables:
- intruderX: Dim
- intruderY: Dim

System variables:
- robotX0: Dim
- robotY0: Dim
- robotX1: Dim
- robotY1: Dim

The system controls the positions of two robots, represented by the variables `robotX0`, `robotY0`, `robotX1`, and `robotY1`. The environment controls the position of an intruder, represented by the variables `intruderX` and `intruderY`. All position variables belong to the domain `Dim`, which consists of integers from 0 to 7.

Initially, the system must place Robot 0 at coordinates (0, 0) and Robot 1 at coordinates (7, 0). The environment places the intruder on the top row of the grid, such that the initial value of `intruderY` is 7.

Regarding movement, the system must ensure that each robot moves only orthogonally or remains stationary. In any step, a robot may change its X coordinate by at most one unit while keeping its Y coordinate constant, change its Y coordinate by at most one unit while keeping its X coordinate constant, or keep both coordinates constant. Diagonal movement is prohibited. The environment is assumed to move the intruder under the same orthogonal movement constraints.

Additionally, the system must guarantee that the two robots never occupy the same grid cell simultaneously.