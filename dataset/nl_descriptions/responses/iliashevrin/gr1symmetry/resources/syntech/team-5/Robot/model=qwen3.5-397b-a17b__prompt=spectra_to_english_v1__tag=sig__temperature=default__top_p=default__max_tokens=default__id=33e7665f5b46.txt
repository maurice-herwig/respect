

Specification name: Robot

Named domains:
- DimX: Int(0..DX)
- DimY: Int(0..DY)

Environment variables:
- none

System variables:
- robotX: DimX
- robotY: DimY

**Requirements Description**

The system controls the position of a robot on a grid using the coordinates `robotX` and `robotY`. There are no environment inputs; the system autonomously determines the robot's movement.

**Initial Condition**
At the start of operation, the robot must be positioned at coordinates (0, 0).

**Movement Rules**
At every step, the robot's coordinates update according to the following rules:
- The `robotX` coordinate may decrease by 1 (if not currently 0), increase by 1 (if not currently DX), or remain unchanged.
- The `robotY` coordinate may decrease by 1 (if not currently 0), increase by 1 (if not currently DY), or remain unchanged.

**Safety Constraints**
- **Stability:** If the robot reaches the position where `robotX` equals DX and `robotY` equals DY, it must remain at that position in all subsequent steps.
- **Obstacle Avoidance:** The robot must never occupy a position where `robotX` is 2 unless `robotY` is 7. Additionally, the robot must never occupy a position where `robotX` is 5 unless `robotY` is 0.

**Liveness Requirement**
- The robot must infinitely often be at the position where `robotX` equals DX and `robotY` equals DX.