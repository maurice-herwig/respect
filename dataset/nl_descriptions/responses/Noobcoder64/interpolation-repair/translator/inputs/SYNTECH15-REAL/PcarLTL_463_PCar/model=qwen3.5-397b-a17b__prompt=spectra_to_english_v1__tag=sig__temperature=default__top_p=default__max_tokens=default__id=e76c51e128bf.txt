

Specification name: PCar

Environment variables:
- obstacle: {CLEAR, BLOCKED, OBJECT}
- sideSense: {CLEAR,P_O, BLOCKED}

System variables:
- throttle: {FWD, BWD, STOP}
- steer: {RIGHT,LEFT, CENTER}

**Requirements Description**

The PCar specification defines the behavior of a vehicle controller interacting with environmental sensors. The environment provides input regarding obstacles and side conditions, while the system controls the throttle and steering.

**Environment Assumptions**
The environment must adhere to the following constraints:
1. Whenever the system sets the throttle to BWD, the environment must ensure that the obstacle becomes CLEAR in the next step.
2. Whenever the system sets the throttle to FWD and the steer to CENTER while the sideSense is BLOCKED, the environment must eventually change the sideSense to CLEAR.

**System Guarantees**
The system must satisfy the following requirements:
1. **Safety:** Whenever the obstacle is BLOCKED, the throttle must not be FWD.
2. **Safety:** Whenever the obstacle is CLEAR and the sideSense is CLEAR, the steer must be CENTER.
3. **Liveness:** The system must infinitely often set the throttle to FWD and the steer to CENTER.