

Specification name: Arbiter

Environment variables:
- a: boolean
- r1: boolean
- r2: boolean

System variables:
- g1: boolean
- g2: boolean

**Requirements Description**

The system functions as an arbiter that manages two grant outputs, `g1` and `g2`, based on two request inputs, `r1` and `r2`, and an enable input `a`. The variables `a`, `r1`, and `r2` are controlled by the environment, while `g1` and `g2` are controlled by the system.

**Environment Assumptions**
The environment must ensure that the enable signal `a` becomes true infinitely often throughout the system's operation. There are no other specified restrictions on the behavior of the request signals `r1` and `r2`.

**System Guarantees**
The system must satisfy the following requirements whenever the environment satisfies its assumptions:

1.  **Request Response:** The system must respond to each request signal. Whenever `r1` is true, the system must eventually assert `g1`. Similarly, whenever `r2` is true, the system must eventually assert `g2`. This response requirement is active from the initial state of the system.
2.  **Enable Constraint:** The grant signals are gated by the enable signal `a`. If `a` is false, the system must not assert either grant; both `g1` and `g2` must be false whenever `a` is false.
3.  **Mutual Exclusion:** The system must never assert both grant signals simultaneously. At any point in time, at most one of `g1` or `g2` may be true.

**Initial Conditions**
The internal logic tracking request responses initializes in an idle state, ensuring that the response guarantees apply from the very beginning of execution.