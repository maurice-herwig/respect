

Specification name: TrafficE2

Environment variables:
- carA: boolean
- carB: boolean
- emergency: boolean

System variables:
- greenA: boolean
- greenB: boolean

The TrafficE2 specification defines a reactive system that controls traffic lights for two roads based on environmental inputs. The environment provides three boolean inputs: `carA` indicates the presence of a car on road A, `carB` indicates the presence of a car on road B, and `emergency` indicates an emergency status. The system controls two boolean outputs: `greenA` activates the green light for road A, and `greenB` activates the green light for road B.

The specification assumes the following about the environment:
- Cars will appear on road A infinitely often.
- Cars will appear on road B infinitely often.

The system must satisfy the following guarantees:
- **Safety:** It must always be the case that the green lights for road A and road B are not active simultaneously. Additionally, whenever the `emergency` signal is true, both `greenA` and `greenB` must be false.
- **Liveness:** It must be the case infinitely often that either `greenA` is true or `emergency` is true. Similarly, it must be the case infinitely often that either `greenB` is true or `emergency` is true.