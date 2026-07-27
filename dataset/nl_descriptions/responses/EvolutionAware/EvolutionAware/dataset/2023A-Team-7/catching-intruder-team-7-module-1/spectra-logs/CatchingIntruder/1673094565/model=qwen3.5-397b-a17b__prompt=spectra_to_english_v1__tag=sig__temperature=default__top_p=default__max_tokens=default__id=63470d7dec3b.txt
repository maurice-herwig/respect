

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

The system controls two robots, Robot 0 and Robot 1, operating on a two-dimensional grid where coordinates are integers ranging from 0 to 7. The environment controls the position of an intruder on the same grid.

**Environment Assumptions**
Initially, the intruder's Y-coordinate is 7. At every step, the intruder must adhere to grid movement constraints: the intruder may change its X-coordinate or Y-coordinate by at most 1, or remain stationary. Diagonal movement is prohibited; if the intruder changes one coordinate, the other must remain unchanged.

**System Guarantees**
Initially, Robot 0 is positioned at coordinates (0, 0), and Robot 1 is positioned at coordinates (7, 0). At every step, both robots must adhere to the same movement constraints as the intruder. Each robot may change its X-coordinate or Y-coordinate by at most 1, or remain stationary. Diagonal movement is prohibited for the robots; if a robot changes one coordinate, the other must remain unchanged.