

Specification name: Patrolling

Named domains:
- DimX: Int(0..DX)
- DimY: Int(0..DY)

Environment variables:
- targetAX: DimX
- targetAY: DimY
- targetBX: DimX
- targetBY: DimY
- targetCX: DimX
- targetCY: DimY

System variables:
- robotX: DimX
- robotY: DimY

**Requirements Description**

This specification defines the behavior of a robot patrolling a two-dimensional grid. The robot's position is determined by the system-controlled variables `robotX` and `robotY`. The environment provides the coordinates for three distinct targets: Target A (`targetAX`, `targetAY`), Target B (`targetBX`, `targetBY`), and Target C (`targetCX`, `targetCY`).

**Environment Assumptions**
The environment is assumed to keep the target locations static. Once initialized, the coordinates for Target A, Target B, and Target C must remain constant throughout the operation; they do not change between steps.

**System Guarantees**
The system must satisfy the following requirements:

1.  **Initial Condition:** The robot must start at the top-left corner of the grid, specifically where `robotX` = 0 and `robotY` = 0.
2.  **Movement Constraints:** In every transition, the robot's movement is limited to one step per dimension. The value of `robotX` in the next state must be equal to, one greater than, or one less than its current value. The same constraint applies to `robotY`.
3.  **Liveness Requirements:** The robot must visit the following locations infinitely often:
    *   The location of Target A (where `robotX` = `targetAX` and `robotY` = `targetAY`).
    *   The location of Target B (where `robotX` = `targetBX` and `robotY` = `targetBY`).
    *   The location of Target C (where `robotX` = `targetCX` and `robotY` = `targetCY`).
    *   The top-left corner (where `robotX` = 0 and `robotY` = 0).