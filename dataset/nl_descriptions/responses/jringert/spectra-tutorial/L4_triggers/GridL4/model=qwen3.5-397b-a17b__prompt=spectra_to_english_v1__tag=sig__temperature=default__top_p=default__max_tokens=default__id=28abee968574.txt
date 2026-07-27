

Specification name: GridL4

Named domains:
- Coord: Int(0..upper)

Environment variables:
- rob: Coord[2]

System variables:
- move: {UP, DOWN, LEFT, RIGHT, STAY}

**Requirements Description**

The system controls the movement of a robot on a grid where coordinates range from 0 to 8 (defined as `upper`). The environment maintains the robot's current position in the variable `rob`, which consists of two coordinates, while the system controls the movement command in the variable `move`.

**Initial Condition**
At the start of operation, the robot's position is initialized to (0, 0), meaning both the first and second coordinates of `rob` are 0.

**Environment Behavior**
The environment is assumed to update the robot's position in response to the system's movement commands according to the following rules:
- If the system commands **UP**, the second coordinate of `rob` decreases by 1 unless it is already 0, in which case it remains 0. The first coordinate remains unchanged.
- If the system commands **DOWN**, the second coordinate of `rob` increases by 1 unless it is already 8, in which case it remains 8. The first coordinate remains unchanged.
- If the system commands **LEFT**, the first coordinate of `rob` decreases by 1 unless it is already 0, in which case it remains 0. The second coordinate remains unchanged.
- If the system commands **RIGHT**, the first coordinate of `rob` increases by 1 unless it is already 8, in which case it remains 8. The second coordinate remains unchanged.

**System Guarantees**
The system must issue movement commands such that the following liveness requirements are satisfied infinitely often:
- The robot must reach the position (0, 8), where the first coordinate is 0 and the second coordinate is 8.
- The robot must reach the position (8, 0), where the first coordinate is 8 and the second coordinate is 0.