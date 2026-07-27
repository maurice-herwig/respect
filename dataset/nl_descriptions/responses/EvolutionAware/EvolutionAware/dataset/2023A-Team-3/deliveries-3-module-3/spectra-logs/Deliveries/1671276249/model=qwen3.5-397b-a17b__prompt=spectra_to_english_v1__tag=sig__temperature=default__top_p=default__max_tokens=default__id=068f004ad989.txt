

# System Requirements: Deliveries

## System Overview
This specification describes a reactive system controlling two robots operating within a two-dimensional grid. The robots interact with an environment that includes an elevator and package lamps. The system must ensure safe movement, prevent collisions between the robots, and coordinate with the elevator under specific conditions.

## System Interface

Specification name: Deliveries

Named domains:
- DimX: Int(0..DX)
- DimY: Int(0..DY)
- Coord: Int(0..DY)

Environment variables:
- elevatorY: DimY
- lamp0X: DimX
- lamp0Y: DimY
- lamp1X: DimX
- lamp1Y: DimY

System variables:
- robotX0: DimX
- robotY0: DimY
- robotX1: DimX
- robotY1: DimY

## Behavioral Requirements

### Initial Conditions
At the start of system operation, both Robot 0 and Robot 1 must be located at Y-coordinate 0. Their initial X-coordinates are unconstrained.

### Safety Requirements
**Collision Avoidance**
The two robots must never occupy the same position simultaneously. At any point in time, it must not be the case that both the X-coordinates and the Y-coordinates of Robot 0 and Robot 1 are identical.

**Movement Constraints**
For both Robot 0 and Robot 1, the X-coordinate must change by at most one unit per step. Specifically, the next X-coordinate must be equal to the current X-coordinate, one less than the current X-coordinate, or one greater than the current X-coordinate.

**Elevator Interaction**
The robots must coordinate with the elevator's vertical position (`elevatorY`) according to the following rules:

*   **Robot 0:**
    *   If the elevator's next Y-coordinate differs from Robot 0's current Y-coordinate, then Robot 0's next X-coordinate must be 0.
    *   If Robot 0's current X-coordinate is 0, then Robot 0's next Y-coordinate must match the elevator's next Y-coordinate.
*   **Robot 1:**
    *   If the elevator's next Y-coordinate differs from Robot 1's current Y-coordinate, then Robot 1's next X-coordinate must be 0.

### Assumptions and Liveness
There are no active assumptions restricting the environment's behavior, and no liveness requirements specifying that events must occur infinitely often within this specification.