

Specification name: GridL2

Named domains:
- Coord: Int(0..20)
- Move: {UP, DOWN, LEFT, RIGHT, STAY}

Environment variables:
- rob: Coord[2]

System variables:
- moveRob: Move
- moveDrone: Move

The system controls the movement commands for a robot and a drone operating on a grid, while the environment controls the robot's coordinates. The robot's position is represented by the coordinate pair `rob`, where `rob[0]` and `rob[1]` are integers. The movement commands `moveRob` and `moveDrone` are selected from the set of directions {UP, DOWN, LEFT, RIGHT, STAY}.

Initially, the robot's coordinates `rob[0]` and `rob[1]` are both 0.

Regarding the environment behavior, it is assumed that whenever the system commands the robot to move `UP`, the environment updates the robot's second coordinate `rob[1]` to decrease by 1 in the next state.

The system must satisfy the following guarantees:
1.  **Move Inversion:** The robot's move command `moveRob` and the drone's move command `moveDrone` must always be inverse directions. Specifically, one must be `UP` while the other is `DOWN`, or one must be `LEFT` while the other is `RIGHT`.
2.  **Boundary Constraints:** The system must not command the robot to move beyond specific boundaries. `moveRob` cannot be `LEFT` if `rob[0]` is 0, cannot be `RIGHT` if `rob[0]` is 4, cannot be `UP` if `rob[1]` is 0, and cannot be `DOWN` if `rob[1]` is 4.
3.  **Stay Condition:** If the system commands the robot to `STAY`, the robot's coordinates `rob[0]` and `rob[1]` must remain unchanged in the next state.