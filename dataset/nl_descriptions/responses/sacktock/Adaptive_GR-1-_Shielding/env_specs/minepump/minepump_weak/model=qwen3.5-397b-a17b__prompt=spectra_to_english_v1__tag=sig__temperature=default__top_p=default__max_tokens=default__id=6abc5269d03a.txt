

Specification name: Minepump

Environment variables:
- highwater: boolean
- methane: boolean

System variables:
- pump: boolean

**Requirements Description**

**Initial Conditions**
At the beginning of operation, the environment indicates that the water level is not high and no methane is present. Simultaneously, the system initializes with the pump turned off.

**System Guarantees**
The system must satisfy the following behavior at every step of the interaction:
1. If the high water signal is true and the methane signal is false, the system must turn the pump on in the next step.
2. If the methane signal is true, the system must turn the pump off in the next step.

**Environment Assumptions**
The environment is constrained by the following assumption at every step:
1. If the pump was on in the previous step and remains on in the current step, the high water signal must be false in the next step.