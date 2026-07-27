

Specification name: EscapingGuard

Named domains:
- Dim: Int(0..D)

Environment variables:
- obsXL: Dim
- obsYT: Dim

System variables:
- robotX: Dim
- robotY: Dim

**Requirements Description**

This specification defines the interaction between a robot and a moving obstacle on a grid. The grid coordinates for both the robot and the obstacle are defined by the domain `Dim`, representing integers from 0 to 7. The system controls the robot's horizontal and vertical position (`robotX`, `robotY`), while the environment controls the obstacle's top-left horizontal and vertical position (`obsXL`, `obsYT`).

**System Guarantees**
The system must ensure the robot moves smoothly across the grid. At every step of the interaction, the robot's X and Y coordinates must either remain unchanged, increase by exactly 1, or decrease by exactly 1. This ensures the robot never jumps more than one grid unit in any direction per step.

**Environment Assumptions**
The environment is assumed to adhere to specific movement and behavioral constraints regarding the obstacle:

1.  **Movement Limits:** Similar to the robot, the obstacle's X and Y coordinates must either remain unchanged, increase by exactly 1, or decrease by exactly 1 at every step.
2.  **Chasing Behavior:** The obstacle always moves towards the robot's current position. Specifically:
    *   If the robot's X coordinate is less than the obstacle's X coordinate, the obstacle's next X coordinate must be less than or equal to its current X coordinate.
    *   If the robot's X coordinate is greater than the obstacle's X coordinate, the obstacle's next X coordinate must be greater than or equal to its current X coordinate.
    *   These same conditions apply to the Y coordinates: the obstacle must move towards or stay level with the robot's Y coordinate, never moving away along either axis.
3.  **Speed Constraint:** An internal counter cycles through values 0, 1, and 2, initialized to 0. Whenever this counter value is less than 2, the obstacle must remain stationary (its next X and Y coordinates must equal its current coordinates). This restricts the obstacle to moving less frequently than the robot.