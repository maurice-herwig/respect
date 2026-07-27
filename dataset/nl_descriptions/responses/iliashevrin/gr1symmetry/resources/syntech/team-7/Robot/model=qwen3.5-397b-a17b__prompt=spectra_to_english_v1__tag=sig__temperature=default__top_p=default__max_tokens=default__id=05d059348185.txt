

Specification name: Robot

Named domains:
- DimX: Int(0..DX)
- DimY: Int(0..DY)

Environment variables:
- none

System variables:
- robotX: DimX
- robotY: DimY

The system controls the robot's position on a grid using the variables `robotX` and `robotY`. Initially, the robot is located at coordinates (0, 0).

At each step, the robot's movement is restricted such that the `robotX` coordinate may increase by 1, decrease by 1, or remain unchanged, and the `robotY` coordinate may similarly increase by 1, decrease by 1, or remain unchanged.

The robot is required to eventually reach the position (7, 7). Once the robot arrives at position (7, 7), it must stay at that position forever.

Additionally, the robot must avoid specific obstacle regions defined by its coordinates:
- Whenever `robotX` is 2, `robotY` must be greater than 6.
- Whenever `robotX` is 5, `robotY` must be less than 1.