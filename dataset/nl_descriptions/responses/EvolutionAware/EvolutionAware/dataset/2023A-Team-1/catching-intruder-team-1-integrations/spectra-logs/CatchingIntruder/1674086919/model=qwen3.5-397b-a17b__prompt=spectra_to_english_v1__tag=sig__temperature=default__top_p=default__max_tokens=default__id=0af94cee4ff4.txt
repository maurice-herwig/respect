

Specification name: CatchingIntruder

Named domains:
- Dim: Int(0..D)

Environment variables:
- intruderX: Dim
- intruderY: Dim
- turns: Int(0..3)

System variables:
- robotX0: Dim
- robotY0: Dim
- robotX1: Dim
- robotY1: Dim

The system models an interaction within a bounded two-dimensional grid where the coordinate range is defined by the domain `Dim`, representing integer values from 0 to 7. The environment controls the position of an intruder on this grid using the variables `intruderX` and `intruderY`, and also provides a `turns` counter ranging from 0 to 3. The system controls the positions of two robots, designated as robot 0 and robot 1, using the variables `robotX0`, `robotY0`, `robotX1`, and `robotY1` to specify their respective horizontal and vertical coordinates.