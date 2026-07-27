

Specification name: Deliveries

Named domains:
- DimX: Int(0..DX)
- DimY: Int(0..DY)
- Coord: Int(0..DY)

Environment variables:
- deliveriesX: DimX [2]
- deliveriesY: DimY [2]
- elevatorX: DimX
- elevatorY: DimY

System variables:
- robotX0: DimX
- robotY0: DimY
- robotX1: DimX
- robotY1: DimY

**Requirements Description**

The system controls the positions of two robots, Robot 0 and Robot 1, within a grid defined by the dimensions `DX` and `DY` (both valued at 5). The environment provides input variables representing two delivery locations and an elevator location. The system outputs the current X and Y coordinates for each robot.

The system must satisfy the following behavioral guarantees regarding the robot positions relative to the delivery locations provided by the environment:

1.  **Robot 0 Delivery Visits:** Infinitely often, the position of Robot 0 (`robotX0`, `robotY0`) must exactly match the first delivery location specified by `deliveriesX[0]` and `deliveriesY[0]`.
2.  **Robot 0 Delivery Departures:** Infinitely often, the position of Robot 0 must not match the first delivery location specified by `deliveriesX[0]` and `deliveriesY[0]`.
3.  **Robot 1 Delivery Visits:** Infinitely often, the position of Robot 1 (`robotX1`, `robotY1`) must exactly match the second delivery location specified by `deliveriesX[1]` and `deliveriesY[1]`.
4.  **Robot 1 Delivery Departures:** Infinitely often, the position of Robot 1 must not match the second delivery location specified by `deliveriesX[1]` and `deliveriesY[1]`.

There are no specified assumptions restricting the environment's behavior, nor are there specific initial conditions or next-state update rules defined beyond the liveness requirements stated above. The elevator variables (`elevatorX`, `elevatorY`) are provided by the environment but are not constrained by the specified guarantees.