

Specification name: EscapingGuard

Named domains:
- Dim: Int(0..D)

Environment variables:
- none

System variables:
- robotX: Dim
- robotY: Dim

**System Overview**
The system controls a robot moving on a two-dimensional grid. The robot's position is defined by coordinates `robotX` and `robotY`, both of which are integers ranging from 0 to 7 (where the constant D is 7). There are no environment-controlled inputs; the system fully determines the robot's movement.

**Initial Conditions**
Upon startup, the robot must be located at position X=7, Y=0.

**Safety Requirements**
The robot must avoid specific obstacle locations. Specifically, if the robot's X coordinate is 2, its Y coordinate must not be 2, 3, 4, or 5. This constraint must hold at all times during operation.

**Liveness Requirements**
The robot is required to visit three specific target locations infinitely often throughout its operation:
1.  Target T1 at position (0, 0).
2.  Target T2 at position (7, 7).
3.  Target T3 at position (0, 7).

**Sequential Constraints**
There is a specific ordering constraint triggered by visiting Target T1. Whenever the robot is at Target T1, it must eventually reach Target T2. Furthermore, during the period between leaving Target T1 and arriving at Target T2, the robot must not visit Target T3.