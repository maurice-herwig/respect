

Specification name: PatrollingTeam8Module1

Named domains:
- DimX: Int(0..DX)
- DimY: Int(0..DY)
- Dim: Int(0..D)

Environment variables:
- fixedObstacle1: Dim[2]
- fixedObstacle2: Dim[2]
- fixedObstacle3: Dim[2]
- fixedObstacle4: Dim[2]
- fixedObstacle5: Dim[2]
- movingObstacle: Dim[2]

System variables:
- robotX: DimX
- robotY: DimY

This specification defines the behavior of obstacles within a patrolling environment. The environment controls five fixed obstacles and one moving obstacle, while the system controls the robot's coordinates.

The environment must maintain the five fixed obstacles at constant coordinates forever. Specifically, `fixedObstacle1` remains at (1, 1), `fixedObstacle2` at (2, 1), `fixedObstacle3` at (0, 3), `fixedObstacle4` at (3, 3), and `fixedObstacle5` at (3, 4).

The moving obstacle is subject to the following constraints. Initially, its Y-coordinate (`movingObstacle[1]`) is 2. Regarding safety, the X-coordinate (`movingObstacle[0]`) must change by at most 1 unit between consecutive steps; it may increment by 1, decrement by 1, or remain unchanged. Regarding liveness, the moving obstacle's X-coordinate must equal 0 infinitely often and must equal 4 infinitely often, ensuring it visits both ends of the row repeatedly.

The system controls the variables `robotX` and `robotY` within their defined domains.