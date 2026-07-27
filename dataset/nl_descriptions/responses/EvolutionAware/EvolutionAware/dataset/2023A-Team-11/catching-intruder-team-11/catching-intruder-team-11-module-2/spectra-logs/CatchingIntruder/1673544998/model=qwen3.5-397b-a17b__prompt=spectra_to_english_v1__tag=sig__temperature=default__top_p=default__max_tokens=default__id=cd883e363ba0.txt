

Specification name: CatchingIntruder

Named domains:
- Dim: Int(0..D)

Environment variables:
- none

System variables:
- robotX0: Dim
- robotY0: Dim
- robotX1: Dim
- robotY1: Dim
- r1ReachedGround: boolean

The system controls five variables: coordinates `robotX0`, `robotY0`, `robotX1`, `robotY1`, and a status flag `r1ReachedGround`. The coordinate variables are integers ranging from 0 to 7, corresponding to the domain `Dim` where `D` is 7. The flag `r1ReachedGround` is a boolean value.

Initially, `r1ReachedGround` is false.

The system updates `r1ReachedGround` based on the next position of the first entity. If the next values of `robotX0` and `robotY0` are 0 and 7 respectively, then `r1ReachedGround` becomes true in the next state. In all other cases, `r1ReachedGround` retains its current value in the next state.

The system must also satisfy a constraint on the second entity's movement relative to the status flag. Whenever `r1ReachedGround` is false, the next values of `robotX1` and `robotY1` must both be 0.