

Specification name: TrafficE2

Environment variables:
- carA: boolean
- carB: boolean
- emergency: boolean
- police: boolean

System variables:
- greenA: boolean
- greenB: boolean

The TrafficE2 specification describes a reactive system controlling two traffic lights, greenA and greenB, based on the presence of cars carA and carB. The environment controls the car presence signals and emergency status, while the system controls the traffic light signals.

In the initial state, the environment ensures that carA, carB, and emergency are all false. The system ensures that both greenA and greenB are initially false.

The environment is assumed to behave according to the following rules regarding car presence. Both carA and carB must appear infinitely often. Additionally, carA must be false infinitely often. Regarding state transitions, if carA is present and greenA is not active, carA remains present in the next step; however, if carA is present and greenA is active, carA becomes absent in the next step. Similarly, if carB is present and greenB is not active, carB remains present in the next step, but if carB is present and greenB is active, carB becomes absent in the next step.

The system must satisfy the following guarantees. Safety requirements dictate that greenA and greenB must never be true simultaneously; if greenA is true, greenB must be false, and if greenB is true, greenA must be false. Liveness requirements mandate that greenA must be true infinitely often and greenB must be true infinitely often. Furthermore, the system must guarantee that carA is false infinitely often.