

Specification name: Deliveries

Named domains:
- DimX: Int(0..DX)
- DimY: Int(0..DY)
- Coord: Int(0..DY)

Environment variables:
- elevatorY: DimY
- deliveriesX: DimX [2]
- deliveriesY: DimY [2]

System variables:
- robotX0: DimX
- robotY0: DimY
- robotX1: DimX
- robotY1: DimY

**Requirements Description**

This specification defines the behavior of a delivery system involving two robots operating within a grid coordinate space where both X and Y dimensions range from 0 to 5.

**Environment Assumptions**
The environment provides the target delivery coordinates for two packages via the arrays `deliveriesX` and `deliveriesY`. The environment must ensure that the Y-coordinate for both delivery locations is never 5. Specifically, `deliveriesY[0]` and `deliveriesY[1]` must always be unequal to 5. The variable `elevatorY` is an environment input provided for simulation purposes but is not constrained by this specification.

**System Guarantees**
The system controls the positions of two robots, Robot 0 (`robotX0`, `robotY0`) and Robot 1 (`robotX1`, `robotY1`). The system must satisfy the following liveness requirements:

1.  **Package Delivery:**
    *   Robot 0 must infinitely often reach the target location specified by `deliveriesX[0]` and `deliveriesY[0]`.
    *   Robot 1 must infinitely often reach the target location specified by `deliveriesX[1]` and `deliveriesY[1]`.

2.  **Return to Corner:**
    *   Robot 0 must infinitely often reach the coordinates (5, 5).
    *   Robot 1 must infinitely often reach the coordinates (5, 5).

**State Tracking Counters**
The system maintains two internal counters to track delivery activity, each ranging from 0 to 3:

*   **`packagesDeliveredByRobot0`**:
    *   **Initial Value:** 0.
    *   **Increment:** The value increases when Robot 0 is located at the coordinates (`deliveriesX[0]`, `deliveriesY[0]`).
    *   **Reset:** The value resets to 0 when Robot 0 is located at coordinates (5, 5).
    *   **Bounds:** The value must not exceed 3.

*   **`packagesDeliveredByRobot1`**:
    *   **Initial Value:** 0.
    *   **Increment:** The value increases when Robot 1 is located at the coordinates (`deliveriesX[1]`, `deliveriesY[1]`).
    *   **Reset:** The value resets to 0 when Robot 1 is located at coordinates (5, 5).
    *   **Bounds:** The value must not exceed 3.