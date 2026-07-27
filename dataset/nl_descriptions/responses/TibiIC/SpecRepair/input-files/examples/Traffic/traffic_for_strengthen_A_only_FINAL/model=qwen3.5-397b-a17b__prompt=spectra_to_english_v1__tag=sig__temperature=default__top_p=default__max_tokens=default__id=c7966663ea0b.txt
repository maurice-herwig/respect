

Specification name: TrafficE2

Environment variables:
- carA: boolean
- emergency: boolean
- police: boolean

System variables:
- greenA: boolean

**Requirements Description**

The TrafficE2 specification defines a reactive system managing traffic flow based on vehicle presence and external conditions. The environment provides inputs indicating whether a car is present (`carA`), whether an emergency is active (`emergency`), and whether police are present (`police`). The system controls the traffic light signal (`greenA`).

**Initial Conditions**
At the start of operation, the environment indicates no car is present (`carA` is false) and no emergency is active (`emergency` is false). The system initializes with the light off (`greenA` is false).

**Environment Assumptions**
The environment is assumed to satisfy the following behaviors:
- A car detection (`carA` is true) must occur infinitely often.
- The police condition (`police` is false) must occur infinitely often.
- If a car is detected (`carA` is true), the light is not green (`greenA` is false), and there is no emergency (`emergency` is false), then the car remains detected in the next step.
- If a car is detected (`carA` is true), the light is green (`greenA` is true), and there is no police presence (`police` is false), then the car clears (becomes false) in the next step.

**System Guarantees**
The system must satisfy the following requirements:
- The light must turn green (`greenA` is true) infinitely often.
- The system must ensure that no car is detected (`carA` is false) infinitely often.