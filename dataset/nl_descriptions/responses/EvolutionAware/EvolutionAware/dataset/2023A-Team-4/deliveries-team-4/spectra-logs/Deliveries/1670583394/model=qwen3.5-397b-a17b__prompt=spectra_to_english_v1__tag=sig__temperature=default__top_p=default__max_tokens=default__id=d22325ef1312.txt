

Specification name: Deliveries

Named domains:
- DimX: Int(0..DX)
- DimY: Int(0..DY)
- Coord: Int(0..DY)
- DimLambX: Int(1..DX)
- DimLambY: Int(1..DX)

Environment variables:
- lambX0: DimLambX
- lambY0: DimLambY
- lambX1: DimLambX
- lambY1: DimLambY
- elevatorY: DimY

System variables:
- robotX0: DimX
- robotY0: DimY
- robotX1: DimX
- robotY1: DimY

**Requirements Description**

This specification defines a reactive delivery system operating on a grid where dimensions DX and DY are both 5. The system controls two robots, while the environment controls the positions of two lambs (representing packages) and the vertical position of an elevator. The elevator is fixed at horizontal coordinate 0.

**Environment Assumptions**
The environment behavior is restricted by the following assumptions:
1.  **Lamb Stability:** Lamb 0 remains stationary (its `lambX0` and `lambY0` coordinates do not change) unless Robot 0 is currently located at the exact same coordinates. Similarly, Lamb 1 remains stationary (its `lambX1` and `lambY1` coordinates do not change) unless Robot 1 is currently located at the exact same coordinates.
2.  **Elevator Movement:** At every step, the elevator vertical position `elevatorY` must change by exactly one floor, either up or down.
3.  **Elevator Liveness:** The elevator must visit floor 0 infinitely often and must visit floor 5 infinitely often.

**System Guarantees**
The system must satisfy the following guarantees whenever the environment satisfies its assumptions:
1.  **Robot 0 Delivery:** Robot 0 must reach the same coordinates as Lamb 0 infinitely often.
2.  **Robot 1 Delivery:** Robot 1 must reach the same coordinates as Lamb 1 infinitely often.

**Data Constraints**
-   Robot coordinates (`robotX0`, `robotY0`, `robotX1`, `robotY1`) range from 0 to 5.
-   Lamb coordinates (`lambX0`, `lambY0`, `lambX1`, `lambY1`) range from 1 to 5; lambs cannot be located on floor 0.
-   The elevator vertical coordinate (`elevatorY`) ranges from 0 to 5.