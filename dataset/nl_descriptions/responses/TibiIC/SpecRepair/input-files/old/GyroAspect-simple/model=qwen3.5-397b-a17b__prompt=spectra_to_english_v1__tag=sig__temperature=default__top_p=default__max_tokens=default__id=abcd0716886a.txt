

Specification name: GyroAspect

Environment variables:
- frontDistSense: {CLEAR, BLOCKED}
- backDistSense: {CLEAR, BLOCKED}
- isReady: boolean
- bluetoothCmd: {STP, FWD, BWD, TURN_LEFT, TURN_RIGHT, SWITCH_MODE, SPEED_DOWN, SPEED_UP, NOP }

System variables:
- balancer: {STP, FWD, BWD, TURN_LEFT, TURN_RIGHT}
- balancerSpeed: { SLOW, REGULAR, FAST }
- spec_mode: { AUTO, MANUAL }
- spec_manualCmd: { STP, FWD, BWD, TURN_LEFT, TURN_RIGHT }

**Requirements Description**

The system controls the balancing and movement behavior of a robot based on sensor inputs and operational modes. The following requirements define the initial state, safety constraints, and liveness goals for the system.

**Initial Condition**
Upon startup, the system must initialize the balancer to the stopped state (STP).

**Safety Requirements**
The system must adhere to the following constraints at all times during operation:
1.  **Readiness Constraint:** If the robot is not ready to move (isReady is false), the balancer must be set to stopped (STP).
2.  **Forward Movement Constraint:** The balancer may only be set to move forward (FWD) if the front distance sensor indicates the path is clear (CLEAR).
3.  **Backward Movement Constraint:** The balancer may only be set to move backward (BWD) if the back distance sensor indicates the path is clear (CLEAR).

**Liveness Requirements**
The system must satisfy the following progress condition over infinite operation:
1.  **Auto Mode Progress:** Infinitely often, if the specification mode is set to AUTO, then the balancer must be set to move forward (FWD).