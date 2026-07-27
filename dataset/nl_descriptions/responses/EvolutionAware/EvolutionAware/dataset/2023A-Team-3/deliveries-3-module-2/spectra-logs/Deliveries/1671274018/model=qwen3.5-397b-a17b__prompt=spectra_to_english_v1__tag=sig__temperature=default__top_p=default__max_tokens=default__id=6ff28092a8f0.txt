

Specification name: Deliveries

Named domains:
- DimX: Int(0..DX)
- DimY: Int(0..DY)
- Coord: Int(0..DY)

Environment variables:
- lamp0X: DimX
- lamp0Y: DimY
- lamp1X: DimX
- lamp1Y: DimY

System variables:
- robotX0: DimX
- robotY0: DimY
- robotX1: DimX
- robotY1: DimY

The Deliveries specification describes a reactive system involving two robots and two lamps operating within a grid where dimensions DX and DY are both defined as 5. The environment controls the coordinates of the lamps, while the system controls the coordinates of the robots.

The environment must satisfy the following assumptions regarding lamp behavior:

1.  **Lamp Location Constraints:** Neither Lamp 0 nor Lamp 1 is ever located at Y coordinate 0. This restricts lamps from appearing on the ground floor.
2.  **Lamp 0 Movement:** Lamp 0 changes its position if and only if Robot 0 is currently at the exact same coordinates as Lamp 0. Specifically, if Robot 0 is not at Lamp 0's position, Lamp 0 must remain stationary in the next step. If Robot 0 is at Lamp 0's position, Lamp 0 must move to a different position in the next step.
3.  **Lamp 1 Movement:** Lamp 1 changes its position if and only if Robot 1 is currently at the exact same coordinates as Lamp 1. Specifically, if Robot 1 is not at Lamp 1's position, Lamp 1 must remain stationary in the next step. If Robot 1 is at Lamp 1's position, Lamp 1 must move to a different position in the next step.

These requirements ensure that lamps remain stationary until picked up by their assigned robot, at which point they must move. The system controls the robot coordinates within the defined domains.