

Specification name: Deliveries

Named domains:
- DimX: Int(0..DX)
- DimY: Int(0..DY)
- Coord: Int(0..DY)

Environment variables:
- elevatorY: DimY

System variables:
- robotX0: DimX
- robotY0: DimY
- robotX1: DimX
- robotY1: DimY

The system models an interaction between two robots and an elevator within a grid bounded by dimensions DX and DY, both defined as 5. The environment controls the vertical position of the elevator, while the system controls the horizontal and vertical positions of two robots.

The elevator operates at a fixed horizontal position of 0. Its vertical position, `elevatorY`, is constrained by environment assumptions. In every step, the elevator may move up by one floor, move down by one floor, or remain at its current floor. Additionally, the environment must ensure that the elevator visits the ground floor (position 0) infinitely often and visits the top floor (position 5) infinitely often.

The system controls the coordinates `robotX0`, `robotY0`, `robotX1`, and `robotY1`, representing the positions of the two robots within the defined dimensions.