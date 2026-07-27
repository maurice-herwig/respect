

Specification name: Patrolling

Named domains:
- DimX: Int(0..DX)
- DimY: Int(0..DY)

Environment variables:
- losingPower: boolean

System variables:
- robotX: DimX
- robotY: DimY

The system controls the robot's position on a grid using coordinates `robotX` and `robotY`, where the dimensions DX and DY are both 4. The environment provides a boolean input `losingPower`.

The system maintains a counter, `turnsAtTopRight`, with a range of 0 to 4. This counter initializes to 0. It increments by 1 whenever the robot is located at `robotX = 4` and `robotY = 0`. The counter resets to 0 whenever `robotX` is not 4 and `robotY` is not 4. If the counter reaches its maximum value of 4, it remains at 4.

Whenever the environment sets `losingPower` to true, the system guarantees that the counter `turnsAtTopRight` reaches the value 4 within 20 steps.