

Specification name: TrafficE2

Environment variables:
- car: boolean
- emergency: boolean
- police: boolean

System variables:
- green: boolean

**Requirements Description**

**Overview**
The system controls a traffic light signal (`green`) based on inputs regarding vehicle presence (`car`), emergency status (`emergency`), and police presence (`police`). The system must manage the light to ensure traffic flow while adhering to specific environmental constraints.

**Environment Assumptions**
The environment is assumed to behave according to the following rules:
1.  **Police Presence:** Police presence is not permanent; there will be infinitely many time steps where no police are present.
2.  **Car Behavior at Red:** If a car is present, the light is not green, and there is no emergency, the car will remain present in the next time step.
3.  **Car Behavior at Green:** If a car is present, the light is green, and no police are present, the car will leave (be absent) in the next time step.

**System Guarantees**
The system must satisfy the following requirements:
1.  **Traffic Clearing:** The system must ensure that the road becomes empty of cars infinitely often.
2.  **Response to Cars:** The system must respond to car presence by eventually turning the light green. This requirement is enforced by an internal monitoring state machine with the following behavior:
    *   **Initial Condition:** The monitoring state initializes to S0.
    *   **Safety Transitions:**
        *   If the state is S0, and either no car is present or both the car is present and the light is green, the state remains S0.
        *   If the state is S0, and a car is present while the light is not green, the state transitions to S1.
        *   If the state is S1, and the light is green, the state transitions to S0.
        *   If the state is S1, and the light is not green, the state remains S1.
    *   **Liveness:** The monitoring state must return to state S0 infinitely often. This ensures that if a car is present without the light being green (entering state S1), the system must eventually set the light to green to return to state S0.