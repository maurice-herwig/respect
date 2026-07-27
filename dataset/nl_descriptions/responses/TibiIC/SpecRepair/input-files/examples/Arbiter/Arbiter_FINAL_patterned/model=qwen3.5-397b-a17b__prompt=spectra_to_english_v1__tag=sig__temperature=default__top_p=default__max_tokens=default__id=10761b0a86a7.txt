

Specification name: Arbiter

Environment variables:
- a: boolean
- r1: boolean
- r2: boolean

System variables:
- g1: boolean
- g2: boolean

The system functions as an arbiter that manages two request signals, `r1` and `r2`, and produces two corresponding grant signals, `g1` and `g2`. The environment controls the input variables `a`, `r1`, and `r2`, while the system controls the output variables `g1` and `g2`.

**Environment Assumptions**
The environment must ensure that the signal `a` becomes true infinitely often throughout the system operation.

**System Guarantees**
The system must satisfy the following requirements whenever the environment satisfies its assumptions:

1.  **Abort Condition:** Whenever the signal `a` is false, both grant outputs `g1` and `g2` must be false.
2.  **Mutual Exclusion:** The grant outputs `g1` and `g2` must never be true simultaneously.
3.  **Request Response:** The system must respond to each request signal (`r1` and `r2`) with its corresponding grant signal (`g1` and `g2`, respectively) according to the following behavior pattern:
    *   **Initial State:** The system starts in an idle state.
    *   **Idle State Behavior:** While in the idle state, if the request is false, the system remains idle. If the request is true and the grant is also true, the system remains idle. If the request is true but the grant is false, the system transitions to a pending state.
    *   **Pending State Behavior:** While in the pending state, if the grant is false, the system remains pending. If the grant becomes true, the system returns to the idle state.
    *   **Liveness:** The system must return to the idle state infinitely often. This ensures that if the system enters the pending state due to a request without an immediate grant, the corresponding grant must eventually occur.