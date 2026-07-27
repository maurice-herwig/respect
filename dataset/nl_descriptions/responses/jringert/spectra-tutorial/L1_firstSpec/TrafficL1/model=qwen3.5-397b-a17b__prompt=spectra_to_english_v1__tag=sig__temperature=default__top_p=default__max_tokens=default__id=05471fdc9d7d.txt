

Specification name: TrafficL1

Environment variables:
- carA: boolean
- carB: boolean

System variables:
- greenA: boolean
- greenB: boolean

This specification describes a traffic light controller system. The environment controls the boolean inputs `carA` and `carB`, which indicate the presence of vehicles at location A and location B, respectively. The system controls the boolean outputs `greenA` and `greenB`, which indicate whether the green light is active at location A and location B.

Regarding initial conditions, the system must start with both `greenA` and `greenB` set to false. The environment is assumed to begin with `carA` true and `carB` false.

The system must satisfy specific safety and liveness guarantees. As a safety requirement, the lights `greenA` and `greenB` must never be true simultaneously; at any point in time, at least one of them must be false. As a liveness requirement, the system ensures that `greenA` becomes true infinitely often throughout the operation of the system.