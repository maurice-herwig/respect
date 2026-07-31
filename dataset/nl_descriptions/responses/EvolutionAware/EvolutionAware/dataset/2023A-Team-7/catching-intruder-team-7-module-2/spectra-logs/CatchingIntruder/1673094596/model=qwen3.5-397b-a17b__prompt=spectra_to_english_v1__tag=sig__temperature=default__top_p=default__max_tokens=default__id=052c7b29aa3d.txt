

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

The system operates on a two-dimensional grid where all coordinates are integers between 0 and 7. There is a static obstacle region defined as any position where the vertical coordinate is 1 and the horizontal coordinate is between 2 and 5 inclusive.

**Initial Conditions**
At the start of operation, the system variables are initialized as follows:
- `robotX0` is 0 and `robotY0` is 0.
- `robotX1` is 7 and `robotY1` is 0.
- `intruderY` is 7.

**Movement Dynamics**
At every step of the system execution, the environment and the system must adhere to specific movement constraints for all entities (the intruder, Robot 0, and Robot 1). For each entity, the horizontal and vertical coordinates may change by at most 1 unit between consecutive states (i.e., a coordinate may increase by 1, decrease by 1, or remain the same). Additionally, diagonal movement is prohibited: during any transition, at least one of the two coordinates for an entity must remain stationary. An entity may also choose to remain completely stationary.

**Safety Requirements**
Throughout the operation of the system, the following safety conditions must always hold:
- The position defined by `robotX0` and `robotY0` must never overlap with the obstacle region.
- The position defined by `robotX1` and `robotY1` must never overlap with the obstacle region.
- The position defined by `intruderX` and `intruderY` must never overlap with the obstacle region.