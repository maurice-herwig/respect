

Specification name: TrafficA1a

Environment variables:
- carA: boolean
- carB: boolean

System variables:
- greenA: boolean
- greenB: boolean

This specification describes a reactive traffic light controller for two lanes, A and B. The environment controls the input variables `carA` and `carB`, which indicate the presence of a car at each respective lane. The system controls the output variables `greenA` and `greenB`, which indicate whether the traffic light for each lane is green.

**Environment Assumptions**
The environment is assumed to adhere to the following behavior:
1.  **Initial Condition:** Initially, a car is present at lane A (`carA` is true) and no car is present at lane B (`carB` is false).
2.  **Traffic Recurrence:** It is assumed that eventually cars will be present at both lanes simultaneously, and this condition will occur infinitely often throughout the operation.

**System Guarantees**
The system must satisfy the following requirements:
1.  **Initial Condition:** Initially, both traffic lights are red (`greenA` and `greenB` are false).
2.  **Safety Requirements:**
    *   At all times, both lights cannot be green simultaneously.
    *   At all times, if there is no car at lane A, light A must not be green.
    *   At all times, if there is no car at lane B, light B must not be green.
3.  **Liveness Requirements:**
    *   Light A must turn green infinitely often.
    *   Light B must turn green infinitely often.