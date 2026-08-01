

Specification name: CatchingIntruder

Named domains:
- Dim: Int(0..D)
- four: Int(0..4)

Environment variables:
- intruderX: Dim
- intruderY: Dim
- dontMove: four

System variables:
- robotX0: Dim
- robotY0: Dim
- robotX1: Dim
- robotY1: Dim

The system controls the positions of two robots, designated as robot 0 and robot 1. Each robot has horizontal and vertical coordinates (X and Y) within a grid defined by the domain Dim, where the maximum coordinate value D is 7. The environment controls the position of an intruder (intruderX, intruderY) and a movement counter (dontMove).

The environment must adhere to the following assumptions regarding the intruder's behavior and the operating context:

**Initial Conditions**
At the start of operation, the intruder's vertical position (intruderY) is initialized to 7. The movement counter (dontMove) is initialized to 0.

**Intruder Movement Safety**
The intruder moves on the grid such that in any single step, a coordinate changes by at most 1 unit. When the movement counter is not equal to 4, the intruder must move along only one axis or remain stationary; diagonal movement is not permitted. Specifically, either the X coordinate changes while Y remains constant, the Y coordinate changes while X remains constant, or both coordinates remain constant.

**Obstacle Avoidance**
The intruder must never occupy specific obstacle locations. The coordinates (2, 1), (3, 1), (4, 1), and (5, 1) are forbidden for the intruder at all times.

**Movement Counter Logic**
The environment maintains the `dontMove` counter to track periods of inactivity:
- If the intruder remains completely stationary (both X and Y coordinates remain unchanged), the counter increments by 1 in the next step.
- If the intruder moves horizontally (X changes while Y remains unchanged), the counter resets to 0 in the next step.

**Intruder Reset and Liveness**
The system operates under the assumption that the intruder will periodically reset its position. Whenever the movement counter reaches 4, the intruder must return to the bottom of the grid in the subsequent step (intruderY becomes 7), and the intruder's position must change (it cannot remain completely stationary during this reset). Furthermore, the environment guarantees that the movement counter will reach the value 4 infinitely often throughout the system's operation.

**System Outputs**
The system controls the variables robotX0, robotY0, robotX1, and robotY1. These variables represent the coordinates of the two robots within the defined grid domain.