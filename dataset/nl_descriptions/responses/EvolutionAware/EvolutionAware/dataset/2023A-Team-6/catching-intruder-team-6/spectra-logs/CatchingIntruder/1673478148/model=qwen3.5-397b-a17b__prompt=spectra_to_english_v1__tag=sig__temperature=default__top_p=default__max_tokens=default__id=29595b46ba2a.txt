

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

**System Overview**
This specification defines a reactive system involving two robots operating on a two-dimensional grid alongside an intruder controlled by the environment. All position coordinates are integers ranging from 0 to 7 inclusive. The system controls the positions of Robot 0 and Robot 1, while the environment controls the position of the intruder.

**Environment Assumptions**
The environment must adhere to the following movement constraints for the intruder:
1.  **Movement Speed:** In every step, the intruder's X and Y coordinates must each change by at most 1 unit. The coordinate may remain the same, increase by 1, or decrease by 1.
2.  **Movement Direction:** The intruder cannot move diagonally. In any given step, either the intruder's X coordinate must remain unchanged, or the intruder's Y coordinate must remain unchanged.
3.  **Obstacle Avoidance:** The intruder must never occupy the obstacle zone. Specifically, if the intruder's Y coordinate is 1, its X coordinate must not be 2, 3, 4, or 5.

**System Guarantees**
The system must ensure the following behaviors for both Robot 0 and Robot 1:
1.  **Movement Speed:** In every step, each robot's X and Y coordinates must each change by at most 1 unit. The coordinate may remain the same, increase by 1, or decrease by 1.
2.  **Movement Direction:** The robots cannot move diagonally. In any given step, for each robot, either its X coordinate must remain unchanged, or its Y coordinate must remain unchanged.
3.  **Obstacle Avoidance:** The robots must never occupy the obstacle zone. Specifically, if a robot's Y coordinate is 1, its X coordinate must not be 2, 3, 4, or 5.

**Safety Requirements**
All movement and positioning constraints described above are safety properties that must hold always throughout the system execution. There are no specified initial conditions or liveness requirements in this specification; the requirements strictly govern the valid transitions and prohibited states regarding movement and obstacle collision.