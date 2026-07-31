

Specification name: TrafficE2

Environment variables:
- carA: boolean
- emergency: boolean
- police: boolean

System variables:
- greenA: boolean

This specification describes a reactive traffic light system. The environment provides inputs regarding car presence, emergency status, and police presence, while the system controls the green light signal for lane A.

**Initial Conditions**
At the start of operation, no car is present at A, and there is no emergency condition. The system must initialize with the light for A not green.

**Environment Assumptions**
The environment is assumed to behave according to the following constraints:
*   Car A must be detected infinitely often.
*   Whenever Car A is present and the light is not green, Car A remains present in the next step.
*   Whenever Car A is present and the light is green, Car A becomes absent in the next step.

**System Guarantees**
The system must satisfy the following requirements:
*   The light for A must be green infinitely often.
*   It must be the case infinitely often that Car A is not present.