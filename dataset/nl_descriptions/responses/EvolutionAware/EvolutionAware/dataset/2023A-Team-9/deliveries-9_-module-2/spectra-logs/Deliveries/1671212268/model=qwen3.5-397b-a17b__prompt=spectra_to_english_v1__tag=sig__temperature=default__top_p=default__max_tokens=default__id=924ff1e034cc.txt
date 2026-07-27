

Specification name: Deliveries

Named domains:
- DimX: Int(0..DX)
- DimY: Int(0..DY)
- Coord: Int(0..DY)

Environment variables:
- lamp0X: DimX
- lamp0Y: DimY
- lamp1X: DimX
- lamp1Y: DimY

System variables:
- robotX0: DimX
- robotY0: DimY
- robotX1: DimX
- robotY1: DimY

The **Deliveries** specification describes a reactive system involving two robots and two lamps operating on a grid. The environment controls the positions of the lamps, while the system controls the positions of the robots. All coordinates are integers within the defined dimensions.

**Environment Assumptions**
The behavior of the lamps is constrained by the following rules regarding their interaction with the robots:

*   **Lamp 0 Movement:** Whenever Robot 0 arrives at the exact same location as Lamp 0 (meaning `robotX0` equals `lamp0X` and `robotY0` equals `lamp0Y`), the environment must change the vertical position of Lamp 0 in the immediately following step. Specifically, the value of `lamp0Y` in the next state must differ from its current value.
*   **Lamp 1 Stability:** Whenever Robot 1 is not at the same location as Lamp 1, the environment must keep Lamp 1 stationary. Both the horizontal coordinate `lamp1X` and the vertical coordinate `lamp1Y` must remain unchanged in the next state until Robot 1 reaches Lamp 1.