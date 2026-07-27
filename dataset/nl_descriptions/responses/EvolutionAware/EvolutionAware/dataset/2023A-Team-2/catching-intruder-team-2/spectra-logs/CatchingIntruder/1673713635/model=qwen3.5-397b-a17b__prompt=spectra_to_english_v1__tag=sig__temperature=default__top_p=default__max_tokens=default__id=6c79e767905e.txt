

Specification name: CatchingIntruder

Named domains:
- Dim: Int(0..D)

Environment variables:
- intruderX: Dim
- intruderY: Dim

System variables:
- robotX0: Dim
- robotY0: Dim
- robotX1: Dim
- robotY1: Dim

**Requirements Description**

The **CatchingIntruder** specification describes a reactive system operating on an 8x8 grid, where coordinates range from 0 to 7. The system controls two robots, R0 and R1, while the environment controls a moving intruder.

**Initial Conditions**
At the start of the system operation:
- Robot R0 is positioned at the top-left corner, with coordinates `robotX0 = 0` and `robotY0 = 0`.
- Robot R1 is positioned at the top-right corner, with coordinates `robotX1 = 7` and `robotY1 = 0`.

**System Behavior and Constraints**
The system must guarantee the following behaviors for the robots in every state:
- **Movement:** Each robot must either remain in its current cell or move to an adjacent cell. Diagonal movement is prohibited; a robot must change at most one coordinate (either X or Y) during a move.
- **Obstacles:** The specification defines four fixed obstacle locations at coordinates (2,1), (3,1), (4,1), and (5,1).

**Environment Inputs**
The environment provides the current coordinates of the intruder (`intruderX`, `intruderY`). The specification defines these variables but does not impose specific assumptions on the intruder's movement or behavior within this snippet.

**System Outputs**
The system controls the coordinates of the two robots (`robotX0`, `robotY0`, `robotX1`, `robotY1`) and must update them in each step according to the movement constraints described above.