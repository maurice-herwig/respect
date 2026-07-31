

Specification name: TrafficA1

Environment variables:
- carA: boolean
- carB: boolean

System variables:
- greenA: boolean
- greenB: boolean

The system controls traffic lights for two directions, A and B, based on the presence of cars detected by the environment. The environment variables `carA` and `carB` indicate whether a car is present at direction A or B, respectively. The system variables `greenA` and `greenB` indicate whether the green light is active for direction A or B, respectively.

**Environment Assumptions**
Initially, there is a car at direction A and no car at direction B. Throughout the system's operation, cars must appear infinitely often at direction A, and cars must appear infinitely often at direction B.

**System Guarantees**
Initially, both green lights are off (neither `greenA` nor `greenB` is active). At all times, the green lights for direction A and direction B must not be active simultaneously. Furthermore, if there is no car at direction A, the green light for A must not be active, and if there is no car at direction B, the green light for B must not be active. Regarding liveness, the green light for direction A must be active infinitely often, and the green light for direction B must be active infinitely often.