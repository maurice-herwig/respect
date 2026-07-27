

Specification name: TrafficL1

Environment variables:
- carA: boolean
- carB: boolean

System variables:
- greenA: boolean
- greenB: boolean

The system controls the traffic light signals `greenA` and `greenB`, while the environment provides inputs `carA` and `carB` indicating the presence of cars.

**Initial Conditions**
At the start of operation, the system must set both `greenA` and `greenB` to false. The environment is assumed to begin with `carA` true and `carB` false.

**Safety Requirements**
The system must guarantee that `greenA` and `greenB` are never true simultaneously.

**Liveness Requirements**
The system must ensure that `greenA` becomes true infinitely often. The environment is assumed to provide traffic such that `carA` becomes true infinitely often and `carB` becomes true infinitely often.