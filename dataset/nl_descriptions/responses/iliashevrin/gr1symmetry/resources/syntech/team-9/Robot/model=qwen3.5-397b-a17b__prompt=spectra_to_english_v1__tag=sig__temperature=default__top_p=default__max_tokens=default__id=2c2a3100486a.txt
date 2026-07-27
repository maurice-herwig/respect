

Specification name: Robot

Named domains:
- DimX: Int(0..DX)
- DimY: Int(0..DY)

Environment variables:
- none

System variables:
- robotX: DimX
- robotY: DimY

The Robot system controls its position on a two-dimensional grid using the system variables robotX and robotY. Both coordinates are integers constrained to the range from 0 to 7.

Initially, the robot starts at the position where robotX is 0 and robotY is 0.

At every step of the system execution, the robot updates its position according to the following transition rules:
- The value of robotX in the next state must be either the current value increased by one, decreased by one, or unchanged.
- The value of robotY in the next state must be either the current value increased by one, decreased by one, or unchanged.

The system must satisfy the following safety constraints regarding specific coordinates:
- Whenever robotX is 2, robotY must be 7.
- Whenever robotX is 5, robotY must be 0.

Additionally, the system must satisfy a liveness requirement: the robot must infinitely often reach the position where robotX is 7 and robotY is 7.