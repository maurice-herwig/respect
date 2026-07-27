

Specification name: Deliveries

Named domains:
- DimX: Int(0..DX)
- DimY: Int(0..DY)
- Coord: Int(0..DY)

Environment variables:
- p0X: DimX
- p0Y: DimY
- p1X: DimX
- p1Y: DimY

System variables:
- robotX0: DimX
- robotY0: DimY
- robotX1: DimX
- robotY1: DimY

The system controls two robots, Robot 0 and Robot 1, operating on a grid where coordinates range from 0 to 5. The environment provides dynamic target package locations for each robot. The system must coordinate the robots to visit these locations infinitely often.

**Environment Assumptions**
The environment controls the package locations (`p0X`, `p0Y` for Robot 0 and `p1X`, `p1Y` for Robot 1). These locations are subject to the following static constraints at all times:
- The X-coordinates `p0X` and `p1X` are never 0.
- The Y-coordinates `p0Y` and `p1Y` are never 5.

The specification defines internal counters `r0Count` and `r1Count`, each ranging from 0 to 3. Both counters initialize to 0. `r0Count` increments when Robot 0 is at the Package 0 location (where `robotX0 = p0X` and `robotY0 = p0Y`) and resets to 0 when Robot 0 reaches the corner coordinate (5, 5). `r1Count` follows identical logic for Robot 1 and Package 1.

The environment must keep the Package 0 location (`p0X`, `p0Y`) unchanged unless Robot 0 is currently at the Package 0 location and `r0Count` is less than 3. If Robot 0 is at the Package 0 location and `r0Count` is less than 3, the environment must change the Y-coordinate `p0Y` in the next step to a value different from the current `p0Y` and different from 5. Identical rules apply to Package 1 (`p1X`, `p1Y`) based on Robot 1's position and `r1Count`.

**System Guarantees**
The system must ensure that Robot 0 infinitely often reaches the Package 0 location. Similarly, the system must ensure that Robot 1 infinitely often reaches the Package 1 location.