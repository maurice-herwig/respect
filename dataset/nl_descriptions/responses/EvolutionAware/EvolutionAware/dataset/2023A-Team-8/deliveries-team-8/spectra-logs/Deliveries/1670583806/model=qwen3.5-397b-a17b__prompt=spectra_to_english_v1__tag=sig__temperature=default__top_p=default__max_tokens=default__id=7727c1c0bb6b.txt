

Specification name: Deliveries

Named domains:
- DimX: Int(0..DX)
- DimY: Int(0..DY)
- Coord: Int(0..DY)

Environment variables:
- elevatorY: Coord
- lamp_A_X: DimX
- lamp_A_Y: DimY
- lamp_B_X: DimX
- lamp_B_Y: DimY

System variables:
- robotX0: DimX
- robotY0: DimY
- robotX1: DimX
- robotY1: DimY

### System Requirements Description

This specification defines the behavior of a delivery system involving two robots operating within a grid environment. The system interacts with an environment that controls the vertical position of an elevator and the positions of two lamps (Lamp A and Lamp B).

**Initial Conditions**
At the start of operation, both Robot 0 and Robot 1 are initialized to a Y coordinate of 0. Their initial X coordinates are unspecified.

**Environment Inputs**
The environment provides the current Y coordinate of the elevator (`elevatorY`) and the X and Y coordinates for Lamp A and Lamp B. There are no specified restrictions on how these environment variables change over time.

**System Guarantees**
The system must control the coordinates of Robot 0 (`robotX0`, `robotY0`) and Robot 1 (`robotX1`, `robotY1`) according to the following safety constraints:

1.  **Elevator Presence Definition:** A robot is considered to be "in the elevator" when its X coordinate is 0 and its Y coordinate is equal to the current `elevatorY` value.

2.  **Movement Constraints While in Elevator:** Whenever a robot is in the elevator, its next state must satisfy one of the following conditions:
    *   **Exit Shaft:** The robot remains on the current floor (its Y coordinate does not change) and moves one step horizontally away from the elevator shaft (its X coordinate increases by 1).
    *   **Ride Elevator:** The robot's next Y coordinate matches the elevator's next Y coordinate. This option is valid provided the robot is currently at X coordinate 0.

These movement constraints apply independently and identically to both Robot 0 and Robot 1 whenever they meet the condition of being in the elevator.