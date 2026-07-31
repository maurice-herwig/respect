

Specification name: TrafficE2

Environment variables:
- carA: boolean
- carB: boolean
- emergency: boolean

System variables:
- greenA: boolean
- greenB: boolean

This specification defines a traffic light controller for two lanes, A and B. The system controls the green light signals for each lane based on the presence of cars and an emergency status signal provided by the environment.

**Environment Assumptions**
The environment manages the car presence sensors and the emergency signal. It is assumed that the emergency condition does not persist indefinitely; the emergency signal will become inactive infinitely often. Regarding vehicle behavior, when there is no emergency, cars wait at red lights and move through green lights. Specifically, if a car is present at a lane while the corresponding light is not green, the car remains present in the next step. Conversely, if a car is present at a lane while the corresponding light is green, the car departs (is no longer present) in the next step.

**System Guarantees**
The system must satisfy safety and liveness requirements regarding the traffic lights. For safety, the lights for lane A and lane B must never be green at the same time. Additionally, if the emergency signal is active, both lights must be red (not green). For liveness, the system must respond to traffic demand. Whenever a car is present at lane A, the light greenA must eventually turn green. Similarly, whenever a car is present at lane B, the light greenB must eventually turn green. These response requirements ensure that cars are not waited upon indefinitely when the system is operational.