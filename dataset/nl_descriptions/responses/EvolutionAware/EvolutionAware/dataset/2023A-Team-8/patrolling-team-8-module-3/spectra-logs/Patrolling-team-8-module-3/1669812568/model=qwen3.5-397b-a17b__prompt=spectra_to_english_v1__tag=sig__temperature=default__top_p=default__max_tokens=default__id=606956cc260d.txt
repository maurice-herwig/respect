

Specification name: PatrollingTeam8Module3

Named domains:
- DimX: Int(0..DX)
- DimY: Int(0..DY)

Environment variables:
- none

System variables:
- robotX: DimX
- robotY: DimY

The system controls the position of a robot using two output variables: `robotX` representing the horizontal coordinate and `robotY` representing the vertical coordinate. Both coordinates are integers ranging from 0 to 4. There are no environment-controlled input variables.

The specification defines the charger location as the position where `robotX` is 4 and `robotY` is 0. The system must satisfy the following behavioral requirements:

1.  **Visitation Requirement:** The robot must visit the charger location infinitely often during operation.
2.  **Charging Duration Requirement:** Once the robot arrives at the charger location, it must remain at that location for at least 4 consecutive states. Specifically, if the robot is at the charger and has not yet remained there for 4 states, it is required to stay at the charger in the next state. The robot is only permitted to leave the charger location after satisfying this minimum duration.

There are no assumptions restricting the environment behavior. The system must guarantee the stated behaviors regardless of environmental conditions.