

The Deliveries specification describes a reactive system involving two robots interacting with an environment containing an elevator and two lamps. The system controls the positions of the robots, while the environment controls the positions of the elevator and the lamps.

The elevator operates at a fixed X coordinate of 0. Its Y coordinate changes by at most one unit per step, meaning it can move up, move down, or remain stationary. The elevator is required to visit the ground floor (Y=0) and the top floor (Y=5) infinitely often.

The environment provides two lamps, Lamp 0 and Lamp 1. Neither lamp is ever located at Y=0. The lamps remain stationary unless picked up by their corresponding robot. Lamp 0 remains stationary unless Robot 0 is at the same coordinates. Lamp 1 remains stationary unless Robot 1 is at the same coordinates. When Robot 0 is at the same coordinates as Lamp 0, Lamp 0's Y coordinate must change in the next step. Similarly, when Robot 1 is at the same coordinates as Lamp 1, Lamp 1's Y coordinate must change in the next step.

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