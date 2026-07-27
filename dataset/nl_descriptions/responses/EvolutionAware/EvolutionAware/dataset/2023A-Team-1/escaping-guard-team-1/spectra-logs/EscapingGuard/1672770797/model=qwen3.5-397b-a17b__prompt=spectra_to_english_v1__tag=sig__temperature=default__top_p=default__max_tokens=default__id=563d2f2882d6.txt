

Specification name: EscapingGuard

Named domains:
- Dim: Int(0..D)

Environment variables:
- none

System variables:
- robotX: Dim
- robotY: Dim

**Requirements Description**

The system controls the horizontal (`robotX`) and vertical (`robotY`) coordinates of a robot operating within a grid. The domain `Dim` defines the valid range for these coordinates as integers from 0 to 7.

**Initial Condition**
At the start of operation, the robot must be located at position (7, 0).

**Movement Safety**
In every step, the robot's movement is restricted to adjacent cells or staying in place. Specifically, the value of each coordinate in the next state must differ from its current value by at most 1 (i.e., the change must be -1, 0, or 1).

**Obstacle Avoidance**
The robot must avoid specific static obstacle locations. It is never permitted to occupy a position where the horizontal coordinate is 2 and the vertical coordinate is simultaneously 2, 3, 4, or 5.

**Target Visitation**
The robot must visit each of the following three target locations infinitely often during operation:
1. (0, 0)
2. (7, 7)
3. (0, 7)

**Turn-Based Stopping**
The system utilizes an internal turn counter that cycles through values 1, 2, and 3. Whenever this counter equals 3, the robot must remain stationary; both `robotX` and `robotY` must retain their current values in the next state.