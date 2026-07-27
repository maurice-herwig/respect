

Specification name: Deliveries

Named domains:
- DimX: Int(0..DX)
- DimY: Int(0..DY)
- Coord: Int(0..DY)

Environment variables:
- package0X: DimX
- package0Y: DimY
- package1X: DimX
- package1Y: DimY

System variables:
- robotX0: DimX
- robotY0: DimY
- robotX1: DimX
- robotY1: DimY

The system controls the positions of two robots within a coordinate grid. The environment determines the target locations for two packages. The system variables `robotX0` and `robotY0` represent the coordinates of Robot 0, while `robotX1` and `robotY1` represent the coordinates of Robot 1. The environment variables `package0X` and `package0Y` specify the location of Package 0, and `package1X` and `package1Y` specify the location of Package 1.

The system must satisfy the following liveness guarantees:

1. Robot 0 must reach the location of Package 0 infinitely often. This condition is met when the system variable `robotX0` equals the environment variable `package0X` and the system variable `robotY0` equals the environment variable `package0Y`.
2. Robot 1 must reach the location of Package 1 infinitely often. This condition is met when the system variable `robotX1` equals the environment variable `package1X` and the system variable `robotY1` equals the environment variable `package1Y`.