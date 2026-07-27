

Specification name: Patrolling

Named domains:
- DimX: Int(0..DX)
- DimY: Int(0..DY)

Environment variables:
- none

System variables:
- robotX: DimX
- robotY: DimY

The system controls the position of a robot using two output variables, `robotX` and `robotY`, which represent the horizontal and vertical coordinates respectively. Both coordinates are integers ranging from 0 to 4. There are no environment-controlled input variables; the system autonomously determines the robot's movement.

The specification defines a specific location called the charging place, which corresponds to the coordinates where `robotX` equals 4 and `robotY` equals 0. The system must satisfy the following guarantees regarding the robot's presence at this location:

1.  **Stability at Charging Place:** Whenever the robot reaches the charging place, it must remain at the charging place for at least 3 consecutive time steps.
2.  **Return to Charging Place:** If the robot remains away from the charging place for 15 consecutive time steps, it must eventually return to the charging place.