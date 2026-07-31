

Specification name: Patrolling

Named domains:
- DimX: Int(0..DX)
- DimY: Int(0..DY)

Environment variables:
- movingObstacleX: DimX
- movingObstacleY: DimY

System variables:
- robotX: DimX
- robotY: DimY

The system operates on a two-dimensional grid where the horizontal dimension ranges from 0 to DX and the vertical dimension ranges from 0 to DY. The system controls the variables `robotX` and `robotY`, which represent the robot's coordinates on the grid. The environment controls the variables `movingObstacleX` and `movingObstacleY`, which represent the coordinates of a moving obstacle. All coordinate variables are integers constrained within the defined grid dimensions.