

The specification defines a reactive interaction between a system and an environment concerning the movement of a robot on a grid. The system controls the movement command variable `move`, while the environment controls the robot's position variable `rob`. The position `rob` is an array of two coordinates, each ranging from 0 to `upper` (where `upper` is 5). The movement command `move` selects a direction from the set {UP, DOWN, LEFT, RIGHT, STAY}.

The specification places assumptions on the environment regarding how the robot's position updates in response to the system's movement commands. At every step, the environment must ensure the next state of `rob` adheres to the following rules based on the current value of `move`:

*   **UP:** If the system commands UP, the environment must decrease the second coordinate (`rob[1]`) by 1 in the next state, unless it is already 0, in which case it must remain 0. The first coordinate (`rob[0]`) must remain unchanged.
*   **DOWN:** If the system commands DOWN, the environment must increase the second coordinate (`rob[1]`) by 1 in the next state, unless it is already `upper`, in which case it must remain `upper`. The first coordinate (`rob[0]`) must remain unchanged.
*   **LEFT:** If the system commands LEFT, the environment must decrease the first coordinate (`rob[0]`) by 1 in the next state, unless it is already 0, in which case it must remain 0. The second coordinate (`rob[1]`) must remain unchanged.
*   **RIGHT:** If the system commands RIGHT, the environment must increase the first coordinate (`rob[0]`) by 1 in the next state, unless it is already `upper`, in which case it must remain `upper`. The second coordinate (`rob[1]`) must remain unchanged.

Specification name: GridL3_less

Named domains:
- Coord: Int(0..upper)

Environment variables:
- rob: Coord[2]

System variables:
- move: {UP, DOWN, LEFT, RIGHT, STAY}