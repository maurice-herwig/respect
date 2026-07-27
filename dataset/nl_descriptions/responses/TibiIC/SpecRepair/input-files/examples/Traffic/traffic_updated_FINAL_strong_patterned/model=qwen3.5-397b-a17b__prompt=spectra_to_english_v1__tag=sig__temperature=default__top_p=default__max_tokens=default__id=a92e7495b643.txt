

Specification name: TrafficE2

Environment variables:
- carA: boolean
- carB: boolean
- emergency: boolean

System variables:
- greenA: boolean
- greenB: boolean

This specification defines the requirements for a traffic light controller managing two lanes, A and B, with an emergency mode. The environment controls the inputs `carA`, `carB`, and `emergency`, while the system controls the outputs `greenA` and `greenB`.

**Environment Assumptions**
The environment guarantees that the `emergency` signal is not permanently active; it will become inactive infinitely often. Car behavior is constrained such that cars wait for a green light. Specifically, if `carA` is true and `greenA` is false, `carA` remains true in the next step. If `carA` is true and `greenA` is true, `carA` becomes false in the next step. The same behavior applies to `carB` and `greenB`.

**System Guarantees**
The system must satisfy the following requirements:
1.  **Safety:** The lights `greenA` and `greenB` must never be green simultaneously. At least one of them must be false at any time.
2.  **Emergency Mode:** If `emergency` is true, both `greenA` and `greenB` must be false.
3.  **Liveness:** The system must respond to traffic requests. Whenever `carA` is present, `greenA` must eventually become true. Whenever `carB` is present, `greenB` must eventually become true.
4.  **Initial Condition:** The system starts in a state where no car requests are pending.