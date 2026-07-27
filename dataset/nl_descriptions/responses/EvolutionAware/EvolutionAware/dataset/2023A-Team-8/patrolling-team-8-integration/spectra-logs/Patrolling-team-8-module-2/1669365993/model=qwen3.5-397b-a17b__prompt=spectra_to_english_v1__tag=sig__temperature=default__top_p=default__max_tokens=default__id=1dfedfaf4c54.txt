

Specification name: PatrollingTeam8Module2

Named domains:
- DimX: Int(0..DX)
- DimY: Int(0..DY)
- Dim: Int(0..D)

Environment variables:
- target1: Dim[2]
- target2: Dim[2]
- target3: Dim[2]

System variables:
- robotX: DimX
- robotY: DimY

This specification describes a patrolling robot system operating within a defined grid. The system controls the robot's horizontal and vertical position using the variables `robotX` and `robotY`. The environment provides the locations of three distinct targets via the variables `target1`, `target2`, and `target3`, each consisting of a pair of coordinates.

The environment is assumed to keep the target locations stationary. Specifically, the coordinates for `target1`, `target2`, and `target3` remain constant throughout the system's execution and do not change between states.

The system must adhere to the following behavioral guarantees. Initially, the robot must start at the origin position where `robotX` equals 0 and `robotY` equals 0. During operation, the robot must infinitely often reach the coordinates specified by `target1`. Similarly, the robot must infinitely often reach the coordinates specified by `target2` and `target3`. Furthermore, the robot is required to infinitely often return to the origin position where `robotX` equals 0 and `robotY` equals 0.