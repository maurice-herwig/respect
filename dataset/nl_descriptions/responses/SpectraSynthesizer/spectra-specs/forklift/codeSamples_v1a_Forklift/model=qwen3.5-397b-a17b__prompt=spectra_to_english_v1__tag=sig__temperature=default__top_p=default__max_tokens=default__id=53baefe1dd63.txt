

Specification name: Forklift

Environment variables:
- obstacle: {BLOCKED, CLEAR}
- atStation: boolean

System variables:
- lMot: {STOP, FWD, BWD}
- rMot: {STOP, FWD, BWD}
- lift: {LIFT, DROP, NIL}

The Forklift system controls the left motor (`lMot`), right motor (`rMot`), and lift mechanism (`lift`) based on the environment's obstacle status (`obstacle`) and station presence (`atStation`).

**Initial Conditions**
Upon startup, both the left motor (`lMot`) and right motor (`rMot`) must be in the STOP state.

**System Guarantees**
The system must satisfy the following requirements:
1.  **Safety:** Whenever the obstacle is BLOCKED, the system must not drive both motors forward simultaneously. Specifically, it is forbidden for `lMot` and `rMot` to both be FWD when `obstacle` is BLOCKED.
2.  **Liveness:** The system must drive both motors forward (`lMot` = FWD and `rMot` = FWD) infinitely often during operation.

**Environment Assumptions**
The system operates under the following assumptions regarding the environment and interaction:
1.  **Obstacle Stability:** If both motors are stopped (`lMot` = STOP and `rMot` = STOP), the obstacle status (`obstacle`) must not change in the subsequent step.
2.  **Response to Backward Motion:** It is assumed that whenever either motor moves backward (`lMot` = BWD or `rMot` = BWD), eventually either the obstacle becomes CLEAR or both motors stop (`lMot` = STOP and `rMot` = STOP). This condition must be satisfied infinitely often.