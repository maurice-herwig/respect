

Specification name: TrafficA3a_repaired_asm

Environment variables:
- carA: boolean
- carB: boolean

System variables:
- greenA: boolean
- greenB: boolean

This specification describes a traffic light controller for two directions, A and B. The environment indicates the presence of cars using boolean inputs, while the system controls the green light signals using boolean outputs.

**Environment Assumptions**
The environment adheres to the following behavioral constraints:
1. Whenever a car is present at A (`carA` is true) and the light for A is not green (`greenA` is false), the car remains present in the next state.
2. Whenever a car is present at B (`carB` is true) and the light for B is not green (`greenB` is false), the car remains present in the next state.
3. Infinitely often, either cars are not present at both A and B simultaneously, or both lights A and B are off.

**System Guarantees**
The system must satisfy the following safety requirement:
1. The lights for A and B must never be green at the same time.