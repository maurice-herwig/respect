

Specification name: Module2

Named domains:
- DimX: Int(0..DX)
- DimY: Int(0..DY)
- Coord: Int(0..DY)

Environment variables:
- elevator: DimY

System variables:
- robotX0: DimX
- robotY0: DimY
- robotX1: DimX
- robotY1: DimY

**Requirements Description**

This specification defines a reactive system involving two robots and an elevator. The constants DX and DY are both defined as 5, meaning all coordinate variables range from 0 to 5.

**Environment Behavior**
The environment controls the `elevator` variable. The elevator position must change gradually; between any two consecutive steps, the elevator value may increase by at most 1, decrease by at most 1, or remain unchanged. Additionally, the environment must ensure that the elevator reaches position 0 infinitely often and reaches position 5 infinitely often throughout the system execution.

**System Behavior**
The system controls the horizontal (`robotX0`, `robotX1`) and vertical (`robotY0`, `robotY1`) coordinates for two robots. The system must satisfy the following safety requirements at all times:

1.  **Robot 0 Positioning:** Whenever Robot 0's horizontal coordinate (`robotX0`) is 0, its vertical coordinate (`robotY0`) must exactly match the current position of the `elevator`.
2.  **Robot 1 Positioning:** Whenever Robot 1's horizontal coordinate (`robotX1`) is 0, its vertical coordinate (`robotY1`) must exactly match the current position of the `elevator`.

These conditions must hold globally whenever the respective robot's horizontal coordinate is 0.