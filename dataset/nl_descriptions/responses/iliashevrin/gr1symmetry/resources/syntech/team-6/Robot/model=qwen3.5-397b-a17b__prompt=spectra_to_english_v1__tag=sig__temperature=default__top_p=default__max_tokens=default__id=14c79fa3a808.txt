

Specification name: Robot

Named domains:
- DimX: Int(0..DX)
- DimY: Int(0..DY)

Environment variables:
- none

System variables:
- robotX: DimX
- robotY: DimY
- move: {UP, DOWN, LEFT, RIGHT, STAY}

**Requirements Description**

The Robot system controls the position and movement of a robot on a two-dimensional grid. The system determines the horizontal coordinate (`robotX`), the vertical coordinate (`robotY`), and the movement command (`move`) at all times. The grid dimensions are defined from 0 to 7 for both coordinates.

**Initial State**
Initially, the robot starts at the position where `robotX` is 0 and `robotY` is 0.

**Movement Dynamics**
The system updates the robot's coordinates based on the selected movement command according to the following rules:
- If `move` is UP, `robotY` decreases by 1 and `robotX` remains unchanged.
- If `move` is DOWN, `robotY` increases by 1 and `robotX` remains unchanged.
- If `move` is LEFT, `robotX` decreases by 1 and `robotY` remains unchanged.
- If `move` is RIGHT, `robotX` increases by 1 and `robotY` remains unchanged.
- If `move` is STAY, both `robotX` and `robotY` remain unchanged.

**Safety Constraints**
The system must ensure the robot remains within the grid boundaries and avoids specific obstacles.

*Boundary Constraints:*
- The robot cannot move LEFT when `robotX` is 0.
- The robot cannot move RIGHT when `robotX` is 7.
- The robot cannot move UP when `robotY` is 0.
- The robot cannot move DOWN when `robotY` is 7.

*Obstacle Avoidance:*
- When `robotX` is 1 and `robotY` is less than 7, the robot cannot move RIGHT.
- When `robotX` is 2 and `robotY` is 7, the robot cannot move UP.
- When `robotX` is 3 and `robotY` is less than 7, the robot cannot move LEFT.
- When `robotX` is 4 and `robotY` is greater than 0, the robot cannot move RIGHT.
- When `robotX` is 6 and `robotY` is greater than 0, the robot cannot move LEFT.
- When `robotX` is 5 and `robotY` is 0, the robot cannot move DOWN.

**Goal and Termination**
The system must ensure that the robot reaches the goal position (`robotX` = 7 and `robotY` = 7) infinitely often. Once the robot reaches the goal position, the subsequent movement command must be STAY.