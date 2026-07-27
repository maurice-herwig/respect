

Specification name: Abcg_arbiter

Environment variables:
- request: boolean[N]

System variables:
- grant: boolean[N]
- a: boolean[N]
- b: boolean[N]
- c: boolean[N]
- state: {S0, S1, S2, S3}[N]

The system manages arbitration for ten clients, indexed from 0 to 9. The environment provides a `request` signal for each client, and the system responds with a `grant` signal. The system also maintains internal boolean signals `a`, `b`, and `c`, and a state variable `state` for each client.

Initially, the `state` for every client is set to `S0`.

The system must satisfy the following safety guarantees at all times:
1.  **Mutual Exclusion:** At any given time, at most one `grant` signal across all clients may be true.
2.  **Signal Propagation:** For each client, the current value of `a` determines the next value of `b`, the current value of `b` determines the next value of `c`, and the current value of `c` determines the next value of `grant`.
3.  **State-Grant Constraint:** If a client's `state` is `S3`, its `grant` signal must be false.
4.  **State Transitions:** For each client, the next state is determined as follows:
    *   If `grant` is true and `request` is true, the next state is `S1`.
    *   If `grant` is true and `request` is false, the next state is `S2`.
    *   If `grant` is false and `request` is false and the current state is not `S0`, the next state is `S3`.
    *   If the current state is `S0` and `grant` is false, the next state remains `S0`.
    *   If `grant` is false and `request` is true, the next state is `S0`.

Additionally, the system must satisfy the following liveness guarantee:
*   For each client, the system must infinitely often be in state `S0`, `S1`, or `S3`.