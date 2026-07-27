

Specification name: Patrolling

Named domains:
- DimX: Int(0..DX)
- DimY: Int(0..DY)

Environment variables:
- A_X: DimX
- A_Y: DimY
- B_X: DimX
- B_Y: DimY
- C_X: DimX
- C_Y: DimY
- BlockedA: boolean
- BlockedB: boolean
- BlockedC: boolean

System variables:
- robotX: DimX
- robotY: DimY

**Requirements Description**

The system controls a robot navigating a two-dimensional grid where both X and Y coordinates range from 0 to 4. The robot's position is defined by the system variables `robotX` and `robotY`. Initially, the robot must start at coordinates (0, 0).

The environment determines the locations of three targets (A, B, and C) via the variables `A_X`, `A_Y`, `B_X`, `B_Y`, `C_X`, and `C_Y`. Additionally, the environment controls boolean flags `BlockedA`, `BlockedB`, and `BlockedC` to indicate whether each respective target is currently blocked. Initially, none of the targets are located at the robot's starting position (0, 0).

Regarding environment assumptions, each target is guaranteed to become unblocked infinitely often. Specifically, it is always the case that eventually `BlockedA`, `BlockedB`, and `BlockedC` will be false.

The system must satisfy safety guarantees concerning blocked targets. Whenever target A is blocked (`BlockedA` is true), the robot must not be located at coordinates (`A_X`, `A_Y`). Similarly, if target B is blocked, the robot must not be at (`B_X`, `B_Y`), and if target C is blocked, the robot must not be at (`C_X`, `C_Y`).