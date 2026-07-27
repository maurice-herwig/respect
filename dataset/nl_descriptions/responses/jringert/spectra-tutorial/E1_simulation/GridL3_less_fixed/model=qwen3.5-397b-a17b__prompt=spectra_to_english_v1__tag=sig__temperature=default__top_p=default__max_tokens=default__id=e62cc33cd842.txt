

Specification name: GridL3_less

Named domains:
- Coord: Int(0..upper)

Environment variables:
- rob: Coord[2]

System variables:
- move: {UP, DOWN, LEFT, RIGHT, STAY}

This specification describes a reactive system that issues movement commands to an environment controlling a robot's position on a bounded grid. The grid coordinates range from 0 to 5, where the value 5 corresponds to the defined upper bound.

The environment controls the variable `rob`, which stores the robot's current coordinates as an array of two integers. The system controls the variable `move`, which specifies the desired direction of movement.

The specification imposes assumptions on the environment regarding how the robot's position updates in response to the system's movement commands. At all times, the environment must update the `rob` coordinates in the next state according to the following rules based on the current value of `move`:

- **UP:** The environment decreases the value of `rob[1]` by 1. If `rob[1]` is already 0, it remains 0. The value of `rob[0]` remains unchanged.
- **DOWN:** The environment increases the value of `rob[1]` by 1. If `rob[1]` is already 5, it remains 5. The value of `rob[0]` remains unchanged.
- **LEFT:** The environment decreases the value of `rob[0]` by 1. If `rob[0]` is already 0, it remains 0. The value of `rob[1]` remains unchanged.
- **RIGHT:** The environment increases the value of `rob[0]` by 1. If `rob[0]` is already 5, it remains 5. The value of `rob[1]` remains unchanged.
- **STAY:** Both `rob[0]` and `rob[1]` remain unchanged.

These assumptions define the expected behavior of the environment whenever the system selects a specific movement command.