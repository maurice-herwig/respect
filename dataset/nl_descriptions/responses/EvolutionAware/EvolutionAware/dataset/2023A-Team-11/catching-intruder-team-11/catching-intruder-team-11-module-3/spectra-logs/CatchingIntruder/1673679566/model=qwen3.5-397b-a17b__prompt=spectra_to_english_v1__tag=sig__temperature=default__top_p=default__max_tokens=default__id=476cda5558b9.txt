

Specification name: CatchingIntruder

Named domains:
- Dim: Int(0..D)

Environment variables:
- intruderX: Dim
- intruderY: Dim
- StaysCounter: Dim

System variables:
- robotX0: Dim
- robotY0: Dim
- robotX1: Dim
- robotY1: Dim

**Requirements Description**

The system operates within a grid where all spatial coordinates and counter values are integers ranging from 0 to 7. The environment contains four fixed obstacles located at coordinates (2,1), (3,1), (4,1), and (5,1).

The environment controls the intruder's position using variables `intruderX` and `intruderY`, and manages a timing variable `StaysCounter`. The system controls the positions of two robots, defined by coordinates (`robotX0`, `robotY0`) and (`robotX1`, `robotY1`).

**Environment Assumptions**

The environment must satisfy the following constraints regarding the `StaysCounter` and the intruder's position:

1.  **Initial Condition:** Upon system initialization, `StaysCounter` must be set to 0.
2.  **Counter Update:** At every step, the value of `StaysCounter` must either increment by 1 or reset to 0.
3.  **Liveness Requirement:** The value of `StaysCounter` must reach at least 4 infinitely often throughout the system execution.
4.  **Forced Reset and Movement:** Whenever `StaysCounter` equals 4, the environment must ensure that in the next step, `StaysCounter` resets to 0 and the intruder's Y-coordinate (`intruderY`) is set to 7.