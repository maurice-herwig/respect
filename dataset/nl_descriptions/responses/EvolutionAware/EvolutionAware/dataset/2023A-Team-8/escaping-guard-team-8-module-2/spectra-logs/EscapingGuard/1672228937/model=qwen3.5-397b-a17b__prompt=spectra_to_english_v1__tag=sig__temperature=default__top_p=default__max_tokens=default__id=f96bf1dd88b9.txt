

Specification name: EscapingGuard

Named domains:
- Dim: Int(0..D)

Environment variables:
- obstacleUpX: Dim
- obstacleLeftY: Dim

System variables:
- robotX: Dim
- robotY: Dim

The system manages a robot's position on a grid while interacting with an environment-controlled obstacle. Coordination between the robot and the obstacle is governed by an internal system counter named `canMove` that cycles continuously through the values 0, 1, and 2. The constant `D` is defined as 7, establishing the domain for all position coordinates.

Initially, the obstacle is placed at coordinates (0, 0). Throughout operation, the obstacle's coordinates must remain strictly less than 7 (within the range 0 to 6). The obstacle's movement depends on the `canMove` counter. When `canMove` is 0, the obstacle may increment, decrement, or maintain its current coordinates, subject to domain bounds. When `canMove` is greater than 0, the obstacle must remain stationary.

The system must ensure the robot never occupies the positions (2, 2), (2, 3), (2, 4), or (2, 5). The robot's movement is inversely synchronized with the obstacle relative to the `canMove` counter. When `canMove` is 0, the robot must remain stationary. When `canMove` is greater than 0, the robot may increment, decrement, or maintain its current coordinates, subject to domain bounds. All robot coordinates must remain within the defined domain 0 to 7.