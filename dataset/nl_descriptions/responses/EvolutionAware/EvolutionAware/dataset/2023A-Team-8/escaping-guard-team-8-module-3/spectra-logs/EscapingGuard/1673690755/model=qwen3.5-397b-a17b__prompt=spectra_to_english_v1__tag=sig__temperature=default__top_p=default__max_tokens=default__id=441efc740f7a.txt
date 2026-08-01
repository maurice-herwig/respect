

Specification name: EscapingGuard

Named domains:
- Dim: Int(0..D)

Environment variables:
- none

System variables:
- robotX: Dim
- robotY: Dim

The EscapingGuard specification defines the control logic for a robot moving on a two-dimensional grid. The robot's position is determined by the coordinates robotX and robotY, which are integers ranging from 0 to 7. Initially, the robot is placed at the position where robotX is 7 and robotY is 0.

The robot's movement is governed by a cyclic timing constraint. During every third step of the system operation, the robot is required to remain stationary, meaning both robotX and robotY must retain their current values. During the other steps, the robot may update its position such that each coordinate changes by at most one unit (incrementing by 1, decrementing by 1, or remaining unchanged), provided the new coordinates remain within the valid range of 0 to 7.

Additionally, the robot must avoid specific static obstacles. The robot is strictly prohibited from occupying the grid position (6, 2) or the grid position (6, 3) at any time.