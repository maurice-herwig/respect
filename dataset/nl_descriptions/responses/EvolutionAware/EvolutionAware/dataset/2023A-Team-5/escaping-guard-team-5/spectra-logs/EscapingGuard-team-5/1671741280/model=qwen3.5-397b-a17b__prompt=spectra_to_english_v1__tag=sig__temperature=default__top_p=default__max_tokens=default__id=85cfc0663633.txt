

Specification name: EscapingGuard

Named domains:
- Dim: Int(0..D)

Environment variables:
- none

System variables:
- robotX: Dim
- robotY: Dim

**Requirements Description**

The system controls the position of a robot using the coordinates `robotX` and `robotY`. Both variables are integers within the domain `Dim`, ranging from 0 to 7 (where D = 7).

**Initial Condition**
At the start of operation, the robot must be located at the position `robotX = 7` and `robotY = 0`.

**Safety Requirements**
In every step of the system's execution, the robot's movement is constrained to adjacent cells. The value of `robotX` in the next state must be between `robotX - 1` and `robotX + 1` inclusive. Similarly, the value of `robotY` in the next state must be between `robotY - 1` and `robotY + 1` inclusive. The coordinates must always remain within the bounds of the domain `Dim`.

**Liveness Requirements**
The system must ensure that the robot visits each of the following three positions infinitely often throughout its operation:
1. `robotX = 0` and `robotY = 0`.
2. `robotX = 7` and `robotY = 7`.
3. `robotX = 0` and `robotY = 7`.