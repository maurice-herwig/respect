

Specification name: Deliveries

Named domains:
- DimX: Int(0..DX)
- DimY: Int(0..DY)
- Coord: Int(0..DY)

Environment variables:
- elvY: DimY

System variables:
- robotX0: DimX
- robotY0: DimY
- robotX1: DimX
- robotY1: DimY

**System Overview**
The system controls two robots, Robot 0 and Robot 1, operating within a two-dimensional grid. The grid coordinates range from 0 to 5 on both the X and Y axes. The environment controls the Y-coordinate of an elevator (`elvY`), while the elevator's X-coordinate is fixed at 0. The system controls the X and Y coordinates for both robots.

**Environment Assumptions**
The environment must ensure that the elevator Y-coordinate (`elvY`) equals 0 infinitely often and equals 5 infinitely often throughout the system operation.

**System Guarantees**
*Initial Conditions:*
At the start of operation, both Robot 0 and Robot 1 must be at Y-coordinate 0.

*Safety Requirements:*
At all times, Robot 0 and Robot 1 must never occupy the same position (i.e., they cannot have the same X and Y coordinates simultaneously).

*Movement Rules:*
The system must adhere to the following movement constraints for each robot at every step:

1.  **Robot 0:**
    *   If Robot 0 is not at the elevator location (X=0 and Y=`elvY`): Its X-coordinate may change by at most 1 unit (increase, decrease, or stay the same), and its Y-coordinate must remain unchanged.
    *   If Robot 0 is at the elevator location: It must either move with the elevator (its X-coordinate becomes 0 and its Y-coordinate updates to match the next elevator Y-coordinate) OR it must move according to the standard rules (X changes by at most 1 unit and Y remains unchanged).

2.  **Robot 1:**
    *   If Robot 1 is not at the elevator location (X=0 and Y=`elvY`): Its X-coordinate may change by at most 1 unit, and its Y-coordinate must remain unchanged.
    *   If Robot 1 is at the elevator location: It must either move with the elevator (its X-coordinate becomes 0 and its Y-coordinate updates to match the next elevator Y-coordinate) OR the system must ensure that Robot 0's X-coordinate changes by at most 1 unit and Robot 0's Y-coordinate remains unchanged.