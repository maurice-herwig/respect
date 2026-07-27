

The Deliveries specification defines a system where all variables are controlled by the system. It establishes constants DX and DY, both equal to 5. Three types are defined: DimX covers integers from 0 to DX, DimY covers integers from 0 to DY, and Coord covers integers from 0 to DY. The system maintains four variables: robotX0 and robotX1 use the DimX type, while robotY0 and robotY1 use the DimY type.

Specification name: Deliveries

Named domains:
- DimX: Int(0..DX)
- DimY: Int(0..DY)
- Coord: Int(0..DY)

Environment variables:
- none

System variables:
- robotX0: DimX
- robotY0: DimY
- robotX1: DimX
- robotY1: DimY