

Specification name: Patrolling

Named domains:
- DimX: Int(0..DX)
- DimY: Int(0..DY)

Environment variables:
- none

System variables:
- robotX: DimX
- robotY: DimY
- targetAX: DimX
- targetAY: DimY
- Agreen: boolean
- targetBX: DimX
- targetBY: DimY
- Bgreen: boolean
- targetCX: DimX
- targetCY: DimY
- Cgreen: boolean

**Requirements Description**

The system controls the coordinates of a robot (`robotX`, `robotY`) and the definitions of three targets (A, B, and C), including their respective coordinates (`targetAX`, `targetAY`, etc.) and active status flags (`Agreen`, `Bgreen`, `Cgreen`). The system must ensure the following behavior regarding the robot's interaction with these targets:

**Liveness Requirements**
The robot must visit the location of Target A infinitely often. Specifically, the condition where the robot's coordinates match Target A's coordinates must occur repeatedly throughout the system's operation. The same requirement applies to Target B and Target C; the robot must visit the locations of Target B and Target C infinitely often as well.

**Safety Requirements**
The robot is prohibited from occupying the location of Target A unless Target A is active. Formally, it must always be the case that if the robot is at Target A's coordinates, then `Agreen` is true. Similarly, the robot must not be at Target B's coordinates unless `Bgreen` is true, and must not be at Target C's coordinates unless `Cgreen` is true. The system must ensure these conditions hold at all times.