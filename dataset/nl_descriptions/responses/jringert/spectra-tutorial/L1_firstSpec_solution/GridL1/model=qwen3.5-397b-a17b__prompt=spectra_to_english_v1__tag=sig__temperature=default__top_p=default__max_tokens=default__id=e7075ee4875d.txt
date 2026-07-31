

Specification name: GridL1

Environment variables:
- robX: Int(0..4)
- robY: Int(0..4)

System variables:
- move: {UP, DOWN, LEFT, RIGHT, STAY}

The system manages a robot operating on a grid where coordinates range from 0 to 4. The environment controls the position variables `robX` and `robY`, while the system controls the `move` command.

Initially, the robot is positioned at `robX`=0 and `robY`=0.

Regarding position updates, the environment ensures that whenever the system commands `UP`, the `robY` coordinate decreases by 1 in the next state.

The system must guarantee that it never commands a move that violates the grid boundaries. The following safety constraints must always hold:
- If `robX` is 0, the `move` command must not be `LEFT`.
- If `robX` is 4, the `move` command must not be `RIGHT`.
- If `robY` is 0, the `move` command must not be `UP`.
- If `robY` is 4, the `move` command must not be `DOWN`.