

Specification name: TrafficE2

Environment variables:
- carA: boolean
- emergency: boolean
- police: boolean

System variables:
- greenA: boolean

The system controls the traffic signal `greenA` based on environmental inputs `carA`, `emergency`, and `police`. At the start of operation, no car is detected (`carA` is false), no emergency is active (`emergency` is false), and the signal is red (`greenA` is false).

The environment is assumed to behave according to the following constraints. A car detection (`carA`) must occur infinitely often. The `police` signal must be false infinitely often. Regarding vehicle movement, if a car is detected (`carA` is true) while the signal is red (`greenA` is false), the car remains detected in the next step. If a car is detected while the signal is green (`greenA` is true), the car clears and becomes undetected (`carA` becomes false) in the next step.

The system must satisfy the following guarantees. The signal `greenA` must turn true infinitely often. Additionally, the system must ensure that periods where no car is detected (`carA` is false) occur infinitely often.