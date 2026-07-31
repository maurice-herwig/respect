

Specification name: Module3

Named domains:
- DimX: Int(0..DX)
- DimY: Int(0..DY)
- Coord: Int(0..DY)

Environment variables:
- targetX0: DimX
- targetY0: DimY
- targetX1: DimX
- targetY1: DimY

System variables:
- robotX0: DimX
- robotY0: DimY
- robotX1: DimX
- robotY1: DimY

### Requirements Description

This specification defines a reactive system controlling two robots, robot 0 and robot 1, operating within a grid environment. The grid dimensions are defined by constants DX and DY (both equal to 5). The system controls the X and Y coordinates of both robots (`robotX0`, `robotY0`, `robotX1`, `robotY1`), while the environment provides target coordinates for each robot (`targetX0`, `targetY0`, `targetX1`, `targetY1`).

**Environment Assumptions**
The environment adheres to the following constraints regarding target locations:
1.  **Target Boundaries:** The target X coordinates for both robots (`targetX0`, `targetX1`) are never 0. The target Y coordinates for both robots (`targetY0`, `targetY1`) are never equal to DY.
2.  **Target Movement:** Whenever a robot reaches its target (meaning its coordinates exactly match the target coordinates), the environment must change the corresponding target Y coordinate in the immediately following step.

**System Guarantees**
The system must satisfy the following requirements:
1.  **Liveness:** Both robot 0 and robot 1 must reach their respective targets infinitely often during system operation.
2.  **Package Counters:** The system maintains two package counters, `packages0` and `packages1`, each ranging from 0 to 3.
    *   **Initialization:** Both counters initialize to 0.
    *   **Increment:** A counter increments when its corresponding robot is at its target location.
    *   **Reset:** A counter resets to 0 when its corresponding robot is located at Y coordinate DY and X coordinate not equal to 0.
    *   **Overflow:** If a counter reaches 3, it remains at 3 until a reset occurs.
    *   **Capacity Constraint:** If a package counter equals 3, the corresponding robot must not be at its target location. This ensures the robot must visit the reset location to clear the counter before reaching the target again once the counter is full.