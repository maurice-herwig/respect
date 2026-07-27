

Specification name: GridA1

Environment variables:
- robX: Int(0..20)
- robY: Int(0..20)

System variables:
- move: {UP, DOWN, LEFT, RIGHT, STAY}

**Requirements Description**

The system controls a movement command based on position coordinates provided by the environment.

**Initial Conditions**
At the start of operation, the environment sets both `robX` and `robY` to 0.

**Environment Assumptions**
The environment controls the position variables. Whenever the system issues the `UP` move command, the environment ensures that the value of `robY` decreases by 1 in the next state.

**System Guarantees**
The system must always select a move command that respects specific boundary constraints based on the current position. The following restrictions apply at all times:
- If `robX` is 0, the system must not select `LEFT`.
- If `robX` is 4, the system must not select `RIGHT`.
- If `robY` is 0, the system must not select `UP`.
- If `robY` is 4, the system must not select `DOWN`.