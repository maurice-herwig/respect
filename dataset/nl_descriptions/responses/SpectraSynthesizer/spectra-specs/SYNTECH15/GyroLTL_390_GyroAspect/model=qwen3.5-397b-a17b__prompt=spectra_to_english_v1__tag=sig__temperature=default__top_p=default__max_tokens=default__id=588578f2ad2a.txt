

Specification name: GyroAspect

Environment variables:
- distSense: {CLEAR, BLOCKED}
- isReady: boolean

System variables:
- balancer: {STP, FWD, BWD, TURN_LEFT, TURN_RIGHT}

This specification describes a reactive system controlling a balancer based on distance sensing and readiness status. The environment provides sensor data and readiness signals, while the system controls the balancer's movement actions.

**Environment Assumptions**
The environment behaves according to the following constraints:
- Initially, the system is not ready (`isReady` is false).
- The system eventually becomes ready and remains ready forever. Once `isReady` becomes true, it stays true in all subsequent steps.
- The environment adheres to a response protocol regarding distance sensing and balancer maneuvers. An internal response flag is initially true. In every step, this flag is true in the next state if either the distance sensor reports `CLEAR`, or the flag was already true and the balancer does not perform a maneuver (where a maneuver is defined as any action other than `FWD` or `STP`). The environment ensures this internal flag is true infinitely often.

**System Guarantees**
The system must satisfy the following requirements:

*Initial Conditions*
- Initially, the balancer must be stopped (`STP`).

*Safety Requirements*
- Whenever the system is not ready, the balancer must be stopped (`STP`).
- If the distance sensor reports `BLOCKED` and the system is ready, the balancer must not move forward (`FWD`).
- If the distance sensor reports `CLEAR` and the system is ready, the balancer must move forward (`FWD`).
- If the balancer is currently moving forward (`FWD`), it must not turn left (`TURN_LEFT`) or turn right (`TURN_RIGHT`) in the next step.

*Next-State Requirements*
- If the distance sensor reports `BLOCKED`, the balancer is currently stopped (`STP`), and the system is ready, the balancer must not remain stopped (`STP`) in the next step.

*Liveness Requirements*
- The balancer must move forward (`FWD`) infinitely often.