

Specification name: EscapingGuard

Named domains:
- Dim: Int(0..D)

Environment variables:
- guardX: Dim
- guardY: Dim

System variables:
- robotX: Dim
- robotY: Dim

**Requirements Description**

This specification defines a reactive system where a robot navigates a two-dimensional grid while interacting with a guard. The grid coordinates range from 0 to 7 (where D = 7). The system controls the robot's position, while the environment controls the guard's position.

**Initial Conditions**
At the start of the system execution, the robot is positioned at the bottom-right corner of the grid (X = 7, Y = 0). The guard is positioned at the top-left corner (X = 0, Y = 0).

**Turn-Taking Protocol**
The interaction follows a cyclic turn-based protocol managed by an internal counter that cycles through values 0, 1, 2, and 3 repeatedly.
- When the counter value is 0, it is the guard's turn. The robot must remain stationary during this step, while the guard is permitted to move.
- When the counter value is 1, 2, or 3, it is the robot's turn. The guard must remain stationary during these steps, while the robot is permitted to move.
This results in a pattern where the guard moves for one step, followed by the robot moving for three steps, repeating indefinitely.

**Movement Constraints**
Whenever a party (robot or guard) is permitted to move according to the turn-taking protocol, their position updates are restricted as follows:
- Each coordinate (X and Y) may change by at most 1 unit per step. Specifically, a coordinate may increase by 1, decrease by 1, or remain unchanged.
- Both coordinates may change simultaneously within the same step.

**System Guarantees**
The system must ensure the following behaviors regarding the robot:
- **Safety:** The robot must adhere to the movement constraints and the turn-taking protocol described above.
- **Liveness:** The robot must infinitely often visit each of the following three target positions:
  1. Top-left corner (X = 0, Y = 0).
  2. Top-right corner (X = 0, Y = 7).
  3. Bottom-right corner (X = 7, Y = 7).

**Environment Assumptions**
The specification assumes the environment adheres to the following behaviors regarding the guard:
- **Safety:** The guard must adhere to the movement constraints and the turn-taking protocol described above.
- **Initial State:** The guard starts at the top-left corner (X = 0, Y = 0).