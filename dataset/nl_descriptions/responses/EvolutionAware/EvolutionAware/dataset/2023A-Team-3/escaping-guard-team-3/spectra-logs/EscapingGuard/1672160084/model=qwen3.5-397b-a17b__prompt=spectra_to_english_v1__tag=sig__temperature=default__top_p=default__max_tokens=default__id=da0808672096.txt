

Specification name: EscapingGuard

Named domains:
- Dim: Int(0..D)
- DimM: Int(0..DM)

Environment variables:
- mx: DimM
- my: DimM

System variables:
- robotX: Dim
- robotY: Dim

The system controls the robot's horizontal and vertical position, represented by the variables `robotX` and `robotY`. The environment controls the guard's horizontal and vertical position, represented by the variables `mx` and `my`.

Initially, the robot must start at position (7, 0), and the guard must start at position (0, 0).

Regarding movement safety, both the robot and the guard are constrained to move incrementally. In every step, each coordinate of the robot (`robotX` and `robotY`) must either remain the same, increase by one, or decrease by one. Similarly, it is assumed that each coordinate of the guard (`mx` and `my`) will either remain the same, increase by one, or decrease by one in every step.

The system must ensure the robot satisfies specific liveness requirements. The robot is required to visit three target locations infinitely often during operation. These target locations are defined as (0, 0), (7, 7), and (0, 7).