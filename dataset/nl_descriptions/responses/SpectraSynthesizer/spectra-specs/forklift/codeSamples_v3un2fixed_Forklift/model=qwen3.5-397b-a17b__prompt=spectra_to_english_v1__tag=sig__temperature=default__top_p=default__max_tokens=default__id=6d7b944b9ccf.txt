

Specification name: Forklift

Environment variables:
- obstacle: {BLOCKED, CLEAR}
- emgOff: boolean

System variables:
- lMot: {STOP, FWD, BWD}
- rMot: {STOP, FWD, BWD}

The Forklift system controls the left and right motors based on obstacle detection and emergency signals. The environment provides the obstacle status and emergency off signal, while the system determines the motor states.

**Environment Assumptions**
The environment is assumed to behave according to the following constraints:
1.  **Obstacle Stability:** If both motors are stopped, the obstacle status must remain unchanged in the next step.
2.  **Response to Backward Movement:** The environment is assumed to ensure that the condition "the obstacle is CLEAR or both motors are STOP" holds infinitely often. Additionally, whenever either motor moves backward, this condition must hold in the immediately following step.

**System Guarantees**
The system must satisfy the following requirements:
1.  **Motor Stop State:** The system must maintain both motors in the STOP state.
2.  **Obstacle Safety:** Whenever the obstacle is BLOCKED, the system must not drive both motors forward simultaneously.
3.  **Emergency Safety:** Whenever the emergency off signal is active, both motors must be stopped.
4.  **Liveness:** Infinitely often, either both motors must move forward simultaneously or the emergency off signal must be active.