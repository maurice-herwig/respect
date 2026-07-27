

Specification name: Patrolling

Named domains:
- DimX: Int(0..DX)
- DimY: Int(0..DY)

Environment variables:
- none

System variables:
- robotX: DimX
- robotY: DimY

The system controls two output variables, `robotX` and `robotY`, which represent coordinates within a grid. The variable `robotX` ranges from 0 to 4, and `robotY` ranges from 0 to 4. There are no environment-controlled input variables.

The system must satisfy a safety guarantee requiring that `robotX` always equals 1. This condition must hold in the initial state and must be maintained at every subsequent step of the system's operation. The system controls the value of `robotY` within its defined domain.